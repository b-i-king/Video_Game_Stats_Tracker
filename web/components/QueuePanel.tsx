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

  // Initial load
  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  // Auto-refresh every 30 seconds
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

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4">
      <h3 className="font-semibold text-sm">📬 Post Queue</h3>

      {/* Queue mode toggle */}
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <div
          onClick={() => setQueueMode(!queueMode)}
          title="Auto ON weekdays 9am–5pm PST (excl. US federal holidays). Toggle to override."
          className={`relative w-10 h-5 rounded-full transition-colors ${
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

      <p className="text-xs text-[var(--muted)]">
        {queueMode
          ? "📥 Posts will be queued, not sent immediately."
          : "🚀 Posts sent immediately via IFTTT."}
      </p>

      {isManualOverride && (
        <p className="text-xs text-yellow-400">Manual override active</p>
      )}

      {/* Queue counts */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded border border-[var(--border)] p-2 text-center">
          <div className="text-lg font-bold text-[var(--gold)]">
            {counts.pending + counts.processing}
          </div>
          <div className="text-xs text-[var(--muted)]">Pending</div>
        </div>
        <div className="rounded border border-[var(--border)] p-2 text-center">
          <div className="text-lg font-bold">{counts.sent}</div>
          <div className="text-xs text-[var(--muted)]">Sent</div>
        </div>
        <div className="rounded border border-[var(--border)] p-2 text-center">
          <div className={`text-lg font-bold ${counts.failed > 0 ? "text-red-400" : ""}`}>
            {counts.failed}
          </div>
          <div className="text-xs text-[var(--muted)]">Failed</div>
        </div>
      </div>

      {counts.failed > 0 && (
        <button
          onClick={handleRetry}
          disabled={retrying}
          className="w-full py-1.5 rounded text-sm bg-red-900 hover:bg-red-800 text-white disabled:opacity-50 transition-colors"
        >
          {retrying ? "Retrying…" : "Retry Failed"}
        </button>
      )}

      <button
        onClick={loadCounts}
        className="w-full py-1 rounded text-xs border border-[var(--border)] hover:border-[var(--gold)] text-[var(--muted)] hover:text-[var(--gold)] transition-colors"
      >
        Refresh
      </button>
    </div>
  );
}
