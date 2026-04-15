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
TRUSTED_EMAILS        = <personal email>
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
body: f'search "{query}"; fields name,cover.url,genres.name,themes.name,game_modes.name,first_release_date; limit 10;'
```

**Game mode — dynamic population from IGDB:**

The game mode dropdown for registered users is populated from IGDB's
`game_modes` field rather than a hardcoded static list. IGDB's canonical
game mode values are:

| IGDB `game_modes.name` | App game_mode value |
|---|---|
| `Single player` | `Solo` |
| `Multiplayer` | `Team` |
| `Co-operative` | `Co-op` |
| `Split screen` | `Split Screen` |
| `Massively Multiplayer Online (MMO)` | `MMO` |
| `Battle Royale` | `Battle Royale` |

FastAPI maps IGDB mode names → app values on the `/api/games/add` response.
Frontend receives `available_modes: string[]` and renders them as the
game mode options for that specific game — no hardcoded list needed.

For trusted users (personal project): game mode options remain fully manual
via the existing dropdown. IGDB-derived modes are a registered-user feature
only since trusted users may add custom game modes not in IGDB.

For games not in IGDB (manual request path): game mode falls back to the
existing static list (`Solo`, `Team`, `Co-op`, etc.).

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

## Trust & Safety — Violation Tracking & User Management (Phase 3)

Designed for large-scale public use. No user is ever auto-banned — all bans are
owner-reviewed. The system tracks violations, surfaces flagged accounts, and
gives the owner full control.

---

### Guiding principle

> **Two-tier response:** Auto-ban for severe, unambiguous violations (slurs,
> derogatory language, bullying). Flag for owner review for everything else —
> a typo that triggers a general profanity filter looks identical to intent
> in raw data, but a racial slur does not.

---

### Violation severity tiers

#### Tier 1 — Immediate auto-ban (zero tolerance)

No strikes, no review, no appeal path at the app level.
Logged to `app.violation_log` with `violation_type = 'severe'`.
Owner is notified but no action is required — ban is already applied.

| Content | Examples |
|---|---|
| Racial slurs | Dedicated slur blocklist (separate from `bad-words`) |
| Derogatory language targeting identity | Slurs based on gender, sexuality, religion, disability |
| Bullying / targeted harassment | Player names or stat names targeting another user by name |

**Implementation:** Maintain a `SEVERE_TERMS` set in `constants.ts` and a server-side equivalent in FastAPI. Checked **before** the general profanity filter. Match on word boundaries (`\b`) to avoid false positives on substrings.

> **Note:** This list is intentionally separate from `BLOCKED_STAT_TERMS` and
> `bad-words` so it can be maintained independently without touching general
> content moderation logic.

#### Tier 2 — Strike system (owner review at threshold)

Ambiguous violations where context matters. A human reviews at strike 3.

| Event | Strike? | Reason |
|---|---|---|
| General profanity filter hit (`bad-words` / `better_profanity`) | ✅ Yes | Unlikely to be a typo but not always intentional |
| Gibberish hit (`BLOCKED_STAT_TERMS` — "asdf", "qwerty") | ✅ Yes | Never a typo |
| Repeated same blocked stat across multiple sessions | ✅ Yes | Pattern = intent |
| Invalid format (`STAT_TYPE_RE` failure — symbols, too long) | ❌ No | Easily a typo |
| Stat value out of range | ❌ No | Fat-finger |
| Duplicate submission (2-min window) | ❌ No | Double-click |

---

### Strike decay (typo protection)

Violations older than **90 days** are forgiven — the count resets before
incrementing. A user who made a genuine mistake months ago starts fresh.

```
Violation arrives → check last_violation_at
  If last_violation_at > 90 days ago → reset violation_count to 0
  Increment violation_count
  Update last_violation_at = now
```

---

### Strike thresholds (Tier 2 only)

| Count | Action | Visible to user? |
|---|---|---|
| 1 | Warning: "Stat name not allowed." | ✅ Yes — generic message |
| 2 | Escalated warning: "Repeated violations have been logged." | ✅ Yes |
| 3 | `flagged_at` set → owner notified | ❌ No — silent flag |
| Owner reviews → ban | `banned_at` set → JWT returns 403 | ✅ Yes — "Account suspended." |
| Owner reviews → clear | `violation_count` reset, `flagged_at` cleared | ❌ No — silent |

**Tier 1 (severe)** bypasses all of the above:
- `banned_at` set immediately
- `violation_count` set to 99 (sentinel — distinguishes auto-ban from owner ban)
- `ban_reason` set to `'auto:severe_content'`
- Owner receives notification but no action required

Users are **never told** they are flagged (count=3) — only that their content
was rejected. This prevents gaming the system to stay just under the threshold.

---

### DB schema changes (`dim.dim_users`)

```sql
ALTER TABLE dim.dim_users
  ADD COLUMN violation_count    INT          NOT NULL DEFAULT 0,
  ADD COLUMN last_violation_at  TIMESTAMPTZ,
  ADD COLUMN flagged_at         TIMESTAMPTZ,
  ADD COLUMN banned_at          TIMESTAMPTZ,
  ADD COLUMN ban_reason         TEXT;
