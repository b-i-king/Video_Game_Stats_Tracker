-- Migration 010: IGDB + Steam enrichment columns, stat templates, aliases, genre presets
-- Run on PERSONAL Supabase first for validation, then PUBLIC.
-- Safe to re-run — all statements use IF NOT EXISTS / DO NOTHING guards.

-- ── 1. Enrich dim.dim_games ───────────────────────────────────────────────────

ALTER TABLE dim.dim_games
    ADD COLUMN IF NOT EXISTS igdb_id      INTEGER,
    ADD COLUMN IF NOT EXISTS igdb_slug    TEXT,
    ADD COLUMN IF NOT EXISTS cover_url    TEXT,
    ADD COLUMN IF NOT EXISTS steam_app_id INTEGER;

-- Unique constraint: one dim_games row per IGDB game
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_dim_games_igdb_id'
    ) THEN
        ALTER TABLE dim.dim_games ADD CONSTRAINT uq_dim_games_igdb_id UNIQUE (igdb_id);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_dim_games_igdb_id
    ON dim.dim_games (igdb_id);

CREATE INDEX IF NOT EXISTS idx_dim_games_steam_app_id
    ON dim.dim_games (steam_app_id);


-- ── 2. Stat templates — priority 2 fallback (personal only) ──────────────────
-- Curated canonical stat suggestions per game, keyed by stable IGDB ID.
-- Synced to public via admin.py alongside dim_games.

CREATE TABLE IF NOT EXISTS dim.dim_game_stat_templates (
    igdb_id    INTEGER PRIMARY KEY,
    game_name  TEXT    NOT NULL,
    stat_types TEXT[]  NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed data populated by scripts/igdb_seed_templates.sql AFTER the import runs.
-- That script looks up igdb_id from the real dim_games rows by game name
-- so there is no risk of wrong IDs here.


-- ── 3. Genre presets — priority 3 fallback ───────────────────────────────────
-- Maps IGDB genre names to default stat suggestions when no template exists.
-- igdb_genre_id is stable and never changes.

CREATE TABLE IF NOT EXISTS dim.dim_genre_presets (
    igdb_genre_id  INTEGER PRIMARY KEY,
    igdb_genre_name TEXT    NOT NULL,
    game_genre     TEXT    NOT NULL,
    game_subgenre  TEXT,
    stat_types     TEXT[]  NOT NULL
);

-- game_genre / game_subgenre values must match GENRES in web/lib/constants.ts exactly.
-- IGDB genre IDs are non-sequential (IGDB's own numbering — gaps are normal).
INSERT INTO dim.dim_genre_presets (igdb_genre_id, igdb_genre_name, game_genre, game_subgenre, stat_types) VALUES
    (2,  'Point-and-click',   'Adventure',                 'Graphic',                         ARRAY['Score','Time','Collectibles']),
    (4,  'Fighting',          'Fighting',                  '2D Versus',                        ARRAY['Wins','KOs','Combos']),
    (5,  'Shooter',           'Shooter',                   'Military',                         ARRAY['Eliminations','Deaths','Damage']),
    (7,  'Music',             'Party',                     'Rhythm & Music',                   ARRAY['Score','Accuracy','Streak']),
    (8,  'Platform',          'Platformers',               'Traditional 2D Side‑Scrolling',    ARRAY['Score','Lives','Coins Collected']),
    (9,  'Puzzle',            'Puzzle',                    'Logic',                            ARRAY['Score','Level','Time']),
    (10, 'Racing',            'Racing',                    'Simulation‑Style',                 ARRAY['Position','Lap Time','Wins']),
    (11, 'Real Time Strategy','Real-Time Strategy (RTS)',  'Classic Base‑Building',            ARRAY['Wins','Units Lost','Resources Gathered']),
    (12, 'Role-playing (RPG)','Role-Playing (RPG)',        'Action',                           ARRAY['Level','XP','Quests Completed']),
    (13, 'Simulator',         'Simulation',                'Other',                            ARRAY['Score','Time','Accuracy']),
    (14, 'Sport',             'Sports',                    'Simulation',                       ARRAY['Score','Goals','Assists']),
    (15, 'Strategy',          'Strategy',                  'Turn-Based Strategy (TBS)',         ARRAY['Wins','Units Lost','Resources Gathered']),
    (16, 'Turn-based strategy','Strategy',                 'Turn-Based Strategy (TBS)',         ARRAY['Wins','Units Lost','Resources Gathered']),
    (24, 'Tactical',          'Strategy',                  'Real-Time Tactics (RTT)',           ARRAY['Wins','Units Lost','Resources Gathered']),
    (25, 'Hack and slash',    'Action RPGs',               'Hack-and-Slash',                   ARRAY['Eliminations','Combos','Score']),
    (26, 'Quiz/Trivia',       'Party',                     'Trivia',                           ARRAY['Score','Wins','Time']),
    (30, 'Pinball',           'Casual',                    'Hyper‑Casual',                     ARRAY['Score','Lives','Level']),
    (31, 'Adventure',         'Adventure',                 'Real-Time 3D',                     ARRAY['Score','Time','Collectibles']),
    (32, 'Indie',             'Action-Adventure',          'Open-World',                       ARRAY['Score','Eliminations','Deaths']),
    (33, 'Arcade',            'Casual',                    'Hyper‑Casual',                     ARRAY['Score','Lives','Level']),
    (34, 'Visual Novel',      'Adventure',                 'Visual Novel',                     ARRAY['Score','Time','Choices']),
    (35, 'Card & Board Game', 'Casual',                    'Card & Board',                     ARRAY['Wins','Score','Rounds']),
    (36, 'MOBA',              'Strategy',                  'Real-Time Strategy (RTS)',          ARRAY['Eliminations','Deaths','Assists'])
ON CONFLICT (igdb_genre_id) DO NOTHING;


-- ── 4. Stat alias glossary ────────────────────────────────────────────────────
-- Maps alternate stat names to canonical values for community frequency queries
-- and leaderboard normalization.

CREATE TABLE IF NOT EXISTS dim.dim_stat_aliases (
    alias         TEXT PRIMARY KEY,
    canonical     TEXT NOT NULL,
    display_label TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO dim.dim_stat_aliases (alias, canonical, display_label) VALUES
    ('Kills',       'Eliminations', 'Eliminations'),
    ('Frags',       'Eliminations', 'Eliminations'),
    ('Takedowns',   'Eliminations', 'Eliminations'),
    ('Deaths',      'Deaths',       'Respawns'),
    ('Respawns',    'Deaths',       'Respawns'),
    ('KOs',         'Deaths',       'Respawns'),
    ('K/D',         'K/D Ratio',    'E/R Ratio'),
    ('Kill/Death',  'K/D Ratio',    'E/R Ratio'),
    ('Dmg',         'Damage',       'Damage'),
    ('Heals',       'Healing',      'Healing'),
    ('XP',          'Experience',   'XP'),
    ('CS',          'CS',           'Creep Score'),
    ('Last Hits',   'CS',           'Creep Score'),
    ('HS%',         'HS%',          'Headshot %'),
    ('Headshots',   'HS%',          'Headshot %'),
    ('ADR',         'ADR',          'Avg Damage/Round'),
    ('GPM',         'GPM',          'Gold Per Min'),
    ('XPM',         'XPM',          'XP Per Min'),
    ('Placement',   'Placement',    'Placement'),
    ('Rank',        'Placement',    'Placement')
ON CONFLICT (alias) DO NOTHING;
