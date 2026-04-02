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
DB_PORT     = 5432   ← Session pooler (psycopg2 — transaction pooler breaks prepared statements)
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

## Phase 3 — Scaffold FastAPI + ML in parallel (~2026-04-07)

**Status as of 2026-04-01:**
- ✅ Redshift Serverless workgroup and database archived — $0 AWS bill
- ✅ Streamlit app archived to `archive/streamlit/` — web app is the only UI
- ✅ `api/` scaffold created and committed
- Flask stays live on existing Render service until cut-over
- FastAPI deploys as a second Render service
- Cut-over = flip `NEXT_PUBLIC_FLASK_API_URL` on Vercel
- Flask archived to `archive/backend/flask_app.py` 24 hours after cut-over with no regressions

ML is scaffolded **in parallel** with FastAPI — the `ml.py` router, `ml_service.py`,
and `app.ml_model_runs` DDL are built alongside the other routers. ML inference
goes live as soon as `stats.py` is wired (retrain fires on `add_stats`).

---

### Schema changes completed before FastAPI (2026-04-01)

These migrations are already live in both Supabase projects. FastAPI must
reflect the new column names — do not write to `is_trusted` directly.

#### dim.dim_users — role column (migration 002)

`is_trusted BOOLEAN` replaced by a `role TEXT` column. `is_trusted` is kept
as a `GENERATED ALWAYS AS (role = 'trusted') STORED` column for backward
compatibility with any remaining Flask reads.

| role value | Who | Access |
|---|---|---|
| `'trusted'` | Developer / owner / promoted loyals | All features, no cost, can manage game catalog |
| `'registered'` | General public via Google auth | Free + premium subscription plans |
| *(no row)* | Guest | Landing page only, no app access |

**FastAPI rule:** all writes use `role`, never `is_trusted`.
- New user insert: `INSERT INTO dim.dim_users (user_email, role) VALUES ($1, $2)`
- Promote user: `UPDATE dim.dim_users SET role = 'trusted' WHERE user_email = $1`
- JWT payload still includes `is_trusted` (reads from generated column — no change needed)

#### app.subscriptions — billing_interval + plan rename (public only)

```sql
-- plan now CHECK (plan IN ('free', 'premium'))  -- was 'free' | 'pro'
-- new column:
billing_interval TEXT CHECK (billing_interval IN ('month', 'year'))  -- NULL = free tier
```

`app.subscriptions` exists on the **public Supabase project only**. Personal
project does not have this table — trusted users always have full access.

---

### User tier system — FastAPI dependency design

Three tiers enforced in `api/core/deps.py`:

```python
async def get_current_user(credentials) -> dict:
    # decodes JWT, returns {"player_id": ..., "email": ..., "is_trusted": bool}

async def require_trusted(user = Depends(get_current_user)):
    if not user["is_trusted"]:
        raise HTTPException(403, "Trusted access required")

async def require_registered(user = Depends(get_current_user)):
    # any authenticated user passes — guest = no valid JWT
    return user
```

Trusted users skip all limit checks. Registered users are gated by
`app.subscriptions.plan` on the public project. Guests cannot reach any
`/api/` endpoint (JWT required).

---

### Bolt AI — usage limits + BoltPanel progress bar

`app.ai_usage` table tracks monthly message counts (public project only).

| Tier | Monthly Bolt limit |
|---|---|
| Trusted | Unlimited (skip check entirely) |
| Premium | 200 messages / month |
| Free | 20 messages / month |
| Guest | 0 (blocked at auth layer) |

**FastAPI `/api/ask` implementation requirements:**
1. Decode `is_trusted` from JWT — if trusted, skip usage check and use
   `gemini-2.0-flash`; otherwise check `app.ai_usage` and use
   `gemini-2.0-flash-lite` for free tier
2. Upsert usage on every successful response:
   ```sql
   INSERT INTO app.ai_usage (user_email, period_start, messages_used)
   VALUES ($1, date_trunc('month', NOW()), 1)
   ON CONFLICT (user_email, period_start)
   DO UPDATE SET messages_used = app.ai_usage.messages_used + 1
   ```
3. Return `usage: {used, limit}` alongside `reply` in the response body
4. Frontend `BoltPanel.tsx` reads `usage` and renders a progress bar above
   the input (gold < 70%, yellow 70–90%, red > 90%, hidden for trusted)

---

### Timezone — all endpoints must accept `tz`

Every endpoint that buckets `played_at` by date must accept a `tz` query
param and use it for both the DB query and any Python `date` comparisons.
**Never use `date.today()` or `datetime.now()` without a timezone on Render
(Render runs UTC — this breaks streak/summary/chart for users after ~5 PM PT).**

