# Cost Optimization Guide
## Stack: Next.js (Vercel) + FastAPI (Render) + Supabase

---

## Target Monthly Cost

| Stage | Services | Cost |
|---|---|---|
| Personal live | Render Starter ($7) + Supabase Pro ($25) + Vercel Hobby ($0) | **$32/mo** |
| Personal + Public | + second Supabase Pro project ($25) + Vercel Pro ($20, required for commercial) | **$77/mo** |
| + ML live | + Render Standard ($25, only if OOM on Starter with XGBoost) | **$102/mo** |

> **Supabase Pro — $25/month per project** includes:
> - 8 GB database, 250 GB bandwidth, 100 GB file storage
> - Shared PgBouncer pooler (port 6543, transaction mode) — free, sufficient for FastAPI
> - Dedicated pooler available on Pro+ at additional cost — **not needed** for this stack
>   (shared pooler handles asyncpg + `statement_cache_size=0` correctly)
> - Daily backups, custom domains, email support
>
> **Pooler strategy (confirmed):**
> - FastAPI (asyncpg) → port **6543** transaction pooler with `statement_cache_size=0`
> - Flask/Lambda (psycopg2) → port **5432** session pooler (prepared statements require this)
> - Next.js direct Supabase calls → PostgREST REST API (no pooler needed, uses anon key + RLS)
>
> **Status as of 2026-04-01:** Redshift archived ($0 AWS), Streamlit archived.
> Neon eliminated after `app.post_queue` migrates to Supabase in Phase 3 step 6.

---

## Step 1 — Eliminate Neon

Migrate `post_queue` into Supabase personal project. One fewer service,
one fewer connection string to manage.

```sql
-- Run in Supabase SQL editor
CREATE TABLE IF NOT EXISTS app.post_queue (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload     JSONB        NOT NULL,
    status      TEXT         NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
```

Update `NEON_DB_URL` references in `flask_app.py` / `fastapi_app.py` to use
the Supabase pooled connection string (port 6543).

---

## Step 2 — Always Use the Pooled Connection String

Supabase gives two connection strings. Use the **pooled** one for all
application traffic.

| Type | Port | Use for |
|---|---|---|
| Direct | 5432 | Database migrations only |
| **Pooled (pgBouncer)** | **6543** | **All FastAPI / app traffic** |

Direct connections count against your Supabase compute limit.
Pooled connections go through pgBouncer transaction mode and do not.

```python
# fastapi_app.py — lifespan pool setup
SUPABASE_DB_URL = os.environ["SUPABASE_DB_URL"]  # must be port 6543

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(
        dsn=SUPABASE_DB_URL,
        min_size=2,
        max_size=10,
    )
    yield
    await app.state.pool.close()
```

---

## Step 3 — Bypass FastAPI for Simple Reads (Next.js → Supabase Direct)

For endpoints that are just authenticated SELECT queries, call Supabase's
PostgREST API directly from Next.js — no FastAPI roundtrip.

```
Before: Next.js → Render (FastAPI) → Supabase   (2 network hops)
After:  Next.js → Supabase PostgREST             (1 network hop)
```

**Endpoints to migrate to direct Supabase calls:**

| Current Flask/FastAPI endpoint | Table |
|---|---|
| `/api/get_games` | `dim.dim_games` |
| `/api/get_players` | `dim.dim_players` |
| `/api/get_game_ranks/<id>` | `fact.fact_game_stats` |
| `/api/get_game_modes/<id>` | `fact.fact_game_stats` |
| `/api/get_game_stat_types/<id>` | `fact.fact_game_stats` |

```typescript
// web/lib/supabase.ts
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function getGames(userId: string) {
  const { data } = await supabase
    .from("dim_games")
    .select("game_id, game_name, game_installment")
    .eq("user_id", userId)
    .order("game_name");
  return data ?? [];
}
```

**Keep FastAPI for:** analytics (heatmap, streaks, CI), ML training/inference,
Gemini NL2SQL, Instagram posting — anything with business logic.

---

## Step 4 — Materialized Views for Analytics Queries

Pre-aggregate expensive full-table scans. Refresh after each stat insert
via a FastAPI background task.

