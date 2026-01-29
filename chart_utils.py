"""
Chart generation utilities for social media posts
Creates high-quality bar/line charts from gaming stats

Features:
- Horizontal bar charts (easier to read left-to-right)
- Direct line labels (no legend clutter)
- Holiday-themed color palettes
- Multi-platform support (Twitter 1200x630, Instagram 1080x1080)
- LOGARITHMIC SCALING for highly skewed data
- Smart text positioning to prevent overflow
- Abbreviated stat names for cleaner display
- Year display in date labels for multi-year tracking
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime
import io
import os
import numpy as np
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

# --- LOAD BUNDLED FIRA CODE FONTS ---
def load_custom_fonts():
    """Load Fira Code fonts from repository fonts directory"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(script_dir, 'fonts')
    
    if os.path.exists(fonts_dir):
        print(f"📁 Loading fonts from: {fonts_dir}")
        
        # Find all TTF files in fonts directory
        font_files = [f for f in os.listdir(fonts_dir) if f.endswith('.ttf')]
        
        if font_files:
            # Add each font to matplotlib
            for font_file in font_files:
                font_path = os.path.join(fonts_dir, font_file)
                try:
                    fm.fontManager.addfont(font_path)
                    print(f"✅ Loaded font: {font_file}")
                except Exception as e:
                    print(f"⚠️ Failed to load {font_file}: {e}")
            
            # Rebuild font cache
            print("🔄 Rebuilding font cache...")
            
            # Set Fira Code as default
            plt.rcParams['font.family'] = 'Fira Code'
            print("✅ Fira Code set as default font")
            return True
        else:
            print("⚠️ No TTF files found in fonts directory")
    else:
        print(f"⚠️ Fonts directory not found: {fonts_dir}")
    
    # Fallback to system fonts
    print("ℹ️ Using system fonts as fallback")
    try:
        # Try system Fira Code
        fira_code_fonts = [f for f in fm.findSystemFonts() 
                          if 'FiraCode' in f or 'Fira Code' in f]
        if fira_code_fonts:
            plt.rcParams['font.family'] = 'Fira Code'
            print("✅ Using system Fira Code font")
            return True
    except:
        pass
    
    # Final fallback
    plt.rcParams['font.family'] = 'monospace'
    print("ℹ️ Using monospace fallback font")
    return False

# Load fonts when module is imported
load_custom_fonts()

plt.rcParams['font.size'] = 12


def abbreviate_stat(stat_name):
    """
    Abbreviate stat name for cleaner chart display.
    
    Rules (in order):
    1. If multi-word (2+ words): Create acronym from first letter of each word
       - "Damage Dealt" -> "DD"
       - "Score Per Minute" -> "SPM"
       - "Total Damage Dealt" -> "TDD"
    2. If single word > 8 chars: Use first 4 letters + 'S'
       - "Eliminations" -> "ELIMS"
    3. Otherwise: Use full name uppercase
       - "Kills" -> "KILLS"
       - "K/D" -> "K/D" (already abbreviated)
    
    Examples:
        "Damage Dealt" -> "DD"
        "Score Per Minute" -> "SPM"
        "Total Damage Dealt" -> "TDD"
        "Eliminations" -> "ELIMS"
        "Kills" -> "KILLS"
        "Assists" -> "ASSISTS"
        "K/D" -> "K/D"
    """
    if not stat_name:
        return "XXXX"
    
    # Clean up the stat name
    clean = stat_name.strip()
    
    # Split into words (handles spaces, dashes, underscores)
    # Note: / is kept as-is (for K/D, E/R ratios)
    words = clean.replace('-', ' ').replace('_', ' ').split()
    
    # RULE 1: Multi-word stats -> Acronym
    if len(words) >= 2:
        # Create acronym from first letter of each word
        acronym = ''.join(word[0].upper() for word in words if word)
        return acronym
    
    # At this point we have a single "word" (may contain /)
    single_word = words[0] if words else clean
    
    # RULE 2: Single word > 8 chars -> First 4 + 'S'
    if len(single_word) > 8:
        abbrev = single_word[:4].upper() + "S"
        return abbrev
    
    # RULE 3: Short single word -> Full name (uppercase, preserve special chars)
    return single_word.upper()


def format_large_number(value):
    """
    Format large numbers with abbreviations for display.
    
    Examples:
        1500 -> "1.5k"
        1000000 -> "1.0M"
        50 -> "50"
    """
    if not isinstance(value, (int, float)):
        return str(value)
    
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value/1_000:.1f}k"
    else:
        return f"{int(value)}"


