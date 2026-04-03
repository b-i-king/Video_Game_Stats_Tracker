// About page — app description and tier comparison

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About — Video Game Stats Tracker",
};

const TIERS = [
  {
    name: "Free",
    badge: "text-emerald-300 border-emerald-700 bg-emerald-900/30",
    features: [
      "Track stats for up to 3 games",
      "Submit session results",
      "View personal bests & summaries",
      "20 Bolt AI requests / month",
      "Read-only leaderboard access (Phase 3)",
    ],
    locked: [
      "Social media posting",
      "Dashboard / OBS overlay",
      "Trend insights & predictions",
      "CSV / JSON data export (Phase 3)",
    ],
  },
  {
    name: "Premium",
    badge: "text-purple-300 border-purple-700 bg-purple-900/30",
    features: [
      "Everything in Free",
      "Unlimited game tracking",
      "2 000 Bolt AI requests / month",
      "CSV / JSON data export (Phase 3)",
      "Leaderboard opt-in (Phase 3)",
      "Dashboard / OBS overlay (Phase 3)",
      "Trend insights & predictions (Phase 3)",
    ],
    locked: ["Social media auto-posting", "Admin controls"],
  },
  {
    name: "Trusted",
    badge: "text-blue-300 border-blue-700 bg-blue-900/30",
    features: [
      "Everything in Premium",
      "Social media auto-posting (Twitter + Instagram queue)",
      "Post queue management",
      "Manually invited by owner",
    ],
    locked: ["Admin controls"],
  },
  {
    name: "Owner",
    badge: "text-[var(--gold)] border-yellow-600 bg-yellow-900/30",
    features: [
      "All capabilities",
      "Post queue + immediate posting",
      "Admin panel (Phase 3)",
      "User management & ban controls (Phase 3)",
      "Violation log review (Phase 3)",
    ],
    locked: [],
  },
];

export default function AboutPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-8 py-4">
      <h1 className="text-3xl font-bold text-[var(--gold)]">
        About Video Game Stats Tracker
      </h1>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">What is this?</h2>
        <p>
          <strong>Video Game Stats Tracker</strong> is a personal stats
          platform built by <strong>BOL Group LLC</strong>. It lets you log
          gaming session results, visualize performance trends over time, and
          optionally share highlights to social media — all from one place.
        </p>
        <p>
          Sign in with your Google account to get started. Your stats are
          private to you by default, with an opt-in leaderboard coming in
          Phase 3.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Features</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>Log per-session stats for any game (kills, deaths, assists, wins, and more).</li>
          <li>Interactive charts and personal-best summaries per game.</li>
          <li>
            <strong className="text-[var(--text)]">Bolt AI</strong> — an
            in-app assistant that answers questions about your own stats.
          </li>
          <li>Social media post queue for Twitter and Instagram (Trusted / Owner).</li>
          <li>Riot Games API integration for automatic stat imports (coming soon).</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">User Tiers</h2>
        <p className="text-[var(--muted)]">
          Access is tiered. Items marked <em>Phase 3</em> are in development
          and not yet live.
        </p>

        <div className="not-prose grid gap-4 sm:grid-cols-2">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${tier.badge}`}
                >
                  {tier.name}
                </span>
              </div>

              <ul className="space-y-1 text-sm text-[var(--muted)]">
                {tier.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-emerald-400 shrink-0">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
                {tier.locked.map((f) => (
                  <li key={f} className="flex gap-2 opacity-40">
                    <span className="shrink-0">✗</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Tech Stack</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--text)]">Frontend</strong> — Next.js
            (App Router) deployed on Vercel.
          </li>
          <li>
            <strong className="text-[var(--text)]">Backend</strong> — Flask
            API (Python), migrating to FastAPI in Phase 3.
          </li>
          <li>
            <strong className="text-[var(--text)]">Database</strong> —
            Supabase (PostgreSQL) with row-level security.
          </li>
          <li>
            <strong className="text-[var(--text)]">Auth</strong> — NextAuth.js
            with Google OAuth.
          </li>
          <li>
            <strong className="text-[var(--text)]">Social automation</strong>{" "}
            — AWS Lambda + EventBridge, IFTTT webhooks.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Contact</h2>
        <p>
          Questions or feedback? Email us at{" "}
          <a
            href="mailto:thebolgroup.llc@gmail.com"
            className="text-[var(--gold)] hover:underline"
          >
            thebolgroup.llc@gmail.com
          </a>
          .
        </p>
      </section>
    </div>
  );
}
