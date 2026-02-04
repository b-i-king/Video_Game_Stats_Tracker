"""
IFTTT Webhook integration for posting to social media
"""

import requests
import os


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


def generate_post_caption(player_name, game_name, game_installment, stat_data, games_played, is_live=False):
    """
    Generate engaging caption for social media post.
    
    Args:
        player_name: str
        game_name: str
        game_installment: str or None
        stat_data: dict with stat1, stat2, stat3
        games_played: int
        is_live: bool (True if user is currently live streaming)
    
    Returns:
        str: Caption text
    """
    from holiday_themes import get_themed_colors
    
    full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
    
    # Extract top stat for highlight
    stat1_label = stat_data.get('stat1', {}).get('label', 'Stat 1')
    stat1_value = stat_data.get('stat1', {}).get('value', 0)
    
    # Get theme info for hashtags
    theme = get_themed_colors()
    
    if games_played == 1:
        # First game caption
        if is_live:
            caption = (
                f"🔴 LIVE NOW! 🔴\n\n"
                f"🎮 First game on {full_game_name}! 🎮\n\n"
                f"🔥 {stat1_label}: {stat1_value}\n\n"
                f"Watch live: twitch.tv/{os.environ.get('TWITCH_HANDLE', 'YourHandle')}\n\n"
            )
            # Add hashtags
            hashtags = [f"#{game_name.replace(' ', '')}", '#Live', '#TheBroadcast', '#Gaming', '#LiveStream']
        else:
            caption = (
                f"🎮 First game on {full_game_name}! 🎮\n\n"
                f"🔥 {stat1_label}: {stat1_value}\n\n"
            )
            # Add hashtags
            hashtags = [f"#{game_name.replace(' ', '')}", '#Gaming', '#Stats']
    else:
        # Multi-game caption
        if is_live:
            caption = (
                f"🔴 LIVE NOW! 🔴\n\n"
                f"📊 {full_game_name} Progress Report! 📊\n\n"
                f"Games Played: {games_played}\n"
                f"🔥 Latest {stat1_label}: {stat1_value}\n\n"
                f"Join the stream: twitch.tv/{os.environ.get('TWITCH_HANDLE', 'YourHandle')}\n\n"
            )
            # Add hashtags
            hashtags = [f"#{game_name.replace(' ', '')}", '#Live', '#TheBroadcast', '#Gaming', '#GamingAnalytics']
        else:
            caption = (
                f"📊 {full_game_name} Progress Report! 📊\n\n"
                f"Games Played: {games_played}\n"
                f"🔥 Latest {stat1_label}: {stat1_value}\n\n"
            )
            # Add hashtags
            hashtags = [f"#{game_name.replace(' ', '')}", '#Gaming', '#Stats', '#GamingAnalytics']
    
    # Add heritage/holiday hashtag if present
    if theme.get('hashtag'):
        hashtags.append(theme['hashtag'])
    
    # Add hashtags to caption
    caption += ' '.join(hashtags)
    
    # Add YouTube handle if offline (less cluttered when live)
    if not is_live:
        caption += f"\n\n📺 YouTube: youtube.com/@{os.environ.get('YOUTUBE_HANDLE', 'TheBOLBroadcast')}"
    
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