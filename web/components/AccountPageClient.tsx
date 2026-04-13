"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import {
  getSubscriptionStatus,
  createSubscriptionCheckout,
  createBillingPortal,
  type SubscriptionStatus,
} from "@/lib/api";

type Interval = "month" | "year";

const MONTHLY_PRICE = 10;
const ANNUAL_PRICE  = 96;

export default function AccountPageClient() {
  const { data: session } = useSession();
  const searchParams       = useSearchParams();
  const jwt                = (session as { flaskJwt?: string })?.flaskJwt ?? "";

  // Pre-select interval from query param (set by PricingSection "Sign In to Upgrade")
  const defaultInterval = searchParams.get("interval") === "year" ? "year" : "month";

  const [status, setStatus]     = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [interval, setInterval] = useState<Interval>(defaultInterval);
  const [working, setWorking]   = useState(false);

  const justSubscribed = searchParams.get("subscribed") === "1";

  useEffect(() => {
    if (!jwt) return;
    getSubscriptionStatus(jwt)
      .then(setStatus)
      .catch(() => setError("Failed to load subscription status."))
      .finally(() => setLoading(false));
  }, [jwt]);

  async function handleUpgrade() {
    if (!jwt) return;
    setWorking(true);
    setError(null);
    try {
      const { url } = await createSubscriptionCheckout(jwt, interval);
      window.location.href = url;
    } catch (e: unknown) {
      if (e instanceof Error && e.message === "already_subscribed") {
        setError("You're already subscribed to Premium.");
      } else {
        setError("Could not start checkout. Please try again.");
      }
      setWorking(false);
    }
  }

  async function handleManage() {
    if (!jwt) return;
    setWorking(true);
    setError(null);
    try {
      const { url } = await createBillingPortal(jwt);
      window.location.href = url;
    } catch {
      setError("Could not open billing portal. Please try again.");
      setWorking(false);
    }
  }

  const role      = (session as { role?: string })?.role ?? "free";
  const isOwner   = (session as { isOwner?: boolean })?.isOwner ?? false;
  const isTrusted = (session as { isTrusted?: boolean })?.isTrusted ?? false;

  const tierCfg = isOwner
    ? { label: "Owner",   cls: "text-[var(--gold)] border-yellow-600 bg-yellow-900/30" }
    : isTrusted
    ? { label: "Trusted", cls: "text-blue-300 border-blue-700 bg-blue-900/30" }
    : role === "premium"
    ? { label: "Premium", cls: "text-purple-300 border-purple-700 bg-purple-900/30" }
    : { label: "Free",    cls: "text-emerald-300 border-emerald-700 bg-emerald-900/30" };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--gold)] border-t-transparent" />
      </div>
    );
  }

  const isPremium = status?.plan === "premium";
  const isFree    = !isPremium;

  const monthlyDisplay = `$${MONTHLY_PRICE} / month`;
  const annualDisplay  = `$${ANNUAL_PRICE} / year`;
  const annualSubLabel = `$${(ANNUAL_PRICE / 12).toFixed(0)}/mo · saves $${MONTHLY_PRICE * 12 - ANNUAL_PRICE}/yr`;

  return (
    <div className="max-w-xl mx-auto space-y-6 py-4 px-4">
      <h1 className="text-2xl font-bold text-[var(--gold)]">Account</h1>

      {/* Profile card */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--muted)]">Signed in as</span>
          <span className="text-sm text-[var(--text)] truncate max-w-[220px]">
            {session?.user?.email}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--muted)]">Plan</span>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${tierCfg.cls}`}>
            {tierCfg.label}
          </span>
        </div>
      </div>

      {/* Just-subscribed banner */}
      {justSubscribed && (
        <div className="rounded-xl border border-green-700 bg-green-900/20 px-4 py-3 text-sm text-green-300">
          Premium activated! Your plan may take a moment to reflect if you just subscribed.
        </div>
      )}

      {/* Owner / Trusted — no subscription UI needed */}
      {(isOwner || isTrusted) && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          {isOwner
            ? "As owner, you have full access to all features."
            : "Your Trusted access was granted by the owner."}
        </div>
      )}

      {/* Premium — manage subscription */}
      {!isOwner && !isTrusted && isPremium && (
        <div className="rounded-xl border border-[var(--gold)] bg-[var(--surface)] p-5 space-y-3">
          <p className="text-sm font-semibold text-[var(--gold)]">Premium Active</p>
          {status?.billing_interval && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--muted)]">Billing</span>
              <span className="capitalize">{status.billing_interval}ly</span>
            </div>
          )}
          {status?.expires_at && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--muted)]">
                {status.cancelled ? "Access until" : "Renews"}
              </span>
              <span>
                {new Date(status.expires_at).toLocaleDateString(undefined, {
                  year: "numeric", month: "long", day: "numeric",
                })}
              </span>
            </div>
          )}
          {status?.cancelled && (
            <p className="text-xs text-yellow-400">
              Subscription cancelled — access continues until the date above.
            </p>
          )}
          <button
            onClick={handleManage}
            disabled={working}
            className="w-full rounded-xl border border-[var(--gold)] py-2.5 text-sm font-semibold text-[var(--gold)] hover:bg-[var(--gold)]/10 disabled:opacity-50 transition-colors"
          >
            {working ? "Opening portal…" : "Manage / Cancel Subscription"}
          </button>
        </div>
      )}

      {/* Free — upgrade section */}
      {!isOwner && !isTrusted && isFree && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
          <p className="text-sm font-semibold">Upgrade to Premium</p>

          {/* Perks */}
          <ul className="text-sm text-[var(--muted)] space-y-1">
            {[
              "Track stats for up to 5 players",
              "ML predictive models",
              "200 Bolt AI queries / month",
              "Everything in Free",
            ].map((p) => (
              <li key={p} className="flex gap-2">
                <span className="text-green-500 shrink-0">✓</span>{p}
              </li>
            ))}
          </ul>

          {/* Interval toggle */}
          <div className="flex gap-3">
            {(["month", "year"] as Interval[]).map((i) => (
              <button
                key={i}
                onClick={() => setInterval(i)}
                className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${
                  interval === i
                    ? "border-[var(--gold)] bg-[var(--gold)] text-black"
                    : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]"
                }`}
              >
                {i === "month" ? "Monthly" : "Annual"}
                {i === "year" && interval !== "year" && (
                  <span className="ml-1 text-xs text-green-400">Save 20%</span>
                )}
              </button>
            ))}
          </div>

          {/* Price display */}
          <div className="text-center">
            <span className="text-2xl font-bold text-[var(--gold)]">
              {interval === "month" ? monthlyDisplay : annualDisplay}
            </span>
            {interval === "year" && (
              <div className="text-xs text-green-400 mt-0.5">{annualSubLabel}</div>
            )}
          </div>

          <button
            onClick={handleUpgrade}
            disabled={working}
            className="w-full rounded-xl bg-[var(--gold)] py-3 text-sm font-bold text-black hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {working ? "Redirecting to checkout…" : `Upgrade — ${interval === "month" ? monthlyDisplay : annualDisplay}`}
          </button>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-400 text-center">{error}</p>
      )}

      {/* Data + Danger zone links */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]">
        <a
          href="/data-export"
          className="flex items-center justify-between px-4 py-3 text-sm text-[var(--muted)] hover:text-[var(--text)] transition-colors"
        >
          <span>Export your data</span>
          <span className="text-[var(--muted)]">→</span>
        </a>
        <a
          href="/account/delete"
          className="flex items-center justify-between px-4 py-3 text-sm text-red-400 hover:text-red-300 transition-colors"
        >
          <span>Delete account</span>
          <span>→</span>
        </a>
      </div>
    </div>
  );
}
