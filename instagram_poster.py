"""
Instagram Automated Poster
Posts gaming stats to Instagram on Monday, Wednesday, Friday at 9 PM PST
Optimized for AWS Lambda execution

Features:
- Multi-game support (not just one game)
- Trendy, concise captions with game-specific hashtags
- @ mentions for game accounts
- No-duplicate system even during dry periods (1+ months)
- Holiday theme integration (exact date only)
- Colored title/subtitle using theme colors
- Fira Code font throughout
- Consistent styling with generate_bar_chart

Priority Logic:
1. If games played TODAY → Stats of the day or anomaly
2. If games played YESTERDAY → Stats from yesterday or anomaly
3. Else → Historical records across ALL games (no duplicates)

Size: 1080x1440 (Instagram portrait format)
Player: player_id=1 only
"""

import os
import sys
import boto3
import time
from datetime import datetime, timedelta
import random
import io
import requests
import hashlib
import logging

# Import utilities (these will be in the Lambda package)
from utils.chart_utils import abbreviate_stat, format_large_number, load_custom_fonts, should_use_log_scale
from utils.holiday_themes import get_themed_colors, is_exact_holiday
from utils.gcs_utils import upload_instagram_poster_to_gcs
from utils.game_handles_utils import get_game_handle, get_game_hashtags

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DB_NAME = os.environ.get("DB_NAME", "game_stats_tracker")
REDSHIFT_WORKGROUP = os.environ.get("REDSHIFT_WORKGROUP")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-1")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")

# Constants
PLAYER_ID = 1
TIMEZONE_STR = os.environ.get("TIMEZONE", "America/Los_Angeles")
INSTAGRAM_IMAGE_SIZE = (1080, 1440)

# Load Fira Code fonts for Instagram posts
load_custom_fonts()

# Set matplotlib style to match generate_bar_chart
sns.set_style("darkgrid")
plt.rcParams['figure.facecolor'] = '#1a1a1a'
plt.rcParams['axes.facecolor'] = '#2d2d2d'
plt.rcParams['text.color'] = 'white'
plt.rcParams['axes.labelcolor'] = 'white'
plt.rcParams['xtick.color'] = 'white'
plt.rcParams['ytick.color'] = 'white'
plt.rcParams['grid.color'] = '#404040'
plt.rcParams['font.family'] = 'Fira Code'  # Explicitly set Fira Code
plt.rcParams['font.size'] = 18

# ============================================================================
# REDSHIFT DATA API CLIENT (Lambda optimized, no VPC needed)
# ============================================================================

# Global client (Lambda reuses this across invocations)
redshift_client = None


def get_redshift_client():
    """Get or create Redshift Data API client."""
    global redshift_client
    if redshift_client is None:
        redshift_client = boto3.client('redshift-data', region_name=AWS_REGION)
    return redshift_client


def execute_query(sql, parameters=None):
    """
    Execute a SQL query via Redshift Data API and return results.

    Args:
        sql: SQL string. Use :param_name for named parameters.
        parameters: list of {'name': str, 'value': str} dicts, or None.

    Returns:
        list of rows, each row a list of field dicts.
    """
    client = get_redshift_client()

    kwargs = {
        'WorkgroupName': REDSHIFT_WORKGROUP,
        'Database': DB_NAME,
        'Sql': sql,
    }
    if parameters:
        kwargs['Parameters'] = parameters

    response = client.execute_statement(**kwargs)
    statement_id = response['Id']

    # Poll until finished
    while True:
        status_response = client.describe_statement(Id=statement_id)
        status = status_response['Status']

        if status == 'FINISHED':
            break
        elif status in ('FAILED', 'ABORTED'):
            error = status_response.get('Error', 'Unknown error')
            raise Exception(f"Query failed [{status}]: {error}")

        time.sleep(0.5)

    if status_response.get('HasResultSet'):
        result = client.get_statement_result(Id=statement_id)
        return result.get('Records', [])

    return []


def get_field_value(field):
    """Extract typed value from a Redshift Data API field dict."""
    if field.get('isNull'):
        return None
    if 'stringValue' in field:
        return field['stringValue']
    if 'longValue' in field:
        return field['longValue']
    if 'doubleValue' in field:
        return field['doubleValue']
    if 'booleanValue' in field:
        return field['booleanValue']
    return None


# ============================================================================
# DUPLICATE PREVENTION (Lambda-compatible storage)
# ============================================================================

