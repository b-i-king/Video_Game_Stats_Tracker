"use client";
// Top navigation bar with sign-in/sign-out and role indicator.

import Link from "next/link";
import { useSession, signIn, signOut } from "next-auth/react";

export default function Navbar() {
  const { data: session } = useSession();

  return (
    <nav className="border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="w-full px-4 flex items-center justify-between h-14">
        {/* Logo / Home link */}
        <Link
          href="/"
          className="text-[var(--gold)] font-bold text-xl hover:opacity-80"
          aria-label="Home"
        >
          🎮
        </Link>

        {/* Navigation links */}
        <div className="hidden sm:flex gap-4 text-sm">
          <Link href="/" className="hover:text-[var(--gold)] transition-colors">
            Home
          </Link>
          {/* Stats page is visible only to logged-in users */}
          {session && (
            <Link
              href="/stats"
              className="hover:text-[var(--gold)] transition-colors"
            >
              Stats
            </Link>
          )}
          {session && (
            <Link
              href="/integrations"
              className="hover:text-[var(--gold)] transition-colors"
            >
              Integrations
            </Link>
          )}
          <Link
            href="/privacy"
            className="hover:text-[var(--gold)] transition-colors"
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            className="hover:text-[var(--gold)] transition-colors"
          >
            Terms
          </Link>
        </div>

        {/* Auth section */}
        <div className="flex items-center gap-3 text-sm">
          {session ? (
            <>
              {/* Role badge */}
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  session.isTrusted
                    ? "bg-[var(--gold)] text-black"
                    : "bg-[var(--border)] text-[var(--muted)]"
                }`}
              >
                {session.isTrusted ? "Admin" : "Guest"}
              </span>

              <span className="text-[var(--muted)] hidden sm:block truncate max-w-[160px]">
                {session.user?.email}
              </span>

              <button
                onClick={() => signOut({ callbackUrl: "/" })}
                className="px-3 py-1 rounded border border-[var(--border)] hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors"
              >
                Sign out
              </button>
            </>
          ) : (
            <button
              onClick={() => signIn("google")}
              className="px-3 py-1 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
            >
              Sign in with Google
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