```

Add to `assets/sql/migrations/` as `004_add_trust_safety.sql`.

---

### FastAPI implementation

**`api/core/deps.py`** — add banned check to JWT dependency:
```python
if user.banned_at:
    raise HTTPException(403, "Account suspended. Contact support.")
```

**`api/routers/stats.py`** — after `_content_check()` violation:
```python
await trust_service.record_violation(user_id, violation_type, content)
```

**`api/services/trust_service.py`** (new file):
- `record_violation(user_id, type, content)` — applies decay, increments, sets flagged_at at 3
- `ban_user(user_id, reason)` — owner action
- `clear_violations(user_id)` — owner action
- `get_flagged_users()` — owner review list

---

### Owner admin endpoints (`api/routers/admin.py`)

All require `requires_owner` FastAPI dependency.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/flagged_users` | List all users with `flagged_at IS NOT NULL` |
| `POST` | `/api/admin/ban_user/{user_id}` | Set `banned_at`, optional `ban_reason` |
| `POST` | `/api/admin/unban_user/{user_id}` | Clear `banned_at` |
| `POST` | `/api/admin/clear_violations/{user_id}` | Reset count + clear `flagged_at` |
| `DELETE` | `/api/admin/delete_user/{user_id}` | Hard delete — cascade all stats (irreversible) |

---

### Owner review UI (Phase 3 web app)

Add an **Admin tab** to the Stats page, visible only when `session.isOwner = true`.

Displays:
- Flagged users table (email, violation count, flagged date, last violation content)
- Ban / Clear / Delete actions per row
- Violation log (what was submitted, when, from which IP if available)

---

### Violation log table (`app.violation_log`)

Separate from `dim.dim_users` to keep the user record clean.
Used for the owner review UI and future ML abuse detection.

```sql
CREATE TABLE app.violation_log (
  log_id         BIGSERIAL PRIMARY KEY,
  user_id        INT REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
  violation_type TEXT NOT NULL,   -- 'profanity' | 'gibberish' | 'pattern'
  content        TEXT,            -- what they tried to submit
  ip_address     TEXT,            -- optional, requires FastAPI middleware
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON app.violation_log (user_id, created_at DESC);
```

---

### Phase 3 checklist — Trust & Safety

- [ ] Add `004_add_trust_safety.sql` migration
- [ ] Add `app.violation_log` DDL to `supabase_schema.sql`
- [ ] Build `SEVERE_TERMS` word-boundary blocklist in `constants.ts` (slurs, derogatory, harassment)
- [ ] Mirror `SEVERE_TERMS` server-side in FastAPI `trust_service.py`
- [ ] Implement `api/services/trust_service.py` with Tier 1 auto-ban + Tier 2 strike logic
- [ ] Wire `record_violation()` into FastAPI `add_stats` content check — Tier 1 checked first
- [ ] Add banned check to `api/core/deps.py` JWT dependency
- [ ] Implement `api/routers/admin.py` with 5 endpoints
- [ ] Add Admin tab to web app (owner-only) — shows flagged queue + auto-ban log separately
- [ ] Carry over `isBlockedStatName` + `SEVERE_TERMS` validation from Flask to FastAPI

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
| ✅ Stripe webhook handler + subscription lifecycle | Documented in Stripe section below | Before premium launch |
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
| **Trust & Safety — violation tracking + owner review** | No strike system exists — design doc in this file (Phase 3 section) | Phase 3 |
| **Email notifications** | Weekly recap, streak alerts, milestone hits — needs Resend integration | Post-launch |
| **Achievement / milestone system** | No gamification beyond streaks — DB tables + FastAPI + UI needed | Post-launch |
| **Search across stat history** | No full-text search — Supabase `to_tsvector` or `WHERE ILIKE` | Post-launch |
| **Gamification — streaks, badges, seasonal challenges** | Full design in Gamification section below | Post-launch |
| **User-facing API keys** | Power users want programmatic read-only access to own data | Post-launch |


---

## Stripe Integration (Before Premium Launch)

### Overview

Stripe handles all billing. FastAPI receives Stripe webhooks and updates
`app.subscriptions` on the **public Supabase project**. The Flask JWT / FastAPI
JWT reflects `role="premium"` on the user's next login after Stripe confirms
payment.

