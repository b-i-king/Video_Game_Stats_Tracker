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
import matplotlib.patheffects as pe
import seaborn as sns
from datetime import datetime
from zoneinfo import ZoneInfo
import io
import os
import numpy as np
from utils.holiday_themes import get_themed_colors

TIMEZONE_STR = os.environ.get("TIMEZONE", "America/Los_Angeles")

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
       - "E/R" -> "E/R" (already abbreviated)
    
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

    # Known abbreviations — checked before the generic rules
    _KNOWN = {"Checkpoints": "CP", "Checkpoint": "CP"}
    if clean in _KNOWN:
        return _KNOWN[clean]

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


def abbreviate_game_mode(game_mode):
    """
    Create a short display tag from a game mode name.
    Takes the first letter of each word, uppercased.
    Returns None for empty or generic modes ('Main', 'N/A').

    Examples:
        'Zombies'         → 'Z'
        'Team Deathmatch' → 'TD'
        'Battle Royale'   → 'BR'
        'Main'            → None
    """
    if not game_mode or not game_mode.strip():
        return None
    clean = game_mode.strip()
    if clean.lower() in ('main', 'n/a', 'none', '-'):
        return None
    words = clean.replace('-', ' ').replace('_', ' ').split()
    if not words:
        return None
    return ''.join(w[0].upper() for w in words if w) or None


