"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  getExportRowCount,
  downloadExport,
  createPowerPackCheckout,
  type ExportRowCount,
} from "@/lib/api";

type Format = "csv" | "json";

export default function DataExportClient() {
  const { data: session } = useSession();
  const jwt     = (session as { flaskJwt?: string })?.flaskJwt ?? "";
  const isOwner = (session as { isOwner?: boolean })?.isOwner ?? false;

  const [info, setInfo]         = useState<ExportRowCount | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [format, setFormat]     = useState<Format>("csv");
  const [downloading, setDownloading] = useState(false);
  const [purchasing, setPurchasing]   = useState(false);
  const [previewUser, setPreviewUser] = useState(false);

  useEffect(() => {
    if (!jwt) return;
    getExportRowCount(jwt)
      .then(setInfo)
      .catch(() => setError("Failed to load export info."))
      .finally(() => setLoading(false));
  }, [jwt]);

  async function handleDownload() {
    if (!jwt) return;
    setDownloading(true);
    try {
      const blob = await downloadExport(jwt, format);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `game_stats_export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      if (e instanceof Error && e.message === "402") {
        setError("Purchase the Power Pack to download your data.");
      } else {
        setError("Download failed. Please try again.");
      }
    } finally {
      setDownloading(false);
    }
  }

  async function handlePurchase() {
    if (!jwt) return;
    setPurchasing(true);
    try {
      const { url } = await createPowerPackCheckout(jwt);
      window.location.href = url;
    } catch {
      setError("Could not start checkout. Please try again.");
      setPurchasing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--gold)] border-t-transparent" />
      </div>
    );
  }

  // Owner sees purchased:true from the API — override when previewing user flow
  const effectivePurchased = info ? (previewUser ? false : info.purchased) : false;

  return (
    <div className="max-w-xl mx-auto space-y-6 py-4 px-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[var(--gold)]">Export Your Data</h1>
        {isOwner && (
          <button
            onClick={() => setPreviewUser((v) => !v)}
            className={`text-xs px-2.5 py-1 rounded border transition-colors ${
              previewUser
                ? "border-yellow-500 text-yellow-400 bg-yellow-900/20"
                : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]"
            }`}
          >
            {previewUser ? "👁 User view" : "Preview user"}
          </button>
        )}
      </div>

      {previewUser && (
        <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 px-3 py-2 text-xs text-yellow-400">
          Previewing as a free user — purchase flow is active. No real charge will occur unless you complete checkout.
        </div>
      )}

      {/* Row count card */}
      {info && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted)]">Your stat rows</span>
            <span className="text-xl font-bold text-[var(--text)]">
              {info.row_count.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted)]">Tier</span>
            <span className="text-sm text-[var(--text)]">{info.tier_label}</span>
          </div>
          {!effectivePurchased && !info.needs_upgrade && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--muted)]">One-time price</span>
              <span className="text-base font-semibold text-[var(--gold)]">
                ${info.price.toFixed(2)}
              </span>
            </div>
          )}
          {info.needs_upgrade && !previewUser && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-yellow-400">Upgrade needed</span>
              <span className="text-base font-semibold text-[var(--gold)]">
                +${info.upgrade_price?.toFixed(2)} difference
              </span>
            </div>
          )}
          {effectivePurchased && !info.needs_upgrade && (
            <div className="flex items-center gap-2 text-sm text-green-400">
              <span>✓</span>
              <span>Power Pack active — re-download any time</span>
            </div>
          )}
        </div>
      )}

      {/* Format selector */}
      {effectivePurchased && (
        <div className="flex gap-3">
          {(["csv", "json"] as Format[]).map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${
                format === f
                  ? "border-[var(--gold)] bg-[var(--gold)] text-black"
                  : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]"
              }`}
            >
              {f.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* Action button */}
      {info && (
        <div>
          {effectivePurchased ? (
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="w-full rounded-xl bg-[var(--gold)] py-3 text-sm font-bold text-black hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {downloading ? "Preparing download…" : `Download ${format.toUpperCase()}`}
            </button>
          ) : (
            <button
              onClick={handlePurchase}
              disabled={purchasing || info.row_count === 0}
              className="w-full rounded-xl bg-[var(--gold)] py-3 text-sm font-bold text-black hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {purchasing
                ? "Redirecting to checkout…"
                : info.row_count === 0
                ? "No data to export yet"
                : info.needs_upgrade && !previewUser
                ? `Upgrade Export — +$${info.upgrade_price?.toFixed(2)}`
                : `Unlock Export — $${info.price.toFixed(2)}`}
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-sm text-red-400 text-center">{error}</p>
      )}

      {/* What's included */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-2">
        <p className="text-sm font-semibold text-[var(--text)]">What&apos;s included</p>
        <ul className="text-sm text-[var(--muted)] space-y-1 list-disc pl-4">
          <li>All players and gaming session records</li>
          <li>Game name, stat type, value, win/loss, notes, timestamp</li>
          <li>CSV (spreadsheet) or JSON (developer)</li>
          <li>One-time purchase — re-download any time</li>
        </ul>
      </div>

      {/* Delete link */}
      <p className="text-xs text-center text-[var(--muted)]">
        Want to remove your data?{" "}
        <a href="/data-deletion" className="text-[var(--gold)] hover:underline">
          Data Deletion
        </a>
      </p>
    </div>
  );
}
