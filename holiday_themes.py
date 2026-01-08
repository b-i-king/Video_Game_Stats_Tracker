"""
Holiday theme detection and color palettes
Automatically switches chart colors based on current date
"""

from datetime import date
from dateutil.easter import easter


def get_current_holiday():
    """
    Determine which holiday (if any) is currently being observed.
    Returns holiday name or None.
    
    Holiday window: 3 days before to 3 days after the actual date
    """
    today = date.today()
    year = today.year
    
    # Define holidays with their dates
    holidays = {
        'New Year': date(year, 1, 1),
        'MLK Day': get_nth_weekday(year, 1, 0, 3),  # 3rd Monday in January
        'Valentine': date(year, 2, 14),
        'Easter': easter(year),
        'Memorial Day': get_last_weekday(year, 5, 0),  # Last Monday in May
        'Juneteenth': date(year, 6, 19),
        'Independence Day': date(year, 7, 4),
        'Labor Day': get_nth_weekday(year, 9, 0, 1),  # 1st Monday in September
        'Veterans Day': date(year, 11, 11),
        'Thanksgiving': get_nth_weekday(year, 11, 3, 4),  # 4th Thursday in November
        'Christmas': date(year, 12, 25),
        'Mother Day': get_nth_weekday(year, 5, 6, 2),  # 2nd Sunday in May
        'Father Day': get_nth_weekday(year, 6, 6, 3)   # 3rd Sunday in June
    }
    
    # Check if today is within 3 days of any holiday
    for holiday_name, holiday_date in holidays.items():
        days_diff = abs((today - holiday_date).days)
        if days_diff <= 3:
            return holiday_name
    
    return None


def get_nth_weekday(year, month, weekday, n):
    """
    Get the nth occurrence of a weekday in a month.
    weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
    n: 1=first, 2=second, etc.
    """
    from calendar import monthcalendar
    cal = monthcalendar(year, month)
    count = 0
    for week in cal:
        if week[weekday] != 0:
            count += 1
            if count == n:
                return date(year, month, week[weekday])
    return None


def get_last_weekday(year, month, weekday):
    """Get the last occurrence of a weekday in a month."""
    from calendar import monthcalendar
    cal = monthcalendar(year, month)
    for week in reversed(cal):
        if week[weekday] != 0:
            return date(year, month, week[weekday])
    return None


def get_color_palette(holiday=None):
    """
    Get color palette based on holiday or default gaming theme.
    
    Returns:
        dict with 'colors' (list of 3 colors) and 'name' (theme name)
    """
    
    # Holiday-specific palettes
    holiday_palettes = {
        'New Year': {
            'colors': ['#FFD700', '#C0C0C0', '#FFFFFF'],  # Gold, Silver, White
            'name': 'New Year (Gold & Silver)'
        },
        'MLK Day': {
            'colors': ['#000000', '#FFFFFF', '#808080'],  # Black, White, Gray
            'name': 'MLK Day (Unity)'
        },
        'Valentine': {
            'colors': ['#FF1493', '#FF69B4', '#FFC0CB'],  # Deep pink, Hot pink, Light pink
            'name': 'Valentine\'s Day (Love)'
        },
        'Easter': {
            'colors': ['#FFB6C1', '#87CEEB', '#98FB98'],  # Pastel pink, Sky blue, Pale green
            'name': 'Easter (Pastels)'
        },
        'Memorial Day': {
            'colors': ['#B22234', '#FFFFFF', '#3C3B6E'],  # Red, White, Blue (USA)
            'name': 'Memorial Day (Patriotic)'
        },
        'Juneteenth': {
            'colors': ['#FF0000', '#000000', '#00FF00'],  # Red, Black, Green (Pan-African)
            'name': 'Juneteenth (Freedom)'
        },
        'Independence Day': {
            'colors': ['#B22234', '#FFFFFF', '#3C3B6E'],  # Red, White, Blue
            'name': '4th of July (America)'
        },
        'Labor Day': {
            'colors': ['#FF6B35', '#004E89', '#1A936F'],  # Orange, Navy, Green (work/industry)
            'name': 'Labor Day (Industry)'
        },
        'Veterans Day': {
            'colors': ['#6B8E23', '#8B4513', '#FFD700'],  # Olive, Brown, Gold (military)
            'name': 'Veterans Day (Military)'
        },
        'Thanksgiving': {
            'colors': ['#FF8C00', '#8B4513', '#FFD700'],  # Orange, Brown, Gold (autumn)
            'name': 'Thanksgiving (Harvest)'
        },
        'Christmas': {
            'colors': ['#C8102E', '#00843D', '#FFD700'],  # Red, Green, Gold
            'name': 'Christmas (Festive)'
        },
        'Mother Day': {
            'colors': ['#FFB6C1', '#DDA0DD', '#FFC0CB'],  # Pink, Plum, Light pink
            'name': 'Mother\'s Day (Appreciation)'
        },
        'Father Day': {
            'colors': ['#4169E1', '#2F4F4F', '#708090'],  # Royal blue, Dark slate, Slate gray
            'name': 'Father\'s Day (Strength)'
        }
    }
    
    # Return holiday palette if applicable
    if holiday and holiday in holiday_palettes:
        return holiday_palettes[holiday]
    
    # Default gaming theme (neon colors)
    return {
        'colors': ['#00ff41', '#00d4ff', '#ff00ff'],  # Neon green, Cyan, Magenta
        'name': 'Gaming (Default)'
    }


def get_themed_colors():
    """
    Main function to get colors for current date.
    Call this when generating charts.
    
    Returns:
        dict with 'colors', 'name', and 'holiday' (or None)
    """
    current_holiday = get_current_holiday()
    palette = get_color_palette(current_holiday)
    
    result = {
        'colors': palette['colors'],
        'theme_name': palette['name'],
        'holiday': current_holiday
    }
    
    # Log for debugging
    if current_holiday:
        print(f"🎉 Holiday theme active: {palette['name']}")
    else:
        print(f"🎮 Using default gaming theme")
    
    return result