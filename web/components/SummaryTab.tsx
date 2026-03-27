"use client";

import { useEffect, useState } from "react";
import {
  getPlayers,
  getAllGames,
  getSummary,
  getInteractiveChart,
  type Player,
  type GameDetails,
  type KpiStat,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatValue(value: number): string {
  return value.toLocaleString();
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({
  stat,
  label,
}: {
  stat: KpiStat;
  label: "Today's Avg" | "All-Time Best";
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-center space-y-1">
      <div className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</div>
      <div className="text-xs font-medium text-[var(--text)] truncate">{stat.stat_type}</div>
      <div className="text-2xl font-bold text-[var(--gold)]">{formatValue(stat.value)}</div>
      <div className="text-xs text-[var(--muted)]">
        {stat.lower_is_better ? "↓ lower is better" : "↑ higher is better"}
      </div>
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
  // undefined = not yet fetched/loading, null = fetch failed, string = html
  const [chartHtml, setChartHtml]     = useState<string | null | undefined>(undefined);
  const [error, setError]             = useState<string | null>(null);

  const loading      = todayAvg === null && !!gameId;
  const chartLoading = chartHtml === undefined && !!gameId;

  // Load players and games on mount
  useEffect(() => {
    if (!jwt) return;
    Promise.all([getPlayers(jwt), getAllGames(jwt)]).then(([p, g]) => {
      setPlayers(p);
      setGames(g);
      if (p.length > 0) setPlayerName(p[0].player_name);
    }).catch(() => setError("Failed to load players or games."));
  }, [jwt]);

  // Fetch KPIs + interactive chart when player + game are both selected
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

    return () => {
      setTodayAvg(null);
      setAllTimeBest(null);
      setChartHtml(undefined);
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
                {g.game_name}{g.game_series ? ` — ${g.game_series}` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* States */}
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

      {/* Interactive chart */}
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
    </div>
  );
}
