import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

// Supported locales — add new ones here as messages/<code>.json files are added.
export const SUPPORTED_LOCALES = [
  "en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur", "ja", "ko", "de",
] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

// RTL languages — layout.tsx reads this to set dir="rtl" on <html>
export const RTL_LOCALES: Locale[] = ["ar", "ur"];

export function isRTL(locale: string): boolean {
  return RTL_LOCALES.includes(locale as Locale);
}

function resolveLocale(cookieLocale: string | undefined): Locale {
  if (cookieLocale && SUPPORTED_LOCALES.includes(cookieLocale as Locale)) {
    return cookieLocale as Locale;
  }
  return "en";
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const locale = resolveLocale(cookieStore.get("NEXT_LOCALE")?.value);

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
