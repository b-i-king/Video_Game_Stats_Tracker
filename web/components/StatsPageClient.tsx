"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import StatsForm from "./StatsForm";
import EditTab from "./EditTab";
import DeleteTab from "./DeleteTab";
import QueuePanel from "./QueuePanel";
import BoltPanel from "./BoltPanel";
import LastSessionPanel from "./LastSessionPanel";
import { ToastProvider } from "./Toast";
import SummaryTab from "./SummaryTab";

type Tab = "enter" | "edit" | "delete" | "summary";

// ── Business hours helper (mirrors is_business_hours_pst() in app_utils.py) ──
function getNthWeekday(year: number, month: number, weekday: number, n: number): Date {
  // month is 0-based (JS Date). weekday: 0=Sun…6=Sat
  const d = new Date(year, month, 1);
  let count = 0;
  while (d.getMonth() === month) {
    if (d.getDay() === weekday) { count++; if (count === n) return new Date(d); }
    d.setDate(d.getDate() + 1);
  }
  return new Date(year, month, 1); // fallback
}

function getLastWeekday(year: number, month: number, weekday: number): Date {
  // Last occurrence of weekday in month
  const d = new Date(year, month + 1, 0); // last day of month
  while (d.getDay() !== weekday) d.setDate(d.getDate() - 1);
  return new Date(d);
}

function isBusinessHoursPST(): boolean {
  // Convert current time to America/Los_Angeles
  const now = new Date();
  const pstStr = now.toLocaleString("en-US", { timeZone: "America/Los_Angeles" });
  const pst = new Date(pstStr);
  const year = pst.getFullYear();
  const month = pst.getMonth(); // 0-based
  const day = pst.getDate();
  const hour = pst.getHours();
  const dow = pst.getDay(); // 0=Sun, 1=Mon…6=Sat

  // Must be Mon–Fri
  if (dow === 0 || dow === 6) return false;
  // Must be 9am–4:59pm
  if (hour < 9 || hour >= 17) return false;

  // US federal holidays (same list as Python)
  const holidays = [
    new Date(year, 0, 1),                          // New Year's Day
    getNthWeekday(year, 0, 1, 3),                  // MLK Day — 3rd Mon in Jan
    getLastWeekday(year, 4, 1),                    // Memorial Day — last Mon in May
    new Date(year, 5, 19),                         // Juneteenth
    new Date(year, 6, 4),                          // Independence Day
    getNthWeekday(year, 8, 1, 1),                  // Labor Day — 1st Mon in Sep
    new Date(year, 10, 11),                        // Veterans Day
    getNthWeekday(year, 10, 4, 4),                 // Thanksgiving — 4th Thu in Nov
    new Date(year, 11, 25),                        // Christmas
  ];

  const today = `${year}-${month}-${day}`;
  const isHoliday = holidays.some(
    (h) => `${h.getFullYear()}-${h.getMonth()}-${h.getDate()}` === today
  );
  return !isHoliday;
}

