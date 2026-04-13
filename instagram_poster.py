"""
Instagram Automated Poster
Posts gaming stats to Instagram on Monday, Wednesday, Friday at 9 PM PST
Optimized for AWS Lambda execution
F
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
import psycopg2
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
import io
import requests
import hashlib
import logging
from collections import defaultdict

# Import utilities (these will be in the Lambda package)
from utils.chart_utils import abbreviate_stat, abbreviate_game_mode, format_large_number, load_custom_fonts, should_use_log_scale
from utils.holiday_themes import get_themed_colors, is_exact_holiday
from utils.gcs_utils import upload_instagram_poster_to_gcs
from utils.game_handles_utils import get_game_handle, get_game_hashtags

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import seaborn as sns

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DB_URL      = os.environ.get("DB_URL")
DB_PORT     = int(os.environ.get("DB_PORT", 6543))
DB_NAME     = os.environ.get("DB_NAME", "postgres")
DB_USER     = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")

# Constants
SOCIAL_PLAYER_NAME = os.environ.get("SOCIAL_PLAYER_NAME", "").strip()
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
# POSTGRESQL (psycopg2) CONNECTION LAYER
# ============================================================================

# Global connection (Lambda reuses this across invocations)
_pg_conn = None


def _get_pg_conn():
    """Get or reuse a psycopg2 connection. Reconnects if closed."""
    global _pg_conn
    if _pg_conn is None or _pg_conn.closed:
        _pg_conn = psycopg2.connect(
            host=DB_URL,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode="require",
            connect_timeout=30,
        )
    return _pg_conn


def execute_query(sql, params=None):
    """Execute SQL via psycopg2 and return list of row tuples."""
    conn = _get_pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if cur.description:
                return cur.fetchall()
        return []
    except Exception:
        conn.rollback()
        raise


def get_field_value(field):
    """Identity shim — psycopg2 returns plain Python types, no unpacking needed."""
    return field


def _resolve_player_id(player_name: str) -> int:
    """Resolve PLAYER_ID from SOCIAL_PLAYER_NAME env var at startup."""
    if not player_name:
        raise RuntimeError("SOCIAL_PLAYER_NAME env var is not set.")
    rows = execute_query(
        "SELECT player_id FROM dim.dim_players WHERE player_name = %s;",
        (player_name,)
    )
    if not rows:
        raise RuntimeError(f"No player found with name '{player_name}'. Check SOCIAL_PLAYER_NAME.")
    return rows[0][0]

PLAYER_ID: int | None = _resolve_player_id(SOCIAL_PLAYER_NAME) if (SOCIAL_PLAYER_NAME and DB_URL) else None


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
        WHERE player_id = %s
        AND (played_at AT TIME ZONE %s)::DATE = %s;
        """,
        (player_id, TIMEZONE_STR, target_date)
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
        WHERE f.player_id = %s
        ORDER BY g.game_name;
        """,
        (player_id,)
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
        WHERE player_id = %s;
        """,
        (player_id,)
    )
    return get_field_value(records[0][0]) if records else None


def get_stats_for_date(player_id, game_id, target_date, game_mode=None, aggregate='max'):
    """
    Get aggregated stat values per stat type for a game on a date.

    aggregate='max': MAX per stat type (single-session or historical display)
    aggregate='avg': ROUND(AVG()) per stat type (multi-session daily/yesterday/recent posts)

    Passing game_mode restricts results to that mode only (use when all sessions
    share the same mode).
    """
    agg_expr = 'ROUND(AVG(stat_value))' if aggregate == 'avg' else 'MAX(stat_value)'
    params = [player_id, game_id, TIMEZONE_STR, target_date]
    mode_clause = ''
    if game_mode:
        mode_clause = 'AND game_mode = %s'
        params.append(game_mode)

    records = execute_query(
        f"""
        SELECT
            stat_type,
            {agg_expr} AS agg_value
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND game_id = %s
          AND (played_at AT TIME ZONE %s)::DATE = %s
          {mode_clause}
        GROUP BY stat_type
        ORDER BY agg_value DESC
        LIMIT 5;
        """,
        tuple(params)
    )
    return [(get_field_value(row[0]), get_field_value(row[1])) for row in records]


def get_match_count_for_date(player_id, game_id, target_date, game_mode=None):
    """
    Count distinct match sessions (unique played_at timestamps) for a game on a
    date.  Each form submission shares one played_at so this equals # of
    submitted sessions.  Returns 1 as a safe fallback.
    """
    params = [player_id, game_id, TIMEZONE_STR, target_date]
    mode_clause = ''
    if game_mode:
        mode_clause = 'AND game_mode = %s'
        params.append(game_mode)

    try:
        records = execute_query(
            f"""
            SELECT COUNT(DISTINCT played_at) AS match_count
            FROM fact.fact_game_stats
            WHERE player_id = %s
              AND game_id = %s
              AND (played_at AT TIME ZONE %s)::DATE = %s
              {mode_clause};
            """,
            tuple(params)
        )
        count = get_field_value(records[0][0]) if records else 1
        return int(count) if count else 1
    except Exception as e:
        logger.warning(f"⚠️ Could not get match count: {e}")
        return 1


