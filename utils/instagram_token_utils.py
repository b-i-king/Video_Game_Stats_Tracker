"""
Instagram long-lived access token refresh utilities.

Long-lived tokens expire every 60 days. This module is called by the GitHub
Actions workflow (.github/workflows/refresh_instagram_token.yml) to refresh
the token automatically every month and write the new value back to AWS
Secrets Manager. Lambda reads the token from Secrets Manager at runtime, so
it picks up the new value automatically on next invocation — no redeployment
needed.

Manual token check:
  https://developers.facebook.com/tools/debug/accesstoken/

Instagram token refresh API reference:
  https://developers.facebook.com/docs/instagram-platform/reference/access_token/
"""

import json

import boto3
import requests

SECRET_NAME = "instagram-poster/instagram"
AWS_REGION = "us-west-1"
REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


def get_current_secret() -> dict:
    """Read the full Instagram secret from AWS Secrets Manager.

    Returns the parsed JSON dict, which includes 'access_token' and 'account_id'.
    """
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(response["SecretString"])


def refresh_token(current_token: str) -> dict:
    """Call the Instagram Graph API token refresh endpoint.

    Returns the API response dict containing 'access_token' and 'expires_in'
    (seconds). Raises requests.HTTPError on a non-2xx response so the workflow
    fails visibly rather than silently writing a bad token.
    """
    response = requests.get(
        REFRESH_URL,
        params={
            "grant_type": "ig_refresh_token",
            "access_token": current_token,
        },
        timeout=15,
    )
    if not response.ok:
        try:
            error_body = response.json()
        except Exception:
            error_body = response.text
        print(f"❌ Instagram API error ({response.status_code}): {error_body}")
        response.raise_for_status()
    return response.json()


def update_secret(new_token: str) -> None:
    """Overwrite only the access_token field, preserving account_id and any other fields."""
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    current = json.loads(
        client.get_secret_value(SecretId=SECRET_NAME)["SecretString"]
    )
    current["access_token"] = new_token
    client.update_secret(
        SecretId=SECRET_NAME,
        SecretString=json.dumps(current),
    )


def run_token_refresh() -> None:
    """End-to-end refresh: read current token → call refresh API → write new token.

    Called directly by the GitHub Actions workflow. Prints progress so the
    Actions log shows exactly what happened.
    """
    print("🔐 Reading current token from Secrets Manager...")
    secret = get_current_secret()
    current_token = secret["access_token"]
    print(f"   Current token suffix: ...{current_token[-8:]}")

    print("🔄 Calling Instagram token refresh endpoint...")
    result = refresh_token(current_token)
    new_token = result["access_token"]
    expires_in_days = result.get("expires_in", 5184000) // 86400
    print(f"   New token suffix:     ...{new_token[-8:]}")
    print(f"   Expires in:           ~{expires_in_days} days")

    print("💾 Writing new token to Secrets Manager...")
    update_secret(new_token)
    print("✅ Token refreshed and saved. Lambda will pick it up on next invocation.")


if __name__ == "__main__":
    run_token_refresh()
