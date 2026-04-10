import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import DashboardPageClient from "@/components/DashboardPageClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "📺 Dashboard",
};

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/?auth=required");
  }

  return <DashboardPageClient />;
}