Pattern (already applied to streaks, chart, holiday themes):
```python
from zoneinfo import ZoneInfo
from datetime import datetime

tz = request.args.get("tz", "America/Los_Angeles")
today = datetime.now(ZoneInfo(tz)).date()
# DB: (played_at AT TIME ZONE $1)::DATE
```

Endpoints requiring `tz`:
- `GET /api/get_streaks/{game_id}` ✓ fixed
- `GET /api/get_interactive_chart/{game_id}` ✓ fixed
- `GET /api/get_summary/{game_id}` — fix in FastAPI
- `GET /api/get_heatmap/{game_id}` — fix in FastAPI
- `GET /api/get_ticker_facts/{game_id}` — fix in FastAPI

Frontend always passes: `Intl.DateTimeFormat().resolvedOptions().timeZone`

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
│   ├── users.py              ← Pydantic User
│   └── ml.py                 ← Pydantic ModelRun, PredictionRequest, PredictionResponse
├── routers/
│   ├── stats.py              ← add_stats, get_summary, edit_stat, delete_stat
│   ├── games.py              ← get_games, get_players, get_ranks
│   ├── charts.py             ← get_interactive_chart, get_ticker_facts
│   ├── obs.py                ← [personal] OBS overlay endpoints
│   ├── queue.py              ← [personal] post_queue endpoints
│   ├── dashboard.py          ← [personal] dashboard state
│   ├── admin.py              ← [personal] sync_game_to_public
│   ├── game_requests.py      ← [public] submit/list game requests
│   ├── leaderboard.py        ← [public] leaderboard opts-in
│   └── ml.py                 ← [personal] model_coefficients, feature_importance,
│                                            accuracy_history, predict (BackgroundTasks retrain)
└── services/
│   └── ml_service.py         ← train_models(), retrain_for_user(), load_model(),
│                                store_to_supabase_storage(), compute_lr_coefficients()
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
1. `stats.py` — highest risk, most logic; wire `BackgroundTasks` retrain here
2. `games.py` — simple reads
3. `ml.py` — parallel to step 2; DDL + retrain pipeline + `/model_coefficients` endpoint
4. `charts.py` — wraps chart_utils, test Plotly output
5. `obs.py` — real-time, test with OBS
6. `queue.py` + `dashboard.py` — personal automation
7. `admin.py` — game sync between pools
8. `game_requests.py` + `leaderboard.py` — public launch prep

### app.post_queue migration

`app.post_queue` is the Instagram/automation job queue, currently on Neon.
Target: personal Supabase project (already in the architecture diagram).

**When:** migrate as part of step 6 (`queue.py` router) — do not migrate
earlier, as Flask's queue worker and the table must cut over together.

**DDL** (already in `cost_optimization_guide.md` Step 1 — run in Supabase
personal SQL editor before starting step 6):
```sql
CREATE TABLE IF NOT EXISTS app.post_queue (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload      JSONB        NOT NULL,
    status       TEXT         NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
```

**What changes in `queue.py` router:**
- Replace `NEON_DB_URL` pool with `personal_pool` (already available via deps)
- Port queue worker logic from Flask `process_queue` / `queue_status` / `retry_failed`
- Update `utils/queue_utils.py` connection string to use Supabase pooler

**Cut-over sequence for queue:**
1. Create `app.post_queue` table in Supabase personal
2. Drain existing Neon queue (let all pending jobs finish or manually migrate rows)
3. Switch `NEON_DB_URL` → `SUPABASE_DB_URL` in Render env vars
4. Delete Neon project → eliminates one more monthly cost

---

### Leaderboard cold-start — percentile benchmarks

Before the public leaderboard has enough users to be meaningful, show users
how they rank against **aggregate opted-in data** — no friends required.

**How it works:**
- Any user who opts into a `game_id` contributes their stats to an aggregate
- Every other opted-in user for the same game sees percentile ranks
- No mutual connection, no friend request — just opt-in and compete

**API endpoint (add to `stats.py` or `leaderboard.py`):**
```
GET /api/leaderboard/percentile/{game_id}?stat_type=Eliminations
→ { "your_avg": 8.4, "percentile": 73, "sample_size": 42, "top_10_avg": 14.2 }
```

