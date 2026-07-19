import json
import tempfile
import unittest
from pathlib import Path

from scripts.tweetclaw_social_metrics import normalize_row, read_rows


class TweetClawSocialMetricsTest(unittest.TestCase):
    def test_normalize_row_sanitizes_invalid_metrics(self):
        row = normalize_row(
            {
                "tweet_text": "A result",
                "like_count": -2,
                "reply_count": "invalid",
                "retweet_count": float("inf"),
                "view_count": 0,
            }
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["likes"], 0)
        self.assertEqual(row["replies"], 0)
        self.assertEqual(row["reposts"], 0)
        self.assertEqual(row["engagement_rate"], 0)

    def test_read_rows_skips_non_object_jsonl_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.jsonl"
            values = [{"text": "A result"}, [], None, "invalid"]
            path.write_text(
                "\n".join(json.dumps(value) for value in values),
                encoding="utf-8",
            )

            self.assertEqual(read_rows(path), [{"text": "A result"}])


if __name__ == "__main__":
    unittest.main()
