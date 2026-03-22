"use client";
// SessionProvider must be in a client component.
// This thin wrapper lets us use getServerSession in layout.tsx (server)
// while still giving every client component access to useSession().

import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";

export default function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session: Session | null;
}) {
  return <SessionProvider session={session}>{children}</SessionProvider>;
}