**DB query (materialized view — refresh on `add_stats`):**
```sql
CREATE MATERIALIZED VIEW analytics.mv_leaderboard_percentiles AS
SELECT
    l.game_id,
    l.stat_type,
    l.user_email,
    l.avg_value,
    PERCENT_RANK() OVER (
        PARTITION BY l.game_id, l.stat_type
        ORDER BY l.avg_value DESC
    ) AS percentile_rank,
    COUNT(*) OVER (PARTITION BY l.game_id, l.stat_type) AS sample_size
FROM app.leaderboard_entries l
JOIN app.leaderboard_opts_in o
    ON l.user_email = o.user_email AND l.game_id = o.game_id
WHERE o.is_public = TRUE;
```

**UI placement:** `SummaryTab` — below streak bar, above chart.
Shows: `"You're in the top 27% for Eliminations (42 players)"`
Hidden if `sample_size < 3` (not enough data to be meaningful).

**Phases:**
| Users opted in | What shows |
|---|---|
| 0 | Hidden |
| 1–2 | Hidden (below threshold) |
| 3–9 | "Top X% — small sample" badge |
| 10+ | Full percentile leaderboard |

---

### IGDB API — game catalog search (all authenticated users)

**Why:** The `dim.dim_games` catalog is currently managed manually by the
trusted user. IGDB (358k+ games) provides canonical game names, genres, and
cover art so both trusted and registered users can search instead of free-typing.

**Auth:** IGDB uses Twitch OAuth client_credentials flow.
- Register app at dev.twitch.tv → get `IGDB_CLIENT_ID` + `IGDB_CLIENT_SECRET`
- Token endpoint: `POST https://id.twitch.tv/oauth2/token?client_id=...&client_secret=...&grant_type=client_credentials`
- Tokens last ~60 days — cache in Render env, refresh via GitHub Actions
  workflow (same pattern as Instagram token refresh)
- All IGDB requests: `Client-ID: {client_id}` + `Authorization: Bearer {token}`

**Rate limits:** 4 requests/second, no monthly cap (free with Twitch auth).

**What IGDB auto-fills on game selection:**

| Field | IGDB source | Editable after? |
|---|---|---|
| `game_name` | `name` | Yes |
| `game_installment` | parsed from `name` (e.g. "Modern Warfare III") | Yes |
| `genre` | `genres[0].name` → mapped to app taxonomy | Yes |
| `subgenre` | `genres[1].name` or `themes[0].name` → mapped | Yes |
| `cover_url` | `cover.url` | Search dropdown thumbnail only — not saved to DB |

`stat_types` remain fully manual — IGDB has no stat data.

Cover art appears as a small thumbnail next to the game name in the search
dropdown results only. It is not stored, not shown in the form after selection,
and not saved to `dim.dim_games`.

**Genre mapping (IGDB → app taxonomy):**
IGDB genre names are mapped to the app's existing genre/subgenre values on the
FastAPI side. Unmapped genres fall back to empty (user fills manually). The
mapping lives in `api/routers/game_requests.py` as a simple dict and can be
extended over time.

**Flow by user tier:**

*Trusted user (personal project — add/edit game form):*
- IGDB search is **optional** — selecting a result pre-fills name, installment,
  genre, and subgenre; all fields remain editable before saving
- Selecting an IGDB result and saving **immediately inserts** into `dim.dim_games`
  (personal) — no approval step
- Manual entry (no IGDB search) still works for games not in IGDB

*Registered user (public project — stats form / game selection):*
- User types a game name → frontend searches IGDB
- **If found in IGDB:** game is auto-added to `dim.dim_games` (public) on first
  use — no approval required, no waiting
- **If NOT in IGDB:** falls back to manual game request → trusted user reviews
  and approves → `admin.py` syncs to both Supabase projects
- `stat_types` for auto-added games default to a genre-based preset (see below)
  and can be extended by the user over time

**Stat_type suggestion — tiered fallback chain:**

When a user adds a game, stat_type suggestions are resolved in this order:

| Priority | Condition | Source |
|---|---|---|
| 1 | Game already tracked by other users | Community stats ranked by frequency from `fact_game_stats` |
| 2 | Game found in seed table | Curated canonical stats (`dim.dim_game_stat_templates`) |
| 3 | IGDB genre maps to a known preset | Genre preset table |
| 4 | Nothing matches | `Score`, `Wins` |

All suggestions are editable — users can add, remove, or rename before saving.

**Community query (priority 1):**
```sql
SELECT stat_type, COUNT(*) AS usage_count
FROM fact.fact_game_stats
WHERE game_id = $1
GROUP BY stat_type
ORDER BY usage_count DESC
LIMIT 10;
```

