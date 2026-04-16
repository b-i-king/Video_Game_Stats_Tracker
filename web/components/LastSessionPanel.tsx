"use client";

import { useEffect, useState } from "react";
import {
  getLastSession,
  getMLCoefficients,
  triggerMLTraining,
  type LastSession,
  type MLCoefficientsData,
} from "@/lib/api";
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

/**
 * Client-side LR sigmoid inference.
 * Normalises session stats using stored μ/σ, then applies the LR equation.
 */
function computeWinProbability(
  session: LastSession,
  c: MLCoefficientsData,
): number {
  const statsMap: Record<string, number> = {};
  for (const s of session.stats) statsMap[s.stat_type] = s.stat_value;

  let z = c.intercept[0];
  for (let i = 0; i < c.feature_names.length; i++) {
    const x     = statsMap[c.feature_names[i]] ?? 0;
    const std   = c.feature_stds[i] === 0 ? 1 : c.feature_stds[i];
    const xNorm = (x - c.feature_means[i]) / std;
    z += c.coef[0][i] * xNorm;
  }
  return 1 / (1 + Math.exp(-z));
}

function probabilityColor(p: number): string {
  if (p >= 0.65) return "border-emerald-500 text-emerald-400";
  if (p >= 0.40) return "border-yellow-500 text-yellow-400";
  return "border-red-500 text-red-400";
}

export default function LastSessionPanel({ jwt, refreshKey = 0 }: Props) {
  const [session,      setSession]      = useState<LastSession | null | undefined>(undefined);
  // undefined = not yet fetched / loading, null = no model trained, object = model ready
  const [mlCoeff,      setMlCoeff]      = useState<MLCoefficientsData | null | undefined>(undefined);
  const [trainQueued,  setTrainQueued]  = useState(false);
  const [trainLoading, setTrainLoading] = useState(false);

  // Fetch last session
  useEffect(() => {
    if (!jwt) return;
    let cancelled = false;
    getLastSession(jwt)
      .then((data) => { if (!cancelled) setSession(data); })
      .catch(() => { if (!cancelled) setSession(null); });
    return () => { cancelled = true; };
  }, [jwt, refreshKey]);

  // Fetch ML coefficients once session (with game_id/player_id) is loaded.
  // Reset to undefined (loading) via the return cleanup so stale data never
  // shows while a new fetch is in flight.
  useEffect(() => {
    if (!session || !jwt) return;
    let cancelled = false;
    getMLCoefficients(jwt, session.game_id, session.player_id)
      .then((res) => { if (!cancelled) setMlCoeff(res?.coefficients ?? null); })
      .catch(()    => { if (!cancelled) setMlCoeff(null); });
    return () => { cancelled = true; setMlCoeff(undefined); };
  }, [jwt, session?.game_id, session?.player_id]);

  function handleTrainModel() {
    if (!session || trainLoading) return;
    setTrainLoading(true);
    triggerMLTraining(jwt, session.game_id, session.player_id)
      .then(() => setTrainQueued(true))
      .catch(() => {})
      .finally(() => setTrainLoading(false));
  }

  const winProb = (session && mlCoeff)
    ? computeWinProbability(session, mlCoeff)
    : null;

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

          {/* Win Probability widget */}
          <hr className="border-[var(--border)]" />

          {mlCoeff === undefined && (
            <p className="text-xs text-[var(--muted)] animate-pulse">Checking model…</p>
          )}

          {mlCoeff !== undefined && winProb !== null && (
            <div
              className={`rounded border-2 bg-[var(--bg)] px-3 py-2 flex items-center justify-between ${probabilityColor(winProb)}`}
            >
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                Win Probability
              </span>
              <span className="text-xl font-bold tabular-nums">
                {Math.round(winProb * 100)}%
              </span>
            </div>
          )}

          {mlCoeff !== undefined && winProb === null && mlCoeff === null && (
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-[var(--muted)]">
                {trainQueued ? "Training queued…" : "No win model yet"}
              </span>
              {!trainQueued && (
                <button
                  onClick={handleTrainModel}
                  disabled={trainLoading}
                  className="text-xs px-2 py-1 rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--gold)] hover:border-[var(--gold)] transition-colors disabled:opacity-40"
                >
                  {trainLoading ? "Queuing…" : "Train Model"}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
