"use client";

import { useEffect, useState, useCallback } from "react";
import { getQueueStatus, retryFailed } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface Props {
  jwt: string;
  queueMode: boolean;
  setQueueMode: (val: boolean) => void;
  isManualOverride: boolean;
}

export default function QueuePanel({ jwt, queueMode, setQueueMode, isManualOverride }: Props) {
  const { showToast } = useToast();
  const [counts, setCounts] = useState({
    pending: 0,
    processing: 0,
    sent: 0,
    failed: 0,
  });
  const [retrying, setRetrying] = useState(false);

  const loadCounts = useCallback(async () => {
    if (!jwt) return;
    const c = await getQueueStatus(jwt);
    setCounts(c);
  }, [jwt]);

  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  useEffect(() => {
    const interval = setInterval(() => { loadCounts(); }, 30_000);
    return () => clearInterval(interval);
  }, [loadCounts]);

  async function handleRetry() {
    setRetrying(true);
    try {
      const result = await retryFailed(jwt);
      showToast(`Reset ${result.reset_count} failed post(s).`);
      await loadCounts();
    } catch {
      showToast("Retry failed — try again.", "error");
    } finally {
      setRetrying(false);
    }
  }

  const total = counts.pending + counts.processing + counts.sent + counts.failed;
  const successRate = counts.sent + counts.failed > 0
    ? Math.round((counts.sent / (counts.sent + counts.failed)) * 100)
    : null;

  return (
    <div className="h-full rounded-lg border border-[var(--border)] bg-[var(--surface)] flex flex-col">

      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-[var(--border)] shrink-0">
        <h3 className="font-semibold text-sm">📬 Post Queue</h3>

        {/* Queue mode toggle */}
        <label className="flex items-center gap-2 cursor-pointer text-sm mt-3">
          <div
            onClick={() => setQueueMode(!queueMode)}
            title="Auto ON weekdays 9am–5pm PST (excl. US federal holidays). Toggle to override."
            className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${
              queueMode ? "bg-[var(--gold)]" : "bg-[var(--border)]"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                queueMode ? "translate-x-5" : ""
              }`}
            />
          </div>
          Queue Mode
        </label>

        <p className="text-xs text-[var(--muted)] mt-1">
          {queueMode
            ? "📥 Posts will be queued, not sent immediately."
            : "🚀 Posts sent immediately via IFTTT."}
        </p>

        {isManualOverride && (
          <p className="text-xs text-yellow-400 mt-1">Manual override active</p>
        )}
      </div>

      {/* Counts — 3 stacked rows */}
      <div className="px-4 pt-4 shrink-0 space-y-2">
        <div className="flex items-center justify-between rounded border border-[var(--border)] px-4 py-3">
          <span className="text-sm text-[var(--muted)]">Pending</span>
          <span className="text-xl font-bold text-[var(--gold)]">{counts.pending + counts.processing}</span>
        </div>
        <div className="flex items-center justify-between rounded border border-[var(--border)] px-4 py-3">
          <span className="text-sm text-[var(--muted)]">Sent</span>
          <span className="text-xl font-bold">{counts.sent}</span>
        </div>
        <div className="flex items-center justify-between rounded border border-[var(--border)] px-4 py-3">
          <span className="text-sm text-[var(--muted)]">Failed</span>
          <span className={`text-xl font-bold ${counts.failed > 0 ? "text-red-400" : ""}`}>{counts.failed}</span>
        </div>

        {counts.failed > 0 && (
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="w-full mt-2 py-1.5 rounded text-sm bg-red-900 hover:bg-red-800 text-white disabled:opacity-50 transition-colors"
          >
            {retrying ? "Retrying…" : "Retry Failed"}
          </button>
        )}
      </div>

      {/* Spacer — grows to fill remaining height */}
      <div className="flex-1" />

      {/* Summary stats — anchored above footer */}
      <div className="px-4 pb-3 space-y-2 shrink-0">
        <div className="rounded border border-[var(--border)] p-3 space-y-2">
          <p className="text-xs text-[var(--muted)] font-semibold uppercase tracking-wide">Session Summary</p>
          <div className="flex justify-between text-sm">
            <span className="text-[var(--muted)]">Total queued</span>
            <span className="font-semibold">{total}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[var(--muted)]">Success rate</span>
            <span className={`font-semibold ${
              successRate === null ? "text-[var(--muted)]" :
              successRate >= 80 ? "text-green-400" :
              successRate >= 50 ? "text-yellow-400" : "text-red-400"
            }`}>
              {successRate === null ? "—" : `${successRate}%`}
            </span>
          </div>
        </div>
      </div>

      {/* Refresh — pinned at bottom */}
      <div className="px-4 pb-4 shrink-0">
        <button
          onClick={loadCounts}
          className="w-full py-1 rounded text-xs border border-[var(--border)] hover:border-[var(--gold)] text-[var(--muted)] hover:text-[var(--gold)] transition-colors"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