**Seed table DDL (priority 2 — add to `supabase_schema.sql`, personal only):**
```sql
CREATE TABLE IF NOT EXISTS dim.dim_game_stat_templates (
    igdb_id    INTEGER PRIMARY KEY,
    game_name  TEXT    NOT NULL,
    stat_types TEXT[]  NOT NULL
);

-- Seed data — expand as needed, igdb_id never changes so this never goes stale
INSERT INTO dim.dim_game_stat_templates (igdb_id, game_name, stat_types) VALUES
(1372,  'Call of Duty: Warzone', ARRAY['Eliminations','Respawns','Damage','Placement']),
(21366, 'Apex Legends',          ARRAY['Eliminations','Damage','Placement','Revives']),
(127,   'League of Legends',     ARRAY['Eliminations','Respawns','Assists','CS','Vision Score']),
(1904,  'Valorant',              ARRAY['Eliminationss','Respawns','Assists','ACS','HS%']),
(512,   'Fortnite',              ARRAY['Eliminations','Placement','Damage','Materials']),
(11133, 'Rocket League',         ARRAY['Goals','Assists','Saves','Score','Shots']),
(18232, 'Overwatch 2',           ARRAY['Eliminations','Respawns','Damage','Healing']),
(9590,  'FIFA',                  ARRAY['Goals','Assists','Possession','Shots on Target'])
ON CONFLICT (igdb_id) DO NOTHING;
```

**Genre preset fallback (priority 3):**

| IGDB Genre | Default stat_types |
|---|---|
| Shooter (FPS/TPS) | `Eliminations`, `Deaths`, `Damage` |
| Role-playing (RPG) | `Level`, `XP`, `Quests Completed` |
| Sport | `Score`, `Goals`, `Assists` |
| Strategy | `Wins`, `Units Lost`, `Resources Gathered` |
| Fighting | `Wins`, `KOs`, `Combos` |
| Racing | `Position`, `Lap Time`, `Wins` |
| *(unmapped)* | `Score`, `Wins` |

**Stat alias glossary — canonical names + child-friendly display:**

A `dim.dim_stat_aliases` table maps alternate names and child-friendly labels
to a canonical stat_type. Used in two places:
1. **Community frequency query** — "Kills" and "Eliminations" roll up to the
   same canonical stat so suggestions stay consistent across games
2. **Leaderboard normalization** — users tracking "Kills" vs "Eliminations"
   compare on the same axis without manual mapping

```sql
CREATE TABLE IF NOT EXISTS dim.dim_stat_aliases (
    alias         TEXT PRIMARY KEY,
    canonical     TEXT NOT NULL,  -- stored value in fact_game_stats
    display_label TEXT            -- child-friendly label shown in UI (optional)
);

INSERT INTO dim.dim_stat_aliases (alias, canonical, display_label) VALUES
('Kills',      'Eliminations', 'Eliminations'),
('Frags',      'Eliminations', 'Eliminations'),
('Takedowns',  'Eliminations', 'Eliminations'),
('Deaths',     'Deaths',       'Respawns'),   -- child-friendly override
('Respawns',   'Deaths',       'Respawns'),
('KOs',        'Deaths',       'Respawns'),
('K/D',        'K/D Ratio',    'K/D Ratio'),
('Kill/Death', 'K/D Ratio',    'K/D Ratio'),
('Dmg',        'Damage',       'Damage'),
('Heals',      'Healing',      'Healing'),
('XP',         'Experience',   'XP')
ON CONFLICT (alias) DO NOTHING;
```

`display_label` is what the UI renders. When `display_label` is `'Respawns'`,
the word "Deaths" never appears in the interface — the DB still stores the
canonical value for query consistency.

The alias table lives in personal Supabase and is synced to public via
`admin.py` alongside `dim_games`.

**FastAPI endpoints (add to `game_requests.py` router):**
```
GET  /api/games/search?q={query}          → IGDB proxy (all authenticated users)
POST /api/games/add                       → auto-add IGDB game to dim_games
POST /api/games/request                   → manual request for non-IGDB games only
GET  /api/games/requests                  → list pending manual requests (trusted only)
POST /api/games/requests/{id}/approve     → approve + sync non-IGDB game (trusted only)
```

**IGDB search proxy (server-side — hides credentials from frontend):**
```python
POST https://api.igdb.com/v4/games
body: f'search "{query}"; fields name,cover.url,genres.name,themes.name,first_release_date; limit 10;'
```

**Schema addition (`app.game_requests` — public Supabase):**
```sql
ALTER TABLE app.game_requests
    ADD COLUMN IF NOT EXISTS igdb_id INTEGER;
```

**Render env vars to add:**
```
IGDB_CLIENT_ID     = <Twitch app client ID>
IGDB_CLIENT_SECRET = <Twitch app client secret>
IGDB_ACCESS_TOKEN  = <cached bearer token — refresh monthly>
```