def get_most_recent_date_in_range(player_id, date_min, date_max):
    """
    Find the most recent local date (in TIMEZONE_STR) on which the player has
    game stats, searching within [date_min, date_max] inclusive.
    Returns a date object or None if no games found in that range.
    """
    try:
        records = execute_query(
            """
            SELECT MAX((played_at AT TIME ZONE %s)::DATE) AS most_recent
            FROM fact.fact_game_stats
            WHERE player_id = %s
              AND (played_at AT TIME ZONE %s)::DATE
                  BETWEEN %s AND %s;
            """,
            (TIMEZONE_STR, player_id, TIMEZONE_STR, date_min, date_max)
        )
        val = get_field_value(records[0][0]) if records else None
        if not val:
            return None
        return datetime.strptime(str(val)[:10], '%Y-%m-%d').date()
    except Exception as e:
        logger.warning(f"⚠️ get_most_recent_date_in_range failed: {e}")
        return None


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
        WHERE f.player_id = %s
        AND (f.played_at AT TIME ZONE %s)::DATE = %s
        ORDER BY f.stat_value DESC;
        """,
        (player_id, TIMEZONE_STR, target_date)
    )

    return [{
        'game': get_field_value(row[0]),
        'installment': get_field_value(row[1]),
        'stat': get_field_value(row[2]),
        'value': get_field_value(row[3]),
    } for row in records]


def get_game_mode_for_date(player_id, game_id, target_date):
    """
    Return the game mode if only one non-Main mode was played on this date.
    Returns None when zero modes or multiple distinct modes were played — this
    tells get_stats_for_date and get_match_count_for_date to aggregate across
    all modes rather than silently excluding sessions.
    """
    records = execute_query(
        """
        SELECT game_mode, COUNT(*) AS cnt
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND game_id = %s
          AND (played_at AT TIME ZONE %s)::DATE = %s
          AND game_mode IS NOT NULL
          AND TRIM(game_mode) != ''
          AND LOWER(TRIM(game_mode)) != 'main'
        GROUP BY game_mode
        ORDER BY cnt DESC, game_mode ASC
        LIMIT 2;
        """,
        (player_id, game_id, TIMEZONE_STR, target_date)
    )
    if len(records) > 1:
        return None  # Multiple modes played — don't filter, include all sessions
    return get_field_value(records[0][0]) if records else None


def get_all_modes_for_date(player_id, game_id, target_date):
    """
    Return all distinct non-Main game modes played for a game on a date,
    sorted alphabetically.  Used for caption display only — does not affect
    stat aggregation or chart generation.
    """
    records = execute_query(
        """
        SELECT DISTINCT game_mode
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND game_id = %s
          AND (played_at AT TIME ZONE %s)::DATE = %s
          AND game_mode IS NOT NULL
          AND TRIM(game_mode) != ''
          AND LOWER(TRIM(game_mode)) != 'main'
        ORDER BY game_mode ASC;
        """,
        (player_id, game_id, TIMEZONE_STR, target_date)
    )
    return [get_field_value(row[0]) for row in records]


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
            WHERE f.player_id = %s
            AND f.game_id = %s
            AND (f.played_at AT TIME ZONE %s)::DATE = %s
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
        (player_id, game_id, TIMEZONE_STR, target_date)
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
                MAX((f.played_at AT TIME ZONE %s)::DATE) as best_date
            FROM fact.fact_game_stats f
            JOIN dim.dim_games g ON f.game_id = g.game_id
            WHERE f.player_id = %s
              AND f.played_at >= NOW() - INTERVAL '365 days'
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
        (TIMEZONE_STR, player_id)
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

def generate_trendy_caption(post_type, stats, game_info, player_name, day_of_week, anomalies, game_mode=None, match_count=1, game_modes=None, is_averaged=False):
    """
    Generate trendy caption with game-specific handle and hashtags.
    Now uses game_handles_utils for centralized social media data.

    Args:
        post_type: str ('daily', 'yesterday', 'recent', 'historical')
        stats: list of tuples [(stat_name, value), ...]
        game_info: dict {'game_name': str, 'game_installment': str or None}
        player_name: str
        day_of_week: str
        anomalies: list of dicts [{'description': str}, ...]
        is_averaged: bool — True when stats are AVG across multiple sessions

    Returns:
        str: Caption text for Instagram
    """
    game_name = game_info['game_name']
    game_installment = game_info.get('game_installment')
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name

    # Get game handle for Instagram
    game_handle = get_game_handle(game_name, platform='instagram')

    # Get game-specific hashtags for Instagram
    game_hashtags = get_game_hashtags(game_name, platform='instagram')

    # Determine hashtag based on day
    day_hashtags = {
        'Monday': '#GamingThreads #MondayMotivation #MondayUpdate',
        'Tuesday': '#GamingThreads #TuesdayVibes #GamingTuesday',
        'Wednesday': '#GamingThreads #WednesdayUpdate #MidweekGrind',
        'Thursday': '#GamingThreads #ThrowbackThursday #GamingThursday',
        'Friday': '#GamingThreads #FridayFeeling #WeekendReady',
        'Saturday': '#GamingThreads #SaturdayGaming #WeekendVibes',
        'Sunday': '#GamingThreads #SundayFunday #SundayGaming'
    }

    day_tag = day_hashtags.get(day_of_week, '#GamingUpdate')

    # Build the main caption content
    if post_type == 'daily':
        emoji = "🔥"
        hook = f"{emoji} {player_name}'s Today's {full_game_name} Session {emoji}"
    elif post_type == 'yesterday':
        emoji = "📊"
        hook = f"{emoji} {player_name}'s Yesterday's {full_game_name} Highlights {emoji}"
    elif post_type == 'recent':
        emoji = "🎮"
        hook = f"{emoji} {player_name}'s Recent {full_game_name} Performance {emoji}"
    else:  # historical
        emoji = "🏆"
        hook = f"{emoji} {player_name}'s {full_game_name} All-Time Records {emoji}"

    caption_lines = [hook, day_tag, ""]

    # Show match count when multiple sessions were played the same day
    if match_count > 1:
        caption_lines.append(f"#️⃣ {match_count} matches played")
        caption_lines.append("")

    # Stats where a higher MAX value is NOT a good thing — skip "Best" prefix
    _lower_is_better = {'respawn', 'damage taken', 'loss', 'missed'}

    def _stat_label(name, ptype, averaged):
        if ptype == 'historical':
            if any(kw in name.lower() for kw in _lower_is_better):
                return name  # e.g. "Respawns: 1" not "Best Respawns: 1"
            return f"Best {name}"
        if averaged:
            return f"Average {name}"
        return name

    def _fmt_stat(v):
        """Display whole-number floats without .0 (e.g. 3244.0 → '3244')."""
        try:
            f = float(v)
            return str(int(f)) if f == int(f) else str(v)
        except (TypeError, ValueError):
            return str(v)

    # Add top stats (limit to top 3 for brevity)
    for stat_name, stat_value in stats[:3]:
        label = _stat_label(stat_name, post_type, is_averaged)
        caption_lines.append(f"• {label}: {_fmt_stat(stat_value)}")

    caption_lines.append("")

    # Add anomaly callouts if present
    if anomalies:
        if post_type in ['daily', 'yesterday', 'recent']:
            caption_lines.append("⚡ Notable:")
            for anomaly in anomalies[:2]:  # Limit to 2 for brevity
                caption_lines.append(f"• {anomaly['description']}")
            caption_lines.append("")

    # Game mode(s)
    if game_modes and len(game_modes) > 1:
        caption_lines.append(f"🎮 Modes: {' · '.join(game_modes)}")
        caption_lines.append("")
    elif game_mode and game_mode.strip().lower() not in ('main', 'n/a', 'none', '-'):
        caption_lines.append(f"🎮 Game Mode: {game_mode.strip()}")
        caption_lines.append("")

    # Add game mention if available
    if game_handle:
        caption_lines.append(f"Playing {game_handle}")
        caption_lines.append("")
    else:
        if post_type in ['daily', 'yesterday', 'recent']:
            caption_lines.append(f"Playing {full_game_name}")
            caption_lines.append("")
        else:
            caption_lines.append(f"{full_game_name} Analyzed")
            caption_lines.append("")

    # Engagement CTA
    if post_type == 'daily':
        caption_lines.append("💬 What was your best match today? Drop it below 👇")
        caption_lines.append("❤️ Like if you're grinding today & 🔁 repost to display match results!")
    elif post_type == 'yesterday':
        caption_lines.append("💬 Can you beat yesterday's score? Let us know 👇")
        caption_lines.append("❤️ Like if you can beat this score & 🔁 repost to challenge the community!")
    elif post_type == 'recent':
        caption_lines.append("💬 Can you top these recent stats? Drop it below 👇")
        caption_lines.append("❤️ Like if you're on the grind & 🔁 repost to see who can match it!")
    else:  # historical
        caption_lines.append("💬 Think you can top this all-time record? 👇")
        caption_lines.append("❤️ Like if you respect the grind & 🔁 repost to see if anyone can match it!")
    caption_lines.append("")
    caption_lines.append("📲 Follow for daily stats, weekly recaps & more!")
    caption_lines.append("")

    # Build hashtag list
    base_hashtags = ['#gaming', '#esports', '#casual', '#gamer', '#gamingcommunity']

    # Add day-specific hashtags for daily/yesterday/recent posts
    if post_type in ['daily', 'yesterday', 'recent']:
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

def _add_branding(fig):
    """Add consistent YT/Twitch handle and timestamp to the bottom of any figure."""
    fs = 19
    try:
        timestamp = datetime.now(ZoneInfo(TIMEZONE_STR)).strftime('%B %d, %Y')
    except Exception:
        timestamp = datetime.now().strftime('%B %d, %Y')
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    y = 0.03
    fig.text(0.99, y, timestamp, ha='right', va='bottom', fontsize=fs, color='gray', style='italic')
    fig.text(0.01,       y, 'YT',          ha='left', va='bottom', fontsize=fs, color='#FF0000', fontweight='bold')
    fig.text(0.01+0.025, y, ' & ',         ha='left', va='bottom', fontsize=fs, color='white',   fontweight='normal')
    fig.text(0.01+0.062, y, 'Twitch',      ha='left', va='bottom', fontsize=fs, color='#9146FF', fontweight='bold')
    fig.text(0.01+0.134, y, f' : {handle}', ha='left', va='bottom', fontsize=fs, color='white',  fontweight='bold')


def create_instagram_portrait_chart(stats, player_name, game_name, game_installment, title, subtitle=None, use_holiday_theme=False, game_mode=None):
    """
    Create portrait-oriented chart for Instagram (1080x1440).

    FEATURES:
    - Uses Fira Code font (matches generate_bar_chart)
    - Sorts bars in descending order (largest at top)
    - Colored title (first theme color) and subtitle (second theme color)
    - Consistent styling with generate_bar_chart / chart_utils.py
    - Log scale with nice_max and intermediate ticks for skewed data
    - Dynamic KPI label fontsize based on character count
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
    stats = stats[:3]

    # Get colors (holiday theme only if exact date)
    if use_holiday_theme:
        theme = get_themed_colors()
        theme_name = theme['theme_name']
        print(f"🎉 Using holiday theme: {theme_name}")
    else:
        theme = get_themed_colors()
        theme_name = None

    all_colors = theme['colors']
    num_stats = len(stats)
    colors = all_colors[:max(num_stats, 1)]

    fig, ax = plt.subplots(figsize=(10.8, 14.4), dpi=100)

    # Compute name lines early — needed for secondary fontsize calculation
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    player_game_line = f"{player_name} - {full_game_name}"

    # --- FONT SIZES ---
    branding_fontsize = 19
    amp_offset = 0.025    # after "YT" (2 chars)
    twitch_offset = 0.062 # after "YT & " (2+3 chars)
    handle_offset = 0.134 # after "YT & Twitch" (2+3+6 chars)
    branding_y_pos = 0.03

    fig_width_pts  = 10.8 * 72   # 777.6 pt
    fig_height_pts = 14.4 * 72   # 1036.8 pt
    char_ratio = 0.60
    fill = 0.88

    # Title: dynamic width-fill, max 72 — same structure as create_weekly header, all bar counts
    title_fontsize = max(36, min(int(fig_width_pts * fill / (len(title) * char_ratio)), 72))

    # Secondary lines always 44 — matches create_weekly secondary style
    secondary_fontsize = 44

    # Bar value labels — 2-stat/3-stat bars only; 1-stat KPI uses its own sizing table below
    if num_stats == 2:
        value_fontsize = 90
    elif num_stats == 3:
        value_fontsize = 80
    else:
        value_fontsize = 18  # unused — KPI section overrides completely

    # Line spacing proportional to font height in figure-fraction coordinates
    line_spacing           = (title_fontsize    / fig_height_pts) * 1.30
    secondary_line_spacing = (secondary_fontsize / fig_height_pts) * 1.30

    # --- PRE-COMPUTE TOP MARGIN & BAR LABEL SIZING ---
    # Mirror the title-block logic to count header lines (max 4 with holiday theme).
    _theme_preview = (theme.get('theme_name')
                      if (use_holiday_theme or theme.get('show_in_title')) else None)
    _n_header = 2 + int(subtitle is not None) + int(bool(_theme_preview))
    _n_header = min(_n_header, 4)  # hard cap: max 4 title rows

    top_margin = 0.97 - line_spacing - secondary_line_spacing * (_n_header - 1)

    if num_stats > 1:
        _axes_h_pts = fig_height_pts * (top_margin - 0.05) * 0.84   # ~84 % after tight_layout pad
        _bar_h_pts  = (_axes_h_pts / num_stats) * 0.8               # 0.8 = default barh height ratio

        # Base fontsize for y-axis stat name labels — constrained to fit in the left margin
        # (~20 % of figure width).  Stretch transform adds the remaining height afterward.
        _max_chars       = max((len(abbreviate_stat(s[0])[:6]) for s in stats[:3]), default=6)
        _margin_pts      = fig_width_pts * 0.20                      # ~155 pt
        _base_lfs        = max(24, min(int(_margin_pts / (_max_chars * char_ratio)), 80))
        # Vertical-only stretch factor so cap height fills the bar height exactly (cap at 6×)
        _label_stretch_y = min(_bar_h_pts / max(_base_lfs * 0.72, 1.0), 6.0)

    # --- CHART CONTENT ---
    if num_stats == 1:
        # KPI scoreboard
        # Label tiers: anchor label_len<=6 → 100pt at 0.58 (ratio = 0.0058/pt)
        # Value fontsize: dynamic by display value character count to fill screen width
        ax.axis('off')
        stat_name = abbreviate_stat(stats[0][0])
        display_val = format_large_number(stats[0][1])

        label_len = len(stat_name)
        val_len = len(display_val)

        # Outer tier: val_len → value fontsize + value box height → drives label offset floor
        # Inner tier: label_len → label fontsize (smaller font = floor at tier anchor)
        # Confirmed anchor: val_len > 4, label_len <= 6 → offset 0.65
        # Larger value font (smaller val_len) → box taller → label offset must rise
        if val_len <= 2:
            kpi_value_fontsize = 260
            kpi_value_offset = 0.38
            if label_len <= 4:
                kpi_label_fontsize = 130
                kpi_label_offset = 0.81   # larger label font, raise above tier anchor
            elif label_len <= 6:
                kpi_label_fontsize = 100
                kpi_label_offset = 0.78   # tier anchor
            elif label_len <= 8:
                kpi_label_fontsize = 85
                kpi_label_offset = 0.77   # floor at tier anchor
            else:
                kpi_label_fontsize = 70
                kpi_label_offset = 0.77   # floor at tier anchor
        elif val_len <= 3:
            kpi_value_fontsize = 220
            kpi_value_offset = 0.38
            if label_len <= 4:
                kpi_label_fontsize = 130
                kpi_label_offset = 0.75   # larger label font, raise above tier anchor
            elif label_len <= 6:
                kpi_label_fontsize = 100
                kpi_label_offset = 0.72  # tier anchor
            elif label_len <= 8:
                kpi_label_fontsize = 85
                kpi_label_offset = 0.71   # floor at tier anchor
            else:
                kpi_label_fontsize = 70
                kpi_label_offset = 0.71   # floor at tier anchor
        elif val_len <= 4:
            kpi_value_fontsize = 190
            kpi_value_offset = 0.38
            if label_len <= 4:
                kpi_label_fontsize = 130
                kpi_label_offset = 0.73   # larger label font, raise above tier anchor
            elif label_len <= 6:
                kpi_label_fontsize = 100
                kpi_label_offset = 0.70   # tier anchor (needs tuning)
            elif label_len <= 8:
                kpi_label_fontsize = 85
                kpi_label_offset = 0.69   # floor at tier anchor
            else:
                kpi_label_fontsize = 70
                kpi_label_offset = 0.69   # floor at tier anchor
        else:  # val_len > 4 (e.g. "45.2k")
            kpi_value_fontsize = 160
            kpi_value_offset = 0.38
            if label_len <= 4:
                kpi_label_fontsize = 130
                kpi_label_offset = 0.68   # larger label font, raise above tier anchor
            elif label_len <= 6:
                kpi_label_fontsize = 100
                kpi_label_offset = 0.65   # CONFIRMED WORKING ANCHOR
            elif label_len <= 8:
                kpi_label_fontsize = 85
                kpi_label_offset = 0.64   # floor at tier anchor
            else:
                kpi_label_fontsize = 70
                kpi_label_offset = 0.64   # floor at tier anchor

        # Scoreboard border: rounded rectangle in primary theme color spanning
        # both the stat label and the value — drawn first so text sits on top.
        from matplotlib.patches import FancyBboxPatch as _FBP
        _box_top    = min(kpi_label_offset + 0.14, 0.92)
        _box_bottom = kpi_value_offset - 0.18
        ax.add_patch(_FBP(
            (0.08, _box_bottom),
            0.84, _box_top - _box_bottom,
            boxstyle='round,pad=0.02',
            facecolor='#2d2d2d',
            edgecolor=colors[0],
            linewidth=5,
            transform=ax.transAxes,
            zorder=0,
        ))

        ax.text(0.5, kpi_label_offset, stat_name, ha='center', va='center',
                fontsize=kpi_label_fontsize, fontweight='bold',
                color='white', transform=ax.transAxes, zorder=1)
        ax.text(0.5, kpi_value_offset, display_val, ha='center', va='center',
                fontsize=kpi_value_fontsize, fontweight='bold',
                color=colors[0], transform=ax.transAxes, zorder=1)

    else:
        # SORT stats by value (descending) — largest at top
        sorted_stats = sorted(stats, key=lambda x: x[1], reverse=True)
        stat_names = [abbreviate_stat(stat[0]) for stat in sorted_stats]
        stat_values = [stat[1] for stat in sorted_stats]
        # REVERSE for matplotlib (barh plots bottom-to-top, we want largest on top)
        stat_names.reverse()
        stat_values.reverse()

        use_log = should_use_log_scale(stat_values)
        plot_values = [max(v, 0.1) for v in stat_values] if use_log else stat_values

        bars = ax.barh(stat_names, plot_values, color=colors[:len(stat_names)])

        # Log scale with nice_max and intermediate ticks (matches chart_utils)
        if use_log:
            ax.set_xscale('log')
            from matplotlib.ticker import FuncFormatter, LogLocator
            import math
            def log_formatter(x, _):
                if x >= 1000: return f'{int(x/1000)}k'
                elif x >= 1: return f'{int(x)}'
                else: return f'{x:.1f}'
            max_val = max(plot_values)
            magnitude = 10 ** math.floor(math.log10(max_val * 1.1))
            normalized = (max_val * 1.1) / magnitude
            if normalized <= 1: nice_max = 1 * magnitude
            elif normalized <= 2: nice_max = 2 * magnitude
            elif normalized <= 5: nice_max = 5 * magnitude
            else: nice_max = 10 * magnitude
            ax.set_xlim(left=ax.get_xlim()[0], right=nice_max)
            ax.xaxis.set_major_locator(LogLocator(base=10, subs=[1, 2, 5]))
            ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))

        xlim_min_val, xlim_max = ax.get_xlim()
        for bar, actual_val in zip(bars, stat_values):
            width = bar.get_width()
            display_val = format_large_number(actual_val)
            bar_center_y = bar.get_y() + bar.get_height() / 2
            if use_log:
                log_min = math.log10(max(xlim_min_val, 0.01))
                log_max = math.log10(xlim_max)
                log_bar_end = math.log10(max(width, 0.01))
                bar_vis_frac = (log_bar_end - log_min) / (log_max - log_min)

                if bar_vis_frac < 0.12:
                    # Bar too short — place label to the right of the bar, centered
                    ax.text(width * 1.15, bar_center_y,
                            display_val, ha='left', va='center',
                            fontsize=value_fontsize, fontweight='bold', color='white',
                            path_effects=[pe.withStroke(linewidth=3, foreground='#111111')])
                else:
                    # Right-align label at the end of the bar
                    ax.text(width * 0.95, bar_center_y,
                            display_val, ha='right', va='center',
                            fontsize=value_fontsize, fontweight='bold', color='white',
                            path_effects=[pe.withStroke(linewidth=3, foreground='#111111')])
            else:
                if width < xlim_max * 0.10:
                    # Bar too short — place label to the right of the bar, centered
                    ax.text(width + xlim_max * 0.02, bar_center_y,
                            display_val, ha='left', va='center',
                            fontsize=value_fontsize, fontweight='bold', color='white',
                            path_effects=[pe.withStroke(linewidth=3, foreground='#111111')])
                else:
                    # Right-align label at the end of the bar
                    ax.text(width * 0.95, bar_center_y,
                            display_val, ha='right', va='center',
                            fontsize=value_fontsize, fontweight='bold', color='white',
                            path_effects=[pe.withStroke(linewidth=3, foreground='#111111')])

        # Fira Sans Extra Condensed + ultra-condensed stretch: two layers of
        # horizontal compression let us push font size up to ~2× while keeping
        # the glyph width close to the original — net result looks like vertical stretch.
        from matplotlib.font_manager import FontProperties
        tick_fontsize = int(value_fontsize/1.5)
        condensed_fp = FontProperties(
            family='Fira Sans Extra Condensed',
            size=tick_fontsize,
        )
        ax.tick_params(axis='y', labelsize=tick_fontsize)
        for _lbl in ax.get_yticklabels():
            _lbl.set_fontproperties(condensed_fp)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('white')
        ax.spines['bottom'].set_color('white')

    # --- TITLE BLOCK ---
    title_color = all_colors[0]
    subtitle_color = all_colors[1] if len(all_colors) > 1 else 'white'
    holiday_theme_color = all_colors[2] if len(all_colors) > 2 else 'white'
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    player_game_line = f"{player_name} - {full_game_name}"

    y_position = 0.97

    # Line 1: main title ("Today's Performance", etc.) — FIRST COLOR
    fig.text(0.5, y_position, title, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color=title_color,
             transform=fig.transFigure)
    y_position -= line_spacing

    # Line 2: player — game — WHITE (secondary fontsize)
    fig.text(0.5, y_position, player_game_line, ha='center', va='top',
             fontsize=secondary_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= secondary_line_spacing

    # Line 3: subtitle (date, "All-Time Bests", etc.) — SECOND COLOR (secondary fontsize)
    if subtitle:
        fig.text(0.5, y_position, subtitle, ha='center', va='top',
                 fontsize=secondary_fontsize, fontweight='bold', color=subtitle_color,
                 transform=fig.transFigure)
        y_position -= secondary_line_spacing

    # Line 4: heritage/holiday theme — THIRD COLOR (secondary fontsize)
    theme_to_display = None
    if use_holiday_theme and theme_name:
        theme_to_display = theme_name
    elif theme.get('show_in_title'):
        theme_to_display = theme['theme_name']

    if theme_to_display:
        fig.text(0.5, y_position, theme_to_display, ha='center', va='top',
                 fontsize=secondary_fontsize, fontweight='bold', color=holiday_theme_color,
                 transform=fig.transFigure)
        y_position -= secondary_line_spacing

    top_margin = y_position

    # --- BRANDING & TIMESTAMP ---
    try:
        timestamp = datetime.now(ZoneInfo(TIMEZONE_STR)).strftime('%B %d, %Y')
    except Exception:
        timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, branding_y_pos, timestamp, ha='right', va='bottom',
             fontsize=branding_fontsize, color='gray', style='italic')

    # Game mode tag (centered between handles and date)
    _mode_tag = abbreviate_game_mode(game_mode) if game_mode else None
    if _mode_tag:
        fig.text(0.5, branding_y_pos, f' {_mode_tag} ', ha='center', va='bottom',
                 fontsize=branding_fontsize, color='white', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='none', edgecolor='white', linewidth=1.5))

    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01
    fig.text(x_start, branding_y_pos, 'YT', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#FF0000', fontweight='bold')
    fig.text(x_start + amp_offset, branding_y_pos, ' & ', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='normal')
    fig.text(x_start + twitch_offset, branding_y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#9146FF', fontweight='bold')
    fig.text(x_start + handle_offset, branding_y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='bold')

    # --- TIGHT LAYOUT ---
    # 2-stat: centered rect so bars don't dominate the tall canvas
    # 1-stat KPI and 3-stat: use dynamic top_margin derived from title block
    if num_stats == 2:
        plt.tight_layout(rect=[0, 0.09, 1, 0.72])
    elif num_stats == 1:
        plt.tight_layout(rect=[0, 0.04, 1, top_margin])
    else:
        plt.tight_layout(rect=[0, 0.05, 1, top_margin])

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

        # Step 2: Poll until container is FINISHED (Instagram needs time to process)
        status_url = f"https://graph.facebook.com/v24.0/{media_id}"
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            time.sleep(4)
            status_resp = requests.get(status_url, params={
                'fields': 'status_code',
                'access_token': INSTAGRAM_ACCESS_TOKEN
            })
            status_data = status_resp.json()
            status_code = status_data.get('status_code', '')
            logger.info(f"⏳ Container status attempt {attempt}/{max_attempts}: {status_code}")
            if status_code == 'FINISHED':
                break
            if status_code == 'ERROR':
                logger.error(f"❌ Container processing failed: {status_data}")
                return False
        else:
            logger.error(f"❌ Container not ready after {max_attempts} attempts")
            return False

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

    # Determine post content using the configured timezone
    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))
    today = now_local.date()
    yesterday = today - timedelta(days=1)
    day_of_week = now_local.strftime('%A')
    logger.info(f"📅 Today: {now_local.strftime('%A, %B %d, %Y')} ({TIMEZONE_STR})")

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    post_type = None
    stats = []
    game_info = {}
    anomalies = []
    game_mode = None
    game_modes: list = []
    match_count = 1
    is_averaged = False
    date_str = ""
    title = ""
    subtitle = None
    content_hash = None

    def _resolve_game_for_date(target_date):
        """
        Shared helper: pick the game with the most stat rows on target_date,
        resolve its game_id, mode, stats, and match count.
        Returns (game_info, game_id, game_mode, game_modes, stats, anomalies, match_count)
        or None if no data found.
        """
        multi = get_stats_for_date_all_games(PLAYER_ID, target_date)
        if not multi:
            return None
        _counts: dict = {}
        for _r in multi:
            _key = (_r['game'], _r['installment'])
            _counts[_key] = _counts.get(_key, 0) + 1
        _top = max(_counts, key=_counts.get)
        _game_info = {'game_name': _top[0], 'game_installment': _top[1]}
        _game_id = next(
            (g['game_id'] for g in all_games
             if g['game_name'] == _top[0] and g['game_installment'] == _top[1]),
            None
        )
        if not _game_id:
            logger.warning(f"⚠️ game_id not found for {_top[0]} {_top[1]}")
            return None
        _mode = get_game_mode_for_date(PLAYER_ID, _game_id, target_date)
        _modes = get_all_modes_for_date(PLAYER_ID, _game_id, target_date)
        _count = get_match_count_for_date(PLAYER_ID, _game_id, target_date, _mode)
        # Use AVG when multiple sessions; MAX when single session
        _agg = 'avg' if _count > 1 else 'max'
        _stats = get_stats_for_date(PLAYER_ID, _game_id, target_date, _mode, aggregate=_agg)
        _anomalies = detect_anomalies(PLAYER_ID, _game_id, target_date)
        return _game_info, _game_id, _mode, _modes, _stats, _anomalies, _count

    # PRIORITY 1: Games played today
    if check_games_on_date(PLAYER_ID, today):
        logger.info(f"✅ Games found today ({today})")
        result = _resolve_game_for_date(today)
        if result:
            game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
            is_averaged = match_count > 1
            if match_count > 1:
                logger.info(f"🔁 {match_count} sessions → using AVG stats for {game_info['game_name']}")
            post_type = 'daily'
            date_str = today.strftime('%A, %B %d')
            title = "Today's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 2: Games played yesterday
    elif check_games_on_date(PLAYER_ID, yesterday):
        logger.info(f"✅ Games found yesterday ({yesterday})")
        result = _resolve_game_for_date(yesterday)
        if result:
            game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
            is_averaged = match_count > 1
            if match_count > 1:
                logger.info(f"🔁 {match_count} sessions → using AVG stats for {game_info['game_name']}")
            post_type = 'yesterday'
            date_str = yesterday.strftime('%A, %B %d')
            title = "Yesterday's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 3: Games in the past 2–7 days (most recent date in that window)
    else:
        week_min = today - timedelta(days=7)
        week_max = today - timedelta(days=2)
        recent_date = get_most_recent_date_in_range(PLAYER_ID, week_min, week_max)
        if recent_date:
            logger.info(f"✅ Recent games found on {recent_date}")
            result = _resolve_game_for_date(recent_date)
            if result:
                game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
                is_averaged = match_count > 1
                if match_count > 1:
                    logger.info(f"🔁 {match_count} sessions → using AVG stats for {game_info['game_name']}")
                post_type = 'recent'
                date_str = recent_date.strftime('%A, %B %d')
                title = "Recent Performance"
                subtitle = date_str
                content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 4: Historical records (past 365 days, MAX)
    if not post_type:
        logger.info(f"📜 No games in past 7 days — fetching historical records (365-day window)")

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
        is_averaged = False
        title = "Historical Records"
        subtitle = "Past Year Bests"
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
        game_info.get('game_installment'), title, subtitle, use_holiday_theme,
        game_mode=game_mode
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
        post_type, stats, game_info, player_name, day_of_week, anomalies,
        game_mode=game_mode, match_count=match_count, game_modes=game_modes,
        is_averaged=is_averaged,
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

    # Determine post content using the configured timezone
    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))
    today = now_local.date()
    yesterday = today - timedelta(days=1)
    day_of_week = now_local.strftime('%A')
    logger.info(f"📅 Today: {now_local.strftime('%A, %B %d, %Y')} ({TIMEZONE_STR})")

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    post_type = None
    stats = []
    game_info = {}
    anomalies = []
    game_mode = None
    game_modes: list = []
    match_count = 1
    is_averaged = False
    date_str = ""
    title = ""
    subtitle = None
    content_hash = None

    def _resolve_game_for_date(target_date):
        multi = get_stats_for_date_all_games(PLAYER_ID, target_date)
        if not multi:
            return None
        _counts: dict = {}
        for _r in multi:
            _key = (_r['game'], _r['installment'])
            _counts[_key] = _counts.get(_key, 0) + 1
        _top = max(_counts, key=_counts.get)
        _game_info = {'game_name': _top[0], 'game_installment': _top[1]}
        _game_id = next(
            (g['game_id'] for g in all_games
             if g['game_name'] == _top[0] and g['game_installment'] == _top[1]),
            None
        )
        if not _game_id:
            logger.warning(f"⚠️ game_id not found for {_top[0]} {_top[1]}")
            return None
        _mode = get_game_mode_for_date(PLAYER_ID, _game_id, target_date)
        _modes = get_all_modes_for_date(PLAYER_ID, _game_id, target_date)
        _count = get_match_count_for_date(PLAYER_ID, _game_id, target_date, _mode)
        _agg = 'avg' if _count > 1 else 'max'
        _stats = get_stats_for_date(PLAYER_ID, _game_id, target_date, _mode, aggregate=_agg)
        _anomalies = detect_anomalies(PLAYER_ID, _game_id, target_date)
        return _game_info, _game_id, _mode, _modes, _stats, _anomalies, _count

    # PRIORITY 1: Games played today
    if check_games_on_date(PLAYER_ID, today):
        logger.info(f"✅ Games found today ({today})")
        result = _resolve_game_for_date(today)
        if result:
            game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
            is_averaged = match_count > 1
            post_type = 'daily'
            date_str = today.strftime('%A, %B %d')
            title = "Today's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 2: Games played yesterday
    elif check_games_on_date(PLAYER_ID, yesterday):
        logger.info(f"✅ Games found yesterday ({yesterday})")
        result = _resolve_game_for_date(yesterday)
        if result:
            game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
            is_averaged = match_count > 1
            post_type = 'yesterday'
            date_str = yesterday.strftime('%A, %B %d')
            title = "Yesterday's Performance"
            subtitle = date_str
            content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 3: Games in the past 2–7 days
    else:
        week_min = today - timedelta(days=7)
        week_max = today - timedelta(days=2)
        recent_date = get_most_recent_date_in_range(PLAYER_ID, week_min, week_max)
        if recent_date:
            logger.info(f"✅ Recent games found on {recent_date}")
            result = _resolve_game_for_date(recent_date)
            if result:
                game_info, _, game_mode, game_modes, stats, anomalies, match_count = result
                is_averaged = match_count > 1
                post_type = 'recent'
                date_str = recent_date.strftime('%A, %B %d')
                title = "Recent Performance"
                subtitle = date_str
                content_hash = generate_content_hash(stats, game_info['game_name'], date_str)

    # PRIORITY 4: Historical records (past 365 days, MAX)
    if not post_type:
        logger.info(f"📜 No games in past 7 days — fetching historical records (365-day window)")
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
        is_averaged = False
        title = "Historical Records"
        subtitle = "Past Year Bests"
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
        game_info.get('game_installment'), title, subtitle, use_holiday_theme,
        game_mode=game_mode
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
        post_type, stats, game_info, player_name, day_of_week, anomalies,
        game_mode=game_mode, match_count=match_count, game_modes=game_modes,
        is_averaged=is_averaged,
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


