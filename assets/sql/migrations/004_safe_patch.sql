-- ══════════════════════════════════════════════════════════════════════
-- MIGRATION 004 — Safe patch for live databases with real data
--
-- RULES:
--   • Never DROP anything — only ADD COLUMN IF NOT EXISTS / CREATE IF NOT EXISTS
--   • fact.fact_game_stats is untouched — all 240+ rows preserved
--   • Each section is labelled [PERSONAL], [PUBLIC], or [BOTH]
--   • Run each section in the SQL editor of the correct Supabase project
--
-- RUN ORDER:
--   1. [BOTH]     — dim / fact / app shared tables
--   2. [PERSONAL] — owner user row, player linkage
--   3. [PUBLIC]   — game_requests columns, power_pack, public-only tables
-- ══════════════════════════════════════════════════════════════════════


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 1 — SCHEMAS & SHARED DIMENSION TABLES               [BOTH]
-- ══════════════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS analytics;

-- dim.dim_users — root of every FK chain (INTEGER PK)
CREATE TABLE IF NOT EXISTS dim.dim_users (
    user_id    INT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL UNIQUE,
    role       TEXT NOT NULL DEFAULT 'registered'
                   CHECK (role IN ('registered', 'trusted')),
    is_trusted BOOLEAN GENERATED ALWAYS AS (role = 'trusted') STORED,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- dim.dim_games — game catalog (already exists; idempotent)
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

-- dim.dim_players — add user_id FK if the column is missing
-- (safe: does nothing if column already exists)
CREATE TABLE IF NOT EXISTS dim.dim_players (
    player_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    user_id     INTEGER      NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(player_name, user_id)
);

-- If dim.dim_players already exists but lacks user_id, add it:
ALTER TABLE dim.dim_players
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES dim.dim_users(user_id) ON DELETE CASCADE;


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 2 — FACT TABLE (existing data preserved)             [BOTH]
-- ══════════════════════════════════════════════════════════════════════

-- fact.fact_game_stats already exists with your 240+ rows.
-- This only adds missing columns — no data is touched.

ALTER TABLE fact.fact_game_stats
    ADD COLUMN IF NOT EXISTS source      TEXT    NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS is_editable BOOLEAN NOT NULL DEFAULT TRUE;


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 3 — SHARED APP TABLES                                [BOTH]
-- ══════════════════════════════════════════════════════════════════════

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


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 4 — PERSONAL ONLY: owner user row + player linkage  [PERSONAL]
-- ══════════════════════════════════════════════════════════════════════

-- Step 4a: Insert your owner row into dim.dim_users (if not already there).
-- Replace YOUR_EMAIL@gmail.com with your actual Google account email.
INSERT INTO dim.dim_users (user_email, role)
VALUES ('YOUR_EMAIL@gmail.com', 'trusted')
ON CONFLICT (user_email) DO NOTHING;

-- Step 4b: If your dim.dim_players rows have a NULL user_id (old schema had
-- no user_id column), link them to your owner user_id now.
-- This sets user_id on all players that currently have no owner assigned.
UPDATE dim.dim_players
SET user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = 'YOUR_EMAIL@gmail.com')
WHERE user_id IS NULL;