**When:** implement as part of router step 8 (`game_requests.py`).

---

### Riot Games API — migration placement

Full plan: `docs/riot_api_pilot.md`. Prerequisites now met (Supabase live).

**When:** implement as router step 9 after `leaderboard.py`, or in parallel
with Phase 3b ML (they share `app.user_integrations` table).

**Two schema additions missing from `supabase_schema.sql` (gap — add before Riot work):**
```sql
-- Stores connected platform accounts (Riot, Steam, PSN, etc.)
CREATE TABLE IF NOT EXISTS app.user_integrations (
    id                 SERIAL PRIMARY KEY,
    user_email         TEXT NOT NULL REFERENCES dim.dim_users(user_email),
    platform           TEXT NOT NULL,              -- 'riot', 'steam', 'psn'
    platform_user_id   TEXT NOT NULL,              -- PUUID for Riot
    platform_username  TEXT,                       -- "BOL#NA1" display name
    connected_at       TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at     TIMESTAMPTZ,
    UNIQUE (user_email, platform)
);

-- Dedup gate — prevents re-importing already-seen match IDs
CREATE TABLE IF NOT EXISTS app.integration_imports (
    id                 SERIAL PRIMARY KEY,
    user_email         TEXT NOT NULL,
    platform           TEXT NOT NULL,
    external_match_id  TEXT NOT NULL,
    imported_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (platform, external_match_id)
);
```

**Two columns missing from `fact_game_stats` (gap — add before Riot work):**
```sql
ALTER TABLE fact.fact_game_stats
    ADD COLUMN IF NOT EXISTS source      TEXT DEFAULT 'manual',  -- 'manual' | 'riot' | 'steam'
    ADD COLUMN IF NOT EXISTS is_editable BOOLEAN DEFAULT TRUE;   -- FALSE for auto-imported rows
```

---

### Cut-over checklist
- [ ] All routers tested against Supabase
- [ ] `app.post_queue` created in Supabase personal, Neon queue drained
- [ ] Web app `NEXT_PUBLIC_FLASK_API_URL` updated to FastAPI Render URL on Vercel
- [ ] Instagram Lambda still uses psycopg2 directly (not calling FastAPI)
- [ ] One full end-to-end session: submit → summary → chart → OBS overlay
- [ ] Move `flask_app.py` → `archive/backend/flask_app.py`
- [ ] Delete old Render Flask service
- [ ] Delete Neon project after queue confirmed on Supabase

---

## Render env vars — current Flask service (set today)

| Variable | Value |
|---|---|
| `DB_URL` | Personal Supabase pooler host |
| `DB_NAME` | `postgres` |
| `DB_USER` | `postgres.<personal-project-ref>` |
| `DB_PASSWORD` | Personal Supabase password |
| `DB_PORT` | `5432` (Session pooler — psycopg2 requires this; 6543 transaction pooler breaks prepared statements) |
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

## Phase 3b — ML Insights (parallel to Phase 3, frontend after FastAPI stable)

**Backend (Phase 3 parallel):** `ml.py` router + `ml_service.py` built alongside
FastAPI routers. Retrain wired into `add_stats` from day one.

**Frontend (after FastAPI stable):** `InsightsTab`, `PredictionBanner` on Summary,
and mobile Insights screen added once the backend endpoints are verified.

**Goal:** Add predictive analytics to the app using the personal stats data already
in Supabase. Three models, one new DB table, one new Supabase Storage bucket,
one new Insights tab, and a quick prediction widget on the Summary tab.

---

### Personal vs Public — storage strategy

The two Supabase projects have different cost profiles and scale constraints,
so the ML storage approach differs:

#### Personal (personal Supabase project)

| Model | Storage | Cost | Latency |
|---|---|---|---|
| Logistic Regression | JSONB in `ml_model_runs.model_coefficients` | $0 — already in DB | Instant (query result) |
| Random Forest | GCS bucket (`gaming-stats-images-thebolgroup`) | ~$0.00/mo at a few MB | ~200ms cold load |
| XGBoost | GCS bucket (`.save_model()` JSON format) | ~$0.00/mo | ~200ms cold load |

**Why GCS for personal RF/XGBoost:** You already have a GCS bucket provisioned for
Instagram chart images. Reusing it adds zero new infrastructure.

**Why NOT Supabase Storage for personal:** Keeps personal project clean — DB only
holds metadata (JSONB coefficients), binary model files go to the existing GCS bucket.

```
gcs://gaming-stats-images-thebolgroup/
  ml-models/
    {game_id}/
      random_forest.pkl
      xgboost.json
```

