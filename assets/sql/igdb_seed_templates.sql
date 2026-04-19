-- igdb_seed_templates.sql
-- Run this AFTER igdb_import.py has populated dim.dim_games.
-- Looks up real igdb_id values from the import rather than hardcoding them.
-- Safe to re-run — uses ON CONFLICT DO NOTHING.

INSERT INTO dim.dim_game_stat_templates (igdb_id, game_name, stat_types)
SELECT g.igdb_id, g.game_name, t.stat_types
FROM (VALUES
    ('Call of Duty',         'Warzone',          ARRAY['Eliminations','Respawns','Damage','Placement']),
    ('Apex Legends',          NULL,               ARRAY['Eliminations','Damage','Placement','Revives']),
    ('League of Legends',     NULL,               ARRAY['Eliminations','Deaths','Assists','CS','Vision Score']),
    ('Valorant',              NULL,               ARRAY['Eliminations','Deaths','Assists','ACS','HS%']),
    ('Fortnite',              NULL,               ARRAY['Eliminations','Placement','Damage','Materials']),
    ('Rocket League',         NULL,               ARRAY['Goals','Assists','Saves','Score','Shots']),
    ('Overwatch',             '2',                ARRAY['Eliminations','Deaths','Damage','Healing']),
    ('FIFA',                  NULL,               ARRAY['Goals','Assists','Possession','Shots on Target']),
    ('Counter-Strike',        '2',                ARRAY['Eliminations','Deaths','Assists','HS%','ADR']),
    ('Dota',                  '2',                ARRAY['Eliminations','Deaths','Assists','GPM','XPM']),
    ('Minecraft',             NULL,               ARRAY['Time Survived','Mobs Killed','Blocks Mined','Deaths']),
    ('Grand Theft Auto',      'V',                ARRAY['Score','Kills','Deaths','Money Earned']),
    ('Elden Ring',            NULL,               ARRAY['Bosses Defeated','Deaths','Playtime','Runes Collected']),
    ('Halo',                  'Infinite',         ARRAY['Eliminations','Deaths','Assists','Damage','Score']),
    ('Destiny',               '2',                ARRAY['Eliminations','Deaths','Assists','Score','Efficiency']),
    ('Rainbow Six',           'Siege',            ARRAY['Eliminations','Deaths','Assists','Headshots','Score']),
    ('Battlefield',           '2042',             ARRAY['Eliminations','Deaths','Assists','Score','Revives']),
    ('Escape from Tarkov',    NULL,               ARRAY['Eliminations','Deaths','Damage','Loot Value','Survival Time'])
) AS t(game_name, game_installment, stat_types)
JOIN dim.dim_games g
  ON g.game_name = t.game_name
 AND (
       (t.game_installment IS NULL AND g.game_installment IS NULL)
    OR  g.game_installment = t.game_installment
     )
WHERE g.igdb_id IS NOT NULL
ON CONFLICT (igdb_id) DO NOTHING;

-- Show what was matched vs missed
SELECT
    t.game_name,
    t.game_installment,
    g.igdb_id,
    g.game_id,
    CASE WHEN g.igdb_id IS NOT NULL THEN '✓ matched' ELSE '✗ not found in dim_games' END AS status
FROM (VALUES
    ('Call of Duty',         'Warzone'),
    ('Apex Legends',          NULL),
    ('League of Legends',     NULL),
    ('Valorant',              NULL),
    ('Fortnite',              NULL),
    ('Rocket League',         NULL),
    ('Overwatch',             '2'),
    ('FIFA',                  NULL),
    ('Counter-Strike',        '2'),
    ('Dota',                  '2'),
    ('Minecraft',             NULL),
    ('Grand Theft Auto',      'V'),
    ('Elden Ring',            NULL),
    ('Halo',                  'Infinite'),
    ('Destiny',               '2'),
    ('Rainbow Six',           'Siege'),
    ('Battlefield',           '2042'),
    ('Escape from Tarkov',    NULL)
) AS t(game_name, game_installment)
LEFT JOIN dim.dim_games g
  ON g.game_name = t.game_name
 AND (
       (t.game_installment IS NULL AND g.game_installment IS NULL)
    OR  g.game_installment = t.game_installment
     )
ORDER BY status, t.game_name;
