// This is the NextAuth catch-all API route.
// It handles all OAuth callbacks automatically.
// You don't need to edit this file.

import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth";

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
