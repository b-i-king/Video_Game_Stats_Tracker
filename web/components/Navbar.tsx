"use client";
// Top navigation bar with sign-in/sign-out and role indicator.

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { useSession, signIn, signOut } from "next-auth/react";

export default function Navbar() {
  const { data: session } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <nav className="border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="w-full px-4 flex items-center justify-between h-14 relative">

        {/* Logo / Home link */}
        <Link
          href="/"
          className="text-[var(--gold)] font-bold text-xl hover:opacity-80"
          aria-label="Home"
        >
          🎮
        </Link>

        {/* Primary nav links — absolutely centered on the full navbar width */}
        <div className="absolute left-1/2 -translate-x-1/2 flex gap-4 text-sm">
          <Link href="/" className="hover:text-[var(--gold)] transition-colors">
            Home
          </Link>
          {session && (
            <Link href="/stats" className="hover:text-[var(--gold)] transition-colors">
              Stats
            </Link>
          )}
          {/* Phase 3: History 📊 | Dashboard 📺 | Insights 🤖 | Leaderboard 🏆
              — rendered here based on role/tier once those pages exist */}
        </div>

        {/* Auth + hamburger section */}
        <div className="flex items-center gap-3 text-sm">
          {session ? (
            <>
              <span className="text-[var(--muted)] hidden xl:block truncate max-w-[160px]">
                {session.user?.email}
              </span>

              {/* Tier badge — 5 levels, Phase 3 adds Premium via role column */}
              {(() => {
                const isOwner   = session.isOwner;
                const isTrusted = session.isTrusted;
                const cfg =
                  isOwner   ? { label: "Owner",   cls: "text-[var(--gold)] border-yellow-600 bg-yellow-900/30" } :
                  isTrusted ? { label: "Trusted",  cls: "text-blue-300 border-blue-700 bg-blue-900/30" } :
                  /* Phase 3: premium check here */
                              { label: "Free",     cls: "text-emerald-300 border-emerald-700 bg-emerald-900/30" };
                return (
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${cfg.cls}`}>
                    {cfg.label}
                  </span>
                );
              })()}

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

          {/* Hamburger menu */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Menu"
              className="flex flex-col justify-center items-center w-8 h-8 gap-1.5 hover:text-[var(--gold)] transition-colors"
            >
              <span className={`block w-5 h-0.5 bg-current transition-transform origin-center ${menuOpen ? "rotate-45 translate-y-2" : ""}`} />
              <span className={`block w-5 h-0.5 bg-current transition-opacity ${menuOpen ? "opacity-0" : ""}`} />
              <span className={`block w-5 h-0.5 bg-current transition-transform origin-center ${menuOpen ? "-rotate-45 -translate-y-2" : ""}`} />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-10 w-52 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg py-1 z-50">

                {/* Signed-in app links */}
                {session && (
                  <>
                    <MenuLink href="/integrations" onClick={() => setMenuOpen(false)}>
                      Integrations
                    </MenuLink>
                    <div className="my-1 border-t border-[var(--border)]" />
                  </>
                )}

                {/* Phase 3 role-gated tabs:
                    History 📊     — all logged-in users (stat session history, filters, search)
                    Dashboard 📺   — trusted + owner + premium (OBS overlay, live session view)
                    Insights 🤖    — trusted + owner + premium (ML predictions, trend analysis)
                    Leaderboard 🏆 — all logged-in users (opt-in, public Supabase project)
                    Admin 🛡️       — owner only (flagged users, ban/unban, violation log)
                */}

                {/* About — app description + tier comparison (Free / Premium / Trusted / Owner) */}
                <MenuLink href="/about" onClick={() => setMenuOpen(false)}>
                  About
                </MenuLink>

                <div className="my-1 border-t border-[var(--border)]" />

                {/* Privacy — Phase 3 adds live leaderboard opt-out toggle on this page */}
                <MenuLink href="/privacy" onClick={() => setMenuOpen(false)}>
                  Privacy
                </MenuLink>
                <MenuLink href="/terms" onClick={() => setMenuOpen(false)}>
                  Terms
                </MenuLink>

                {session && (
                  <>
                    <div className="my-1 border-t border-[var(--border)]" />
                    {/* Data — Phase 3: CSV/JSON export of user's own stats (GDPR portability) */}
                    <MenuLink href="/data-export" onClick={() => setMenuOpen(false)}>
                      Data
                    </MenuLink>
                    {/* Delete Account — Phase 3: verified cascade across all tables */}
                    <MenuLink
                      href="/account/delete"
                      onClick={() => setMenuOpen(false)}
                      danger
                    >
                      Delete Account
                    </MenuLink>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

// ── Menu item helper ──────────────────────────────────────────────────────────
function MenuLink({
  href,
  onClick,
  danger = false,
  children,
}: {
  href: string;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`block px-4 py-2 text-sm transition-colors ${
        danger
          ? "text-red-400 hover:bg-red-900/20"
          : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]/40"
      }`}
    >
      {children}
    </Link>
  );
}
