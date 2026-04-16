-- Migration 006: Add newsletter_optin to dim.dim_users
-- Run against BOTH the personal and public Supabase DBs.
--
-- The account page newsletter toggle calls GET/POST /api/newsletter/optin
-- which queries this column. Without it the account page crashes on load.

ALTER TABLE dim.dim_users
    ADD COLUMN IF NOT EXISTS newsletter_optin BOOLEAN NOT NULL DEFAULT FALSE;
