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
--   [PUBLIC]   run on public only
--   [PERSONAL] run on personal only (currently none)
--
-- Run order: Schemas → dim → fact → app (shared) → app (public-only)
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
CREATE TABLE IF NOT EXISTS dim.dim_users (
    user_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL UNIQUE,
    is_trusted BOOLEAN      NOT NULL DEFAULT FALSE
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
CREATE TABLE IF NOT EXISTS dim.dim_players (
    player_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    user_id     INTEGER      NOT NULL REFERENCES dim.dim_users(user_id),
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(player_name, user_id)
);

-- ── dim.dim_dashboard_state ───────────────────────────────────
-- PERSONAL: single-row table — only one user (you).
--           state_id = 1 is the only row ever inserted.
-- PUBLIC:   see redesigned version in the [PUBLIC] section below.
--           This version is intentionally kept for personal use only.
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
    is_editable           BOOLEAN      NOT NULL DEFAULT TRUE
);


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — SHARED                                  [BOTH]
-- ══════════════════════════════════════════════════════════════

-- ── app.post_queue ────────────────────────────────────────────
-- Social media post queue. PUBLIC: enable RLS.
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
CREATE TABLE IF NOT EXISTS app.integration_imports (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email        TEXT NOT NULL,
    platform          TEXT NOT NULL,
    external_match_id TEXT NOT NULL,
    imported_at       TIMESTAMPTZ DEFAULT NOW(),
    game_stat_id      INTEGER REFERENCES fact.fact_game_stats(stat_id),
    UNIQUE(platform, external_match_id, user_email)
);

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
-- PERSONAL: shows your own multi-player/profile comparison.
-- PUBLIC:   join with app.leaderboard_opts_in to filter to opted-in users only.
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


-- ══════════════════════════════════════════════════════════════
-- APP TABLES — PUBLIC ONLY                             [PUBLIC]
-- ══════════════════════════════════════════════════════════════
-- Do NOT run these on the personal Supabase project.

-- ── app.ai_usage ──────────────────────────────────────────────
-- Tracks Bolt AI query counts per user per day for free-tier enforcement.
-- Upsert pattern on each /api/ask call:
--   INSERT INTO app.ai_usage (user_email, query_date)
--   VALUES ($1, CURRENT_DATE)
--   ON CONFLICT (user_email, query_date)
--   DO UPDATE SET query_count = app.ai_usage.query_count + 1;
-- Cutoff check: SELECT query_count ... WHERE user_email = $1 AND query_date = CURRENT_DATE
-- Free plan limit: 20/day. Pro plan: unlimited (skip the check).
CREATE TABLE IF NOT EXISTS app.ai_usage (
    user_email  TEXT    NOT NULL,
    query_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
    query_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_email, query_date)
);

-- ── app.subscriptions ─────────────────────────────────────────
-- Stripe billing state per user.
-- plan: 'free' | 'pro'
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
    plan                   TEXT NOT NULL DEFAULT 'free',
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
-- Pattern: auth.jwt()->>'email' returns the email from the Supabase
-- JWT, matching user_email stored in each table.
-- Run ENABLE ROW LEVEL SECURITY before CREATE POLICY on each table.

-- ── dim.dim_users ─────────────────────────────────────────────
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

-- ── app.post_queue ────────────────────────────────────────────
-- ALTER TABLE app.post_queue ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_queue" ON app.post_queue
--     FOR ALL USING (
--         player_id::INTEGER IN (
--             SELECT p.player_id FROM dim.dim_players p
--             JOIN dim.dim_users u ON p.user_id = u.user_id
--             WHERE u.user_email = auth.jwt()->>'email'
--         )
--     );

-- ── app.user_integrations ─────────────────────────────────────
-- ALTER TABLE app.user_integrations ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_integrations" ON app.user_integrations
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.integration_imports ───────────────────────────────────
-- ALTER TABLE app.integration_imports ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_imports" ON app.integration_imports
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.ml_model_runs ─────────────────────────────────────────
-- ALTER TABLE app.ml_model_runs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_model_runs" ON app.ml_model_runs
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.leaderboard_entries ───────────────────────────────────
-- SELECT policy is intentionally open for opted-in rows so the
-- leaderboard tab can display other users' best scores.
-- ALTER TABLE app.leaderboard_entries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_entries_write" ON app.leaderboard_entries
--     FOR INSERT, UPDATE, DELETE
--     USING (user_email = auth.jwt()->>'email');
-- CREATE POLICY "public_leaderboard_read" ON app.leaderboard_entries
--     FOR SELECT USING (
--         user_email IN (
--             SELECT user_email FROM app.leaderboard_opts_in
--             WHERE game_id = app.leaderboard_entries.game_id
--               AND is_public = TRUE
--         )
--         OR user_email = auth.jwt()->>'email'
--     );

-- ── app.ai_usage ──────────────────────────────────────────────
-- ALTER TABLE app.ai_usage ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_usage" ON app.ai_usage
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.subscriptions ─────────────────────────────────────────
-- ALTER TABLE app.subscriptions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_subscription" ON app.subscriptions
--     FOR ALL USING (user_email = auth.jwt()->>'email');

-- ── app.push_tokens ───────────────────────────────────────────
-- ALTER TABLE app.push_tokens ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_tokens" ON app.push_tokens
--     FOR ALL USING (user_email = auth.jwt()->>'email');
