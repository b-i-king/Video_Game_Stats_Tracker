// ── Flask API helper ──────────────────────────────────────────────────────────
// All fetch calls go through these typed functions.
// The Flask base URL is read from NEXT_PUBLIC_FLASK_API_URL (client) or
// FLASK_API_URL (server). For client components, expose the URL via
// NEXT_PUBLIC_FLASK_API_URL in .env.local.

const BASE =
  process.env.NEXT_PUBLIC_FLASK_API_URL ??
  process.env.FLASK_API_URL ??
  "";

function authHeaders(jwt: string) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${jwt}`,
  };
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Player {
  player_id: number;
  player_name: string;
}

export interface Installment {
  game_id: number;
  installment_name: string;
}

export interface GameDetails {
  game_id: number;
  game_name: string;
  game_series?: string;
  game_genre?: string;
  game_subgenre?: string;
}

export interface StatEntry {
  stat_id: number;
  player_name: string;
  game_name: string;
  game_id: number;
  stat_type: string;
  stat_value: number;
  game_mode?: string;
  game_level?: number;
  win?: number;
  ranked?: number;
  pre_match_rank_value?: string;
  post_match_rank_value?: string;
  played_at: string;
}

export interface StatRow {
  stat_type: string;
  stat_value: number;
  game_mode: string;
  solo_mode: number;
  party_size: string;
  game_level: number | null;
  win: number | null;
  ranked: number;
  pre_match_rank_value: string | null;
  post_match_rank_value: string | null;
  overtime: number;
  difficulty: string | null;
  input_device: string;
  platform: string;
  first_session_of_day: number;
  was_streaming: number;
}

export interface AddStatsPayload {
  player_name: string;
  game_name: string;
  game_installment?: string | null;
  game_genre?: string | null;
  game_subgenre?: string | null;
  stats: StatRow[];
  is_live: boolean;
  queue_mode: boolean;
  credit_style: string;
}

// ── Keep-alive ────────────────────────────────────────────────────────────────
// Pings the public /health endpoint to wake Render before the user logs in.
// No auth required — fire-and-forget from the root layout.
export function pingHealth(): void {
  if (!BASE) return;
  fetch(`${BASE}/health`, { method: "GET" }).catch(() => {});
}

// ── Player endpoints ──────────────────────────────────────────────────────────

export async function getPlayers(jwt: string): Promise<Player[]> {
  const res = await fetch(`${BASE}/api/get_players`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load players (${res.status})`);
  const data = await res.json();
  return data.players ?? [];
}

// ── Game endpoints ────────────────────────────────────────────────────────────

