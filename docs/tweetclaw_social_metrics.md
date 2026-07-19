# TweetClaw Social Metrics Import

Use `scripts/tweetclaw_social_metrics.py` to convert TweetClaw or Xquik
X/Twitter exports into a local CSV for social-performance review.

This is an offline utility. It does not post, queue posts, call deployment
services, or read runtime credentials.

## Supported Inputs

The converter accepts CSV, JSON, JSONL, and NDJSON files with common export
aliases:

| Output field | Accepted input aliases |
|---|---|
| `post_text` | `text`, `tweet_text`, `full_text`, `content`, `caption`, `message` |
| `created_at` | `created_at`, `timestamp`, `date`, `posted_at` |
| `post_url` | `url`, `tweet_url`, `link` |
| `likes` | `likes`, `like_count`, `favorite_count` |
| `replies` | `comments`, `reply_count`, `replies` |
| `reposts` | `shares`, `retweet_count`, `repost_count` |
| `views` | `views`, `view_count`, `impressions` |

Missing, invalid, and negative counts become `0`. Blank post text and non-object
JSONL rows are skipped.

## Usage

```bash
python scripts/tweetclaw_social_metrics.py \
  assets/social/tweetclaw-post-metrics.json \
  assets/social/tweetclaw-post-metrics.csv
```

The output includes:

- `engagement_total = likes + replies + reposts`
- `engagement_rate = engagement_total / views` when views are positive,
  otherwise `0`
- source URL and created time when present

## Review Workflow

1. Export post or monitor rows from TweetClaw or Xquik.
2. Run the converter locally.
3. Compare social metrics against generated chart captions and stream recaps.
4. Keep the CSV out of commits if it contains private account or player data.