def get_posted_content_hash():
    """
    Get hash of previously posted content to prevent duplicates.
    Uses /tmp directory in Lambda (persists during container lifetime).

    Returns:
        set: Set of content hashes that have been posted
    """
    hash_file = '/tmp/instagram_post_hashes.txt'

    if not os.path.exists(hash_file):
        return set()

    try:
        with open(hash_file, 'r') as f:
            hashes = set(line.strip() for line in f if line.strip())
        logger.info(f"📝 Loaded {len(hashes)} previously posted hashes")
        return hashes
    except Exception as e:
        logger.warning(f"⚠️ Could not load hashes: {e}")
        return set()


def save_content_hash(content_hash):
    """Save content hash to prevent future duplicates"""
    hash_file = '/tmp/instagram_post_hashes.txt'

    try:
        with open(hash_file, 'a') as f:
            f.write(f"{content_hash}\n")
        logger.info(f"✅ Saved content hash: {content_hash[:8]}...")
    except Exception as e:
        logger.warning(f"⚠️ Could not save content hash: {e}")


def generate_content_hash(stats, game_name, date_str=None):
    """Generate unique hash for content to detect duplicates"""
    content = f"{game_name}_{stats}_{date_str or 'historical'}"
    return hashlib.md5(content.encode()).hexdigest()


# ============================================================================
# DATABASE QUERY FUNCTIONS
# ============================================================================

def check_games_on_date(player_id, target_date):
    """Check if player has games on a specific date"""
    records = execute_query(
        """
        SELECT COUNT(DISTINCT stat_id)
        FROM fact.fact_game_stats
        WHERE player_id = :player_id
        AND CAST(CONVERT_TIMEZONE(:timezone, played_at) AS DATE) = :target_date;
        """,
        [
            {'name': 'player_id', 'value': str(player_id)},
            {'name': 'timezone', 'value': TIMEZONE_STR},
            {'name': 'target_date', 'value': str(target_date)},
        ]
    )
    count = get_field_value(records[0][0]) if records else 0
    return count > 0


def get_all_games_for_player(player_id):
    """Get all games player has played"""
    records = execute_query(
        """
        SELECT DISTINCT g.game_id, g.game_name, g.game_installment
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = :player_id
        ORDER BY g.game_name;
        """,
        [{'name': 'player_id', 'value': str(player_id)}]
    )

    games = []
    for row in records:
        games.append({
            'game_id': get_field_value(row[0]),
            'game_name': get_field_value(row[1]),
            'game_installment': get_field_value(row[2]),
        })
    return games


def get_player_info(player_id):
    """Get player information"""
    records = execute_query(
        """
        SELECT player_name
        FROM dim.dim_players
        WHERE player_id = :player_id;
        """,
        [{'name': 'player_id', 'value': str(player_id)}]
    )
    return get_field_value(records[0][0]) if records else None


def get_stats_for_date(player_id, game_id, target_date):
    """Get stats for a specific date and game"""
    records = execute_query(
        """
        SELECT
            f.stat_type,
            f.stat_value
        FROM fact.fact_game_stats f
        WHERE f.player_id = :player_id
        AND f.game_id = :game_id
        AND CAST(CONVERT_TIMEZONE(:timezone, f.played_at) AS DATE) = :target_date
        ORDER BY f.stat_value DESC
        LIMIT 5;
        """,
        [
            {'name': 'player_id', 'value': str(player_id)},
            {'name': 'game_id', 'value': str(game_id)},
            {'name': 'timezone', 'value': TIMEZONE_STR},
            {'name': 'target_date', 'value': str(target_date)},
        ]
    )
    return [(get_field_value(row[0]), get_field_value(row[1])) for row in records]


def get_stats_for_date_all_games(player_id, target_date):
    """Get stats for all games on a specific date"""
    records = execute_query(
        """
        SELECT
            g.game_name,
            g.game_installment,
            f.stat_type,
            f.stat_value
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = :player_id
        AND CAST(CONVERT_TIMEZONE(:timezone, f.played_at) AS DATE) = :target_date
        ORDER BY f.stat_value DESC;
        """,
        [
            {'name': 'player_id', 'value': str(player_id)},
            {'name': 'timezone', 'value': TIMEZONE_STR},
            {'name': 'target_date', 'value': str(target_date)},
        ]
    )

    return [{
        'game': get_field_value(row[0]),
        'installment': get_field_value(row[1]),
        'stat': get_field_value(row[2]),
        'value': get_field_value(row[3]),
    } for row in records]


