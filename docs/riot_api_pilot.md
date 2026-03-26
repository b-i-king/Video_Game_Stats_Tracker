# Riot Games API — Pilot Integration Plan

Riot Games is the most realistic first integration for this project. They offer a genuine public developer API with real documentation, stable versioning, and granular per-match stat data across multiple titles.

---

## Why Riot First

| Factor | Details |
|---|---|
| **API availability** | Public — apply at developer.riotgames.com, get a key same day |
| **Data quality** | Full match timeline: kills, deaths, assists, damage, rank, champion/agent, result |
| **Games covered** | Valorant, League of Legends, TFT, Wild Rift |
| **Rate limits** | Development key: 20 req/2s, 100 req/2min. Production key (apply): much higher |
| **Auth model** | API key in header — no OAuth needed to read public match history |
| **Stability** | Riot versioned their API properly; endpoints don't randomly break |

---

## Prerequisites

1. **Riot Developer Account** — register at `developer.riotgames.com`
2. **Development API Key** — issued immediately, expires every 24h (rotate daily or apply for production key)
3. **Production Key** — apply after building a working prototype; required for real user traffic
4. **Supabase migration complete** — `app.user_integrations` and `app.integration_imports` tables must exist

---

## Core API Concepts

### Player Identity
Every Riot account has two identifiers:

```
PUUID  — globally unique, never changes, use this as your key
        e.g. "abc123...40-char-uuid"

Riot ID — human-readable: "PlayerName#TAG"
        e.g. "BOL#NA1"
```

To resolve a Riot ID → PUUID:
```
GET https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
```

### Match History (Valorant example)
```
GET https://na.api.riotgames.com/val/match/v1/matchlists/by-puuid/{puuid}
```

Returns a list of `matchId` strings. Then fetch each match:
```
GET https://na.api.riotgames.com/val/match/v1/matches/{matchId}
```

### Match History (League of Legends)
```
GET https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20
GET https://americas.api.riotgames.com/lol/match/v5/matches/{matchId}
```

---

## Data Mapping → fact_game_stats

| Riot field | Our column | Notes |
|---|---|---|
| `kills` | `stat_value` where `stat_type = 'Eliminations'` | |
| `deaths` | `stat_value` where `stat_type = 'Respawns'` | |
| `assists` | `stat_value` where `stat_type = 'Assists'` | |
| `combatScore` / `totalDamageDealt` | `stat_value` where `stat_type = 'Score'` | Varies by game |
| `win` (bool) | `win` (0/1) | |
| `queueId` / `queueType` | `game_mode` | Ranked, Normal, etc. |
| `tierAfterUpdate` | `post_match_rank_value` | |
| `tierBeforeUpdate` | `pre_match_rank_value` | |
| `gameStartMillis` | `played_at` | Convert ms → TIMESTAMPTZ |
| `matchId` | `integration_imports.external_match_id` | Used to prevent duplicate imports |
| `'riot'` (literal) | `source` | Marks row as auto-imported |
| `FALSE` | `is_editable` | Locks the row from edit/delete |

Each match generates **multiple rows** in `fact_game_stats` — one per `stat_type` (Eliminations, Respawns, Assists, Score) — mirroring how manual entries work.

---

## Session End Detection

Riot's match API only returns **completed** matches. A player who disconnects mid-match still appears in the result with whatever stats accumulated. You can filter incomplete matches by checking:

```python
# Valorant: players who left early have roundsPlayed < totalRounds
if player['stats']['roundsPlayed'] < match_info['roundsPlayed']:
    skip_or_flag = True
```

For League: check `timePlayed` vs `gameDuration` — if significantly shorter, the player likely left early.

---

## Implementation Steps (Post-Supabase)

### Step 1 — Backend: Connect endpoint
```
POST /api/integrations/riot/connect
Body: { "riot_id": "BOL#NA1" }
```
- Calls Riot API to resolve PUUID
- Stores `(user_email, platform='riot', platform_user_id=puuid)` in `app.user_integrations`
- Returns success/error

### Step 2 — Backend: Poller Lambda (or scheduled Flask job)
- Runs on a schedule (every 15 min, or triggered post-submit)
- For each active `user_integrations` row where `platform = 'riot'`:
  1. Fetch latest match IDs for that PUUID
  2. Filter out any `matchId` already in `app.integration_imports`
  3. For new matches: fetch full match data, map to `fact_game_stats` rows
  4. Insert stats with `source='riot'`, `is_editable=FALSE`
  5. Insert `matchId` into `app.integration_imports`

### Step 3 — Frontend: Connect flow
- User enters their `Riot ID` (e.g. `BOL#NA1`) in the Integrations tab
- App validates it resolves to a PUUID
- Stores connection, shows "● Connected" badge

### Step 4 — UI: Lock imported rows
- In `EditTab` and `DeleteTab`, check `is_editable` flag
- Show a platform badge (e.g. `[Riot]`) instead of edit/delete buttons for locked rows

---

## Rate Limit Strategy

Development key limits are tight (100 req/2min). To stay within limits:

- **Batch fetch**: pull the last 5 match IDs, not 20, per poll cycle
- **Dedup early**: check `integration_imports` before calling the match detail endpoint
- **Backoff**: implement exponential backoff on 429 responses
- **Cache PUUID**: store it in `user_integrations`, never re-resolve unless user changes Riot ID

---

## Environment Variables Needed (when ready)

```
RIOT_API_KEY=RGAPI-xxxx-xxxx-xxxx   # from developer.riotgames.com
RIOT_REGION=na1                      # na1, euw1, kr, etc.
RIOT_ROUTING=americas                # americas, europe, asia (for account/match v5)
```

---

## Reference Links

- Developer portal: `developer.riotgames.com`
- API docs: `developer.riotgames.com/apis`
- Valorant match endpoint: `val/match/v1`
- LoL match v5 endpoint: `lol/match/v5`
- Rate limit guide: `developer.riotgames.com/docs/portal#web-portal_rate-limiting`
