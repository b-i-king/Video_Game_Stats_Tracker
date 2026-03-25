-- ============================================================
-- Supabase Schema Migration
-- Translated from AWS Redshift — run in Supabase SQL Editor
-- ============================================================

-- ── Schemas ───────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS app;

-- ── dim.dim_users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim.dim_users (
    user_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL UNIQUE,
    is_trusted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ── dim.dim_games ─────────────────────────────────────────────────────
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

-- ── dim.dim_players ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim.dim_players (
    player_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL REFERENCES dim.dim_users(user_id),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_name, user_id)
);

-- ── dim.dim_dashboard_state ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
    state_id          INT PRIMARY KEY DEFAULT 1,
    current_player_id INTEGER,
    current_game_id   INTEGER,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── fact.fact_game_stats ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact.fact_game_stats (
    stat_id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_id               INTEGER REFERENCES dim.dim_games(game_id),
    player_id             INTEGER REFERENCES dim.dim_players(player_id),
    stat_type             VARCHAR(50) NOT NULL,
    stat_value            INTEGER,
    game_mode             VARCHAR(255),
    solo_mode             INTEGER,
    party_size            VARCHAR(20),
    game_level            INTEGER,
    win                   INTEGER,
    ranked                INTEGER,
    pre_match_rank_value  VARCHAR(50),
    post_match_rank_value VARCHAR(50),
    overtime              INTEGER NOT NULL DEFAULT 0,
    difficulty            VARCHAR(20),
    input_device          VARCHAR(30) NOT NULL DEFAULT 'Controller',
    platform              VARCHAR(20) NOT NULL DEFAULT 'PC',
    first_session_of_day  INTEGER NOT NULL DEFAULT 1,
    was_streaming         INTEGER NOT NULL DEFAULT 0,
    played_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ── app.post_queue ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app.post_queue (
    queue_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id    VARCHAR(50),
    platform     VARCHAR(20),
    image_url    VARCHAR(1000),
    caption      TEXT,
    status       VARCHAR(20) DEFAULT 'pending',
    scheduled_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