def detect_anomalies(player_id, game_id, target_date):
    """Detect statistical anomalies for a specific date"""
    records = execute_query(
        """
        WITH daily_stats AS (
            SELECT
                f.stat_type,
                f.stat_value,
                AVG(f.stat_value) OVER (PARTITION BY f.stat_type) as avg_value,
                STDDEV(f.stat_value) OVER (PARTITION BY f.stat_type) as stddev_value
            FROM fact.fact_game_stats f
            WHERE f.player_id = :player_id
            AND f.game_id = :game_id
            AND CAST(CONVERT_TIMEZONE(:timezone, f.played_at) AS DATE) = :target_date
        )
        SELECT
            stat_type,
            stat_value,
            avg_value,
            stddev_value,
            (stat_value - avg_value) / NULLIF(stddev_value, 0) as z_score
        FROM daily_stats
        WHERE ABS((stat_value - avg_value) / NULLIF(stddev_value, 0)) > 2
        ORDER BY ABS((stat_value - avg_value) / NULLIF(stddev_value, 0)) DESC
        LIMIT 3;
        """,
        [
            {'name': 'player_id', 'value': str(player_id)},
            {'name': 'game_id', 'value': str(game_id)},
            {'name': 'timezone', 'value': TIMEZONE_STR},
            {'name': 'target_date', 'value': str(target_date)},
        ]
    )

    anomalies = []
    for row in records:
        stat = get_field_value(row[0])
        value = get_field_value(row[1])
        avg = get_field_value(row[2])
        stddev = get_field_value(row[3])
        z_score = get_field_value(row[4])
        anomalies.append({
            'stat': stat,
            'value': value,
            'avg': avg,
            'stddev': stddev,
            'z_score': z_score,
            'description': f"{stat}: {float(value):.1f} (avg: {float(avg):.1f}, z-score: {float(z_score):.2f})"
        })
    return anomalies


def get_historical_records_all_games(player_id, posted_hashes, limit=10):
    """
    Get interesting historical records across ALL games.
    Excludes previously posted content to prevent duplicates.
    """
    fetch_limit = limit * 2
    records = execute_query(
        f"""
        WITH ranked_stats AS (
            SELECT
                g.game_name,
                g.game_installment,
                f.stat_type,
                MAX(f.stat_value) as max_value,
                MAX(CAST(CONVERT_TIMEZONE(:timezone, f.played_at) AS DATE)) as best_date
            FROM fact.fact_game_stats f
            JOIN dim.dim_games g ON f.game_id = g.game_id
            WHERE f.player_id = :player_id
            GROUP BY g.game_name, g.game_installment, f.stat_type
        )
        SELECT
            game_name,
            game_installment,
            stat_type,
            max_value,
            best_date
        FROM ranked_stats
        ORDER BY max_value DESC
        LIMIT {fetch_limit};
        """,
        [
            {'name': 'timezone', 'value': TIMEZONE_STR},
            {'name': 'player_id', 'value': str(player_id)},
        ]
    )

    result = []
    for row in records:
        game_name = get_field_value(row[0])
        game_installment = get_field_value(row[1])
        stat_name = get_field_value(row[2])
        max_value = get_field_value(row[3])
        best_date_str = get_field_value(row[4])

        # Parse date string returned by Data API (format: 'YYYY-MM-DD')
        best_date = datetime.strptime(best_date_str[:10], '%Y-%m-%d').date() if best_date_str else None

        content_hash = generate_content_hash(
            [(stat_name, max_value)],
            game_name,
            best_date.strftime('%Y-%m-%d') if best_date else 'unknown'
        )

        if content_hash in posted_hashes:
            continue

        result.append({
            'game': game_name,
            'installment': game_installment,
            'stat': stat_name,
            'value': max_value,
            'date': best_date,
            'hash': content_hash
        })

        if len(result) >= limit:
            selected = random.sample(result, min(limit, len(result)))
            return selected

    return result


# ============================================================================
# CAPTION GENERATION
# ============================================================================

