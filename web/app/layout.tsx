import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Fira_Code } from "next/font/google";
import { getServerSession } from "next-auth";
import { getLocale, getMessages } from "next-intl/server";
import { NextIntlClientProvider } from "next-intl";
import { authOptions } from "@/lib/auth";
import { isRTL } from "@/i18n/request";
import Providers from "@/components/Providers";
import ThemeProvider from "@/components/ThemeProvider";
import Navbar from "@/components/Navbar";
import SocialLinks from "@/components/SocialLinks";
import RenderWarmup from "@/components/RenderWarmup";
import MaintenanceBanner from "@/components/MaintenanceBanner";

// Edge Config is only available on Vercel — falls back to env var for local dev.
// Layout already renders dynamically (getServerSession reads cookies), so this
// fires on every request with no extra cache configuration needed.
async function getMaintenanceMsg(): Promise<string> {
  try {
    const { get } = await import("@vercel/edge-config");
    return (await get<string>("maintenanceMsg")) ?? "";
  } catch {
    // Local dev or EDGE_CONFIG env var not set — fall back to env var
    return process.env.NEXT_PUBLIC_MAINTENANCE_MSG ?? "";
  }
}

// Fira Code — loaded via Next.js font optimization (no layout shift, cached by CDN)
const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: "--font-fira-code",
  display: "swap",
});

const SITE_NAME = "Video Game Stats Tracker";
const DESCRIPTION =
  "Track, log, and analyze your video game stats across every game you play. View performance trends, KPI breakdowns, bar charts, and share highlights. Built by BOL.";

export const metadata: Metadata = {
  // Title template — individual pages set their own segment
  title: {
    default: SITE_NAME,
    template: `%s | ${SITE_NAME}`,
  },
  description: DESCRIPTION,
  keywords: [
    "video game stats tracker",
    "game statistics app",
    "gaming performance tracker",
    "track game stats",
    "gaming session log",
    "FPS stats tracker",
    "Call of Duty stats tracker",
    "esports stats tracker",
    "game history tracker",
    "multiplayer stats",
    "gaming analytics",
    "personal game statistics",
    "game match logger",
    "video game data tracker",
    "gaming dashboard",
    "game KPI tracker",
    "gaming progress tracker",
    "BOL game tracker",
    "TheBOLGuide",
  ],
  authors: [{ name: "The BOL Group LLC" }],
  applicationName: SITE_NAME,
  category: "Gaming, Esports, Sports, Productivity",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
  verification: {
    google: "lPYdHOgd3-kVW7mLpGyL4c7RJuTq_BVM1wJS_6eqnc8",
  },
  openGraph: {
    title: `${SITE_NAME} — Log & Analyze Your Gaming Performance`,
    description:
      "Log every match, track performance trends, and visualize your gaming stats with bar charts and KPIs. Free web app built by BOL.",
    siteName: SITE_NAME,
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description:
      "Log your game sessions, track KPIs, and share your stats. Built for gamers by BOL.",
    site: "@TheBOLGuide",
    creator: "@TheBOLGuide",
  },
};

export const viewport: Viewport = {
  themeColor: "#c8ac44",
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: SITE_NAME,
  description:
    "A free web application to log, track, and analyze personal video game statistics across multiple games and sessions.",
  applicationCategory: "GameApplication",
  operatingSystem: "Web Browser",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  author: {
    "@type": "Person",
    name: "BOL",
    url: "https://youtube.com/@TheBOLGuide",
    sameAs: ["https://youtube.com/@TheBOLGuide"],
  },
  featureList: [
    "Log video game match statistics",
    "Track performance trends over multiple sessions",
    "Bar chart and KPI stat visualizations",
    "Multi-game support with genre and subgenre classification",
    "Instagram and Twitter/X stat card sharing",
    "Google account authentication",
    "Guest mode for public stat viewing",
    "Historical line chart comparisons",
  ],
  keywords:
    "video game stats, gaming tracker, game statistics, esports analytics, COD stats, FPS tracker, gaming dashboard",
  inLanguage: "en-US",
  isAccessibleForFree: true,
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [session, maintenanceMsg, locale, messages] = await Promise.all([
    getServerSession(authOptions),
    getMaintenanceMsg(),
    getLocale(),
    getMessages(),
  ]);

  return (
    <html lang={locale} dir={isRTL(locale) ? "rtl" : "ltr"} className={firaCode.variable}>
      <head>
        {/* Anti-flash: read theme from localStorage before React hydrates */}
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var t=localStorage.getItem('theme')||(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');document.documentElement.setAttribute('data-theme',t);}catch(e){}})();` }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-screen flex flex-col font-mono">
        <Providers session={session}>
          <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider>
          <RenderWarmup />
          <MaintenanceBanner msg={maintenanceMsg} />
          <Navbar />

          <main className="flex-1 px-4 py-6">
            {children}
          </main>

          <footer className="border-t border-[var(--border)] bg-[var(--surface)] pt-3 pb-4">
            {/* Social media icons */}
            <SocialLinks />

            {/* Credit line */}
            <p className="text-center text-xs text-[var(--muted)]">
              Made with 💡 by{" "}
              <a
                href="https://youtube.com/@TheBOLGuide"
                className="text-[var(--gold)] hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                BOL
              </a>
            </p>
          </footer>
          </ThemeProvider>
          </NextIntlClientProvider>
        </Providers>
      </body>
    </html>
  );
}
