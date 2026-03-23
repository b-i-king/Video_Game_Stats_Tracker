"use client";

import { useEffect, useState, useCallback } from "react";
import { getQueueStatus, retryFailed } from "@/lib/api";

interface Props {
  jwt: string;
  queueMode: boolean;
  setQueueMode: (val: boolean) => void;
}

export default function QueuePanel({ jwt, queueMode, setQueueMode }: Props) {
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

  async function handleRetry() {
    setRetrying(true);
    try {
      const result = await retryFailed(jwt);
      alert(`Reset ${result.reset_count} failed post(s).`);
      await loadCounts();
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
