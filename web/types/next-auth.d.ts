// Extend the built-in NextAuth types so TypeScript knows about the extra
// fields we store in the session (Flask JWT, role, etc.)

import NextAuth, { DefaultSession } from "next-auth";
import { JWT as DefaultJWT } from "next-auth/jwt";

declare module "next-auth" {
  interface Session extends DefaultSession {
    /** JWT returned by the Flask /api/login endpoint */
    flaskJwt?: string;
    /** "trusted" | "guest" */
    role?: string;
    isTrusted?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    flaskJwt?: string;
    role?: string;
    isTrusted?: boolean;
  }
}
