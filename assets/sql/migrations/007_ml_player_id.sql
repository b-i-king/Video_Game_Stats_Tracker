-- Migration 007: Add player_id to app.ml_model_runs
-- Run against BOTH personal and public Supabase DBs.
--
-- Allows per-player LR models so win probability is scoped to the
-- specific player profile, not just the game.

ALTER TABLE app.ml_model_runs
    ADD COLUMN IF NOT EXISTS player_id INTEGER REFERENCES dim.dim_players(player_id) ON DELETE CASCADE;

-- Update index to include player_id for fast per-player lookups
DROP INDEX IF EXISTS idx_ml_runs_user_game;
CREATE INDEX IF NOT EXISTS idx_ml_runs_user_game
    ON app.ml_model_runs (user_id, game_id, player_id, model_type, trained_at DESC);
