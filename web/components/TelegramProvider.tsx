"use client";

/**
 * TelegramProvider — mounts in every page via layout.tsx.
 * Renders nothing visible. Does three things on load inside a Telegram WebView:
 *
 * 1. Calls Telegram.WebApp.ready() — tells Telegram the app has loaded
 *    (removes the loading spinner in the WebView chrome).
 * 2. Calls Telegram.WebApp.expand() — fills the full screen height.
 * 3. If the user is not yet signed in, exchanges initData for a NextAuth
 *    session via the "telegram" CredentialsProvider (fires once per session).
 */

import { useEffect, useRef } from "react";
import { useSession, signIn } from "next-auth/react";

export default function TelegramProvider() {
  const { data: session, status } = useSession();
  const attempted = useRef(false);

  useEffect(() => {
    const twa = (window as any).Telegram?.WebApp;
    if (!twa) return;

    // Step 1 & 2 — always fire inside Telegram
    twa.ready();
    twa.expand();

    // Step 3 — sign in via Telegram identity if not already authenticated
    if (attempted.current) return;
    if (status === "loading") return;
    if (session) return;

    const initData: string = twa.initData;
    if (!initData) return;

    attempted.current = true;
    signIn("telegram", { initData, redirect: false }).catch(() => {});
  }, [session, status]);

  return null;
}
