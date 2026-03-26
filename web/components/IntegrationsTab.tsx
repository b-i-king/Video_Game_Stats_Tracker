"use client";

import { useState } from "react";

// ── Platform definitions ───────────────────────────────────────────────────────

type Status = "coming_soon" | "available" | "connected";

interface Platform {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: Status;
  dataPoints: string[];
  note?: string;
}

const PLATFORMS: Platform[] = [
  {
    id: "riot",
    name: "Riot Games",
    description: "Valorant, League of Legends, TFT",
    icon: "🎯",
    status: "available",
    dataPoints: ["Match history", "Kills / Deaths / Assists", "Rank & tier", "Win/loss", "Agent / champion played"],
    note: "Riot has a real public API — pilot integration planned.",
  },
  {
    id: "steam",
    name: "Steam",
    description: "Counter-Strike 2, Dota 2, and more",
    icon: "🖥️",
    status: "coming_soon",
    dataPoints: ["Time played", "Achievements", "Basic per-game stats"],
    note: "Limited to what Steam exposes per game.",
  },
  {
    id: "activision",
    name: "Activision (Call of Duty)",
    description: "Warzone, Black Ops, Modern Warfare",
    icon: "🎖️",
    status: "coming_soon",
    dataPoints: ["K/D ratio", "Match result", "Damage", "Gulag stats"],
    note: "No official API — requires partnership or unofficial endpoints.",
  },
  {
    id: "ea",
    name: "EA / Respawn",
    description: "Apex Legends, EA FC, Battlefield",
    icon: "🏟️",
    status: "coming_soon",
    dataPoints: ["Match stats", "Ranked data", "Legend / hero played"],
    note: "No public API currently available.",
  },
  {
    id: "dispatch",
    name: "Dispatch",
    description: "Indie game — direct partnership",
    icon: "🚀",
    status: "coming_soon",
    dataPoints: ["Full match stats", "Session result", "Custom stat types"],
    note: "Would require direct API partnership with the developer.",
  },
];

// ── Status badge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Status }) {
  if (status === "connected") {
    return (
      <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-900/40 text-green-400 border border-green-800">
        ● Connected
      </span>
    );
  }
  if (status === "available") {
    return (
      <span className="px-2 py-0.5 rounded text-xs font-medium bg-[var(--gold)]/10 text-[var(--gold)] border border-[var(--gold)]/30">
        Soon™
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium bg-[var(--border)] text-[var(--muted)]">
      Coming Soon
    </span>
  );
}

// ── Platform card ──────────────────────────────────────────────────────────────

function PlatformCard({ platform }: { platform: Platform }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{platform.icon}</span>
          <div>
            <div className="font-semibold text-sm text-[var(--text)]">{platform.name}</div>
            <div className="text-xs text-[var(--muted)]">{platform.description}</div>
          </div>
        </div>
        <StatusBadge status={platform.status} />
      </div>

      {/* Data points toggle */}
      <button
        onClick={() => setExpanded((p) => !p)}
        className="text-xs text-[var(--muted)] hover:text-[var(--gold)] text-left transition-colors"
      >
        {expanded ? "▾ Hide" : "▸ Show"} what would sync
      </button>

      {expanded && (
        <ul className="text-xs text-[var(--muted)] space-y-1 pl-1">
          {platform.dataPoints.map((pt) => (
            <li key={pt} className="flex items-center gap-2">
              <span className="text-[var(--gold)]">•</span> {pt}
            </li>
          ))}
          {platform.note && (
            <li className="mt-2 text-[var(--muted)] italic border-t border-[var(--border)] pt-2">
              {platform.note}
            </li>
          )}
        </ul>
      )}

      {/* Connect button */}
      <div className="relative group">
        <button
          disabled
          className="w-full px-3 py-1.5 rounded border border-[var(--border)] text-sm text-[var(--muted)]
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {platform.status === "connected" ? "Disconnect" : "Connect"}
        </button>
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 rounded
                        bg-[var(--surface)] border border-[var(--border)] text-xs text-[var(--muted)]
                        whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10">
          {platform.status === "available"
            ? "Integration in development — available after Supabase migration"
            : "Integration requires API partnership"}
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function IntegrationsTab() {
  const [search, setSearch] = useState("");

  const filtered = PLATFORMS.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-[var(--gold)]">🔗 Integrations</h1>
        <p className="text-sm text-[var(--muted)] mt-1">
          Connect your gaming accounts to automatically import match stats after each session.
          Connected stats are read-only — they can&apos;t be edited or deleted.
        </p>
      </div>

      {/* How it works */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-xs text-[var(--muted)] space-y-1">
        <div className="text-sm font-semibold text-[var(--text)] mb-2">How integrations work</div>
        <div className="flex items-start gap-2"><span className="text-[var(--gold)]">1.</span> Connect your account for a supported platform below.</div>
        <div className="flex items-start gap-2"><span className="text-[var(--gold)]">2.</span> After each match, stats are automatically pulled and logged to your tracker.</div>
        <div className="flex items-start gap-2"><span className="text-[var(--gold)]">3.</span> Auto-imported rows show a platform badge and cannot be edited or deleted.</div>
        <div className="flex items-start gap-2"><span className="text-[var(--gold)]">4.</span> You still set the initial context: player name, input device, console.</div>
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search platforms or games..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="input"
      />

      {/* Platform cards */}
      {filtered.length === 0 ? (
        <p className="text-sm text-[var(--muted)] text-center py-8">No platforms match &quot;{search}&quot;</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((p) => (
            <PlatformCard key={p.id} platform={p} />
          ))}
        </div>
      )}

      {/* Footer note */}
      <p className="text-xs text-[var(--muted)] text-center pb-4">
        Want to see a game here?{" "}
        <a
          href="https://youtube.com/@TheBOLGuide"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--gold)] hover:underline"
        >
          Reach out on YouTube
        </a>
        .
      </p>
    </div>
  );
}
