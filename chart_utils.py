"""
Chart generation utilities for social media posts
Creates high-quality bar/line charts from gaming stats

Supports multiple sizes:
- Twitter: 1200x630 (landscape)
- Instagram: 1080x1080 (square)
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime
import io
import os

# Set style for professional-looking charts
sns.set_style("darkgrid")
plt.rcParams['figure.facecolor'] = '#1a1a1a'  # Dark background
plt.rcParams['axes.facecolor'] = '#2d2d2d'
plt.rcParams['text.color'] = 'white'
plt.rcParams['axes.labelcolor'] = 'white'
plt.rcParams['xtick.color'] = 'white'
plt.rcParams['ytick.color'] = 'white'
plt.rcParams['grid.color'] = '#404040'

# Try to use Fira Code, fallback to monospace
try:
    import matplotlib.font_manager as fm
    fira_code_fonts = [f for f in fm.findSystemFonts() if 'FiraCode' in f or 'Fira Code' in f]
    if fira_code_fonts:
        plt.rcParams['font.family'] = 'Fira Code'
        print("✅ Using Fira Code font")
    else:
        plt.rcParams['font.family'] = 'monospace'  # Fallback
        print("⚠️ Fira Code not found, using monospace. Install Fira Code for consistency with dashboard.")
except:
    plt.rcParams['font.family'] = 'monospace'
    print("⚠️ Using fallback monospace font")

plt.rcParams['font.size'] = 12


def generate_bar_chart(stat_data, player_name, game_name, game_installment=None, size='twitter'):
    """
    Generate a bar chart for first-time game stats (1 game played).
    
    Args:
        stat_data: dict with keys 'stat1', 'stat2', 'stat3'
                   Each contains {'label': str, 'value': int/float}
        player_name: str
        game_name: str
        game_installment: str (optional)
        size: str ('twitter' = 1200x630, 'instagram' = 1080x1080)
    
    Returns:
        BytesIO object containing PNG image
    """
    # Extract data
    labels = [stat_data.get(f'stat{i}', {}).get('label', f'Stat {i}') 
              for i in range(1, 4)]
    values = [stat_data.get(f'stat{i}', {}).get('value', 0) 
              for i in range(1, 4)]
    
    # Determine figure size based on platform
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)  # 1080x1080
        title_fontsize = 20
        value_fontsize = 16
        label_fontsize = 16
    else:  # twitter (default)
        fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)  # 1200x630
        title_fontsize = 18
        value_fontsize = 14
        label_fontsize = 14
    
    # Color palette (gaming-themed)
    colors = ['#00ff41', '#00d4ff', '#ff00ff']  # Neon green, cyan, magenta
    
    # Create bar chart
    bars = ax.bar(labels, values, color=colors, edgecolor='white', linewidth=2)
    
    # Add value labels on top of bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{value:,.0f}' if isinstance(value, (int, float)) else str(value),
                ha='center', va='bottom', fontsize=value_fontsize, fontweight='bold', color='white')
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    ax.set_title(f"{player_name}'s First Game Stats\n{full_game_name}", 
                 fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    ax.set_ylabel('Value', fontsize=label_fontsize, fontweight='bold')
    ax.set_xlabel('Stats', fontsize=label_fontsize, fontweight='bold')
    
    # Grid
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    # Add timestamp
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.01, timestamp, ha='right', va='bottom', 
             fontsize=10, color='gray', style='italic')
    
    # Add multi-platform branding (bottom left, single line)
    # Format: YT & Twitch: TheBOLBroadcast
    # Colors: Red "YT" + White "&" + Purple "Twitch" + White ": TheBOLBroadcast"
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    
    # Position for text elements
    x_start = 0.01
    y_pos = 0.01
    
    # "YT" in red
    fig.text(x_start, y_pos, 'YT', ha='left', va='bottom',
             fontsize=10, color='#FF0000', fontweight='bold')
    
    # " & " in white (positioned after "YT")
    fig.text(x_start + 0.012, y_pos, ' & ', ha='left', va='bottom',
             fontsize=10, color='white', fontweight='normal')
    
    # "Twitch" in purple (positioned after " & ")
    fig.text(x_start + 0.029, y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=10, color='#9146FF', fontweight='bold')
    
    # ": TheBOLBroadcast" in white (positioned after "Twitch")
    fig.text(x_start + 0.07, y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=10, color='white', fontweight='bold')
    
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    
    return buf


def generate_line_chart(stat_history, player_name, game_name, game_installment=None, size='twitter'):
    """
    Generate a line chart for multi-game stats (2+ games played).
    
    Args:
        stat_history: dict with structure:
            {
                'dates': [datetime objects],
                'stat1': {'label': str, 'values': [list of values]},
                'stat2': {'label': str, 'values': [list of values]},
                'stat3': {'label': str, 'values': [list of values]}
            }
        player_name: str
        game_name: str
        game_installment: str (optional)
        size: str ('twitter' = 1200x630, 'instagram' = 1080x1080)
    
    Returns:
        BytesIO object containing PNG image
    """
    dates = stat_history.get('dates', [])
    
    # Determine figure size based on platform
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)  # 1080x1080
        title_fontsize = 20
        label_fontsize = 16
        legend_fontsize = 14
    else:  # twitter (default)
        fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)  # 1200x630
        title_fontsize = 18
        label_fontsize = 14
        legend_fontsize = 12
    
    # Color palette
    colors = ['#00ff41', '#00d4ff', '#ff00ff']
    markers = ['o', 's', 'D']  # Circle, square, diamond
    
    # Plot each stat
    for i in range(1, 4):
        stat_key = f'stat{i}'
        if stat_key in stat_history and stat_history[stat_key]:
            label = stat_history[stat_key].get('label', f'Stat {i}')
            values = stat_history[stat_key].get('values', [])
            
            if values:
                ax.plot(dates, values, 
                       color=colors[i-1], 
                       marker=markers[i-1], 
                       linewidth=3, 
                       markersize=8,
                       label=label,
                       markeredgecolor='white',
                       markeredgewidth=1.5)
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    ax.set_title(f"{player_name}'s Performance Trend\n{full_game_name}", 
                 fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    ax.set_ylabel('Value', fontsize=label_fontsize, fontweight='bold')
    ax.set_xlabel('Date', fontsize=label_fontsize, fontweight='bold')
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Legend
    ax.legend(loc='upper left', framealpha=0.9, facecolor='#2d2d2d', 
              edgecolor='white', fontsize=legend_fontsize)
    
    # Grid
    ax.grid(alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    # Add timestamp
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.01, timestamp, ha='right', va='bottom', 
             fontsize=10, color='gray', style='italic')
    
    # Add multi-platform branding (bottom left, single line)
    # Format: YT & Twitch: TheBOLBroadcast
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    
    # Position for text elements
    x_start = 0.01
    y_pos = 0.01
    
    # "YT" in red
    fig.text(x_start, y_pos, 'YT', ha='left', va='bottom',
             fontsize=10, color='#FF0000', fontweight='bold')
    
    # " & " in white (positioned after "YT")
    fig.text(x_start + 0.012, y_pos, ' & ', ha='left', va='bottom',
             fontsize=10, color='white', fontweight='normal')
    
    # "Twitch" in purple (positioned after " & ")
    fig.text(x_start + 0.029, y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=10, color='#9146FF', fontweight='bold')
    
    # ": TheBOLBroadcast" in white (positioned after "Twitch")
    fig.text(x_start + 0.07, y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=10, color='white', fontweight='bold')
    
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    
    return buf


def get_stat_history_from_db(cur, player_id, game_id, top_stat_types, timezone_str='UTC'):
    """
    Fetch historical data for line chart from database.
    
    Args:
        cur: Database cursor
        player_id: int
        game_id: int
        top_stat_types: list of str (stat type names)
        timezone_str: str (timezone for date conversion)
    
    Returns:
        dict with structure for generate_line_chart
    """
    from datetime import datetime
    
    stat_history = {
        'dates': [],
        'stat1': {'label': '', 'values': []},
        'stat2': {'label': '', 'values': []},
        'stat3': {'label': '', 'values': []}
    }
    
    # Get distinct dates
    cur.execute("""
        SELECT DISTINCT CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) as play_date
        FROM fact.fact_game_stats
        WHERE player_id = %s AND game_id = %s
        ORDER BY play_date;
    """, (timezone_str, player_id, game_id))
    
    dates = [row[0] for row in cur.fetchall()]
    stat_history['dates'] = dates
    
    if not dates:
        return stat_history
    
    # For each stat type, get values per date
    for i, stat_type in enumerate(top_stat_types[:3], 1):
        stat_key = f'stat{i}'
        stat_history[stat_key]['label'] = stat_type
        
        values = []
        for date in dates:
            # Get average for this stat on this date
            cur.execute("""
                SELECT AVG(stat_value)
                FROM fact.fact_game_stats
                WHERE player_id = %s 
                  AND game_id = %s 
                  AND stat_type = %s
                  AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s;
            """, (player_id, game_id, stat_type, timezone_str, date))
            
            result = cur.fetchone()
            avg_value = round(float(result[0]), 1) if result and result[0] else 0
            values.append(avg_value)
        
        stat_history[stat_key]['values'] = values
    
    return stat_history