def generate_trendy_caption(post_type, stats, game_info, player_name, day_of_week, anomalies):
    """
    Generate trendy caption with game-specific handle and hashtags.
    Now uses game_handles_utils for centralized social media data.

    Args:
        post_type: str ('daily', 'recent', 'historical')
        stats: list of tuples [(stat_name, value), ...]
        game_info: dict {'game_name': str, 'game_installment': str or None}
        player_name: str
        day_of_week: str
        anomalies: list of dicts [{'description': str}, ...]

    Returns:
        str: Caption text for Instagram
    """
    from utils.holiday_themes import get_themed_colors

    game_name = game_info['game_name']
    game_installment = game_info.get('game_installment')
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name

    # Get game handle for Instagram
    game_handle = get_game_handle(game_name, platform='instagram')

    # Get game-specific hashtags for Instagram
    game_hashtags = get_game_hashtags(game_name, platform='instagram')

    # Determine hashtag based on day
    day_hashtags = {
        'Monday': '#MondayMotivation #MondayUpdate',
        'Tuesday': '#TuesdayVibes #GamingTuesday',
        'Wednesday': '#WednesdayUpdate #MidweekGrind',
        'Thursday': '#ThrowbackThursday #GamingThursday',
        'Friday': '#FridayFeeling #WeekendReady',
        'Saturday': '#SaturdayGaming #WeekendVibes',
        'Sunday': '#SundayFunday #SundayGaming'
    }

    day_tag = day_hashtags.get(day_of_week, '#GamingUpdate')

    # Build the main caption content
    if post_type == 'daily':
        emoji = "🔥"
        hook = f"{emoji} Today's {full_game_name} Session {day_tag} {emoji}"
    elif post_type == 'recent':
        emoji = "📊"
        hook = f"{emoji} Yesterday's {full_game_name} Highlights {day_tag} {emoji}"
    else:  # historical
        emoji = "🏆"
        hook = f"{emoji} {full_game_name} All-Time Records {day_tag} {emoji}"

    caption_lines = [hook, ""]

    # Add top stats (limit to top 3 for brevity)
    for stat_name, stat_value in stats[:3]:
        caption_lines.append(f"• {stat_name}: {stat_value}")

    caption_lines.append("")

    # Add anomaly callouts if present
    if anomalies:
        if post_type in ['daily', 'recent']:
            caption_lines.append("⚡ Notable:")
            for anomaly in anomalies[:2]:  # Limit to 2 for brevity
                caption_lines.append(f"• {anomaly['description']}")
            caption_lines.append("")

    # Add game mention if available
    if game_handle:
        caption_lines.append(f"Playing {game_handle}")
        caption_lines.append("")
    else:
        if post_type in ['daily', 'recent']:
            caption_lines.append(f"Playing {full_game_name}")
            caption_lines.append("")
        else:
            caption_lines.append(f"{full_game_name} Analyzed")
            caption_lines.append("")

    # Build hashtag list
    base_hashtags = ['#gaming', '#esports', '#casual', '#gamer', '#gamingcommunity']

    # Add day-specific hashtags for daily/recent posts
    if post_type in ['daily', 'recent']:
        if day_of_week in ['Monday', 'Wednesday', 'Friday']:
            base_hashtags.append('#dailygamer')

    # Combine with game-specific hashtags
    all_hashtags = base_hashtags + game_hashtags

    # Add holiday theme hashtag if present
    theme = get_themed_colors()
    if theme.get('hashtag'):
        all_hashtags.append(theme['hashtag'])

    # Remove duplicates while preserving order
    seen = set()
    unique_hashtags = []
    for tag in all_hashtags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_hashtags.append(tag)

    # Add hashtags to caption
    caption_lines.append(' '.join(unique_hashtags))

    # Add YouTube link
    youtube_handle = os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')
    caption_lines.append("")
    caption_lines.append(f"📺 YouTube: {youtube_handle} | Link in bio")

    # Combine all parts
    caption = '\n'.join(caption_lines)

    # Ensure caption is under 2200 characters (Instagram limit)
    if len(caption) > 2200:
        caption = caption[:2197] + "..."

    return caption


# ============================================================================
# CHART GENERATION
# ============================================================================

