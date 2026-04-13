-- ============================================================
-- Supabase Schema
-- Translated from AWS Redshift
--
-- DEPLOYMENT GUIDE
-- ─────────────────────────────────────────────────────────────
-- Two separate Supabase projects run in parallel:
--
--   PERSONAL  — your data only, single-tenant, no RLS needed,
--               no billing tables, free tier forever.
--               Doubles as staging before public changes go live.
--
--   PUBLIC    — all users, multi-tenant, RLS required on every
--               table, includes billing + rate-limiting tables.
--
-- Sections below are labelled:
--   [BOTH]     run on personal + public
--   [PERSONAL] run on personal only  (OBS/streaming, third-party API integrations)
--   [PUBLIC]   run on public only    (billing, game requests, mobile push, AI limits)
--
-- FK DESIGN PRINCIPLE
-- ─────────────────────────────────────────────────────────────
-- ALL foreign keys reference dim.dim_users(user_id) — the INTEGER PK.
-- user_email lives in dim.dim_users only. No child table stores user_email
-- as a FK column. This means:
--   - Email changes in dim.dim_users never orphan child rows
--   - Integer FKs = smaller indexes, faster JOINs
--   - Deletion cascades automatically from a single root row
-- Queries needing email → JOIN dim.dim_users ON user_id.
-- The JWT payload includes both user_id and email — use user_id
-- for all DB writes/lookups.
--
-- Public users get the Download Chart button — social media auto-posting
-- (post_queue, user_integrations) is a personal streaming feature only.
--
-- Run order: Schemas → dim [BOTH] → dim [PERSONAL] → fact → app [BOTH]
--            → app [PERSONAL] → app [PUBLIC] → triggers → indexes → analytics
-- ============================================================


-- ══════════════════════════════════════════════════════════════
-- SCHEMAS                                              [BOTH]
-- ══════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS app;


-- ══════════════════════════════════════════════════════════════
-- DIMENSION TABLES                                     [BOTH]
-- ══════════════════════════════════════════════════════════════

-- ── dim.dim_users ─────────────────────────────────────────────
-- The root of every FK chain. All child tables reference user_id.
--
-- Tiers (mutually exclusive, single source of truth):
--   role = 'trusted'    → developer / owner / promoted loyal user
--   role = 'registered' → general public via Google auth
--   (no row)            → guest — landing page only, no app access
--
-- is_trusted is a generated column kept for backward compatibility.
-- To promote a user:  UPDATE dim.dim_users SET role = 'trusted' WHERE user_id = X;
CREATE TABLE IF NOT EXISTS dim.dim_users (
    user_id    INT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL UNIQUE,
    role       TEXT NOT NULL DEFAULT 'registered'
                   CHECK (role IN ('registered', 'trusted')),
    is_trusted BOOLEAN GENERATED ALWAYS AS (role = 'trusted') STORED,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── dim.dim_games ─────────────────────────────────────────────
-- PERSONAL: your curated game list.
-- PUBLIC:   shared catalog — users contribute games.
--           created_by + is_verified added in the [PUBLIC] section below.
CREATE TABLE IF NOT EXISTS dim.dim_games (
    game_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_name        VARCHAR(255) NOT NULL,
    game_installment VARCHAR(255),
    game_genre       VARCHAR(255),
    game_subgenre    VARCHAR(255),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    last_played_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_name, game_installment)
);

-- ── dim.dim_players ───────────────────────────────────────────
-- Player limits enforced in application layer (not DB constraint):
--   Free tier:    2 players per user
--   Premium tier: 5 players per user (requires active subscription)
CREATE TABLE IF NOT EXISTS dim.dim_players (
    player_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    user_id     INTEGER      NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(player_name, user_id)
);


-- ══════════════════════════════════════════════════════════════
-- DIMENSION TABLES — PERSONAL ONLY                    [PERSONAL]
-- ══════════════════════════════════════════════════════════════

-- ── dim.dim_dashboard_state ───────────────────────────────────
-- Drives the OBS overlay. Single-row table — state_id = 1 only.
CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
    state_id          INT PRIMARY KEY DEFAULT 1,
    current_player_id INTEGER,
    current_game_id   INTEGER,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);


-- ══════════════════════════════════════════════════════════════
-- FACT TABLES                                          [BOTH]
-- ══════════════════════════════════════════════════════════════

