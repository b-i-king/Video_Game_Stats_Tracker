"""
Google Cloud Storage utilities for uploading social media images
Organized folder structure:
- twitter/YYYY/MM/  → Auto-posted charts (1200x630)
- instagram/YYYY/MM/  → Weekly compilations (1080x1080)
- instagram/games/{game}/{installment}/{mode}/  → Game-specific collections
- instagram/posters/YYYY/MM/WEEK/  → Auto-posted Instagram portraits (1080x1440)
"""

from google.cloud import storage
from google.oauth2 import service_account
import os
import json
from datetime import datetime


def get_gcs_client():
    """
    Initialize and return GCS client with credentials.
    Supports both JSON string and file-based credentials.
    """
    credentials_json = os.environ.get('GCS_CREDENTIALS_JSON')
    
    if credentials_json:
        # Using JSON string from environment variable
        try:
            credentials_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            client = storage.Client(credentials=credentials, project=credentials_dict['project_id'])
            print("✅ GCS client initialized from JSON string")
            return client
        except Exception as e:
            print(f"❌ Failed to initialize GCS from JSON string: {e}")
            return None
    
    elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        # Using credentials file path
        try:
            client = storage.Client()
            print("✅ GCS client initialized from credentials file")
            return client
        except Exception as e:
            print(f"❌ Failed to initialize GCS from file: {e}")
            return None
    
    else:
        print("❌ No GCS credentials found in environment variables")
        return None


def upload_chart_to_gcs(image_buffer, player_name, game_name, chart_type='bar', platform='twitter',
                        storage_option='game', game_installment=None, game_mode=None):
    """
    Upload chart image to Google Cloud Storage with organized folder structure.

    Args:
        image_buffer: BytesIO object containing PNG image
        player_name: str (sanitized for filename)
        game_name: str (sanitized for filename)
        chart_type: str ('bar' or 'line')
        platform: str ('twitter' or 'instagram')
        storage_option: str — instagram only: 'game' | 'week' | 'month'
            'game'  → instagram/games/{game}/{installment}/{mode}/
                      (installment and mode segments omitted if None/empty/Main)
            'week'  → instagram/weekly/{year}/week_{week_num}/
            'month' → instagram/monthly/{year}/{month}/
        game_installment: str or None — game installment for 'game' storage path
        game_mode: str or None — game mode for 'game' storage path (skipped if None/empty/Main)

    Returns:
        str: Public URL of uploaded image, or None if failed
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    
    if not bucket_name:
        print("❌ GCS_BUCKET_NAME not set in environment variables")
        return None
    
    client = get_gcs_client()
    if not client:
        return None
    
    try:
        bucket = client.bucket(bucket_name)
        
        # Generate organized path based on platform
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        
        safe_player = sanitize_filename(player_name)
        safe_game = sanitize_filename(game_name)
        
        if platform == 'twitter':
            # twitter/2025/01/player_game_bar_20250115_143022.png
            folder_path = f"twitter/{year}/{month}"
            filename = f"{safe_player}_{safe_game}_{chart_type}_{timestamp}.png"

        elif platform == 'instagram':
            week_of_year = now.strftime('%W')  # ISO week number (00–53)
            if storage_option == 'week':
                # instagram/weekly/2025/week_12/player_game_bar_20250115_143022.png
                folder_path = f"instagram/weekly/{year}/week_{week_of_year}"
            elif storage_option == 'month':
                # instagram/monthly/2025/03/player_game_bar_20250115_143022.png
                folder_path = f"instagram/monthly/{year}/{month}"
            else:
                # default: 'game' — instagram/games/{game}/{installment}/{mode}/
                # Installment and mode segments are only added when non-null and non-trivial.
                _skip_mode = {'main', 'n/a', 'none', '-', ''}
                path_parts = [f"instagram/games/{safe_game}"]
                if game_installment and game_installment.strip():
                    path_parts.append(sanitize_filename(game_installment))
                if game_mode and game_mode.strip().lower() not in _skip_mode:
                    path_parts.append(sanitize_filename(game_mode))
                folder_path = '/'.join(path_parts)
            filename = f"{safe_player}_{safe_game}_{chart_type}_{timestamp}.png"

        else:
            # Fallback to generic path
            folder_path = f"charts/{platform}/{year}/{month}"
            filename = f"{safe_player}_{safe_game}_{chart_type}_{timestamp}.png"
        
        full_path = f"{folder_path}/{filename}"
        
        # Create blob and upload
        blob = bucket.blob(full_path)
        image_buffer.seek(0)  # Reset buffer position
        blob.upload_from_file(image_buffer, content_type='image/png')
        
        # Make public
        blob.make_public()
        
        public_url = blob.public_url
        print(f"✅ Chart uploaded: {full_path}")
        print(f"   Platform: {platform}")
        print(f"   URL: {public_url}")
        
        return public_url
        
    except Exception as e:
        print(f"❌ Failed to upload to GCS: {e}")
        return None


def upload_interactive_chart_to_gcs(html_bytes, player_name, game_name, game_installment=None):
    """Upload an interactive Plotly HTML chart to GCS using a fixed filename.

    The file is overwritten on every stat submission — no accumulation over time.
    Fixed path: twitter/interactive/{player_slug}_{game_slug}.html

    Args:
        html_bytes: UTF-8 encoded HTML from generate_interactive_chart()
        player_name, game_name, game_installment: used to build the filename

    Returns:
        str: Public URL, or None if upload failed
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    if not bucket_name:
        print("❌ GCS_BUCKET_NAME not set")
        return None

    client = get_gcs_client()
    if not client:
        return None

    def _slug(s):
        return s.lower().replace(' ', '_').replace(':', '').replace('/', '_') if s else ''

    game_slug = _slug(game_name)
    if game_installment:
        game_slug += f"_{_slug(game_installment)}"
    player_slug = _slug(player_name)

    full_path = f"twitter/interactive/{player_slug}_{game_slug}.html"

    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(full_path)
        blob.upload_from_string(html_bytes, content_type='text/html; charset=utf-8')
        blob.make_public()
        public_url = blob.public_url
        print(f"✅ Interactive chart uploaded (overwrite): {full_path}")
        print(f"   URL: {public_url}")
        return public_url
    except Exception as e:
        print(f"❌ Failed to upload interactive chart: {e}")
        return None


