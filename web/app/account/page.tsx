import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import AccountPageClient from "@/components/AccountPageClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Account",
};

export default async function AccountPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/?auth=required");
  }

  return (
    <Suspense>
      <AccountPageClient />
    </Suspense>
  );
}
