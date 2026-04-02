-- Migration 003: Analytics schema, missing columns, and performance indexes
-- Run on: personal project (analytics + columns + indexes)
--          public project  (analytics + indexes only — skip personal-only tables)
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. analytics schema ───────────────────────────────────────────────────────
-- Holds materialized views for expensive aggregations.
-- Refreshed via FastAPI BackgroundTasks after each add_stats call.

CREATE SCHEMA IF NOT EXISTS analytics;

-- Heatmap: session frequency by day-of-week × hour in user's timezone.
-- Hardcoded to America/Los_Angeles for now; tz-aware version in FastAPI.
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

-- Session days: distinct play dates per player/game used by streak calculation.
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

-- Leaderboard percentiles: PERCENT_RANK per (game, stat_type) across opted-in users.
-- PUBLIC project only — skip on personal (no leaderboard_opts_in table).
-- Uncomment on public project after app.leaderboard_opts_in is populated.
--
-- CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_leaderboard_percentiles AS
-- SELECT
--     l.game_id,
--     l.stat_type,
--     l.user_email,
--     l.best_value                                                        AS avg_value,
--     PERCENT_RANK() OVER (
--         PARTITION BY l.game_id, l.stat_type
--         ORDER BY l.best_value DESC
--     )                                                                   AS percentile_rank,
--     COUNT(*) OVER (PARTITION BY l.game_id, l.stat_type)                AS sample_size
-- FROM app.leaderboard_entries l
-- JOIN app.leaderboard_opts_in o
--     ON l.user_email = o.user_email AND l.game_id = o.game_id
-- WHERE o.is_public = TRUE;
--
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_leaderboard_percentiles
--     ON analytics.mv_leaderboard_percentiles (user_email, game_id, stat_type);


-- ── 2. Missing columns ────────────────────────────────────────────────────────

-- app.ml_model_runs — add model_coefficients for LR client-side inference.
-- Shape: {"coef": [[...]], "intercept": [float], "classes": [0, 1]}
-- Frontend reads this to compute P(win) via TypeScript sigmoid — zero extra API calls.
ALTER TABLE app.ml_model_runs
    ADD COLUMN IF NOT EXISTS model_coefficients JSONB;

-- app.user_integrations — add human-readable display name (e.g. "BOL#NA1" for Riot).
ALTER TABLE app.user_integrations
    ADD COLUMN IF NOT EXISTS platform_username TEXT;


-- ── 3. Missing indexes ────────────────────────────────────────────────────────

-- app.ml_model_runs — latest run lookup per (user, game, model_type)
CREATE INDEX IF NOT EXISTS idx_ml_runs_user_game
    ON app.ml_model_runs (user_email, game_id, model_type, trained_at DESC);

-- app.user_integrations — active integration lookup per user
CREATE INDEX IF NOT EXISTS idx_user_integrations_email_platform
    ON app.user_integrations (user_email, platform)
    WHERE is_active = TRUE;

-- app.integration_imports — dedup check (hot path on every Riot poll cycle)
CREATE INDEX IF NOT EXISTS idx_integration_imports_dedup
    ON app.integration_imports (platform, external_match_id);

-- app.leaderboard_entries — leaderboard reads by game + stat
CREATE INDEX IF NOT EXISTS idx_leaderboard_entries_game_stat
    ON app.leaderboard_entries (game_id, stat_type, best_value DESC);

-- app.ai_usage — usage check on every /api/ask call
CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date
    ON app.ai_usage (user_email, query_date DESC);
