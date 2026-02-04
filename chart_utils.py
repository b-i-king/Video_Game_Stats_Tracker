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
- Reduced height and improved spacing to prevent x-axis label overlap
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
       - "Assists" -> "ASSISTS"
       - "K/D" -> "K/D" (already abbreviated)
    
    Examples:
        "Damage Dealt" -> "DD"
        "Score Per Minute" -> "SPM"
        "Total Damage Dealt" -> "TDD"
        "Eliminations" -> "ELIMS"
        "Assists" -> "ASSISTS"
        "E/R"-> "E/R"
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
    # FIX: Handle dict values properly
    if isinstance(values[0], dict):
        numeric_values = [v.get('value', 0) if isinstance(v, dict) else v for v in values]
    else:
        numeric_values = values
    
    non_zero_values = [v for v in numeric_values if isinstance(v, (int, float)) and v > 0]
    
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
    
    FEATURES:
    - Abbreviated stat names (> 8 chars)
    - Smart text positioning (inside bar for large values, outside for small)
    - Removed "Stats" and "Value" axis labels
    - Log scale for skewed data
    - Reduced height and improved bottom spacing to prevent overlap
    - SORTED: Bars displayed in descending order (largest at top)
    - TWO-TONE TITLE: Main title white, heritage/holiday in third color
    
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
    # Extract data from dict format
    stats = []
    for i in range(1, 4):
        stat_key = f'stat{i}'
        if stat_key in stat_data:
            label = stat_data[stat_key].get('label', f'Stat {i}')
            value = stat_data[stat_key].get('value', 0)
            
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
    
    # Determine figure size - REDUCED HEIGHT for better spacing
    if size == 'instagram':
        # Reduced from 10.8 to 9.5 to give more room at bottom
        fig, ax = plt.subplots(figsize=(10.8, 9.5), dpi=100)
        title_fontsize = 20
        label_fontsize = 16
        value_fontsize = 14
    else:  # twitter
        # Reduced from 6.3 to 5.5 to give more room at bottom
        fig, ax = plt.subplots(figsize=(12, 5.5), dpi=100)
        title_fontsize = 18
        label_fontsize = 14
        value_fontsize = 12
    
    # For log scale, replace zeros with small value for plotting
    if use_log:
        plot_values = [max(v, 0.1) for v in values]
    else:
        plot_values = values
    
    # Create horizontal bar chart
    bars = ax.barh(labels, plot_values, color=colors[:len(labels)])
    
    # Add value labels - position depends on bar size
    max_val = max(plot_values) if plot_values else 1
    for i, (bar, actual_val) in enumerate(zip(bars, values)):
        width = bar.get_width()
        
        # Format the value for display
        display_val = format_large_number(actual_val)
        
        # Smart positioning: inside bar if large enough, outside if too small
        if width > max_val * 0.15:  # Bar is large enough for inside label
            x_pos = width * 0.95
            ha = 'right'
            color = 'white'
        else:  # Bar too small, put label outside
            x_pos = width * 1.05
            ha = 'left'
            color = 'white'
        
        ax.text(x_pos, bar.get_y() + bar.get_height()/2, 
               display_val,
               ha=ha, va='center',
               fontsize=value_fontsize, fontweight='bold', color=color)
    
    # Set log scale if needed
    if use_log:
        ax.set_xscale('log')
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
    
    # MANUAL TITLE with two-tone coloring
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    
    # Build title manually with fig.text for proper positioning
    y_position = 0.96  # Start near top
    line_spacing = 0.04  # Space between lines
    
    # Line 1: "{Player}'s First Game Stats" - WHITE
    line1 = f"{player_name}'s First Game Stats"
    fig.text(0.5, y_position, line1, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing
    
    # Line 2: "Game: Installment" - WHITE
    fig.text(0.5, y_position, full_game_name, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing
    
    # Line 3 (OPTIONAL): Heritage month/holiday name - THIRD COLOR
    if theme['show_in_title']:
        theme_color = colors[2] if len(colors) > 2 else colors[0]
        fig.text(0.5, y_position, theme['theme_name'], ha='center', va='top',
                 fontsize=title_fontsize, fontweight='bold', color=theme_color,
                 transform=fig.transFigure)
    
    # REMOVED axis labels (self-explanatory)
    # ax.set_xlabel('Value', fontsize=label_fontsize, fontweight='bold')
    # ax.set_ylabel('Stats', fontsize=label_fontsize, fontweight='bold')
    
    # Grid
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Remove spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    # Add timestamp - positioned higher to avoid overlap
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.03, timestamp, ha='right', va='bottom', 
             fontsize=10, color='gray', style='italic')
    
    # Add multi-platform branding - positioned higher to avoid overlap
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01
    y_pos = 0.03  # Changed from 0.01 to 0.03 for more spacing
    
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
    
    # DYNAMIC tight_layout adjustment based on title lines
    # Calculate top margin based on whether theme name is displayed
    if theme['show_in_title']:
        # Theme name adds an extra line, need more top space
        top_margin = 0.84  # Leave 16% for 3-line title
    else:
        # No theme name, standard 2-line title
        top_margin = 0.88  # Leave 12% for 2-line title
    
    plt.tight_layout(rect=[0, 0.05, 1, top_margin])
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.3)  # Added padding
    buf.seek(0)
    plt.close(fig)
    
    return buf


