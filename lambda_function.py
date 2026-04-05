"""
Unified AWS Lambda handler for Instagram Auto-Poster
With AWS Secrets Manager integration for secure credential management
Can run in two modes:
1. FETCH_MODE: Get data from Redshift, send to SQS (runs in VPC)
2. POST_MODE: Receive from SQS, post to Instagram (no VPC needed)
"""

import json
import os
import logging
import boto3
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
MODE = os.environ.get('MODE')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-1')

# AWS clients (lazy init)
sqs_client = None
sns_client = None
secrets_client = None

# Cache for secrets (avoid repeated API calls)
secrets_cache = {}


def get_sqs_client():
    """Get or create SQS client"""
    global sqs_client
    if sqs_client is None:
        sqs_client = boto3.client('sqs')
    return sqs_client


def get_sns_client():
    """Get or create SNS client"""
    global sns_client
    if sns_client is None:
        sns_client = boto3.client('sns')
    return sns_client


def get_secrets_client():
    """Get or create Secrets Manager client"""
    global secrets_client
    if secrets_client is None:
        secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)
    return secrets_client


def get_secret(secret_name):
    """
    Retrieve secret from AWS Secrets Manager (with caching).

    Args:
        secret_name: Name of the secret in Secrets Manager

    Returns:
        dict: Secret value as dictionary
    """
    # Check cache first
    if secret_name in secrets_cache:
        logger.info(f"Using cached secret: {secret_name}")
        return secrets_cache[secret_name]

    try:
        logger.info(f"Retrieving secret from Secrets Manager: {secret_name}")
        secrets = get_secrets_client()
        response = secrets.get_secret_value(SecretId=secret_name)

        # Parse JSON secret
        secret_value = json.loads(response['SecretString'])

        # Cache it
        secrets_cache[secret_name] = secret_value
        logger.info(f"Secret retrieved and cached: {secret_name}")

        return secret_value

    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise Exception(f"Failed to retrieve secret {secret_name}: {str(e)}")


def send_notification(subject, message, success=True):
    """Send SNS notification."""
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not set, skipping notification")
        return

    try:
        icon = "✅" if success else "❌"
        full_subject = f"{icon} {subject}"

        sns = get_sns_client()
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=full_subject[:100],
            Message=message
        )

        logger.info(f"📧 Notification sent: MessageId={response['MessageId']}")

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def detect_mode(event):
    """Detect which mode to run based on event type."""
    if MODE:
        logger.info(f"🔧 Mode override from environment: {MODE}")
        return MODE.upper()

    if 'Records' in event:
        if event['Records'][0].get('eventSource') == 'aws:sqs':
            logger.info("📥 Detected SQS event → POST mode")
            return 'POST'

    logger.info("📅 Detected EventBridge/manual event → FETCH mode")
    return 'FETCH'


