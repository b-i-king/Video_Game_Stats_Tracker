"use client";

import { useSession } from "next-auth/react";
import LeaderboardTab from "./LeaderboardTab";

export default function LeaderboardPageClient() {
  const { data: session } = useSession();
  const jwt = session?.flaskJwt ?? "";

  if (!session) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
      <h1 className="text-2xl font-bold text-[var(--gold)] text-center">
        🏆 Leaderboard
      </h1>
      <LeaderboardTab jwt={jwt} />
    </div>
  );
}
