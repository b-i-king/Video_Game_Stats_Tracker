"use client";

import { useEffect, useState } from "react";
import {
  getLastSession,
  getMLCoefficients,
  getMLProgress,
  triggerMLTraining,
  type LastSession,
  type MLCoefficientsData,
  type MLProgress,
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
function computeWinProbability(session: LastSession, c: MLCoefficientsData): number {
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

/** Circular SVG progress ring. Uses gold theme colour for the arc. */
function ProgressRing({ value, max }: { value: number; max: number }) {
  const size   = 64;
  const stroke = 6;
  const r      = (size - stroke) / 2;
  const circ   = 2 * Math.PI * r;
  const pct    = Math.min(value / max, 1);
  const offset = circ * (1 - pct);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* track */}
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="var(--border)" strokeWidth={stroke} />
        {/* arc */}
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="var(--gold)" strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.4s ease" }}
        />
      </svg>
      {/* centred label — counter-rotate so text is upright */}
      <div className="absolute inset-0 flex items-center justify-center rotate-0">
        <span className="text-xs font-bold text-[var(--gold)] tabular-nums leading-none">
          {Math.round(pct * 100)}%
        </span>
      </div>
    </div>
  );
}

export default function LastSessionPanel({ jwt, refreshKey = 0 }: Props) {
  const [session,      setSession]      = useState<LastSession | null | undefined>(undefined);
  // undefined = loading, null = no model, object = model ready
  const [mlCoeff,      setMlCoeff]      = useState<MLCoefficientsData | null | undefined>(undefined);
  const [mlProgress,   setMlProgress]   = useState<MLProgress | null>(null);
  const [trainQueued,  setTrainQueued]  = useState(false);
  const [trainLoading, setTrainLoading] = useState(false);

  // Fetch last session
  useEffect(() => {
    if (!jwt) return;
    let cancelled = false;
    getLastSession(jwt)
      .then((data) => { if (!cancelled) setSession(data); })
      .catch(()    => { if (!cancelled) setSession(null); });
    return () => { cancelled = true; };
  }, [jwt, refreshKey]);

  // Fetch ML coefficients once session loads.
  // Cleanup resets to undefined so stale data never shows during a new fetch.
  useEffect(() => {
    if (!session || !jwt) return;
    let cancelled = false;
    getMLCoefficients(jwt, session.game_id, session.player_id)
      .then((res) => { if (!cancelled) setMlCoeff(res?.coefficients ?? null); })
      .catch(()   => { if (!cancelled) setMlCoeff(null); });
    return () => { cancelled = true; setMlCoeff(undefined); };
  }, [jwt, session?.game_id, session?.player_id]);

  // Fetch training progress when there is no model yet.
  useEffect(() => {
    if (!session || !jwt || mlCoeff !== null) return;
    let cancelled = false;
    getMLProgress(jwt, session.game_id, session.player_id)
      .then((res) => { if (!cancelled) setMlProgress(res); })
      .catch(()   => {});
    return () => { cancelled = true; };
  }, [jwt, session?.game_id, session?.player_id, mlCoeff]);

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
                <span className={`text-xs font-semibold ${
                  session.win_loss === "Win" ? "text-emerald-400" : "text-red-400"
                }`}>
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

          {/* Win Probability / progress widget */}
          <hr className="border-[var(--border)]" />

          {/* Loading */}
          {mlCoeff === undefined && (
            <p className="text-xs text-[var(--muted)] animate-pulse">Checking model…</p>
          )}

          {/* Model ready — show win probability */}
          {mlCoeff !== undefined && winProb !== null && (
            <div className={`rounded border-2 bg-[var(--bg)] px-3 py-2 flex items-center justify-between ${probabilityColor(winProb)}`}>
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                Win Probability
              </span>
              <span className="text-xl font-bold tabular-nums">
                {Math.round(winProb * 100)}%
              </span>
            </div>
          )}

          {/* No model — show circular progress toward unlock threshold */}
          {mlCoeff !== undefined && mlCoeff === null && mlProgress && (
            <div className="flex items-center gap-3">
              <ProgressRing value={mlProgress.win_sessions} max={mlProgress.min_sessions} />
              <div className="flex flex-col gap-1 min-w-0">
                <p className="text-xs font-semibold text-[var(--text)] leading-tight">
                  Win Model Locked
                </p>
                <p className="text-xs text-[var(--muted)] leading-snug">
                  {mlProgress.win_sessions} / {mlProgress.min_sessions} win-tracked sessions
                </p>
                {mlProgress.ready && !trainQueued && (
                  <button
                    onClick={handleTrainModel}
                    disabled={trainLoading}
                    className="mt-1 text-xs px-2 py-1 rounded border border-[var(--gold)] text-[var(--gold)] hover:bg-[var(--gold)] hover:text-black transition-colors disabled:opacity-40 self-start"
                  >
                    {trainLoading ? "Queuing…" : "Train Model"}
                  </button>
                )}
                {trainQueued && (
                  <p className="text-xs text-[var(--gold)]">Training queued…</p>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
