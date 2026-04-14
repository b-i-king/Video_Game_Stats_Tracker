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

/** If the server returns 401 the Flask JWT has expired — redirect to sign-in. */
function handle401(res: Response): void {
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/api/auth/signin";
  }
}

/** Wrapper around fetch that automatically triggers 401 redirect. */
async function fetchWithAuth(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  handle401(res);
  return res;
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
  game_installment?: string | null;
  game_genre?: string;
  game_subgenre?: string;
}

export interface StatEntry {
  stat_id: number;
  player_name: string;
  game_name: string;
  game_installment?: string | null;
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
  is_outlier?: boolean;
  z_score?: number | null;
  percentile?: number | null;
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
  queue_platforms: string[];
  active_platforms: string[];
  credit_style: string;
}

export interface KpiStat {
  stat_type: string;
  value: number;
  lower_is_better: boolean;
  ci_low?: number | null;
  ci_high?: number | null;
  n_sessions?: number;
  today_z_score?: number | null;
}

export interface SummaryData {
  today_avg: KpiStat[];
  all_time_best: KpiStat[];
}

export interface HeatmapCell {
  dow: number;         // 0 = Sunday … 6 = Saturday
  hour: number;        // 0–23
  session_count: number;
}

export interface HeatmapData {
  cells: HeatmapCell[];
  max_sessions: number;
}

