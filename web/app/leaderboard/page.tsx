import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import LeaderboardPageClient from "@/components/LeaderboardPageClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "🏆 Leaderboard",
};

export default async function LeaderboardPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/?auth=required");
  }

  return <LeaderboardPageClient />;
}
