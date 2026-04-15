"use client";

/**
 * ReferralTracker — renders nothing, runs two side effects:
 *
 * 1. On any page load: if ?ref=CODE is in the URL, store it in a
 *    REFERRAL_CODE cookie (30-day attribution window).
 *
 * 2. Once signed in: if REFERRAL_CODE cookie exists, call
 *    POST /referral/record to link this user to the referrer.
 *    Clears the cookie afterwards so it only fires once.
 */

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { recordReferral } from "@/lib/api";

export default function ReferralTracker() {
  const { data: session } = useSession();
  const searchParams = useSearchParams();
  const jwt = (session as { flaskJwt?: string })?.flaskJwt ?? "";

  // Step 1 — capture ?ref= into a cookie
  useEffect(() => {
    const ref = searchParams.get("ref");
    if (ref) {
      const maxAge = 60 * 60 * 24 * 30; // 30 days
      document.cookie = `REFERRAL_CODE=${encodeURIComponent(ref)}; path=/; max-age=${maxAge}; SameSite=Lax`;
    }
  }, [searchParams]);

  // Step 2 — record the referral once the user is signed in
  useEffect(() => {
    if (!jwt) return;

    const match = document.cookie.match(/(?:^|;\s*)REFERRAL_CODE=([^;]+)/);
    if (!match) return;

    const code = decodeURIComponent(match[1]);
    if (!code) return;

    // Clear the cookie immediately to prevent duplicate calls
    document.cookie = "REFERRAL_CODE=; path=/; max-age=0; SameSite=Lax";

    recordReferral(jwt, code).catch(() => {/* non-fatal */});
  }, [jwt]);

  return null;
}