def should_use_log_scale(values):
    """
    Determine if logarithmic scaling should be used based on data distribution.
    
    Uses log scale when:
    - Max value is 100x or more than the median non-zero value
    - This indicates highly skewed data (e.g., [600, 2, 2, 1])
    
    Args:
        values: list of numeric values
    
    Returns:
        bool: True if log scale should be used
    """
    if not values or len(values) < 2:
        return False
    
    # Filter out zeros for ratio calculation
    non_zero_values = [v for v in values if v > 0]
    
    if not non_zero_values or len(non_zero_values) < 2:
        return False
    
    max_val = max(non_zero_values)
    median_val = sorted(non_zero_values)[len(non_zero_values) // 2]
    
    # Use log scale if max is 100x or more than median
    ratio = max_val / median_val if median_val > 0 else 0
    
    if ratio >= 100:
        print(f"📊 Using logarithmic scale (ratio: {ratio:.1f}x)")
        return True
    
    return False


def format_date_label(dates):
    """
    Determine appropriate date format based on date range.
    Returns format string for matplotlib date formatter.
    
    - If span < 1 year: '%b %d' (Jan 15)
    - If span >= 1 year: '%b %d, %Y' (Jan 15, 2026)
    """
    if not dates or len(dates) < 2:
        return '%b %d'
    
    date_range = dates[-1] - dates[0]
    
    # If date range is more than 365 days, include year
    if date_range.days >= 365:
        return '%b %d, %Y'
    else:
        return '%b %d'


def generate_bar_chart(stat_data, player_name, game_name, game_installment=None, size='twitter'):
    """
    Generate a HORIZONTAL bar chart for first-time game stats.
    
    NEW FEATURES:
    - Abbreviated stat names (> 8 chars)
    - Smart text positioning (inside bar for large values, outside for small)
    - Removed "Stats" and "Value" axis labels
    - Log scale for skewed data
    
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
        
        # Abbreviate long stat names
        abbrev_label = abbreviate_stat(label)
        
        stats.append({
            'label': abbrev_label,
            'original_label': label,
            'value': value
        })
    
    # SORT by value (largest to smallest)
    stats.sort(key=lambda x: x['value'], reverse=True)
    
    # Extract sorted labels and values
    labels = [s['label'] for s in stats]
    values = [s['value'] for s in stats]
    
    # REVERSE for matplotlib (barh plots bottom-to-top, we want largest on top)
    labels.reverse()
    values.reverse()
    
    # Determine if we should use log scale
    use_log = should_use_log_scale(values)
 
    # Get holiday-themed colors
    theme = get_themed_colors()
    colors = theme['colors']
    
    # Determine figure size
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        title_fontsize = 20
        value_fontsize = 16
        label_fontsize = 14
    else:  # twitter
        fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
        title_fontsize = 18
        value_fontsize = 14
        label_fontsize = 12
    
    # Create HORIZONTAL bar chart
    if use_log:
        # Use logarithmic scale for x-axis
        plot_values = [max(v, 0.1) for v in values]
        bars = ax.barh(labels, plot_values, color=colors, edgecolor='white', linewidth=2)
        ax.set_xscale('log')
        
        # Custom x-axis formatting for log scale
        from matplotlib.ticker import FuncFormatter
        def log_formatter(x, pos):
            """Format log scale labels to show actual values"""
            if x >= 1000:
                return f'{int(x/1000)}k'
            elif x >= 1:
                return f'{int(x)}'
            else:
                return f'{x:.1f}'
        
        ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))
    else:
        # Normal linear scale
        bars = ax.barh(labels, values, color=colors, edgecolor='white', linewidth=2)
    
    # Smart text positioning to prevent overflow
    max_value = max(values) if values else 1
    
    for bar, actual_value in zip(bars, values):
        width = bar.get_width()
        
        # Format the value text
        value_text = format_large_number(actual_value)
        
        # Determine if text should be inside or outside bar
        # If bar is > 15% of max width, put text inside (right-aligned)
        # Otherwise, put text outside (left-aligned)
        threshold = max_value * 0.15
        
        if actual_value > threshold:
            # Place text INSIDE bar (right side, white text)
            text_x = width * 0.95
            text_color = 'white'
            h_align = 'right'
        else:
            # Place text OUTSIDE bar (left of end, white text)
            text_x = width
            text_color = 'white'
            h_align = 'left'
            value_text = f' {value_text}'  # Add space before
        
        ax.text(text_x, bar.get_y() + bar.get_height()/2.,
                value_text,
                ha=h_align, va='center', 
                fontsize=value_fontsize, 
                fontweight='bold', 
                color=text_color)
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    title_text = f"{player_name}'s First Game Stats\n{full_game_name}"
    
    # Add theme indicator ONLY if today is EXACT holiday date
    if theme['show_in_title']:
        title_text += f"\n{theme['theme_name']}"
    
    ax.set_title(title_text, fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    
    # REMOVED axis labels as requested (self-explanatory)
    # ax.set_xlabel('Value', fontsize=label_fontsize, fontweight='bold')
    # ax.set_ylabel('Stats', fontsize=label_fontsize, fontweight='bold')
    
    # Grid (vertical for horizontal bars)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    # Extend x-axis slightly to accommodate outside text
    if not use_log:
        ax.set_xlim(0, max_value * 1.15)
    
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
    
    NEW FEATURES:
    - Abbreviated stat names in labels
    - Year display if date range > 1 year
    - Removed "Value" and "Date" axis labels
    - Smart date formatting
    
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
    
    # Collect all values to check if we need log scale
    all_values = []
    for i in range(1, 4):
        stat_key = f'stat{i}'
        if stat_key in stat_history and stat_history[stat_key]:
            values = stat_history[stat_key].get('values', [])
            all_values.extend(values)
    
    # Determine if we should use log scale
    use_log = should_use_log_scale(all_values) if all_values else False
    
    # Plot each stat
    for i in range(1, 4):
        stat_key = f'stat{i}'
        if stat_key in stat_history and stat_history[stat_key]:
            label = stat_history[stat_key].get('label', f'Stat {i}')
            values = stat_history[stat_key].get('values', [])
            
            # Abbreviate stat name
            abbrev_label = abbreviate_stat(label)
            
            if values:
                # For log scale, replace zeros with small value
                if use_log:
                    plot_values = [max(v, 0.1) for v in values]
                else:
                    plot_values = values
                
                line, = ax.plot(dates, plot_values, 
                       color=colors[i-1], 
                       marker=markers[i-1], 
                       linewidth=3, 
                       markersize=8,
                       label=abbrev_label,
                       markeredgecolor='white',
                       markeredgewidth=1.5)
                
                # Store final position for direct label
                if len(dates) > 0 and len(values) > 0:
                    line_end_positions.append({
                        'x': dates[-1],
                        'y': plot_values[-1],
                        'actual_y': values[-1],
                        'label': abbrev_label,
                        'color': colors[i-1]
                    })
    
    # Set log scale if needed
    if use_log:
        ax.set_yscale('log')
        from matplotlib.ticker import FuncFormatter
        def log_formatter(x, pos):
            """Format log scale labels to show actual values"""
            if x >= 1000:
                return f'{int(x/1000)}k'
            elif x >= 1:
                return f'{int(x)}'
            else:
                return f'{x:.1f}'
        ax.yaxis.set_major_formatter(FuncFormatter(log_formatter))
    
    # Styling
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    title_text = f"{player_name}'s Performance Trend\n{full_game_name}"
    
    # Add theme indicator ONLY if today is EXACT holiday date
    if theme['show_in_title']:
        title_text += f"\n{theme['theme_name']}"
    
    ax.set_title(title_text, fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    
    # REMOVED axis labels as requested (self-explanatory)
    # ax.set_ylabel('Value', fontsize=label_fontsize, fontweight='bold')
    # ax.set_xlabel('Date', fontsize=label_fontsize, fontweight='bold')
    
    # Format x-axis dates with year if needed
    date_format = format_date_label(dates)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add direct labels at end of lines (instead of legend)
    if line_end_positions:
        # Sort by y-position to avoid overlaps
        line_end_positions.sort(key=lambda x: x['y'])
        
        # Add text labels at line ends (show ACTUAL values with abbreviation)
        for pos in line_end_positions:
            label_x = pos['x']
            label_y = pos['y']
            
            # Format actual value for display
            actual_val = pos['actual_y']
            value_display = format_large_number(actual_val)
            
            label_text = f"{pos['label']}: {value_display}"
            
            ax.annotate(label_text, 
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
    
    # " & " in white
    fig.text(x_start + 0.012, y_pos, ' & ', ha='left', va='bottom',
             fontsize=10, color='white', fontweight='normal')
    
    # "Twitch" in purple
    fig.text(x_start + 0.029, y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=10, color='#9146FF', fontweight='bold')
    
    # Handle in white
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
    
    return stat_history