def upload_instagram_poster_to_gcs(image_buffer, player_name, game_name, post_type='daily'):
    """
    Upload Instagram portrait poster (1080x1440) to Google Cloud Storage.
    Organized by year/month/week for easy searching and carousel compilation.
    
    Folder structure: instagram/posters/YYYY/MM/WEEK_X/
    
    Args:
        image_buffer: BytesIO object containing PNG image (1080x1440)
        player_name: str (sanitized for filename)
        game_name: str (sanitized for filename)
        post_type: str ('daily', 'recent', 'historical', 'multi_game')
    
    Returns:
        str: Public URL of uploaded image, or None if failed
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    
    if not bucket_name:
        print("❌ GCS_BUCKET_NAME not set in environment variables")
        return None
    
    client = get_gcs_client()
    if not client:
        return None
    
    try:
        bucket = client.bucket(bucket_name)
        
        # Generate organized path with year/month/week
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        week_of_month = (now.day - 1) // 7 + 1  # Week 1-5 within month
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        
        safe_player = sanitize_filename(player_name)
        safe_game = sanitize_filename(game_name)
        
        # Folder structure: instagram/posters/2026/02/week_1/
        folder_path = f"instagram/posters/{year}/{month}/week_{week_of_month}"
        
        # Filename: player_game_posttype_timestamp.png
        # Example: bol_call_of_duty_daily_20260203_210000.png
        filename = f"{safe_player}_{safe_game}_{post_type}_{timestamp}.png"
        
        full_path = f"{folder_path}/{filename}"
        
        # Create blob and upload
        blob = bucket.blob(full_path)
        image_buffer.seek(0)  # Reset buffer position
        blob.upload_from_file(image_buffer, content_type='image/png')
        
        # Make public
        blob.make_public()
        
        public_url = blob.public_url
        print(f"✅ Instagram poster uploaded: {full_path}")
        print(f"   Type: {post_type}")
        print(f"   Week: {week_of_month} of {month}/{year}")
        print(f"   URL: {public_url}")
        
        return public_url
        
    except Exception as e:
        print(f"❌ Failed to upload Instagram poster to GCS: {e}")
        return None


def list_instagram_posters_by_week(year, month, week_of_month):
    """
    List all Instagram portrait posters for a specific week within a month.
    Useful for reviewing weekly posts or creating compilations.
    
    Args:
        year: int (e.g., 2026)
        month: int (1-12)
        week_of_month: int (1-5, week within the month)
    
    Returns:
        list of dicts with image info
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return []
    
    try:
        bucket = client.bucket(bucket_name)
        
        # Build prefix for specific week
        month_str = f"{month:02d}"
        prefix = f"instagram/posters/{year}/{month_str}/week_{week_of_month}/"
        
        blobs = bucket.list_blobs(prefix=prefix)
        
        week_posters = []
        for blob in blobs:
            week_posters.append({
                'name': blob.name,
                'url': blob.public_url,
                'created': blob.time_created.replace(tzinfo=None),
                'size_mb': round(blob.size / 1024 / 1024, 2),
                'download_url': f"https://storage.googleapis.com/{bucket_name}/{blob.name}",
                'post_type': extract_post_type_from_filename(blob.name)
            })
        
        # Sort by creation date
        week_posters.sort(key=lambda x: x['created'])
        
        print(f"📊 {year}-{month_str} Week {week_of_month}: Found {len(week_posters)} Instagram posters")
        return week_posters
        
    except Exception as e:
        print(f"❌ Failed to list weekly posters: {e}")
        return []