---

#### Public (public Supabase project)

Skip GCS entirely — **Supabase Pro already includes 100GB file storage** (S3-compatible).
No reason to add a second service.

| Model | Storage | Cost | Latency |
|---|---|---|---|
| Logistic Regression | JSONB in `ml_model_runs.model_coefficients` | $0 | Instant |
| Random Forest | Supabase Storage bucket (`ml-models/`) | Included in Pro (100GB) | ~100ms warm load |
| XGBoost | Supabase Storage bucket (`ml-models/`) | Included in Pro (100GB) | ~100ms warm load |

**Cost control for public at scale — two policies:**

1. **Session threshold gate:** Only train RF/XGBoost when `sessions_used >= 50`.
   Below that, LR-only (JSONB, zero storage cost per new user).

2. **Eviction policy:** Delete RF/XGBoost model files from Supabase Storage after
   90 days of inactivity (no `add_stats` calls). LR coefficients in JSONB stay forever
   (negligible row size). A nightly cleanup function handles eviction.

```
supabase-storage://ml-models/ (public Supabase project)
  {user_email}/
    {game_id}/
      random_forest.pkl     ← only created at sessions_used >= 50
      xgboost.json          ← only created at sessions_used >= 50
      (no logistic_regression file — always JSONB in DB)
```

**Cost picture at scale:**

| Scale | LR storage | RF/XGBoost storage | Total extra cost |
|---|---|---|---|
| 100 users, avg 30 sessions | JSONB rows only | 0 files (below threshold) | $0 |
| 1,000 users, avg 100 sessions | JSONB rows only | ~1,000 files × 3MB = ~3GB | $0 (within 100GB Pro) |
| 10,000 users, avg 100 sessions | JSONB rows only | ~10,000 × 3MB = ~30GB | $0 (within 100GB Pro) |
| 33,000+ active users | JSONB rows only | ~100GB ceiling | Upgrade storage ($0.021/GB overage) |

---

### Models summary

| Model | Retrain trigger | Personal storage | Public storage |
|---|---|---|---|
| Logistic Regression | Every `add_stats` | JSONB (`ml_model_runs`) | JSONB (`ml_model_runs`) |
| Random Forest | Every `add_stats` if sessions ≥ 10 (personal) / 50 (public) | GCS bucket | Supabase Storage |
| XGBoost | Every `add_stats` if sessions ≥ 10 (personal) / 50 (public) | GCS bucket | Supabase Storage |

**Retrain trigger:** async `BackgroundTasks` on every successful `add_stats` call.

---

### New DB table — app.ml_model_runs

Add to `assets/sql/supabase_schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS app.ml_model_runs (
    id                  SERIAL PRIMARY KEY,
    user_email          TEXT        NOT NULL,
    game_id             INTEGER     NOT NULL REFERENCES dim.dim_games(game_id),
    stat_type           TEXT        NOT NULL,
    model_type          TEXT        NOT NULL,  -- 'logistic_regression', 'random_forest', 'xgboost'
    r2_score            NUMERIC(5,4),
    mae                 NUMERIC(10,2),
    sessions_used       INTEGER,
    feature_importances JSONB,                 -- {"stat_type": importance_value, ...}
    model_coefficients  JSONB,                 -- LR only: {"coef": [...], "intercept": float, "classes": [...]}
    trained_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON app.ml_model_runs (user_email, game_id, model_type, trained_at DESC);
```

---

### New FastAPI router — api/routers/ml.py

```
GET  /api/ml/model_coefficients/{game_id}   → LR coef_ + intercept_ (for client-side inference)
GET  /api/ml/feature_importance/{game_id}   → top features per stat type
GET  /api/ml/accuracy_history/{game_id}     → R² + MAE over time per model
POST /api/ml/predict/{game_id}              → server-side RF/XGBoost prediction (what-if)
```

Add `ml.py` to the Phase 3 router list (mount after `leaderboard.py`).

---

### Summary tab — quick prediction widget

**Location:** `web/components/SummaryTab.tsx` — add a `PredictionBanner` below the
KPI cards, scoped to the currently selected `game_id`.

**Behavior:**
- Fetch LR coefficients once via `GET /api/ml/model_coefficients/{game_id}`
- Use most recent session's stat values as input features
- Compute `P(win)` client-side with TypeScript sigmoid (zero extra backend calls)
- Display as a single confidence bar: `"Win probability next session: 73%"`
- Show `"Not enough data"` if `sessions_used < 10`