```sql
-- Run in Supabase SQL editor

CREATE SCHEMA IF NOT EXISTS analytics;

-- Heatmap: session frequency by day-of-week × hour (PST)
CREATE MATERIALIZED VIEW analytics.mv_heatmap AS
SELECT
    player_id,
    game_id,
    EXTRACT(DOW  FROM played_at AT TIME ZONE 'America/Los_Angeles')::INT AS dow,
    EXTRACT(HOUR FROM played_at AT TIME ZONE 'America/Los_Angeles')::INT AS hour,
    COUNT(*) AS session_count
FROM fact.fact_game_stats
GROUP BY player_id, game_id, dow, hour;

CREATE UNIQUE INDEX ON analytics.mv_heatmap (player_id, game_id, dow, hour);

-- Streaks: distinct session days per player/game
CREATE MATERIALIZED VIEW analytics.mv_session_days AS
SELECT
    player_id,
    game_id,
    (played_at AT TIME ZONE 'America/Los_Angeles')::DATE AS session_date
FROM fact.fact_game_stats
GROUP BY player_id, game_id, session_date
ORDER BY player_id, game_id, session_date DESC;

CREATE UNIQUE INDEX ON analytics.mv_session_days (player_id, game_id, session_date);
```

```python
# fastapi_app.py — refresh after stat insert
from fastapi import BackgroundTasks

async def _refresh_views(pool, player_id: int, game_id: int):
    async with pool.acquire() as conn:
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_heatmap;")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_session_days;")

@router.post("/api/add_stats")
async def add_stats(payload: AddStatsPayload, background_tasks: BackgroundTasks, ...):
    # ... insert stats ...
    background_tasks.add_task(_refresh_views, request.app.state.pool, player_id, game_id)
    return {"message": "Stats added"}
```

---

## Step 5 — In-Memory Model Cache for ML

Avoid reloading ML models from Supabase Storage on every prediction request.
Cache by `(user_email, game_id)` with a TTL.

```python
# fastapi_app.py
import pickle
from functools import lru_cache

_model_cache: dict = {}

async def load_model(pool, user_email: str, game_id: int):
    key = (user_email, game_id)
    if key in _model_cache:
        return _model_cache[key]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT model_artifact FROM app.ml_model_runs
            WHERE user_email = $1 AND game_id = $2
            ORDER BY trained_at DESC LIMIT 1
        """, user_email, game_id)
    if row:
        model = pickle.loads(row["model_artifact"])
        _model_cache[key] = model
    return _model_cache.get(key)
```

**For Logistic Regression specifically:** store only the coefficients as JSONB
(not a binary pickle). Frontend computes `P(win)` in JavaScript — zero
inference calls to FastAPI for what-if sliders.

```typescript
// Pure frontend inference — no API call on slider drag
function predictWin(
  coefs: Record<string, number>,
  intercept: number,
  stats: Record<string, number>
): number {
  const logit =
    intercept +
    Object.entries(coefs).reduce(
      (sum, [feat, coef]) => sum + coef * (stats[feat] ?? 0),
      0
    );
  return 1 / (1 + Math.exp(-logit)); // sigmoid → P(win)
}
```

---

## Step 6 — ISR for Public Pages (Vercel)

Once the public app has users, leaderboard and public profiles do not need
real-time data. Use Next.js Incremental Static Regeneration to cache pages
server-side and revalidate on a schedule.

```typescript
// app/leaderboard/page.tsx
export const revalidate = 300; // revalidate every 5 minutes

export default async function LeaderboardPage() {
  const data = await getLeaderboard(); // runs at build + revalidation only
  return <LeaderboardTable data={data} />;
}
```

This eliminates a serverless function invocation per visitor on the
highest-traffic public page.

---

## Migration Timeline

| Date | Milestone |
|---|---|
| ✅ 2026-03-31 | Supabase migration live (personal) |
| ✅ 2026-04-01 | Redshift archived ($0 AWS), Streamlit archived |
| ~2026-04-07 | FastAPI migration, Neon eliminated (post_queue → Supabase) |
| After FastAPI stable | Steps 3–4: direct Supabase calls + materialized views |
| After first paying user | Second Supabase Pro + Vercel Pro ($45/mo increase) |
| After 10 premium users | ML public storage viable, leaderboard ISR (Step 6) |
| After ML endpoints live | Step 5: model cache + LR frontend inference |

---

## Phase-Gated Cost Strategy

The single biggest lever is **don't pay for public infrastructure until you have public users.** Every feature below can be deferred until a revenue trigger is met.

### Stage 0 — Personal only (current) · $32/mo

All premium features work for you personally at $32/mo. Nothing changes.

