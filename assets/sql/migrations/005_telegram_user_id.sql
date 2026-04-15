-- Migration 005: Add telegram_user_id to dim_users
-- Run against the PUBLIC Supabase DB — general users (including Telegram Mini App
-- users) live in the public dim.dim_users. The personal DB is owner-only.

ALTER TABLE dim.dim_users
  ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT UNIQUE;

CREATE INDEX IF NOT EXISTS idx_dim_users_telegram_id
  ON dim.dim_users(telegram_user_id);
