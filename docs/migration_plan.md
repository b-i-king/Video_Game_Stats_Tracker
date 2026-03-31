# Migration Plan: Redshift → Supabase → FastAPI

**Goal:** Eliminate $100/month AWS Redshift Serverless bill and migrate to a
single FastAPI service on Render backed by two Supabase projects (personal +
public data isolation).

**Written:** 2026-03-31  
**Target complete:** 2026-04-07

---

## Target Architecture

```
Vercel (Next.js web app)
         ↓
Render  (one FastAPI service)
  ├── personal_pool ──→ Personal Supabase  (your stats, OBS, Instagram, post_queue)
  └── public_pool   ──→ Public Supabase    (public users, game_requests, leaderboard)
```

- One Render service, two Supabase connection pools
- Personal data physically isolated from public users
- `require_trusted` FastAPI dependency gates all personal endpoints
- `dim_games` lives in personal Supabase; an admin sync endpoint copies
  approved games to public Supabase
- `instagram_poster.py` stays on AWS Lambda but connects via psycopg2
  (no more Redshift Data API / boto3-redshift-data)

---

## Phase 1 — Fix utils/ SQL syntax (TODAY 2026-03-31)

Flask is now live on Supabase with flask_app.py fully converted.
The utils/ modules still contain Redshift-specific SQL that will fail.

### chart_utils.py — 5 fixes needed

| Line | Redshift syntax | PostgreSQL replacement |
|------|----------------|------------------------|
| 1017 | `CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE)` | `((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::DATE` |
| 1021 | `CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE)` | `((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::DATE` |
| 1028 | `DATEADD(day, -%s, GETDATE())` | `NOW() - (%s \|\| ' days')::INTERVAL` |
| 1038 | `CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE)` | `((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::DATE` |
| 1042 | `CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE)` | `((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::DATE` |

### Other utils/ files
- `ai_utils.py`, `app_utils.py`, `queue_utils.py`, `gcs_utils.py` — scan for
  any Redshift syntax before going live (no SQL found in initial scan but verify)

### Verification checklist
- [ ] Submit a stat session via web app → fact_game_stats row appears in Supabase
- [ ] Summary tab loads (get_summary endpoint)
- [ ] Streak bar shows correct dates
- [ ] Interactive Plotly chart renders and downloads PNG
- [ ] Edit stat works
- [ ] Delete stat works
- [ ] OBS overlay loads current session

---

## Phase 2 — Migrate instagram_poster.py (TODAY 2026-03-31)

**Why it must change:** `instagram_poster.py` uses the AWS Redshift Data API
(`boto3.client('redshift-data')`). This cannot connect to Supabase. Keeping
Redshift alive for Lambda costs ~$100/month.

### What changes in instagram_poster.py