---

### Stripe Dashboard Setup

1. Create two **Products** in the Stripe dashboard:
   - `Game Tracker Premium — Monthly` → price: `price_monthly_xxx`
   - `Game Tracker Premium — Annual` → price: `price_annual_xxx`
2. Save both price IDs as Render env vars:
   ```
   STRIPE_PRICE_MONTHLY=price_monthly_xxx
   STRIPE_PRICE_ANNUAL=price_annual_xxx
   ```
3. Create a **Webhook endpoint** pointing at:
   ```
   https://your-app.onrender.com/webhooks/stripe
   ```
   Events to enable:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`

4. Save the webhook signing secret:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_SECRET_KEY=sk_live_xxx   (sk_test_xxx for dev)
   ```

---

### FastAPI Route — `api/routers/webhooks.py`

```python
import stripe
from fastapi import APIRouter, Request, HTTPException
from api.core.db import public_pool

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"])
    elif event["type"] == "customer.subscription.updated":
        await _handle_subscription_updated(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        await _handle_subscription_deleted(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        await _handle_payment_failed(event["data"]["object"])

    return {"status": "ok"}
```

---

### Subscription Lifecycle

| Stripe Event | Action on `app.subscriptions` |
|---|---|
| `checkout.session.completed` | Insert/update row: `plan='premium'`, `stripe_customer_id`, `stripe_subscription_id`, `billing_interval`, `current_period_end` |
| `customer.subscription.updated` | Update `billing_interval`, `current_period_end`, `plan` (handles upgrades/downgrades) |
| `customer.subscription.deleted` | Set `plan='free'`, clear `stripe_subscription_id`, set `cancelled_at` |
| `invoice.payment_failed` | Log failure — optionally email user via Resend; do NOT downgrade immediately (Stripe retries) |

---

### Checkout Flow (Next.js → FastAPI)

1. User clicks **Upgrade to Premium** in web app
2. `POST /api/billing/create-checkout-session` (FastAPI, requires JWT)
   - Creates Stripe Checkout session with `customer_email` pre-filled
   - Sets `metadata: { user_email: ... }` so webhook can identify the user
   - Returns `{ url: "https://checkout.stripe.com/..." }`
3. Frontend redirects to Stripe-hosted checkout page
4. On success, Stripe fires `checkout.session.completed` webhook → FastAPI updates DB
5. User is redirected back to `/billing/success` page
6. On next sign-in (or JWT refresh), Flask/FastAPI reads `app.subscriptions.plan='premium'` → issues JWT with `role="premium"`

---

### `app.subscriptions` Schema (public Supabase)

```sql
CREATE TABLE app.subscriptions (
    subscription_id     SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES dim.dim_users(user_id),
    plan                TEXT CHECK (plan IN ('free', 'premium')) DEFAULT 'free',
    billing_interval    TEXT CHECK (billing_interval IN ('month', 'year')),  -- NULL = free
    stripe_customer_id  TEXT UNIQUE,
    stripe_subscription_id TEXT,
    current_period_end  TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

### JWT — How `role="premium"` Gets Into the Token

FastAPI `/api/login` checks `app.subscriptions` on the public project during
login and folds the result into the JWT payload:

```python
# In /api/login
sub = await public_pool.fetchrow(
    "SELECT plan FROM app.subscriptions WHERE user_id = $1", user_id
)
plan = sub["plan"] if sub else "free"

