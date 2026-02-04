"""
Instagram Automated Poster
Posts gaming stats to Instagram on Monday, Wednesday, Friday at 9 PM PST

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
from datetime import datetime, timedelta
import random
import io
import requests
from chart_utils import abbreviate_stat, format_large_number, load_custom_fonts, should_use_log_scale
from holiday_themes import get_themed_colors, is_exact_holiday
from gcs_utils import upload_instagram_poster_to_gcs  # GCS backup integration
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import hashlib

# Environment variables
DB_URL = os.environ.get("DB_URL")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
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

# Instagram game account handles (@ mentions)
GAME_HANDLES = {
    # --- Publishers & Studios ---
    'ad hoc studio': '@theadhocstudio',
    'electronic arts': '@ea',
    'ea': '@ea',
    'activision': '@activision',
    'blizzard': '@blizzard_ent',
    'ubisoft': '@ubisoft',
    'bethesda': '@bethesda',
    'rockstar games': '@rockstargames',
    'nintendo': '@nintendoamerica',
    'playstation': '@playstation',
    'xbox': '@xbox',
    'riot games': '@riotgames',
    'epic games': '@epicgames',
    'square enix': '@squareenix',
    'capcom': '@capcom_unity',
    'cd projekt red': '@cdprojektred',
    'fromsoftware': '@fromsoftware_pr',
    'valve': '@valvesoftware',
    'bioware': '@bioware',
    'naughty dog': '@naughty_dog',
    'insomniac games': '@insomniacgames',
    'bungie': '@bungie',

    # --- Popular Franchises & Titles ---
    'call of duty': '@callofduty',
    'warzone': '@callofduty',
    'apex legends': '@playapex',
    'fortnite': '@fortnite',
    'valorant': '@valorant',
    'overwatch': '@playoverwatch',
    'overwatch 2': '@playoverwatch',
    'rocket league': '@rocketleague',
    'fifa': '@easportsfifa',
    'fc 24': '@easportsfc',
    'fc 25': '@easportsfc',
    'madden': '@eamaddennfl',
    'nba 2k': '@nba2k',
    'mlb the show': '@mlbtheshow',
    'minecraft': '@minecraft',
    'gta': '@rockstargames',
    'grand theft auto': '@rockstargames',
    'red dead': '@rockstargames',
    'destiny': '@destinythegame',
    'destiny 2': '@destinythegame',
    'halo': '@halo',
    'battlefield': '@battlefield',
    'fallout': '@fallout',
    'elder scrolls': '@elderscrolls',
    'skyrim': '@elderscrolls',
    'dark souls': '@darksouls',
    'elden ring': '@eldenring',
    'resident evil': '@residentevil',
    'street fighter': '@streetfighter',
    'mortal kombat': '@mortalkombat',
    'tekken': '@tekken',
    'league of legends': '@leagueoflegends',
    'dota': '@dota2',
    'counter-strike': '@counterstrike',
    'csgo': '@counterstrike',
    'cs2': '@counterstrike',
    'rainbow six': '@rainbow6game',
    'pubg': '@pubg',
    'warframe': '@playwarframe',
    'diablo': '@diablo',
    'world of warcraft': '@warcraft',
    'starcraft': '@starcraft',
    'sims': '@thesims',
    'animal crossing': '@animalcrossing',
    'zelda': '@zelda',
    'pokemon': '@pokemon',
    'super smash bros': '@smashbrosus',
    'mario kart': '@mariokart',
    'splatoon': '@splatoon',
    'god of war': '@santamonicastu',
    'spider-man': '@insomniacgames',
    'last of us': '@naughty_dog',
    'uncharted': '@naughty_dog',
    'horizon': '@guerrilla',
    'ghost of tsushima': '@suckerpunchprod',
    'final fantasy': '@finalfantasy',
    'monster hunter': '@monsterhunter',
    'dragon ball': '@dragonballgames',
    'naruto': '@narutogames',
    'one piece': '@onepiecegames',
}


def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_URL,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=5439,
            connect_timeout=10,
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


def get_posted_content_hash():
    """
    Get hash of previously posted content to prevent duplicates.
    Stores in a simple table or file.
    
    Returns:
        set: Set of content hashes that have been posted
    """
    hash_file = '/tmp/instagram_post_hashes.txt'
    
    if not os.path.exists(hash_file):
        return set()
    
    try:
        with open(hash_file, 'r') as f:
            hashes = set(line.strip() for line in f if line.strip())
        return hashes
    except:
        return set()


def save_content_hash(content_hash):
    """Save content hash to prevent future duplicates"""
    hash_file = '/tmp/instagram_post_hashes.txt'
    
    try:
        with open(hash_file, 'a') as f:
            f.write(f"{content_hash}\n")
    except Exception as e:
        print(f"⚠️ Could not save content hash: {e}")


def generate_content_hash(stats, game_name, date_str=None):
    """
    Generate unique hash for content to detect duplicates.
    Based on: stats + game + date (if provided)
    """
    content = f"{game_name}_{stats}_{date_str or 'historical'}"
    return hashlib.md5(content.encode()).hexdigest()


def check_games_on_date(cur, player_id, target_date):
    """Check if player has games on a specific date"""
    cur.execute("""
        SELECT COUNT(DISTINCT stat_id)
        FROM fact.fact_game_stats
        WHERE player_id = %s
        AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s;
    """, (player_id, TIMEZONE_STR, target_date))
    
    result = cur.fetchone()
    count = result[0] if result else 0
    return count > 0


def get_all_games_for_player(cur, player_id):
    """Get all games player has played"""
    cur.execute("""
        SELECT DISTINCT g.game_id, g.game_name, g.game_installment
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = %s
        ORDER BY g.game_name;
    """, (player_id,))
    
    games = []
    for row in cur.fetchall():
        games.append({
            'game_id': row[0],
            'game_name': row[1],
            'game_installment': row[2]
        })
    
    return games


def get_player_info(cur, player_id):
    """Get player name"""
    cur.execute("""
        SELECT player_name
        FROM dim.dim_players
        WHERE player_id = %s;
    """, (player_id,))
    
    player_result = cur.fetchone()
    return player_result[0] if player_result else None


def get_stats_for_date(cur, player_id, game_id, target_date):
    """Get all stats for a specific date"""
    cur.execute("""
        SELECT stat_type, AVG(stat_value) as avg_value
        FROM fact.fact_game_stats
        WHERE player_id = %s
        AND game_id = %s
        AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s
        GROUP BY stat_type
        ORDER BY avg_value DESC
        LIMIT 3;
    """, (player_id, game_id, TIMEZONE_STR, target_date))
    
    stats = [(row[0], round(row[1], 1)) for row in cur.fetchall()]
    return stats


def get_stats_for_date_all_games(cur, player_id, target_date):
    """Get stats across ALL games for a date (multi-game posts)"""
    cur.execute("""
        SELECT g.game_name, g.game_installment, stat_type, AVG(stat_value) as avg_value
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = %s
        AND CAST(CONVERT_TIMEZONE(%s, f.played_at) AS DATE) = %s
        GROUP BY g.game_name, g.game_installment, stat_type
        ORDER BY avg_value DESC
        LIMIT 5;
    """, (player_id, TIMEZONE_STR, target_date))
    
    results = []
    for row in cur.fetchall():
        results.append({
            'game': row[0],
            'installment': row[1],
            'stat': row[2],
            'value': round(row[3], 1)
        })
    
    return results


def detect_anomalies(cur, player_id, game_id, target_date):
    """Detect statistical anomalies (records, unusual performances)"""
    anomalies = []
    
    cur.execute("""
        SELECT stat_type, MAX(stat_value) as max_value
        FROM fact.fact_game_stats
        WHERE player_id = %s
        AND game_id = %s
        AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s
        GROUP BY stat_type;
    """, (player_id, game_id, TIMEZONE_STR, target_date))
    
    date_stats = cur.fetchall()
    
    for stat_type, max_value in date_stats:
        cur.execute("""
            SELECT MAX(stat_value) as all_time_max
            FROM fact.fact_game_stats
            WHERE player_id = %s
            AND game_id = %s
            AND stat_type = %s;
        """, (player_id, game_id, stat_type))
        
        all_time_result = cur.fetchone()
        all_time_max = all_time_result[0] if all_time_result else 0
        
        if max_value == all_time_max and max_value > 0:
            anomalies.append({
                'type': 'personal_record',
                'stat': stat_type,
                'value': max_value,
                'description': f"New personal record: {max_value} {stat_type}!"
            })
    
    return anomalies


def get_historical_records_all_games(cur, player_id, posted_hashes, limit=10):
    """
    Get interesting historical records across ALL games.
    Excludes previously posted content to prevent duplicates.
    """
    cur.execute("""
        SELECT g.game_name, g.game_installment, f.stat_type, 
               MAX(f.stat_value) as max_value, 
               CAST(CONVERT_TIMEZONE(%s, f.played_at) AS DATE) as record_date
        FROM fact.fact_game_stats f
        JOIN dim.dim_games g ON f.game_id = g.game_id
        WHERE f.player_id = %s
        GROUP BY g.game_name, g.game_installment, f.stat_type, 
                 CAST(CONVERT_TIMEZONE(%s, f.played_at) AS DATE)
        ORDER BY max_value DESC
        LIMIT 50;
    """, (TIMEZONE_STR, player_id, TIMEZONE_STR))
    
    all_records = cur.fetchall()
    
    # Filter out already posted content
    available_records = []
    for row in all_records:
        game_name, installment, stat_type, max_value, record_date = row
        
        # Create content hash
        stats_tuple = [(stat_type, max_value)]
        content_hash = generate_content_hash(stats_tuple, game_name, str(record_date))
        
        if content_hash not in posted_hashes:
            available_records.append({
                'game': game_name,
                'installment': installment,
                'stat': stat_type,
                'value': max_value,
                'date': record_date,
                'hash': content_hash
            })
    
    # Randomly select from available records
    if len(available_records) >= limit:
        selected = random.sample(available_records, min(limit, len(available_records)))
    else:
        selected = available_records
    
    return selected


def get_game_handle(game_name, game_installment=None):
    """Get Instagram handle for game"""
    search_name = game_name.lower()
    
    # Check direct matches first
    if search_name in GAME_HANDLES:
        return GAME_HANDLES[search_name]
    
    # Check if installment is in handles
    if game_installment:
        installment_lower = game_installment.lower()
        if installment_lower in GAME_HANDLES:
            return GAME_HANDLES[installment_lower]
    
    # Check partial matches
    for key, handle in GAME_HANDLES.items():
        if key in search_name or search_name in key:
            return GAME_HANDLES[key]
    
    return None


def generate_trendy_caption(post_type, stats, game_info, player_name, day_of_week, anomalies=None):
    """
    Generate trendy, concise Instagram captions with hashtags and game mentions.
    Includes heritage month and holiday hashtags automatically.
    """
    from holiday_themes import get_themed_colors
    
    # Get theme info for hashtags
    theme = get_themed_colors()
    
    # Get game handle
    game_handle = get_game_handle(game_info.get('game_name'), game_info.get('game_installment'))
    
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
    
    # Build caption
    caption_parts = []
    
    # Opening line (emoji + hook)
    if post_type == 'daily':
        caption_parts.append(f"📊 Stat of the Day {day_tag}")
    elif post_type == 'recent':
        caption_parts.append(f"📈 Yesterday's Session {day_tag}")
    elif post_type == 'historical':
        caption_parts.append(f"🏆 Record Book {day_tag}")
    elif post_type == 'multi_game':
        caption_parts.append(f"🎮 Multi-Game Grind {day_tag}")
    
    caption_parts.append("")  # Empty line
    
    # Game mention
    game_name = game_info.get('game_name')
    if game_handle:
        caption_parts.append(f"🎯 {game_handle}")
    else:
        caption_parts.append(f"🎯 {game_name}")
    
    caption_parts.append("")  # Empty line
    
    # Stats (concise format)
    if isinstance(stats[0], tuple):
        # Simple tuple format
        for stat, value in stats[:3]:
            caption_parts.append(f"▪️ {stat}: {format_large_number(value)}")
    else:
        # Dict format (multi-game)
        for item in stats[:3]:
            game = item.get('game', game_name)
            stat = item.get('stat')
            value = item.get('value')
            caption_parts.append(f"▪️ {game} - {stat}: {format_large_number(value)}")
    
    # Anomaly/record callout
    if anomalies and len(anomalies) > 0:
        caption_parts.append("")
        caption_parts.append(f"🔥 {anomalies[0]['description']}")
    
    caption_parts.append("")  # Empty line
    
    # Hashtags (game-specific + general)
    hashtags = ['#gaming', '#esports', '#casual', '#gamer', '#gamingcommunity']
    
    # Add game-specific hashtags
    game_name_lower = game_name.lower()

    # --- Publishers & Studios ---
    if 'ad hoc' in game_name_lower:
        hashtags.extend(['#adhocstudio', '#gamedev'])
    elif 'electronic arts' in game_name_lower or game_name_lower == 'ea':
        hashtags.extend(['#ea', '#electronicarts'])
    elif 'activision' in game_name_lower:
        hashtags.extend(['#activision', '#callofduty'])
    elif 'blizzard' in game_name_lower:
        hashtags.extend(['#blizzard', '#overwatch'])
    elif 'ubisoft' in game_name_lower:
        hashtags.extend(['#ubisoft', '#assassinscreed'])
    elif 'bethesda' in game_name_lower:
        hashtags.extend(['#bethesda', '#fallout'])
    elif 'rockstar' in game_name_lower:
        hashtags.extend(['#rockstargames', '#gta'])
    elif 'nintendo' in game_name_lower:
        hashtags.extend(['#nintendo', '#nintendoswitch'])
    elif 'playstation' in game_name_lower:
        hashtags.extend(['#playstation', '#ps5'])
    elif 'xbox' in game_name_lower:
        hashtags.extend(['#xbox', '#xboxseriesx'])
    elif 'riot games' in game_name_lower:
        hashtags.extend(['#riotgames', '#leagueoflegends'])
    elif 'epic games' in game_name_lower:
        hashtags.extend(['#epicgames', '#fortnite'])
    elif 'square enix' in game_name_lower:
        hashtags.extend(['#squareenix', '#finalfantasy'])
    elif 'capcom' in game_name_lower:
        hashtags.extend(['#capcom', '#residentevil'])
    elif 'cd projekt red' in game_name_lower:
        hashtags.extend(['#cdprojektred', '#cyberpunk2077'])
    elif 'fromsoftware' in game_name_lower:
        hashtags.extend(['#fromsoftware', '#eldenring'])
    elif 'valve' in game_name_lower:
        hashtags.extend(['#valve', '#steam'])
    elif 'bioware' in game_name_lower:
        hashtags.extend(['#bioware', '#masseffect'])
    elif 'naughty dog' in game_name_lower:
        hashtags.extend(['#naughtydog', '#thelastofus'])
    elif 'insomniac' in game_name_lower:
        hashtags.extend(['#insomniacgames', '#spiderman'])
    elif 'bungie' in game_name_lower:
        hashtags.extend(['#bungie', '#destiny2'])

    # --- Popular Franchises & Titles ---
    elif 'call of duty' in game_name_lower or 'warzone' in game_name_lower:
        hashtags.extend(['#callofduty', '#warzone', '#cod'])
    elif 'apex' in game_name_lower:
        hashtags.extend(['#apexlegends', '#playapex'])
    elif 'fortnite' in game_name_lower:
        hashtags.extend(['#fortnite', '#fortnitebr'])
    elif 'valorant' in game_name_lower:
        hashtags.extend(['#valorant', '#valorantclips'])
    elif 'overwatch' in game_name_lower:
        hashtags.extend(['#overwatch2', '#overwatch'])
    elif 'rocket league' in game_name_lower:
        hashtags.extend(['#rocketleague', '#rlcs'])
    elif 'fifa' in game_name_lower or 'fc 24' in game_name_lower or 'fc 25' in game_name_lower:
        hashtags.extend(['#eafc', '#easportsfc'])
    elif 'madden' in game_name_lower:
        hashtags.extend(['#madden', '#nfl'])
    elif 'nba 2k' in game_name_lower:
        hashtags.extend(['#nba2k', '#2k'])
    elif 'mlb the show' in game_name_lower:
        hashtags.extend(['#mlbtheshow', '#mlb'])
    elif 'minecraft' in game_name_lower:
        hashtags.extend(['#minecraft', '#minecraftbuilds'])
    elif 'gta' in game_name_lower or 'grand theft auto' in game_name_lower:
        hashtags.extend(['#gtav', '#gta6'])
    elif 'red dead' in game_name_lower:
        hashtags.extend(['#rdr2', '#reddeadredemption'])
    elif 'destiny' in game_name_lower:
        hashtags.extend(['#destiny2', '#destinythegame'])
    elif 'halo' in game_name_lower:
        hashtags.extend(['#haloinfinite', '#halo'])
    elif 'battlefield' in game_name_lower:
        hashtags.extend(['#battlefield', '#fps'])
    elif 'fallout' in game_name_lower:
        hashtags.extend(['#fallout', '#fallout4'])
    elif 'elder scrolls' in game_name_lower or 'skyrim' in game_name_lower:
        hashtags.extend(['#elderscrolls', '#skyrim'])
    elif 'dark souls' in game_name_lower:
        hashtags.extend(['#darksouls', '#fromsoftware'])
    elif 'elden ring' in game_name_lower:
        hashtags.extend(['#eldenring', '#fromsoftware'])
    elif 'resident evil' in game_name_lower:
        hashtags.extend(['#residentevil', '#capcom'])
    elif 'street fighter' in game_name_lower:
        hashtags.extend(['#streetfighter', '#sf6'])
    elif 'mortal kombat' in game_name_lower:
        hashtags.extend(['#mortalkombat', '#mk1'])
    elif 'tekken' in game_name_lower:
        hashtags.extend(['#tekken', '#tekken8'])
    elif 'league of legends' in game_name_lower:
        hashtags.extend(['#leagueoflegends', '#lol'])
    elif 'dota' in game_name_lower:
        hashtags.extend(['#dota2', '#dota'])
    elif 'counter-strike' in game_name_lower or 'csgo' in game_name_lower or 'cs2' in game_name_lower:
        hashtags.extend(['#cs2', '#counterstrike'])
    elif 'rainbow six' in game_name_lower:
        hashtags.extend(['#rainbow6', '#r6siege'])
    elif 'pubg' in game_name_lower:
        hashtags.extend(['#pubg', '#pubgmobile'])
    elif 'warframe' in game_name_lower:
        hashtags.extend(['#warframe', '#tenno'])
    elif 'diablo' in game_name_lower:
        hashtags.extend(['#diablo4', '#diablo'])
    elif 'world of warcraft' in game_name_lower:
        hashtags.extend(['#warcraft', '#worldofwarcraft'])
    elif 'starcraft' in game_name_lower:
        hashtags.extend(['#starcraft', '#starcraft2'])
    elif 'sims' in game_name_lower:
        hashtags.extend(['#thesims', '#sims4'])
    elif 'animal crossing' in game_name_lower:
        hashtags.extend(['#animalcrossing', '#acnh'])
    elif 'zelda' in game_name_lower:
        hashtags.extend(['#zelda', '#legendofzelda'])
    elif 'pokemon' in game_name_lower:
        hashtags.extend(['#pokemon', '#nintendo'])
    elif 'super smash bros' in game_name_lower:
        hashtags.extend(['#smashbros', '#supersmashbros'])
    elif 'mario kart' in game_name_lower:
        hashtags.extend(['#mariokart', '#nintendo'])
    elif 'splatoon' in game_name_lower:
        hashtags.extend(['#splatoon', '#splatoon3'])
    elif 'god of war' in game_name_lower:
        hashtags.extend(['#godofwar', '#ragnarok'])
    elif 'spider-man' in game_name_lower:
        hashtags.extend(['#spidermanps5', '#marvel'])
    elif 'last of us' in game_name_lower:
        hashtags.extend(['#thelastofus', '#tlou'])
    elif 'uncharted' in game_name_lower:
        hashtags.extend(['#uncharted', '#naughtydog'])
    elif 'horizon' in game_name_lower:
        hashtags.extend(['#horizonforbiddenwest', '#playstation'])
    elif 'ghost of tsushima' in game_name_lower:
        hashtags.extend(['#ghostoftsushima', '#suckerpunch'])
    elif 'final fantasy' in game_name_lower:
        hashtags.extend(['#finalfantasy', '#ff7r'])
    elif 'monster hunter' in game_name_lower:
        hashtags.extend(['#monsterhunter', '#mhwilds'])
    elif 'dragon ball' in game_name_lower:
        hashtags.extend(['#dragonball', '#dbz'])
    elif 'naruto' in game_name_lower:
        hashtags.extend(['#naruto', '#anime'])
    elif 'one piece' in game_name_lower:
        hashtags.extend(['#onepiece', '#anime'])
    
    # Add heritage/holiday hashtag if present
    if theme.get('hashtag'):
        hashtags.append(theme['hashtag'])
    
    caption_parts.append(' '.join(hashtags))
    
    return '\n'.join(caption_parts)


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


def post_to_instagram(image_buffer, caption):
    """Post image to Instagram using Graph API"""
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("❌ Instagram credentials not configured")
        return False
    
    try:
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
                print(f"❌ Image upload failed: {response_data}")
                return False
            
            media_id = response_data['id']
            print(f"✅ Media container created: {media_id}")
        
        publish_url = f"https://graph.facebook.com/v24.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        publish_data = {
            'creation_id': media_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        
        publish_response = requests.post(publish_url, data=publish_data)
        publish_result = publish_response.json()
        
        if 'id' in publish_result:
            print(f"✅ Successfully posted to Instagram: {publish_result['id']}")
            return True
        else:
            print(f"❌ Publishing failed: {publish_result}")
            return False
            
    except Exception as e:
        print(f"❌ Instagram posting error: {e}")
        return False


def main():
    """Main execution function"""
    print(f"🚀 Instagram Auto-Poster FINAL Starting...")
    print(f"📅 Today: {datetime.now().strftime('%A, %B %d, %Y')}")
    
    conn = get_db_connection()
    if not conn:
        sys.exit(1)
    
    cur = conn.cursor()
    
    try:
        # Get player info
        player_name = get_player_info(cur, PLAYER_ID)
        
        if not player_name:
            print(f"❌ No player data found for player_id={PLAYER_ID}")
            sys.exit(1)
        
        print(f"👤 Player: {player_name}")
        
        # Get all games player has played
        all_games = get_all_games_for_player(cur, PLAYER_ID)
        print(f"🎮 Games in database: {len(all_games)}")
        for game in all_games:
            print(f"   - {game['game_name']} {game['game_installment'] or ''}")
        
        # Load posted content hashes
        posted_hashes = get_posted_content_hash()
        print(f"📝 Previously posted content hashes: {len(posted_hashes)}")
        
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
        if check_games_on_date(cur, PLAYER_ID, today):
            print(f"✅ Games found today ({today})")
            
            # Get stats across all games today
            multi_game_stats = get_stats_for_date_all_games(cur, PLAYER_ID, today)
            
            if len(multi_game_stats) > 0:
                # Use first game for chart
                first_game = multi_game_stats[0]
                game_info = {
                    'game_name': first_game['game'],
                    'game_installment': first_game['installment']
                }
                
                # Find game_id for anomaly detection
                game_id = next((g['game_id'] for g in all_games 
                               if g['game_name'] == first_game['game']), None)
                
                if game_id:
                    stats = get_stats_for_date(cur, PLAYER_ID, game_id, today)
                    anomalies = detect_anomalies(cur, PLAYER_ID, game_id, today)
                
                post_type = 'daily'
                date_str = today.strftime('%A, %B %d')
                title = "Today's Performance"
                subtitle = date_str
                content_hash = generate_content_hash(stats, game_info['game_name'], date_str)
        
        # PRIORITY 2: Games played yesterday
        elif check_games_on_date(cur, PLAYER_ID, yesterday):
            print(f"✅ Games found yesterday ({yesterday})")
            
            multi_game_stats = get_stats_for_date_all_games(cur, PLAYER_ID, yesterday)
            
            if len(multi_game_stats) > 0:
                first_game = multi_game_stats[0]
                game_info = {
                    'game_name': first_game['game'],
                    'game_installment': first_game['installment']
                }
                
                game_id = next((g['game_id'] for g in all_games 
                               if g['game_name'] == first_game['game']), None)
                
                if game_id:
                    stats = get_stats_for_date(cur, PLAYER_ID, game_id, yesterday)
                    anomalies = detect_anomalies(cur, PLAYER_ID, game_id, yesterday)
                
                post_type = 'recent'
                date_str = yesterday.strftime('%A, %B %d')
                title = "Yesterday's Performance"
                subtitle = date_str
                content_hash = generate_content_hash(stats, game_info['game_name'], date_str)
        
        # PRIORITY 3: Historical records (ALL games, no duplicates)
        else:
            print(f"📜 No recent games - fetching historical records")
            
            records = get_historical_records_all_games(cur, PLAYER_ID, posted_hashes, limit=10)
            
            if not records:
                print(f"❌ No new historical content available (all posted)")
                sys.exit(1)
            
            # Select top 3 records
            selected_records = records[:3]
            
            # Use first record's game for chart
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
            
            # Build anomalies list for caption
            anomalies = [{
                'description': f"Best {r['stat']}: {r['value']} ({r['date'].strftime('%b %d, %Y')})"
            } for r in selected_records]
        
        if not stats:
            print(f"❌ No stats to post")
            sys.exit(1)
        
        # Check if already posted
        if content_hash and content_hash in posted_hashes:
            print(f"⚠️ Content already posted (hash: {content_hash[:8]}...)")
            print(f"   Fetching alternative content...")
            sys.exit(1)
        
        print(f"📊 Post type: {post_type}")
        print(f"📈 Stats: {stats}")
        print(f"🎮 Game: {game_info['game_name']}")
        
        # Create chart
        print(f"🎨 Creating Instagram chart (Holiday theme: {use_holiday_theme})...")
        image_buffer = create_instagram_portrait_chart(
            stats, player_name, game_info['game_name'], 
            game_info.get('game_installment'), title, subtitle, use_holiday_theme
        )
        
        # BACKUP TO GCS (before posting to Instagram)
        print(f"☁️ Backing up to Google Cloud Storage...")
        try:
            # Create a copy of the buffer for GCS (preserve original for Instagram)
            gcs_buffer = io.BytesIO(image_buffer.getvalue())
            
            gcs_url = upload_instagram_poster_to_gcs(
                gcs_buffer,
                player_name,
                game_info['game_name'],
                post_type  # 'daily', 'recent', or 'historical'
            )
            
            if gcs_url:
                print(f"✅ Backed up to GCS: {gcs_url}")
            else:
                print(f"⚠️ GCS backup failed (continuing with Instagram post)")
        except Exception as gcs_error:
            print(f"⚠️ GCS backup error: {gcs_error} (continuing with Instagram post)")
        
        # Generate trendy caption
        caption = generate_trendy_caption(
            post_type, stats, game_info, player_name, day_of_week, anomalies
        )
        print(f"📝 Caption:\n{caption}\n")
        
        # Post to Instagram
        print(f"📤 Posting to Instagram...")
        success = post_to_instagram(image_buffer, caption)
        
        if success:
            # Save content hash to prevent duplicates
            if content_hash:
                save_content_hash(content_hash)
            
            print(f"✅ Successfully posted to Instagram!")
            sys.exit(0)
        else:
            print(f"❌ Failed to post to Instagram")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()