"use client";

import { useEffect, useState } from "react";
import {
  getAllGames,
  GameDetails,
  toggleLeaderboardOptIn,
  getOptInStatus,
  getLeaderboardSampleSize,
  getLeaderboardTopStats,
  getLeaderboardRankings,
  getLeaderboardStandings,
  LeaderboardRankings,
  StandingCard,
} from "@/lib/api";

type Tab = "rankings" | "standings";

export default function LeaderboardTab({ jwt }: { jwt: string }) {
  const [activeTab, setActiveTab]     = useState<Tab>("rankings");

  // Games + opt-in state
  const [games, setGames]             = useState<GameDetails[]>([]);
  const [optedIn, setOptedIn]         = useState<number[]>([]);
  const [selectedGame, setSelectedGame] = useState<number | null>(null);

  // Rankings state
  const [phase, setPhase]             = useState<string>("hidden");
  const [statTypes, setStatTypes]     = useState<string[]>([]);
  const [selectedStat, setSelectedStat] = useState<string | null>(null);
  const [rankings, setRankings]       = useState<LeaderboardRankings | null>(null);
  const [rankingsLoading, setRankingsLoading] = useState(false);

  // Standings state
  const [standings, setStandings]     = useState<StandingCard[]>([]);
  const [standingsLoading, setStandingsLoading] = useState(false);

  const [togglingOptIn, setTogglingOptIn] = useState(false);
  const [error, setError]             = useState<string | null>(null);

  // Load games + opt-in status on mount
  useEffect(() => {
    getAllGames(jwt).then(setGames).catch(() => {});
    getOptInStatus(jwt).then((d) => setOptedIn(d.opted_in)).catch(() => {});
    getLeaderboardStandings(jwt)
      .then((d) => setStandings(d.standings))
      .catch(() => {});
  }, [jwt]);

  // When game changes, fetch sample size + top stats
  useEffect(() => {
    if (!selectedGame) return;
    setStatTypes([]);
    setSelectedStat(null);
    setRankings(null);

    getLeaderboardSampleSize(jwt, selectedGame).then((d) => setPhase(d.phase)).catch(() => {});
    getLeaderboardTopStats(jwt, selectedGame)
      .then((d) => {
        setStatTypes(d.stat_types);
        if (d.stat_types.length > 0) setSelectedStat(d.stat_types[0]);
      })
      .catch(() => {});
  }, [jwt, selectedGame]);

  // When stat type changes, fetch rankings
  useEffect(() => {
    if (!selectedGame || !selectedStat) return;
    setRankingsLoading(true);
    setError(null);
    getLeaderboardRankings(jwt, selectedGame, selectedStat)
      .then(setRankings)
      .catch(() => setError("Failed to load rankings."))
      .finally(() => setRankingsLoading(false));
  }, [jwt, selectedGame, selectedStat]);

  async function handleOptInToggle() {
    if (!selectedGame) return;
    setTogglingOptIn(true);
    try {
      const res = await toggleLeaderboardOptIn(jwt, selectedGame);
      setOptedIn((prev) =>
        res.opted_in ? [...prev, selectedGame] : prev.filter((id) => id !== selectedGame)
      );
      // Refresh standings after toggle
      getLeaderboardStandings(jwt).then((d) => setStandings(d.standings)).catch(() => {});
    } finally {
      setTogglingOptIn(false);
    }
  }

  const isOptedIn   = selectedGame ? optedIn.includes(selectedGame) : false;
  const gameTitle   = games.find((g) => g.game_id === selectedGame);

  return (
    <div className="space-y-4">
      {/* Tab switcher */}
      <div className="flex border-b border-[var(--border)]">
        {(["rankings", "standings"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              activeTab === t
                ? "border-[var(--gold)] text-[var(--gold)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            {t === "rankings" ? "Rankings" : "Standings"}
          </button>
        ))}
      </div>

      {/* ── Rankings tab ─────────────────────────────────────────── */}
      {activeTab === "rankings" && (
        <div className="space-y-4">
          {/* Game selector + opt-in toggle */}
          <div className="flex items-center gap-3">
            <select
              value={selectedGame ?? ""}
              onChange={(e) => setSelectedGame(Number(e.target.value) || null)}
              className="flex-1 text-sm rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] px-3 py-1.5 focus:outline-none focus:border-[var(--gold)]"
            >
              <option value="">Select a game…</option>
              {games.map((g) => (
                <option key={g.game_id} value={g.game_id}>
                  {g.game_name}{g.game_installment ? `: ${g.game_installment}` : ""}
                </option>
              ))}
            </select>

            {selectedGame && (
              <button
                onClick={handleOptInToggle}
                disabled={togglingOptIn}
                className={`text-xs px-3 py-1.5 rounded border transition-colors whitespace-nowrap ${
                  isOptedIn
                    ? "border-[var(--gold)] text-[var(--gold)] hover:bg-[var(--gold)]/10"
                    : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]"
                }`}
              >
                {isOptedIn ? "✓ Opted in" : "Opt in"}
              </button>
            )}
          </div>

          {/* Phase gates */}
          {!selectedGame && (
            <p className="text-sm text-[var(--muted)] text-center py-8">
              Select a game to view rankings.
            </p>
          )}

          {selectedGame && phase === "hidden" && (
            <div className="text-center py-8 space-y-2">
              <p className="text-2xl">🏆</p>
              <p className="text-sm text-[var(--muted)]">No players opted in yet.</p>
              <p className="text-xs text-[var(--muted)]">Be the first — opt in above.</p>
            </div>
          )}

          {selectedGame && phase === "placeholder" && (
            <div className="text-center py-8 space-y-2">
              <p className="text-2xl">🏆</p>
              <p className="text-sm text-[var(--muted)]">
                {rankings?.sample_size ?? 0} / 3 players needed to unlock rankings.
              </p>
              <p className="text-xs text-[var(--muted)]">Invite friends to compete.</p>
            </div>
          )}

          {selectedGame && (phase === "standings_only" || phase === "full") && (
            <>
              {/* Stat type pills */}
              {statTypes.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {statTypes.map((s) => (
                    <button
                      key={s}
                      onClick={() => setSelectedStat(s)}
                      className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                        selectedStat === s
                          ? "bg-[var(--gold)] text-black border-[var(--gold)] font-semibold"
                          : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--gold)]"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {phase === "standings_only" && (
                <p className="text-xs text-yellow-400 px-1">
                  Small sample · {rankings?.sample_size ?? 0} players — full rankings unlock at 10
                </p>
              )}

              {/* Rankings table */}
              {rankingsLoading && (
                <p className="text-sm text-[var(--muted)] animate-pulse">Loading rankings…</p>
              )}
              {error && <p className="text-sm text-red-400">{error}</p>}

              {rankings && !rankingsLoading && (
                <div className="space-y-2">
                  <div className="grid grid-cols-[2rem_1fr_5rem_4rem] gap-x-3 text-[10px] uppercase text-[var(--muted)] px-1">
                    <span>#</span>
                    <span>Player</span>
                    <span className="text-right">Avg</span>
                    <span className="text-right">Sessions</span>
                  </div>

                  {rankings.top10.map((entry) => (
                    <div
                      key={entry.rank}
                      className={`grid grid-cols-[2rem_1fr_5rem_4rem] gap-x-3 items-center px-3 py-2 rounded border text-sm ${
                        entry.is_you
                          ? "border-[var(--gold)] bg-[var(--gold)]/5 text-[var(--gold)]"
                          : "border-[var(--border)] text-[var(--text)]"
                      }`}
                    >
                      <span className="font-bold text-xs">
                        {entry.rank === 1 ? "🥇" : entry.rank === 2 ? "🥈" : entry.rank === 3 ? "🥉" : `#${entry.rank}`}
                      </span>
                      <span className="truncate">
                        {entry.player_name}
                        {entry.is_you && <span className="ml-1 text-[10px]">(you)</span>}
                      </span>
                      <span className="text-right font-semibold">{entry.avg_value}</span>
                      <span className="text-right text-[var(--muted)] text-xs">{entry.sessions}</span>
                    </div>
                  ))}

                  {/* User rank if outside top 10 */}
                  {rankings.your_rank && !rankings.top10.some((e) => e.is_you) && (
                    <>
                      <div className="text-center text-[var(--muted)] text-xs py-1">· · ·</div>
                      <div className="grid grid-cols-[2rem_1fr_5rem_4rem] gap-x-3 items-center px-3 py-2 rounded border border-[var(--gold)] bg-[var(--gold)]/5 text-[var(--gold)] text-sm">
                        <span className="font-bold text-xs">#{rankings.your_rank.rank}</span>
                        <span>You</span>
                        <span className="text-right font-semibold">{rankings.your_rank.avg_value}</span>
                        <span className="text-right text-xs">{rankings.your_rank.sessions}</span>
                      </div>
                    </>
                  )}

                  {/* Premium lock for weighted sliders */}
                  <div className="flex items-center gap-2 px-3 py-2 rounded border border-[var(--border)] opacity-50 mt-2">
                    <span className="text-xs text-[var(--muted)]">🔒</span>
                    <span className="text-xs text-[var(--muted)]">Custom weights — Premium feature</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Standings tab ─────────────────────────────────────────── */}
      {activeTab === "standings" && (
        <div className="space-y-3">
          {standingsLoading && (
            <p className="text-sm text-[var(--muted)] animate-pulse">Loading standings…</p>
          )}

          {!standingsLoading && standings.length === 0 && (
            <div className="text-center py-8 space-y-2">
              <p className="text-2xl">📊</p>
              <p className="text-sm text-[var(--muted)]">No standings yet.</p>
              <p className="text-xs text-[var(--muted)]">
                Opt into at least one game in the Rankings tab to see your standing.
              </p>
            </div>
          )}

          {standings.map((card) => (
            <div
              key={card.game_id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-sm">{card.game_title}</p>
                  <p className="text-xs text-[var(--muted)]">{card.stat_type}</p>
                </div>
                {card.small_sample && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-400/20 text-yellow-400 border border-yellow-400/40 whitespace-nowrap">
                    small sample
                  </span>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded border border-[var(--border)] py-2">
                  <p className="text-lg font-bold text-[var(--gold)]">#{card.rank}</p>
                  <p className="text-[10px] text-[var(--muted)]">Rank</p>
                </div>
                <div className="rounded border border-[var(--border)] py-2">
                  <p className="text-lg font-bold">{card.percentile}%</p>
                  <p className="text-[10px] text-[var(--muted)]">Percentile</p>
                </div>
                <div className="rounded border border-[var(--border)] py-2">
                  <p className="text-lg font-bold">{card.avg_value}</p>
                  <p className="text-[10px] text-[var(--muted)]">Avg</p>
                </div>
              </div>

              <p className="text-xs text-[var(--muted)] text-center">
                {card.sample_size} player{card.sample_size !== 1 ? "s" : ""} competing
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