def list_instagram_posters_by_month(year, month):
    """
    List all Instagram portrait posters for an entire month (all weeks).
    
    Args:
        year: int (e.g., 2026)
        month: int (1-12)
    
    Returns:
        dict with weeks as keys and lists of image info as values
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return {}
    
    try:
        bucket = client.bucket(bucket_name)
        
        # Build prefix for entire month
        month_str = f"{month:02d}"
        prefix = f"instagram/posters/{year}/{month_str}/"
        
        blobs = bucket.list_blobs(prefix=prefix)
        
        # Organize by week
        month_posters = {}
        for blob in blobs:
            # Extract week number from path
            # Path: instagram/posters/2026/02/week_1/filename.png
            path_parts = blob.name.split('/')
            if len(path_parts) >= 5 and 'week_' in path_parts[4]:
                week_str = path_parts[4]  # e.g., "week_1"
                
                if week_str not in month_posters:
                    month_posters[week_str] = []
                
                month_posters[week_str].append({
                    'name': blob.name,
                    'url': blob.public_url,
                    'created': blob.time_created.replace(tzinfo=None),
                    'size_mb': round(blob.size / 1024 / 1024, 2),
                    'post_type': extract_post_type_from_filename(blob.name)
                })
        
        # Sort each week by creation date
        for week in month_posters:
            month_posters[week].sort(key=lambda x: x['created'])
        
        total_posters = sum(len(posters) for posters in month_posters.values())
        print(f"📊 {year}-{month_str}: Found {total_posters} posters across {len(month_posters)} weeks")
        return month_posters
        
    except Exception as e:
        print(f"❌ Failed to list monthly posters: {e}")
        return {}


def extract_post_type_from_filename(filename):
    """
    Extract post type from Instagram poster filename.
    Example: bol_call_of_duty_daily_20260203_210000.png → 'daily'
    """
    try:
        basename = os.path.basename(filename)
        parts = basename.split('_')
        # Format: player_game_posttype_timestamp.png
        # Find the part before timestamp (which is YYYYMMDD_HHMMSS)
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) == 8:  # Found timestamp date
                if i > 0:
                    return parts[i-1]  # Return the part before timestamp
        return 'unknown'
    except:
        return 'unknown'


def list_instagram_images_by_week(year, week_number):
    """
    List all Instagram images for a specific week.
    Useful for creating weekly compilation reels.
    
    Args:
        year: int (e.g., 2025)
        week_number: int (1-52)
    
    Returns:
        list of dicts with image info
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return []
    
    try:
        from datetime import datetime, timedelta
        bucket = client.bucket(bucket_name)
        
        # Calculate date range for the week
        jan_1 = datetime(year, 1, 1)
        week_start = jan_1 + timedelta(weeks=week_number - 1)
        week_end = week_start + timedelta(days=7)
        
        # List all Instagram images
        prefix = "instagram/games/"
        blobs = bucket.list_blobs(prefix=prefix)
        
        week_images = []
        for blob in blobs:
            # Check if image falls within week
            created = blob.time_created.replace(tzinfo=None)
            if week_start <= created < week_end:
                week_images.append({
                    'name': blob.name,
                    'url': blob.public_url,
                    'created': created,
                    'size_mb': round(blob.size / 1024 / 1024, 2),
                    'game': extract_game_from_path(blob.name)
                })
        
        # Sort by creation date
        week_images.sort(key=lambda x: x['created'])
        
        print(f"📊 Week {week_number}, {year}: Found {len(week_images)} Instagram images")
        return week_images
        
    except Exception as e:
        print(f"❌ Failed to list weekly images: {e}")
        return []


