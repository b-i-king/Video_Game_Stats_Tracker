// Server component — uses native <details>/<summary> so no JS is needed,
// content is fully crawlable by Google, and satisfies the FAQPage schema
// visibility requirement (questions must be readable in the rendered HTML).

const faqs = [
  {
    q: "What is a video game stats tracker?",
    a: "A video game stats tracker is a web app that lets you log, store, and analyze your in-game performance data — kills, deaths, win rate, KPIs — across multiple sessions and games. VGST tracks all your games in one place without requiring any app download.",
  },
  {
    q: "Can I track stats for every game in one place?",
    a: "Yes. VGST is a universal platform — add any game manually or via API integrations (Steam and Riot Games coming soon) and log stats for all of them from a single dashboard. No separate app download needed for each game.",
  },
  {
    q: "Is Video Game Stats Tracker free?",
    a: "Yes, there is a free tier with full stat logging and analytics. A Premium plan unlocks advanced features including AI win-probability predictions, data export, and leaderboard access.",
  },
  {
    q: "Do I need to download an app to track my gaming stats?",
    a: "No. VGST runs entirely in your web browser. There is nothing to install — just sign in with Google and start logging your sessions.",
  },
  {
    q: "How does AI win probability prediction work?",
    a: "After you log enough sessions with win/loss results, the app trains a logistic regression model on your personal stats. It then computes a win probability percentage for each new session based on your historical performance.",
  },
  {
    q: "Will Steam and Riot Games stats be supported?",
    a: "Yes. Steam API integration and Riot Games (Valorant, League of Legends) API integration are on the roadmap. Once live, your stats will import automatically without manual logging.",
  },
];

export default function FaqSection() {
  return (
    <section id="faq" className="space-y-3">
      <h2 className="text-xl font-semibold text-[var(--gold)]">
        Frequently Asked Questions
      </h2>
      <div className="space-y-2">
        {faqs.map(({ q, a }) => (
          <details
            key={q}
            className="group rounded-lg border border-[var(--border)] bg-[var(--surface)]"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 font-medium hover:text-[var(--gold)] transition-colors">
              {q}
              <span className="ml-4 shrink-0 text-[var(--muted)] transition-transform group-open:rotate-180">
                ▾
              </span>
            </summary>
            <p className="px-4 pb-4 text-sm text-[var(--muted)] leading-relaxed">
              {a}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}
