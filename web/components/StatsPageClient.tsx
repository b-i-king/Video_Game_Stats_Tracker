"use client";
// Parent client component for the Stats page.
// Renders tabs (Enter Stats / Edit / Delete) and the Queue Mode sidebar panel.

import { useState } from "react";
import { useSession } from "next-auth/react";
import StatsForm from "./StatsForm";
import EditTab from "./EditTab";
import DeleteTab from "./DeleteTab";
import QueuePanel from "./QueuePanel";

type Tab = "enter" | "edit" | "delete";

export default function StatsPageClient() {
  const { data: session } = useSession();
  const isTrusted = session?.isTrusted ?? false;
  const jwt = session?.flaskJwt ?? "";

  const [activeTab, setActiveTab] = useState<Tab>("enter");

  if (!session) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--gold)] text-center">
        🎮 Video Game Stats Entry
      </h1>

      {/* Guest banner */}
      {!isTrusted && (
        <div className="rounded border border-yellow-600 bg-yellow-900/20 px-4 py-3 text-sm text-yellow-200">
          You are signed in as a <strong>Registered Guest</strong>. The Stats
          form is in read-only preview mode. Contact the admin to be granted
          full access.
        </div>
      )}

      <div className="flex gap-6">
        {/* ── Main content ── */}
        <div className="flex-1 min-w-0">
          {/* Tabs — Edit & Delete are trusted-only */}
          <div className="flex border-b border-[var(--border)] mb-5">
            {(["enter", ...(isTrusted ? ["edit", "delete"] : [])] as Tab[]).map(
              (tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
                    activeTab === tab
                      ? "border-[var(--gold)] text-[var(--gold)]"
                      : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"
                  }`}
                >
                  {tab === "enter"
                    ? "Enter Stats"
                    : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              )
            )}
          </div>

          {activeTab === "enter" && (
            <StatsForm jwt={jwt} isTrusted={isTrusted} />
          )}
          {activeTab === "edit" && isTrusted && <EditTab jwt={jwt} />}
          {activeTab === "delete" && isTrusted && <DeleteTab jwt={jwt} />}
        </div>

        {/* ── Queue sidebar (trusted only, desktop) ── */}
        {isTrusted && (
          <aside className="hidden lg:block w-64 shrink-0">
            <QueuePanel jwt={jwt} />
          </aside>
        )}
      </div>
    </div>
  );
}