export default function StatsPageClient() {
  const { data: session } = useSession();
  const isTrusted = session?.isTrusted ?? false;
  const isOwner = session?.isOwner ?? false;
  const jwt = session?.flaskJwt ?? "";

  const [activeTab, setActiveTab] = useState<Tab>("enter");
  const [lastSessionKey, setLastSessionKey] = useState(0);

  // Auto-ON during weekdays 9am–5pm PST (excl. federal holidays), manual override respected
  const [queueMode, setQueueModeState] = useState(() => isBusinessHoursPST());
  const [isManualOverride, setIsManualOverride] = useState(false);
  const [enabledPlatforms, setEnabledPlatforms] = useState<string[]>(["twitter"]);
  const [mobilePanel, setMobilePanel] = useState<"bolt" | "queue" | null>(null);

  function setQueueMode(val: boolean) {
    const auto = isBusinessHoursPST();
    setQueueModeState(val);
    setIsManualOverride(val !== auto);
  }

  if (!session) return null;

  return (
    <ToastProvider>
      <div className="space-y-6 pb-20 lg:pb-0">
        <h1 className="text-2xl font-bold text-[var(--gold)] text-center">
          🎮 Video Game Stats Entry
        </h1>

        {!isTrusted && (
          <div className="rounded border border-yellow-600 bg-yellow-900/20 px-4 py-3 text-sm text-yellow-200">
            You are signed in as a <strong>Registered Guest</strong>. The Stats
            form is in read-only preview mode. Contact the admin for full access.
          </div>
        )}

        <div className="flex gap-6 items-stretch">
          {/* Bolt AI sidebar — desktop only, all signed-in users */}
          <aside className="hidden lg:block w-64 shrink-0 self-start sticky top-6 h-[510px]">
            <BoltPanel jwt={jwt} />
          </aside>

          <div className="flex-1 min-w-0">
            {/* Tabs */}
            <div className="flex border-b border-[var(--border)] mb-5">
              {(["enter", "summary", ...(isTrusted ? ["edit", "delete"] : [])] as Tab[]).map(
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
                    {tab === "enter" ? "Enter Stats" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                )
              )}
            </div>

            {activeTab === "enter" && (
              <StatsForm jwt={jwt} isTrusted={isTrusted} queueMode={queueMode} activePlatforms={enabledPlatforms} onSuccess={() => setLastSessionKey((k) => k + 1)} />
            )}
            {activeTab === "summary" && <SummaryTab jwt={jwt} />}
            {activeTab === "edit" && isTrusted && <EditTab jwt={jwt} />}
            {activeTab === "delete" && isTrusted && <DeleteTab jwt={jwt} />}
          </div>

          {/* Right sidebar — desktop only, all signed-in users */}
          <aside className="hidden lg:block w-64 shrink-0 self-start sticky top-6 h-[510px]">
            {isOwner
              ? <QueuePanel jwt={jwt} queueMode={queueMode} setQueueMode={setQueueMode} isManualOverride={isManualOverride} enabledPlatforms={enabledPlatforms} setEnabledPlatforms={setEnabledPlatforms} />
              : <LastSessionPanel jwt={jwt} refreshKey={lastSessionKey} />
            }
          </aside>
        </div>

        {/* Mobile bottom bar — all signed-in users, hidden on desktop */}
        <div className="lg:hidden fixed bottom-0 left-0 right-0 z-40 flex border-t border-[var(--border)] bg-[var(--surface)]">
          <button
            onClick={() => setMobilePanel((p) => (p === "bolt" ? null : "bolt"))}
            className={`flex-1 py-3 text-xs flex flex-col items-center gap-0.5 transition-colors ${
              mobilePanel === "bolt" ? "text-[var(--gold)]" : "text-[var(--muted)]"
            }`}
          >
            <span className="text-lg">⚡</span>
            <span>Bolt</span>
          </button>
          <button
            onClick={() => setMobilePanel((p) => (p === "queue" ? null : "queue"))}
            className={`flex-1 py-3 text-xs flex flex-col items-center gap-0.5 transition-colors ${
              mobilePanel === "queue" ? "text-[var(--gold)]" : "text-[var(--muted)]"
            }`}
          >
            <span className="text-lg">{isOwner ? "📬" : "🕹️"}</span>
            <span>{isOwner ? "Queue" : "Last Session"}</span>
          </button>
        </div>

        {/* Mobile drawer */}
        {mobilePanel && (
          <div
            className="lg:hidden fixed inset-0 z-30 bg-black/50"
            onClick={() => setMobilePanel(null)}
          >
            <div
              className="absolute bottom-[52px] left-0 right-0 max-h-[70vh] overflow-y-auto bg-[var(--surface)] border-t border-[var(--border)] p-4"
              onClick={(e) => e.stopPropagation()}
            >
              {mobilePanel === "bolt" && <BoltPanel jwt={jwt} />}
              {mobilePanel === "queue" && (
                isOwner
                  ? <QueuePanel jwt={jwt} queueMode={queueMode} setQueueMode={setQueueMode} isManualOverride={isManualOverride} enabledPlatforms={enabledPlatforms} setEnabledPlatforms={setEnabledPlatforms} />
                  : <LastSessionPanel jwt={jwt} refreshKey={lastSessionKey} />
              )}
            </div>
          </div>
        )}
      </div>
    </ToastProvider>
  );
}
