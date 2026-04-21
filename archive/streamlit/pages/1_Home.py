import streamlit as st
from archive.utils.app_utils import YOUR_PRIVACY_POLICY_URL, YOUR_TERMS_OF_SERVICE_URL

# --- SEO: Inject meta tags, Open Graph, Twitter Card, JSON-LD into <head> ---
st.markdown("""
<script>
(function() {
    // ── Core meta tags ──────────────────────────────────────────────────────
    var metas = [
        // Indexing & description
        { name: "description",
          content: "Track, log, and analyze your video game stats across every game you play. View performance trends, KPI breakdowns, bar charts, and share highlights. Built by BOL." },
        { name: "keywords",
          content: "video game stats tracker, game statistics app, gaming performance tracker, track game stats, gaming session log, FPS stats tracker, Call of Duty stats tracker, esports stats tracker, game history tracker, multiplayer stats, gaming analytics, personal game statistics, game match logger, video game data tracker, gaming dashboard, game KPI tracker, gaming progress tracker, BOL game tracker, TheBOLGuide, game score tracker, COD stats, gaming leaderboard app" },
        { name: "author",        content: "The BOL Group LLC" },
        { name: "robots",        content: "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" },
        { name: "theme-color",   content: "#c8ac44" },
        { name: "application-name", content: "Video Game Stats Tracker" },
        { name: "category",      content: "Gaming, Esports, Sports, Productivity" },
        { name: "rating",        content: "general" },
        { name: "revisit-after", content: "7 days" },
        // Google site verification
        { name: "google-site-verification", content: "lPYdHOgd3-kVW7mLpGyL4c7RJuTq_BVM1wJS_6eqnc8" },

        // ── Open Graph (Facebook / LinkedIn / Discord) ─────────────────────
        { property: "og:type",        content: "website" },
        { property: "og:title",       content: "Video Game Stats Tracker — Log & Analyze Your Gaming Performance" },
        { property: "og:description", content: "Log every match, track performance trends, and visualize your gaming stats with bar charts and KPIs. Free web app built by BOL." },
        { property: "og:site_name",   content: "Video Game Stats Tracker" },
        { property: "og:locale",      content: "en_US" },

        // ── Twitter / X Card ──────────────────────────────────────────────
        { name: "twitter:card",        content: "summary_large_image" },
        { name: "twitter:title",       content: "Video Game Stats Tracker" },
        { name: "twitter:description", content: "Log your game sessions, track KPIs, and share your stats. Built for gamers by BOL." },
        { name: "twitter:site",        content: "@TheBOLGuide" },
        { name: "twitter:creator",     content: "@TheBOLGuide" },
    ];

    metas.forEach(function(attrs) {
        var key = attrs.name !== undefined ? "name" : "property";
        var val = attrs[key];
        var el = document.querySelector("meta[" + key + '="' + val + '"]');
        if (!el) { el = document.createElement("meta"); document.head.appendChild(el); }
        Object.keys(attrs).forEach(function(k) { el.setAttribute(k, attrs[k]); });
    });

    // ── JSON-LD Structured Data (WebApplication) ───────────────────────────
    if (!document.querySelector('script[data-bol-ld]')) {
        var ld = document.createElement("script");
        ld.type = "application/ld+json";
        ld.setAttribute("data-bol-ld", "1");
        ld.text = JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "Video Game Stats Tracker",
            "url": window.location.origin,
            "description": "A free web application to log, track, and analyze personal video game statistics across multiple games and sessions.",
            "applicationCategory": "GameApplication",
            "operatingSystem": "Web Browser",
            "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
            "author": {
                "@type": "Person",
                "name": "BOL",
                "url": "https://youtube.com/@TheBOLGuide",
                "sameAs": ["https://youtube.com/@TheBOLGuide"]
            },
            "featureList": [
                "Log video game match statistics",
                "Track performance trends over multiple sessions",
                "Bar chart and KPI stat visualizations",
                "Multi-game support with genre and subgenre classification",
                "Instagram and Twitter/X stat card sharing",
                "Google account authentication",
                "Guest mode for public stat viewing",
                "Historical line chart comparisons"
            ],
            "keywords": "video game stats, gaming tracker, game statistics, esports analytics, COD stats, FPS tracker, gaming dashboard",
            "inLanguage": "en-US",
            "isAccessibleForFree": true
        });
        document.head.appendChild(ld);
    }
})();
</script>
""", unsafe_allow_html=True)

st.write(
    """
    Welcome to the Video Game Stats Tracker!

    This application allows you to log, track, and manage your personal video game statistics.
    
    ### Features:
    - **Admin Access:** Log in with a trusted Google account to unlock full data entry capabilities.
    - **Enter Stats:** Add new players, games (with genres), and detailed match stats.
    - **Edit Data:** Correct typos or update details for players, games, or individual stat entries.
    - **Delete Data:** Safely remove players, games (if empty), or specific stat records.
    - **Guest Mode:** Logged-in guests can view their own stats. Anonymous guests can explore the UI.
    
    Please use the **sidebar** to log in or navigate.
    """
)

# Footer
st.markdown("---")
st.markdown("Made with💡by [BOL](https://youtube.com/@TheBOLGuide)")
st.markdown(f"""
[Privacy Policy]({YOUR_PRIVACY_POLICY_URL}) | [Terms of Service]({YOUR_TERMS_OF_SERVICE_URL})
""")