def generate_line_chart(stat_history, player_name, game_name, game_installment=None, size='twitter'):
    """
    Generate a line chart showing stat trends over time.
    
    FEATURES:
    - Direct line labels (no legend)
    - Abbreviated stat names
    - Log scale for skewed data
    - FIXED: Reduced height and improved bottom spacing to prevent overlap
    
    Args:
        stat_history: dict with 'dates' and 'stat1'/'stat2'/'stat3' keys
        player_name: name of the player
        game_name: name of the game
        game_installment: optional game installment/version
        size: 'twitter' (1200x630) or 'instagram' (1080x1080)
    
    Returns:
        BytesIO buffer containing the chart image
    """
    dates = stat_history.get('dates', [])
    
    if not dates:
        raise ValueError("No dates provided in stat_history")
    
    # Get themed colors
    theme = get_themed_colors()
    colors = theme['colors']
    
    # Determine figure size - REDUCED HEIGHT for better spacing
    if size == 'instagram':
        # Reduced from 10.8 to 9.5 to give more room at bottom
        fig, ax = plt.subplots(figsize=(10.8, 9.5), dpi=100)
        title_fontsize = 20
        label_fontsize = 16
        direct_label_fontsize = 13
    else:  # twitter
        # Reduced from 6.3 to 5.5 to give more room at bottom
        fig, ax = plt.subplots(figsize=(12, 5.5), dpi=100)
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
    
    # # Styling
    # full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    # title_text = f"{player_name}'s Performance Trend\n{full_game_name}"
    
    # # Add theme indicator ONLY if today is EXACT holiday date
    # if theme['show_in_title']:
    #     title_text += f"\n{theme['theme_name']}"
        
     # MANUAL TITLE with two-tone coloring
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    
    # Build title manually with fig.text for proper positioning
    y_position = 0.96  # Start near top
    line_spacing = 0.04  # Space between lines
    
    # Line 1: "{Player}'s First Game Stats" - WHITE
    line1 = f"{player_name}'s First Game Stats"
    fig.text(0.5, y_position, line1, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing
    
    # Line 2: "Game: Installment" - WHITE
    fig.text(0.5, y_position, full_game_name, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing
    
    # Line 3 (OPTIONAL): Heritage month/holiday name - THIRD COLOR
    if theme['show_in_title']:
        theme_color = colors[2] if len(colors) > 2 else colors[0]
        fig.text(0.5, y_position, theme['theme_name'], ha='center', va='top',
                 fontsize=title_fontsize, fontweight='bold', color=theme_color,
                 transform=fig.transFigure)
    
    # ax.set_title(title_text, fontsize=title_fontsize, fontweight='bold', color='white', pad=20)
    
    # REMOVED axis labels as requested (self-explanatory)
    # ax.set_ylabel('Value', fontsize=label_fontsize, fontweight='bold')
    # ax.set_xlabel('Date', fontsize=label_fontsize, fontweight='bold')
    
    # Format x-axis dates with year if needed
    date_format = format_date_label(dates)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    # Reduced rotation for better readability and less overlap
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha='right', fontsize=10)
    
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
    
    # Add timestamp - positioned higher to avoid overlap
    timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.03, timestamp, ha='right', va='bottom', 
             fontsize=10, color='gray', style='italic')
    
    # Add multi-platform branding - positioned higher to avoid overlap
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01
    y_pos = 0.03  # Changed from 0.01 to 0.03 for more spacing
    
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
    
    # DYNAMIC tight_layout adjustment based on title lines
    # Calculate top margin based on whether theme name is displayed
    if theme['show_in_title']:
        # Theme name adds an extra line, need more top space
        top_margin = 0.84  # Leave 16% for 3-line title
    else:
        # No theme name, standard 2-line title
        top_margin = 0.88  # Leave 12% for 2-line title
    
    plt.tight_layout(rect=[0, 0.05, 1, top_margin])
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.3)  # Added padding
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