**TypeScript inference (no backend round-trip):**
```typescript
function predictWin(
  coefs: Record<string, number>,
  intercept: number,
  stats: Record<string, number>
): number {
  const logit = intercept + Object.entries(coefs).reduce(
    (sum, [feat, coef]) => sum + coef * (stats[feat] ?? 0), 0
  );
  return 1 / (1 + Math.exp(-logit)); // sigmoid → P(win)
}
```

---

### Insights tab — new web tab + mobile 6th tab

**Web:** add `InsightsTab` alongside `SummaryTab`, `HistoryTab`, etc.

| Section | Content |
|---|---|
| Predicted Next Session | Cards: one per stat type, RF/XGBoost point estimate + confidence interval |
| Win Probability | LR P(win) gauge (reuses client-side sigmoid) |
| Feature Importance | Horizontal bar chart (Plotly) — top N stats ranked by RF importance |
| What-if Sliders | Adjust stat values → live P(win) update (client-side, no backend call) |
| Model Accuracy History | Line chart: R² + MAE per training run over time |

**Mobile:** add 6th tab `Insights` (between Dashboard and Leaderboard):
```
Stats 🎮 | History 📊 | Dashboard 📺 | Insights 🤖 | Leaderboard 🏆 | Profile 👤
```
- Predicted Next Session → horizontal scroll of `PredictionCard` components
- Feature importance → `VictoryBar` (Victory Native), horizontal orientation
- What-if sliders → native RN `Slider` component
- Model accuracy → compact `AccuracyBadge` (R² + MAE inline)

---

### K-Means efficiency clustering (shared model, per game)

Unlike LR/RF/XGBoost which are per-user, K-Means is a **shared model across
all opted-in users for a given game**. It improves automatically as more users
contribute stats — no per-user training cost.

**What it does:** Groups sessions into performance tiers based on multi-stat
vectors. Labels are generic so they apply to any game:
`Elite`, `Consistent`, `Developing`, `Outlier`.

**Scaling:** Models are created **lazily, on demand** — only when a game reaches
the training threshold. The IGDB catalog has 358k+ games but your K-Means
model count stays proportional to your active user base, not the catalog size.
Realistically: 10–50 models at early scale, each 1–5MB.

**Feature alignment constraint:** K-Means requires a consistent feature vector
across all users for a game. Users track different stats (one logs
Eliminations + Damage, another logs Kills + Deaths). Fix: only include
stat_types that appear in ≥ 80% of opted-in sessions for that game.
If fewer than 2 stat_types meet the 80% threshold, skip clustering for
that game entirely — not enough shared signal to be meaningful.

**Training thresholds (both must be met before first fit):**
- ≥ 10 opted-in users for the game
- ≥ 10 sessions each from those users
- ≥ 2 stat_types with ≥ 80% coverage across sessions

**When it trains:** Nightly background job. New users assigned to nearest
centroid via `.predict()` on existing model — no re-fit per new user.

**Storage:**
- Personal: GCS bucket → `ml-models/shared/{game_id}/kmeans.pkl`
- Public: Supabase Storage → `ml-models/shared/{game_id}/kmeans.pkl`

**New FastAPI endpoint:**
```
GET /api/ml/cluster/{game_id}
→ { "cluster_label": "Consistent", "cluster_id": 1, "centroid_distance": 0.42,
    "tier_distribution": {"Elite": 18%, "Consistent": 45%, "Developing": 37%},
    "features_used": ["Eliminations", "Damage"] }
```

**UI placement:** `SummaryTab` — inline badge next to the streak bar.
```
🔥 7d streak   •   Cluster: Consistent (top 45%)
```
Hidden until all three training thresholds are met.

**DB addition:**
```sql
-- Cluster assignment cache — avoids re-predicting on every API call
ALTER TABLE app.leaderboard_entries
    ADD COLUMN IF NOT EXISTS cluster_id    INTEGER,
    ADD COLUMN IF NOT EXISTS cluster_label TEXT;
```

---

### Requirements additions

```
# requirements.txt (Render / FastAPI)
scikit-learn>=1.4.0
xgboost>=2.0.0
joblib>=1.3.0        # pickle alternative for RF

# requirements-lambda.txt (Lambda — NOT needed unless Lambda does inference)
# Keep Lambda lean — inference runs on Render, not Lambda
```

---

### Phase 4 checklist

- [ ] Add `app.ml_model_runs` DDL to `assets/sql/supabase_schema.sql`
- [ ] Run DDL against personal Supabase
- [ ] Create `ml-models/` bucket in Supabase Storage (personal project)
- [ ] Implement `api/routers/ml.py` with 4 endpoints
- [ ] Wire `BackgroundTasks` retrain into `add_stats` route
- [ ] Add `PredictionBanner` to `SummaryTab.tsx`
- [ ] Add `InsightsTab` to web app
- [ ] Add Insights screen to React Native mobile (6th tab)
- [ ] Add scikit-learn + xgboost to Render requirements.txt
- [ ] End-to-end test: submit session → retrain fires → coefficients update → Summary banner updates

