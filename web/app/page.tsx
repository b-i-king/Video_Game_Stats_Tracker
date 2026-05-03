// Home page — Server Component shell.
// Interactive sections (pricing toggle, Bolt AI card) are client components.

import type { Metadata } from "next";
import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import GetStartedButton from "@/components/GetStartedButton";
import PricingSection from "@/components/PricingSection";
import BoltAICard from "@/components/BoltAICard";
import FaqSection from "@/components/FaqSection";

export const metadata: Metadata = {
  title: { absolute: "🎮 Video Game Stats Tracker" },
  description:
    "Track your video game stats, generate chart graphics, and auto-post to Twitter & Instagram.",
};

const features = [
  {
    icon: "🎮",
    title: "Track Any Game",
    desc: "Log stats for any game — points, wins, scores, waves — with full history.",
    tier: "free" as const,
  },
  {
    icon: "📊",
    title: "Auto-Generated Charts",
    desc: "Beautiful bar and line chart graphics built automatically for every session.",
    tier: "free" as const,
  },
  {
    icon: "🏆",
    title: "Leaderboard",
    desc: "Opt-in to compare your stats with other players on a public leaderboard.",
    tier: "free" as const,
  },
  {
    icon: "🔗",
    title: "Integrations",
    desc: "Connect external data sources — Steam, APIs, and more — added by the developer.",
    tier: "free" as const,
  },
  {
    icon: "🤖",
    title: "Machine Learning",
    desc: "Predictive models surface performance trends and forecast future sessions.",
    tier: "premium" as const,
  },
];

export default async function HomePage() {
  const session = await getServerSession(authOptions);

  return (
    <div className="max-w-5xl mx-auto space-y-10">
      {/* Hero */}
      <section className="text-center space-y-4 pt-6">
        <h1 className="text-4xl font-bold text-[var(--gold)]">
          🎮 Video Game Stats Tracker
        </h1>
        <p className="text-lg text-[var(--muted)] max-w-2xl mx-auto">
          Log your gaming sessions, auto-generate chart graphics, and share
          your stats on Twitter & Instagram — all in one place.
        </p>

        {/* CTA buttons */}
        <div className="flex flex-wrap gap-3 justify-center mt-4">
          {session ? (
            <Link
              href="/stats"
              className="px-5 py-2 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
            >
              Open Stats Form →
            </Link>
          ) : (
            <>
              <GetStartedButton />
              <Link
                href="/privacy"
                className="px-5 py-2 rounded border border-[var(--border)] hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors"
              >
                Privacy Policy
              </Link>
            </>
          )}
        </div>
      </section>

      {/* Tier comparison — client component (needs billing toggle) */}
      {!session && <PricingSection />}

      {/* Features grid */}
      <section>
        <h2 className="text-xl font-semibold text-[var(--gold)] mb-4">
          Features
        </h2>
        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-1 relative"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="text-2xl">{f.icon}</div>
                {f.tier === "premium" ? (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--gold)] text-black shrink-0">
                    Premium
                  </span>
                ) : (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full border border-[var(--border)] text-[var(--muted)] shrink-0">
                    Free
                  </span>
                )}
              </div>
              <div className="font-semibold">{f.title}</div>
              <p className="text-sm text-[var(--muted)]">{f.desc}</p>
            </div>
          ))}

          {/* Bolt AI — client component (needs free/premium toggle) */}
          <BoltAICard />
        </div>
      </section>

      {/* FAQ — visible content required for FAQPage schema to be valid */}
      <FaqSection />

      {/* Legal links */}
      <section className="text-sm text-center text-[var(--muted)] space-x-4">
        <Link href="/privacy" className="hover:text-[var(--gold)]">
          Privacy Policy
        </Link>
        <Link href="/terms" className="hover:text-[var(--gold)]">
          Terms of Service
        </Link>
        <Link href="/data-deletion" className="hover:text-[var(--gold)]">
          Data Deletion
        </Link>
      </section>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: [
              {
                "@type": "Question",
                name: "What is a video game stats tracker?",
                acceptedAnswer: { "@type": "Answer", text: "A video game stats tracker is a web app that lets you log, store, and analyze your in-game performance data — score, eliminations, win rate, KPIs — across multiple sessions and games. VGST tracks all your games in one place without requiring any app download." },
              },
              {
                "@type": "Question",
                name: "Can I track stats for every game in one place?",
                acceptedAnswer: { "@type": "Answer", text: "Yes. VGST is a universal platform — add any game manually or via API integrations (Steam and Riot Games coming soon) and log stats for all of them from a single dashboard. No separate app download needed for each game." },
              },
              {
                "@type": "Question",
                name: "Is Video Game Stats Tracker free?",
                acceptedAnswer: { "@type": "Answer", text: "Yes, there is a free tier with full stat logging and analytics. A Premium plan unlocks advanced features including AI win-probability predictions, data export, and leaderboard access." },
              },
              {
                "@type": "Question",
                name: "Do I need to download an app to track my gaming stats?",
                acceptedAnswer: { "@type": "Answer", text: "No. VGST runs entirely in your web browser. There is nothing to install — just sign in with Google and start logging your sessions." },
              },
              {
                "@type": "Question",
                name: "How does AI win probability prediction work?",
                acceptedAnswer: { "@type": "Answer", text: "After you log enough sessions with win/loss results, the app trains a logistic regression model on your personal stats. It then computes a win probability percentage for each new session based on your historical performance." },
              },
              {
                "@type": "Question",
                name: "Will Steam and Riot Games stats be supported?",
                acceptedAnswer: { "@type": "Answer", text: "Yes. Steam API integration and Riot Games (Valorant, League of Legends) API integration are on the roadmap. Once live, your stats will import automatically without manual logging." },
              },
            ],
          }),
        }}
      />
    </div>
  );
}