def list_instagram_images_by_game(game_name):
    """
    List all Instagram images for a specific game.
    Useful for creating game-specific compilation reels.
    
    Args:
        game_name: str (game name, will be sanitized)
    
    Returns:
        list of dicts with image info
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return []
    
    try:
        bucket = client.bucket(bucket_name)
        
        safe_game = sanitize_filename(game_name)
        prefix = f"instagram/games/{safe_game}/"
        
        blobs = bucket.list_blobs(prefix=prefix)
        
        game_images = []
        for blob in blobs:
            game_images.append({
                'name': blob.name,
                'url': blob.public_url,
                'created': blob.time_created.replace(tzinfo=None),
                'size_mb': round(blob.size / 1024 / 1024, 2),
                'download_url': f"https://storage.googleapis.com/{bucket_name}/{blob.name}"
            })
        
        # Sort by creation date (newest first)
        game_images.sort(key=lambda x: x['created'], reverse=True)
        
        print(f"🎮 {game_name}: Found {len(game_images)} Instagram images")
        return game_images
        
    except Exception as e:
        print(f"❌ Failed to list game images: {e}")
        return []


def download_instagram_images(image_list, output_dir='./instagram_downloads'):
    """
    Download a list of Instagram images for compilation.
    
    Args:
        image_list: list of dicts from list_instagram_images_by_week or list_instagram_images_by_game
        output_dir: str (local directory to save images)
    
    Returns:
        list of local file paths
    """
    import os
    import requests
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded_files = []
    
    for i, img in enumerate(image_list, 1):
        try:
            # Download image
            response = requests.get(img['url'], timeout=30)
            response.raise_for_status()
            
            # Generate local filename
            filename = os.path.basename(img['name'])
            local_path = os.path.join(output_dir, filename)
            
            # Save to disk
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            downloaded_files.append(local_path)
            print(f"✅ Downloaded ({i}/{len(image_list)}): {filename}")
            
        except Exception as e:
            print(f"❌ Failed to download {img['name']}: {e}")
    
    print(f"\n✅ Downloaded {len(downloaded_files)}/{len(image_list)} images to {output_dir}")
    return downloaded_files


def get_storage_summary():
    """
    Get organized summary of storage usage by platform.
    
    Returns:
        dict with platform-specific stats
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return None
    
    try:
        bucket = client.bucket(bucket_name)
        
        summary = {
            'twitter': {'count': 0, 'size_mb': 0},
            'instagram': {'count': 0, 'size_mb': 0},
            'total': {'count': 0, 'size_mb': 0}
        }
        
        # Count Twitter images
        twitter_blobs = bucket.list_blobs(prefix='twitter/')
        for blob in twitter_blobs:
            summary['twitter']['count'] += 1
            summary['twitter']['size_mb'] += blob.size / 1024 / 1024
        
        # Count Instagram images
        instagram_blobs = bucket.list_blobs(prefix='instagram/')
        for blob in instagram_blobs:
            summary['instagram']['count'] += 1
            summary['instagram']['size_mb'] += blob.size / 1024 / 1024
        
        # Calculate totals
        summary['total']['count'] = summary['twitter']['count'] + summary['instagram']['count']
        summary['total']['size_mb'] = summary['twitter']['size_mb'] + summary['instagram']['size_mb']
        
        # Round sizes
        for platform in summary:
            summary[platform]['size_mb'] = round(summary[platform]['size_mb'], 2)
        
        print(f"📊 Storage Summary:")
        print(f"   Twitter: {summary['twitter']['count']} images, {summary['twitter']['size_mb']} MB")
        print(f"   Instagram: {summary['instagram']['count']} images, {summary['instagram']['size_mb']} MB")
        print(f"   Total: {summary['total']['count']} images, {summary['total']['size_mb']} MB")
        
        return summary
        
    except Exception as e:
        print(f"❌ Failed to get storage summary: {e}")
        return None


def extract_game_from_path(path):
    """Extract game name from GCS path."""
    try:
        if 'instagram/games/' in path:
            game_part = path.split('instagram/games/')[1]
            game_name = game_part.split('/')[0]
            return game_name.replace('_', ' ').title()
        return 'Unknown'
    except:
        return 'Unknown'


