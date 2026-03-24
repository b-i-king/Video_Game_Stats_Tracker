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
      // Decode Flask JWT expiry without a library (base64 payload, field: exp)
      const flaskJwtExpired = (): boolean => {
        if (!token.flaskJwt) return true;
        try {
          const payload = JSON.parse(
            Buffer.from((token.flaskJwt as string).split(".")[1], "base64").toString()
          );
          // Refresh if expired or expiring within the next 5 minutes
          return payload.exp < Math.floor(Date.now() / 1000) + 300;
        } catch {
          return true;
        }
      };

      // Exchange Google identity for a Flask JWT on first sign-in OR when expired
      if ((account && user) || flaskJwtExpired()) {
        const email = user?.email ?? token.email;
        try {
          const res = await fetch(
            `${process.env.FLASK_API_URL}/api/login`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-API-KEY": process.env.FLASK_API_KEY!,
              },
              body: JSON.stringify({ email }),
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
