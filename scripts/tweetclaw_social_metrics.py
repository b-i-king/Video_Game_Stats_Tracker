"""Normalize TweetClaw and Xquik post exports into social metric CSV rows."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

TEXT_KEYS = ("text", "tweet_text", "full_text", "content", "caption", "message")
TIME_KEYS = ("created_at", "timestamp", "date", "posted_at")
URL_KEYS = ("url", "tweet_url", "link")
LIKE_KEYS = ("likes", "like_count", "favorite_count")
REPLY_KEYS = ("comments", "reply_count", "replies")
REPOST_KEYS = ("shares", "retweet_count", "repost_count")
VIEW_KEYS = ("views", "view_count", "impressions")

OUTPUT_FIELDS = (
    "created_at",
    "post_text",
    "post_url",
    "likes",
    "replies",
    "reposts",
    "views",
    "engagement_total",
    "engagement_rate",
)


def first_value(row: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def to_int(value: Any) -> int:
    try:
        return max(int(float(value)), 0)
    except (OverflowError, TypeError, ValueError):
        return 0


def dict_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [row for row in rows if isinstance(row, dict)]


def read_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return dict_rows(payload)
        if isinstance(payload, dict):
            for key in ("tweets", "data", "items", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return dict_rows(value)
    if suffix in {".jsonl", ".ndjson"}:
        payload = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return dict_rows(payload)
    raise ValueError("Input must be CSV, JSON, JSONL, or NDJSON.")


def normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    post_text = str(first_value(row, TEXT_KEYS)).strip()
    if not post_text:
        return None

    likes = to_int(first_value(row, LIKE_KEYS, 0))
    replies = to_int(first_value(row, REPLY_KEYS, 0))
    reposts = to_int(first_value(row, REPOST_KEYS, 0))
    views = to_int(first_value(row, VIEW_KEYS, 0))
    engagement_total = likes + replies + reposts
    engagement_rate = round(engagement_total / views, 4) if views > 0 else 0

    return {
        "created_at": first_value(row, TIME_KEYS),
        "post_text": post_text,
        "post_url": first_value(row, URL_KEYS),
        "likes": likes,
        "replies": replies,
        "reposts": reposts,
        "views": views,
        "engagement_total": engagement_total,
        "engagement_rate": engagement_rate,
    }


def write_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/tweetclaw_social_metrics.py <export> <output.csv>")
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    rows = [row for row in (normalize_row(row) for row in read_rows(input_path)) if row]
    if not rows:
        raise ValueError("No rows with post text were found.")

    write_rows(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