export interface StreakData {
  current_streak: number;
  longest_streak: number;
  last_session: string | null;
  total_session_days: number;
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
  const res = await fetchWithAuth(`${BASE}/api/get_players`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load players (${res.status})`);
  const data = await res.json();
  return data.players ?? [];
}

// ── Game endpoints ────────────────────────────────────────────────────────────

export async function getFranchises(jwt: string): Promise<string[]> {
  const res = await fetchWithAuth(`${BASE}/api/get_game_franchises`, {
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
  const res = await fetchWithAuth(`${BASE}/api/get_game_installments/${encoded}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/get_game_ranks/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.ranks ?? [];
}

export async function getGameModes(
  jwt: string,
  gameId: number
): Promise<string[]> {
  const res = await fetchWithAuth(`${BASE}/api/get_game_modes/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return ["Main"];
  const data = await res.json();
  return data.game_modes ?? ["Main"];
}

export async function getGameStatTypes(
  jwt: string,
  gameId: number
): Promise<string[]> {
  const res = await fetchWithAuth(`${BASE}/api/get_game_stat_types/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.stat_types ?? [];
}

export async function getGameContext(
  jwt: string,
  gameId: number
): Promise<{ ranks: string[]; modes: string[]; stat_types: string[] }> {
  const res = await fetchWithAuth(`${BASE}/api/get_game_context/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return { ranks: [], modes: ["Main"], stat_types: [] };
  return res.json();
}

export async function getGameDetails(
  jwt: string,
  gameId: number
): Promise<GameDetails | null> {
  const res = await fetchWithAuth(`${BASE}/api/get_game_details/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function getAllGames(jwt: string): Promise<GameDetails[]> {
  const res = await fetchWithAuth(`${BASE}/api/get_games`, {
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
  const res = await fetchWithAuth(`${BASE}/api/add_stats`, {
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
  const res = await fetchWithAuth(`${BASE}/api/get_recent_stats`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load recent stats (${res.status})`);
  const data = await res.json();
  return data.stats ?? [];
}

export interface LastSession {
  game_title: string;
  player_name: string;
  game_mode: string | null;
  difficulty: string | null;
  platform: string | null;
  played_at: string | null;
  win_loss: "Win" | "Loss" | null;
  stats: { stat_type: string; stat_value: number }[];
}

export async function getLastSession(jwt: string): Promise<LastSession | null> {
  const res = await fetchWithAuth(`${BASE}/api/last_session`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load last session (${res.status})`);
  const data = await res.json();
  return data.session ?? null;
}

export async function deleteStats(jwt: string, statId: number): Promise<void> {
  const res = await fetchWithAuth(`${BASE}/api/delete_stats/${statId}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/update_stats/${statId}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/update_player/${playerId}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/delete_player/${playerId}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/update_game/${gameId}`, {
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
  const res = await fetchWithAuth(`${BASE}/api/delete_game/${gameId}`, {
    method: "DELETE",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Delete game failed (${res.status})`);
}

// ── OBS / Queue ───────────────────────────────────────────────────────────────

export async function getObsStatus(
  jwt: string
): Promise<{ obs_active: boolean }> {
  const res = await fetchWithAuth(`${BASE}/api/obs_status`, {
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
  const res = await fetch(`${BASE}/api/set_live_state`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ player_id: playerId, game_id: gameId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `set_live_state failed (${res.status})`);
  }
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
  const res = await fetchWithAuth(`${BASE}/api/queue_status`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) return { pending: 0, processing: 0, sent: 0, failed: 0 };
  return res.json();
}

export async function retryFailed(
  jwt: string
): Promise<{ reset_count: number }> {
  const res = await fetchWithAuth(`${BASE}/api/retry_failed`, {
    method: "POST",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Retry failed");
  return res.json();
}

export async function getSummary(
  jwt: string,
  gameId: number,
  playerId: number,
  gameMode?: string
): Promise<SummaryData> {
  const params = new URLSearchParams({ player_id: String(playerId) });
  if (gameMode) params.set("game_mode", gameMode);
  const res = await fetchWithAuth(`${BASE}/api/get_summary/${gameId}?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load summary (${res.status})`);
  return res.json();
}

export async function getInteractiveChart(
  jwt: string,
  gameId: number,
  playerId: number,
  gameMode?: string,
  tz?: string
): Promise<string> {
  const params = new URLSearchParams({ player_id: String(playerId) });
  if (gameMode) params.set("game_mode", gameMode);
  if (tz) params.set("tz", tz);
  const res = await fetchWithAuth(`${BASE}/api/get_interactive_chart/${gameId}?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load chart (${res.status})`);
  return res.text();
}

export async function downloadChart(
  jwt: string,
  gameId: number,
  playerId: number,
  platform: "twitter" | "instagram"
): Promise<void> {
  const res = await fetchWithAuth(`${BASE}/api/download_chart`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ game_id: gameId, player_id: playerId, platform }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `player_${playerId}_${platform}_chart.png`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getHeatmap(
  jwt: string,
  gameId: number,
  playerId: number,
  tz?: string
): Promise<HeatmapData> {
  const params = new URLSearchParams({ player_id: String(playerId) });
  if (tz) params.set("tz", tz);
  const res = await fetchWithAuth(`${BASE}/api/get_heatmap/${gameId}?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load heatmap (${res.status})`);
  return res.json();
}

export async function getTickerFacts(
  jwt: string,
  gameId: number,
  playerId: number,
  tz?: string
): Promise<{ facts: string[]; sessions: number }> {
  const params = new URLSearchParams({ player_id: String(playerId) });
  if (tz) params.set("tz", tz);
  const res = await fetchWithAuth(`${BASE}/api/get_ticker_facts/${gameId}?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load ticker facts (${res.status})`);
  return res.json();
}

export async function getStreaks(
  jwt: string,
  gameId: number,
  playerId: number,
  tz?: string
): Promise<StreakData> {
  const params = new URLSearchParams({ player_id: String(playerId) });
  if (tz) params.set("tz", tz);
  const res = await fetchWithAuth(`${BASE}/api/get_streaks/${gameId}?${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error(`Failed to load streaks (${res.status})`);
  return res.json();
}

export async function askBolt(
  jwt: string,
  prompt: string
): Promise<string> {
  const res = await fetchWithAuth(`${BASE}/api/ask`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) throw new Error("Bolt unavailable");
  const data = await res.json();
  return data.reply as string;
}

export interface AiUsage {
  used: number;
  limit: number | null;   // null = owner (no cap)
  reset_date: string;     // ISO date — first day of next month
  is_unlimited: boolean;  // true for owner only
  simulating?: string;    // echoed back when owner/trusted previews a capped role
}

export async function getAiUsage(
  jwt: string,
  simulateRole?: "free" | "premium" | "trusted"
): Promise<AiUsage> {
  const params = simulateRole ? `?simulate_role=${simulateRole}` : "";
  const res = await fetchWithAuth(`${BASE}/api/ai_usage${params}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load AI usage");
  return res.json();
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

export interface LeaderboardRankEntry {
  rank:        number;
  player_name: string;
  avg_value:   number;
  sessions:    number;
  is_you:      boolean;
}

export interface LeaderboardRankings {
  game_id:     number;
  stat_type:   string;
  top10:       LeaderboardRankEntry[];
  your_rank:   { rank: number; avg_value: number; sessions: number } | null;
  sample_size: number;
}

export interface StandingCard {
  game_id:      number;
  game_title:   string;
  stat_type:    string;
  avg_value:    number;
  rank:         number;
  percentile:   number;
  sample_size:  number;
  small_sample: boolean;
}

export async function getLeaderboardSampleSize(
  jwt: string,
  gameId: number
): Promise<{ game_id: number; sample_size: number; phase: string }> {
  const res = await fetchWithAuth(`${BASE}/api/leaderboard/sample_size/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load sample size");
  return res.json();
}

export async function getLeaderboardTopStats(
  jwt: string,
  gameId: number
): Promise<{ game_id: number; stat_types: string[] }> {
  const res = await fetchWithAuth(`${BASE}/api/leaderboard/top_stats/${gameId}`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load top stats");
  return res.json();
}

export async function getLeaderboardRankings(
  jwt: string,
  gameId: number,
  statType: string
): Promise<LeaderboardRankings> {
  const res = await fetchWithAuth(
    `${BASE}/api/leaderboard/rankings/${gameId}?stat_type=${encodeURIComponent(statType)}`,
    { headers: authHeaders(jwt) }
  );
  if (!res.ok) throw new Error("Failed to load rankings");
  return res.json();
}

export async function getLeaderboardStandings(
  jwt: string
): Promise<{ standings: StandingCard[] }> {
  const res = await fetchWithAuth(`${BASE}/api/leaderboard/standings`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load standings");
  return res.json();
}

export async function toggleLeaderboardOptIn(
  jwt: string,
  gameId: number
): Promise<{ game_id: number; opted_in: boolean }> {
  const res = await fetchWithAuth(`${BASE}/api/leaderboard/opt_in/${gameId}`, {
    method: "POST",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to toggle opt-in");
  return res.json();
}

export async function getOptInStatus(
  jwt: string
): Promise<{ opted_in: number[] }> {
  const res = await fetchWithAuth(`${BASE}/api/leaderboard/opt_in_status`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load opt-in status");
  return res.json();
}

export async function submitGameRequest(
  jwt: string,
  body: {
    game_name: string;
    game_installment?: string;
    game_genre?: string;
    game_subgenre?: string;
  }
): Promise<{ request_id: number; status: string; message: string }> {
  const res = await fetchWithAuth(`${BASE}/api/game_requests`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Failed to submit game request");
  }
  return res.json();
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface DashboardTopGame {
  game_id:          number;
  game_name:        string;
  game_installment: string | null;
  sessions:         number;
  last_played:      string | null;
  top_stat:         string | null;
  top_stat_avg:     number | null;
}

export interface DashboardData {
  total_sessions: number;
  total_games:    number;
  current_streak: number;
  longest_streak: number;
  last_played:    string | null;
  top_games:      DashboardTopGame[];
  heatmap:        HeatmapData;
}

export async function getDashboard(jwt: string): Promise<DashboardData> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const res = await fetchWithAuth(
    `${BASE}/api/dashboard?tz=${encodeURIComponent(tz)}`,
    { headers: authHeaders(jwt) }
  );
  if (!res.ok) throw new Error("Failed to load dashboard");
  return res.json();
}

// ── Data Export ───────────────────────────────────────────────────────────────

export interface ExportRowCount {
  row_count:     number;
  price:         number;
  tier_label:    string;
  purchased:     boolean;
  needs_upgrade: boolean;
  upgrade_price: number | null;
}

export async function getExportRowCount(jwt: string): Promise<ExportRowCount> {
  const res = await fetchWithAuth(`${BASE}/api/export/row_count`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load row count");
  return res.json();
}

export async function downloadExport(
  jwt: string,
  format: "csv" | "json"
): Promise<Blob> {
  const res = await fetchWithAuth(
    `${BASE}/api/export/download?format=${format}`,
    { headers: authHeaders(jwt) }
  );
  if (res.status === 402) throw new Error("402");
  if (!res.ok) throw new Error("Download failed");
  return res.blob();
}

export async function createPowerPackCheckout(jwt: string): Promise<{ url: string }> {
  const res = await fetchWithAuth(`${BASE}/api/export/checkout`, {
    method: "POST",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to create checkout session");
  return res.json();
}

// ── Subscriptions ─────────────────────────────────────────────────────────────

export interface SubscriptionStatus {
  plan:             "free" | "premium";
  billing_interval?: "month" | "year";
  expires_at?:       string | null;
  cancelled?:        boolean;
}

export async function getSubscriptionStatus(jwt: string): Promise<SubscriptionStatus> {
  const res = await fetchWithAuth(`${BASE}/api/subscription/status`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load subscription status");
  return res.json();
}

export async function createSubscriptionCheckout(
  jwt: string,
  interval: "month" | "year"
): Promise<{ url: string }> {
  const res = await fetchWithAuth(`${BASE}/api/subscription/checkout`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ interval }),
  });
  if (res.status === 409) throw new Error("already_subscribed");
  if (!res.ok) throw new Error("Failed to create subscription checkout");
  return res.json();
}

export async function createBillingPortal(jwt: string): Promise<{ url: string }> {
  const res = await fetchWithAuth(`${BASE}/api/subscription/portal`, {
    method: "POST",
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to open billing portal");
  return res.json();
}

// ── Newsletter ────────────────────────────────────────────────────────────────

export async function getNewsletterOptin(jwt: string): Promise<{ optin: boolean }> {
  const res = await fetchWithAuth(`${BASE}/api/newsletter/optin`, {
    headers: authHeaders(jwt),
  });
  if (!res.ok) throw new Error("Failed to load newsletter preference");
  return res.json();
}

export async function setNewsletterOptin(
  jwt: string,
  optin: boolean
): Promise<{ optin: boolean }> {
  const res = await fetchWithAuth(`${BASE}/api/newsletter/optin`, {
    method: "POST",
    headers: authHeaders(jwt),
    body: JSON.stringify({ optin }),
  });
  if (!res.ok) throw new Error("Failed to update newsletter preference");
  return res.json();
}
