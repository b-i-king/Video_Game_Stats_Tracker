import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Fira_Code } from "next/font/google";
import Script from "next/script";
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
import ReferralTracker from "@/components/ReferralTracker";
import TelegramProvider from "@/components/TelegramProvider";

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

// Production URL — set NEXT_PUBLIC_SITE_URL in Vercel environment variables.
// Temporary fallback: your Vercel preview URL. Replace with a custom domain when purchased.
const SITE_URL  = process.env.NEXT_PUBLIC_SITE_URL ?? "https://vgst.app";
const SITE_NAME = "Video Game Stats Tracker";
const SITE_ABBR = "VGST";

// Shown in SERPs — 150–160 chars, front-loads primary keyword, highlights key differentiator.
const DESCRIPTION =
  "VGST — Video Game Stats Tracker for every game. No app downloads. Log matches, track KPIs, view performance trends, and get AI win-probability predictions across all your games in one free web app.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),

  // Title template — individual pages export their own segment via metadata.title
  title: {
    default: `${SITE_ABBR} — ${SITE_NAME} | Track Every Game, No App Required`,
    template: `%s | ${SITE_ABBR} — ${SITE_NAME}`,
  },
  description: DESCRIPTION,
  icons: {
    icon:     [{ url: "/favicon.ico", sizes: "any" }, { url: "/icon.png", type: "image/png", sizes: "192x192" }],
    shortcut: "/favicon.ico",
    apple:    "/apple-touch-icon.png",
  },
  keywords: [
    // ── Brand ────────────────────────────────────────────────────────────────
    "VGST",
    "vgst.app",
    "vgst game tracker",
    "vgst gaming stats",
    // ── Primary target ────────────────────────────────────────────────────────
    "video game stats tracker",
    "game stats tracker",
    "gaming stats tracker",
    "track video game stats",
    "game statistics tracker",
    // ── Differentiator: universal / no download ───────────────────────────────
    "universal game stats tracker",
    "track all games in one place",
    "no download game tracker",
    "web based game tracker",
    "cross game stats tracker",
    "all games one stats app",
    "game tracker without app",
    "browser game stats tracker",
    // ── Performance / analytics ───────────────────────────────────────────────
    "gaming performance tracker",
    "gaming analytics dashboard",
    "game KPI tracker",
    "gaming session logger",
    "esports stats tracker",
    "esports analytics",
    "gaming progress tracker",
    "game match history tracker",
    "personal gaming analytics",
    "video game performance analysis",
    "game win rate tracker",
    "AI win probability gaming",
    // ── Game-specific (high search volume) ───────────────────────────────────
    "Call of Duty stats tracker",
    "FPS stats tracker",
    "multiplayer game stats",
    "shooter game stats tracker",
    "ranked game tracker",
    // ── Future API integrations (index now, rank later) ───────────────────────
    "Steam stats tracker",
    "Riot games stats tracker",
    "Valorant stats tracker",
    "game tracker Steam integration",
    // ── Ecosystem / sharing ───────────────────────────────────────────────────
    "gaming dashboard",
    "game history log",
    "share gaming stats",
    "gaming stat card",
    "gaming highlights tracker",
    // ── Brand ────────────────────────────────────────────────────────────────
    "BOL game tracker",
    "TheBOLGuide stats",
    "The BOL Group gaming",
  ],
  authors:         [{ name: "The BOL Group LLC", url: SITE_URL }],
  applicationName: SITE_NAME,
  category:        "Gaming, Esports, Sports, Productivity",
  robots: {
    index:  true,
    follow: true,
    googleBot: {
      index:               true,
      follow:              true,
      "max-snippet":       -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
  alternates: {
    canonical: SITE_URL,
  },
  verification: {
    google: "lPYdHOgd3-kVW7mLpGyL4c7RJuTq_BVM1wJS_6eqnc8",
  },
  openGraph: {
    title:       `${SITE_NAME} — Track Every Game, No App Required`,
    description: "One free web app to log, track, and analyze stats for every game you play. No downloads. AI win-probability predictions. Share stat cards on Instagram & X.",
    siteName:    SITE_NAME,
    url:         SITE_URL,
    locale:      "en_US",
    type:        "website",
    // Create /public/og-image.png (1200×630) — shown on Google, Discord, Twitter link previews.
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: `${SITE_NAME} — Dashboard preview` }],
  },
  twitter: {
    card:        "summary_large_image",
    title:       `${SITE_NAME} — Track Every Game, No App Required`,
    description: "Log sessions, track KPIs, and get AI win-probability predictions for every game — all in one free web app. No downloads needed.",
    site:        "@TheBOLGuide",
    creator:     "@TheBOLGuide",
    images:      ["/og-image.png"],
  },
};

export const viewport: Viewport = {
  themeColor:    "#c8ac44",
  width:         "device-width",
  initialScale:  1,
  minimumScale:  1,
};

