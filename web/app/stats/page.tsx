// Stats page — server component shell that gates access by auth role.
// The heavy lifting (form state, API calls) is in client components below.

import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import StatsPageClient from "@/components/StatsPageClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Stats Form | 🎮 Game Tracker",
};

export default async function StatsPage() {
  const session = await getServerSession(authOptions);

  // Not signed in at all — redirect to home
  if (!session) {
    redirect("/?auth=required");
  }

  return <StatsPageClient />;
}