def format_large_number(value):
    """
    Format large numbers with abbreviations for display.

    Examples:
        1500 -> "1.5k"
        1000000 -> "1.0M"
        50 -> "50"
    """
    if not isinstance(value, (int, float)):
        try:
            value = float(value)  # handles decimal.Decimal from psycopg2 NUMERIC columns
        except (TypeError, ValueError):
            return str(value)
    
     
    if value >= 1_000_000_000_000:
        return f"{value/1_000_000_000:.1f}T"
    elif value >= 1_000_000_000:
        return f"{value/1_000_000_000:.1f}B"
    elif value >= 1_000_000:
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
    
    _non_zero = []
    for v in numeric_values:
        try:
            fv = float(v)
            if fv > 0:
                _non_zero.append(fv)
        except (TypeError, ValueError):
            pass
    non_zero_values = _non_zero

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

    - If all dates share the same calendar year: '%b %d' (Jan 15)
    - If dates span multiple calendar years: '%b %d, %Y' (Jan 15, 2026)

    This handles short windows that cross a year boundary (e.g., Dec–Mar)
    as well as long multi-year histories.
    """
    if not dates or len(dates) < 2:
        return '%b %d'

    years = set(d.year for d in dates)
    if len(years) > 1:
        return '%b %d, %Y'
    return '%b %d'


def _generate_kpi_chart(stat, player_name, game_name, game_installment, size, theme, game_mode=None, title_label="First Game Stats"):
    """
    Generate a KPI scoreboard visual for a single stat.
    Shows the abbreviated stat name in large text with the value as a huge
    centered number — used when a game tracks only one statistic.
    """
    colors = theme['colors']

    # Pre-compute title line for dynamic font sizing
    _line1 = f"{player_name}'s {title_label}"
    _char_ratio = 0.60
    _fill = 0.88

    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        fig_width_pts  = 10.8 * 72
        fig_height_pts = 10.8 * 72
        title_fontsize = max(36, min(int(fig_width_pts * _fill / (len(_line1) * _char_ratio)), 64))
        kpi_value_fontsize = 140
        kpi_value_offset = 0.38
        branding_fontsize = 19
        amp_offset = 0.025
        twitch_offset = 0.062
        handle_offset = 0.134
    else:  # twitter - 1600x900
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        fig_width_pts  = 16 * 72
        fig_height_pts = 9  * 72
        title_fontsize = max(36, min(int(fig_width_pts * _fill / (len(_line1) * _char_ratio)), 64))
        kpi_value_fontsize = 160
        kpi_value_offset = 0.38
        branding_fontsize = 18
        amp_offset = 0.016
        twitch_offset = 0.040
        handle_offset = 0.087

    # Dynamic kpi_label_fontsize and kpi_label_offset based on character count.
    # The grey box (value bbox) top edge is at a fixed position in axes coords.
    # Each tier lowers the offset slightly as the font shrinks — but always
    # stays safely above the box. Offsets derived from the largest-tier anchor.
    label_len = len(stat['label'])
    if size == 'instagram':
        # Anchor: label_len<=6 → 72pt at 0.70.
        # Tiers with smaller font must NOT drop below the anchor offset — the
        # value bbox top is fixed, so pulling the label down causes overlap.
        if label_len <= 4:
            kpi_label_fontsize = 90
            kpi_label_offset = 0.72   # larger font, raise above anchor
        elif label_len <= 6:
            kpi_label_fontsize = 80
            kpi_label_offset = 0.70   # anchor (confirmed working)
        elif label_len <= 8:
            kpi_label_fontsize = 70
            kpi_label_offset = 0.70   # same as anchor — smaller font still needs same clearance
        else:
            kpi_label_fontsize = 60
            kpi_label_offset = 0.70   # same as anchor — smallest font, most whitespace above
    else:
        # Anchor: label_len<=6 → 80pt at 0.80.
        # Same rule: floor offset at anchor to prevent value-box overlap.
        if label_len <= 4:
            kpi_label_fontsize = 90
            kpi_label_offset = 0.82   # larger font, raise above anchor
        elif label_len <= 6:
            kpi_label_fontsize = 80
            kpi_label_offset = 0.80   # anchor (confirmed working)
        elif label_len <= 8:
            kpi_label_fontsize = 70
            kpi_label_offset = 0.80   # same as anchor — smaller font still needs same clearance
        else:
            kpi_label_fontsize = 60
            kpi_label_offset = 0.80   # same as anchor — smallest font, most whitespace above

    ax.axis('off')

    display_val = format_large_number(stat['value'])
    kpi_color = colors[0]

    # Scoreboard border: rounded rectangle in primary theme color spanning
    # both the stat label and the value — drawn first so text sits on top.
    from matplotlib.patches import FancyBboxPatch
    _box_top    = min(kpi_label_offset + 0.14, 0.92)
    _box_bottom = kpi_value_offset - 0.18
    ax.add_patch(FancyBboxPatch(
        (0.08, _box_bottom),
        0.84, _box_top - _box_bottom,
        boxstyle='round,pad=0.02',
        facecolor='#2d2d2d',
        edgecolor=kpi_color,
        linewidth=5,
        transform=ax.transAxes,
        zorder=0,
    ))

    # Stat label — shifted up and closer to the value bbox top edge
    ax.text(0.5, kpi_label_offset, stat['label'],
            ha='center', va='center',
            fontsize=kpi_label_fontsize, fontweight='bold',
            color='white', transform=ax.transAxes,
            zorder=1)

    # Huge value in theme color
    ax.text(0.5, kpi_value_offset, display_val,
            ha='center', va='center',
            fontsize=kpi_value_fontsize, fontweight='bold',
            color=kpi_color, transform=ax.transAxes,
            zorder=1)

    # Title (same structure as generate_bar_chart)
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    y_position = 0.96
    line_spacing = (title_fontsize / fig_height_pts) * 1.30

    fig.text(0.5, y_position, f"{player_name}'s {title_label}", ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing

    fig.text(0.5, y_position, full_game_name, ha='center', va='top',
             fontsize=title_fontsize, fontweight='bold', color='white',
             transform=fig.transFigure)
    y_position -= line_spacing

    if theme['show_in_title']:
        theme_color = colors[2] if len(colors) > 2 else colors[0]
        fig.text(0.5, y_position, theme['theme_name'], ha='center', va='top',
                 fontsize=title_fontsize, fontweight='bold', color=theme_color,
                 transform=fig.transFigure)

    # Timestamp
    try:
        timestamp = datetime.now(ZoneInfo(TIMEZONE_STR)).strftime('%B %d, %Y')
    except Exception:
        timestamp = datetime.now().strftime('%B %d, %Y')
    fig.text(0.99, 0.03, timestamp, ha='right', va='bottom',
             fontsize=branding_fontsize, color='gray', style='italic')

    # Game mode tag (centered between handles and date)
    _mode_tag = abbreviate_game_mode(game_mode) if game_mode else None
    if _mode_tag:
        fig.text(0.5, 0.03, f' {_mode_tag} ', ha='center', va='bottom',
                 fontsize=branding_fontsize, color='white', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='none', edgecolor='white', linewidth=1.5))

    # Multi-platform branding
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01
    y_pos = 0.03
    fig.text(x_start, y_pos, 'YT', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#FF0000', fontweight='bold')
    fig.text(x_start + amp_offset, y_pos, ' & ', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='normal')
    fig.text(x_start + twitch_offset, y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#9146FF', fontweight='bold')
    fig.text(x_start + handle_offset, y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='bold')

    n_title_lines = 3 if theme['show_in_title'] else 2
    top_margin = 0.96 - n_title_lines * line_spacing
    plt.tight_layout(rect=[0, 0.05, 1, top_margin])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.3)
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_bar_chart(stat_data, player_name, game_name, game_installment=None, size='twitter', game_mode=None, tz=None, title_label="First Game Stats"):
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
    
    # Count stats, get theme early, and branch for single-stat KPI visual
    num_stats = len(stats)
    theme = get_themed_colors(tz)
    colors = theme['colors']

    if num_stats == 1:
        return _generate_kpi_chart(stats[0], player_name, game_name, game_installment, size, theme, game_mode=game_mode, title_label=title_label)

    # Determine if we should use log scale
    use_log = should_use_log_scale(values)

    # Pre-compute title line for dynamic font sizing (used in both size branches)
    _line1_preview = f"{player_name}'s {title_label}"
    _char_ratio = 0.60
    _fill = 0.88

    # Fixed canvas sizes; bar area is controlled via tight_layout rect below
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        fig_width_pts  = 10.8 * 72   # 777.6 pt
        fig_height_pts = 10.8 * 72   # 777.6 pt
        # Dynamic title: fills width up to a readable cap
        title_fontsize = max(28, min(int(fig_width_pts * _fill / (len(_line1_preview) * _char_ratio)), 48))
        # Value labels sized to fill ~28% of bar height (bar area ≈ 184pt for 3-stat)
        value_fontsize = 70 if num_stats == 3 else 80
        branding_fontsize = 19
        # Branding offsets for 19pt on 10.8-inch figure (0.0114/char)
        amp_offset = 0.025
        twitch_offset = 0.062
        handle_offset = 0.134
        branding_y_pos = 0.06 if num_stats == 2 else 0.03
    else:  # twitter - 1600x900
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        fig_width_pts  = 16 * 72     # 1152 pt
        fig_height_pts = 9  * 72     # 648 pt
        # Dynamic title: wider canvas allows larger text, height-capped lower
        title_fontsize = max(28, min(int(fig_width_pts * _fill / (len(_line1_preview) * _char_ratio)), 52))
        # Value labels sized to fill ~26% of bar height (bar area ≈ 153pt for 3-stat)
        value_fontsize = 52 if num_stats == 3 else 64
        branding_fontsize = 18
        # Branding offsets for 18pt on 16-inch figure (0.00729/char)
        amp_offset = 0.016
        twitch_offset = 0.040
        handle_offset = 0.087
        branding_y_pos = 0.05 if num_stats == 2 else 0.03
    
    # For log scale, replace zeros with small value for plotting
    if use_log:
        plot_values = [max(v, 0.1) for v in values]
    else:
        plot_values = values
    
    # Create horizontal bar chart
    bars = ax.barh(labels, plot_values, color=colors[:len(labels)])

    # Apply log scale before label positioning so xlim reflects the log axis range
    if use_log:
        ax.set_xscale('log')
        from matplotlib.ticker import FuncFormatter, LogLocator
        def log_formatter(x, pos):
            """Format log scale labels to show actual values"""
            if x >= 1000:
                return f'{int(x/1000)}k'
            elif x >= 1:
                return f'{int(x)}'
            else:
                return f'{x:.1f}'
        ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))
        # Set xlim_max to a "nice" number above max_val so the axis extends past the data
        max_val = max(plot_values)
        import math
        magnitude = 10 ** math.floor(math.log10(max_val * 1.1))
        normalized = (max_val * 1.1) / magnitude
        if normalized <= 1:
            nice_max = 1 * magnitude
        elif normalized <= 2:
            nice_max = 2 * magnitude
        elif normalized <= 5:
            nice_max = 5 * magnitude
        else:
            nice_max = 10 * magnitude
        ax.set_xlim(left=ax.get_xlim()[0], right=nice_max)
        # Add intermediate ticks (1, 2, 5 × 10^n) so labels like 2k, 5k appear
        ax.xaxis.set_major_locator(LogLocator(base=10, subs=[1, 2, 5]))
        ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))

    # Add value labels - position depends on bar size relative to axis range
    _, xlim_max = ax.get_xlim()
    for i, (bar, actual_val) in enumerate(zip(bars, values)):
        width = bar.get_width()
        display_val = format_large_number(actual_val)

        if use_log:
            # Check bar visual fraction — short bars can't fit the label inside
            xlim_min_val, _ = ax.get_xlim()
            import math as _math
            log_min = _math.log10(max(xlim_min_val, 0.01))
            log_max = _math.log10(xlim_max)
            log_bar_end = _math.log10(max(width, 0.01))
            bar_vis_frac = (log_bar_end - log_min) / (log_max - log_min)
            if bar_vis_frac < 0.12:
                # Bar too short — place label just outside to the right
                x_pos = width * 1.15
                ha = 'left'
            else:
                x_pos = width * 0.95
                ha = 'right'
        else:
            if width > xlim_max * 0.15:
                x_pos = min(width * 0.95, xlim_max * 0.95)
                ha = 'right'
            else:
                x_pos = width + xlim_max * 0.02
                ha = 'left'

        ax.text(x_pos, bar.get_y() + bar.get_height()/2,
               display_val,
               ha=ha, va='center',
               fontsize=value_fontsize, fontweight='bold', color='white',
               path_effects=[pe.withStroke(linewidth=3, foreground='#111111')])

    # Y-axis stat name labels: Fira Sans Extra Condensed — naturally narrow glyphs
    # sized smaller than value labels so they fit the left margin cleanly
    from matplotlib.font_manager import FontProperties
    tick_fontsize = int(value_fontsize / 1.5)
    condensed_fp = FontProperties(
        family='Fira Sans Extra Condensed',
        size=tick_fontsize,
    )
    ax.tick_params(axis='y', labelsize=tick_fontsize)
    for _lbl in ax.get_yticklabels():
        _lbl.set_fontproperties(condensed_fp)

    # X-axis value ticks: proportional to value_fontsize (secondary reference numbers),
    # capped at 20pt so they don't compete with bar labels on phone screens.
    ax.tick_params(axis='x', labelsize=max(12, min(int(value_fontsize * 0.45), 20)))

    # MANUAL TITLE with two-tone coloring
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name

    # Build title manually with fig.text for proper positioning
    y_position = 0.96  # Start near top
    # Line spacing proportional to font height in figure-fraction coordinates
    line_spacing = (title_fontsize / fig_height_pts) * 1.30

    # Line 1: "{Player}'s {title_label}" - WHITE
    line1 = f"{player_name}'s {title_label}"
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

    # Add timestamp
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

    # Add multi-platform branding
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01

    # "YT" in red
    fig.text(x_start, branding_y_pos, 'YT', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#FF0000', fontweight='bold')

    # " & " in white
    fig.text(x_start + amp_offset, branding_y_pos, ' & ', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='normal')

    # "Twitch" in purple
    fig.text(x_start + twitch_offset, branding_y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#9146FF', fontweight='bold')

    # Handle in white
    fig.text(x_start + handle_offset, branding_y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='bold')

    # Compute top margin dynamically: 2 title lines normally, 3 with holiday theme
    n_title_lines = 3 if theme['show_in_title'] else 2
    top_margin = 0.96 - n_title_lines * line_spacing

    # 2-stat: use a centered, slightly smaller rect so bars don't dominate the canvas.
    # 3-stat: use full dynamic top_margin to fill available space.
    if num_stats == 2:
        if size == 'instagram':
            plt.tight_layout(rect=[0, 0.15, 1, 0.72])
        else:  # twitter
            plt.tight_layout(rect=[0, 0.12, 1, 0.75])
    else:
        plt.tight_layout(rect=[0, 0.05, 1, top_margin])

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.3)
    buf.seek(0)
    plt.close(fig)

    return buf


def generate_line_chart(stat_history, player_name, game_name, game_installment=None, size='twitter', game_mode=None, tz=None):
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
        size: 'twitter' (1600x900) or 'instagram' (1080x1080)
    
    Returns:
        BytesIO buffer containing the chart image
    """
    dates = stat_history.get('dates', [])

    if not dates:
        raise ValueError("No dates provided in stat_history")

    # Get themed colors
    theme = get_themed_colors(tz)
    colors = theme['colors']

    # Count active stats for font sizing
    num_stats = sum(
        1 for i in range(1, 4)
        if f'stat{i}' in stat_history and stat_history[f'stat{i}']
    )

    # Pre-compute title line for dynamic font sizing
    _line1_preview = f"{player_name}'s Performance Over Time"
    _char_ratio = 0.60
    _fill = 0.88

    # Fixed canvas sizes matching generate_bar_chart
    if size == 'instagram':
        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        fig_width_pts  = 10.8 * 72
        fig_height_pts = 10.8 * 72
        title_fontsize = max(28, min(int(fig_width_pts * _fill / (len(_line1_preview) * _char_ratio)), 48))
        direct_label_fontsize = 42 if num_stats <= 2 else 30
        branding_fontsize = 18
        # Branding offsets for 18pt on 10.8-inch figure (0.0108/char)
        amp_offset = 0.024
        twitch_offset = 0.059
        handle_offset = 0.127
        branding_y_pos = 0.03
    else:  # twitter - 1600x900
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        fig_width_pts  = 16 * 72
        fig_height_pts = 9 * 72
        title_fontsize = max(28, min(int(fig_width_pts * _fill / (len(_line1_preview) * _char_ratio)), 52))
        direct_label_fontsize = 42 if num_stats <= 2 else 30
        branding_fontsize = 17
        # Branding offsets for 17pt on 16-inch figure (0.00689/char)
        amp_offset = 0.015
        twitch_offset = 0.038
        handle_offset = 0.082
        branding_y_pos = 0.03

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
                
                # Glow effect: wide low-alpha strokes behind the main line
                # (no fill_between — fills stack badly when stats span orders of magnitude)
                ax.plot(dates, plot_values, color=colors[i-1], linewidth=18, alpha=0.08, zorder=1)
                ax.plot(dates, plot_values, color=colors[i-1], linewidth=10, alpha=0.14, zorder=2)

                line, = ax.plot(dates, plot_values,
                       color=colors[i-1],
                       marker=markers[i-1],
                       linewidth=4,
                       markersize=10,
                       label=abbrev_label,
                       markeredgecolor='white',
                       markeredgewidth=1.5,
                       zorder=5)

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
        from matplotlib.ticker import FuncFormatter, LogLocator
        import math
        def log_formatter(x, pos):
            """Format log scale labels to show actual values"""
            if x >= 1000:
                return f'{int(x/1000)}k'
            elif x >= 1:
                return f'{int(x)}'
            else:
                return f'{x:.1f}'
        ax.yaxis.set_major_formatter(FuncFormatter(log_formatter))
        # Extend y-axis to a nice number above the data max so the axis shows all values
        max_val = max(all_values)
        magnitude = 10 ** math.floor(math.log10(max_val * 1.1))
        normalized = (max_val * 1.1) / magnitude
        if normalized <= 1:
            nice_max = 1 * magnitude
        elif normalized <= 2:
            nice_max = 2 * magnitude
        elif normalized <= 5:
            nice_max = 5 * magnitude
        else:
            nice_max = 10 * magnitude
        ax.set_ylim(top=nice_max)
        # Add intermediate ticks (1, 2, 5 × 10^n) so labels like 2k, 5k appear
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=[1, 2, 5]))
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
    # Line spacing proportional to font height in figure-fraction coordinates
    line_spacing = (title_fontsize / fig_height_pts) * 1.30

    # Line 1: "{Player}'s  Performance Over Time" - WHITE
    line1 = f"{player_name}'s Performance Over Time"
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
    # Dynamic date label size: space per label divided by rotated-label footprint.
    # At 35° rotation horizontal footprint ≈ fontsize × 3.5 (width × cos + height × sin).
    # Capped at 20pt (phone-readable) and floored at 12pt (still legible when dense).
    _axis_w_pts = fig_width_pts * 0.80  # ~80% of figure width used by axes
    _space_per_date = _axis_w_pts / max(len(dates), 1)
    date_fontsize = max(12, min(int(_space_per_date / 3.5), 20))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha='right', fontsize=date_fontsize)
    
    # Add direct labels at end of lines (instead of legend)
    if line_end_positions:
        # Sort by y-position (ascending) so we can detect and resolve overlaps
        line_end_positions.sort(key=lambda x: x['y'])

        ymin, ymax = ax.get_ylim()
        ax_height_pts = fig.get_size_inches()[1] * 72 * ax.get_position().height

        # On a log axis the data→screen mapping is log10-linear, not linear.
        # Using raw data values to estimate screen gaps gives completely wrong
        # spread distances (e.g. values 9 and 12 look far apart in data space
        # but are visually close on a log scale).  Convert to log10 space first
        # so the gap calculation matches what is actually rendered on screen.
        if use_log:
            import math
            _to_screen = lambda v: math.log10(max(v, 1e-10))
            log_min = _to_screen(max(ymin, 1e-10))
            log_max = _to_screen(max(ymax, 1e-10))
            y_range = max(log_max - log_min, 1e-6)
            spread_positions = [_to_screen(pos['y']) for pos in line_end_positions]
        else:
            y_range = max(ymax - ymin, 1)
            spread_positions = [pos['y'] for pos in line_end_positions]

        # Convert data-space units → approximate screen points so we can
        # compare label positions against a fixed pixel/point gap threshold.
        data_to_pts = ax_height_pts / y_range

        MIN_GAP_PTS = int(direct_label_fontsize * 1.6)  # scales with label size

        n = len(line_end_positions)
        y_offsets = [0.0] * n

        # Iterative spread: keep nudging overlapping pairs apart until all are
        # separated by MIN_GAP_PTS.  Handles 2 or 3 lines at the same y-value.
        for _ in range(30):
            moved = False
            for j in range(n - 1):
                pos_j  = spread_positions[j]     * data_to_pts + y_offsets[j]
                pos_j1 = spread_positions[j + 1] * data_to_pts + y_offsets[j + 1]
                gap = pos_j1 - pos_j
                if gap < MIN_GAP_PTS:
                    push = (MIN_GAP_PTS - gap) / 2.0
                    y_offsets[j]     -= push
                    y_offsets[j + 1] += push
                    moved = True
            if not moved:
                break

        # Add text labels at line ends (show ACTUAL values with abbreviation)
        _max_label_chars = 6  # minimum — drives right-margin calculation below
        for idx, pos in enumerate(line_end_positions):
            label_x = pos['x']
            label_y = pos['y']

            # Format actual value for display
            actual_val = pos['actual_y']
            value_display = format_large_number(actual_val)

            label_text = f"{pos['label']}: {value_display}"
            _max_label_chars = max(_max_label_chars, len(label_text))

            ax.annotate(label_text,
                       xy=(label_x, label_y),
                       xytext=(10, y_offsets[idx]),  # x offset right + vertical spread if needed
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
    
    # Elevate-style: no y-axis, subtle x grid only, full-bleed width
    ax.yaxis.set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('white')
    ax.grid(axis='x', alpha=0.15, linestyle='--')
    ax.set_axisbelow(True)

    # Snap x-axis to data range — no padding so line fills full width
    ax.set_xlim(dates[0], dates[-1])

    # Add timestamp
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

    # Add multi-platform branding
    handle = os.environ.get('TWITCH_HANDLE', 'TheBOLBroadcast')
    x_start = 0.01

    # "YT" in red
    fig.text(x_start, branding_y_pos, 'YT', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#FF0000', fontweight='bold')

    # " & " in white
    fig.text(x_start + amp_offset, branding_y_pos, ' & ', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='normal')

    # "Twitch" in purple
    fig.text(x_start + twitch_offset, branding_y_pos, 'Twitch', ha='left', va='bottom',
             fontsize=branding_fontsize, color='#9146FF', fontweight='bold')

    # Handle in white
    fig.text(x_start + handle_offset, branding_y_pos, f' : {handle}', ha='left', va='bottom',
             fontsize=branding_fontsize, color='white', fontweight='bold')

    # Compute top margin dynamically: 2 title lines normally, 3 with holiday theme
    n_title_lines = 3 if theme['show_in_title'] else 2
    top_margin = 0.96 - n_title_lines * line_spacing

    # Dynamic right boundary: measure longest label text and reserve exactly
    # enough figure-fraction for it (char width + bbox pad + 10pt offset).
    _max_label_chars = _max_label_chars if line_end_positions else 6
    _label_width_pts = _max_label_chars * direct_label_fontsize * 0.60 + direct_label_fontsize + 10
    _right = max(0.60, 1.0 - _label_width_pts / fig_width_pts)

    # Three independent bands — no tight_layout so nothing can shift the regions:
    #   Top band   : title text (fig.text, y > top_margin)
    #   Middle band: axes — full bleed left, right = dynamic label margin
    #   Bottom band: branding text (fig.text, y < 0.18)
    plt.subplots_adjust(left=0, right=_right, bottom=0.18, top=top_margin)

    # Save to bytes — fixed canvas size, no bbox expansion so title stays centered
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100,
                facecolor=fig.get_facecolor(), pad_inches=0)
    buf.seek(0)
    plt.close(fig)


    return buf


def get_stat_history_from_db(cur, player_id, game_id, top_stat_types, timezone_str='UTC', days_back=365):
    """
    Fetch historical data for line chart from database.

    Args:
        days_back: int or None. Limit results to this many days back from today.
                   Pass None to fetch all-time history.
    """
    stat_history = {
        'dates': [],
        'stat1': {'label': '', 'values': []},
        'stat2': {'label': '', 'values': []},
        'stat3': {'label': '', 'values': []}
    }

    if not top_stat_types:
        return stat_history

    # Single batched query: all stat types × all dates in one round-trip.
    # Previously this was a nested loop that fired up to (dates × stat_types)
    # individual queries — up to 1,095 queries for 365 days × 3 stats.
    placeholders = ','.join(['%s'] * len(top_stat_types[:3]))

    # Use a window function to get the most recently submitted value per (date, stat_type).
    # MAX would show the highest value from all matches on a given day, which doesn't
    # match what the user just submitted when a later match has a lower value (e.g.,
    # match 1: 9 elims, match 2: 7 elims → MAX=9 but latest=7).
    # Each session's played_at (converted to local time) is used as the x-axis key.
    # Multiple stat types within the same session share the same played_at, so the
    # seen_dates deduplication below groups them into one x position automatically.
    # Same-day sessions become separate dots rather than collapsing to one per day.
    if days_back is not None:
        cur.execute(f"""
            SELECT (played_at AT TIME ZONE %s) AS play_ts, stat_type, stat_value
            FROM fact.fact_game_stats
            WHERE player_id = %s
              AND game_id = %s
              AND stat_type IN ({placeholders})
              AND played_at >= NOW() - (%s || ' days')::INTERVAL
            ORDER BY play_ts;
        """, (timezone_str, player_id, game_id, *top_stat_types[:3], days_back))
    else:
        cur.execute(f"""
            SELECT (played_at AT TIME ZONE %s) AS play_ts, stat_type, stat_value
            FROM fact.fact_game_stats
            WHERE player_id = %s
              AND game_id = %s
              AND stat_type IN ({placeholders})
            ORDER BY play_ts;
        """, (timezone_str, player_id, game_id, *top_stat_types[:3]))

    # Pivot results into the expected stat_history structure
    stat_values_map = {st: {} for st in top_stat_types[:3]}
    dates_ordered = []
    seen_dates = set()

    for row in cur.fetchall():
        play_ts, stat_type, best_value = row
        if play_ts not in seen_dates:
            seen_dates.add(play_ts)
            dates_ordered.append(play_ts)
        if stat_type in stat_values_map:
            stat_values_map[stat_type][play_ts] = int(float(best_value)) if best_value is not None else 0

    stat_history['dates'] = dates_ordered

    if not dates_ordered:
        return stat_history

    for i, stat_type in enumerate(top_stat_types[:3], 1):
        stat_key = f'stat{i}'
        stat_history[stat_key]['label'] = stat_type
        stat_history[stat_key]['values'] = [
            stat_values_map[stat_type].get(ts, 0) for ts in dates_ordered
        ]

    return stat_history


def generate_interactive_chart(chart_type, data, player_name, game_name,
                               game_installment=None, game_mode=None, tz=None):
    """Generate an interactive Plotly HTML chart from already-computed in-memory data.

    No database queries — data must be pre-computed before calling this function.

    Args:
        chart_type: 'bar' (first game) or 'line' (multiple games)
        data: stat_data dict for 'bar', stat_history dict for 'line'
        player_name, game_name, game_installment, game_mode: metadata for titles

    Returns:
        bytes: UTF-8 encoded HTML (~15-25 KB with CDN plotly.js)
    """
    import plotly.graph_objects as go

    game_label = f"{game_name}: {game_installment}" if game_installment else game_name
    if game_mode:
        game_label += f" — {game_mode}"
    title = f"{player_name} · {game_label}"

    bg_color = "#111111"
    grid_color = "#2a2a2a"
    text_color = "#e0e0e0"
    theme = get_themed_colors(tz)
    accent_colors = theme['colors']  # Dynamically matches holiday_themes.py

    fig = go.Figure()

    if chart_type == 'bar':
        labels, values = [], []
        for i in range(1, 4):
            key = f'stat{i}'
            if key not in data or not data[key]:
                continue
            stat = data[key]
            labels.append(stat.get('label', key))
            values.append(stat.get('value', 0))

        use_log = should_use_log_scale(values)
        plot_values = [max(v, 0.001) for v in values] if use_log else values
        formatted = [format_large_number(v) for v in values]

        fig.add_trace(go.Bar(
            x=plot_values,
            y=labels,
            orientation='h',
            name='This Session',
            marker_color=accent_colors[:len(labels)],
            text=formatted,
            textposition='outside',
            textfont=dict(color='white', size=14),
            customdata=formatted,
            hovertemplate='%{y}<br>Value: %{customdata}<extra></extra>',
        ))

        x_axis_cfg = {}
        if use_log:
            x_axis_cfg['type'] = 'log'
        elif any(v >= 1000 for v in values):
            x_axis_cfg['tickformat'] = '.2s'
        else:
            x_axis_cfg['rangemode'] = 'tozero'

        fig.update_layout(
            bargap=0.3,
            xaxis=x_axis_cfg,
            yaxis=dict(autorange='reversed'),
        )

    else:  # line chart
        dates = data.get('dates', [])
        date_strings = [d.strftime('%b %d, %Y') if hasattr(d, 'strftime') else str(d)
                        for d in dates]

        all_line_values = []
        for i in range(1, 4):
            key = f'stat{i}'
            if key in data and data[key]:
                all_line_values.extend(data[key].get('values', []))
        use_log = should_use_log_scale(all_line_values) if all_line_values else False

        for i, color in enumerate(accent_colors, 1):
            key = f'stat{i}'
            if key not in data or not data[key]:
                continue
            series = data[key]
            label = series.get('label', key)
            vals = series.get('values', [])
            if not any(v for v in vals):
                continue

            plot_vals = [max(v, 0.001) for v in vals] if use_log else vals
            formatted_vals = [format_large_number(v) for v in vals]

            fig.add_trace(go.Scatter(
                x=date_strings,
                y=plot_vals,
                mode='lines+markers',
                name=label,
                line=dict(color=color, width=2),
                marker=dict(size=6, color=color),
                customdata=formatted_vals,
                hovertemplate=f'{label}<br>%{{x}}<br>Value: %{{customdata}}<extra></extra>',
            ))

        if use_log:
            fig.update_layout(yaxis=dict(type='log'))
        else:
            fig.update_layout(yaxis=dict(rangemode='tozero'))

        # Date-axis formatting only makes sense for the line chart's category/date x-axis
        fig.update_layout(
            xaxis=dict(
                gridcolor=grid_color,
                linecolor=grid_color,
                tickfont=dict(color=text_color, size=10),
                dtick="M1",                      # one tick per month
                tickformat="%b '%y",             # "Mar '26" — year always visible
                tickangle=-45,
                ticklabeloverflow="hide past div",
            ),
        )

    fig.update_layout(
        title=dict(text=title, font=dict(color=text_color, size=16), x=0.5),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color, family='monospace'),
        xaxis=dict(
            gridcolor=grid_color,
            linecolor=grid_color,
            tickfont=dict(color=text_color, size=10),
        ),
        yaxis=dict(gridcolor=grid_color, linecolor=grid_color, tickfont=dict(color=text_color)),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=text_color)),
        margin=dict(t=60, b=100, l=60, r=40),
        hovermode='x unified' if chart_type == 'line' else 'closest',
        hoverlabel=dict(font_color='white', bgcolor='#1e1e1e', bordercolor='#444444'),
    )

    html = fig.to_html(
        full_html=True,
        include_plotlyjs='cdn',       # ~15 KB file vs ~3 MB self-contained
        config={'displayModeBar': True, 'responsive': True},
    )
    # Inject CSS so the chart fills the iframe viewport with no scrollbars.
    # 'responsive: True' handles Plotly resizing but doesn't remove browser
    # default body margins or prevent the page from overflowing the iframe.
    html = html.replace(
        '</head>',
        '<style>'
        'html,body{margin:0;padding:0;overflow:hidden;height:100%;width:100%}'
        '.js-plotly-plot,.plot-container{height:100%!important;width:100%!important}'
        '</style></head>',
        1,
    )
    return html.encode('utf-8')