| Feature | Personal cost | How |
|---|---|---|
| ML (LR) | ~$0 | Coefficients stored as JSONB in Supabase |
| ML (RF / XGBoost) | ~$0.02/mo | Pickle in GCS bucket (already paying $0 for it) |
| AI / Bolt | ~$0–$1/mo | Gemini Flash billed per token; your usage is minimal |
| Game API | $0 | Direct Supabase queries via FastAPI personal pool |
| Leaderboard | N/A | Personal only — no leaderboard |

---

### Stage 1 — Public launch trigger · +$45/mo → $77/mo

Add the second Supabase Pro project + Vercel Pro **only when you have paying users.**
At $10/month premium: **5 premium users = break-even on public infrastructure.**

| New cost | What unlocks |
|---|---|
| Supabase Pro #2 ($25) | Public user data, RLS, game catalog, leaderboard |
| Vercel Pro ($20) | Commercial use allowed, team features, higher limits |

Break-even math:
```
Public infra cost:  $45/mo
Premium plan:       $10/user/mo
Break-even:         5 premium users
Profit starts at:   6 premium users (+$10/mo net)
```

---

### Stage 2 — ML public storage · included in Supabase Pro #2

Supabase Pro includes **100 GB file storage** — public ML models (RF/XGBoost pickles)
live here at no extra cost until you exceed 100 GB, which requires thousands of users.

Cost controls already in the plan:
- **50-session gate** — no model trained until user has 50 sessions (prevents wasted compute on new users)
- **90-day eviction** — inactive user models deleted from Supabase Storage automatically
- **LR always free** — coefficients are JSONB, never touch file storage

---

### Stage 3 — AI / Bolt cost controls

Gemini pricing (approximate):
| Model | Input | Output |
|---|---|---|
| `gemini-2.0-flash` (premium/trusted) | ~$0.075/1M tokens | ~$0.30/1M tokens |
| `gemini-2.0-flash-lite` (free tier) | ~$0.04/1M tokens | ~$0.15/1M tokens |

A typical Bolt message (game context + question + reply) ≈ 800 tokens total.

| Tier | Messages/mo | Est. Gemini cost/user |
|---|---|---|
| Free | 20 | ~$0.001 |
| Premium | 200 | ~$0.02 |
| Trusted | Unlimited | track and review monthly |

At $10/month premium, AI cost per premium user is **< $0.03/mo** — negligible.
The main control is the `app.ai_usage` monthly cap enforced in `/api/ask`.

Additional controls (implement before public launch):
- **15-minute server cache** on `/api/get_ticker_facts` (already in Flask) — prevents repeated identical AI calls
- **Last-3-session context only** — keeps prompt tokens bounded regardless of history size
- **No AI for guests** — blocked at JWT auth layer, zero cost

---

### Stage 4 — Leaderboard cost (near zero until scale)

The leaderboard is a public good — it drives user acquisition and is free to run:
- Materialized views (Step 4) eliminate full-table scans — one DB refresh per stat submit
- ISR on Vercel (Step 6) — leaderboard page cached for 5 minutes, no serverless invocation per visitor
- Supabase PostgREST serves leaderboard reads directly from Next.js — no Render roundtrip

Leaderboard only becomes a cost concern above ~10,000 monthly active users.

---

### Stage 5 — Game Integration API cost

| Caller | Method | Cost |
|---|---|---|
| Personal web app | FastAPI personal pool → Supabase | Covered by $7 Render + $25 Supabase |
| Public web app (simple reads) | Next.js → PostgREST direct | $0 extra (Step 3) |
| Public web app (analytics) | FastAPI public pool → Supabase | Covered by $25 Supabase #2 |
| Instagram Lambda | psycopg2 → Supabase session pooler | $0 (AWS Lambda free tier) |

The only material compute cost is Render. FastAPI + asyncpg runs ~180MB RAM,
meaning the $7 Starter tier handles all API traffic including ML inference for LR
models. Only upgrade to Standard ($25) if XGBoost inference causes OOM — and
only after that is confirmed in production logs.

---

## Render RAM Reference

| Tier | RAM | Sufficient for |
|---|---|---|
| Free ($0) | 512MB | Flask/FastAPI + LR only; spins down |
| **Starter ($7)** | **512MB** | **FastAPI + LR + RF/XGBoost (FastAPI is lean enough)** |
| Standard ($25) | 2GB | Only needed if OOM errors appear with RF/XGBoost loaded |

FastAPI + uvicorn + asyncpg runs in ~180MB vs Flask + gunicorn + psycopg2
at ~350MB. This is why Starter ($7) covers ML on FastAPI where it wouldn't
on Flask.
