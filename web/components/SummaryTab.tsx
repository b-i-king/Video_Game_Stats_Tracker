"use client";

import { useEffect, useState } from "react";
import {
  getPlayers,
  getAllGames,
  getSummary,
  getInteractiveChart,
  getHeatmap,
  getStreaks,
  type Player,
  type GameDetails,
  type KpiStat,
  type HeatmapData,
  type StreakData,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatValue(value: number): string {
  return value.toLocaleString();
}

function gameLabel(g: { game_name: string; game_installment?: string | null }): string {
  return g.game_installment ? `${g.game_name}: ${g.game_installment}` : g.game_name;
}

// z-score → badge label + color
function zBadge(z: number | null | undefined, lowerIsBetter: boolean) {
  if (z == null) return null;
  const good = lowerIsBetter ? z < -1.5 : z > 1.5;
  const bad  = lowerIsBetter ? z > 1.5  : z < -1.5;
  if (good) return { label: "Top session", color: "text-emerald-400" };
  if (bad)  return { label: "Below avg",   color: "text-red-400" };
  return null;
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({
  stat,
  label,
}: {
  stat: KpiStat;
  label: "Today's Avg" | "All-Time Best";
}) {
  const badge = label === "Today's Avg" ? zBadge(stat.today_z_score, stat.lower_is_better) : null;
  const hasCI = stat.ci_low != null && stat.ci_high != null;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-center space-y-1">
      <div className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</div>
      <div className="text-xs font-medium text-[var(--text)] truncate">{stat.stat_type}</div>
      <div className="text-2xl font-bold text-[var(--gold)]">{formatValue(stat.value)}</div>
      {hasCI && (
        <div className="text-xs text-[var(--muted)]">
          95% CI: {stat.ci_low} – {stat.ci_high}
        </div>
      )}
      {stat.n_sessions != null && (
        <div className="text-xs text-[var(--muted)]">{stat.n_sessions} sessions</div>
      )}
      <div className="text-xs text-[var(--muted)]">
        {stat.lower_is_better ? "↓ lower is better" : "↑ higher is better"}
      </div>
      {badge && (
        <div className={`text-xs font-semibold ${badge.color}`}>{badge.label}</div>
      )}
    </div>
  );
}

// ── Streak Bar ────────────────────────────────────────────────────────────────

function StreakBar({ data }: { data: StreakData }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: "Current Streak", value: `${data.current_streak}d`, highlight: data.current_streak > 0 },
        { label: "Longest Streak", value: `${data.longest_streak}d`, highlight: false },
        { label: "Session Days",   value: data.total_session_days,   highlight: false },
        { label: "Last Played",    value: data.last_session ?? "—",  highlight: false },
      ].map(({ label, value, highlight }) => (
        <div
          key={label}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-center space-y-1"
        >
          <div className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</div>
          <div className={`text-xl font-bold ${highlight ? "text-[var(--gold)]" : "text-[var(--text)]"}`}>
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Heatmap ───────────────────────────────────────────────────────────────────

const DAYS        = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TIME_SLOTS  = [
  { label: "Late Night", hours: [0, 1, 2, 3, 4, 5] },
  { label: "Morning",    hours: [6, 7, 8, 9, 10, 11] },
  { label: "Afternoon",  hours: [12, 13, 14, 15, 16, 17] },
  { label: "Evening",    hours: [18, 19, 20, 21, 22, 23] },
];

function Heatmap({ data }: { data: HeatmapData }) {
  // Build lookup: dow+slot → session count
  const lookup: Record<string, number> = {};
  for (const cell of data.cells) {
    const slotIdx = TIME_SLOTS.findIndex((s) => s.hours.includes(cell.hour));
    if (slotIdx === -1) continue;
    const key = `${cell.dow}-${slotIdx}`;
    lookup[key] = (lookup[key] ?? 0) + cell.session_count;
  }

  function intensity(count: number): string {
    if (count === 0 || data.max_sessions === 0) return "bg-[var(--border)] opacity-40";
    const pct = count / data.max_sessions;
    if (pct < 0.25) return "bg-[var(--gold)] opacity-20";
    if (pct < 0.5)  return "bg-[var(--gold)] opacity-40";
    if (pct < 0.75) return "bg-[var(--gold)] opacity-70";
    return "bg-[var(--gold)]";
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-[var(--muted)] font-normal pr-2 text-right w-10" />
            {TIME_SLOTS.map((s) => (
              <th key={s.label} className="text-[var(--muted)] font-normal pb-1 text-center px-1">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DAYS.map((day, dow) => (
            <tr key={day}>
              <td className="text-[var(--muted)] pr-2 text-right py-0.5">{day}</td>
              {TIME_SLOTS.map((_, slotIdx) => {
                const count = lookup[`${dow}-${slotIdx}`] ?? 0;
                return (
                  <td key={slotIdx} className="px-1 py-0.5">
                    <div
                      className={`rounded h-6 ${intensity(count)}`}
                      title={count > 0 ? `${count} session${count !== 1 ? "s" : ""}` : "No sessions"}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-[var(--muted)] mt-2">
        Darker = more sessions. Times shown in Pacific Time.
      </p>
    </div>
  );
}

// ── ESPN Ticker ───────────────────────────────────────────────────────────────

/** Build narrative fact strings from already-fetched KPI data — zero extra queries. */
function buildTickerFacts(
  gameName: string,
  todayStats: KpiStat[],
  bestStats: KpiStat[]
): string[] {
  const facts: string[] = [];

  for (const s of todayStats) {
    const v = formatValue(s.value);
    if (s.ci_low != null && s.ci_high != null && s.n_sessions != null) {
      facts.push(
        `${s.stat_type}: avg ${v} across ${s.n_sessions} sessions` +
          ` (95% CI ${formatValue(s.ci_low)}–${formatValue(s.ci_high)})`
      );
    } else {
      facts.push(`Today's ${s.stat_type}: ${v}${s.lower_is_better ? " ↓" : " ↑"}`);
    }
    if (s.today_z_score != null) {
      const z = s.today_z_score;
      const label =
        z >= 2    ? "elite — top 2.5%"
        : z >= 1  ? "above average"
        : z <= -2 ? "well below average"
        : z <= -1 ? "below average"
        : "right on average";
      facts.push(`${s.stat_type} today: ${z > 0 ? "+" : ""}${z}σ (${label})`);
    }
  }

  for (const s of bestStats) {
    facts.push(`All-time best ${s.stat_type} in ${gameName}: ${formatValue(s.value)}`);
  }

  return facts;
}

function StatTicker({
  gameName,
  todayStats,
  bestStats,
}: {
  gameName: string;
  todayStats: KpiStat[];
  bestStats: KpiStat[];
}) {
  const items = buildTickerFacts(gameName, todayStats, bestStats);
  if (!items.length) return null;

  const content = [gameName.toUpperCase(), ...items].join("  •  ");
  const doubled = `${content}  •  ${content}`;

  return (
    <div className="overflow-hidden rounded border border-[var(--border)] bg-black/60 text-[var(--gold)] text-xs font-semibold py-1.5 select-none">
      <style>{`
        @keyframes ticker-scroll {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .ticker-track {
          display: inline-block;
          white-space: nowrap;
          animation: ticker-scroll 35s linear infinite;
        }
        .ticker-track:hover { animation-play-state: paused; }
      `}</style>
      <span className="ticker-track px-4">{doubled}</span>
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--muted)]">
      {message}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SummaryTab({ jwt }: { jwt: string }) {
  const [players, setPlayers]         = useState<Player[]>([]);
  const [games, setGames]             = useState<GameDetails[]>([]);
  const [playerName, setPlayerName]   = useState("");
  const [gameId, setGameId]           = useState<number | null>(null);

  // null = loading/not yet fetched, [] = fetched but empty
  const [todayAvg, setTodayAvg]       = useState<KpiStat[] | null>(null);
  const [allTimeBest, setAllTimeBest] = useState<KpiStat[] | null>(null);
  // undefined = loading, null = failed, string = html
  const [chartHtml, setChartHtml]     = useState<string | null | undefined>(undefined);
  const [heatmap, setHeatmap]         = useState<HeatmapData | null | undefined>(undefined);
  const [streaks, setStreaks]         = useState<StreakData | null | undefined>(undefined);
  const [error, setError]             = useState<string | null>(null);

  const loading      = todayAvg === null && !!gameId;
  const chartLoading = chartHtml === undefined && !!gameId;
  const heatLoading  = heatmap  === undefined && !!gameId;
  const streakLoading = streaks === undefined && !!gameId;

  // Load players and games on mount
  useEffect(() => {
    if (!jwt) return;
    Promise.all([getPlayers(jwt), getAllGames(jwt)]).then(([p, g]) => {
      setPlayers(p);
      setGames(g);
      if (p.length > 0) setPlayerName(p[0].player_name);
    }).catch(() => setError("Failed to load players or games."));
  }, [jwt]);

  // Fetch all data when player + game are both selected
  useEffect(() => {
    if (!jwt || !gameId || !playerName) return;

    getSummary(jwt, gameId, playerName)
      .then((data) => {
        setTodayAvg(data.today_avg);
        setAllTimeBest(data.all_time_best);
      })
      .catch((e) => {
        setError(e.message ?? "Failed to load summary.");
        setTodayAvg([]);
        setAllTimeBest([]);
      });

    getInteractiveChart(jwt, gameId, playerName)
      .then((html) => setChartHtml(html))
      .catch(() => setChartHtml(null));

    getHeatmap(jwt, gameId, playerName)
      .then((data) => setHeatmap(data))
      .catch(() => setHeatmap(null));

    getStreaks(jwt, gameId, playerName)
      .then((data) => setStreaks(data))
      .catch(() => setStreaks(null));

    return () => {
      setTodayAvg(null);
      setAllTimeBest(null);
      setChartHtml(undefined);
      setHeatmap(undefined);
      setStreaks(undefined);
      setError(null);
    };
  }, [jwt, gameId, playerName]);

  return (
    <div className="space-y-6">

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {players.length > 1 && (
          <div className="flex-1 min-w-[160px]">
            <label className="label">Player</label>
            <select
              className="input"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
            >
              {players.map((p) => (
                <option key={p.player_id} value={p.player_name}>
                  {p.player_name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex-1 min-w-[160px]">
          <label className="label">Game</label>
          <select
            className="input"
            value={gameId ?? ""}
            onChange={(e) => setGameId(Number(e.target.value) || null)}
          >
            <option value="">— Select a game —</option>
            {games.map((g) => (
              <option key={g.game_id} value={g.game_id}>
                {gameLabel(g)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ESPN Ticker */}
      {gameId && !loading && (
        <StatTicker
          gameName={gameLabel(games.find((g) => g.game_id === gameId) ?? { game_name: "" })}
          todayStats={todayAvg ?? []}
          bestStats={allTimeBest ?? []}
        />
      )}

      {/* Error */}
      {error && (
        <div className="rounded px-4 py-3 text-sm bg-red-900/30 border border-red-700 text-red-300">
          ❌ {error}
        </div>
      )}

      {!gameId && !loading && (
        <EmptyState message="Select a game above to view your summary." />
      )}

      {loading && (
        <div className="text-sm text-[var(--muted)] text-center py-8 animate-pulse">
          Loading summary…
        </div>
      )}

      {/* Streaks */}
      {gameId && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">🔥 Session Streaks</h2>
          {streakLoading && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-center text-sm text-[var(--muted)] animate-pulse">
              Loading streaks…
            </div>
          )}
          {!streakLoading && streaks && <StreakBar data={streaks} />}
          {!streakLoading && !streaks && (
            <EmptyState message="No session data yet for this game." />
          )}
        </div>
      )}

      {/* Today's Average */}
      {!loading && gameId && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">📅 Today&apos;s Average</h2>
          {todayAvg!.length === 0 ? (
            <EmptyState message="No stats logged today for this game." />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {todayAvg!.map((stat) => (
                <KpiCard key={stat.stat_type} stat={stat} label="Today's Avg" />
              ))}
            </div>
          )}
        </div>
      )}

      {/* All-Time Best */}
      {!loading && gameId && allTimeBest!.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">🏆 All-Time Best</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {allTimeBest!.map((stat) => (
              <KpiCard key={stat.stat_type} stat={stat} label="All-Time Best" />
            ))}
          </div>
        </div>
      )}

      {/* Performance Trend */}
      {gameId && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">📈 Performance Trend</h2>
          {chartLoading && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] h-[420px] flex items-center justify-center text-sm text-[var(--muted)] animate-pulse">
              Loading chart…
            </div>
          )}
          {!chartLoading && chartHtml && (
            <iframe
              srcDoc={chartHtml}
              sandbox="allow-scripts"
              className="w-full rounded-lg border border-[var(--border)]"
              style={{ height: 420 }}
              title="Performance Trend"
            />
          )}
          {!chartLoading && !chartHtml && (
            <EmptyState message="Chart unavailable for this game." />
          )}
        </div>
      )}

      {/* Play-time Heatmap */}
      {gameId && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">🗓 When You Play</h2>
          {heatLoading && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-center text-sm text-[var(--muted)] animate-pulse">
              Loading heatmap…
            </div>
          )}
          {!heatLoading && heatmap && heatmap.cells.length > 0 && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <Heatmap data={heatmap} />
            </div>
          )}
          {!heatLoading && (!heatmap || heatmap.cells.length === 0) && (
            <EmptyState message="Not enough data to show play-time patterns." />
          )}
        </div>
      )}
    </div>
  );
}
