"use client";
// Top navigation bar with sign-in/sign-out and role indicator.

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useTheme } from "@/components/ThemeProvider";
import LanguagePicker from "@/components/LanguagePicker";

export default function Navbar() {
  const { data: session } = useSession();
  const { theme, toggle } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const t = useTranslations("nav");
  const tAuth = useTranslations("auth");

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

        {/* Logo / Home link + theme toggle */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-[var(--gold)] font-bold text-xl hover:opacity-80"
            aria-label="Home"
          >
            🎮
          </Link>
          <button
            onClick={toggle}
            role="switch"
            aria-checked={theme === "light"}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className={`relative w-11 h-6 rounded-full transition-colors duration-200
              ${theme === "light" ? "bg-sky-200" : "bg-zinc-600"}`}
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm
              flex items-center justify-center text-xs transition-transform duration-200
              ${theme === "light" ? "translate-x-5" : "translate-x-0"}`}
            >
              {theme === "dark" ? "🌙" : "☀️"}
            </span>
          </button>
        </div>

        {/* Primary nav links — absolutely centered on the full navbar width */}
        <div className="absolute left-1/2 -translate-x-1/2 flex gap-4 text-sm">
          <Link href="/" className="hover:text-[var(--gold)] transition-colors">
            {t("home")}
          </Link>
          {session && (
            <Link href="/stats" className="hover:text-[var(--gold)] transition-colors">
              {t("stats")}
            </Link>
          )}
          {session && (
            <Link href="/dashboard" className="hover:text-[var(--gold)] transition-colors">
              {t("dashboard")}
            </Link>
          )}
          {session && (
            <Link href="/leaderboard" className="hover:text-[var(--gold)] transition-colors">
              {t("leaderboard")}
            </Link>
          )}
          {/* Phase 3: History 📊 | Dashboard 📺 | Insights 🤖
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
                  isOwner   ? { label: tAuth("roles.owner"),   cls: "text-[var(--gold)] border-yellow-600 bg-yellow-900/30" } :
                  isTrusted ? { label: tAuth("roles.trusted"), cls: "text-blue-300 border-blue-700 bg-blue-900/30" } :
                  (session.role as string) === "premium"
                            ? { label: tAuth("roles.premium"), cls: "text-purple-300 border-purple-700 bg-purple-900/30" } :
                              { label: tAuth("roles.free"),    cls: "text-emerald-300 border-emerald-700 bg-emerald-900/30" };
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
                {t("signOut")}
              </button>
            </>
          ) : (
            <button
              onClick={() => signIn("google")}
              className="px-3 py-1 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
            >
              {t("signIn")}
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

                {/* Account — first item when signed in */}
                {session && (
                  <>
                    <MenuLink href="/account" onClick={() => setMenuOpen(false)}>
                      {t("account")}
                    </MenuLink>
                    <div className="my-1 border-t border-[var(--border)]" />
                  </>
                )}

                {/* Signed-in app links */}
                {session && (
                  <>
                    <MenuLink href="/integrations" onClick={() => setMenuOpen(false)}>
                      {t("integrations")}
                    </MenuLink>
                    <MenuLink href="/data-export" onClick={() => setMenuOpen(false)}>
                      {t("dataExport")}
                    </MenuLink>
                    <div className="my-1 border-t border-[var(--border)]" />
                  </>
                )}

                <MenuLink href="/about" onClick={() => setMenuOpen(false)}>
                  {t("about")}
                </MenuLink>
                <MenuLink href="/privacy" onClick={() => setMenuOpen(false)}>
                  {t("privacy")}
                </MenuLink>
                <MenuLink href="/terms" onClick={() => setMenuOpen(false)}>
                  {t("terms")}
                </MenuLink>

                {/* Language picker */}
                <div className="my-1 border-t border-[var(--border)]" />
                <LanguagePicker onSelect={() => setMenuOpen(false)} />

                {/* Account info footer — email + tier + sign out */}
                <div className="my-1 border-t border-[var(--border)]" />
                <div className="px-3 py-2 flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)] truncate px-1">
                    {session ? session.user?.email : tAuth("notSignedIn")}
                  </span>

                  {(() => {
                    const cfg = !session
                      ? { label: tAuth("roles.guest"),   cls: "text-zinc-400 border-zinc-600 bg-zinc-800/30" }
                      : session.isOwner
                      ? { label: tAuth("roles.owner"),   cls: "text-[var(--gold)] border-yellow-600 bg-yellow-900/30" }
                      : session.isTrusted
                      ? { label: tAuth("roles.trusted"), cls: "text-blue-300 border-blue-700 bg-blue-900/30" }
                      : (session.role as string) === "premium"
                      ? { label: tAuth("roles.premium"), cls: "text-purple-300 border-purple-700 bg-purple-900/30" }
                      : { label: tAuth("roles.free"),    cls: "text-emerald-300 border-emerald-700 bg-emerald-900/30" };
                    return (
                      <span className={`w-full text-center text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cfg.cls}`}>
                        {cfg.label}
                      </span>
                    );
                  })()}

                  {session ? (
                    <button
                      onClick={() => { setMenuOpen(false); signOut({ callbackUrl: "/" }); }}
                      className="w-full text-sm py-1.5 rounded border border-[var(--border)] hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors"
                    >
                      {t("signOut")}
                    </button>
                  ) : (
                    <button
                      onClick={() => { setMenuOpen(false); signIn("google"); }}
                      className="w-full text-sm py-1.5 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
                    >
                      {t("signIn")}
                    </button>
                  )}
                </div>
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