def fetch_and_queue(event, context):
    """FETCH MODE: Query Redshift, create chart, upload to GCS, send URL to SQS."""
    logger.info("=" * 60)
    logger.info("🔄 FETCH MODE: Fetching data from Redshift")
    logger.info("=" * 60)

    if not SQS_QUEUE_URL:
        raise Exception("SQS_QUEUE_URL environment variable not set")

    logger.info("🔐 Using DB credentials from Lambda environment variables")

    from instagram_poster import get_queue_result_for_today

    try:
        result = get_queue_result_for_today()

        if result is None:
            logger.info("📵 No post scheduled for today")
            send_notification(
                subject="Instagram Post Skipped",
                message="No post scheduled for today (Sunday).",
                success=True
            )
            return {
                'statusCode': 200,
                'body': json.dumps({'mode': 'FETCH', 'message': 'No post scheduled', 'posted': False})
            }

        caption = result['caption']
        post_type = result['post_type']
        game_name = result['game']
        player_name = result['player']
        content_hash = result.get('content_hash')
        gcs_url = result.get('gcs_url')

        logger.info(f"📊 Post type: {post_type}")
        logger.info(f"🎮 Game: {game_name}")
        logger.info(f"👤 Player: {player_name}")

        if not gcs_url:
            logger.error("❌ GCS upload failed after all retries — skipping post to avoid crash loop")
            send_notification(
                subject=f"Instagram Post Skipped - GCS Unavailable ({post_type.title()})",
                message=f"""Instagram post was skipped because GCS upload failed after all retries.

Post that was ready to send:
- Type: {post_type.title()}
- Game: {game_name}
- Player: {player_name}

No action needed unless this recurs. GCS may have had a transient outage.
Check https://status.cloud.google.com if the issue persists.

Request ID: {context.aws_request_id}
Timestamp: {datetime.now().isoformat()}
""",
                success=False
            )
            return {
                'statusCode': 200,
                'body': json.dumps({'mode': 'FETCH', 'message': 'Skipped — GCS unavailable', 'posted': False})
            }

        logger.info(f"🖼️ Image URL: {gcs_url}")

        message_body = {
            'image_url': gcs_url,
            'caption': caption,
            'post_type': post_type,
            'game': game_name,
            'player': player_name,
            'content_hash': content_hash
        }

        message_json = json.dumps(message_body)
        message_size = len(message_json)

        logger.info(f"📦 Message size: {message_size / 1024:.2f} KB")

        # Send to SQS
        logger.info(f"📤 Sending to SQS...")
        sqs = get_sqs_client()
        response = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_json
        )

        logger.info(f"✅ Sent to SQS: MessageId={response['MessageId']}")

        notification_message = f"""Instagram post data prepared successfully!

Post Details:
- Type: {post_type.title()}
- Game: {game_name}
- Player: {player_name}
- Image URL: {gcs_url}
- SQS Message ID: {response['MessageId']}

Request ID: {context.aws_request_id}
Timestamp: {datetime.now().isoformat()}
"""

        send_notification(
            subject=f"Instagram Post Queued - {post_type.title()}",
            message=notification_message,
            success=True
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'mode': 'FETCH',
                'message': 'Data queued successfully',
                'messageId': response['MessageId'],
                'post_type': post_type
            })
        }

    except Exception as e:
        logger.error(f"❌ FETCH mode error: {e}")
        import traceback
        logger.error(traceback.format_exc())

        error_message = f"""Instagram post preparation FAILED!

Error: {str(e)}

Request ID: {context.aws_request_id}
Timestamp: {datetime.now().isoformat()}
"""

        send_notification(
            subject="Instagram Post FAILED - Data Fetch",
            message=error_message,
            success=False
        )

        raise


def post_to_instagram(image_url, caption):
    """Post image URL and caption to Instagram using Graph API."""
    import requests

    # Get Instagram credentials from Secrets Manager
    logger.info("🔐 Retrieving Instagram credentials from Secrets Manager...")
    instagram_secret = get_secret('instagram-poster/instagram')

    INSTAGRAM_ACCESS_TOKEN = instagram_secret['access_token']
    INSTAGRAM_ACCOUNT_ID = instagram_secret['account_id']

    try:
        logger.info("📤 Creating Instagram media container...")

        upload_url = f"https://graph.facebook.com/v24.0/{INSTAGRAM_ACCOUNT_ID}/media"
        data = {
            'image_url': image_url,
            'caption': caption,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }

        # Retry up to 3 times for transient Instagram API errors
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            response = requests.post(upload_url, data=data, timeout=30)
            response_data = response.json()
            if 'id' in response_data:
                break
            error = response_data.get('error', {})
            is_transient = error.get('is_transient', False)
            if is_transient and attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s
                logger.warning(f"⚠️ Transient error on attempt {attempt}/{max_retries}, retrying in {wait}s: {error}")
                time.sleep(wait)
            else:
                raise Exception(f"Failed to create container: {response_data}")

        media_id = response_data['id']
        logger.info(f"✅ Media container created: {media_id}")

        # Poll until Instagram finishes processing the image (error 2207027 if skipped)
        import time
        status_url = f"https://graph.facebook.com/v24.0/{media_id}"
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            time.sleep(5)
            status_resp = requests.get(
                status_url,
                params={'fields': 'status_code', 'access_token': INSTAGRAM_ACCESS_TOKEN},
                timeout=15
            )
            status_data = status_resp.json()
            status_code = status_data.get('status_code', 'UNKNOWN')
            logger.info(f"⏳ Container status ({attempt}/{max_attempts}): {status_code}")
            if status_code == 'FINISHED':
                break
            if status_code == 'ERROR':
                raise Exception(f"Instagram media processing failed: {status_data}")
        else:
            raise Exception(f"Instagram container not ready after {max_attempts * 5}s (last status: {status_code})")

        logger.info("📤 Publishing Instagram post...")

        publish_url = f"https://graph.facebook.com/v24.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        publish_data = {
            'creation_id': media_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }

        publish_response = requests.post(publish_url, data=publish_data, timeout=30)
        publish_result = publish_response.json()

        if 'id' in publish_result:
            logger.info(f"✅ Posted to Instagram: {publish_result['id']}")
            return True
        else:
            raise Exception(f"Publishing failed: {publish_result}")

    except Exception as e:
        logger.error(f"❌ Instagram posting error: {e}")
        raise


