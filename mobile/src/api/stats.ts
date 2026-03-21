const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';

function authHeaders(jwt: string) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${jwt}`,
  };
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StatEntry {
  label: string;
  value: number;
}

export interface AddStatsPayload {
  player_name: string;
  game_name: string;
  game_installment?: string;
  game_mode?: string;
  stat1_label: string;
  stat1_value: number;
  stat2_label?: string;
  stat2_value?: number;
  stat3_label?: string;
  stat3_value?: number;
  chart_type?: 'bar' | 'line';
  platform?: 'twitter' | 'instagram' | 'both' | 'none';
  is_live?: boolean;
  credit_style?: string;
}

export interface StatHistoryPoint {
  date: string;
  stat_type: string;
  stat_value: number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function addStats(jwt: string, payload: AddStatsPayload): Promise<{ message: string }> {
  const res = await fetch(`${API_URL}/api/add_stats`, {
    method: 'POST',
    headers: authHeaders(jwt),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? `Failed to add stats (${res.status})`);
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

  const res = await fetch(`${API_URL}/api/get_stats?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? `Failed to fetch stats (${res.status})`);
  }
  return res.json();
}

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
