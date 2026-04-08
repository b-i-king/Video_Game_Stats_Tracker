"use client";

import { useState } from "react";

export default function BoltAICard() {
  const [tier, setTier] = useState<"free" | "premium">("free");

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-2 relative">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="text-2xl">⚡</div>
        {/* Tier toggle */}
        <div className="flex rounded-full border border-[var(--border)] overflow-hidden text-xs shrink-0">
          <button
            onClick={() => setTier("free")}
            className={`px-2.5 py-0.5 transition-colors ${
              tier === "free"
                ? "bg-[var(--border)] text-[var(--text)] font-semibold"
                : "text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            Free
          </button>
          <button
            onClick={() => setTier("premium")}
            className={`px-2.5 py-0.5 transition-colors ${
              tier === "premium"
                ? "bg-[var(--gold)] text-black font-semibold"
                : "text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            Premium
          </button>
        </div>
      </div>

      <div className="font-semibold">Bolt AI Assistant</div>

      {tier === "free" ? (
        <div className="space-y-1">
          <p className="text-sm text-[var(--muted)]">
            Ask natural language questions about your stats — trends, insights, and caption ideas.
          </p>
          <p className="text-xs text-[var(--muted)] font-medium">20 queries / month</p>
        </div>
      ) : (
        <div className="space-y-1">
          <p className="text-sm text-[var(--muted)]">
            Full Bolt AI access — deeper analysis, longer context, faster responses, and priority model access.
          </p>
          <p className="text-xs text-[var(--gold)] font-medium">200 queries / month</p>
        </div>
      )}
    </div>
  );
}