| Current (Redshift Data API) | New (psycopg2 direct) |
|---|---|
| `boto3.client('redshift-data')` | `psycopg2.connect(...)` |
| `REDSHIFT_WORKGROUP` env var | `DB_URL`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` env vars |
| `:named_param` SQL syntax | `%s` positional params |
| `execute_query(sql, parameters)` helper | direct `cur.execute(sql, params)` |
| `CONVERT_TIMEZONE(:tz, played_at)` | `((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::DATE` |
| `GETDATE()` | `NOW()` |
| `DATEADD(day, -365, GETDATE())` | `NOW() - INTERVAL '365 days'` |
| `EXTRACT(YEAR FROM CONVERT_TIMEZONE(...))` | `EXTRACT(YEAR FROM ((played_at AT TIME ZONE 'UTC') AT TIME ZONE %s))` |
| `get_field_value(field)` dict unpacking | standard psycopg2 row tuples |

### AWS Lambda env vars to add
```
DB_URL      = <personal Supabase pooler host>
DB_PORT     = 6543
DB_NAME     = postgres
DB_USER     = postgres.<personal-project-ref>
DB_PASSWORD = <personal Supabase password>
```

### AWS Lambda env vars to remove after verification
```
REDSHIFT_WORKGROUP
AWS_ACCESS_KEY_ID      (if only used for Redshift Data API)
AWS_SECRET_ACCESS_KEY  (if only used for Redshift Data API)
```

### After instagram_poster.py verified working on Supabase
- [ ] Run one full Instagram post end-to-end
- [ ] Confirm stats appear correctly in chart
- [ ] Delete Redshift workgroup in AWS Console → $0/month bill

---

## Phase 3 — Scaffold FastAPI + archive Flask (~2026-04-07)

Reference: `docs/fastapi_app.py` — existing FastAPI migration placeholder with
all route stubs. SQL bodies stay the same; only framework boilerplate changes.

### New folder structure
```
api/                          ← new FastAPI service (alongside flask_app.py)
├── main.py                   ← mounts all routers, two-pool lifespan
├── core/
│   ├── config.py             ← env vars, settings
│   ├── db.py                 ← personal_pool + public_pool (asyncpg)
│   └── auth.py               ← require_auth + require_trusted deps
├── models/
│   ├── stats.py              ← Pydantic StatRecord, AddStatsRequest
│   ├── games.py              ← Pydantic Game, Player
│   └── users.py              ← Pydantic User
├── routers/
│   ├── stats.py              ← add_stats, get_summary, edit_stat, delete_stat
│   ├── games.py              ← get_games, get_players, get_ranks
│   ├── charts.py             ← get_interactive_chart, get_ticker_facts
│   ├── obs.py                ← [personal] OBS overlay endpoints
│   ├── queue.py              ← [personal] post_queue endpoints
│   ├── dashboard.py          ← [personal] dashboard state
│   ├── admin.py              ← [personal] sync_game_to_public
│   ├── game_requests.py      ← [public] submit/list game requests
│   └── leaderboard.py        ← [public] leaderboard opts-in
└── requirements.txt
```

### core/db.py — two pools
```python
personal_pool = None
public_pool   = None

@asynccontextmanager
async def lifespan(app):
    global personal_pool, public_pool
    personal_pool = await asyncpg.create_pool(
        host=os.environ["PERSONAL_DB_URL"],
        port=int(os.environ.get("PERSONAL_DB_PORT", 6543)),
        database="postgres",
        user=os.environ["PERSONAL_DB_USER"],
        password=os.environ["PERSONAL_DB_PASSWORD"],
        ssl="require", min_size=1, max_size=3,
    )
    public_pool = await asyncpg.create_pool(
        host=os.environ["PUBLIC_DB_URL"],
        port=int(os.environ.get("PUBLIC_DB_PORT", 6543)),
        database="postgres",
        user=os.environ["PUBLIC_DB_USER"],
        password=os.environ["PUBLIC_DB_PASSWORD"],
        ssl="require", min_size=1, max_size=5,
    )
    yield
    await personal_pool.close()
    await public_pool.close()
```

### Render env vars for FastAPI service
```
PERSONAL_DB_URL       = <personal Supabase pooler host>
PERSONAL_DB_PORT      = 6543
PERSONAL_DB_USER      = postgres.<personal-ref>
PERSONAL_DB_PASSWORD  = <personal password>

PUBLIC_DB_URL         = <public Supabase pooler host>
PUBLIC_DB_PORT        = 6543
PUBLIC_DB_USER        = postgres.<public-ref>
PUBLIC_DB_PASSWORD    = <public password>

JWT_SECRET_KEY        = <same key as Flask for session continuity>
API_KEY               = <same or new key>
TRUSTED_EMAILS        = biking.phd@gmail.com
GCS_BUCKET_NAME       = gaming-stats-images-thebolgroup
GCS_CREDENTIALS_JSON  = <same as Flask>
```

### Migration order (routes)
Migrate one router at a time, test, then move on:
1. `stats.py` — highest risk, most logic
2. `games.py` — simple reads
3. `charts.py` — wraps chart_utils, test Plotly output
4. `obs.py` — real-time, test with OBS
5. `queue.py` + `dashboard.py` — personal automation
6. `admin.py` — game sync between pools
7. `game_requests.py` + `leaderboard.py` — public launch prep

### Cut-over checklist
- [ ] All routers tested against Supabase
- [ ] Web app `NEXT_PUBLIC_FLASK_API_URL` updated to FastAPI Render URL on Vercel
- [ ] Instagram Lambda still uses psycopg2 directly (not calling FastAPI)
- [ ] One full end-to-end session: submit → summary → chart → OBS overlay
- [ ] Move `flask_app.py` → `archive/flask_app.py`
- [ ] Move `docs/fastapi_app.py` → `api/` (it becomes the live file)
- [ ] Delete old Render Flask service

---

## Render env vars — current Flask service (set today)

| Variable | Value |
|---|---|
| `DB_URL` | Personal Supabase pooler host |
| `DB_NAME` | `postgres` |
| `DB_USER` | `postgres.<personal-project-ref>` |
| `DB_PASSWORD` | Personal Supabase password |
| `DB_PORT` | `6543` |
| `DB_TYPE` | `supabase` |

---

## SQL syntax reference: Redshift → PostgreSQL

| Redshift | PostgreSQL |
|---|---|
| `GETDATE()` | `NOW()` |
| `CAST(CONVERT_TIMEZONE('UTC', tz, col) AS DATE)` | `((col AT TIME ZONE 'UTC') AT TIME ZONE tz)::DATE` |
| `CAST(CONVERT_TIMEZONE(tz, col) AS DATE)` | `((col AT TIME ZONE 'UTC') AT TIME ZONE tz)::DATE` |
| `DATEADD(day, -N, GETDATE())` | `NOW() - INTERVAL 'N days'` |
| `DATEADD(day, -%s, GETDATE())` | `NOW() - (%s \|\| ' days')::INTERVAL` |
| `EXTRACT(YEAR FROM CONVERT_TIMEZONE(tz, col))` | `EXTRACT(YEAR FROM ((col AT TIME ZONE 'UTC') AT TIME ZONE tz))` |
| `CAST(GETDATE() AS DATE)` | `CURRENT_DATE` |
| `ISNULL(x, y)` | `COALESCE(x, y)` |
| `IDENTITY(1,1)` | `GENERATED ALWAYS AS IDENTITY` |
| `VARCHAR(MAX)` | `TEXT` |
| `:named_param` (Redshift Data API) | `%s` (psycopg2) or `$1` (asyncpg) |

---

## Key files

| File | Status |
|---|---|
| `flask_app.py` | Active backend — Supabase-ready as of 2026-03-31 |
| `utils/chart_utils.py` | Needs SQL fixes (Phase 1) |
| `instagram_poster.py` | Needs full rewrite psycopg2 (Phase 2) |
| `docs/fastapi_app.py` | FastAPI migration placeholder — becomes `api/main.py` |
| `assets/sql/supabase_schema.sql` | Source of truth for both Supabase projects |
| `archive/flask_app.py` | Flask archived after FastAPI cut-over (~2026-04-07) |