def sanitize_filename(name):
    """
    Sanitize string for use in filenames.
    Removes special characters and spaces.
    """
    import re
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Keep only alphanumeric, underscore, hyphen
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    # Limit length
    return name[:50].lower()


def smart_cleanup(warning_gb=4.0, target_gb=3.5, min_days_old=90):
    """
    Storage-aware cleanup: only deletes when approaching the 5 GB free-tier cap.

    Strategy:
      - If total usage < warning_gb  → do nothing (safe zone)
      - If total usage >= warning_gb → delete oldest files across all platforms
        until usage drops to target_gb, but never delete files newer than min_days_old days.

    Args:
        warning_gb:   float — trigger cleanup above this threshold (default 4.0 GB)
        target_gb:    float — delete until usage reaches this level (default 3.5 GB)
        min_days_old: int   — never delete files younger than this (default 90 days)

    Returns:
        dict with action taken and stats
    """
    from datetime import timedelta

    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()

    if not client or not bucket_name:
        print("❌ GCS not configured")
        return {'action': 'skipped', 'reason': 'GCS not configured'}

    try:
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())

        total_bytes = sum(b.size for b in blobs)
        total_gb = total_bytes / (1024 ** 3)

        print(f"📊 Current GCS usage: {total_gb:.3f} GB / 5.0 GB free tier")

        if total_gb < warning_gb:
            print(f"✅ Storage safe ({total_gb:.3f} GB < {warning_gb} GB threshold) — no cleanup needed")
            return {'action': 'none', 'usage_gb': round(total_gb, 3)}

        print(f"⚠️ Approaching free-tier cap — targeting {target_gb} GB")

        cutoff = datetime.now() - timedelta(days=min_days_old)
        # Sort oldest first so we delete least-recent content
        eligible = sorted(
            [b for b in blobs if b.time_created.replace(tzinfo=None) < cutoff],
            key=lambda b: b.time_created
        )

        deleted_count = 0
        freed_bytes = 0

        for blob in eligible:
            if total_bytes - freed_bytes <= target_gb * (1024 ** 3):
                break
            freed_bytes += blob.size
            blob.delete()
            deleted_count += 1
            print(f"🗑️ Deleted: {blob.name} ({blob.size / 1024 / 1024:.2f} MB)")

        remaining_gb = (total_bytes - freed_bytes) / (1024 ** 3)
        print(f"✅ Cleanup done — freed {freed_bytes / 1024 / 1024:.1f} MB, now at {remaining_gb:.3f} GB")

        return {
            'action': 'cleaned',
            'deleted': deleted_count,
            'freed_mb': round(freed_bytes / 1024 / 1024, 2),
            'usage_before_gb': round(total_gb, 3),
            'usage_after_gb': round(remaining_gb, 3)
        }

    except Exception as e:
        print(f"❌ Smart cleanup failed: {e}")
        return {'action': 'error', 'error': str(e)}


def cleanup_old_images(days_old=365, platform=None):
    """
    Delete images older than specified days to manage storage costs.
    Can target specific platform or all images.
    
    Args:
        days_old: int (delete images older than this many days, default 1 year)
        platform: str ('twitter', 'instagram', or None for all)
    
    Returns:
        dict with cleanup stats
    """
    from datetime import timedelta
    
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        print("❌ Cannot perform cleanup: GCS not configured")
        return {'deleted': 0, 'error': 'GCS not configured'}
    
    try:
        bucket = client.bucket(bucket_name)
        
        # Determine prefix based on platform
        if platform == 'twitter':
            prefix = 'twitter/'
        elif platform == 'instagram':
            prefix = 'instagram/'
        else:
            prefix = ''  # All images
        
        blobs = bucket.list_blobs(prefix=prefix)
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        total_size_freed = 0
        
        for blob in blobs:
            if blob.time_created.replace(tzinfo=None) < cutoff_date:
                size = blob.size
                blob.delete()
                deleted_count += 1
                total_size_freed += size
                print(f"🗑️ Deleted: {blob.name} ({size / 1024 / 1024:.2f} MB)")
        
        size_freed_mb = total_size_freed / 1024 / 1024
        print(f"✅ Cleanup complete ({platform or 'all platforms'})")
        print(f"   Deleted: {deleted_count} images")
        print(f"   Freed: {size_freed_mb:.2f} MB")
        
        return {
            'deleted': deleted_count,
            'size_freed_mb': round(size_freed_mb, 2),
            'platform': platform or 'all',
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return {'deleted': 0, 'error': str(e)}