---

## Key files

| File | Status |
|---|---|
| `flask_app.py` | Active backend — Supabase-ready as of 2026-03-31 |
| `utils/chart_utils.py` | SQL fixed (Phase 1 complete) |
| `instagram_poster.py` | psycopg2 rewrite (Phase 2 complete) |
| `api/main.py` | FastAPI entry point — scaffold committed 2026-04-01 |
| `api/routers/*.py` | All routers stubbed — migrate logic from Flask one by one |
| `assets/sql/supabase_schema.sql` | Source of truth for both Supabase projects |
| `assets/sql/migrations/002_add_user_role.sql` | role column migration — applied 2026-04-01 |
| `archive/backend/flask_app.py` | Flask archived after FastAPI cut-over |
| `archive/streamlit/game_tracker_streamlit_app.py` | Archived 2026-04-01 |
| `docs/riot_api_pilot.md` | Riot integration plan — implement post-FastAPI |
| `api/routers/ml.py` | ML endpoints — Phase 4 |
| `web/components/InsightsTab.tsx` | Insights tab — Phase 4 (not yet created) |
| `web/components/SummaryTab.tsx` | Add PredictionBanner — Phase 4 |

---

## Known gaps (pre-public launch)

These items are documented or partially planned but not yet implemented.
Address before public launch.

| Gap | Where | Priority |
|---|---|---|
| ✅ `app.user_integrations` + `app.integration_imports` tables | Already in schema | Done |
| ✅ `fact_game_stats.source` + `is_editable` columns | Already in schema | Done |
| ✅ `analytics` schema + materialized views | Migration 003 + schema | Done |
| ✅ `app.ml_model_runs.model_coefficients` JSONB | Migration 003 + schema | Done |
| ✅ `app.user_integrations.platform_username` | Migration 003 + schema | Done |
| ✅ Missing indexes (ml_runs, user_integrations, integration_imports, leaderboard_entries, ai_usage) | Migration 003 + schema | Done |
| ✅ `formatPlayedAt` hardcoded `America/Los_Angeles` | `DeleteTab.tsx`, `EditTab.tsx` fixed | Done |
| ✅ Stat name block list (profanity / gibberish) | `constants.ts` + `StatsForm.tsx` | Done |
| ✅ Stat alias glossary (Kills → Eliminations, Deaths → Respawns) | `constants.ts` + `StatsForm.tsx` | Done |
| ✅ Instagram token refresh — migrated to `graph.facebook.com` | `instagram_token_utils.py` | Done |
| ✅ RLS policies designed for all public tables | `supabase_schema.sql` — uncomment at FastAPI cut-over (psycopg2 bypasses RLS) | Enable at cut-over |
| Stripe webhook handler + subscription lifecycle | No doc exists | Before premium launch |
| BoltPanel progress bar (`app.ai_usage` → UI) | Phase 4 checklist missing it | Before public launch |
| Vercel env var list | No doc exists | Before cut-over |
| Personal → Public game sync logic (`admin.py`) | Router stubbed, logic not documented | Phase 3 |
| Timezone hardcodes in `get_summary`, `get_heatmap`, `get_ticker_facts` | `flask_app.py` | Fix in FastAPI versions |
| **API rate limiting** | No throttle on FastAPI endpoints — add `slowapi` middleware | Phase 3 cut-over |
| **Full account deletion cascade** | Data deletion page exists but cascade across all tables unverified | Before public launch |
| **Data export (CSV/JSON)** | No endpoint — GDPR right to portability | Before public launch |
| **Privacy opt-out controls** | No per-user opt-out of leaderboard / community stat templates | Phase 3 |
| **JWT secret rotation plan** | No documented process for rotating without mass logout | Before public launch |
| **Content moderation (server-side)** | Block list is client-side only — FastAPI must re-validate on `add_stats` | Phase 3 cut-over |
| **Email notifications** | Weekly recap, streak alerts, milestone hits — needs Resend integration | Post-launch |
| **Achievement / milestone system** | No gamification beyond streaks — DB tables + FastAPI + UI needed | Post-launch |
| **Search across stat history** | No full-text search — Supabase `to_tsvector` or `WHERE ILIKE` | Post-launch |
| **User-facing API keys** | Power users want programmatic read-only access to own data | Post-launch |
