"use client";

import { useEffect, useState, useCallback } from "react";
import { getLastSession, type LastSession } from "@/lib/api";
import { STAT_DISPLAY_LABELS } from "@/lib/constants";

interface Props {
  jwt: string;
  /** Increment to trigger a refresh after a successful stat submission */
  refreshKey?: number;
}

function formatPlayedAt(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function LastSessionPanel({ jwt, refreshKey = 0 }: Props) {
  const [session, setSession] = useState<LastSession | null | undefined>(undefined);

  const load = useCallback(async () => {
    if (!jwt) return;
    try {
      const data = await getLastSession(jwt);
      setSession(data);
    } catch {
      setSession(null);
    }
  }, [jwt]);

  // Refetch on mount and whenever refreshKey changes (after a new submission)
  useEffect(() => {
    load();
  }, [load, refreshKey]);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 h-full flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--gold)] uppercase tracking-wide">
        🕹️ Last Session
      </h2>

      {session === undefined && (
        <p className="text-xs text-[var(--muted)] animate-pulse">Loading…</p>
      )}

      {session === null && (
        <p className="text-xs text-[var(--muted)]">No sessions recorded yet.</p>
      )}

      {session && (
        <>
          {/* Game + meta */}
          <div className="space-y-0.5">
            <p className="text-sm font-semibold text-[var(--text)] leading-tight">
              {session.game_title}
            </p>
            <p className="text-xs text-[var(--muted)]">{session.player_name}</p>
            <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1">
              {session.played_at && (
                <span className="text-xs text-[var(--muted)]">
                  {formatPlayedAt(session.played_at)}
                </span>
              )}
              {session.win_loss && (
                <span
                  className={`text-xs font-semibold ${
                    session.win_loss === "Win" ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {session.win_loss}
                </span>
              )}
              {session.game_mode && session.game_mode !== "Main" && (
                <span className="text-xs text-[var(--muted)]">{session.game_mode}</span>
              )}
            </div>
          </div>

          <hr className="border-[var(--border)]" />

          {/* Stats */}
          <ul className="flex flex-col gap-1.5 overflow-y-auto flex-1">
            {session.stats.map((s, i) => {
              const label = STAT_DISPLAY_LABELS[s.stat_type] ?? s.stat_type;
              return (
                <li key={i} className="flex justify-between items-center text-xs">
                  <span className="text-[var(--muted)]">{label}</span>
                  <span className="font-semibold text-[var(--text)]">
                    {s.stat_value.toLocaleString()}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
