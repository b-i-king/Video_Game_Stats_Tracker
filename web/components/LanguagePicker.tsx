"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
  { code: "hi", label: "हिन्दी" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "ar", label: "العربية" },
  { code: "bn", label: "বাংলা" },
  { code: "pt", label: "Português" },
  { code: "ru", label: "Русский" },
  { code: "ur", label: "اردو" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "de", label: "Deutsch" },
] as const;

interface Props {
  onSelect?: () => void;
}

export default function LanguagePicker({ onSelect }: Props) {
  const router = useRouter();
  const locale = useLocale();

  function setLocale(code: string) {
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; SameSite=Lax`;
    onSelect?.();
    router.refresh();
  }

  return (
    <div className="px-3 py-2 flex items-center gap-2">
      <span className="text-sm">🌐</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value)}
        className="flex-1 text-sm bg-[var(--surface)] text-[var(--text)] border border-[var(--border)] rounded px-2 py-1 cursor-pointer hover:border-[var(--gold)] focus:outline-none focus:border-[var(--gold)] transition-colors"
        aria-label="Select language"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </div>
  );
}
