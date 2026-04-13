"use client";

import { useState } from "react";
import Link from "next/link";
import { signIn } from "next-auth/react";

const FREE_PERKS = [
  "Track stats for up to 2 players",
  "Auto-generated chart graphics",
  "Full session history",
  "Leaderboard opt-in",
  "Developer integrations",
  "20 Bolt AI queries / month",
];

const PREMIUM_PERKS = [
  "Everything in Free",
  "Track stats for up to 5 players",
  "ML predictive models",
  "200 Bolt AI queries / month",
];

const MONTHLY_PRICE = 10;
const ANNUAL_PRICE  = 96; // $8/mo billed annually — saves $24/yr

export default function PricingSection() {
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");

  const priceLabel = billing === "monthly"
    ? `$${MONTHLY_PRICE} / month`
    : `$${ANNUAL_PRICE} / year`;
  const subLabel   = billing === "annual"
    ? `$${(ANNUAL_PRICE / 12).toFixed(0)}/mo · saves $${MONTHLY_PRICE * 12 - ANNUAL_PRICE}/yr`
    : null;

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
      <p className="font-semibold text-center">Choose your plan</p>

      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3 text-sm">
        <button
          onClick={() => setBilling("monthly")}
          className={`px-3 py-1 rounded-full transition-colors ${
            billing === "monthly"
              ? "bg-[var(--gold)] text-black font-semibold"
              : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]"
          }`}
        >
          Monthly
        </button>
        <button
          onClick={() => setBilling("annual")}
          className={`px-3 py-1 rounded-full transition-colors ${
            billing === "annual"
              ? "bg-[var(--gold)] text-black font-semibold"
              : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]"
          }`}
        >
          Annual
          {billing !== "annual" && (
            <span className="ml-1.5 text-xs text-green-400">Save 20%</span>
          )}
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 text-sm items-stretch">
        {/* Free */}
        <div className="flex flex-col p-4 rounded-lg border border-[var(--border)]">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-base">Free</span>
            <span className="text-xs px-2 py-0.5 rounded-full border border-[var(--border)] text-[var(--muted)]">
              Sign in with Google
            </span>
          </div>
          <div className="text-2xl font-bold mb-3">$0</div>
          <ul className="space-y-1.5 text-[var(--muted)] flex-1">
            {FREE_PERKS.map((p) => (
              <li key={p} className="flex gap-2">
                <span className="text-green-500 shrink-0">✓</span>{p}
              </li>
            ))}
            <li className="flex gap-2">
              <span className="text-[var(--muted)] shrink-0">✗</span>ML predictive models
            </li>
          </ul>
          <Link
            href="/auth/signin"
            className="mt-4 block text-center w-full py-2 rounded border border-[var(--border)] hover:border-[var(--gold)] hover:text-[var(--gold)] transition-colors font-medium"
          >
            Get Started Free
          </Link>
        </div>

        {/* Premium */}
        <div className="flex flex-col p-4 rounded-lg border border-[var(--gold)] relative">
          <div className="absolute -top-3 left-1/2 -translate-x-1/2">
            <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[var(--gold)] text-black whitespace-nowrap">
              Best Plan
            </span>
          </div>
          <div className="flex items-center justify-between pt-1 mb-1">
            <span className="font-semibold text-base text-[var(--gold)]">Premium</span>
          </div>
          <div className="mb-3">
            <span className="text-2xl font-bold text-[var(--gold)]">{priceLabel}</span>
            {subLabel && (
              <div className="text-xs text-green-400 mt-0.5">{subLabel}</div>
            )}
          </div>
          <ul className="space-y-1.5 text-[var(--muted)] flex-1">
            {PREMIUM_PERKS.map((p) => (
              <li key={p} className="flex gap-2">
                <span className="text-green-500 shrink-0">✓</span>{p}
              </li>
            ))}
          </ul>
          <button
            onClick={() =>
              signIn("google", {
                callbackUrl: `/account?interval=${billing === "monthly" ? "month" : "year"}`,
              })
            }
            className="mt-4 w-full py-2 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
          >
            Sign In to Upgrade
          </button>
        </div>
      </div>
    </section>
  );
}
