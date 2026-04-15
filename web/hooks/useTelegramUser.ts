"use client";

import { useState, useEffect } from "react";

/**
 * Detects whether the app is running inside a Telegram Mini App WebView.
 * Returns isTelegram: true only on the client after hydration.
 */
export function useTelegramUser(): { isTelegram: boolean } {
  const [isTelegram, setIsTelegram] = useState(false);

  useEffect(() => {
    setIsTelegram(
      typeof window !== "undefined" &&
        Boolean((window as TelegramWindow).Telegram?.WebApp?.initData)
    );
  }, []);

  return { isTelegram };
}

// Minimal Telegram WebApp type — full SDK types available via @types/telegram-web-app if needed
interface TelegramWindow extends Window {
  Telegram?: {
    WebApp?: {
      initData: string;
      ready: () => void;
      expand: () => void;
      openInvoice: (url: string, callback: (status: string) => void) => void;
      colorScheme: "light" | "dark";
      themeParams: Record<string, string>;
    };
  };
}