def create_instagram_portrait_chart(stats, player_name, game_name, game_installment, title, subtitle=None, use_holiday_theme=False):
    """
    Create portrait-oriented chart for Instagram (1080x1440).

    FEATURES:
    - Uses Fira Code font (matches generate_bar_chart)
    - Sorts bars in descending order (largest at top)
    - Colored title (first theme color) and subtitle (second theme color)
    - Consistent styling with generate_bar_chart
    - Holiday theme support (only if exact date)

    Args:
        stats: list of tuples [(stat_name, value), ...]
        player_name: player name
        game_name: game name
        game_installment: game installment/version
        title: main title text
        subtitle: optional subtitle
        use_holiday_theme: bool, only True if today is exact holiday

    Returns:
        BytesIO buffer with image
    """
    # Get colors (holiday theme only if exact date)
    if use_holiday_theme:
        theme = get_themed_colors()
        colors = theme['colors'][:len(stats)]
        theme_name = theme['theme_name']
        print(f"🎉 Using holiday theme: {theme_name}")
    else:
        theme = get_themed_colors()  # Get default theme for colors
        colors = theme['colors'][:len(stats)]
        theme_name = None

    fig, ax = plt.subplots(figsize=(10.8, 14.4), dpi=100)

    # SORT stats by value (descending) - MATCHES generate_bar_chart
    sorted_stats = sorted(stats, key=lambda x: x[1], reverse=True)

    # Extract data and abbreviate
    stat_names = [abbreviate_stat(stat[0]) for stat in sorted_stats]
    stat_values = [stat[1] for stat in sorted_stats]

    # REVERSE for matplotlib (barh plots bottom-to-top, we want largest on top)
    stat_names.reverse()
    stat_values.reverse()

    # Determine if we should use log scale
    use_log = should_use_log_scale(stat_values)

    # For log scale, replace zeros with small value for plotting
    if use_log:
        plot_values = [max(v, 0.1) for v in stat_values]
    else:
        plot_values = stat_values

    # Create horizontal bar chart
    bars = ax.barh(stat_names, plot_values, color=colors)

    # Add value labels
    max_val = max(plot_values) if plot_values else 1
    value_fontsize = 18 # Matching Twitter chart value font size

    for bar, actual_val in zip(bars, plot_values):
        width = bar.get_width()
        display_val = format_large_number(actual_val)

        # Smart positioning: inside bar if large enough, outside if too small
        if width > max_val * 0.15:
            x_pos = width * 0.95
            ha = 'right'
            color = 'white'
        else:
            x_pos = width * 1.05
            ha = 'left'
            color = 'white'

        ax.text(x_pos, bar.get_y() + bar.get_height()/2,
               display_val,
               ha=ha, va='center',
               fontsize=value_fontsize, fontweight='bold', color=color)

    # Title with COLORED text (title = first color, subtitle = second color)
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    player_game_line = f"{player_name} - {full_game_name}"

    # Build title with color formatting
    # Use first color for main title
    title_color = colors[0] if len(colors) > 0 else 'white'
    # Use second color for subtitle
    subtitle_color = colors[1] if len(colors) > 1 else 'white'
    # Use third color for holiday theme name (if applicable)
    holiday_theme_color = colors[2] if len(colors) > 2 else 'white'

    # Create the title (we'll manually add each line with different colors)
    title_fontsize = 20  # Matching Twitter chart title size
    y_position = 0.965  # Start near top
    line_spacing = 0.028  # Space between lines

    # Line 1: Main title (e.g., "Today's Performance") - FIRST COLOR
    fig.text(0.5, y_position, title, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color=title_color,
             transform=fig.transFigure)
    y_position -= line_spacing

    # Line 2: Player + Game
    fig.text(0.5, y_position, player_game_line, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing

    # Line 3: Subtitle (e.g., date) - SECOND COLOR
    if subtitle:
        fig.text(0.5, y_position, subtitle, ha='center', va='top',
                 fontsize=title_fontsize, fontweight='bold', color=subtitle_color,
                 transform=fig.transFigure)
        y_position -= line_spacing

    # Line 4: Heritage month or holiday theme name - THIRD COLOR
    # Show if use_holiday_theme is True OR if theme has show_in_title set
    theme_to_display = None
    if use_holiday_theme and theme_name:
        # Old behavior - exact holiday passed in
        theme_to_display = theme_name
    else:
        # Check if current date has heritage month or holiday to display
        if theme.get('show_in_title'):
            theme_to_display = theme['theme_name']

    if theme_to_display:
        fig.text(0.5, y_position, theme_to_display, ha='center', va='top',
                 fontsize=title_fontsize, fontweight='bold', color=holiday_theme_color,
                 transform=fig.transFigure)

    # Grid and styling
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')

    # Timestamp
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.02, timestamp, ha='right', va='bottom',
             fontsize=14, color='gray', style='italic')

    # Branding
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01
    y_pos = 0.02

    # "YT" in red
    fig.text(x_start, y_pos, 'YT', ha='left', va='bottom',
             fontsize=14, color='#FF0000', fontweight='bold')

    # " & " in white
    fig.text(x_start + 0.014, y_pos, ' & ', ha='left', va='bottom',
             fontsize=14, color='white', fontweight='normal')

    # "Twitch" in purple
    fig.text(x_start + 0.038, y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=14, color='#9146FF', fontweight='bold')

    # Handle in white
    fig.text(x_start + 0.091, y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=14, color='white', fontweight='bold')

    # DYNAMIC tight_layout adjustment based on title lines
    # Calculate top margin based on whether theme name is displayed
    if theme_to_display:
        # Theme name adds an extra line, need more top space
        top_margin = 0.88  # Leave 12% for 4-line title
    else:
        # No theme name, standard 3-line title
        top_margin = 0.9   # Leave 10% for 3-line title

    plt.tight_layout(rect=[0, 0.04, 1, top_margin])

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)

    return buf


