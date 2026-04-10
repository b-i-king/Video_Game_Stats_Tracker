"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getDashboard, type DashboardData, type DashboardTopGame } from "@/lib/api";

// ── Heatmap ───────────────────────────────────────────────────────────────────

const DAYS       = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TIME_SLOTS = [
  { label: "Morning",    hours: [6, 7, 8, 9, 10, 11] },
  { label: "Afternoon",  hours: [12, 13, 14, 15, 16, 17] },
  { label: "Evening",    hours: [18, 19, 20, 21, 22, 23] },
  { label: "Late Night", hours: [0, 1, 2, 3, 4, 5] },
];

function Heatmap({ data }: { data: DashboardData["heatmap"] }) {
  const lookup: Record<string, number> = {};
  for (const cell of data.cells) {
    const slotIdx = TIME_SLOTS.findIndex((s) => s.hours.includes(cell.hour));
    if (slotIdx === -1) continue;
    lookup[`${cell.dow}-${slotIdx}`] = (lookup[`${cell.dow}-${slotIdx}`] ?? 0) + cell.session_count;
  }

  function intensity(count: number) {
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
            <th className="w-10 pr-2" />
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
      <p className="text-xs text-[var(--muted)] mt-2">Darker = more sessions · your local timezone</p>
    </div>
  );
}

// ── Top Game Card ─────────────────────────────────────────────────────────────

function GameCard({ game, rank }: { game: DashboardTopGame; rank: number }) {
  const title = game.game_installment
    ? `${game.game_name}: ${game.game_installment}`
    : game.game_name;
  const medal = rank === 1 ? "🥇" : rank === 2 ? "🥈" : "🥉";

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
      <div className="flex items-start gap-2">
        <span className="text-xl">{medal}</span>
        <p className="font-semibold text-sm leading-tight">{title}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 text-center">
        <div className="rounded border border-[var(--border)] py-2">
          <p className="text-lg font-bold text-[var(--gold)]">{game.sessions}</p>
          <p className="text-[10px] text-[var(--muted)]">Sessions</p>
        </div>
        <div className="rounded border border-[var(--border)] py-2">
          <p className="text-lg font-bold">
            {game.top_stat_avg != null ? game.top_stat_avg : "—"}
          </p>
          <p className="text-[10px] text-[var(--muted)]">{game.top_stat ?? "Avg"}</p>
        </div>
      </div>
    </div>
  );
}

// ── Stat Pill ─────────────────────────────────────────────────────────────────

function StatPill({ label, value, highlight = false }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 flex flex-col items-center justify-center text-center gap-1">
      <div className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold ${highlight ? "text-[var(--gold)]" : "text-[var(--text)]"}`}>
        {value}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPageClient() {
  const { data: session } = useSession();
  const jwt = session?.flaskJwt ?? "";

  const [data, setData]       = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!jwt) return;
    getDashboard(jwt)
      .then(setData)
      .catch(() => setError("Failed to load dashboard."))
      .finally(() => setLoading(false));
  }, [jwt]);

  if (!session) return null;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <h1 className="text-2xl font-bold text-[var(--gold)] text-center">📺 Dashboard</h1>

      {loading && (
        <p className="text-sm text-[var(--muted)] text-center animate-pulse">Loading…</p>
      )}
      {error && (
        <p className="text-sm text-red-400 text-center">{error}</p>
      )}

      {data && (
        <>
          {/* ── Aggregate stats ── */}
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-[var(--text)]">Overall</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatPill label="Total Sessions" value={data.total_sessions} />
              <StatPill label="Games Played"   value={data.total_games} />
              <StatPill label="Current Streak" value={`${data.current_streak}d`} highlight={data.current_streak > 0} />
              <StatPill label="Longest Streak" value={`${data.longest_streak}d`} />
            </div>
            {data.last_played && (
              <p className="text-xs text-[var(--muted)] text-right">
                Last played:{" "}
                {(() => {
                  const [y, m, d] = data.last_played!.split("-").map(Number);
                  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
                    month: "short", day: "numeric", year: "numeric",
                  });
                })()}
              </p>
            )}
          </section>

          {/* ── Top 3 games ── */}
          {data.top_games.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-[var(--text)]">Top Games</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {data.top_games.map((g, i) => (
                  <GameCard key={g.game_id} game={g} rank={i + 1} />
                ))}
              </div>
            </section>
          )}

          {/* ── Heatmap ── */}
          {data.heatmap.cells.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-[var(--text)]">📅 When You Play</h2>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <Heatmap data={data.heatmap} />
              </div>
            </section>
          )}

          {data.total_sessions === 0 && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--muted)]">
              No sessions logged yet. Submit your first stat to populate the dashboard.
            </div>
          )}
        </>
      )}
    </div>
  );
}