role = (
    "owner"   if is_owner else
    "trusted" if is_trusted else
    "premium" if plan == "premium" else
    "free"
)
```

The Next.js session and Navbar tier badge update automatically on the next
sign-in or JWT refresh (60-minute expiry).

---

### Render Env Vars Required

```
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_MONTHLY=price_monthly_xxx
STRIPE_PRICE_ANNUAL=price_annual_xxx
```

---

### Phase checklist — Stripe

- [ ] Create Stripe products + prices (monthly + annual) in dashboard
- [ ] Add Render env vars (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, prices)
- [ ] Create `api/routers/webhooks.py` with webhook handler
- [ ] Create `api/routers/billing.py` with `create-checkout-session` endpoint
- [ ] Add `stripe_customer_id` + `stripe_subscription_id` + `billing_interval` + `current_period_end` columns to `app.subscriptions` (migration `006_add_stripe_billing.sql`)
- [ ] Wire `plan` check into `/api/login` JWT generation
- [ ] Build `/billing/success` and `/billing/cancel` pages in Next.js
- [ ] Add **Upgrade to Premium** button in web app (gated to `role="free"` users)
- [ ] Update `next-auth.d.ts` role comment to include `"premium"`
- [ ] Test full checkout flow end-to-end in Stripe test mode
- [ ] Switch to live keys before public launch

---

## Wellness Notifications (Phase 4 / Post-launch)

### Purpose

Encourage healthy gaming habits through generic, opt-in nudges — not medical
advice. Inspired by Apple Watch Stand reminders and sleep scheduling (Fitbit,
Whoop, Google Fit). Since this is a web app with no sensors, all nudges are
**time-based** and **user-configured**.

> Disclaimer shown in UI: *"These are general wellness reminders, not medical
> advice. Consult a healthcare professional for personalized guidance."*

---

### Features

| Feature | Trigger | Delivery |
|---|---|---|
| **Break reminder** | User has been active on the app for X minutes (configurable, default 60 min) | Browser notification + optional in-app banner |
| **Bedtime nudge** | Clock reaches user's configured bedtime | Browser notification: *"Heading toward bedtime — consider wrapping up"* |
| **Session length banner** | In-app passive banner after long session (no browser permissions needed) | Non-intrusive top-of-page ribbon |

All features are **opt-in** and configurable per user. No defaults are applied
without explicit user consent.

---

### Schema — `app.wellness_settings` (public Supabase)

```sql
CREATE TABLE app.wellness_settings (
    user_id             INTEGER PRIMARY KEY REFERENCES dim.dim_users(user_id),
    break_reminders     BOOLEAN DEFAULT FALSE,
    break_interval_min  INTEGER DEFAULT 60,        -- minutes between break nudges
    bedtime_enabled     BOOLEAN DEFAULT FALSE,
    bedtime_local       TIME,                      -- e.g. '22:30:00' in user's local time
    bedtime_tz          TEXT,                      -- IANA timezone string
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

### Frontend Implementation

- **Break timer** — `useEffect` in a top-level layout component tracks
  cumulative time-on-site using `Date.now()`. Fires browser
  `Notification.requestPermission()` once opted in, then uses
  `setTimeout` to schedule nudges at the configured interval.
- **Bedtime nudge** — on page load, compute milliseconds until bedtime in
  the user's timezone and set a single `setTimeout`. Re-schedules itself
  daily.
- **In-app banner** — fallback for users who decline browser notification
  permission. Simple dismissible ribbon at the top of the page.

---

### FastAPI Routes

```
GET  /api/wellness/settings        → fetch user's wellness settings
PUT  /api/wellness/settings        → save/update preferences
```

No server-side scheduling needed — all timers run client-side in the browser.

---

### Phase checklist — Wellness Notifications

- [ ] Create `app.wellness_settings` table (migration `008_add_wellness_settings.sql`)
- [ ] Create `api/routers/wellness.py` with GET + PUT settings endpoints
- [ ] Register wellness router in `api/main.py`
- [ ] Build **Wellness Settings** section in web app (Settings or Profile page)
  - Break reminder toggle + interval selector (30 / 45 / 60 / 90 min)
  - Bedtime toggle + time picker + timezone confirmation
- [ ] Implement `useWellnessNotifications` hook in Next.js
  - Request browser notification permission on opt-in
  - Break timer via `setTimeout` + visibility API (pause when tab is hidden)
  - Bedtime timer scoped to user's local timezone
- [ ] In-app session banner (fallback for denied notification permissions)
- [ ] Add disclaimer copy: *"General wellness reminders — not medical advice"*
- [ ] Respect `prefers-reduced-motion` and Do Not Disturb where detectable

---

## Steam Integration (Post-launch)

### Purpose

Steam does not provide match-level game stats — only playtime. This makes it a
**read-only enrichment layer** for the Summary tab rather than a core stat
source. Steam data informs context alongside manually logged sessions but never
replaces them.

---

### What Steam API Provides

| Endpoint | Data | Use |
|---|---|---|
| `GetOwnedGames` | All owned games + `playtime_forever` (minutes) | Total hours per game |
| `GetRecentlyPlayedGames` | Last 2 weeks playtime per game | Recent activity widget |
| `GetPlayerSummaries` | Display name, avatar, profile visibility | Profile enrichment |

**Key caveat:** Steam profiles must be set to **public** by the user for any
data to be returned. Private profiles return empty results — handle this
gracefully in the UI with a "Set your Steam profile to public to enable this
feature" message.

---

### API Access

- **Public API** — any Steam account holder can request a free key at
  `steamcommunity.com/dev/apikey`
- No OAuth2 — Steam uses an **OpenID** login flow for user identity
- Add to Render env vars:
  ```
  STEAM_API_KEY=your_steam_api_key
  ```

---

### Auth Flow (OpenID)

Steam does not use OAuth2. The connect flow is:

1. User clicks **Connect Steam** in web app
2. Redirect to `https://steamcommunity.com/openid/login` with your return URL
3. Steam redirects back with a signed `openid.claimed_id` containing the user's
   64-bit `steamid`
4. FastAPI verifies the OpenID signature and stores `steamid` in
   `app.user_integrations`
5. All subsequent API calls use the stored `steamid` — no token to refresh

---

### Schema

Steam playtime does not belong in `fact_game_stats` (no match context).
Store it in a dedicated table on the **public Supabase project**:

```sql
CREATE TABLE app.steam_playtime (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES dim.dim_users(user_id),
    steam_app_id    INTEGER NOT NULL,           -- Steam's internal game ID
    game_name       TEXT,                       -- from Steam API
    playtime_total  INTEGER NOT NULL,           -- minutes, lifetime
    playtime_2weeks INTEGER,                    -- minutes, last 2 weeks (NULL if not recent)
    last_synced_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, steam_app_id)
);
```

`app.user_integrations` already has a `platform` column — add a row with
`platform='steam'` and store the `steamid` in `platform_user_id`.

---

### Summary Tab — What Gets Surfaced

- **Total hours played** for each game in your `dim_games` table (matched by
  Steam app ID — requires a `steam_app_id` column on `dim_games`)
- **"Time played this week"** from `playtime_2weeks` — visible even on days
  with no logged session
- **Completeness ratio** — "You've logged X sessions covering Y% of your total
  Warzone playtime" (motivates more logging)
- **Game library** — Steam cover art + official title for `dim_games` enrichment

---

### `dim_games` Enrichment

Add a `steam_app_id` column to `dim_games` so playtime can be matched to your
tracked games:

```sql
ALTER TABLE dim.dim_games ADD COLUMN IF NOT EXISTS steam_app_id INTEGER;
```

An admin sync endpoint can pre-populate known app IDs (e.g. Warzone = 1962663).

---

### FastAPI Routes

```
GET  /api/integrations/steam/connect      → initiates OpenID redirect
GET  /api/integrations/steam/callback     → verifies OpenID, stores steamid
POST /api/integrations/steam/sync         → pulls latest playtime, upserts app.steam_playtime
GET  /api/integrations/steam/playtime     → returns playtime rows for Summary tab
DELETE /api/integrations/steam/disconnect → removes steamid + playtime rows
```

---

### Sync Strategy

- Sync is **on-demand** (user triggers) or **on login** if last sync > 24 hours
- Do not poll continuously — Steam rate limits are generous but unnecessary load
- If profile is private, return a clear error: `{ "error": "profile_private" }`
  so the frontend can show the "make your profile public" prompt

---

### Phase checklist — Steam

- [ ] Add `steam_app_id` column to `dim_games` (migration `007_add_steam_app_id.sql`)
- [ ] Create `app.steam_playtime` table (same migration)
- [ ] Add `STEAM_API_KEY` to Render env vars
- [ ] Create `api/routers/steam.py` with OpenID connect + playtime sync routes
- [ ] Handle private profile gracefully — surface "make profile public" message in UI
- [ ] Build **Connect Steam** button in web app integrations settings
- [ ] Summary tab — add playtime widget (total hours + 2-week activity per game)
- [ ] Summary tab — add completeness ratio ("X% of playtime logged")
- [ ] Enrich `dim_games` cover art + official names from Steam app details endpoint
- [ ] Admin: pre-populate `steam_app_id` for known games in `dim_games`

---

## Gamification (Post-launch)

The core retention loop is already in place — users play daily, log stats, and
want to see improvement. Gamification layers meaning on top of that data to
make *logging* feel as rewarding as *playing*.

---

### Features

#### Streaks & Consistency
- Log a session at least once per day (or per week — configurable) → streak counter
- Streak displayed on the Stats page and user profile
- Streak break is a powerful re-engagement trigger → email/push notification (Resend)

#### Personal Milestones & Badges
- Auto-detect when a user hits a new personal best and surface it prominently
- Example triggers: "First time averaging 10+ kills", "50 sessions logged", "30-day streak"
- Each milestone unlocks a badge stored in `app.user_badges`
- Badges are displayable on the user's profile and shareable to social media

#### Seasonal Challenges
- Monthly stat goals users opt into ("Average 8 assists/game in April")
- Resets on the 1st of each month — creates a recurring reason to return
- On completion: unlock a **downloadable season badge image** (PNG/SVG)
  - Free/Premium users without social media integration can download the badge
    and post it manually to their own social accounts
  - Trusted/Owner users can push directly via the existing social pipeline
- Owner can define new challenges via the Admin panel (Phase 3)

#### Leaderboard (Phase 3)
- Opt-in public ranking by game + stat type
- Even seeing someone ranked above you is a daily pull-back
- Backed by `app.leaderboard_entries` (already in schema)

#### Bolt AI Weekly Recap
- Bolt generates a personalized weekly summary: trends, streaks, milestone progress
- "You're trending up in kills but your death rate increased — here's what changed"
- Delivered in-app and optionally via email (Resend)
- Makes Bolt feel like a coach, not just a query tool

---

### DB Schema

```sql
-- Badges catalog (seeded by owner)
CREATE TABLE app.badges (
  badge_id    SERIAL PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,        -- e.g. 'first_pb', 'streak_30'
  name        TEXT NOT NULL,
  description TEXT,
  image_url   TEXT,                        -- e.g. /badges/streak_30.png (Vercel static asset)
  tier_required TEXT DEFAULT 'free'        -- 'free' | 'premium' | 'trusted' | 'owner'
);

-- Badges earned by users
CREATE TABLE app.user_badges (
  id          BIGSERIAL PRIMARY KEY,
  user_id     INT REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
  badge_id    INT REFERENCES app.badges(badge_id),
  earned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, badge_id)
);
CREATE INDEX ON app.user_badges (user_id);

-- Seasonal challenges
CREATE TABLE app.challenges (
  challenge_id  SERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT,
  stat_type     TEXT,                      -- NULL = any stat
  target_value  NUMERIC,
  period_start  DATE NOT NULL,
  period_end    DATE NOT NULL,
  badge_id      INT REFERENCES app.badges(badge_id),
  created_by    INT REFERENCES dim.dim_users(user_id)
);

-- User challenge enrollment + progress
CREATE TABLE app.user_challenges (
  id            BIGSERIAL PRIMARY KEY,
  user_id       INT REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
  challenge_id  INT REFERENCES app.challenges(challenge_id),
  enrolled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at  TIMESTAMPTZ,
  progress      NUMERIC DEFAULT 0,
  UNIQUE (user_id, challenge_id)
);
CREATE INDEX ON app.user_challenges (user_id, challenge_id);

-- Streak tracking (one row per user per streak type)
CREATE TABLE app.user_streaks (
  user_id       INT REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
  streak_type   TEXT NOT NULL DEFAULT 'daily_log',
  current       INT  NOT NULL DEFAULT 0,
  longest       INT  NOT NULL DEFAULT 0,
  last_activity DATE,
  PRIMARY KEY (user_id, streak_type)
);
```

---

### Downloadable Badge Flow (Free / Premium users)

Badge assets live in `web/public/badges/{slug}.png` and are served by
Vercel's CDN — no GCS, no signed URLs, no cost.

The URL is technically public, but the frontend only renders the download
button if `app.user_badges` contains a row for that user + badge. This is
soft enforcement — sufficient for a gaming stats app. If hard enforcement is
ever needed, a FastAPI endpoint can gate the URL behind a `user_badges` check.

```
User completes seasonal challenge
         ↓
FastAPI marks app.user_challenges.completed_at
         ↓
Milestone check → award badge → app.user_badges insert (earned_at = NOW())
         ↓
Return badge slug to frontend
         ↓
Frontend queries user_badges — row exists → show "Download Badge" button
         ↓
<a href="/badges/{slug}.png" download> served by Vercel CDN
         ↓
User downloads PNG → posts manually to social media
```

Trusted / Owner users skip the manual download — badge post fires through the
existing `_social_media_pipeline` using the `/badges/{slug}.png` URL.

**Asset location:**
```
web/public/badges/
  first_pb.png
  streak_7.png
  streak_30.png
  sessions_50.png
  sessions_100.png
  challenge_{slug}.png   ← one per seasonal challenge
  ...
```

---

### Phase checklist — Gamification

- [ ] Add `005_add_gamification.sql` migration (badges, user_badges, challenges, user_challenges, user_streaks)
- [ ] Seed `app.badges` with initial set (personal best, streak milestones, session counts)
- [ ] Implement `api/routers/gamification.py` — milestone check, challenge enrollment, streak update
- [ ] Wire streak update into `add_stats` route (fires after successful insert)
- [ ] Wire milestone check into `add_stats` route (personal best detection)
- [ ] Add badge PNG assets to `web/public/badges/` (one file per badge slug)
- [ ] Frontend: query `user_badges` on load — render download button only if row exists
- [ ] Wire badge post into `_social_media_pipeline` using `/badges/{slug}.png` URL (trusted/owner path)
- [ ] Add `ChallengesTab` or section to web app — enroll, track progress, download badge
- [ ] Add `BadgesPanel` to user profile / Stats page sidebar
- [ ] Add streak counter to Stats page header
- [ ] Owner: Admin panel UI to create/edit seasonal challenges (Phase 3)

---

## Phase 3 — Migration Realistic Timeline

**flask_app.py scope:** 3,300 lines, 41 routes. Not a single-day job.

### Chunk 1 — Scaffold + Core Personal Endpoints
- Scaffold `api/` folder structure
- Set up FastAPI app, lifespan, dual connection pools (`personal_pool` + `public_pool`)
- Port auth dependencies (`require_trusted`, `require_owner`)
- Port ~10 core personal endpoints: submit stat, get summary, streaks, edit stat, delete stat, OBS overlay

### Chunk 2 — Instagram/Post Queue + Automation Verification
- Port post queue, Instagram, and chart generation endpoints
- **Must verify Wednesday Instagram automation runs clean against FastAPI before moving on**
- This is the critical checkpoint — do not advance to Chunk 3 until automation confirms end-to-end
- Port remaining personal endpoints after automation verified

### Chunk 3 — Public Endpoints + Premium Tier + Cleanup
- Port public endpoints (game requests, leaderboard, public user management)
- Wire `role="premium"` into FastAPI auth dependency
- Update `next-auth.d.ts` role comment to include `"premium"`
- Full end-to-end test across web app
- Archive `flask_app.py` → `archive/flask_app.py`
- Remove Flask env vars from Render once verified clean

### Notes
- Each route needs Flask decorators translated to FastAPI `Depends()` — budget ~20 min/route
- Dual pool setup must be verified working before porting any route
- Do not archive Flask until all 41 routes are tested in FastAPI
- Wednesday automation run is the go/no-go gate between Chunk 2 and Chunk 3
- [ ] Bolt weekly recap endpoint + Resend email integration (post-launch)

---

## Phase 5 — Telegram Mini App (Option A: Wrapper)

**Goal:** Make the existing Next.js web app accessible inside Telegram through the
broadcast bot's menu button. No rewrite. No new hosting. Stripe continues to handle
all payments. This phase validates Telegram engagement before committing to Stars
integration (Option B).

**Written:** 2026-04-14

---

### What is actually being built

The Mini App is NOT built inside the bot. The bot is only the launcher.

```
User DMs your broadcast bot (@GameStatsBOLBot)
              ↓
Taps "Open Stats Tracker" menu button  ← set once in BotFather, points at Vercel URL
              ↓
Telegram opens WebView → loads https://yourdomain.vercel.app
              ↓
Your existing Next.js app runs — same code, same Vercel deployment
              ↓
Telegram SDK (3 lines of JS) provides user's Telegram identity automatically
              ↓
New FastAPI endpoint verifies identity, returns JWT → user is logged in
```

All build work is in the existing Next.js + FastAPI codebase.
The bot receives one new BotFather setting (menu button URL). That is all.

---

### How authentication changes

Currently: Google OAuth → NextAuth → FastAPI JWT

Inside Telegram: Telegram injects `initData` (a signed payload containing the
user's Telegram ID, name, and a hash). There is no sign-in form — Telegram
handles identity automatically.

```
Telegram WebView loads app
       ↓
window.Telegram.WebApp.initData  (available immediately, no user action)
       ↓
POST /api/telegram_login  (new FastAPI endpoint)
  → verify HMAC-SHA256 signature using bot token  ← security critical, must not be skipped
  → upsert dim_users on telegram_user_id
  → return FastAPI JWT (same shape as Google login)
       ↓
App behaves identically — all existing features work
```

Google login still works on the web. Telegram login only applies when running
inside the Telegram WebView. They share the same `dim_users` table — a user can
link both identities to one account later if needed.

---

### New files

| File | Purpose |
|---|---|
| `web/components/TelegramProvider.tsx` | Client component — initialises `window.Telegram.WebApp`, calls `.ready()`, syncs Telegram color scheme with app theme, exposes context |
| `web/hooks/useTelegramUser.ts` | Returns `{ isTelegram, telegramUser }` — used to conditionally hide Google sign-in UI |
| `api/routers/telegram_auth.py` | `POST /telegram_login` — verifies `initData` HMAC, upserts user, returns JWT |

---

### Changes to existing files

| File | Change |
|---|---|
| `web/app/layout.tsx` | Add Telegram SDK script tag to `<head>`; mount `<TelegramProvider />` |
| `web/lib/auth.ts` | On first load inside Telegram, exchange `initData` for a FastAPI JWT instead of triggering Google OAuth |
| `web/components/Navbar.tsx` | When `isTelegram`, hide Google sign-in button — user is already identified |
| `web/components/AccountPageClient.tsx` | Stripe checkout button opens in `_blank` — Telegram blocks same-tab navigation to external URLs |
| `api/main.py` | Register `telegram_auth.router` |
| `api/core/config.py` | No change — `TELEGRAM_BROADCAST_BOT_TOKEN` already in env and is reused for HMAC verification |

---

### Database change (one SQL statement, public DB)

```sql
ALTER TABLE dim.dim_users
  ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT UNIQUE;
```

No other schema changes needed.

---

### HMAC verification — security critical

Telegram provides a signed `initData` string. The signature must be verified
server-side before trusting any identity claim. A failed or skipped check allows
anyone to spoof a Telegram identity.

```python
# api/routers/telegram_auth.py
import hashlib, hmac as _hmac, urllib.parse

def verify_init_data(init_data: str, bot_token: str) -> dict:
    parsed   = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received = parsed.pop("hash", "")
    data_str = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret   = _hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = _hmac.new(secret, data_str.encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, received):
        raise ValueError("Invalid initData — possible spoofing attempt")
    return parsed  # safe to use after this point
```

---

### BotFather setup (one-time, after deploy)

1. Open `@BotFather` → `/mybots` → select your broadcast bot
2. **Bot Settings → Menu Button → Configure menu button**
3. Set URL: `https://yourdomain.vercel.app`
4. Set Button Text: `Open Stats Tracker`

This places a persistent button at the bottom of every DM with the bot.
One tap opens the Mini App.

Optional — add an inline launch button to channel session posts so subscribers
can open the app directly from a post:

```python
# In utils/telegram_broadcast.py — add to post_session() payload
"reply_markup": {
    "inline_keyboard": [[{
        "text": "📊 Open Stats Tracker",
        "web_app": {"url": "https://yourdomain.vercel.app"}
    }]]
}
```

---

### New env vars

| Var | Value | Notes |
|---|---|---|
| `TELEGRAM_MINI_APP_URL` | `https://yourdomain.vercel.app` | Used to build Stripe `success_url` deep link back into Mini App after checkout |

No new bot token — reuses `TELEGRAM_BROADCAST_BOT_TOKEN` for HMAC verification.

---

### Implementation checklist

**Database**
- [ ] Run `ALTER TABLE dim.dim_users ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT UNIQUE` on personal DB

**Backend (FastAPI)**
- [ ] Create `api/routers/telegram_auth.py` with `POST /telegram_login`
- [ ] Implement `verify_init_data()` HMAC check — reject anything that fails
- [ ] Upsert `dim_users` on `telegram_user_id`; return same JWT shape as Google login
- [ ] Register router in `api/main.py`

**Frontend (Next.js)**
- [ ] Add `<script src="https://telegram.org/js/telegram-web-app.js" />` to `layout.tsx` head
- [ ] Write `TelegramProvider.tsx` — call `window.Telegram.WebApp.ready()` and `.expand()` on mount
- [ ] Write `useTelegramUser.ts` hook
- [ ] On app load inside Telegram: POST `initData` to `/api/telegram-auth` (Next.js route handler) → exchange for NextAuth session
- [ ] `Navbar.tsx` — hide Google sign-in when `isTelegram === true`
- [ ] `AccountPageClient.tsx` — open Stripe checkout in `target="_blank"`

**Bot**
- [ ] Set Menu Button URL in BotFather (see above)
- [ ] Optionally add inline launch button to `post_session()` in `telegram_broadcast.py`

**Testing**
- [ ] Open bot on mobile Telegram → tap menu button → Mini App loads full-screen
- [ ] `initData` HMAC verification passes; tampered requests return 403
- [ ] User row created/matched in `dim_users` with correct `telegram_user_id`
- [ ] Submit stats, view dashboard, leaderboard, account — all work inside WebView
- [ ] Stripe checkout opens in external browser; returns to Mini App after payment
- [ ] App theme matches Telegram's current color scheme (light and dark)
- [ ] Tested on iOS and Android (WebView behavior differs slightly between platforms)

---

### Future — Option B: Add Telegram Stars alongside Stripe

Once Option A is live and engagement is validated, Stars can be added as a
second payment path without touching the Stripe flow. Stars purchases would
then qualify for Telegram's native affiliate program.

| Item | Work |
|---|---|
| "Pay with Stars" button on upgrade screen | Calls `Bot.sendInvoice` via Telegram Bot API |
| `PreCheckoutQuery` webhook handler | FastAPI: validate order, respond within 10 s |
| `successful_payment` webhook handler | FastAPI: upsert `app.subscriptions`, plan = premium |
| Telegram native affiliate program | Enable in `@BotFather` → set commission % and period |
| Parallel commission tracking | Stars commissions handled natively by Telegram; Stripe commissions stay in `app.referrals` |

Stars and Stripe map to the same `app.subscriptions` row — the `plan` column
does not care which payment method funded it.
