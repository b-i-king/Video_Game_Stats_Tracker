const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';

function authHeaders(jwt: string) {
  return {
    'Content-Type': 'application/json',
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

// Used by StatsHistoryScreen
export interface StatHistoryPoint {
  date: string;
  stat_type: string;
  stat_value: number;
}

// ── Keep-alive ────────────────────────────────────────────────────────────────
// Call on app launch to wake the Render service before the user authenticates.
export function pingHealth(): void {
  if (!API_URL) return;
  fetch(`${API_URL}/health`, { method: 'GET' }).catch(() => {});
}

// ── Player endpoints ──────────────────────────────────────────────────────────

export async function getPlayers(jwt: string): Promise<Player[]> {
  const res = await fetch(`${API_URL}/api/get_players`, { headers: authHeaders(jwt) });
  if (!res.ok) throw new Error(`Failed to load players (${res.status})`);
  const data = await res.json();
  return data.players ?? [];
}

// ── Game endpoints ────────────────────────────────────────────────────────────

export async function getFranchises(jwt: string): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/get_game_franchises`, { headers: authHeaders(jwt) });
  if (!res.ok) throw new Error(`Failed to load franchises (${res.status})`);
  const data = await res.json();
  return data.game_franchises ?? [];
}

export async function getInstallments(jwt: string, franchise: string): Promise<Installment[]> {
  const encoded = encodeURIComponent(franchise);
  const res = await fetch(`${API_URL}/api/get_game_installments/${encoded}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load installments (${res.status})`);
  const data = await res.json();
  return data.game_installments ?? [];
}

export async function getGameRanks(jwt: string, gameId: number): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/get_game_ranks/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getGameModes(jwt: string, gameId: number): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/get_game_modes/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return ['Main'];
  return res.json();
}

export async function getGameStatTypes(jwt: string, gameId: number): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/get_game_stat_types/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getGameDetails(jwt: string, gameId: number): Promise<GameDetails | null> {
  const res = await fetch(`${API_URL}/api/get_game_details/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function getAllGames(jwt: string): Promise<GameDetails[]> {
  const res = await fetch(`${API_URL}/api/get_games`, { headers: authHeaders(jwt) });
  if (!res.ok) throw new Error(`Failed to load games (${res.status})`);
  const data = await res.json();
  return data.games ?? [];
}

// ── Stats endpoints ───────────────────────────────────────────────────────────

export async function addStats(
  jwt: string,
  payload: AddStatsPayload
): Promise<{ message: string; social_media: string }> {
  const res = await fetch(`${API_URL}/api/add_stats`, {
    method: 'POST',
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `Submit failed (${res.status})`);
  }
  return res.json();
}

export async function getStats(
  jwt: string,
  playerName: string,
  gameName: string,
  gameInstallment?: string,
  gameMode?: string,
  limit = 20
): Promise<StatHistoryPoint[]> {
  const params = new URLSearchParams({
    player_name: playerName,
    game_name: gameName,
    limit: String(limit),
  });
  if (gameInstallment) params.set('game_installment', gameInstallment);
  if (gameMode) params.set('game_mode', gameMode);
  const res = await fetch(`${API_URL}/api/get_stats?${params}`, { headers: authHeaders(jwt) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `Failed to fetch stats (${res.status})`);
  }
  return res.json();
}

export async function getRecentStats(jwt: string): Promise<StatEntry[]> {
  const res = await fetch(`${API_URL}/api/get_recent_stats`, { headers: authHeaders(jwt) });
  if (!res.ok) throw new Error(`Failed to load recent stats (${res.status})`);
  const data = await res.json();
  return data.stats ?? [];
}

export async function deleteStats(jwt: string, statId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/delete_stats/${statId}`, {
    method: 'DELETE',
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete failed (${res.status})`);
}

export async function updateStats(
  jwt: string,
  statId: number,
  payload: Partial<StatEntry>
): Promise<void> {
  const res = await fetch(`${API_URL}/api/update_stats/${statId}`, {
    method: 'PUT',
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
  const res = await fetch(`${API_URL}/api/update_player/${playerId}`, {
    method: 'PUT',
    headers: authHeaders(jwt),
    body: JSON.stringify({ player_name: newName }),
  });
  if (!res.ok) throw new Error(`Update player failed (${res.status})`);
}

export async function deletePlayer(jwt: string, playerId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/delete_player/${playerId}`, {
    method: 'DELETE',
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete player failed (${res.status})`);
}

export async function updateGame(
  jwt: string,
  gameId: number,
  payload: Partial<GameDetails>
): Promise<void> {
  const res = await fetch(`${API_URL}/api/update_game/${gameId}`, {
    method: 'PUT',
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Update game failed (${res.status})`);
}

export async function deleteGame(jwt: string, gameId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/delete_game/${gameId}`, {
    method: 'DELETE',
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete game failed (${res.status})`);
}

// ── OBS / Queue ───────────────────────────────────────────────────────────────

export async function getObsStatus(jwt: string): Promise<{ obs_active: boolean }> {
  const res = await fetch(`${API_URL}/api/obs_status`, { headers: authHeaders(jwt) });
  if (!res.ok) return { obs_active: false };
  return res.json();
}

export async function setLiveState(
  jwt: string,
  playerId: number,
  gameId: number
): Promise<void> {
  await fetch(`${API_URL}/api/set_live_state`, {
    method: 'POST',
    headers: authHeaders(jwt),
    body: JSON.stringify({ player_id: playerId, game_id: gameId }),
  });
}

export async function setObsActive(jwt: string, active: boolean): Promise<void> {
  await fetch(`${API_URL}/api/set_obs_active`, {
    method: 'POST',
    headers: authHeaders(jwt),
    body: JSON.stringify({ active }),
  });
}

export async function getQueueStatus(
  jwt: string
): Promise<{ pending: number; processing: number; sent: number; failed: number }> {
  const res = await fetch(`${API_URL}/api/queue_status`, { headers: authHeaders(jwt) });
  if (!res.ok) return { pending: 0, processing: 0, sent: 0, failed: 0 };
  return res.json();
}

export async function retryFailed(jwt: string): Promise<{ reset_count: number }> {
  const res = await fetch(`${API_URL}/api/retry_failed`, {
    method: 'POST',
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error('Retry failed');
  return res.json();
}

// ── OBS stat ticker (used by useTicker / StatsHistoryScreen) ─────────────────

export async function getStatTicker(
  jwt: string,
  playerName: string
): Promise<{ ticker_url: string }> {
  const params = new URLSearchParams({ player_name: playerName });
  const res = await fetch(`${API_URL}/api/get_stat_ticker?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Ticker fetch failed (${res.status})`);
  return res.json();
}