def run_tuesday_thursday_poster_for_queue():
    """
    FETCH step for Tuesday/Thursday Tale of the Tape comparison posts.
    Returns a dict compatible with fetch_and_queue() — does NOT post to Instagram.
    """
    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    logger.info(f"👤 Player: {player_name}")

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))
    day_of_week = now_local.strftime('%A')

    # Get comparison data
    data = get_tale_of_tape_data(PLAYER_ID)
    if data is None:
        # Fallback 1: regular stats post (has duplicate filtering built in)
        logger.warning("⚠️ No Tale of the Tape data — falling back to regular stats post...")
        try:
            return run_instagram_poster_for_queue()
        except Exception as fallback_err:
            # Fallback 2: nothing to post — return None so the caller can skip
            logger.warning(f"⚠️ Regular stats fallback also failed: {fallback_err} — skipping post")
            return None

    logger.info(f"🎮 Game: {data['game_name']} | Modes: {data['mode_1']} vs {data['mode_2']}")

    game_info = {
        'game_name': data['game_name'],
        'game_installment': data['game_installment']
    }

    # Create chart
    logger.info(f"🎨 Creating Tale of the Tape chart (Holiday theme: {use_holiday_theme})...")
    image_buffer = create_tale_of_tape_chart(
        data['game_name'], data['game_installment'],
        data['mode_1'], data['mode_2'], data['stats'],
        player_name, use_holiday_theme
    )

    # Upload to GCS
    logger.info(f"☁️ Uploading to Google Cloud Storage...")
    gcs_url = None
    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(gcs_buffer, player_name, data['game_name'], 'comparison')
        if gcs_url:
            logger.info(f"✅ Uploaded to GCS: {gcs_url}")
        else:
            logger.warning(f"⚠️ GCS upload failed (continuing)")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS upload error: {gcs_error}")

    # Generate caption
    caption = generate_comparison_caption(
        game_info, data['mode_1'], data['mode_2'], data['stats'], player_name, day_of_week
    )
    logger.info(f"📝 Caption generated ({len(caption)} chars)")

    # No dedup needed for comparison posts
    content_hash = None

    return {
        'image_buffer': image_buffer,
        'gcs_url': gcs_url,
        'caption': caption,
        'post_type': 'comparison',
        'game': data['game_name'],
        'player': player_name,
        'content_hash': content_hash
    }