export async function getFranchises(jwt: string): Promise<string[]> {
  const res = await fetch(`${BASE}/api/get_game_franchises`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load franchises (${res.status})`);
  const data = await res.json();
  return data.game_franchises ?? [];
}

export async function getInstallments(
  jwt: string,
  franchise: string
): Promise<Installment[]> {
  const encoded = encodeURIComponent(franchise);
  const res = await fetch(`${BASE}/api/get_game_installments/${encoded}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load installments (${res.status})`);
  const data = await res.json();
  return data.game_installments ?? [];
}

export async function getGameRanks(
  jwt: string,
  gameId: number
): Promise<string[]> {
  const res = await fetch(`${BASE}/api/get_game_ranks/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getGameModes(
  jwt: string,
  gameId: number
): Promise<string[]> {
  const res = await fetch(`${BASE}/api/get_game_modes/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return ["Main"];
  return res.json();
}

export async function getGameStatTypes(
  jwt: string,
  gameId: number
): Promise<string[]> {
  const res = await fetch(`${BASE}/api/get_game_stat_types/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getGameContext(
  jwt: string,
  gameId: number
): Promise<{ ranks: string[]; modes: string[]; stat_types: string[] }> {
  const res = await fetch(`${BASE}/api/get_game_context/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return { ranks: [], modes: ["Main"], stat_types: [] };
  return res.json();
}

export async function getGameDetails(
  jwt: string,
  gameId: number
): Promise<GameDetails | null> {
  const res = await fetch(`${BASE}/api/get_game_details/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function getAllGames(jwt: string): Promise<GameDetails[]> {
  const res = await fetch(`${BASE}/api/get_games`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load games (${res.status})`);
  const data = await res.json();
  return data.games ?? [];
}

// ── Stats endpoints ───────────────────────────────────────────────────────────

export async function addStats(
  jwt: string,
  payload: AddStatsPayload
): Promise<{ message: string; social_media: string }> {
  const res = await fetch(`${BASE}/api/add_stats`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as { error?: string }).error ?? `Submit failed (${res.status})`
    );
  }
  return res.json();
}

export async function getRecentStats(jwt: string): Promise<StatEntry[]> {
  const res = await fetch(`${BASE}/api/get_recent_stats`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load recent stats (${res.status})`);
  const data = await res.json();
  return data.stats ?? [];
}

export async function deleteStats(jwt: string, statId: number): Promise<void> {
  const res = await fetch(`${BASE}/api/delete_stats/${statId}`, {
    method: "DELETE",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete failed (${res.status})`);
}

export async function updateStats(
  jwt: string,
  statId: number,
  payload: Partial<StatEntry>
): Promise<void> {
  const res = await fetch(`${BASE}/api/update_stats/${statId}`, {
    method: "PUT",
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Update failed (${res.status})`);
}

// ── Player / Game edit / delete ───────────────────────────────────────────────

export async function updatePlayer(
  jwt: string,
  playerId: number,
  newName: string
): Promise<void> {
  const res = await fetch(`${BASE}/api/update_player/${playerId}`, {
    method: "PUT",
    headers: authHeaders(jwt),
    body: JSON.stringify({ player_name: newName }),
  });
  if (!res.ok) throw new Error(`Update player failed (${res.status})`);
}

export async function deletePlayer(
  jwt: string,
  playerId: number
): Promise<void> {
  const res = await fetch(`${BASE}/api/delete_player/${playerId}`, {
    method: "DELETE",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete player failed (${res.status})`);
}

export async function updateGame(
  jwt: string,
  gameId: number,
  payload: Partial<GameDetails>
): Promise<void> {
  const res = await fetch(`${BASE}/api/update_game/${gameId}`, {
    method: "PUT",
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Update game failed (${res.status})`);
}

export async function deleteGame(
  jwt: string,
  gameId: number
): Promise<void> {
  const res = await fetch(`${BASE}/api/delete_game/${gameId}`, {
    method: "DELETE",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete game failed (${res.status})`);
}

// ── OBS / Queue ───────────────────────────────────────────────────────────────

export async function getObsStatus(
  jwt: string
): Promise<{ obs_active: boolean }> {
  const res = await fetch(`${BASE}/api/obs_status`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return { obs_active: false };
  return res.json();
}

export async function setLiveState(
  jwt: string,
  playerId: number,
  gameId: number
): Promise<void> {
  await fetch(`${BASE}/api/set_live_state`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ player_id: playerId, game_id: gameId }),
  });
}

export async function setObsActive(
  jwt: string,
  active: boolean
): Promise<void> {
  await fetch(`${BASE}/api/set_obs_active`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ active }),
  });
}

export async function getQueueStatus(
  jwt: string
): Promise<{ pending: number; processing: number; sent: number; failed: number }> {
  const res = await fetch(`${BASE}/api/queue_status`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return { pending: 0, processing: 0, sent: 0, failed: 0 };
  return res.json();
}

export async function retryFailed(
  jwt: string
): Promise<{ reset_count: number }> {
  const res = await fetch(`${BASE}/api/retry_failed`, {
    method: "POST",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Retry failed");
  return res.json();
}

export async function askBolt(
  jwt: string,
  prompt: string
): Promise<string> {
  const res = await fetch(`${BASE}/api/ask`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) throw new Error("Bolt unavailable");
  const data = await res.json();
  return data.reply as string;
}