-- Step 4c: Add NOT NULL constraint once all rows are filled.
-- Only run this AFTER confirming zero NULLs with:
--   SELECT COUNT(*) FROM dim.dim_players WHERE user_id IS NULL;  -- must return 0
-- Then uncomment:
-- ALTER TABLE dim.dim_players ALTER COLUMN user_id SET NOT NULL;


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 5 — PERSONAL ONLY: dashboard state & integrations   [PERSONAL]
-- ══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
    state_id          INT PRIMARY KEY DEFAULT 1,
    current_player_id INTEGER,
    current_game_id   INTEGER,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS app.integration_imports (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    platform          TEXT NOT NULL,
    external_match_id TEXT NOT NULL,
    imported_at       TIMESTAMPTZ DEFAULT NOW(),
    game_stat_id      INTEGER REFERENCES fact.fact_game_stats(stat_id) ON DELETE SET NULL,
    UNIQUE(platform, external_match_id, user_id)
);


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 6 — PUBLIC ONLY: fix app.game_requests columns       [PUBLIC]
-- ══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app.game_requests (
    request_id       INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          INTEGER     NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    game_name        TEXT        NOT NULL,
    game_installment TEXT,
    game_genre       TEXT,
    game_subgenre    TEXT, 
    status           TEXT        NOT NULL DEFAULT 'pending',
    reviewed_by      INTEGER     REFERENCES dim.dim_users(user_id),
    rejection_reason TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at      TIMESTAMPTZ,
    CONSTRAINT chk_request_status CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- These columns are used by the routers but were missing from the schema.

ALTER TABLE app.game_requests
    ADD COLUMN IF NOT EXISTS game_genre      TEXT,
    ADD COLUMN IF NOT EXISTS game_subgenre   TEXT,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- NOTE: The owner list query was also selecting 'user_email' directly from
-- this table, but the table only stores user_id. The router has been updated
-- to JOIN dim.dim_users instead — no column change needed here.


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 7 — PUBLIC ONLY: power_pack tier ceiling             [PUBLIC]
-- ══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app.power_pack_purchases (
    user_id           INTEGER     NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    purchased_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    amount_cents      INTEGER     NOT NULL,
    tier_ceiling_rows INTEGER     NOT NULL DEFAULT 499,
    stripe_session_id TEXT,
    PRIMARY KEY (user_id)
);

-- ══════════════════════════════════════════════════════════════════════
-- SECTION 8 — PUBLIC ONLY: remaining public tables             [PUBLIC]
-- ══════════════════════════════════════════════════════════════════════

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

CREATE TABLE IF NOT EXISTS app.ai_usage (
    user_id     INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    query_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
    query_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, query_date)
);

CREATE TABLE IF NOT EXISTS app.leaderboard_opts_in (
    user_id     INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    game_id     INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    is_public   BOOLEAN NOT NULL DEFAULT FALSE,
    opted_in_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

CREATE TABLE IF NOT EXISTS app.push_tokens (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES dim.dim_users(user_id) ON DELETE CASCADE,
    expo_token   TEXT NOT NULL UNIQUE,
    platform     TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 9 — INDEXES (safe: IF NOT EXISTS)                    [BOTH]
-- ══════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_fgs_player_game     ON fact.fact_game_stats (player_id, game_id);
CREATE INDEX IF NOT EXISTS idx_fgs_played_at       ON fact.fact_game_stats (played_at DESC);
CREATE INDEX IF NOT EXISTS idx_fgs_game_stat_type  ON fact.fact_game_stats (game_id, stat_type);
CREATE INDEX IF NOT EXISTS idx_players_user_id     ON dim.dim_players (user_id);
CREATE INDEX IF NOT EXISTS idx_game_requests_status ON app.game_requests (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_runs_user_game    ON app.ml_model_runs (user_id, game_id, model_type, trained_at DESC);
CREATE INDEX IF NOT EXISTS idx_leaderboard_entries_game_stat ON app.leaderboard_entries (game_id, stat_type, best_value DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date  ON app.ai_usage (user_id, query_date DESC);


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 10 — AUTO-UPDATE TRIGGER                             [BOTH]
-- ══════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_dim_users_updated_at ON dim.dim_users;
CREATE TRIGGER trg_dim_users_updated_at
    BEFORE UPDATE ON dim.dim_users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ══════════════════════════════════════════════════════════════════════
-- SECTION 11 — MATERIALIZED VIEWS                              [BOTH]
-- (safe: uses IF NOT EXISTS — won't break if views already exist)
-- ══════════════════════════════════════════════════════════════════════

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


-- ══════════════════════════════════════════════════════════════════════
-- VERIFY — run these checks after each section to confirm state
-- ══════════════════════════════════════════════════════════════════════

-- 1. Confirm your fact data is untouched:
--    SELECT COUNT(*) FROM fact.fact_game_stats;   -- should still be 240+

-- 2. Confirm all players have a user_id (run before Section 4c):
--    SELECT COUNT(*) FROM dim.dim_players WHERE user_id IS NULL;  -- must be 0

-- 3. Confirm game_requests has the new columns (PUBLIC):
--    SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'app' AND table_name = 'game_requests'
--    ORDER BY ordinal_position;

-- 4. Confirm power_pack has tier_ceiling_rows (PUBLIC):
--    SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'app' AND table_name = 'power_pack_purchases';
