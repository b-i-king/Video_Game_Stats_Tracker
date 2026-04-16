-- Migration 008: Unique constraint on ml_model_runs for upsert behaviour.
-- Run against BOTH personal and public Supabase DBs.
--
-- Ensures each (user, game, player, model_type, stat_type) tuple has exactly
-- one row — training a new model updates the existing record rather than
-- appending a new one.

ALTER TABLE app.ml_model_runs
    ADD CONSTRAINT uq_ml_model_runs_key
    UNIQUE (user_id, game_id, player_id, model_type, stat_type);
