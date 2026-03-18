# Utils

Shared utility modules used by both the Lambda functions and local development tools.

## Files

| File | Purpose |
|------|---------|
| `chart_utils.py` | Chart generation (bar charts, line charts), formatting helpers, log scale detection, font loading |
| `gcs_utils.py` | Google Cloud Storage upload/download for chart images and Instagram posters |
| `game_handles_utils.py` | Social media handles and hashtags per game, per platform |
| `holiday_themes.py` | Color themes for holidays and heritage months |
| `app_utils.py` | Shared helpers for the Streamlit and Flask apps (API calls, session state helpers, business hours detection) |
| `ifttt_utils.py` | IFTTT webhook integration and caption generation |
| `queue_utils.py` | Post queue CRUD helpers backed by a persistent Postgres database (Neon) |
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

### queue_utils.py

| Variable | Description | Example |
|----------|-------------|---------|
| `QUEUE_DATABASE_URL` | PostgreSQL connection string for the post queue database | `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require` |

**Recommended provider: [Neon](https://neon.tech)** — free tier, no expiration, serverless Postgres.

> **Why not Render Postgres?** Render's free Postgres tier deletes the database after 90 days. Neon's free tier has no expiration and works identically since both use a standard `postgresql://` connection string.

#### Neon Setup
1. Sign up at [neon.tech](https://neon.tech) (free)
2. Create a new project named `game-tracker-queue`
3. Copy the **Connection string** from the dashboard
4. Add it as `QUEUE_DATABASE_URL` in your Render web service environment variables
5. On first app start, `flask_app.py` calls `ensure_post_queue_table()` which creates the table automatically

#### Queue Table Schema

```sql
CREATE TABLE IF NOT EXISTS post_queue (
    queue_id     SERIAL PRIMARY KEY,
    player_id    VARCHAR(50),
    platform     VARCHAR(20),        -- 'twitter' | 'instagram'
    image_url    VARCHAR(1000),
    caption      TEXT,
    status       VARCHAR(20) DEFAULT 'pending',  -- pending | processing | sent | failed
    scheduled_at TIMESTAMP,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

#### Queue Lifecycle

```
Form submit (Queue Mode ON)
    → enqueue_post()          status: pending
    → get_oldest_pending()    status: processing  (atomic claim)
    → trigger_ifttt_post()
        success → mark_status('sent')
        failure → mark_status('failed')

Housekeeping (runs on every /api/process_queue call):
    → reset_stale_processing(minutes=10)   resets stuck 'processing' rows
    → purge_old_sent(days=7)               deletes sent rows older than 7 days
```

### holiday_themes.py

No environment variables required. Themes are date-driven automatically.

### game_handles_utils.py

No environment variables required. Handles and hashtags are hardcoded per game.

---

## Queue Mode (Blended Auto + Manual)

`queue_utils.py` works alongside `app_utils.is_business_hours_pst()` to implement a post scheduling system:

- **Auto ON**: Weekdays 9am–5pm PST (excluding US federal holidays) → posts are queued, not sent immediately
- **Auto OFF**: Weekends, US holidays, after 5pm PST → posts sent immediately via IFTTT
- **Manual override**: Toggle in the Streamlit sidebar overrides auto-detection at any time

Posts queued during work hours are released at 5pm PST in 30-minute increments via a **Render cron job** that calls `/api/process_queue`.

#### Render Cron Schedule

```
Service type:  Cron Job
Schedule:      */30 0-6 * * 2-6   (covers 5pm–9:30pm PST year-round in UTC)
Command:       python -c "import requests, os; r = requests.post(
                   os.environ['WEB_SERVICE_URL'] + '/api/process_queue',
                   headers={'X-Cron-Secret': os.environ['CRON_SECRET']},
                   timeout=30); print(r.status_code, r.text)"
```

Environment variables needed on the cron service:

| Variable | Value |
|----------|-------|
| `WEB_SERVICE_URL` | `https://video-game-stats-api.onrender.com` |
| `CRON_SECRET` | Same secret set on the web service |

The `CRON_SECRET` must also be set on the **web service** — it authenticates the cron job's POST to `/api/process_queue` and rejects unauthorized calls.

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
