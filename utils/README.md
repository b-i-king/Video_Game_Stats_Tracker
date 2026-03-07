# Utils

Shared utility modules used by both the Lambda functions and local development tools.

## Files

| File | Purpose |
|------|---------|
| `chart_utils.py` | Chart formatting helpers (abbreviations, number formatting, log scale detection, font loading) |
| `gcs_utils.py` | Google Cloud Storage upload/download for chart images and Instagram posters |
| `game_handles_utils.py` | Social media handles and hashtags per game, per platform |
| `holiday_themes.py` | Color themes for holidays and heritage months |
| `app_utils.py` | Shared helpers for the Streamlit and Flask apps |
| `ifttt_utils.py` | IFTTT webhook integration |
| `fonts/` | Fira Code font files (TTF) used in chart generation |

---

## Setup

### Local Development

These modules are imported directly. No extra setup needed beyond installing `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Lambda Deployment

`utils/` is included in the Lambda code package automatically by `build_code_only.ps1`. No separate step needed.

---

## Environment Variables

### gcs_utils.py

| Variable | Description | Example |
|----------|-------------|---------|
| `GCS_BUCKET_NAME` | GCS bucket name for image storage | `my-game-stats-images` |
| `GCS_CREDENTIALS_JSON` | Full JSON string of GCS service account key | `{"type": "service_account", ...}` |

To get `GCS_CREDENTIALS_JSON`:
1. Google Cloud Console → IAM & Admin → Service Accounts
2. Select your service account → Keys → Add Key → JSON
3. Paste the entire file contents as the env var value

### holiday_themes.py

No environment variables required. Themes are date-driven automatically.

### game_handles_utils.py

No environment variables required. Handles and hashtags are hardcoded per game.

---

## GCS Folder Structure

Images uploaded via `gcs_utils.py` follow this layout in the bucket:

```
my-bucket/
├── twitter/
│   └── YYYY/MM/
│       └── player_game_bar_20260306_210000.png
└── instagram/
    ├── games/
    │   └── call_of_duty/
    │       └── player_bar_20260306_210000.png
    └── posters/
        └── YYYY/MM/week_N/
            └── player_game_historical_20260306_210000.png
```

---

## Adding a New Game to Hashtags/Handles

Edit `game_handles_utils.py` and add an entry to the `GAME_DATA` dictionary:

```python
"Your Game Name": {
    "instagram": "@yourgamehandle",
    "twitter": "@yourgamehandle",
    "hashtags": {
        "instagram": ["#yourgame", "#gaming"],
        "twitter": ["#yourgame", "#gaming"]
    }
}
```