def run_saturday_poster_for_queue():
    """
    FETCH step for Saturday weekly summary posts.
    Returns a dict compatible with fetch_and_queue() — does NOT post to Instagram.
    """
    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    logger.info(f"👤 Player: {player_name}")

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    today = now_local.date()
    week_end = today - timedelta(days=1)    # Friday
    week_start = today - timedelta(days=7)  # Previous Saturday

    logger.info(f"📅 Weekly range: {week_start} to {week_end}")

    # Get weekly summary data
    summary = get_weekly_summary_data(PLAYER_ID, week_start, week_end)

    if summary is None:
        # No gaming data this week — post "No Weekly Recap" placeholder
        logger.info("📭 No gaming data this week — creating 'No Weekly Recap' placeholder post...")
        image_buffer = create_no_weekly_recap_chart(player_name, use_holiday_theme)
        caption = generate_no_weekly_recap_caption(player_name)
        content_hash = hashlib.md5(f"no_recap_{week_start}".encode()).hexdigest()

        gcs_url = None
        try:
            gcs_buffer = io.BytesIO(image_buffer.getvalue())
            gcs_url = upload_instagram_poster_to_gcs(gcs_buffer, player_name, 'no_weekly_recap', 'weekly')
            if gcs_url:
                logger.info(f"✅ No-recap placeholder uploaded to GCS: {gcs_url}")
        except Exception as gcs_error:
            logger.warning(f"⚠️ GCS upload error for no-recap: {gcs_error}")

        return {
            'image_buffer': image_buffer,
            'gcs_url': gcs_url,
            'caption': caption,
            'post_type': 'no_weekly_recap',
            'game': 'No Weekly Recap',
            'player': player_name,
            'content_hash': content_hash
        }

    logger.info(f"🎮 Games in summary: {summary.get('games_played', 0)}")

    # Create chart
    logger.info(f"🎨 Creating weekly summary chart (Holiday theme: {use_holiday_theme})...")
    image_buffer = create_weekly_summary_chart(summary, player_name, use_holiday_theme)

    # Upload to GCS
    logger.info(f"☁️ Uploading to Google Cloud Storage...")
    gcs_url = None
    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(gcs_buffer, player_name, 'weekly_summary', 'weekly')
        if gcs_url:
            logger.info(f"✅ Uploaded to GCS: {gcs_url}")
        else:
            logger.warning(f"⚠️ GCS upload failed (continuing)")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS upload error: {gcs_error}")

    # Generate caption
    caption = generate_weekly_caption(summary, player_name)
    logger.info(f"📝 Caption generated ({len(caption)} chars)")

    # Hash from week_start date string to prevent double-posting the same week
    content_hash = hashlib.md5(str(week_start).encode()).hexdigest()

    return {
        'image_buffer': image_buffer,
        'gcs_url': gcs_url,
        'caption': caption,
        'post_type': 'weekly_summary',
        'game': 'Weekly Summary',
        'player': player_name,
        'content_hash': content_hash
    }


def run_new_years_poster_for_queue():
    """
    FETCH step for New Year's Day yearly recap posts.
    Returns a dict compatible with fetch_and_queue() — does NOT post to Instagram.
    """
    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    logger.info(f"👤 Player: {player_name}")

    # Check if today is exact holiday (for theme)
    exact_holiday = is_exact_holiday()
    use_holiday_theme = exact_holiday is not None

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    recap_year = now_local.year - 1
    logger.info(f"📅 Generating recap for year: {recap_year}")

    # Get yearly recap data
    recap = get_yearly_recap_data(PLAYER_ID, recap_year)
    if recap is None:
        raise Exception(f"Insufficient data for {recap_year} yearly recap")

    logger.info(f"🎮 Gamer type: {recap.get('gamer_type', 'unknown')}")

    # Create chart
    logger.info(f"🎨 Creating yearly recap chart (Holiday theme: {use_holiday_theme})...")
    image_buffer = create_yearly_recap_chart(recap, player_name, use_holiday_theme)

    # Upload to GCS
    logger.info(f"☁️ Uploading to Google Cloud Storage...")
    gcs_url = None
    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(
            gcs_buffer, player_name, f'yearly_recap_{recap_year}', 'yearly'
        )
        if gcs_url:
            logger.info(f"✅ Uploaded to GCS: {gcs_url}")
        else:
            logger.warning(f"⚠️ GCS upload failed (continuing)")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS upload error: {gcs_error}")

    # Generate caption
    caption = generate_yearly_recap_caption(recap, player_name)
    logger.info(f"📝 Caption generated ({len(caption)} chars)")

    # Deterministic hash — same year never posts twice
    content_hash = hashlib.md5(f"yearly_{recap_year}".encode()).hexdigest()

    return {
        'image_buffer': image_buffer,
        'gcs_url': gcs_url,
        'caption': caption,
        'post_type': 'yearly_recap',
        'game': f'{recap_year} Recap',
        'player': player_name,
        'content_hash': content_hash
    }


# ============================================================================
# TUESDAY / THURSDAY: GAME MODE COMPARISON  (Tale of the Tape)
# ============================================================================