# ============================================================================
# INSTAGRAM POSTING
# ============================================================================

def post_to_instagram(image_buffer, caption):
    """
    Post image and caption to Instagram using Graph API.

    Args:
        image_buffer: BytesIO buffer containing PNG image
        caption: Caption text for the post

    Returns:
        bool: True if posted successfully, False otherwise
    """
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("❌ Instagram credentials not configured")
        return False

    try:
        # Step 1: Create container
        logger.info("📤 Step 1: Creating Instagram media container...")

        upload_url = f"https://graph.facebook.com/v24.0/{INSTAGRAM_ACCOUNT_ID}/media"

        temp_path = "/tmp/instagram_post.png"
        with open(temp_path, 'wb') as f:
            f.write(image_buffer.getvalue())

        with open(temp_path, 'rb') as image_file:
            files = {'file': image_file}
            data = {
                'caption': caption,
                'access_token': INSTAGRAM_ACCESS_TOKEN
            }

            response = requests.post(upload_url, data=data, files=files)
            response_data = response.json()

            if 'id' not in response_data:
                logger.error(f"❌ Image upload failed: {response_data}")
                return False

            media_id = response_data['id']
            logger.info(f"✅ Media container created: {media_id}")

        publish_url = f"https://graph.facebook.com/v24.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        publish_data = {
            'creation_id': media_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }

        publish_response = requests.post(publish_url, data=publish_data)
        publish_result = publish_response.json()

        if 'id' in publish_result:
            logger.info(f"✅ Successfully posted to Instagram: {publish_result['id']}")
            return True
        else:
            logger.error(f"❌ Publishing failed: {publish_result}")
            return False

    except Exception as e:
        logger.error(f"❌ Instagram posting error: {e}")
        return False


# ============================================================================
# MAIN EXECUTION FUNCTION (Lambda entry point)
# ============================================================================

