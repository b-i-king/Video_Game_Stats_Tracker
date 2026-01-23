"""
Chart generation utilities for social media posts
Creates high-quality bar/line charts from gaming stats

Features:
- Horizontal bar charts (easier to read left-to-right)
- Direct line labels (no legend clutter)
- Holiday-themed color palettes
- Multi-platform support (Twitter 1200x630, Instagram 1080x1080)
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime
import io
import os
from holiday_themes import get_themed_colors

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
    Generate a HORIZONTAL bar chart for first-time game stats.
    Horizontal layout improves readability (left-to-right reading).
    Bars are AUTOMATICALLY SORTED from largest to smallest (top to bottom).
    
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
    stats = []
    for i in range(1, 4):
        label = stat_data.get(f'stat{i}', {}).get('label', f'Stat {i}')
        value = stat_data.get(f'stat{i}', {}).get('value', 0)
        stats.append({'label': label, 'value': value})
    
    # SORT by value (largest to smallest)
    stats.sort(key=lambda x: x['value'], reverse=True)# Extract data
    
    # Extract sorted labels and values
    labels = [s['label'] for s in stats]
    values = [s['value'] for s in stats]
    
    # REVERSE for matplotlib (barh plots bottom-to-top, we want largest on top)
    labels.reverse()
    values.reverse()
 
    # Get holiday-themed colors
    theme = get_themed_colors()
    colors = theme['colors']
    
    # Determine figure size
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        title_fontsize = 20
        value_fontsize = 16
        label_fontsize = 16
    else:  # twitter
        fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
        title_fontsize = 18
        value_fontsize = 14
        label_fontsize = 14
    
    # Create HORIZONTAL bar chart (barh instead of bar)
    bars = ax.barh(labels, values, color=colors, edgecolor='white', linewidth=2)
    
    # Add value labels at the end of bars (right side)
    for bar, value in zip(bars, values):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2.,
                f' {value:,.0f}' if isinstance(value, (int, float)) else f' {str(value)}',
                ha='left', va='center', fontsize=value_fontsize, fontweight='bold', color='white')
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    title_text = f"{player_name}'s First Game Stats\n{full_game_name}"
    
     # Add theme indicator ONLY if today is EXACT holiday date
    if theme['show_in_title']:
        title_text += f"\n{theme['theme_name']}"
    
    ax.set_title(title_text, fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    ax.set_xlabel('Value', fontsize=label_fontsize, fontweight='bold')
    ax.set_ylabel('Stats', fontsize=label_fontsize, fontweight='bold')
    
    # Grid (vertical for horizontal bars)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
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
    
    # Add multi-platform branding (single line)
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
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
    Generate a line chart with DIRECT LABELS (no legend).
    Labels are placed at the end of each line for clarity.
    
    Args:
        stat_history: dict with dates and stat values
        player_name: str
        game_name: str
        game_installment: str (optional)
        size: str ('twitter' = 1200x630, 'instagram' = 1080x1080)
    
    Returns:
        BytesIO object containing PNG image
    """
    dates = stat_history.get('dates', [])
    
    # Get holiday-themed colors
    theme = get_themed_colors()
    colors = theme['colors']
    
    # Determine figure size
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        title_fontsize = 20
        label_fontsize = 16
        direct_label_fontsize = 13
    else:  # twitter
        fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
        title_fontsize = 18
        label_fontsize = 14
        direct_label_fontsize = 12
    
    markers = ['o', 's', 'D']  # Circle, square, diamond
    
    # Store line end positions for direct labeling
    line_end_positions = []
    
    # Plot each stat
    for i in range(1, 4):
        stat_key = f'stat{i}'
        if stat_key in stat_history and stat_history[stat_key]:
            label = stat_history[stat_key].get('label', f'Stat {i}')
            values = stat_history[stat_key].get('values', [])
            
            if values:
                line, = ax.plot(dates, values, 
                       color=colors[i-1], 
                       marker=markers[i-1], 
                       linewidth=3, 
                       markersize=8,
                       label=label,  # Still set for internal use
                       markeredgecolor='white',
                       markeredgewidth=1.5)
                
                # Store final position for direct label
                if len(dates) > 0 and len(values) > 0:
                    line_end_positions.append({
                        'x': dates[-1],
                        'y': values[-1],
                        'label': label,
                        'color': colors[i-1]
                    })
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    title_text = f"{player_name}'s Performance Trend\n{full_game_name}"
    
    # Add theme indicator ONLY if today is EXACT holiday date
    if theme['show_in_title']:
        title_text += f"\n{theme['theme_name']}"
    
    ax.set_title(title_text, fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    ax.set_ylabel('Value', fontsize=label_fontsize, fontweight='bold')
    ax.set_xlabel('Date', fontsize=label_fontsize, fontweight='bold')
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add direct labels at end of lines (instead of legend)
    if line_end_positions:
        # Get axis limits to position labels
        x_range = ax.get_xlim()
        y_range = ax.get_ylim()
        
        # Sort by y-position to avoid overlaps
        line_end_positions.sort(key=lambda x: x['y'])
        
        # Add text labels at line ends
        for pos in line_end_positions:
            # Position label slightly to the right of last point
            label_x = pos['x']
            label_y = pos['y']
            
            ax.annotate(pos['label'], 
                       xy=(label_x, label_y),
                       xytext=(10, 0),  # 10 points to the right
                       textcoords='offset points',
                       fontsize=direct_label_fontsize,
                       fontweight='bold',
                       color=pos['color'],
                       va='center',
                       bbox=dict(boxstyle='round,pad=0.3', 
                                facecolor='#2d2d2d', 
                                edgecolor=pos['color'],
                                linewidth=2,
                                alpha=0.9))
    
    # Grid
    ax.grid(alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    # Extend x-axis slightly to make room for labels
    x_min, x_max = ax.get_xlim()
    ax.set_xlim(x_min, x_max + (x_max - x_min) * 0.15)
    
    # Add timestamp
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.01, timestamp, ha='right', va='bottom', 
             fontsize=10, color='gray', style='italic')
    
    # Add multi-platform branding
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
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
    (Same as before - no changes needed)
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