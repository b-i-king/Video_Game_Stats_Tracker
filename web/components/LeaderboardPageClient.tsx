"use client";

import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import LeaderboardTab from "./LeaderboardTab";

export default function LeaderboardPageClient() {
  const { data: session } = useSession();
  const jwt = session?.flaskJwt ?? "";
  const t = useTranslations("leaderboard");

  if (!session) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
      <h1 className="text-2xl font-bold text-[var(--gold)] text-center">
        🏆 {t("pageTitle")}
      </h1>
      <LeaderboardTab jwt={jwt} />
    </div>
  );
}