def run_instagram_poster():
    """
    Main function to run Instagram poster.

    Returns:
        dict: Result information for Lambda response
    """
    logger.info(f"📅 Today: {datetime.now().strftime('%A, %B %d, %Y')}")

    # Get player info
    player_name = get_player_info(PLAYER_ID)

    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    logger.info(f"👤 Player: {player_name}")

    # Get all games player has played
    all_games = get_all_games_for_player(PLAYER_ID)
    logger.info(f"🎮 Games in database: {len(all_games)}")
    for game in all_games:
        logger.info(f"   - {game['game_name']} {game['game_installment'] or ''}")

    # Load posted content hashes
    posted_hashes = get_posted_content_hash()
    logger.info(f"📝 Previously posted content hashes: {len(posted_hashes)}")

    # Determine post content
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    day_of_week = today.strftime('%A')

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    post_type = None
    stats = []
    game_info = {}
    anomalies = []
    date_str = ""
    title = ""
    subtitle = None
    content_hash = None

    # PRIORITY 1: Games played today
    if check_games_on_date(PLAYER_ID, today):
        logger.info(f"✅ Games found today ({today})")

        multi_game_stats = get_stats_for_date_all_games(PLAYER_ID, today)

        if len(multi_game_stats) > 0:
            first_game = multi_game_stats[0]
            game_info = {
                'game_name': first_game['game'],
                'game_installment': first_game['installment']
            }

            game_id = next((g['game_id'] for g in all_games
                           if g['game_name'] == first_game['game']), None)

            if game_id:
                stats = get_stats_for_date(PLAYER_ID, game_id, today)
                anomalies = detect_anomalies(PLAYER_ID, game_id, today)

            post_type = 'daily'
            date_str = today.strftime('%A, %B %d')
            title = "Today's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 2: Games played yesterday
    elif check_games_on_date(PLAYER_ID, yesterday):
        logger.info(f"✅ Games found yesterday ({yesterday})")

        multi_game_stats = get_stats_for_date_all_games(PLAYER_ID, yesterday)

        if len(multi_game_stats) > 0:
            first_game = multi_game_stats[0]
            game_info = {
                'game_name': first_game['game'],
                'game_installment': first_game['installment']
            }

            game_id = next((g['game_id'] for g in all_games
                           if g['game_name'] == first_game['game']), None)

            if game_id:
                stats = get_stats_for_date(PLAYER_ID, game_id, yesterday)
                anomalies = detect_anomalies(PLAYER_ID, game_id, yesterday)

            post_type = 'recent'
            date_str = yesterday.strftime('%A, %B %d')
            title = "Yesterday's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 3: Historical records
    else:
        logger.info(f"📜 No recent games - fetching historical records")

        records = get_historical_records_all_games(PLAYER_ID, posted_hashes, limit=10)

        if not records:
            raise Exception("No new historical content available (all posted)")

        selected_records = records[:3]
        first_record = selected_records[0]

        game_info = {
            'game_name': first_record['game'],
            'game_installment': first_record['installment']
        }

        stats = [(r['stat'], r['value']) for r in selected_records]
        post_type = 'historical'
        title = "Historical Records"
        subtitle = "All-Time Bests"
        content_hash = first_record['hash']

        anomalies = [{
            'description': f"Best {r['stat']}: {r['value']} ({r['date'].strftime('%b %d, %Y') if r['date'] else 'N/A'})"
        } for r in selected_records]

    if not stats:
        raise Exception("No stats to post")

    # Check if already posted
    if content_hash and content_hash in posted_hashes:
        logger.warning(f"⚠️ Content already posted (hash: {content_hash[:8]}...)")
        raise Exception("Content already posted - need alternative content")

    logger.info(f"📊 Post type: {post_type}")
    logger.info(f"📈 Stats: {stats}")
    logger.info(f"🎮 Game: {game_info['game_name']}")

    # Create chart
    logger.info(f"🎨 Creating Instagram chart (Holiday theme: {use_holiday_theme})...")
    image_buffer = create_instagram_portrait_chart(
        stats, player_name, game_info['game_name'],
        game_info.get('game_installment'), title, subtitle, use_holiday_theme
    )

    # Backup to GCS
    logger.info(f"☁️ Backing up to Google Cloud Storage...")
    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(
            gcs_buffer, player_name, game_info['game_name'], post_type
        )

        if gcs_url:
            logger.info(f"✅ Backed up to GCS: {gcs_url}")
        else:
            logger.warning(f"⚠️ GCS backup failed (continuing with Instagram post)")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS backup error: {gcs_error}")

    # Generate caption
    caption = generate_trendy_caption(
        post_type, stats, game_info, player_name, day_of_week, anomalies
    )
    logger.info(f"📝 Caption:\n{caption}\n")

    # Post to Instagram
    logger.info(f"📤 Posting to Instagram...")
    success = post_to_instagram(image_buffer, caption)

    if success:
        # Save content hash to prevent duplicates
        if content_hash:
            save_content_hash(content_hash)

        logger.info(f"✅ Successfully posted to Instagram!")

        return {
            'posted': True,
            'post_type': post_type,
            'game': game_info['game_name'],
            'player': player_name,
            'content_hash': content_hash[:8] if content_hash else None
        }
    else:
        raise Exception("Failed to post to Instagram")


# ============================================================================
# LAMBDA PREPERATION FUNCTION (used by FETCH Lambda to prepare post data for SQS queue)
# ============================================================================

