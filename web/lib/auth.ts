// NextAuth configuration
// Flow: Google Sign-In → NextAuth jwt callback calls Flask /api/login → stores Flask JWT in session
// The Flask JWT is then used for all API calls that need authentication.

import type { AuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

export const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],

  // ── JWT callback: runs server-side when a token is created/refreshed ───────
  // On first sign-in (account is defined), call Flask to get a JWT.
  callbacks: {
    async jwt({ token, account, user }) {
      if (account && user) {
        // First sign-in — exchange Google identity for a Flask JWT
        try {
          const res = await fetch(
            `${process.env.FLASK_API_URL}/api/login`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-API-KEY": process.env.FLASK_API_KEY!,
              },
              body: JSON.stringify({ email: user.email }),
            }
          );

          if (res.ok) {
            const data = await res.json();
            token.flaskJwt = data.token ?? undefined;
            token.isTrusted = data.is_trusted ?? false;
            token.role = data.is_trusted ? "trusted" : "guest";
          } else {
            // Flask login failed — treat as a registered guest with no JWT
            token.role = "guest";
            token.isTrusted = false;
          }
        } catch {
          token.role = "guest";
          token.isTrusted = false;
        }
      }
      return token;
    },

    // ── Session callback: exposes fields to the client ──────────────────────
    async session({ session, token }) {
      session.flaskJwt = token.flaskJwt;
      session.role = token.role;
      session.isTrusted = token.isTrusted;
      return session;
    },
  },

  pages: {
    // Custom sign-in page (optional — remove to use NextAuth's built-in page)
    // signIn: '/auth/signin',
  },
};