def get_tale_of_tape_data(player_id):
    """
    Find the best comparison pair for Tale of the Tape.

    Priority:
    1. Within-game mode comparison — same game, two different modes, both with
       >= 30 samples per stat_type.  When 3+ modes qualify, the pair with the
       highest combined average stat value wins.
    2. Cross-game stat comparison (fallback) — two different games that share
       at least one stat_type (e.g., both track 'Score').  mode_1/mode_2 are
       formatted as '<GameName> (<Mode>)' so the existing chart function works
       without modification.

    Returns dict or None when insufficient data exists.
    """
    # ------------------------------------------------------------------
    # PASS 1: within-game mode vs mode (original logic)
    # ------------------------------------------------------------------
    records = execute_query(
        """
        WITH mode_stats AS (
            SELECT
                f.game_id,
                f.game_mode,
                f.stat_type,
                COUNT(*)                            AS n,
                AVG(CAST(f.stat_value AS FLOAT))    AS mean_val,
                STDDEV(CAST(f.stat_value AS FLOAT)) AS std_val
            FROM fact.fact_game_stats f
            WHERE f.player_id = %s
              AND f.game_mode IS NOT NULL
              AND TRIM(f.game_mode) != ''
            GROUP BY f.game_id, f.game_mode, f.stat_type
            HAVING COUNT(*) >= 30
        )
        SELECT
            a.game_id,
            a.game_mode  AS mode_1,
            b.game_mode  AS mode_2,
            a.stat_type,
            a.n          AS n1,
            a.mean_val   AS mean1,
            a.std_val    AS std1,
            b.n          AS n2,
            b.mean_val   AS mean2,
            b.std_val    AS std2
        FROM mode_stats a
        JOIN mode_stats b
          ON  a.game_id   = b.game_id
          AND a.stat_type = b.stat_type
          AND a.game_mode < b.game_mode
        ORDER BY a.game_id, (a.mean_val + b.mean_val) DESC;
        """,
        (player_id,)
    )

    if records:
        pairs = defaultdict(list)
        for row in records:
            key = (
                get_field_value(row[0]),   # game_id
                get_field_value(row[1]),   # mode_1
                get_field_value(row[2]),   # mode_2
            )
            pairs[key].append({
                'stat_type': get_field_value(row[3]),
                'n1':    int(get_field_value(row[4]) or 0),
                'mean1': float(get_field_value(row[5]) or 0),
                'std1':  float(get_field_value(row[6]) or 0),
                'n2':    int(get_field_value(row[7]) or 0),
                'mean2': float(get_field_value(row[8]) or 0),
                'std2':  float(get_field_value(row[9]) or 0),
            })

        for (game_id, mode_1, mode_2), stats_list in pairs.items():
            game_records = execute_query(
                "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = %s;",
                (game_id,)
            )
            if game_records:
                return {
                    'game_id':          game_id,
                    'game_name':        get_field_value(game_records[0][0]),
                    'game_installment': get_field_value(game_records[0][1]),
                    'mode_1':           mode_1,
                    'mode_2':           mode_2,
                    'stats':            stats_list[:3],
                }

    # ------------------------------------------------------------------
    # PASS 2: cross-game shared stat_type comparison (fallback)
    # Two different games that both track the same stat_type with >= 30
    # samples each.  mode_1/mode_2 are labelled as "GameName (Mode)" so
    # the existing create_tale_of_tape_chart renders them correctly.
    # ------------------------------------------------------------------
    logger.info("No within-game pairs found — trying cross-game stat comparison")
    cross_records = execute_query(
        """
        WITH game_stats AS (
            SELECT
                f.game_id,
                g.game_name,
                g.game_installment,
                f.game_mode,
                f.stat_type,
                COUNT(*)                            AS n,
                AVG(CAST(f.stat_value AS FLOAT))    AS mean_val,
                STDDEV(CAST(f.stat_value AS FLOAT)) AS std_val
            FROM fact.fact_game_stats f
            JOIN dim.dim_games g ON f.game_id = g.game_id
            WHERE f.player_id = %s
              AND f.game_mode IS NOT NULL
              AND TRIM(f.game_mode) != ''
            GROUP BY f.game_id, g.game_name, g.game_installment, f.game_mode, f.stat_type
            HAVING COUNT(*) >= 30
        )
        SELECT
            a.game_id                                           AS game_id_1,
            a.game_name                                         AS game_name_1,
            a.game_installment                                  AS installment_1,
            a.game_mode                                         AS game_mode_1,
            b.game_id                                           AS game_id_2,
            b.game_name                                         AS game_name_2,
            b.game_installment                                  AS installment_2,
            b.game_mode                                         AS game_mode_2,
            a.stat_type,
            a.n          AS n1,
            a.mean_val   AS mean1,
            a.std_val    AS std1,
            b.n          AS n2,
            b.mean_val   AS mean2,
            b.std_val    AS std2
        FROM game_stats a
        JOIN game_stats b
          ON  a.stat_type = b.stat_type
          AND a.game_id   < b.game_id
        ORDER BY (a.mean_val + b.mean_val) DESC;
        """,
        (player_id,)
    )

    if not cross_records:
        return None

    cross_pairs = defaultdict(list)
    for row in cross_records:
        game_id_1    = get_field_value(row[0])
        game_name_1  = get_field_value(row[1])
        install_1    = get_field_value(row[2])
        game_mode_1  = get_field_value(row[3])
        game_id_2    = get_field_value(row[4])
        game_name_2  = get_field_value(row[5])
        install_2    = get_field_value(row[6])
        game_mode_2  = get_field_value(row[7])

        # Label includes game name so the chart columns are identifiable
        full_1 = f"{game_name_1}{': ' + install_1 if install_1 else ''} ({game_mode_1})"
        full_2 = f"{game_name_2}{': ' + install_2 if install_2 else ''} ({game_mode_2})"
        key = (game_id_1, game_id_2, full_1, full_2)

        cross_pairs[key].append({
            'stat_type': get_field_value(row[8]),
            'n1':    int(get_field_value(row[9]) or 0),
            'mean1': float(get_field_value(row[10]) or 0),
            'std1':  float(get_field_value(row[11]) or 0),
            'n2':    int(get_field_value(row[12]) or 0),
            'mean2': float(get_field_value(row[13]) or 0),
            'std2':  float(get_field_value(row[14]) or 0),
        })

    for (game_id_1, game_id_2, label_1, label_2), stats_list in cross_pairs.items():
        # Use game_id_1's info as the "game" header; labels carry the full context
        game_records = execute_query(
            "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = %s;",
            (game_id_1,)
        )
        if game_records:
            return {
                'game_id':          game_id_1,
                'game_name':        get_field_value(game_records[0][0]),
                'game_installment': get_field_value(game_records[0][1]),
                'mode_1':           label_1,   # "CoD: Warzone (Resurgence Casual)"
                'mode_2':           label_2,   # "CoD: Black Ops 7 (Zombies)"
                'stats':            stats_list[:3],
                'cross_game':       True,      # flag for caption/logging
            }

    return None


