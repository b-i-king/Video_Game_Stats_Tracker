-- Migration 009: Rename stat_type → model_target in app.ml_model_runs.
-- Run against BOTH personal and public Supabase DBs.
--
-- stat_type was misleading — 'win' is not a stat_type in fact_game_stats,
-- it is a separate column. model_target clarifies this is the prediction
-- target of the model (e.g. 'win_probability').

-- 1. Rename the column
ALTER TABLE app.ml_model_runs
    RENAME COLUMN stat_type TO model_target;

-- 2. Drop the unique constraint added in migration 008 (references old column name)
ALTER TABLE app.ml_model_runs
    DROP CONSTRAINT IF EXISTS uq_ml_model_runs_key;

-- 3. Re-create the unique constraint with the new column name
ALTER TABLE app.ml_model_runs
    ADD CONSTRAINT uq_ml_model_runs_key
    UNIQUE (user_id, game_id, player_id, model_type, model_target);

-- 4. Rebuild the index from migration 007 to use the new column name
DROP INDEX IF EXISTS idx_ml_runs_user_game;
CREATE INDEX IF NOT EXISTS idx_ml_runs_user_game
    ON app.ml_model_runs (user_id, game_id, player_id, model_type, trained_at DESC);
