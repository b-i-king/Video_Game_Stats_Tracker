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
-- Public users get the Download Chart button — social media auto-posting
-- (post_queue, user_integrations) is a personal streaming feature only.
--
-- Run order: Schemas → dim [BOTH] → dim [PERSONAL] → fact → app [BOTH]
--            → app [PERSONAL] → app [PUBLIC] → triggers → indexes
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
-- PUBLIC: enable RLS — users can only read their own row.
--
-- Tiers (mutually exclusive, single source of truth):
--   role = 'trusted'    → developer / owner / promoted loyal
--                          all features, no cost, can manage game catalog
--   role = 'registered' → general public via Google auth
--                          access to free + premium subscription plans
--   (no row)            → guest — landing page only, no app access
--
-- is_trusted is a generated column kept for backward compatibility.
-- To promote a user:  UPDATE dim.dim_users SET role = 'trusted' WHERE user_email = '...';
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
-- PUBLIC: enable RLS — users can only see their own players.
-- Player limits enforced in application layer (not DB constraint):
--   Free tier:    2 players per user
--   Premium tier: 5 players per user (requires active subscription)
-- Check: SELECT COUNT(*) FROM dim.dim_players WHERE user_id = $1
CREATE TABLE IF NOT EXISTS dim.dim_players (
    player_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    user_id     INTEGER      NOT NULL REFERENCES dim.dim_users(user_id),
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(player_name, user_id)
);

-- ══════════════════════════════════════════════════════════════
-- DIMENSION TABLES — PERSONAL ONLY                    [PERSONAL]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run on the public Supabase project.