def run_instagram_poster_for_queue():
    """
    Prepare Instagram post data for SQS queue (doesn't post to Instagram).
    This is used by the FETCH Lambda to create the post data.

    Returns:
        dict: {
            'image_buffer': BytesIO,
            'caption': str,
            'post_type': str,
            'game': str,
            'player': str,
            'content_hash': str
        }
    """
    logger.info(f"📅 Today: {datetime.now().strftime('%A, %B %d, %Y')}")

    # Get player info
    player_name = get_player_info(PLAYER_ID)

    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    logger.info(f"👤 Player: {player_name}")

    # Get all games player has played
    all_games = get_all_games_for_player(PLAYER_ID)
    logger.info(f"🎮 Games in database: {len(all_games)}")
    for game in all_games:
        logger.info(f"   - {game['game_name']} {game['game_installment'] or ''}")

    # Load posted content hashes
    posted_hashes = get_posted_content_hash()
    logger.info(f"📝 Previously posted content hashes: {len(posted_hashes)}")

    # Determine post content
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    day_of_week = today.strftime('%A')

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    post_type = None
    stats = []
    game_info = {}
    anomalies = []
    date_str = ""
    title = ""
    subtitle = None
    content_hash = None

    # PRIORITY 1: Games played today
    if check_games_on_date(PLAYER_ID, today):
        logger.info(f"✅ Games found today ({today})")

        multi_game_stats = get_stats_for_date_all_games(PLAYER_ID, today)

        if len(multi_game_stats) > 0:
            first_game = multi_game_stats[0]
            game_info = {
                'game_name': first_game['game'],
                'game_installment': first_game['installment']
            }

            game_id = next((g['game_id'] for g in all_games
                           if g['game_name'] == first_game['game']), None)

            if game_id:
                stats = get_stats_for_date(PLAYER_ID, game_id, today)
                anomalies = detect_anomalies(PLAYER_ID, game_id, today)

            post_type = 'daily'
            date_str = today.strftime('%A, %B %d')
            title = "Today's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 2: Games played yesterday
    elif check_games_on_date(PLAYER_ID, yesterday):
        logger.info(f"✅ Games found yesterday ({yesterday})")

        multi_game_stats = get_stats_for_date_all_games(PLAYER_ID, yesterday)

        if len(multi_game_stats) > 0:
            first_game = multi_game_stats[0]
            game_info = {
                'game_name': first_game['game'],
                'game_installment': first_game['installment']
            }

            game_id = next((g['game_id'] for g in all_games
                           if g['game_name'] == first_game['game']), None)

            if game_id:
                stats = get_stats_for_date(PLAYER_ID, game_id, yesterday)
                anomalies = detect_anomalies(PLAYER_ID, game_id, yesterday)

            post_type = 'recent'
            date_str = yesterday.strftime('%A, %B %d')
            title = "Yesterday's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 3: Historical records
    else:
        logger.info(f"📜 No recent games - fetching historical records")

        records = get_historical_records_all_games(PLAYER_ID, posted_hashes, limit=10)

        if not records:
            raise Exception("No new historical content available (all posted)")

        selected_records = records[:3]
        first_record = selected_records[0]

        game_info = {
            'game_name': first_record['game'],
            'game_installment': first_record['installment']
        }

        stats = [(r['stat'], r['value']) for r in selected_records]
        post_type = 'historical'
        title = "Historical Records"
        subtitle = "All-Time Bests"
        content_hash = first_record['hash']

        anomalies = [{
            'description': f"Best {r['stat']}: {r['value']} ({r['date'].strftime('%b %d, %Y') if r['date'] else 'N/A'})"
        } for r in selected_records]

    if not stats:
        raise Exception("No stats to post")

    # Check if already posted
    if content_hash and content_hash in posted_hashes:
        logger.warning(f"⚠️ Content already posted (hash: {content_hash[:8]}...)")
        raise Exception("Content already posted - need alternative content")

    logger.info(f"📊 Post type: {post_type}")
    logger.info(f"📈 Stats: {stats}")
    logger.info(f"🎮 Game: {game_info['game_name']}")

    # Create chart
    logger.info(f"🎨 Creating Instagram chart (Holiday theme: {use_holiday_theme})...")
    image_buffer = create_instagram_portrait_chart(
        stats, player_name, game_info['game_name'],
        game_info.get('game_installment'), title, subtitle, use_holiday_theme
    )

    # Backup to GCS (URL is required for Instagram posting)
    logger.info(f"☁️ Backing up to Google Cloud Storage...")
    gcs_url = None
    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(
            gcs_buffer, player_name, game_info['game_name'], post_type
        )
        if gcs_url:
            logger.info(f"✅ Backed up to GCS: {gcs_url}")
        else:
            logger.warning(f"⚠️ GCS backup failed (continuing)")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS backup error: {gcs_error}")

    # Generate caption
    caption = generate_trendy_caption(
        post_type, stats, game_info, player_name, day_of_week, anomalies
    )
    logger.info(f"📝 Caption generated ({len(caption)} chars)")

    # Return data for queue (DON'T post to Instagram yet)
    return {
        'image_buffer': image_buffer,
        'gcs_url': gcs_url,
        'caption': caption,
        'post_type': post_type,
        'game': game_info['game_name'],
        'player': player_name,
        'content_hash': content_hash
    }


# Backward compatibility for non-Lambda execution
if __name__ == "__main__":
    result = run_instagram_poster()
    logger.info(f"Result: {result}")