// WebSite structured data — establishes VGST as an alternate name so Google
// associates the abbreviation with this site, not the Vanguard ETF ticker.
const jsonLdSite = {
  "@context":     "https://schema.org",
  "@type":        "WebSite",
  name:           SITE_NAME,
  alternateName:  [SITE_ABBR, "vgst.app", "BOL Game Tracker", "Game Stats Tracker", "Game Tracker", "Tracker Network", "Play Trackter", "Game Stats Log", "Universal Game Tracker", "No Download Game Tracker"],
  url:            SITE_URL,
  description:    DESCRIPTION,
  potentialAction: {
    "@type":       "SearchAction",
    target:        `${SITE_URL}/stats?q={search_term_string}`,
    "query-input": "required name=search_term_string",
  },
};

// WebApplication structured data — powers Google rich results / app cards.
const jsonLdApp = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name:                SITE_NAME,
  url:                 SITE_URL,
  description:         "A free web application to log, track, and analyze personal video game statistics across every game — no app downloads required.",
  applicationCategory: "GameApplication",
  applicationSubCategory: "Sports & Esports Analytics",
  operatingSystem:     "Web Browser",
  browserRequirements: "Requires JavaScript. Works in Chrome, Firefox, Safari, Edge.",
  inLanguage:          "en-US",
  isAccessibleForFree: true,
  offers: [
    { "@type": "Offer", price: "0",   priceCurrency: "USD", name: "Free" },
    { "@type": "Offer", price: "10", priceCurrency: "USD", name: "Premium", billingIncrement: "month" },
  ],
  author: {
    "@type": "Organization",
    name:    "The BOL Group LLC",
    url:     SITE_URL,
    sameAs:  [
      "https://youtube.com/@TheBOLGuide",
      "https://twitter.com/TheBOLGuide",
    ],
  },
  featureList: [
    "Log video game match statistics for any game",
    "Universal cross-game tracking — no per-game app required",
    "AI win-probability predictions using logistic regression",
    "KPI and bar chart stat visualizations",
    "Session heatmap and streak tracking",
    "Multi-game support with genre and subgenre classification",
    "Leaderboards across public users",
    "Instagram and Twitter/X stat card image sharing",
    "Telegram Mini App and channel broadcast integration",
    "Steam game library integration (coming soon)",
    "Riot Games / Valorant API integration (coming soon)",
    "IGDB game database integration (coming soon)",
    "Achievement and gamification system (coming soon)",
    "K-Means clustering performance insights (coming soon)",
  ],
  keywords: "video game stats tracker, universal game tracker, no download game tracker, gaming analytics, esports stats, AI win prediction, COD stats, FPS tracker, Steam stats, Valorant stats",
  potentialAction: {
    "@type":       "SearchAction",
    target:        `${SITE_URL}/stats?q={search_term_string}`,
    "query-input": "required name=search_term_string",
  },
};

// FAQ structured data — targets featured snippet / People Also Ask boxes on Google.
const jsonLdFaq = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "What is a video game stats tracker?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "A video game stats tracker is a web app or tool that lets you log, store, and analyze your in-game performance data — things like kills, deaths, win rate, and KPIs — across multiple sessions and games. Video Game Stats Tracker by BOL tracks all your games in one place without requiring any app download.",
      },
    },
    {
      "@type": "Question",
      name: "Can I track stats for every game in one place?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Video Game Stats Tracker is a universal platform — you add any game manually or via API integrations (Steam and Riot Games coming soon) and log stats for all of them from a single dashboard. No separate app download is needed for each game.",
      },
    },
    {
      "@type": "Question",
      name: "Is Video Game Stats Tracker free?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes, there is a free tier with full stat logging and analytics. A Premium plan ($4.99/month) unlocks advanced features including AI win-probability predictions, data export, and leaderboard access.",
      },
    },
    {
      "@type": "Question",
      name: "Do I need to download an app to track my gaming stats?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. Video Game Stats Tracker runs entirely in your web browser. There is nothing to install — just sign in with Google and start logging your sessions.",
      },
    },
    {
      "@type": "Question",
      name: "How does AI win probability prediction work?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "After you log enough sessions with win/loss results, the app trains a logistic regression model on your personal stats. It then computes a win probability percentage for each new session based on your historical performance — entirely client-side with no extra API calls.",
      },
    },
    {
      "@type": "Question",
      name: "Will Steam and Riot Games stats be supported?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Steam API integration and Riot Games (Valorant, League of Legends) API integration are on the roadmap. Once live, your stats will import automatically without manual logging.",
      },
    },
  ],
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
        {/* Telegram Mini App SDK — no-op outside of Telegram WebView */}
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdSite) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdApp) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdFaq) }}
        />
      </head>
      <body className="min-h-screen flex flex-col font-mono">
        <Providers session={session}>
          <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider>
          <TelegramProvider />
          <ReferralTracker />
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
