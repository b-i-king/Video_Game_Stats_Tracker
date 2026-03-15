-- ============================================================================
-- Instagram Poster – Redshift Serverless Test Queries
-- ============================================================================
-- Purpose : Validate SQL from instagram_poster.py before Lambda deployment.
-- How to use: Run each section in AWS Redshift Query Editor v2.
--             Replace test values (marked with -- ← CHANGE ME) as needed.
-- ============================================================================

-- ── Shared test variables (substitute these throughout) ─────────────────────
--   player_id  = 1
--   timezone   = 'America/Los_Angeles'
--   target_date = CURRENT_DATE  (or a specific date like '2025-03-14')
-- ============================================================================


-- ============================================================================
-- 1. UTILITY QUERIES (used by all poster types)
-- ============================================================================

-- 1a. Check if player has any games on a specific date
SELECT COUNT(DISTINCT stat_id)
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)    -- ← CHANGE ME (timezone)
      = CURRENT_DATE;                                                      -- ← CHANGE ME (date)


-- 1b. Get all games player has ever played
SELECT DISTINCT g.game_id, g.game_name, g.game_installment
FROM fact.fact_game_stats f
JOIN dim.dim_games g ON f.game_id = g.game_id
WHERE f.player_id = 1                                                      -- ← CHANGE ME
ORDER BY g.game_name;


-- 1c. Get player name
SELECT player_name
FROM dim.dim_players
WHERE player_id = 1;                                                       -- ← CHANGE ME


-- ============================================================================
-- 2. MWF PORTRAIT POSTER  (Mon / Wed / Fri  –  daily · recent · historical)
-- ============================================================================

-- 2a. Stats for a specific date and game (daily / recent poster)
--     Returns top 5 stats by value for the given game on a given date.
SELECT
    f.stat_type,
    f.stat_value
FROM fact.fact_game_stats f
WHERE f.player_id = 1                                                      -- ← CHANGE ME
  AND f.game_id   = 1                                                      -- ← CHANGE ME (game_id)
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE)  -- ← CHANGE ME (timezone)
      = CURRENT_DATE                                                       -- ← CHANGE ME (date)
ORDER BY f.stat_value DESC
LIMIT 5;


-- 2b. Stats for ALL games on a specific date (multi-game daily poster)
SELECT
    g.game_name,
    g.game_installment,
    f.stat_type,
    f.stat_value
FROM fact.fact_game_stats f
JOIN dim.dim_games g ON f.game_id = g.game_id
WHERE f.player_id = 1                                                      -- ← CHANGE ME
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE)  -- ← CHANGE ME (timezone)
      = CURRENT_DATE                                                       -- ← CHANGE ME (date)
ORDER BY f.stat_value DESC;


-- 2c. Most-played game mode on a specific date (excludes blank / 'Main')
SELECT game_mode, COUNT(*) AS cnt
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND game_id   = 1                                                        -- ← CHANGE ME (game_id)
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)    -- ← CHANGE ME (timezone)
      = CURRENT_DATE                                                       -- ← CHANGE ME (date)
  AND game_mode IS NOT NULL
  AND TRIM(game_mode) != ''
  AND LOWER(TRIM(game_mode)) != 'main'
GROUP BY game_mode
ORDER BY cnt DESC
LIMIT 1;


-- 2d. Anomaly detection for a specific date / game
--     Returns stats whose z-score > 2 (unusually high/low vs. overall average).
WITH daily_stats AS (
    SELECT
        f.stat_type,
        f.stat_value,
        AVG(f.stat_value) OVER (PARTITION BY f.stat_type) AS avg_value,
        STDDEV(f.stat_value) OVER (PARTITION BY f.stat_type) AS stddev_value
    FROM fact.fact_game_stats f
    WHERE f.player_id = 1                                                  -- ← CHANGE ME
      AND f.game_id   = 1                                                  -- ← CHANGE ME (game_id)
      AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE) -- ← CHANGE ME (timezone)
          = CURRENT_DATE                                                   -- ← CHANGE ME (date)
)
SELECT
    stat_type,
    stat_value,
    avg_value,
    stddev_value,
    (stat_value - avg_value) / NULLIF(stddev_value, 0) AS z_score
FROM daily_stats
WHERE ABS((stat_value - avg_value) / NULLIF(stddev_value, 0)) > 2
ORDER BY ABS((stat_value - avg_value) / NULLIF(stddev_value, 0)) DESC
LIMIT 3;


-- 2e. Historical records across ALL games (historical poster)
--     Returns the all-time best value per game + stat combo.
--     Increase LIMIT for wider de-duplication window (code uses limit * 2).
WITH ranked_stats AS (
    SELECT
        g.game_name,
        g.game_installment,
        f.stat_type,
        MAX(f.stat_value) AS max_value,
        MAX(CAST(CONVERT_TIMEZONE('America/Los_Angeles', f.played_at) AS DATE)) AS best_date -- ← CHANGE ME (timezone)
    FROM fact.fact_game_stats f
    JOIN dim.dim_games g ON f.game_id = g.game_id
    WHERE f.player_id = 1                                                  -- ← CHANGE ME
    GROUP BY g.game_name, g.game_installment, f.stat_type
)
SELECT
    game_name,
    game_installment,
    stat_type,
    max_value,
    best_date
