# Instagram Poster — Reference Guide

Covers the AWS Lambda poster, EventBridge schedule, token management, and planned expansions.

---

## Architecture Overview

```
EventBridge Rule(s)
      │
      ▼
AWS Lambda (instagram_poster.py)
      │
      ├── psycopg2 ──→ Supabase (fact.fact_game_stats, dim.*)
      ├── GCS        ──→ Google Cloud Storage (image backup)
      └── Instagram Graph API ──→ Post to Instagram
```

The Lambda runs fully standalone — it does **not** call the Flask/Render backend. It connects directly to Supabase via psycopg2 and posts via the Instagram Graph API.

---

## EventBridge Schedules

All times are PDT (UTC−7) during daylight saving, PST (UTC−8) in winter.
EventBridge cron always runs in **UTC** — times shift ±1 hour when clocks change.

### Active

| Description | Local time | UTC time | Cron expression | Days shift? |
|---|---|---|---|---|
| Mon / Wed / Fri at 9 PM PDT | 21:00 PDT | 04:00 UTC (next day) | `cron(0 4 ? * TUE,THU,SAT *)` | ✅ Yes — crosses midnight |
| Saturday at 9 AM PDT | 09:00 PDT | 16:00 UTC (same day) | `cron(0 16 ? * SAT *)` | ❌ No |

> **Note:** The M/W/F rule fires on TUE, THU, SAT in UTC because 9 PM PDT crosses into the next UTC day. The Saturday 9 AM rule does not cross midnight so the day stays `SAT`.

> **PST drift:** Both rules were configured for PDT (UTC−7). In winter (PST, UTC−8) they will fire one hour earlier local time (8 PM and 8 AM respectively). Acceptable for a casual social media poster.

### Planned

| Description | Local time | UTC time | Cron expression | Rationale |
|---|---|---|---|---|
| Tue / Thu at 11 AM PDT | 11:00 PDT | 18:00 UTC (same day) | `cron(0 18 ? * TUE,THU *)` | Peak Instagram engagement window |

> **Why Tue/Thu 11 AM?** Industry data consistently shows Tuesday and Thursday 9 AM–12 PM as top engagement slots. Gaming content specifically performs well at the lunch scroll window. 2 PM PDT (`cron(0 21 ? * TUE,THU *)`) is a fallback option.

---

## Post Priority Logic

Each Lambda invocation selects content in this order:

```
1. Games played TODAY (PST)
   └── Post today's stats or an anomaly highlight

2. Games played YESTERDAY (PST) — no games today
   └── Post yesterday's stats or an anomaly highlight

3. No recent games
   └── Post all-time historical records across all games
       (duplicate prevention ensures no repeated posts)
```

---

## Duplicate Prevention

The Lambda writes a SHA hash of each post's content to `/tmp/instagram_post_hashes.txt`.

**Important:** `/tmp` persists only for the lifetime of the Lambda container. A cold start clears it.

- Works well for the M/W/F cadence — containers typically stay warm between runs.
- A Saturday gap after Friday night may hit a cold start and re-allow a previously posted hash.
- **Future improvement:** Write hashes to a Supabase table (`dim.dim_instagram_post_log`) to survive cold starts permanently.

---

## Environment Variables

Set in AWS Lambda → Configuration → Environment variables.

| Variable | Description |
|---|---|
| `DB_URL` | Supabase host |
| `DB_PORT` | `5432` |
| `DB_NAME` | `postgres` |
| `DB_USER` | Supabase user |
| `DB_PASSWORD` | Supabase password |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Instagram access token (60-day expiry) |
| `INSTAGRAM_ACCOUNT_ID` | Instagram Business Account ID |
| `TIMEZONE` | `America/Los_Angeles` (default) |

---

## Token Management

Instagram access tokens expire after **60 days**. Refreshing is handled by `utils/instagram_token_utils.py`.

### Refresh endpoint

```
POST https://graph.facebook.com/v21.0/oauth/access_token
grant_type=fb_exchange_token
```

Requires `app_id` and `app_secret` in AWS Secrets Manager under `instagram-poster/instagram`.

### Current token schedule

The refresh automation runs via a separate cron. Refresh at least every 50 days to stay ahead of expiry.

- Token expiry does **not** throw a Lambda error gracefully — the post silently fails.
- **Recommended:** Set a calendar reminder at day 45 to manually verify the token is still valid.

---

## Image Specs

| Field | Value |
|---|---|
| Size | 1080 × 1440 px (portrait) |
| Font | Fira Code |
| Style | Dark background (`#1a1a1a`), gold/white text |
| Chart type | Bar chart (stats) or line chart (trend) |
| GCS backup | Uploaded to Google Cloud Storage on every run |

---

## Lambda Package Notes

- `requirements-lambda.txt` is kept lean — no ML inference packages.
- Inference (Gemini / Bolt AI) runs on Render, not Lambda.
- Dependencies: `psycopg2-binary`, `matplotlib`, `seaborn`, `requests`, `Pillow`

---

## Known Limitations

| Issue | Notes |
|---|---|
| `/tmp` hash store clears on cold start | Fix: migrate to Supabase `dim.dim_instagram_post_log` |
| No timezone-aware cron in EventBridge | 1-hour PDT/PST drift accepted; two rules needed for strict precision |
| `PLAYER_ID = 1` hardcoded | Only posts for player 1; multi-player support is a future enhancement |
| Instagram only queues — no immediate fire path | Posts only go out via the queue, never via direct IFTTT call |

---

## Adding a New EventBridge Rule

1. AWS Console → Lambda → your function → **Configuration** → **Triggers** → **Add trigger**
2. Source: **EventBridge (CloudWatch Events)**
3. Create new rule → Schedule expression (see table above)
4. The same Lambda function handles all rules — no code changes needed

**UTC conversion quick reference:**

| PDT time | UTC | Crosses midnight? | Cron day adjustment |
|---|---|---|---|
| 9 AM PDT | 16:00 UTC | No | Same day |
| 11 AM PDT | 18:00 UTC | No | Same day |
| 2 PM PDT | 21:00 UTC | No | Same day |
| 9 PM PDT | 04:00 UTC | Yes (+1 day) | Next day |
