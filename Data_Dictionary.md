# Data Dictionary: Video Game Stats Database

This document details the schemas and tables for the **AWS Redshift Serverless** database. The database follows a **star schema**, separating descriptive "dimensions" from quantitative "facts."

---

## Schema: `dim` (Dimension Tables)

This schema holds the descriptive context (the "who," "what," "where").

### Table: `dim.dim_users`

Stores user account information, authenticated via Google.

| Column Name | Data Type | Constraints | Description |
|--------------|------------|-------------|--------------|
| `user_id` | INT | IDENTITY(1, 1) PK | Primary Key. Unique, auto-incrementing ID for the user. |
| `user_email` | VARCHAR(255) | NOT NULL, UNIQUE | The user's Google email address. |
| `is_trusted` | BOOLEAN | NOT NULL, DEFAULT FALSE | Flag to grant admin privileges. `True = Admin`, `False = Guest`. |

---

### Table: `dim.dim_players`

Stores player profiles. Each user can have multiple player profiles.

| Column Name | Data Type | Constraints | Description |
|--------------|------------|-------------|--------------|
| `player_id` | INT | IDENTITY(1, 1) PK | Primary Key. Unique, auto-incrementing ID for the player. |
| `player_name` | VARCHAR(255) | NOT NULL | The in-game name or alias of the player. |
| `user_id` | INTEGER | NOT NULL, FK | Foreign Key. Links to `dim.dim_users(user_id)`. |
| `created_at` | TIMESTAMP | DEFAULT GETDATE() | Timestamp of when the player profile was created. |

---

### Table: `dim.dim_games`

Stores information about unique games.

| Column Name | Data Type | Constraints | Description |
|--------------|------------|-------------|--------------|
| `game_id` | INT | IDENTITY(1, 1) PK | Primary Key. Unique, auto-incrementing ID for the game. |
| `game_name` | VARCHAR(255) | NOT NULL, UNIQUE | The official name of the game franchise or standalone game (e.g., "Call of Duty"). |
| `game_installment` | VARCHAR(255) | NULL | The game's installment (e.g., "Warzone, Black Ops 7"). |
| `game_genre` | VARCHAR(255) | NULL | The primary genre (e.g., "Action", "RPG"). |
| `game_subgenre` | VARCHAR(255) | NULL | The specific subgenre (e.g., "FPS", "Soulslike"). |
| `created_at` | TIMESTAMP | DEFAULT GETDATE() | Timestamp of when the game was first added. |
| `last_played_at` | TIMESTAMP | DEFAULT GETDATE() | Timestamp of the last time stats were recorded for this game. |

---

## Schema: `fact` (Fact Table)

This schema holds measurable events and numeric data.

### Table: `fact.fact_game_stats`

Stores the results of a specific stat for a specific match. This is the central table for all analyses.

| Column Name | Data Type | Constraints | Description |
|--------------|------------|-------------|--------------|
| `stat_id` | INT | IDENTITY(1, 1) PK | Primary Key. Unique, auto-incrementing ID for the stat entry. |
| `game_id` | INTEGER | FK | Foreign Key. Links to `dim.dim_games(game_id)`. |
| `player_id` | INTEGER | FK | Foreign Key. Links to `dim.dim_players(player_id)`. |
| `stat_type` | VARCHAR(50) | NOT NULL | The name of the stat being measured (e.g., "Kills", "Score"). |
| `stat_value` | INTEGER |  | The numeric value of the stat (e.g., 10, 1500). |
| `game_mode` | VARCHAR(255) |  | The specific mode played (e.g., "Team Deathmatch", "Main"). |
| `game_level` | INTEGER | NULL | The level, wave, or mission number (e.g., 10, 3). |
| `win` | INTEGER | NULL | A boolean-like integer. 1 = Win, 0 = Loss. |
| `ranked` | INTEGER | NULL | A boolean-like integer. 1 = Ranked, 0 = Unranked. |
| `pre_match_rank_value` | VARCHAR(50) | NULL | The player's rank before the match (e.g., "Gold 2"). |
| `post_match_rank_value` | VARCHAR(50) | NULL | The player's rank after the match (e.g., "Gold 1"). |
| `played_at` | TIMESTAMP | DEFAULT GETDATE() | Timestamp of when the stat was recorded. |
