"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import Link from "next/link";
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
    lookup[`${cell.dow}-${slotIdx}`] =
      (lookup[`${cell.dow}-${slotIdx}`] ?? 0) + cell.session_count;
  }

  function intensity(count: number) {
    if (count === 0 || data.max_sessions === 0)
      return "bg-[var(--border)] opacity-40";
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
              <th
                key={s.label}
                className="text-[var(--muted)] font-normal pb-1 text-center px-1"
              >
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
                      title={
                        count > 0
                          ? `${count} session${count !== 1 ? "s" : ""}`
                          : "No sessions"
                      }
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-[var(--muted)] mt-2">
        Darker = more sessions · your local timezone
      </p>
    </div>
  );
}

// ── Top Game Card ─────────────────────────────────────────────────────────────

function formatLastPlayed(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  const date  = new Date(y, m - 1, d);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff  = Math.round((today.getTime() - date.getTime()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function GameCard({
  game,
  rank,
  expanded = false,
}: {
  game: DashboardTopGame;
  rank: number;
  expanded?: boolean;
}) {
  const title = game.game_installment
    ? `${game.game_name}: ${game.game_installment}`
    : game.game_name;
  const medal           = rank === 1 ? "🥇" : rank === 2 ? "🥈" : "🥉";
  const isSingle        = game.sessions === 1;
  const statLabel       = isSingle
    ? `${game.top_stat ?? "Stat"} (1 session)`
    : `Avg ${game.top_stat ?? "Stat"}`;
  const lastPlayedLabel = formatLastPlayed(game.last_played);

  return (
    <div
      className={`rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3 ${
        expanded ? "flex flex-col justify-between" : ""
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-xl">{medal}</span>
        <p className={`font-semibold leading-tight ${expanded ? "text-base" : "text-sm"}`}>
          {title}
        </p>
      </div>

      <div className={`grid gap-2 text-center ${expanded ? "grid-cols-3" : "grid-cols-2"}`}>
        <div className="rounded border border-[var(--border)] py-2">
          <p className="text-lg font-bold text-[var(--gold)]">{game.sessions}</p>
          <p className="text-[10px] text-[var(--muted)]">
            {game.sessions === 1 ? "Session" : "Sessions"}
          </p>
        </div>
        <div className="rounded border border-[var(--border)] py-2">
          <p className="text-lg font-bold">
            {game.top_stat_avg != null ? game.top_stat_avg : "—"}
          </p>
          <p className="text-[10px] text-[var(--muted)]">{statLabel}</p>
        </div>
        {expanded && (
          <Link
            href="/stats"
            className="rounded border border-dashed border-[var(--border)] py-2 flex flex-col items-center justify-center gap-0.5 hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors"
          >
            <span className="text-lg">📊</span>
            <span className="text-[10px] text-[var(--muted)]">Log Stats</span>
            {lastPlayedLabel && (
              <span className="text-[9px] text-[var(--muted)] opacity-70 mt-0.5">
                Last played: {lastPlayedLabel}
              </span>
            )}
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Ghost Card (empty slot) ───────────────────────────────────────────────────

function GhostCard({ slot = 1 }: { slot?: 1 | 2 | 3 }) {
  const text =
    slot === 2 ? "Play a second game to fill this spot"
    : slot === 3 ? "Play a third game to fill this spot"
    : "Play a new game to fill this spot";

  return (
    <Link href="/stats">
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface)]/40 p-4 flex flex-col items-center justify-center gap-2 h-full min-h-[120px] hover:border-[var(--gold)] hover:bg-[var(--surface)] transition-colors cursor-pointer">
        <span className="text-2xl">🎮</span>
        <p className="text-xs text-[var(--muted)] text-center leading-snug">{text}</p>
      </div>
    </Link>
  );
}

// ── Stat Pill ─────────────────────────────────────────────────────────────────

function StatPill({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 flex flex-col items-center justify-center text-center gap-1">
      <div className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</div>
      <div
        className={`text-xl font-bold ${
          highlight ? "text-[var(--gold)]" : "text-[var(--text)]"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

// ── Top Games section (handles all 4 cases) ───────────────────────────────────

function TopGamesSection({ games }: { games: DashboardTopGame[] }) {
  const count = games.length;

  if (count === 0) return null;

  if (count === 1) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--text)]">Top Games</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-1">
            <GameCard game={games[0]} rank={1} expanded />
          </div>
          <div className="hidden sm:block">
            <GhostCard slot={2} />
          </div>
          <div className="hidden sm:block">
            <GhostCard slot={3} />
          </div>
        </div>
        {/* Mobile ghost row */}
        <div className="grid grid-cols-2 gap-3 sm:hidden">
          <GhostCard slot={2} />
          <GhostCard slot={3} />
        </div>
      </section>
    );
  }

  if (count === 2) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--text)]">Top Games</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <GameCard game={games[0]} rank={1} />
          <GameCard game={games[1]} rank={2} />
          <div className="col-span-2 sm:col-span-1">
            <GhostCard slot={3} />
          </div>
        </div>
      </section>
    );
  }

  // count === 3
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-[var(--text)]">Top Games</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {games.map((g, i) => (
          <GameCard key={g.game_id} game={g} rank={i + 1} />
        ))}
      </div>
    </section>
  );
}

// ── Case 0: No data ───────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface)] p-12 flex flex-col items-center justify-center gap-4 text-center">
      <span className="text-5xl">🎮</span>
      <div className="space-y-1">
        <p className="font-semibold text-[var(--text)]">No sessions logged yet</p>
        <p className="text-sm text-[var(--muted)]">
          Submit your first stat to populate the dashboard.
        </p>
      </div>
      <Link
        href="/stats"
        className="mt-2 px-5 py-2 rounded bg-[var(--gold)] text-black text-sm font-semibold hover:opacity-90 transition-opacity"
      >
        Log your first session →
      </Link>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPageClient() {
  const { data: session } = useSession();
  const jwt = session?.flaskJwt ?? "";
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");

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

  const hasData = data && data.total_sessions > 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <h1 className="text-2xl font-bold text-[var(--gold)] text-center">📺 {t("pageTitle")}</h1>

      {loading && (
        <p className="text-sm text-[var(--muted)] text-center animate-pulse">{tCommon("loading")}</p>
      )}
      {error && (
        <p className="text-sm text-red-400 text-center">{error}</p>
      )}

      {data && !hasData && <EmptyState />}

      {hasData && (
        <>
          {/* ── Aggregate stats ── */}
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-[var(--text)]">Overall</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatPill label="Total Sessions" value={data.total_sessions} />
              <StatPill label="Games Played"   value={data.total_games} />
              <StatPill
                label="Current Streak"
                value={`${data.current_streak}d`}
                highlight={data.current_streak > 0}
              />
              <StatPill label="Longest Streak" value={`${data.longest_streak}d`} />
            </div>
            {data.last_played && (
              <p className="text-xs text-[var(--muted)] text-right">
                Last played:{" "}
                {(() => {
                  const [y, m, d] = data.last_played!.split("-").map(Number);
                  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  });
                })()}
              </p>
            )}
          </section>

          {/* ── Top games (cases 1–3) ── */}
          <TopGamesSection games={data.top_games} />

          {/* ── Heatmap ── */}
          {data.heatmap.cells.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-[var(--text)]">📅 When You Play</h2>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <Heatmap data={data.heatmap} />
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
