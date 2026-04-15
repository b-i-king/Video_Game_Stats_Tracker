-- Migration 004: Referral program tables
-- Run against the PUBLIC Supabase DB (same database as app.subscriptions)
-- NOT needed on the personal DB (game stats pool)
--
-- Note: user_id references dim.dim_users(user_id) which lives in the same DB.
-- If your public and personal pools point to DIFFERENT Supabase projects,
-- the FK constraint below won't work — change it to just `INTEGER NOT NULL UNIQUE`.

-- One row per referrer — their shareable code and aggregate lifetime earnings
CREATE TABLE IF NOT EXISTS app.referral_codes (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER     NOT NULL UNIQUE REFERENCES dim.dim_users(user_id),
    code               VARCHAR(16) NOT NULL UNIQUE,
    total_earned_cents INTEGER     NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per referred user — tracks conversion + per-referral lifetime earnings
-- referred_user_id is NULL until they sign in; stripe_customer_id NULL until they subscribe
CREATE TABLE IF NOT EXISTS app.referrals (
    id                  SERIAL      PRIMARY KEY,
    referral_code_id    INTEGER     NOT NULL REFERENCES app.referral_codes(id),
    referred_user_id    INTEGER     UNIQUE REFERENCES dim.dim_users(user_id),
    stripe_customer_id  TEXT        UNIQUE,
    total_earned_cents  INTEGER     NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    converted_at        TIMESTAMPTZ                        -- first subscription date
);

CREATE INDEX IF NOT EXISTS idx_referrals_code_id  ON app.referrals(referral_code_id);
CREATE INDEX IF NOT EXISTS idx_referrals_customer ON app.referrals(stripe_customer_id);