-- ── dim.dim_dashboard_state ───────────────────────────────────
-- Drives the OBS overlay and the /obs_dashboard endpoint.
-- Single-row table — state_id = 1 is the only row ever inserted.
-- PUBLIC: replaced by a per-user version in the [PUBLIC] section below.
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
-- PUBLIC: most critical table — RLS policy example in [PUBLIC] section.
-- source: 'manual' | 'riot' | 'steam' | future integrations
CREATE TABLE IF NOT EXISTS fact.fact_game_stats (
    stat_id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_id               INTEGER REFERENCES dim.dim_games(game_id),
    player_id             INTEGER REFERENCES dim.dim_players(player_id),
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

    -- Data quality constraints
    -- win/ranked/overtime/solo_mode allow NULL: some game modes (e.g. zombies, waves)
    -- do not have a win/loss concept — NULL means "not applicable", not missing.
    CONSTRAINT chk_win        CHECK (win       IS NULL OR win       IN (0, 1)),
    CONSTRAINT chk_ranked     CHECK (ranked    IS NULL OR ranked    IN (0, 1)),
    CONSTRAINT chk_overtime   CHECK (overtime  IN (0, 1)),
    CONSTRAINT chk_solo_mode  CHECK (solo_mode IS NULL OR solo_mode IN (0, 1)),
    CONSTRAINT chk_stat_value CHECK (stat_value >= 0 AND stat_value <= 100000),
    -- Prevent future-dated stats; 5-min grace covers clock skew between client and server
    CONSTRAINT chk_played_at  CHECK (played_at <= NOW() + INTERVAL '5 minutes')
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — SHARED                                  [BOTH]
-- ══════════════════════════════════════════════════════════════

-- ── app.ml_model_runs ─────────────────────────────────────────
-- Audit log of every ML training run per (user, game, stat_type, model).
-- feature_importances JSONB shape: { "ranked": 0.31, "game_mode": 0.22 }
-- model_type: 'random_forest' | 'xgboost'
-- gcs_path:   gs://bucket/models/personal/{user_email}/{game_id}/{stat_type}/{model_type}.joblib
--             gs://bucket/models/generalized/{game_id}/{stat_type}/{model_type}.joblib
CREATE TABLE IF NOT EXISTS app.ml_model_runs (
    id                  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email          TEXT    NOT NULL REFERENCES dim.dim_users(user_email),
    game_id             INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    stat_type           TEXT    NOT NULL,
    model_type          TEXT    NOT NULL,
    r2_score            NUMERIC(5, 4),
    mae                 NUMERIC(10, 2),
    sessions_used       INTEGER,
    feature_importances JSONB,
    gcs_path            TEXT,
    trained_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── app.leaderboard_entries ───────────────────────────────────
-- Pre-aggregated best-value snapshot per (user, game, stat_type).
-- Refreshed by the /api/add_stats pipeline after each submission.
-- PERSONAL: multi-player comparison across your own profiles.
-- PUBLIC:   powers the global leaderboard — join with leaderboard_opts_in
--           to show only opted-in users.
CREATE TABLE IF NOT EXISTS app.leaderboard_entries (
    id             INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email     TEXT    NOT NULL REFERENCES dim.dim_users(user_email),
    player_name    TEXT    NOT NULL,
    game_id        INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    stat_type      TEXT    NOT NULL,
    best_value     NUMERIC,
    total_sessions INTEGER,
    last_updated   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_email, game_id, stat_type)
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — PERSONAL ONLY                          [PERSONAL]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run on the public Supabase project.
-- These features (OBS auto-posting, third-party API integrations)
-- are streaming/personal tools. Public users get the Download Chart
-- button instead of social media auto-posting.

-- ── app.post_queue ────────────────────────────────────────────
-- Social media auto-post queue for your personal streaming setup.
-- Public users download the chart manually — this table is NOT needed
-- on the public project.
--
-- ⚠️  CURRENT STATE: The queue currently runs on a SEPARATE Render
-- Postgres database (QUEUE_DATABASE_URL env var) managed by queue_utils.py.
-- That table has no schema prefix and uses player_id VARCHAR(50).
-- Run this on personal Supabase ONLY when migrating the queue off Render.
CREATE TABLE IF NOT EXISTS app.post_queue (
    queue_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id    VARCHAR(50),   -- VARCHAR to match queue_utils.py (str(player_id))
    platform     VARCHAR(20),
    image_url    VARCHAR(1000),
    caption      TEXT,
    status       VARCHAR(20)  DEFAULT 'pending',
    scheduled_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ── app.user_integrations ─────────────────────────────────────
-- Connected third-party gaming accounts (Riot, Steam, etc.).
-- Personal only — third-party API reliability is not suitable for
-- a public multi-user product yet.
-- Tokens must be encrypted at the application layer before insert.
-- platform: 'riot' | 'steam' | 'activision'
CREATE TABLE IF NOT EXISTS app.user_integrations (
    id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email       TEXT NOT NULL,
    platform         TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,  -- puuid, steam_id, etc.
    access_token     TEXT,           -- encrypted at app layer
    refresh_token    TEXT,
    token_expires_at TIMESTAMPTZ,
    connected_at     TIMESTAMPTZ DEFAULT NOW(),
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE(user_email, platform)
);

-- ── app.integration_imports ───────────────────────────────────
-- Deduplication log — prevents importing the same external match twice.
-- Follows user_integrations — personal only.
CREATE TABLE IF NOT EXISTS app.integration_imports (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email        TEXT NOT NULL,
    platform          TEXT NOT NULL,
    external_match_id TEXT NOT NULL,
    imported_at       TIMESTAMPTZ DEFAULT NOW(),
    game_stat_id      INTEGER REFERENCES fact.fact_game_stats(stat_id),
    UNIQUE(platform, external_match_id, user_email)
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — PUBLIC ONLY                             [PUBLIC]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run these on the personal Supabase project.

-- ── app.game_requests ────────────────────────────────────────
-- Public users request games to be added to the shared catalog.
-- Trusted users (is_trusted=TRUE) bypass this and auto-create directly.
-- status: 'pending' | 'approved' | 'rejected'
CREATE TABLE IF NOT EXISTS app.game_requests (
    request_id       INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email       TEXT        NOT NULL,
    game_name        TEXT        NOT NULL,
    game_installment TEXT,
    status           TEXT        NOT NULL DEFAULT 'pending',
    reviewed_by      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at      TIMESTAMPTZ,
    CONSTRAINT chk_request_status CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- ── app.push_tokens ───────────────────────────────────────────
-- Expo push tokens from the mobile app. One user can have multiple devices.
-- platform: 'ios' | 'android'
-- Stale tokens pruned when Expo returns DeviceNotRegistered.
CREATE TABLE IF NOT EXISTS app.push_tokens (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email   TEXT NOT NULL REFERENCES dim.dim_users(user_email),
    expo_token   TEXT NOT NULL UNIQUE,
    platform     TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── app.ai_usage ──────────────────────────────────────────────
-- Tracks Bolt AI query counts per user per day for free-tier enforcement.
-- Upsert pattern on each /api/ask call:
--   INSERT INTO app.ai_usage (user_email, query_date)
--   VALUES ($1, CURRENT_DATE)
--   ON CONFLICT (user_email, query_date)
--   DO UPDATE SET query_count = app.ai_usage.query_count + 1;
-- Cutoff check: SELECT query_count ... WHERE user_email = $1 AND query_date = CURRENT_DATE
-- Free plan limit: 20/day. Premium plan: 200/month. Trusted: unlimited (skip the check).
CREATE TABLE IF NOT EXISTS app.ai_usage (
    user_email  TEXT    NOT NULL,
    query_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
    query_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_email, query_date)
);

-- ── app.subscriptions ─────────────────────────────────────────
-- Stripe billing state per user.
-- plan: 'free' | 'premium'
-- Lifecycle:
--   checkout.session.completed  → insert row, set plan='pro', is_active=TRUE
--   customer.subscription.updated → update expires_at if billing date changes
--   customer.subscription.deleted → set is_active=FALSE (cancel took effect)
-- Cancel anytime: Stripe sets cancel_at_period_end=TRUE on the Stripe side;
--   cancelled_at is set immediately, expires_at holds the access end date,
--   is_active flips to FALSE only when the period actually ends.
CREATE TABLE IF NOT EXISTS app.subscriptions (
    id                     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email             TEXT NOT NULL UNIQUE REFERENCES dim.dim_users(user_email),
    plan                   TEXT NOT NULL DEFAULT 'free'
                               CHECK (plan IN ('free', 'premium')),
    billing_interval       TEXT CHECK (billing_interval IN ('month', 'year')), -- NULL = free tier
    stripe_customer_id     TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    started_at             TIMESTAMPTZ DEFAULT NOW(),
    expires_at             TIMESTAMPTZ,  -- NULL = active indefinitely (free tier)
    cancelled_at           TIMESTAMPTZ,  -- SET immediately on cancel request
    is_active              BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── app.leaderboard_opts_in ───────────────────────────────────
-- Public consent gate — users must explicitly opt in per game before
-- their stats appear on the public leaderboard.
-- Defaults to private. Never shown publicly without is_public = TRUE.
CREATE TABLE IF NOT EXISTS app.leaderboard_opts_in (
    user_email  TEXT    NOT NULL REFERENCES dim.dim_users(user_email),
    game_id     INTEGER NOT NULL REFERENCES dim.dim_games(game_id),
    is_public   BOOLEAN NOT NULL DEFAULT FALSE,
    opted_in_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_email, game_id)
);


-- ══════════════════════════════════════════════════════════════
-- PUBLIC SCHEMA MODIFICATIONS                          [PUBLIC]
-- ══════════════════════════════════════════════════════════════
-- These replace or extend the [BOTH] versions above.
-- Run INSTEAD OF the personal versions where noted.

-- ── dim.dim_dashboard_state (public version) ──────────────────
-- Replaces the single-row personal version.
-- One row per user instead of one global row.
-- DO NOT run this on personal — use the single-row version above.
--
-- CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
--     user_email        TEXT PRIMARY KEY REFERENCES dim.dim_users(user_email),
--     current_player_id INTEGER,
--     current_game_id   INTEGER,
--     updated_at        TIMESTAMPTZ DEFAULT NOW()
-- );

-- ── dim.dim_games additions (public version) ──────────────────
-- Extends the shared dim.dim_games with catalog metadata.
-- Run after CREATE TABLE dim.dim_games on public only.
--
-- ALTER TABLE dim.dim_games
--     ADD COLUMN IF NOT EXISTS created_by  TEXT REFERENCES dim.dim_users(user_email),
--     ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE;
-- -- is_verified: TRUE for well-known titles you manually flag as canonical.


-- ══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)                             [PUBLIC]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run on personal. Personal is single-tenant — RLS adds
-- complexity with zero security benefit.
--
-- ⚠️  IMPORTANT — auth.jwt() and your Flask backend:
--   auth.jwt()->>'email' reads the Supabase Auth JWT.
--   Your current stack uses NextAuth + Flask JWT, NOT Supabase Auth.
--   Flask connects via direct psycopg2 — it bypasses RLS entirely.
--   These policies protect direct PostgREST access and are
--   forward-looking for when Supabase Auth replaces NextAuth.
--   Until that migration: RLS is a safety net, not a primary gate.
--
-- Run ENABLE ROW LEVEL SECURITY before CREATE POLICY on each table.
-- PostgreSQL does NOT support combining commands in one FOR clause —
-- use FOR ALL or separate policies per operation.

-- ── dim.dim_games ─────────────────────────────────────────────
-- Shared game catalog — not per-user data.
-- SELECT is open to all authenticated users.
-- No INSERT/UPDATE/DELETE policy defined — RLS denies writes by default,
-- so PostgREST cannot modify the catalog. All writes go through the
-- backend (psycopg2 bypasses RLS) where is_trusted is enforced.
-- ALTER TABLE dim.dim_games ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "all_read_games" ON dim.dim_games
--     FOR SELECT USING (true);

-- ── dim.dim_users ─────────────────────────────────────────────
-- Users can only read/update their own row.
-- INSERT is handled by the Flask backend (psycopg2, bypasses RLS).
-- ALTER TABLE dim.dim_users ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_row" ON dim.dim_users
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── dim.dim_players ───────────────────────────────────────────
-- ALTER TABLE dim.dim_players ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_players" ON dim.dim_players
--     FOR ALL USING (
--         user_id = (
--             SELECT user_id FROM dim.dim_users
--             WHERE user_email = auth.jwt()->>'email'
--         )
--     );

-- ── fact.fact_game_stats ──────────────────────────────────────
-- ALTER TABLE fact.fact_game_stats ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_stats" ON fact.fact_game_stats
--     FOR ALL USING (
--         player_id IN (
--             SELECT p.player_id FROM dim.dim_players p
--             JOIN dim.dim_users u ON p.user_id = u.user_id
--             WHERE u.user_email = auth.jwt()->>'email'
--         )
--     );

-- ── app.ml_model_runs ─────────────────────────────────────────
-- ALTER TABLE app.ml_model_runs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_model_runs" ON app.ml_model_runs
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.leaderboard_entries ───────────────────────────────────
-- Two separate policies required — PostgreSQL does not allow combining
-- multiple commands (INSERT, UPDATE, DELETE) in a single FOR clause.
--
-- Write policy: users can only modify their own entries.
-- Read policy:  users see their own entries PLUS any entry where the
--               owner has opted in to the public leaderboard for that game.
-- ALTER TABLE app.leaderboard_entries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_entries_write" ON app.leaderboard_entries
--     FOR ALL USING (user_email = auth.jwt()->>'email');
-- CREATE POLICY "public_leaderboard_read" ON app.leaderboard_entries
--     FOR SELECT USING (
--         user_email = auth.jwt()->>'email'
--         OR user_email IN (
--             SELECT user_email FROM app.leaderboard_opts_in
--             WHERE game_id = app.leaderboard_entries.game_id
--               AND is_public = TRUE
--         )
--     );

-- ── app.game_requests ─────────────────────────────────────────
-- Users can submit and read their own game requests.
-- Admin review (status updates) is done via the Flask backend
-- (psycopg2 superuser connection — bypasses RLS).
-- ALTER TABLE app.game_requests ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_requests" ON app.game_requests
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.ai_usage ──────────────────────────────────────────────
-- ALTER TABLE app.ai_usage ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_usage" ON app.ai_usage
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.subscriptions ─────────────────────────────────────────
-- ALTER TABLE app.subscriptions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_subscription" ON app.subscriptions
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.leaderboard_opts_in ───────────────────────────────────
-- Users manage their own opt-in preferences.
-- Anyone can SELECT to power the leaderboard display.
-- ALTER TABLE app.leaderboard_opts_in ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_manage_own_optin" ON app.leaderboard_opts_in
--     FOR ALL USING (user_email = auth.jwt()->>'email');
-- CREATE POLICY "public_optin_read" ON app.leaderboard_opts_in
--     FOR SELECT USING (true);

-- ── app.push_tokens ───────────────────────────────────────────
-- ALTER TABLE app.push_tokens ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_tokens" ON app.push_tokens
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- Tables intentionally excluded from public RLS
-- (personal-only — not present on the public project):
--   app.post_queue          → personal streaming feature
--   app.user_integrations   → personal third-party API integrations
--   app.integration_imports → follows user_integrations
--   dim.dim_dashboard_state → personal OBS single-row table


-- ══════════════════════════════════════════════════════════════
-- AUTO-UPDATE TRIGGER                                  [BOTH]
-- ══════════════════════════════════════════════════════════════
-- Keeps dim_users.updated_at current whenever a row is modified.
-- PostgreSQL does not auto-update timestamp columns — a trigger is required.

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
-- Run on both personal and public Supabase projects.
-- Every non-trivial query in flask_app.py filters or joins on these columns.

-- fact_game_stats — most queried table
CREATE INDEX IF NOT EXISTS idx_fgs_player_game
    ON fact.fact_game_stats (player_id, game_id);

CREATE INDEX IF NOT EXISTS idx_fgs_played_at
    ON fact.fact_game_stats (played_at DESC);

CREATE INDEX IF NOT EXISTS idx_fgs_game_stat_type
    ON fact.fact_game_stats (game_id, stat_type);

-- dim_players — looked up by user_id on nearly every request
CREATE INDEX IF NOT EXISTS idx_players_user_id
    ON dim.dim_players (user_id);

-- dim_users — looked up by email on every authenticated request
-- Already covered by the UNIQUE constraint (implicit index), but explicit for clarity:
-- CREATE INDEX IF NOT EXISTS idx_users_email ON dim.dim_users (user_email);

-- dim_games — franchise / installment lookups
CREATE INDEX IF NOT EXISTS idx_games_name
    ON dim.dim_games (game_name);

-- app.post_queue — status polling for queue worker
CREATE INDEX IF NOT EXISTS idx_post_queue_status
    ON app.post_queue (status, created_at);

-- app.game_requests — admin review dashboard
CREATE INDEX IF NOT EXISTS idx_game_requests_status
    ON app.game_requests (status, created_at DESC);