def create_tale_of_tape_chart(game_name, installment, mode_1, mode_2, stats_data,
                               player_name, use_holiday_theme=False):
    """
    UFC Tale of the Tape style 3-column comparison chart (1080x1440).
    Left = mode_1 averages (dimmed if lower), center = stat labels,
    right = mode_2 averages (dimmed if lower).
    """
    theme = get_themed_colors()
    all_colors = theme['colors']
    mode_1_color = all_colors[0]
    mode_2_color = all_colors[1] if len(all_colors) > 1 else '#4fc3f7'
    full_game_name = f"{game_name}: {installment}" if installment else game_name
    num_stats = len(stats_data)

    fig = plt.figure(figsize=(10.8, 14.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('#1a1a1a')

    import textwrap as _tw

    def rule(y, alpha=0.3, lw=1):
        ax.plot([0.05, 0.95], [y, y], color='white', linewidth=lw,
                alpha=alpha, transform=ax.transAxes)

    def _wrap_mode(name, maxcols=12):
        """Wrap mode name to at most 2 lines."""
        lines = _tw.wrap(name.upper(), width=maxcols)
        return '\n'.join(lines[:2])

    def _fmtv(v):
        """Abbreviate stat value if >=1000, otherwise 1 decimal place."""
        if v >= 1000:
            return format_large_number(round(v, 1))
        return f"{v:.1f}"

    # ── Title (auto-size font to fit image width) ───────────────────────────
    game_len = len(full_game_name)
    if game_len <= 16:   game_title_fs = 62
    elif game_len <= 22: game_title_fs = 56
    elif game_len <= 28: game_title_fs = 48 
    elif game_len <= 34: game_title_fs = 32
    else:                game_title_fs = 28
    
    ax.text(0.5, 0.94, full_game_name, ha='center', va='center',
            fontsize=game_title_fs, fontweight='bold', color='white',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.90, player_name, ha='center', va='center',
            fontsize=30, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)
    rule(0.87)

    # ── 1-stat: table layout ─────────────────────────────────────────────
    if num_stats == 1:
        stat = stats_data[0]
        stat_label = abbreviate_stat(stat['stat_type']).upper()
        val_fs = 72
        max_val_len = max(len(_fmtv(stat['mean1'])), len(_fmtv(stat['mean2'])))
        if max_val_len > 4:
            val_fs = max(int(val_fs * 4 / max_val_len), val_fs // 2)

        # Full-width "TALE OF THE TAPE" title
        ax.text(0.5, 0.80, 'TALE OF THE TAPE', ha='center', va='center',
                fontsize=52, fontweight='bold', color='gray',
                fontfamily='Fira Code', transform=ax.transAxes)
        rule(0.73)

        # Column headers
        col1_x, col2_x = 0.25, 0.72
        ax.text(col1_x, 0.67, 'GAME MODE', ha='center', va='center',
                fontsize=52, color='gray', fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(col2_x, 0.67, stat_label, ha='center', va='center',
                fontsize=52, fontweight='bold', color='gray',
                fontfamily='Fira Code', transform=ax.transAxes)
        rule(0.61, alpha=0.4, lw=0.5)

        # Vertical column divider
        ax.plot([0.5, 0.5], [0.13, 0.73], color='white', alpha=0.2, lw=0.5,
                transform=ax.transAxes)

        # Row 1 — mode_1
        row1_y = 0.49
        m1_alpha = 1.0 if stat['mean1'] >= stat['mean2'] else 0.45
        ax.text(col1_x, row1_y, _wrap_mode(mode_1), ha='center', va='center',
                fontsize=56, fontweight='bold', color=mode_1_color,
                multialignment='center', fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(col2_x, row1_y + 0.02, _fmtv(stat['mean1']), ha='center', va='center',
                fontsize=val_fs, fontweight='bold', color=mode_1_color, alpha=m1_alpha,
                fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(col2_x, row1_y - 0.03, f"n={stat['n1']}", ha='center', va='center',
                fontsize=52, color='gray', fontfamily='Fira Code', transform=ax.transAxes)

        rule(0.37, alpha=0.3, lw=0.5)

        # Row 2 — mode_2
        row2_y = 0.25
        m2_alpha = 1.0 if stat['mean2'] >= stat['mean1'] else 0.45
        ax.text(col1_x, row2_y, _wrap_mode(mode_2), ha='center', va='center',
                fontsize=56, fontweight='bold', color=mode_2_color,
                multialignment='center', fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(col2_x, row2_y + 0.02, _fmtv(stat['mean2']), ha='center', va='center',
                fontsize=val_fs, fontweight='bold', color=mode_2_color, alpha=m2_alpha,
                fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(col2_x, row2_y - 0.03, f"n={stat['n2']}", ha='center', va='center',
                fontsize=52, color='gray', fontfamily='Fira Code', transform=ax.transAxes)

        rule(0.13)
        _add_branding(fig)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                    facecolor='#1a1a1a', pad_inches=0.2)
        buf.seek(0)
        plt.close(fig)
        return buf

    # ── Column headers (2/3-stat) ─────────────────────────────────────────
    # "TALE OF THE TAPE" sits at the same y-level as the mode names, centred
    ax.text(0.5, 0.78, 'TALE OF\nTHE TAPE', ha='center', va='center',
            fontsize=33, color='gray', style='italic', multialignment='center',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.18, 0.78, _wrap_mode(mode_1), ha='center', va='center',
            fontsize=33, fontweight='bold', color=mode_1_color,
            multialignment='center', fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.82, 0.78, _wrap_mode(mode_2), ha='center', va='center',
            fontsize=33, fontweight='bold', color=mode_2_color,
            multialignment='center', fontfamily='Fira Code', transform=ax.transAxes)
    rule(0.72)

    # ── Stat rows — stacked: value (top) → label → n= (bottom) ────────────
    # row centers distributed evenly between top rule (0.72) and bottom rule (0.13).
    # For N rows: spacing = 0.59/N, first center = 0.72 - spacing/2.
    if num_stats == 2:
        stat_fs, label_fs, n_fs = 120, 38, 38
        val_off, lbl_off, n_off = 0.040, 0.040, -0.044
        row_y_start, row_spacing = 0.575, 0.30
        val_x1, val_x2 = 0.20, 0.80
    else:  # 3 — equal sections: spacing=0.59/3≈0.197, first center=0.72-0.197/2≈0.622
        stat_fs, label_fs, n_fs = 96, 32, 38
        val_off, lbl_off, n_off = 0.040, 0.040, -0.033
        row_y_start, row_spacing = 0.622, 0.197
        val_x1, val_x2 = 0.18, 0.82

    # Dynamic safeguard: scale stat_fs down if any formatted value exceeds 4 chars
    max_val_len = max(
        max(len(_fmtv(s['mean1'])) for s in stats_data),
        max(len(_fmtv(s['mean2'])) for s in stats_data),
    )
    if max_val_len > 4:
        stat_fs = max(int(stat_fs * 4 / max_val_len), stat_fs // 2)

    for i, stat in enumerate(stats_data):
        y = row_y_start - i * row_spacing
        m1_alpha = 1.0 if stat['mean1'] >= stat['mean2'] else 0.45
        m2_alpha = 1.0 if stat['mean2'] >= stat['mean1'] else 0.45

        ax.text(val_x1, y + val_off, _fmtv(stat['mean1']), ha='center', va='center',
                fontsize=stat_fs, fontweight='bold', color=mode_1_color, alpha=m1_alpha,
                fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(val_x1, y + n_off, f"n={stat['n1']}", ha='center', va='center',
                fontsize=n_fs, color='gray',
                fontfamily='Fira Code', transform=ax.transAxes)

        ax.text(0.5, y + lbl_off, abbreviate_stat(stat['stat_type']).upper(),
                ha='center', va='center', fontsize=label_fs, fontweight='bold', color='white',
                fontfamily='Fira Code', transform=ax.transAxes)

        ax.text(val_x2, y + val_off, _fmtv(stat['mean2']), ha='center', va='center',
                fontsize=stat_fs, fontweight='bold', color=mode_2_color, alpha=m2_alpha,
                fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(val_x2, y + n_off, f"n={stat['n2']}", ha='center', va='center',
                fontsize=n_fs, color='gray',
                fontfamily='Fira Code', transform=ax.transAxes)

        if i < num_stats - 1:
            rule(y - row_spacing / 2, alpha=0.2, lw=0.5)

    rule(0.13)
    _add_branding(fig)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor='#1a1a1a', pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_comparison_caption(game_info, mode_1, mode_2, stats, player_name, day_of_week):
    """Caption for Tuesday/Thursday game mode comparison posts."""
    full_game_name = (f"{game_info['game_name']}: {game_info['game_installment']}"
                      if game_info.get('game_installment') else game_info['game_name'])
    day_hashtags_map = {
        'Tuesday':  '#GamingThreads #TuesdayVibes #GamingTuesday',
        'Thursday': '#GamingThreads #ThrowbackThursday #GamingThursday',
    }
    day_tag = day_hashtags_map.get(day_of_week, '#GamingThreads')

    lines = [
        f"⚔️ {full_game_name} Mode Breakdown ⚔️ {day_tag}",
        "",
        f"{mode_1} vs {mode_2} — which mode hits harder?",
        "",
    ]
    for stat in stats:
        winner = mode_1 if stat['mean1'] >= stat['mean2'] else mode_2
        lines.append(
            f"• {stat['stat_type']}: {mode_1} {stat['mean1']:.1f} | {mode_2} {stat['mean2']:.1f} → {winner} leads"
        )

    game_handle = get_game_handle(game_info['game_name'], platform='instagram')
    game_hashtags = get_game_hashtags(game_info['game_name'], platform='instagram')

    lines += [
        "",
        f"Playing {game_handle}" if game_handle else f"Playing {full_game_name}",
        "",
        "💬 Which mode do YOU prefer? Drop your take below 👇",
        "❤️ Like if you're messsing with the winning mode & 🔁 repost to settle the debate!",
        "",
        "📲 Follow for daily stats, weekly recaps & more!",
        "",
    ]

    base_hashtags = ['#gaming', '#esports', '#casual', '#gamer', '#gamingcommunity', '#statsnerds']
    all_hashtags = base_hashtags + game_hashtags
    seen, unique_hashtags = set(), []
    for tag in all_hashtags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique_hashtags.append(tag)

    lines.append(' '.join(unique_hashtags))
    youtube_handle = os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')
    lines += ["", f"📺 YouTube: {youtube_handle} | Link in bio"]

    caption = '\n'.join(lines)
    return caption[:2200] if len(caption) > 2200 else caption


def run_tuesday_thursday_poster():
    """Run the Tuesday/Thursday game mode comparison (Tale of the Tape) poster."""
    logger.info("⚔️  Running Tale of the Tape comparison poster...")

    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    day_of_week = now_local.strftime('%A')
    use_holiday_theme = is_exact_holiday() is not None

    data = get_tale_of_tape_data(PLAYER_ID)
    if not data:
        # Fallback 1: regular stats post
        logger.warning("⚠️ No Tale of the Tape data — falling back to regular stats post...")
        try:
            return run_instagram_poster()
        except Exception as fallback_err:
            # Fallback 2: skip gracefully
            logger.warning(f"⚠️ Regular stats fallback also failed: {fallback_err} — skipping post")
            return {'posted': False, 'reason': 'No Tale of the Tape data and no recent stats'}

    logger.info(f"🎮 {data['game_name']} — {data['mode_1']} vs {data['mode_2']}")
    logger.info(f"📊 Stats: {[s['stat_type'] for s in data['stats']]}")

    image_buffer = create_tale_of_tape_chart(
        data['game_name'], data['game_installment'],
        data['mode_1'], data['mode_2'], data['stats'],
        player_name, use_holiday_theme
    )

    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(gcs_buffer, player_name, data['game_name'], 'comparison')
        if gcs_url:
            logger.info(f"✅ Backed up to GCS: {gcs_url}")
    except Exception as gcs_error:
        logger.warning(f"⚠️  GCS backup error: {gcs_error}")

    game_info = {'game_name': data['game_name'], 'game_installment': data['game_installment']}
    caption = generate_comparison_caption(
        game_info, data['mode_1'], data['mode_2'], data['stats'], player_name, day_of_week
    )
    logger.info(f"📝 Caption:\n{caption}\n")

    if not post_to_instagram(image_buffer, caption):
        raise Exception("Failed to post comparison to Instagram")

    logger.info("✅ Tale of the Tape posted!")
    return {
        'posted': True, 'post_type': 'comparison',
        'game': data['game_name'], 'mode_1': data['mode_1'],
        'mode_2': data['mode_2'], 'player': player_name,
    }


# ============================================================================
# SATURDAY: WEEKLY SUMMARY
# ============================================================================

def get_weekly_summary_data(player_id, week_start, week_end):
    """Fetch gaming summary for week_start–week_end (both inclusive)."""
    overview = execute_query(
        """
        SELECT
            COUNT(DISTINCT game_id)   AS games_played,
            COUNT(DISTINCT played_at) AS sessions
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND (played_at AT TIME ZONE %s)::DATE
              BETWEEN %s AND %s;
        """,
        (player_id, TIMEZONE_STR, week_start, week_end)
    )
    if not overview:
        return None

    games_played = int(get_field_value(overview[0][0]) or 0)
    sessions     = int(get_field_value(overview[0][1]) or 0)
    if sessions == 0:
        return None

    top_stat = execute_query(
        """
        SELECT stat_type, stat_value
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND (played_at AT TIME ZONE %s)::DATE
              BETWEEN %s AND %s
        ORDER BY stat_value DESC
        LIMIT 1;
        """,
        (player_id, TIMEZONE_STR, week_start, week_end)
    )

    top_day_raw = execute_query(
        """
        SELECT (played_at AT TIME ZONE %s)::DATE AS play_date,
               COUNT(*) AS cnt
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND (played_at AT TIME ZONE %s)::DATE
              BETWEEN %s AND %s
        GROUP BY played_at, (played_at AT TIME ZONE %s)::DATE
        ORDER BY cnt DESC, play_date ASC
        LIMIT 1;
        """,
        (TIMEZONE_STR, player_id, TIMEZONE_STR, week_start, week_end, TIMEZONE_STR)
    )

    if top_day_raw:
        top_date_val = get_field_value(top_day_raw[0][0])
        if top_date_val:
            if isinstance(top_date_val, str):
                from datetime import datetime as _dt
                top_date_val = _dt.strptime(top_date_val[:10], '%Y-%m-%d').date()
            top_day_name = top_date_val.strftime('%A')
        else:
            top_day_name = 'N/A'
    else:
        top_day_name = 'N/A'

    return {
        'games_played':   games_played,
        'sessions':       sessions,
        'top_day':        top_day_name,
        'top_stat_name':  get_field_value(top_stat[0][0]) if top_stat else 'N/A',
        'top_stat_value': int(get_field_value(top_stat[0][1]) or 0) if top_stat else 0,
        'week_start':     week_start,
        'week_end':       week_end,
    }


_NO_RECAP_CAPTIONS = [
    "Taking a break this week! 🕹️\n\nDrop a comment — what games are you playing right now? 👇",
    "Week off from gaming! 😤\n\nWhat's the longest gaming session you've had this year? Let me know! 💬",
    "No recap this week — life happened! 😅\n\nWhat's a game you keep meaning to play but never get around to? 🎮",
    "Skipped the controller this week! 🎮\n\nWhat milestone did YOU hit in a game recently? Share it below! 👇",
    "Rest week! 😴\n\nIf you could only play one game for the rest of the year, what would it be? 🔥",
    "No games logged this week! 📊\n\nWhat's your go-to game when you only have 30 minutes? Comment below! ⏱️",
    "Taking a breather this week! 🌬️\n\nWhat's the hardest game you've ever beaten? Brag a little! 💪",
    "Week off from the grind! 🏃\n\nWhat game has the best soundtrack in your opinion? Drop it below! 🎵",
    "No sessions this week! 📉\n\nBattle Royale or Resurgence — which do you prefer and why? 👇",
    "Recharging for next week! 🔋\n\nWhat's a game you think is underrated that more people should try? 🎯",
    "Off the sticks this week! 🕹️\n\nCo-op or solo — how do you prefer to play? Let me know! 🤝",
    "No weekly recap this time! 📆\n\nWhat's your biggest gaming achievement of 2026 so far? Share below! 🏆",
]


def create_no_weekly_recap_chart(player_name, use_holiday_theme=False):
    """Create a bold placeholder 'No Weekly Recap' chart (1080x1440)."""
    theme = get_themed_colors()
    accent = theme['colors'][0] if use_holiday_theme else '#00ff41'

    fig = plt.figure(figsize=(10.8, 14.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('#0a0a0a')

    ax.text(0.5, 0.72, 'NO WEEKLY', ha='center', va='center',
            fontsize=150, fontweight='bold', color=accent,
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.56, 'RECAP', ha='center', va='center',
            fontsize=150, fontweight='bold', color='white',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.42, 'THIS WEEK', ha='center', va='center',
            fontsize=64, fontweight='bold', color='#888888',
            fontfamily='Fira Code', transform=ax.transAxes)

    # Divider line
    ax.plot([0.2, 0.8], [0.35, 0.35], color=accent, linewidth=2, transform=ax.transAxes)

    ax.text(0.5, 0.25, f'— {player_name} —', ha='center', va='center',
            fontsize=64, color='#555555', fontstyle='italic',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.14, 'Back next week!', ha='center', va='center',
            fontsize=52, color='#444444',
            fontfamily='Fira Code', transform=ax.transAxes)

    _add_branding(fig)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor='#0a0a0a', pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_no_weekly_recap_caption(player_name):
    """Return a randomized engagement caption for a no-recap week."""
    base = random.choice(_NO_RECAP_CAPTIONS)
    return (
        f"📊 {player_name}'s Weekly Recap 📊\n\n"
        f"{base}\n\n"
        f"#gaming #stats #gamingcommunity #WeeklyRecap #gamer"
    )


def create_weekly_summary_chart(summary, player_name, use_holiday_theme=False):
    """
    Creative weekly summary poster (1080x1440).
    Four large KPI blocks: Games Played, Sessions, Top Day, Top Stat.
    """
    theme = get_themed_colors()
    c = theme['colors']
    week_str = (f"{summary['week_start'].strftime('%b %d')} – "
                f"{summary['week_end'].strftime('%b %d, %Y')}")

    fig = plt.figure(figsize=(10.8, 14.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('#1a1a1a')

    def rule(y, alpha=0.2, lw=1):
        ax.plot([0.08, 0.92], [y, y], color='white', linewidth=lw,
                alpha=alpha, transform=ax.transAxes)

    def kpi_block(icon, label, value, y_center, accent):
        # Scale font down for longer values; ≤5 chars keeps full 122pt
        val_fs = min(122, int(122 * 5 / max(5, len(value))))
        ax.text(0.5, y_center + 0.065, f"{icon}  {label}",
                ha='center', va='center', fontsize=26, color='gray',
                fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(0.5, y_center - 0.015, value,
                ha='center', va='center', fontsize=val_fs, fontweight='bold',
                color=accent, fontfamily='Fira Code', transform=ax.transAxes)

    # ── Header ─────────────────────────────────────────────────────────────
    ax.text(0.5, 0.94, 'WEEK IN REVIEW', ha='center', va='center',
            fontsize=72, fontweight='bold', color='white',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.88, week_str, ha='center', va='center',
            fontsize=44, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.83, player_name, ha='center', va='center',
            fontsize=44, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)
    rule(0.80)

    # ── 4 KPI blocks — evenly distributed between 0.80 and 0.13 ───────────
    # Unicode symbols that render in Fira Code (no emoji glyphs needed)
    block_ys = [0.716, 0.548, 0.381, 0.214]

    kpi_block('\u25cf', 'GAMES PLAYED', str(summary['games_played']),
              block_ys[0], c[0])
    rule(0.633, alpha=0.15)

    kpi_block('\u25c9', 'GAME SESSIONS', str(summary['sessions']),
              block_ys[1], c[1] if len(c) > 1 else c[0])
    rule(0.465, alpha=0.15)

    kpi_block('\u25c6', 'TOP GAMING DAY', summary['top_day'],
              block_ys[2], c[2] if len(c) > 2 else c[0])
    rule(0.298, alpha=0.15)

    top_stat_display = (f"{abbreviate_stat(summary['top_stat_name'])}: "
                        f"{format_large_number(summary['top_stat_value'])}")
    kpi_block('\u25b2', 'TOP STAT OF THE WEEK', top_stat_display,
              block_ys[3], c[3] if len(c) > 3 else c[0])
    rule(0.13)

    _add_branding(fig)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor='#1a1a1a', pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_weekly_caption(summary, player_name):
    """Caption for Saturday weekly summary posts."""
    week_str = (f"{summary['week_start'].strftime('%b %d')} – "
                f"{summary['week_end'].strftime('%b %d, %Y')}")
    lines = [
        f"📊 Weekly Gaming Recap | {week_str} 📊",
        "",
        f"🎮 {summary['games_played']} game(s) played this week",
        f"🔥 {summary['sessions']} session(s) logged",
        f"📅 Top gaming day: {summary['top_day']}",
        f"🏆 Best stat: {summary['top_stat_name']} — {summary['top_stat_value']}",
        "",
        "Another week, another grind. Follow the Data Journey!",
        "",
        "💬 How was your gaming week? Share your best moment below 👇",
        "❤️ Like if you hit a personal best this week & 🔁 repost to support the weekly grind!",
        "",
        "📲 Follow for daily stats, weekly recaps & more!",
        "",
    ]
    base_hashtags = [
        '#GamingThreads','#gaming', '#esports', '#casual', '#gamer', '#gamingcommunity',
        '#weeklyrecap', '#GamingSaturday', '#GameStats',
    ]
    lines.append(' '.join(base_hashtags))
    youtube_handle = os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')
    lines += ["", f"📺 YouTube: {youtube_handle} | Link in bio"]
    caption = '\n'.join(lines)
    return caption[:2200] if len(caption) > 2200 else caption


def run_saturday_poster():
    """Run the Saturday weekly summary poster."""
    logger.info("📊 Running Saturday weekly summary poster...")

    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    today      = now_local.date()
    week_end   = today - timedelta(days=1)   # Friday
    week_start = today - timedelta(days=7)   # Previous Saturday
    use_holiday_theme = is_exact_holiday() is not None

    summary = get_weekly_summary_data(PLAYER_ID, week_start, week_end)

    if not summary:
        logger.info("📭 No gaming data this week — posting 'No Weekly Recap' placeholder...")
        image_buffer = create_no_weekly_recap_chart(player_name, use_holiday_theme)
        caption = generate_no_weekly_recap_caption(player_name)
    else:
        logger.info(f"📈 Week summary: {summary}")
        image_buffer = create_weekly_summary_chart(summary, player_name, use_holiday_theme)
        caption = generate_weekly_caption(summary, player_name)

    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(
            gcs_buffer, player_name,
            'no_weekly_recap' if not summary else 'weekly_summary', 'weekly'
        )
        if gcs_url:
            logger.info(f"✅ Backed up to GCS: {gcs_url}")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS backup error: {gcs_error}")

    logger.info(f"📝 Caption:\n{caption}\n")

    if not post_to_instagram(image_buffer, caption):
        raise Exception("Failed to post Saturday content to Instagram")

    post_type = 'weekly_summary' if summary else 'no_weekly_recap'
    logger.info(f"✅ Saturday post ({post_type}) complete!")
    return {
        'posted': True, 'post_type': post_type,
        'games_played': summary['games_played'] if summary else 0,
        'sessions': summary['sessions'] if summary else 0, 'player': player_name,
    }


# ============================================================================
# NEW YEAR'S DAY: YEARLY RECAP
# ============================================================================

# Ordered list of (genre_keywords, gamer_type_name, tagline).
# Covers all genres and subgenres from app_utils.py GENRES dict.
# More specific entries (subgenres, niche genres) listed first so they win over broad categories.
_GAMER_TYPES = [
    # ── Specific subgenres first ───────────────────────────────────────────
    (['Soulslike'],                                                   'The Soulsborn',         'Everyone has an expiration date.'),
    (['Battle Royale'],                                               'The Last One Standing', 'Drop in. Outlast. Win.'),
    (['MOBA'],                                                        'The Strategist',        'Every macro move matters.'),
    (['Hack-and-Slash', 'Masher'],                                    'The Blade Dancer',      'Skill is the only stat that matters.'),
    (['Metroidvania'],                                                'The Explorer',          'Every path leads somewhere new.'),
    (['Roguelike', 'Dungeon Crawler'],                                'The Rogue',             'Permadeath is a feature, not a bug.'),
    (['Monster-Taming'],                                              'The Tamer',             'Gotta catch the meta.'),
    (['Walking Simulator', 'Visual Novel', 'Interactive Movie'],      'The Storyteller',       'Here for the narrative.'),
    (['Escape Room'],                                                 'The Puzzle Master',     'No room can hold them.'),
    (['Social Deduction'],                                            'The Deceiver',          'Trust no one.'),
    (['Auto Battler'],                                                'The Economist',         'Comp is everything.'),
    (['Tower Defense'],                                               'The Defender',          'No unit gets through.'),
    (['4X'],                                                          'The Emperor',           'Explore. Expand. Exploit. Exterminate.'),
    # ── Genre-level matches ────────────────────────────────────────────────
    (['Massively Multiplayer', 'MMORPG', 'MMORPGs'],                  'The Guild Master',      'Never raids alone.'),
    (['Action RPG', 'Action RPGs'],                                   'The Blade Dancer',      'Skill is the only stat that matters.'),
    (['Tactical RPG', 'Tacical RPG', 'Tactical'],                     'The Tactician',         'Every grid square counts.'),
    (['Real-Time Strategy', 'RTS', 'Real-Time Strategy (RTS)'],       'The Commander',         'Macro wins. Always.'),
    (['Stealth'],                                                     'The Phantom',           'Strike before they see you.'),
    (['Survival Horror', 'Horror', 'Survival'],                       'The Survivor',          'Thrives where others fear.'),
    (['First-Person Shooter', 'FPS', 'First\u2011Person Shooter',
      'First‑Person Shooter (FPS)'],                                  'The Sharpshooter',      'Precision. Reflexes. Domination.'),
    (['Shooter'],                                                     'The Gunslinger',        'Locked, loaded, and lethal.'),
    (['Simulation'],                                                  'The Architect',         'Building worlds, one sim at a time.'),
    (['Platformer', 'Platformers'],                                   'The Platformer',        'One more jump. Always.'),
    (['Puzzle'],                                                      'The Problem Solver',    'Logic is the way.'),
    (['Strategy'],                                                    'The Grand Strategist',  'Always three steps ahead.'),
    (['Role-Playing', 'RPG', 'Role\u2011Playing (RPG)'],              'The Adventurer',        'Living for the story.'),
    (['Fighting'],                                                    'The Kombatant',         'Mastering the meta.'),
    (['Racing'],                                                      'The Speedster',         'First across the line.'),
    (['Sports'],                                                      'The Competitor',        'Here to win, always.'),
    (['Adventure'],                                                   'The Explorer',          'Every path leads somewhere new.'),
    (['Action-Adventure', 'Action '],                                 'The Warrior',           'Bold moves, big results.'),
    (['Party'],                                                       'The Party Animal',      'Every game is more fun with friends.'),
    (['Casual'],                                                      'The Chill Gamer',       'Gaming on your terms.'),
]


def generate_gamer_type(genres_played):
    """Return (type_name, tagline) based on the genres the player played most."""
    genres_upper = [g.upper() for g in genres_played if g]
    for keywords, type_name, tagline in _GAMER_TYPES:
        for kw in keywords:
            if any(kw.upper() in g for g in genres_upper):
                return type_name, tagline
    return 'The All-Rounder', 'A little bit of everything.'


def get_yearly_recap_data(player_id, year):
    """Fetch all data needed for the yearly recap poster."""
    game_records = execute_query(
        """
        SELECT
            g.game_name,
            g.game_installment,
            g.game_genre,
            g.game_subgenre,
            COUNT(DISTINCT f.played_at) AS sessions
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = %s
          AND EXTRACT(YEAR FROM (f.played_at AT TIME ZONE %s)) = %s
        GROUP BY g.game_name, g.game_installment, g.game_genre, g.game_subgenre
        ORDER BY sessions DESC;
        """,
        (player_id, TIMEZONE_STR, year)
    )
    if not game_records:
        return None

    games = []
    total_sessions = 0
    genres_seen = []    # includes both genre and subgenre strings for gamer-type matching
    for row in game_records:
        game_name   = get_field_value(row[0])
        installment = get_field_value(row[1])
        genre       = get_field_value(row[2])
        subgenre    = get_field_value(row[3])
        sessions    = int(get_field_value(row[4]) or 0)
        total_sessions += sessions
        games.append({'game_name': game_name, 'installment': installment,
                      'genre': genre, 'sessions': sessions})
        if genre and genre not in genres_seen:
            genres_seen.append(genre)
        if subgenre and subgenre not in genres_seen:
            genres_seen.append(subgenre)

    for g in games:
        g['pct'] = round(g['sessions'] / total_sessions * 100) if total_sessions > 0 else 0

    top_stat = execute_query(
        """
        SELECT stat_type, stat_value
        FROM fact.fact_game_stats
        WHERE player_id = %s
          AND EXTRACT(YEAR FROM (played_at AT TIME ZONE %s)) = %s
        ORDER BY stat_value DESC
        LIMIT 1;
        """,
        (player_id, TIMEZONE_STR, year)
    )

    gamer_type, gamer_tagline = generate_gamer_type(genres_seen)
    return {
        'year':           year,
        'total_sessions': total_sessions,
        'games':          games[:3],
        'genres':         genres_seen[:3],
        'top_stat_name':  get_field_value(top_stat[0][0]) if top_stat else 'N/A',
        'top_stat_value': int(get_field_value(top_stat[0][1]) or 0) if top_stat else 0,
        'gamer_type':     gamer_type,
        'gamer_tagline':  gamer_tagline,
    }


def create_yearly_recap_chart(recap, player_name, use_holiday_theme=False):
    """
    Spotify/YouTube-style yearly recap chart (1080x1440).
    Sections: year title → gamer type → top games with % bars → top genres.
    """
    theme = get_themed_colors()
    c = theme['colors']
    year = recap['year']
    num_games = len(recap['games'])

    fig = plt.figure(figsize=(10.8, 14.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('#1a1a1a')

    def rule(y, alpha=0.2, lw=1):
        ax.plot([0.08, 0.92], [y, y], color='white', linewidth=lw,
                alpha=alpha, transform=ax.transAxes)

    # ── Title (auto-size to fill width: "YYYY RECAP" = 10 chars) ───────────
    ax.text(0.5, 0.94, f'{year} RECAP', ha='center', va='center',
            fontsize=80, fontweight='bold', color='white',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.88, player_name, ha='center', va='center',
            fontsize=24, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)
    rule(0.85)

    # ── Gamer Type ─────────────────────────────────────────────────────────
    # Dynamic font: scale to fill ~90% of content width (Fira Code char ≈ font_pt * 0.833px)
    _content_px    = 907   # 0.84 * 1080px
    gamer_type_fs  = min(70, max(28, int(_content_px * 0.9 / max(1, len(recap['gamer_type'])) / 0.833)))
    ax.text(0.5, 0.82, 'Gamer Type', ha='center', va='center',
            fontsize=20, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.77, recap['gamer_type'], ha='center', va='center',
            fontsize=gamer_type_fs, fontweight='bold', color=c[0],
            fontfamily='Fira Code', transform=ax.transAxes)
    ax.text(0.5, 0.73, recap['gamer_tagline'], ha='center', va='center',
            fontsize=18, color='gray', style='italic',
            fontfamily='Fira Code', transform=ax.transAxes)
    rule(0.70)

    # ── Dynamic layout: distribute space between game rows and genre items ───
    # Available from "Top Games" label (0.67) down to bottom boundary (0.17).
    # Game rows get 2× weight vs genre items so bars stay prominent.
    top_y         = 0.67
    bottom_y      = 0.17
    games_hdr_h   = 0.04   # height consumed by "Top Games" label
    gap_h         = 0.05   # gap between last bar and genres section
    genres_hdr_h  = 0.04   # height consumed by "Top Genres" label
    num_genres    = len(recap['genres'])

    remaining_h   = (top_y - bottom_y) - games_hdr_h - gap_h - genres_hdr_h
    total_units   = num_games * 2 + num_genres        # game rows = 2 units each
    unit_h        = remaining_h / max(1, total_units)
    game_row_h    = unit_h * 2
    genre_item_h  = unit_h

    # Scale fonts and bar from 3-game baseline (game_row_h ≈ 0.082)
    _base_row_h   = 0.082
    game_name_fs  = max(19, int(19 * game_row_h / _base_row_h))
    pct_fs        = game_name_fs
    bar_height    = game_row_h * 0.28
    name_y_off    = game_row_h * 0.31
    bar_y_off     = -game_row_h * 0.06

    game_y_start  = top_y - games_hdr_h - game_row_h / 2   # first row centre

    # Header font scales with num_games; capped at 39pt (50% above base 26pt) for 1-game
    header_fs     = min(39, max(26, int(26 * game_row_h / _base_row_h)))

    # ── Top Games ────────────────────────────────────────────────────────────
    ax.text(0.5, top_y, f"Top {'Games' if num_games > 1 else 'Game'}",
            ha='center', va='center', fontsize=header_fs, color='white',
            fontfamily='Fira Code', transform=ax.transAxes)

    bar_x0, bar_x1 = 0.08, 0.92
    bar_w = bar_x1 - bar_x0

    for i, game in enumerate(recap['games']):
        y = game_y_start - i * game_row_h
        color = c[i % len(c)]
        full_name = (f"{game['game_name']}: {game['installment']}"
                     if game['installment'] else game['game_name'])

        ax.text(bar_x0, y + name_y_off, full_name,
                ha='left', va='center', fontsize=game_name_fs, fontweight='bold',
                color='white', fontfamily='Fira Code', transform=ax.transAxes)
        ax.text(bar_x1, y + name_y_off, f"{game['pct']}%",
                ha='right', va='center', fontsize=pct_fs, fontweight='bold',
                color=color, fontfamily='Fira Code', transform=ax.transAxes)

        ax.barh([y + bar_y_off], [bar_w], left=bar_x0, height=bar_height, color='#333333')
        ax.barh([y + bar_y_off], [bar_w * (game['pct'] / 100)],
                left=bar_x0, height=bar_height, color=color, alpha=0.85)

    # Genres section anchors off the bottom edge of the last game row
    last_game_bottom = game_y_start - (num_games - 1) * game_row_h - game_row_h / 2
    genres_y = last_game_bottom - gap_h
    rule(last_game_bottom - gap_h / 2)

    # Distribute genres evenly from header down to just above bottom rule (0.16)
    # so they fill the full divider section regardless of num_games
    _genres_bottom = 0.16
    genre_spacing  = (genres_y - _genres_bottom) / num_genres
    # Scale genre font from 3-game baseline spacing (≈ 0.058 → 24pt)
    genre_fs       = max(24, int(24 * genre_spacing / 0.058))

    # ── Top Genres ───────────────────────────────────────────────────────────
    ax.text(0.5, genres_y, 'Top Genres', ha='center', va='center',
            fontsize=header_fs, color='white',
            fontfamily='Fira Code', transform=ax.transAxes)
    for j, genre in enumerate(recap['genres']):
        gy = genres_y - genre_spacing * (j + 1)
        ax.text(0.5, gy, genre, ha='center', va='center',
                fontsize=genre_fs, color=c[j % len(c)],
                fontfamily='Fira Code', transform=ax.transAxes)

    rule(0.13)
    sessions_display = format_large_number(recap['total_sessions'])
    ax.text(0.5, 0.10, f"{sessions_display} sessions in {year}",
            ha='center', va='center', fontsize=22, color='gray',
            fontfamily='Fira Code', transform=ax.transAxes)

    _add_branding(fig)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor='#1a1a1a', pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_yearly_recap_caption(recap, player_name):
    """Caption for New Year's Day yearly recap post."""
    year = recap['year']
    lines = [
        f"🎮 {year} Gaming Recap 🎮",
        "",
        f"Gamer Type: {recap['gamer_type']}",
        f'"{recap["gamer_tagline"]}"',
        "",
        f"📊 {recap['total_sessions']} sessions logged in {year}",
    ]
    if recap['games']:
        lines += ["", "Top Games:"]
        for g in recap['games']:
            full_name = (f"{g['game_name']}: {g['installment']}"
                         if g['installment'] else g['game_name'])
            lines.append(f"• {full_name} ({g['pct']}%)")
    if recap['top_stat_name'] != 'N/A':
        lines += ["", f"🏆 Best stat: {recap['top_stat_name']} — {recap['top_stat_value']}"]
    lines += [
        "",
        "New year. New games. Same grind. 🔥",
        "",
        "💬 What was your biggest gaming achievement this year? Drop it below 👇",
        "❤️ Like if you're locking in for an even bigger year & 🔁 repost to inspire your crew!",
        "",
        "📲 Follow for daily stats, weekly recaps & more!",
        "",
    ]
    base_hashtags = [
        'GamingThreads', '#gaming', '#NewYearsDay', '#GamingRecap', '#YearInReview',
        f'#{year}Wrapped', '#gamer', '#esports', '#gamingcommunity',
    ]
    lines.append(' '.join(base_hashtags))
    youtube_handle = os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')
    lines += ["", f"📺 YouTube: {youtube_handle} | Link in bio"]
    caption = '\n'.join(lines)
    return caption[:2200] if len(caption) > 2200 else caption


def run_new_years_poster():
    """Run the New Year's Day yearly recap poster."""
    logger.info("🎊 Running New Year's Day yearly recap poster...")

    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise Exception(f"No player data found for player_id={PLAYER_ID}")

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    recap_year = now_local.year - 1   # recap covers the PREVIOUS calendar year
    use_holiday_theme = is_exact_holiday() is not None

    recap = get_yearly_recap_data(PLAYER_ID, recap_year)
    if not recap:
        raise Exception(f"No gaming data found for {recap_year} — skipping yearly recap")

    logger.info(f"📅 {recap_year} recap: {recap['total_sessions']} sessions, "
                f"gamer type: {recap['gamer_type']}")

    image_buffer = create_yearly_recap_chart(recap, player_name, use_holiday_theme)

    try:
        gcs_buffer = io.BytesIO(image_buffer.getvalue())
        gcs_url = upload_instagram_poster_to_gcs(
            gcs_buffer, player_name, f'yearly_recap_{recap_year}', 'yearly'
        )
        if gcs_url:
            logger.info(f"✅ Backed up to GCS: {gcs_url}")
    except Exception as gcs_error:
        logger.warning(f"⚠️ GCS backup error: {gcs_error}")

    caption = generate_yearly_recap_caption(recap, player_name)
    logger.info(f"📝 Caption:\n{caption}\n")

    if not post_to_instagram(image_buffer, caption):
        raise Exception("Failed to post yearly recap to Instagram")

    logger.info(f"✅ {recap_year} yearly recap posted!")
    return {
        'posted': True, 'post_type': 'yearly_recap',
        'year': recap_year, 'gamer_type': recap['gamer_type'],
        'player': player_name,
    }


def get_queue_result_for_today():
    """
    Route to the correct _for_queue function based on day of week.
    Jan 1 (New Year's Day) overrides everything and runs yearly recap.
    Returns None on Sunday (no post scheduled).
    """
    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))

    if now_local.month == 1 and now_local.day == 1:
        logger.info("🎊 New Year's Day — routing to yearly recap")
        return run_new_years_poster_for_queue()

    day = now_local.strftime('%A')
    logger.info(f"📅 Routing queue function for {day}")

    if day in ('Monday', 'Wednesday', 'Friday'):
        return run_instagram_poster_for_queue()
    elif day in ('Tuesday', 'Thursday'):
        return run_tuesday_thursday_poster_for_queue()
    elif day == 'Saturday':
        return run_saturday_poster_for_queue()
    else:  # Sunday
        logger.info("📵 Sunday — no post scheduled")
        return None


# Backward compatibility for non-Lambda execution
if __name__ == "__main__":
    _now = datetime.now(ZoneInfo(TIMEZONE_STR))

    if _now.month == 1 and _now.day == 1:
        result = run_new_years_poster()
    else:
        _day = _now.strftime('%A')
        if _day in ('Monday', 'Wednesday', 'Friday'):
            result = run_instagram_poster()
        elif _day in ('Tuesday', 'Thursday'):
            result = run_tuesday_thursday_poster()
        elif _day == 'Saturday':
            result = run_saturday_poster()
        else:
            logger.info("📵 Sunday — no post scheduled")
            result = {'posted': False, 'reason': 'No post on Sunday'}
    logger.info(f"Result: {result}")