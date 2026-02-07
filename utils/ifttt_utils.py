"""
IFTTT Webhook integration for posting to social media
Now uses centralized game_handles_utils for handles and hashtags
"""

import requests
import os
from utils.game_handles_utils import get_game_handle, get_game_hashtags


def trigger_ifttt_post(image_url, caption, platform='twitter'):
    """
    Trigger IFTTT webhook to post image to social media.
    
    Args:
        image_url: str (public URL of image on GCS)
        caption: str (post caption/tweet text)
        platform: str ('twitter', 'instagram', or 'both')
    
    Returns:
        bool: True if successful, False otherwise
    """
    webhook_key = os.environ.get('IFTTT_WEBHOOK_KEY')
    
    if not webhook_key:
        print("❌ IFTTT_WEBHOOK_KEY not set in environment variables")
        return False
    
    # Determine which event to trigger
    if platform == 'twitter':
        event_name = os.environ.get('IFTTT_EVENT_NAME_TWITTER', 'post_to_twitter')
    elif platform == 'instagram':
        event_name = os.environ.get('IFTTT_EVENT_NAME_INSTAGRAM', 'post_to_instagram')
    elif platform == 'both':
        # Trigger both
        success_twitter = trigger_ifttt_post(image_url, caption, 'twitter')
        success_instagram = trigger_ifttt_post(image_url, caption, 'instagram')
        return success_twitter and success_instagram
    else:
        print(f"❌ Unknown platform: {platform}")
        return False
    
    # IFTTT Webhook URL format
    url = f"https://maker.ifttt.com/trigger/{event_name}/with/key/{webhook_key}"
    
    # Payload with value1, value2, value3 (IFTTT standard)
    payload = {
        "value1": image_url,  # Image URL
        "value2": caption,     # Post caption
        "value3": platform     # Platform identifier
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        print(f"✅ IFTTT webhook triggered successfully for {platform}")
        print(f"   Event: {event_name}")
        print(f"   Response: {response.text}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to trigger IFTTT webhook: {e}")
        return False


def generate_post_caption(player_name, game_name, game_installment, stat_data, games_played, 
                         platform='twitter', is_live=False, credit_style='shoutout'):
    """
    Generate engaging caption for social media post.
    Now uses game_handles_utils for platform-specific handles and hashtags.
    
    Args:
        player_name: str
        game_name: str
        game_installment: str or None
        stat_data: dict with stat1, stat2, stat3
        games_played: int
        platform: str ('twitter' or 'instagram')
        is_live: bool (True if user is currently live streaming)
        credit_style: str - How to credit the game
            Options: 'shoutout', 'credit', 'props', 'playing', 'respect', 'vibes'
    
    Returns:
        str: Caption text optimized for the platform
    """
    from utils.holiday_themes import get_themed_colors
    
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    
    # Extract top stat for highlight
    stat1_label = stat_data.get('stat1', {}).get('label', 'Stat 1')
    stat1_value = stat_data.get('stat1', {}).get('value', 0)
    
    # Get theme info for hashtags
    theme = get_themed_colors()
    
    # Get game-specific handle and hashtags for this platform
    game_handle = get_game_handle(game_name, platform)
    game_hashtags = get_game_hashtags(game_name, platform)
    
    # Credit line options with game handle
    credit_lines = {
        'shoutout': f"S/O {game_handle}",
        'credit': f"Game Credit: {game_handle}",
        'props': f"Props to {game_handle}",
        'playing': f"Playing {game_handle}",
        'respect': f"Respect {game_handle}",
        'vibes': f"Vibes: {game_handle}",
        'powered': f"Powered by {game_handle}",
        'courtesy': f"Courtesy of {game_handle}",
        'ft': f"ft. {game_handle}",
        'brought': f"Brought to you by {game_handle}"
    }
    
    # Get the credit line (fallback to 'shoutout' if invalid style)
    credit_line = credit_lines.get(credit_style, credit_lines['shoutout'])
    
    # Build caption based on games played and live status
    if games_played == 1:
        # First game caption
        if is_live:
            caption = f"🔴 LIVE NOW! 🔴\n"
            caption += f"🎮 First game on {full_game_name}! 🎮\n"
            if game_handle:
                caption += f"{credit_line}\n"
            caption += f"\n🔥 {stat1_label.upper()}: {stat1_value}\n"
            
            # Add stream link based on platform
            if platform == 'twitter':
                caption += f"\nWatch live: twitch.tv/{os.environ.get('TWITCH_HANDLE', 'YourHandle')}\n"
            else:  # Instagram
                caption += f"\n🔗 Link in bio to watch live!\n"
            
            # Platform-specific base hashtags
            if platform == 'twitter':
                hashtags = ['#Live', '#TheBroadcast', '#Gaming', '#LiveStream']
            else:  # Instagram
                hashtags = ['#live', '#thebroadcast', '#gaming', '#livestream']
            
        else:
            caption = f"🎮 First game on {full_game_name}! 🎮\n"
            if game_handle:
                caption += f"{credit_line}\n"
            caption += f"\n🔥 {stat1_label.upper()}: {stat1_value}\n"
            
            # Platform-specific base hashtags
            if platform == 'twitter':
                hashtags = ['#Gaming', '#Stats']
            else:  # Instagram
                hashtags = ['#gaming', '#stats']
    
    else:
        # Multi-game caption
        if is_live:
            caption = f"🔴 LIVE NOW! 🔴\n"
            caption += f"📊 {full_game_name} Progress Report! 📊\n"
            if game_handle:
                caption += f"{credit_line}\n"
            caption += f"\nGames Played: {games_played}\n"
            caption += f"🔥 Latest {stat1_label.upper()}: {stat1_value}\n"
            
            # Add stream link based on platform
            if platform == 'twitter':
                caption += f"\nJoin the stream: twitch.tv/{os.environ.get('TWITCH_HANDLE', 'YourHandle')}\n"
            else:  # Instagram
                caption += f"\n🔗 Link in bio to join!\n"
            
            # Platform-specific base hashtags
            if platform == 'twitter':
                hashtags = ['#Live', '#TheBroadcast', '#Gaming', '#GamingAnalytics']
            else:  # Instagram
                hashtags = ['#live', '#thebroadcast', '#gaming', '#gaminganalytics']
            
        else:
            caption = f"📊 {full_game_name} Progress Report! 📊\n"
            if game_handle:
                caption += f"{credit_line}\n"
            caption += f"\nGames Played: {games_played}\n"
            caption += f"🔥 Latest {stat1_label.upper()}: {stat1_value}\n"
            
            # Platform-specific base hashtags
            if platform == 'twitter':
                hashtags = ['#Gaming', '#Stats', '#GamingAnalytics']
            else:  # Instagram
                hashtags = ['#gaming', '#stats', '#gaminganalytics']
    
    # Add game-specific hashtags
    if game_hashtags:
        hashtags.extend(game_hashtags)
    
    # Add heritage/holiday hashtag if present
    if theme.get('hashtag'):
        hashtags.append(theme['hashtag'])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_hashtags.append(tag)
    
    # Add hashtags to caption with single newline
    caption += f"\n{' '.join(unique_hashtags)}\n"
    
    # Add YouTube handle if offline (less cluttered when live)
    # Only for Instagram (Twitter has character limits)
    if not is_live:
        youtube_handle = os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')
        caption += f"\n📺 YouTube: youtube.com/@{youtube_handle}"
    
    return caption


def test_ifttt_connection():
    """
    Test IFTTT webhook connection with a simple test event.
    Run this to verify your IFTTT setup is working.
    """
    webhook_key = os.environ.get('IFTTT_WEBHOOK_KEY')
    
    if not webhook_key:
        print("❌ IFTTT_WEBHOOK_KEY not set")
        return False
    
    test_event = 'test_gaming_stats'
    url = f"https://maker.ifttt.com/trigger/{test_event}/with/key/{webhook_key}"
    
    payload = {
        "value1": "Test image URL",
        "value2": "Test caption from gaming stats bot",
        "value3": "test"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ IFTTT test successful!")
        print(f"   Response: {response.text}")
        return True
    except Exception as e:
        print(f"❌ IFTTT test failed: {e}")
        return False


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("Testing IFTTT Utils with game_handles_utils integration\n")
    
    # Test stat data
    test_stat_data = {
        'stat1': {'label': 'Eliminations', 'value': 28},
        'stat2': {'label': 'Respawns', 'value': 10},
        'stat3': {'label': 'E/R', 'value': 2.8}
    }
    
    # Test all credit styles
    credit_styles = ['shoutout', 'credit', 'props', 'playing', 'respect', 'vibes', 'ft', 'powered']
    
    print("=" * 80)
    print("TESTING DIFFERENT CREDIT STYLES")
    print("=" * 80)
    
    for style in credit_styles:
        print(f"\n{'='*80}")
        print(f"STYLE: '{style}' (First Game, Not Live, Twitter)")
        print(f"{'='*80}")
        caption = generate_post_caption(
            player_name="TestPlayer",
            game_name="Call of Duty",
            game_installment="Warzone",
            stat_data=test_stat_data,
            games_played=1,
            platform='twitter',
            is_live=False,
            credit_style=style
        )
        print(caption)
    
    print("\n" + "=" * 80)
    print("INSTAGRAM EXAMPLE (S/O style, Multiple Games, Not Live)")
    print("=" * 80)
    instagram_caption = generate_post_caption(
        player_name="TestPlayer",
        game_name="Apex Legends",
        game_installment=None,
        stat_data={'stat1': {'label': 'Eliminations', 'value': 15}},
        games_played=5,
        platform='instagram',
        is_live=False,
        credit_style='shoutout'
    )
    print(instagram_caption)
    
    print("\n" + "=" * 80)
    print("LIVE STREAM EXAMPLE (Props style, Twitter)")
    print("=" * 80)
    live_caption = generate_post_caption(
        player_name="TestPlayer",
        game_name="Valorant",
        game_installment=None,
        stat_data={'stat1': {'label': 'Eliminations', 'value': 22}},
        games_played=1,
        platform='twitter',
        is_live=True,
        credit_style='props'
    )
    print(live_caption)