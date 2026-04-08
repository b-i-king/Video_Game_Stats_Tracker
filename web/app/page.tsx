// Home page — mirrors pages/1_Home.py
// This is a Server Component (no "use client" needed).

import type { Metadata } from "next";
import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import GetStartedButton from "@/components/GetStartedButton";

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
  {
    icon: "⚡",
    title: "Bolt AI Assistant",
    desc: "Ask natural language questions about your stats — trends, insights, caption ideas. Free: 20/mo · Premium: 200/mo.",
    tier: "free" as const,
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

      {/* Tier comparison */}
      {!session && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
          <p className="font-semibold text-center">Choose your plan</p>
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            {/* Free */}
            <div className="p-4 rounded-lg border border-[var(--border)] space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-base">Free</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-[var(--border)] text-[var(--muted)]">
                  Sign in with Google
                </span>
              </div>
              <ul className="space-y-1.5 text-[var(--muted)]">
                <li className="flex gap-2"><span className="text-green-500">✓</span> Track stats for up to 2 players</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> Auto-generated chart graphics</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> Full session history</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> Leaderboard opt-in</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> Developer integrations</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> 20 Bolt AI queries / month</li>
                <li className="flex gap-2"><span className="text-[var(--muted)]">✗</span> ML predictive models</li>
              </ul>
              <Link
                href="/auth/signin"
                className="block text-center w-full py-2 rounded border border-[var(--border)] hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors font-medium"
              >
                Get Started Free
              </Link>
            </div>

            {/* Premium */}
            <div className="p-4 rounded-lg border border-[var(--gold)] space-y-3 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[var(--gold)] text-black">
                  Most Popular
                </span>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="font-semibold text-base text-[var(--gold)]">Premium</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--gold)] text-black font-semibold">
                  Upgraded by owner
                </span>
              </div>
              <ul className="space-y-1.5 text-[var(--muted)]">
                <li className="flex gap-2"><span className="text-green-500">✓</span> Everything in Free</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> Track stats for up to 5 players</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> ML predictive models</li>
                <li className="flex gap-2"><span className="text-green-500">✓</span> 200 Bolt AI queries / month</li>
              </ul>
              <Link
                href="/auth/signin"
                className="block text-center w-full py-2 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
              >
                Sign In to Upgrade
              </Link>
            </div>
          </div>
        </section>
      )}

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
        </div>
      </section>

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
    </div>
  );
}
