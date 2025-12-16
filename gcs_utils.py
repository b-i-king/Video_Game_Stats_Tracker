"""
Google Cloud Storage utilities for uploading social media images
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


def upload_chart_to_gcs(image_buffer, player_name, game_name, chart_type='bar'):
    """
    Upload chart image to Google Cloud Storage and return public URL.
    
    Args:
        image_buffer: BytesIO object containing PNG image
        player_name: str (sanitized for filename)
        game_name: str (sanitized for filename)
        chart_type: str ('bar' or 'line')
    
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
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_player = sanitize_filename(player_name)
        safe_game = sanitize_filename(game_name)
        filename = f"charts/{safe_player}_{safe_game}_{chart_type}_{timestamp}.png"
        
        # Create blob and upload
        blob = bucket.blob(filename)
        image_buffer.seek(0)  # Reset buffer position
        blob.upload_from_file(image_buffer, content_type='image/png')
        
        # Make public
        blob.make_public()
        
        public_url = blob.public_url
        print(f"✅ Chart uploaded successfully: {public_url}")
        
        return public_url
        
    except Exception as e:
        print(f"❌ Failed to upload to GCS: {e}")
        return None


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
    return name[:50]


def cleanup_old_images(days_old=365):
    """
    Delete images older than specified days to manage storage costs.
    Run this as a periodic cleanup job (e.g., monthly via cron or Render scheduled job).
    
    Args:
        days_old: int (delete images older than this many days, default 1 year)
    
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
        blobs = bucket.list_blobs(prefix='charts/')
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        total_size_freed = 0
        
        for blob in blobs:
            if blob.time_created.replace(tzinfo=None) < cutoff_date:
                size = blob.size
                blob.delete()
                deleted_count += 1
                total_size_freed += size
                print(f"🗑️ Deleted old image: {blob.name} ({size / 1024 / 1024:.2f} MB)")
        
        size_freed_mb = total_size_freed / 1024 / 1024
        print(f"✅ Cleanup complete. Deleted {deleted_count} images, freed {size_freed_mb:.2f} MB")
        
        return {
            'deleted': deleted_count,
            'size_freed_mb': round(size_freed_mb, 2),
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return {'deleted': 0, 'error': str(e)}


def get_storage_stats():
    """
    Get current storage usage statistics.
    Useful for monitoring how close you are to limits.
    
    Returns:
        dict with storage stats
    """
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    client = get_gcs_client()
    
    if not client or not bucket_name:
        return None
    
    try:
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix='charts/'))
        
        total_size = sum(blob.size for blob in blobs)
        total_count = len(blobs)
        total_size_mb = total_size / 1024 / 1024
        
        # Group by month
        from collections import defaultdict
        monthly_counts = defaultdict(int)
        for blob in blobs:
            month_key = blob.time_created.strftime('%Y-%m')
            monthly_counts[month_key] += 1
        
        stats = {
            'total_images': total_count,
            'total_size_mb': round(total_size_mb, 2),
            'free_tier_remaining_gb': round(5 - (total_size_mb / 1024), 2),
            'monthly_breakdown': dict(monthly_counts)
        }
        
        print(f"📊 Storage Stats:")
        print(f"   Total images: {stats['total_images']}")
        print(f"   Total size: {stats['total_size_mb']:.2f} MB")
        print(f"   Free tier remaining: {stats['free_tier_remaining_gb']:.2f} GB")
        
        return stats
        
    except Exception as e:
        print(f"❌ Failed to get storage stats: {e}")
        return None