-- ── fact.fact_game_stats ──────────────────────────────────────
-- source: 'manual' | 'riot' | 'steam' | future integrations
CREATE TABLE IF NOT EXISTS fact.fact_game_stats (
    stat_id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_id               INTEGER REFERENCES dim.dim_games(game_id),
    player_id             INTEGER REFERENCES dim.dim_players(player_id) ON DELETE CASCADE,
    stat_type             VARCHAR(50)  NOT NULL,
    stat_value            INTEGER,
    game_mode             VARCHAR(255),
    solo_mode             INTEGER,
    party_size            VARCHAR(20),
    game_level            INTEGER,
    win                   INTEGER,
    ranked                INTEGER,
    pre_match_rank_value  VARCHAR(50),
    post_match_rank_value VARCHAR(50),
    overtime              INTEGER      NOT NULL DEFAULT 0,
    difficulty            VARCHAR(20),
    input_device          VARCHAR(30)  NOT NULL DEFAULT 'Controller',
    platform              VARCHAR(20)  NOT NULL DEFAULT 'PC',
    first_session_of_day  INTEGER      NOT NULL DEFAULT 1,
    was_streaming         INTEGER      NOT NULL DEFAULT 0,
    played_at             TIMESTAMPTZ  DEFAULT NOW(),
    source                TEXT         NOT NULL DEFAULT 'manual',
    is_editable           BOOLEAN      NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_win        CHECK (win       IS NULL OR win       IN (0, 1)),
    CONSTRAINT chk_ranked     CHECK (ranked    IS NULL OR ranked    IN (0, 1)),
    CONSTRAINT chk_overtime   CHECK (overtime  IN (0, 1)),
    CONSTRAINT chk_solo_mode  CHECK (solo_mode IS NULL OR solo_mode IN (0, 1)),
    CONSTRAINT chk_stat_value CHECK (stat_value >= 0 AND stat_value <= 100000),
    CONSTRAINT chk_played_at  CHECK (played_at <= NOW() + INTERVAL '5 minutes')
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — SHARED                                  [BOTH]
-- ══════════════════════════════════════════════════════════════

-- ── app.ml_model_runs ─────────────────────────────────────────
-- model_type: 'logistic_regression' | 'random_forest' | 'xgboost'
-- gcs_path: gs://bucket/models/{user_id}/{game_id}/{stat_type}/{model_type}.joblib
CREATE TABLE IF NOT EXISTS app.ml_model_runs (
    id                  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    game_id             INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    stat_type           TEXT    NOT NULL,
    model_type          TEXT    NOT NULL,
    r2_score            NUMERIC(5, 4),
    mae                 NUMERIC(10, 2),
    sessions_used       INTEGER,
    feature_importances JSONB,
    model_coefficients  JSONB,
    gcs_path            TEXT,
    trained_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── app.leaderboard_entries ───────────────────────────────────
-- Pre-aggregated best-value snapshot per (user, game, stat_type).
-- Refreshed after each stat submission.
CREATE TABLE IF NOT EXISTS app.leaderboard_entries (
    id             INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    player_name    TEXT    NOT NULL,
    game_id        INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    stat_type      TEXT    NOT NULL,
    best_value     NUMERIC,
    total_sessions INTEGER,
    last_updated   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, game_id, stat_type)
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — PERSONAL ONLY                          [PERSONAL]
-- ══════════════════════════════════════════════════════════════

-- ── app.post_queue ────────────────────────────────────────────
-- Social media auto-post queue. Personal streaming only.
-- ⚠️  Currently on a separate Render Postgres DB (QUEUE_DATABASE_URL).
-- Run on personal Supabase ONLY when migrating the queue off Render.
CREATE TABLE IF NOT EXISTS app.post_queue (
    queue_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id    VARCHAR(50),
    platform     VARCHAR(20),
    image_url    VARCHAR(1000),
    caption      TEXT,
    status       VARCHAR(20)  DEFAULT 'pending',
    scheduled_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ── app.user_integrations ─────────────────────────────────────
-- Connected third-party gaming accounts (Riot, Steam, etc.).
-- platform: 'riot' | 'steam' | 'activision'
CREATE TABLE IF NOT EXISTS app.user_integrations (
    id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    platform         TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    platform_username TEXT,
    access_token     TEXT,
    refresh_token    TEXT,
    token_expires_at TIMESTAMPTZ,
    connected_at     TIMESTAMPTZ DEFAULT NOW(),
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE(user_id, platform)
);

-- ── app.integration_imports ───────────────────────────────────
-- Deduplication log — prevents re-importing the same external match.
CREATE TABLE IF NOT EXISTS app.integration_imports (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    platform          TEXT NOT NULL,
    external_match_id TEXT NOT NULL,
    imported_at       TIMESTAMPTZ DEFAULT NOW(),
    game_stat_id      INTEGER REFERENCES fact.fact_game_stats(stat_id) ON DELETE SET NULL,
    UNIQUE(platform, external_match_id, user_id)
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — PUBLIC ONLY                             [PUBLIC]
-- ══════════════════════════════════════════════════════════════

-- ── app.game_requests ────────────────────────────────────────
-- status: 'pending' | 'approved' | 'rejected'
CREATE TABLE IF NOT EXISTS app.game_requests (
    request_id        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           INTEGER     NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    game_name         TEXT        NOT NULL,
    game_installment  TEXT,
    game_genre        TEXT,
    game_subgenre     TEXT,
    status            TEXT        NOT NULL DEFAULT 'pending',
    reviewed_by       INTEGER     REFERENCES dim.dim_users(user_id),
    rejection_reason  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at       TIMESTAMPTZ,
    CONSTRAINT chk_request_status CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- ── app.push_tokens ───────────────────────────────────────────
-- Expo push tokens. One user can have multiple devices.
-- platform: 'ios' | 'android'
CREATE TABLE IF NOT EXISTS app.push_tokens (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    expo_token   TEXT NOT NULL UNIQUE,
    platform     TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── app.ai_usage ──────────────────────────────────────────────
-- Bolt AI query counts per user per day.
-- Upsert pattern:
--   INSERT INTO app.ai_usage (user_id, query_date)
--   VALUES ($1, CURRENT_DATE)
--   ON CONFLICT (user_id, query_date)
--   DO UPDATE SET query_count = app.ai_usage.query_count + 1;
-- Free: 20/month. Premium: 200/month. Trusted: 200/month. Owner: unlimited.
CREATE TABLE IF NOT EXISTS app.ai_usage (
    user_id     INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    query_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
    query_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, query_date)
);

-- ── app.subscriptions ─────────────────────────────────────────
-- Stripe billing state per user.
-- plan: 'free' | 'premium'
CREATE TABLE IF NOT EXISTS app.subscriptions (
    id                     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                INTEGER NOT NULL UNIQUE REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    plan                   TEXT NOT NULL DEFAULT 'free'
                               CHECK (plan IN ('free', 'premium')),
    billing_interval       TEXT CHECK (billing_interval IN ('month', 'year')),
    stripe_customer_id     TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    started_at             TIMESTAMPTZ DEFAULT NOW(),
    expires_at             TIMESTAMPTZ,
    cancelled_at           TIMESTAMPTZ,
    is_active              BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── app.leaderboard_opts_in ───────────────────────────────────
-- Consent gate — users opt in per game for their stats to appear publicly.
CREATE TABLE IF NOT EXISTS app.leaderboard_opts_in (
    user_id     INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    game_id     INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    is_public   BOOLEAN NOT NULL DEFAULT FALSE,
    opted_in_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

-- ── app.power_pack_purchases ──────────────────────────────────
-- One-time data export purchase. Idempotent on conflict.
-- Run on PUBLIC pool only.
CREATE TABLE IF NOT EXISTS app.power_pack_purchases (
    user_id           INTEGER     NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    purchased_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    amount_cents      INTEGER     NOT NULL,
    tier_ceiling_rows INTEGER     NOT NULL DEFAULT 499,  -- row ceiling at time of purchase; enforced on download
    stripe_session_id TEXT,
    PRIMARY KEY (user_id)
);


-- ══════════════════════════════════════════════════════════════
-- PUBLIC SCHEMA MODIFICATIONS                          [PUBLIC]
-- ══════════════════════════════════════════════════════════════

-- ── dim.dim_dashboard_state (public version) ──────────────────
-- Replaces the single-row personal version. One row per user.
-- DO NOT run on personal.
--
-- CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
--     user_id           INTEGER PRIMARY KEY REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
--     current_player_id INTEGER,
--     current_game_id   INTEGER,
--     updated_at        TIMESTAMPTZ DEFAULT NOW()
-- );

-- ── dim.dim_games additions (public version) ──────────────────
-- Run after CREATE TABLE dim.dim_games on public only.
--
-- ALTER TABLE dim.dim_games
--     ADD COLUMN IF NOT EXISTS created_by  INTEGER REFERENCES dim.dim_users(user_id),
--     ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE;


-- ══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)                             [PUBLIC]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run on personal.
--
-- ⚠️  Your stack uses NextAuth + FastAPI JWT, NOT Supabase Auth.
-- FastAPI connects via asyncpg — it bypasses RLS entirely.
-- These policies protect direct PostgREST access only.
--
-- All RLS policies resolve user_id from the JWT email:
--   (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')

-- ALTER TABLE dim.dim_games ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "all_read_games" ON dim.dim_games FOR SELECT USING (true);

-- ALTER TABLE dim.dim_users ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_row" ON dim.dim_users
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ALTER TABLE dim.dim_players ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_players" ON dim.dim_players
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE fact.fact_game_stats ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_stats" ON fact.fact_game_stats
--     FOR ALL USING (
--         player_id IN (
--             SELECT player_id FROM dim.dim_players
--             WHERE user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--         )
--     );

-- ALTER TABLE app.ml_model_runs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_model_runs" ON app.ml_model_runs
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE app.leaderboard_entries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_entries_write" ON app.leaderboard_entries
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );
-- CREATE POLICY "public_leaderboard_read" ON app.leaderboard_entries
--     FOR SELECT USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--         OR user_id IN (
--             SELECT user_id FROM app.leaderboard_opts_in
--             WHERE game_id = app.leaderboard_entries.game_id AND is_public = TRUE
--         )
--     );

-- ALTER TABLE app.game_requests ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_requests" ON app.game_requests
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE app.ai_usage ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_usage" ON app.ai_usage
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE app.subscriptions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_subscription" ON app.subscriptions
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE app.leaderboard_opts_in ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_manage_own_optin" ON app.leaderboard_opts_in
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );
-- CREATE POLICY "public_optin_read" ON app.leaderboard_opts_in
--     FOR SELECT USING (true);

-- ALTER TABLE app.push_tokens ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_tokens" ON app.push_tokens
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- ALTER TABLE app.power_pack_purchases ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_purchases" ON app.power_pack_purchases
--     FOR ALL USING (
--         user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = auth.jwt()->>'email')
--     );

-- Personal-only tables — not present on public, no RLS needed:
--   app.post_queue | app.user_integrations | app.integration_imports
--   dim.dim_dashboard_state


-- ══════════════════════════════════════════════════════════════
-- AUTO-UPDATE TRIGGER                                  [BOTH]
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dim_users_updated_at
    BEFORE UPDATE ON dim.dim_users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ══════════════════════════════════════════════════════════════
-- PERFORMANCE INDEXES                                  [BOTH]
-- ══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_fgs_player_game
    ON fact.fact_game_stats (player_id, game_id);

CREATE INDEX IF NOT EXISTS idx_fgs_played_at
    ON fact.fact_game_stats (played_at DESC);

CREATE INDEX IF NOT EXISTS idx_fgs_game_stat_type
    ON fact.fact_game_stats (game_id, stat_type);

CREATE INDEX IF NOT EXISTS idx_players_user_id
    ON dim.dim_players (user_id);

CREATE INDEX IF NOT EXISTS idx_games_name
    ON dim.dim_games (game_name);

CREATE INDEX IF NOT EXISTS idx_post_queue_status
    ON app.post_queue (status, created_at);

CREATE INDEX IF NOT EXISTS idx_game_requests_status
    ON app.game_requests (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ml_runs_user_game
    ON app.ml_model_runs (user_id, game_id, model_type, trained_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_integrations_active
    ON app.user_integrations (user_id, platform)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_integration_imports_dedup
    ON app.integration_imports (platform, external_match_id);

CREATE INDEX IF NOT EXISTS idx_leaderboard_entries_game_stat
    ON app.leaderboard_entries (game_id, stat_type, best_value DESC);

CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date
    ON app.ai_usage (user_id, query_date DESC);


-- ══════════════════════════════════════════════════════════════
-- ANALYTICS SCHEMA — MATERIALIZED VIEWS               [BOTH]
-- ══════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_heatmap AS
SELECT
    player_id,
    game_id,
    EXTRACT(DOW  FROM played_at AT TIME ZONE 'America/Los_Angeles')::INT AS dow,
    EXTRACT(HOUR FROM played_at AT TIME ZONE 'America/Los_Angeles')::INT AS hour,
    COUNT(*) AS session_count
FROM fact.fact_game_stats
GROUP BY player_id, game_id, dow, hour;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_heatmap
    ON analytics.mv_heatmap (player_id, game_id, dow, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_session_days AS
SELECT
    player_id,
    game_id,
    (played_at AT TIME ZONE 'America/Los_Angeles')::DATE AS session_date
FROM fact.fact_game_stats
GROUP BY player_id, game_id, session_date
ORDER BY player_id, game_id, session_date DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_session_days
    ON analytics.mv_session_days (player_id, game_id, session_date);

-- Leaderboard percentiles — PUBLIC only, uncomment when leaderboard_opts_in has data.
--
-- CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_leaderboard_percentiles AS
-- SELECT
--     l.game_id,
--     l.stat_type,
--     l.user_id,
--     l.best_value AS avg_value,
--     PERCENT_RANK() OVER (
--         PARTITION BY l.game_id, l.stat_type
--         ORDER BY l.best_value DESC
--     ) AS percentile_rank,
--     COUNT(*) OVER (PARTITION BY l.game_id, l.stat_type) AS sample_size
-- FROM app.leaderboard_entries l
-- JOIN app.leaderboard_opts_in o ON l.user_id = o.user_id AND l.game_id = o.game_id
-- WHERE o.is_public = TRUE;
--
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_leaderboard_percentiles
--     ON analytics.mv_leaderboard_percentiles (user_id, game_id, stat_type);