FROM ranked_stats
ORDER BY max_value DESC
LIMIT 20;  -- code default is limit*2 where limit=10


-- ============================================================================
-- 3. TUESDAY / THURSDAY  –  TALE OF THE TAPE  (mode vs. mode comparison)
-- ============================================================================

-- 3a. Find game + mode pairs with ≥ 30 samples per stat and compute averages
--     The first qualifying pair is used for the chart.
WITH mode_stats AS (
    SELECT
        f.game_id,
        f.game_mode,
        f.stat_type,
        COUNT(*)                            AS n,
        AVG(CAST(f.stat_value AS FLOAT))    AS mean_val,
        STDDEV(CAST(f.stat_value AS FLOAT)) AS std_val
    FROM fact.fact_game_stats f
    WHERE f.player_id = 1                                                  -- ← CHANGE ME
      AND f.game_mode IS NOT NULL
      AND TRIM(f.game_mode) != ''
    GROUP BY f.game_id, f.game_mode, f.stat_type
    HAVING COUNT(*) >= 30
)
SELECT
    a.game_id,
    a.game_mode  AS mode_1,
    b.game_mode  AS mode_2,
    a.stat_type,
    a.n          AS n1,
    a.mean_val   AS mean1,
    a.std_val    AS std1,
    b.n          AS n2,
    b.mean_val   AS mean2,
    b.std_val    AS std2
FROM mode_stats a
JOIN mode_stats b
  ON  a.game_id   = b.game_id
  AND a.stat_type = b.stat_type
  AND a.game_mode < b.game_mode       -- ensures each pair appears once
ORDER BY a.game_id, (a.mean_val + b.mean_val) DESC;


-- 3b. Look up game name / installment for a specific game_id
--     (Called after 3a to resolve game_id → display name)
SELECT game_name, game_installment
FROM dim.dim_games
WHERE game_id = 1;                                                         -- ← CHANGE ME (game_id from 3a)


-- ============================================================================
-- 4. SATURDAY  –  WEEKLY SUMMARY
-- ============================================================================
-- Substitute week_start / week_end with the Monday–Sunday of the target week.

-- 4a. Week overview: distinct games played and total sessions
SELECT
    COUNT(DISTINCT game_id)   AS games_played,
    COUNT(DISTINCT played_at) AS sessions
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)    -- ← CHANGE ME (timezone)
      BETWEEN '2025-03-10' AND '2025-03-16';                              -- ← CHANGE ME (week_start / week_end)


-- 4b. Top single stat of the week (highest raw value)
SELECT stat_type, stat_value
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)    -- ← CHANGE ME (timezone)
      BETWEEN '2025-03-10' AND '2025-03-16'                               -- ← CHANGE ME (week_start / week_end)
ORDER BY stat_value DESC
LIMIT 1;


-- 4c. Busiest day of the week (most game stat rows recorded)
--     played_at is included in GROUP BY so Redshift can resolve the aggregate alias.
SELECT CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE) AS play_date, -- ← CHANGE ME (timezone)
       COUNT(*) AS cnt
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)    -- ← CHANGE ME (timezone)
      BETWEEN '2025-03-10' AND '2025-03-16'                               -- ← CHANGE ME (week_start / week_end)
GROUP BY played_at, CAST(CONVERT_TIMEZONE('America/Los_Angeles', played_at) AS DATE)
ORDER BY cnt DESC, play_date ASC
LIMIT 1;


-- ============================================================================
-- 5. NEW YEAR'S DAY  –  YEARLY RECAP
-- ============================================================================

-- 5a. Games played by session count for the target year
SELECT
    g.game_name,
    g.game_installment,
    g.game_genre,
    g.game_subgenre,
    COUNT(DISTINCT f.played_at) AS sessions
FROM fact.fact_game_stats f
JOIN dim.dim_games g ON f.game_id = g.game_id
WHERE f.player_id = 1                                                      -- ← CHANGE ME
  AND EXTRACT(YEAR FROM CONVERT_TIMEZONE('America/Los_Angeles', f.played_at)) = 2025 -- ← CHANGE ME (year)
GROUP BY g.game_name, g.game_installment, g.game_genre, g.game_subgenre
ORDER BY sessions DESC;


-- 5b. All-time highest single stat for the target year
SELECT stat_type, stat_value
FROM fact.fact_game_stats
WHERE player_id = 1                                                        -- ← CHANGE ME
  AND EXTRACT(YEAR FROM CONVERT_TIMEZONE('America/Los_Angeles', played_at)) = 2025 -- ← CHANGE ME (year)
ORDER BY stat_value DESC
LIMIT 1;