def receive_and_post(event, context):
    """POST MODE: Receive data from SQS and post to Instagram."""
    logger.info("=" * 60)
    logger.info("📤 POST MODE: Posting to Instagram")
    logger.info("=" * 60)

    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])

            image_url = message_body['image_url']
            caption = message_body['caption']
            post_type = message_body['post_type']
            game = message_body['game']
            player = message_body['player']
            content_hash = message_body.get('content_hash')

            logger.info(f"📊 Post type: {post_type}")
            logger.info(f"🎮 Game: {game}")
            logger.info(f"🖼️ Image URL: {image_url}")

            # Post to Instagram
            logger.info("📤 Posting to Instagram...")
            success = post_to_instagram(image_url, caption)

            if success:
                if content_hash:
                    try:
                        from instagram_poster import save_content_hash
                        save_content_hash(content_hash)
                        logger.info(f"✅ Content hash saved")
                    except Exception as hash_err:
                        logger.warning(f"⚠️ Could not save content hash (non-fatal): {hash_err}")

                logger.info("✅ Successfully posted to Instagram!")

                notification_message = f"""Instagram post published successfully! 🎉

Post Details:
- Type: {post_type.title()}
- Game: {game}
- Player: {player}
- Image URL: {image_url}

Security: Instagram credentials retrieved from Secrets Manager
Request ID: {context.aws_request_id}
Timestamp: {datetime.now().isoformat()}
"""

                send_notification(
                    subject=f"Instagram Posted - {post_type.title()}",
                    message=notification_message,
                    success=True
                )

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'mode': 'POST',
                        'message': 'Posted successfully',
                        'post_type': post_type
                    })
                }

        except Exception as e:
            logger.error(f"❌ POST mode error: {e}")
            import traceback
            logger.error(traceback.format_exc())

            error_message = f"""Instagram post publishing FAILED!

Error: {str(e)}

Request ID: {context.aws_request_id}
Timestamp: {datetime.now().isoformat()}
"""

            send_notification(
                subject="Instagram Post FAILED - Publishing",
                message=error_message,
                success=False
            )

            raise


def lambda_handler(event, context):
    """Unified AWS Lambda entry point."""
    logger.info("=" * 60)
    logger.info("🚀 Instagram Auto-Poster Lambda Started")
    logger.info("🔐 Using AWS Secrets Manager for credentials")
    logger.info("=" * 60)
    logger.info(f"Request ID: {context.aws_request_id}")
    logger.info(f"Function name: {context.function_name}")

    try:
        mode = detect_mode(event)

        if mode == 'FETCH':
            return fetch_and_queue(event, context)
        elif mode == 'POST':
            return receive_and_post(event, context)
        else:
            raise Exception(f"Unknown mode: {mode}")

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Lambda execution failed: {e}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())

        raise Exception(f"Instagram poster failed: {str(e)}")
