"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const FREE_PERKS = [
  "Track stats for up to 2 players",
  "Auto-generated chart graphics",
  "Full session history & trends",
  "Leaderboard opt-in",
  "Developer integrations (Steam, etc.)",
  "20 Bolt AI queries / month",
];

const PREMIUM_PERKS = [
  "Everything in Free",
  "Track stats for up to 5 players",
  "ML predictive performance models",
  "200 Bolt AI queries / month",
];

function SignInContent() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? "/stats";

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-4xl space-y-8">
        {/* Branding */}
        <div className="text-center space-y-2">
          <div className="text-5xl">🎮</div>
          <h1 className="text-3xl font-bold text-[var(--gold)]">
            Video Game Stats Tracker
          </h1>
          <p className="text-[var(--muted)] text-sm">
            Log sessions · Auto-generate charts · Bolt AI insights
          </p>
        </div>

        {/* Main layout: Free | Sign-in card | Premium */}
        <div className="grid md:grid-cols-3 gap-4 items-stretch">

          {/* Free tier */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 h-full">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg">Free</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-[var(--border)] text-[var(--muted)]">
                  Default
                </span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Included when you sign in with Google.
              </p>
            </div>
            <ul className="space-y-2 text-sm">
              {FREE_PERKS.map((perk) => (
                <li key={perk} className="flex gap-2 text-[var(--muted)]">
                  <span className="text-green-500 shrink-0">✓</span>
                  {perk}
                </li>
              ))}
            </ul>
          </div>

          {/* Sign-in card */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 space-y-6 shadow-xl h-full">
            <div className="space-y-1 text-center">
              <h2 className="text-lg font-semibold">Sign in to continue</h2>
              <p className="text-sm text-[var(--muted)]">
                Your game data is tied to your Google account.
              </p>
            </div>

            <button
              onClick={() => signIn("google", { callbackUrl })}
              className="w-full flex items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-white text-gray-800 font-medium px-4 py-3 hover:bg-gray-100 transition-colors"
            >
              {/* Google logo SVG */}
              <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
                <path
                  fill="#EA4335"
                  d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
                />
                <path
                  fill="#4285F4"
                  d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
                />
                <path
                  fill="#FBBC05"
                  d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
                />
                <path
                  fill="#34A853"
                  d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
                />
                <path fill="none" d="M0 0h48v48H0z" />
              </svg>
              Sign in with Google
            </button>

            <p className="text-xs text-center text-[var(--muted)]">
              By signing in you agree to our{" "}
              <a href="/terms" className="hover:text-[var(--gold)] underline">
                Terms
              </a>{" "}
              and{" "}
              <a href="/privacy" className="hover:text-[var(--gold)] underline">
                Privacy Policy
              </a>
              .
            </p>
          </div>

          {/* Premium tier */}
          <div className="rounded-xl border border-[var(--gold)] bg-[var(--surface)] p-5 space-y-4 relative h-full">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[var(--gold)] text-black whitespace-nowrap">
                ⚡ Premium
              </span>
            </div>
            <div className="space-y-1 pt-2">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-[var(--gold)]">Premium</span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Unlocked by the app owner — contact to request an upgrade.
              </p>
            </div>
            <ul className="space-y-2 text-sm">
              {PREMIUM_PERKS.map((perk) => (
                <li key={perk} className="flex gap-2 text-[var(--muted)]">
                  <span className="text-[var(--gold)] shrink-0">✓</span>
                  {perk}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Footer links */}
        <div className="text-center text-xs text-[var(--muted)] space-x-3">
          <a href="/privacy" className="hover:text-[var(--gold)] transition-colors">
            Privacy Policy
          </a>
          <span>·</span>
          <a href="/terms" className="hover:text-[var(--gold)] transition-colors">
            Terms of Service
          </a>
          <span>·</span>
          <a href="/data-deletion" className="hover:text-[var(--gold)] transition-colors">
            Data Deletion
          </a>
        </div>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense>
      <SignInContent />
    </Suspense>
  );
}
