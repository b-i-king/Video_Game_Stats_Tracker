"use client";

import { useState } from "react";

/**
 * Detects whether the app is running inside a Telegram Mini App WebView.
 * Lazy useState initializer runs only on the client — typeof window guard
 * makes it SSR-safe without needing an effect.
 */
export function useTelegramUser(): { isTelegram: boolean } {
  const [isTelegram] = useState(
    () =>
      typeof window !== "undefined" &&
      Boolean((window as TelegramWindow).Telegram?.WebApp?.initData),
  );

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
