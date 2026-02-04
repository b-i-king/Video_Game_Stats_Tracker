"""
Holiday theme detection and color palettes
Automatically switches chart colors based on current date
"""

from datetime import datetime, date
from dateutil.easter import easter


def get_current_holiday():
    """
    Determine which holiday (if any) is currently being observed.
    Returns holiday name or None.
    
    Holiday window: ±1 days before to ±1 days after the actual date
    Heritage Months: Entire month (no buffer)
    
    Priority: Specific holidays take precedence over heritage months
    """
    today = date.today()
    year = today.year
    month = today.month
    
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
    
    # Check if today is within ±1 days of any holiday (HOLIDAYS TAKE PRIORITY)
    for holiday_name, holiday_date in holidays.items():
        days_diff = abs((today - holiday_date).days)
        if days_diff <= 1:
            return holiday_name
    
    # If no specific holiday, check for heritage months (ENTIRE MONTH)
    heritage_months = {
        2: 'Black History Month',
        3: 'Women\'s History Month',
        11: 'Native American Heritage Month'
    }
    
    if month in heritage_months:
        return heritage_months[month]
    
    return None


def is_exact_holiday():
    """
    Check if TODAY is the EXACT date of a holiday (not buffer days).
    Used for displaying holiday name in chart title.
    
    Returns:
        str: Holiday name if today is exact date, None otherwise
    """
    today = date.today()
    year = today.year
    
    holidays = {
        'New Year': date(year, 1, 1),
        'MLK Day': get_nth_weekday(year, 1, 0, 3),
        'Valentine': date(year, 2, 14),
        'Easter': easter(year),
        'Memorial Day': get_last_weekday(year, 5, 0),
        'Juneteenth': date(year, 6, 19),
        'Independence Day': date(year, 7, 4),
        'Labor Day': get_nth_weekday(year, 9, 0, 1),
        'Veterans Day': date(year, 11, 11),
        'Thanksgiving': get_nth_weekday(year, 11, 3, 4),
        'Christmas': date(year, 12, 25),
        'Mother Day': get_nth_weekday(year, 5, 6, 2),
        'Father Day': get_nth_weekday(year, 6, 6, 3)
    }
    
    # Check if today matches any holiday exactly
    for holiday_name, holiday_date in holidays.items():
        if today == holiday_date:
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
        dict with 'colors' (list of 3 colors), 'name' (theme name), and 'hashtag' (optional)
    """
    
    # Holiday-specific palettes (includes heritage months)
    holiday_palettes = {
        'New Year': {
            'colors': ['#FFD700', '#C0C0C0', '#FFFFFF'],  # Gold, Silver, White
            'name': 'New Year',
            'hashtag': '#NewYear'
        },
        'Black History Month': {
            'colors': ['#008000', '#FFD700', '#DC143C'],  # Green, Gold, Red (Pan-African)
            'name': 'Black History Month',
            'hashtag': '#BHM'
        },
        'Women\'s History Month': {
            'colors': ['#9370DB', '#DA70D6', '#DDA0DD'],  # Purple, Orchid, Plum
            'name': 'Women\'s History Month',
            'hashtag': '#WomensHistoryMonth'
        },
        'Native American Heritage Month': {
            'colors': ['#8B4513', '#DAA520', '#CD853F'],  # Brown, Goldenrod, Peru (Earth tones)
            'name': 'Native American Heritage Month',
            'hashtag': '#NAHM'
        },
        'MLK Day': {
            'colors': ['#000000', '#FFFFFF', '#808080'],  # Black, White, Gray
            'name': 'MLK Day',
            'hashtag': '#MLKDay'
        },
        'Valentine': {
            'colors': ['#FF1493', '#FF69B4', '#FFC0CB'],  # Deep pink, Hot pink, Light pink
            'name': 'Valentine\'s Day',
            'hashtag': '#ValentinesDay'
        },
        'Easter': {
            'colors': ['#FFB6C1', '#87CEEB', '#98FB98'],  # Pastel pink, Sky blue, Pale green
            'name': 'Easter',
            'hashtag': '#Easter'
        },
        'Memorial Day': {
            'colors': ['#B22234', '#FFFFFF', '#3C3B6E'],  # Red, White, Blue (USA)
            'name': 'Memorial Day',
            'hashtag': '#MemorialDay'
        },
        'Juneteenth': {
            'colors': ['#FF0000', '#000000', '#00FF00'],  # Red, Black, Green (Pan-African)
            'name': 'Juneteenth',
            'hashtag': '#Juneteenth'
        },
        'Independence Day': {
            'colors': ['#B22234', '#FFFFFF', '#3C3B6E'],  # Red, White, Blue
            'name': '4th of July',
            'hashtag': '#IndependenceDay'
        },
        'Labor Day': {
            'colors': ['#FF6B35', '#004E89', '#1A936F'],  # Orange, Navy, Green (work/industry)
            'name': 'Labor Day',
            'hashtag': '#LaborDay'
        },
        'Veterans Day': {
            'colors': ['#6B8E23', '#8B4513', '#FFD700'],  # Olive, Brown, Gold (military)
            'name': 'Veterans Day',
            'hashtag': '#VeteransDay'
        },
        'Thanksgiving': {
            'colors': ['#FF8C00', '#8B4513', '#FFD700'],  # Orange, Brown, Gold (autumn)
            'name': 'Thanksgiving',
            'hashtag': '#Thanksgiving'
        },
        'Christmas': {
            'colors': ['#C8102E', '#00843D', '#FFD700'],  # Red, Green, Gold
            'name': 'Christmas',
            'hashtag': '#Christmas'
        },
        'Mother Day': {
            'colors': ['#FFB6C1', '#DDA0DD', '#FFC0CB'],  # Pink, Plum, Light pink
            'name': 'Mother\'s Day',
            'hashtag': '#MothersDay'
        },
        'Father Day': {
            'colors': ['#4169E1', '#2F4F4F', '#708090'],  # Royal blue, Dark slate, Slate gray
            'name': 'Father\'s Day',
            'hashtag': '#FathersDay'
        }
    }
    
    # Return holiday palette if applicable
    if holiday and holiday in holiday_palettes:
        return holiday_palettes[holiday]
    
    # Default gaming theme (neon colors)
    return {
        'colors': ['#00ff41', '#00d4ff', '#ff00ff'],  # Neon green, Cyan, Magenta
        'name': 'Gaming',
        'hashtag': None
    }


def get_themed_colors():
    """
    Main function to get colors for current date.
    Call this when generating charts.
    
    Heritage Months: Colors + hashtag + TITLE for ENTIRE month (unless specific holiday)
    Specific Holidays: Colors + hashtag + title apply within ±1 day window
    
    Priority: Exact holidays override heritage months for title display
    
    Returns:
        dict with 'colors', 'theme_name', 'holiday', 'show_in_title' (bool), and 'hashtag' (str or None)
    """
    current_holiday = get_current_holiday()  # Checks holidays first, then heritage months
    exact_holiday = is_exact_holiday()        # Exact date only for specific holidays
    palette = get_color_palette(current_holiday)
    
    # Determine if we should show name in title
    # Show heritage month name in title UNLESS there's an exact holiday
    heritage_months = ['Black History Month', 'Women\'s History Month', 'Native American Heritage Month']
    
    if exact_holiday:
        # Exact holiday takes precedence - show holiday in title
        show_in_title = exact_holiday
    elif current_holiday in heritage_months:
        # Heritage month - show in title for entire month
        show_in_title = current_holiday
    else:
        # No exact holiday and not a heritage month
        show_in_title = None
    
    result = {
        'colors': palette['colors'],
        'theme_name': palette['name'],
        'holiday': current_holiday,           # For logging/debugging
        'show_in_title': show_in_title,       # Holiday name or heritage month name or None
        'hashtag': palette.get('hashtag')     # From palette (works for both holidays and heritage months)
    }
    
    # Log for debugging
    if current_holiday:
        # Check if it's a heritage month (entire month)
        if current_holiday in heritage_months:
            print(f"📅 Heritage Month Active: {palette['name']}")
            print(f"   Colors: {palette['colors']}")
            print(f"   Hashtag: {palette.get('hashtag')}")
            print(f"   Show in title: Yes (entire month)")
        elif exact_holiday:
            print(f"🎉 EXACT HOLIDAY: {palette['name']} (colors + title + hashtag)")
        else:
            print(f"🎨 Holiday colors active: {palette['name']} (colors + hashtag, no title)")
    else:
        print(f"🎮 Using default gaming theme")
    
    return result