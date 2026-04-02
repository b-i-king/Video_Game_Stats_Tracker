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

**Status as of 2026-04-01:** `api/` scaffold created and committed. Flask stays
live on existing Render service. FastAPI deploys as a second Render service.
Cut-over = flip `NEXT_PUBLIC_FLASK_API_URL` on Vercel. Flask archived to
`archive/backend/flask_app.py` 24 hours after cut-over with no regressions.

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
| `docs/fastapi_app.py` | FastAPI migration placeholder — becomes `api/main.py` |
| `assets/sql/supabase_schema.sql` | Source of truth for both Supabase projects |
| `archive/flask_app.py` | Flask archived after FastAPI cut-over (~2026-04-07) |
| `api/routers/ml.py` | ML endpoints — Phase 4 |
| `web/components/InsightsTab.tsx` | Insights tab — Phase 4 |
| `web/components/SummaryTab.tsx` | Add PredictionBanner — Phase 4 |
