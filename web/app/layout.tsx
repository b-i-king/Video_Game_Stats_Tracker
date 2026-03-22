// Root layout — wraps every page with the session provider and navbar.
// SessionProvider lets any client component call useSession().

import "./globals.css";
import type { Metadata } from "next";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import Providers from "@/components/Providers";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "🎮 Video Game Stats Tracker",
  description:
    "Track your video game stats, generate charts, and auto-post to social media.",
  openGraph: {
    title: "Video Game Stats Tracker",
    description: "Track your video game stats and share on social media.",
    type: "website",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        {/* Providers wraps children in the NextAuth SessionProvider */}
        <Providers session={session}>
          <Navbar />
          <main className="flex-1 container mx-auto px-4 py-6 max-w-5xl">
            {children}
          </main>
          <footer className="text-center text-sm py-4 text-[var(--muted)] border-t border-[var(--border)]">
            Made with 💡 by{" "}
            <a
              href="https://youtube.com/@TheBOLGuide"
              className="text-[var(--gold)] hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              BOL
            </a>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
