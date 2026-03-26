// Integrations page — gated to signed-in users.

import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import IntegrationsTab from "@/components/IntegrationsTab";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "🔗 Integrations",
};

export default async function IntegrationsPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/?auth=required");
  }

  return <IntegrationsTab />;
}
