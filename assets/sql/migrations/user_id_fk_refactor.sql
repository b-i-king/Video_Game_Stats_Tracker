-- ══════════════════════════════════════════════════════════════
-- MIGRATION: user_email FK → user_id INTEGER FK
-- No data exists — DROP + RECREATE is cleaner than ALTER + backfill.
--
-- Run sections labelled [BOTH] on PERSONAL and PUBLIC.
-- Run sections labelled [PUBLIC] on PUBLIC only.
-- Run sections labelled [PERSONAL] on PERSONAL only.
--
-- Drop order: children first, parents last.
-- Recreate order: parents first, children last.
-- ══════════════════════════════════════════════════════════════


-- ══════════════════════════════════════════════════════════════
-- STEP 1 — DROP ALL CHILD TABLES                       [BOTH]
-- ══════════════════════════════════════════════════════════════

-- Public-only children
DROP TABLE IF EXISTS app.power_pack_purchases  CASCADE;  -- [PUBLIC]
DROP TABLE IF EXISTS app.leaderboard_opts_in   CASCADE;  -- [PUBLIC]
DROP TABLE IF EXISTS app.subscriptions         CASCADE;  -- [PUBLIC]
DROP TABLE IF EXISTS app.ai_usage              CASCADE;  -- [PUBLIC]
DROP TABLE IF EXISTS app.push_tokens           CASCADE;  -- [PUBLIC]
DROP TABLE IF EXISTS app.game_requests         CASCADE;  -- [PUBLIC]

-- Shared children
DROP TABLE IF EXISTS app.integration_imports   CASCADE;  -- [PERSONAL]
DROP TABLE IF EXISTS app.user_integrations     CASCADE;  -- [PERSONAL]
DROP TABLE IF EXISTS app.leaderboard_entries   CASCADE;  -- [BOTH]
DROP TABLE IF EXISTS app.ml_model_runs         CASCADE;  -- [BOTH]

-- Fact table (references dim_players)
DROP TABLE IF EXISTS fact.fact_game_stats      CASCADE;  -- [BOTH]

-- Dimension children (reference dim_users)
DROP TABLE IF EXISTS dim.dim_players           CASCADE;  -- [BOTH]

-- Materialized views that depend on fact_game_stats
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_heatmap     CASCADE;  -- [BOTH]
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_session_days CASCADE;  -- [BOTH]


-- ══════════════════════════════════════════════════════════════
-- STEP 2 — RECREATE (copy from supabase_schema.sql)     [BOTH]
-- ══════════════════════════════════════════════════════════════
-- Paste the relevant CREATE TABLE blocks from supabase_schema.sql below,
-- or just re-run supabase_schema.sql in full after this DROP script.
--
-- Quickest path: run this DROP script, then re-run supabase_schema.sql.
-- Both scripts are idempotent (IF NOT EXISTS / IF EXISTS).
-- ══════════════════════════════════════════════════════════════


-- ══════════════════════════════════════════════════════════════
-- ALSO: fix dim.dim_players CASCADE on existing row            [BOTH]
-- (dim_users → dim_players already existed but had no CASCADE)
-- ══════════════════════════════════════════════════════════════
-- This runs AFTER recreating dim_players from the schema.
-- If you re-ran supabase_schema.sql the CASCADE is already there.
-- Only needed if you patched the old table without re-running schema:

-- ALTER TABLE dim.dim_players
--     DROP CONSTRAINT IF EXISTS dim_players_user_id_fkey,
--     ADD  CONSTRAINT dim_players_user_id_fkey
--          FOREIGN KEY (user_id)
--          REFERENCES dim.dim_users(user_id)
--          ON DELETE CASCADE;

-- ALTER TABLE fact.fact_game_stats
--     DROP CONSTRAINT IF EXISTS fact_game_stats_player_id_fkey,
--     ADD  CONSTRAINT fact_game_stats_player_id_fkey
--          FOREIGN KEY (player_id)
--          REFERENCES dim.dim_players(player_id)
--          ON DELETE CASCADE;


-- ══════════════════════════════════════════════════════════════
-- VERIFY — run after migration
-- ══════════════════════════════════════════════════════════════
-- SELECT
--     tc.table_schema || '.' || tc.table_name  AS child_table,
--     kcu.column_name,
--     ccu.table_schema || '.' || ccu.table_name AS references,
--     rc.delete_rule
-- FROM information_schema.table_constraints tc
-- JOIN information_schema.key_column_usage kcu
--     ON tc.constraint_name = kcu.constraint_name
--     AND tc.table_schema   = kcu.table_schema
-- JOIN information_schema.referential_constraints rc
--     ON tc.constraint_name = rc.constraint_name
-- JOIN information_schema.constraint_column_usage ccu
--     ON rc.unique_constraint_name = ccu.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY'
--   AND ccu.table_name IN ('dim_users', 'dim_players')
-- ORDER BY child_table;
--
-- All rows should show: delete_rule = 'CASCADE'
-- No row should show column_name = 'user_email' pointing to dim_users
