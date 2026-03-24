// Home page — mirrors pages/1_Home.py
// This is a Server Component (no "use client" needed).

import type { Metadata } from "next";
import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import GetStartedButton from "@/components/GetStartedButton";

export const metadata: Metadata = {
  title: "Home | 🎮 Video Game Stats Tracker",
  description:
    "Track your video game stats, generate chart graphics, and auto-post to Twitter & Instagram.",
};

const features = [
  {
    icon: "🎮",
    title: "Track Any Game",
    desc: "Log stats for any game — kills, wins, scores, waves — with full history.",
  },
  {
    icon: "📊",
    title: "Auto-Generated Charts",
    desc: "Bar and line chart graphics are built automatically for each session.",
  },
  {
    icon: "📱",
    title: "Social Media Auto-Post",
    desc: "Posts go out to Twitter and Instagram automatically after you submit.",
  },
  {
    icon: "🔴",
    title: "Live Streaming Mode",
    desc: "Enable Live Mode to add #Live hashtags and stream links to posts.",
  },
  {
    icon: "🎬",
    title: "OBS Overlay & Ticker",
    desc: "Real-time stat overlay and scrolling ticker for OBS scenes.",
  },
  {
    icon: "📈",
    title: "Weekly Recaps",
    desc: "Automated Saturday recap posts summarize your week of gaming.",
  },
];

export default async function HomePage() {
  const session = await getServerSession(authOptions);

  return (
    <div className="space-y-10">
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

      {/* Auth notice */}
      {!session && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 text-center space-y-2">
          <p className="font-semibold">Three ways to use this app:</p>
          <div className="grid sm:grid-cols-3 gap-4 text-sm mt-3">
            <div className="p-3 rounded border border-[var(--border)] space-y-1">
              <div className="text-[var(--gold)] font-semibold">
                🔐 Trusted User
              </div>
              <p className="text-[var(--muted)]">
                Full access — submit stats, edit, delete, manage social media
                posts.
              </p>
            </div>
            <div className="p-3 rounded border border-[var(--border)] space-y-1">
              <div className="font-semibold">👤 Registered Guest</div>
              <p className="text-[var(--muted)]">
                Sign in with Google — view the form and your stats history
                (read-only).
              </p>
            </div>
            <div className="p-3 rounded border border-[var(--border)] space-y-1">
              <div className="font-semibold">👁️ No Sign-in</div>
              <p className="text-[var(--muted)]">
                Browse the home, privacy, and terms pages without logging in.
              </p>
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
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-1"
            >
              <div className="text-2xl">{f.icon}</div>
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
