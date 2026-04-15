-- Migration 005: Add telegram_user_id to dim_users
-- Run against the PERSONAL Supabase DB (same database as dim.dim_users)

ALTER TABLE dim.dim_users
  ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT UNIQUE;

CREATE INDEX IF NOT EXISTS idx_dim_users_telegram_id
  ON dim.dim_users(telegram_user_id);
