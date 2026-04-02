"use client";
// StatsForm — the "Enter Stats" tab.
// Mirrors all form fields from pages/2_Stats.py.

import { useState, useEffect, useCallback, useRef } from "react";
import {
  getPlayers,
  getFranchises,
  getInstallments,
  getGameContext,
  getObsStatus,
  setObsActive,
  setLiveState,
  getRecentStats,
  addStats,
  downloadChart,
  type Player,
  type Installment,
  type StatRow,
  type StatEntry,
} from "@/lib/api";
import {
  GENRES,
  STAT_ALIASES,
  isBlockedStatName,
  CREDIT_STYLE_OPTIONS,
  MATCH_TYPES,
  WIN_LOSS_OPTIONS,
  PARTY_SIZES,
  DIFFICULTY_OPTIONS,
  INPUT_DEVICES,
  PLATFORMS,
} from "@/lib/constants";

function resolveAlias(input: string) {
  return STAT_ALIASES[input.trim().toLowerCase()] ?? null;
}
import Tooltip from "@/components/Tooltip";

// Mirror flask_app.py regexes for immediate client-side feedback
const STAT_TYPE_RE = /^[A-Za-z0-9 \-]{1,50}$/;
const NAME_RE = /^[A-Za-z0-9 _\-\.]{1,100}$/;

interface Props {
  jwt: string;
  isTrusted: boolean;
  queueMode: boolean;
}

interface StatInput {
  type: string;
  value: string;
}

export default function StatsForm({ jwt, isTrusted, queueMode }: Props) {
  // ── Player state ──────────────────────────────────────────────────────────
  const [players, setPlayers] = useState<Player[]>([]);
  const [playerName, setPlayerName] = useState("");
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [addingNewPlayer, setAddingNewPlayer] = useState(false);
  const [newPlayerName, setNewPlayerName] = useState("");
  const [playerConfirmed, setPlayerConfirmed] = useState(false);

  // ── Game selection state ──────────────────────────────────────────────────
  const [franchises, setFranchises] = useState<string[]>([]);
  const [selectedFranchise, setSelectedFranchise] = useState("");
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [selectedInstallment, setSelectedInstallment] = useState("");
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [isNewFranchiseMode, setIsNewFranchiseMode] = useState(false);
  const [isNewInstallmentMode, setIsNewInstallmentMode] = useState(false);
  const [newFranchiseName, setNewFranchiseName] = useState("");
  const [newInstallmentName, setNewInstallmentName] = useState("");

  // ── New game genre/subgenre ───────────────────────────────────────────────
  const [gameGenre, setGameGenre] = useState("Select a Genre");
  const [gameSubgenre, setGameSubgenre] = useState("Select a Subgenre");

  // ── Credit style ──────────────────────────────────────────────────────────
  const [creditStyle, setCreditStyle] = useState("S/O (Shoutout)");

  // ── Loading states ────────────────────────────────────────────────────────
  const [playersLoading, setPlayersLoading] = useState(true);
  const [franchisesLoading, setFranchisesLoading] = useState(true);
  const [gameContextLoading, setGameContextLoading] = useState(false);

  // ── OBS / Live ────────────────────────────────────────────────────────────
  const [isLive, setIsLive] = useState(false);
  const [obsActive, setObsActiveState] = useState(false);
  const [obsLoaded, setObsLoaded] = useState(false);
  const [liveSetMsg, setLiveSetMsg] = useState<string | null>(null);

  // ── Rank state ────────────────────────────────────────────────────────────
  const [isRanked, setIsRanked] = useState(false);
  const [gameRanks, setGameRanks] = useState<string[]>([]);
  const [preRank, setPreRank] = useState("Unranked");
  const [postRank, setPostRank] = useState("Unranked");
  const [preRankCustom, setPreRankCustom] = useState("");
  const [postRankCustom, setPostRankCustom] = useState("");

  // ── Game context ──────────────────────────────────────────────────────────
  const [gameModes, setGameModes] = useState<string[]>(["Main"]);
  const [gameMode, setGameMode] = useState("Main");
  const [gameModeIsCustom, setGameModeIsCustom] = useState(false);
  const [prevStatTypes, setPrevStatTypes] = useState<string[]>([]);

  // ── Match details ─────────────────────────────────────────────────────────
  const [matchType, setMatchType] = useState<(typeof MATCH_TYPES)[number]>("Solo");
  const [gameLevel, setGameLevel] = useState<string>("");
  const [winLoss, setWinLoss] = useState<(typeof WIN_LOSS_OPTIONS)[number]>("");
  const [partySize, setPartySize] = useState<(typeof PARTY_SIZES)[number]>("1");
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTY_OPTIONS)[number]>("");
  const [inputDevice, setInputDevice] = useState<(typeof INPUT_DEVICES)[number]>("Controller");
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("PC");
  const [overtime, setOvertime] = useState(false);
  const [firstSession, setFirstSession] = useState(true);
  const [firstSessionTodayCount, setFirstSessionTodayCount] = useState<number | null>(null);

  // ── Stat rows (1-10) ──────────────────────────────────────────────────────
  const [statRows, setStatRows] = useState<StatInput[]>([{ type: "", value: "" }]);

  // ── Submit state ──────────────────────────────────────────────────────────
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitStage, setSubmitStage] = useState(0);
  const stageTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSubmitRef = useRef<() => void>(() => {});
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    msg: string;
    statCount?: number;
  } | null>(null);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // ── Draft persistence refs ────────────────────────────────────────────────
  const draftRef = useRef<Record<string, unknown> | null>(null);
  const playerRestored = useRef(false);

  // ── Today's stats (client-side filter — no extra Redshift query) ──────────
  const [todayStats, setTodayStats] = useState<StatEntry[]>([]);

  // ── Today's stats loader (client-side filter, no extra Redshift query) ───
  const loadTodayStats = useCallback(async () => {
    if (!jwt) return;
    try {
      const all = await getRecentStats(jwt);
      // Use browser local timezone, not UTC, to determine "today"
      const today = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local tz
      setTodayStats(all.filter((s) => {
        // played_at may arrive as "2026-04-01 00:54:22+00" or "2026-04-01T00:54:22.971181+00"
        // Strip any existing timezone suffix (+00, +00:00, Z) then re-add Z so the
        // string is unambiguous UTC before converting to the browser's local date.
        const withT = s.played_at.includes("T") ? s.played_at : s.played_at.replace(" ", "T");
        const clean = withT.replace(/([Z]|[+-]\d{2}(:\d{2})?)$/, "") + "Z";
        const localDate = new Date(clean).toLocaleDateString("en-CA");
        return localDate === today;
      }));
    } catch {
      /* silently ignore */
    }
  }, [jwt]);

  useEffect(() => {
    loadTodayStats();
  }, [loadTodayStats]);

  // ── Auto-detect first session per game ────────────────────────────────────
  useEffect(() => {
    if (!selectedGameId) {
      setFirstSessionTodayCount(null);
      return;
    }
    const count = todayStats.filter((s) => s.game_id === selectedGameId).length;
    setFirstSessionTodayCount(count);
    setFirstSession(count === 0);
  }, [selectedGameId, todayStats]);

  // ── Form draft persistence (localStorage) ─────────────────────────────────
  const DRAFT_KEY = "statsForm_v1";

  // Restore match settings on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      draftRef.current = d;
      if (d.creditStyle) setCreditStyle(d.creditStyle);
      if (d.matchType) setMatchType(d.matchType);
      if (d.inputDevice) setInputDevice(d.inputDevice);
      if (d.platform) setPlatform(d.platform);
      if (d.partySize) setPartySize(d.partySize);
      if (d.difficulty !== undefined) setDifficulty(d.difficulty);
      // firstSession is auto-detected per game — not restored from draft
    } catch {}
  }, []);

  // Restore player after players list loads
  useEffect(() => {
    if (playerRestored.current || !players.length || !draftRef.current) return;
    const d = draftRef.current;
    if (typeof d.playerName === "string") {
      const found = players.find((p) => p.player_name === d.playerName);
      if (found) { setPlayerName(found.player_name); setPlayerId(found.player_id); }
    }
    playerRestored.current = true;
  }, [players]);

  // Save draft whenever relevant fields change (skip if serialised draft exceeds 10 KB)
  useEffect(() => {
    try {
      const serialised = JSON.stringify({
        playerName, creditStyle, matchType, inputDevice, platform, partySize, difficulty,
      });
      if (serialised.length <= 10_000) {
        localStorage.setItem(DRAFT_KEY, serialised);
      }
    } catch {}
  }, [playerName, creditStyle, matchType, inputDevice, platform, partySize, difficulty]);

  // ── Load players + franchises on mount (parallel) ────────────────────────
  useEffect(() => {
    if (!jwt || !isTrusted) return;
    setPlayersLoading(true);
    setFranchisesLoading(true);
    getPlayers(jwt)
      .then(setPlayers)
      .catch(console.error)
      .finally(() => setPlayersLoading(false));
    getFranchises(jwt)
      .then(setFranchises)
      .catch(console.error)
      .finally(() => setFranchisesLoading(false));
    getObsStatus(jwt)
      .then((d) => {
        setObsActiveState(d.obs_active);
        setObsLoaded(true);
      })
      .catch(() => setObsLoaded(true));
  }, [jwt, isTrusted]);

  // ── Load installments when franchise changes ──────────────────────────────
  useEffect(() => {
    if (!jwt || !selectedFranchise || isNewFranchiseMode) {
      setInstallments([]);
      return;
    }
    getInstallments(jwt, selectedFranchise)
      .then(setInstallments)
      .catch(console.error);
  }, [jwt, selectedFranchise, isNewFranchiseMode]);

  // ── Load game-specific data when a game is selected ───────────────────────
  useEffect(() => {
    if (!jwt || !selectedGameId || isNewInstallmentMode) {
      setGameRanks([]);
      setGameModes(["Main"]);
      setGameMode("Main");
      setGameModeIsCustom(false);
      setPrevStatTypes([]);
      return;
    }
    setGameMode("Main");
    setGameModeIsCustom(false);
    setGameContextLoading(true);
    getGameContext(jwt, selectedGameId)
      .then(({ ranks, modes, stat_types }) => {
        setGameRanks(ranks);
        setGameModes(modes.length ? modes : ["Main"]);
        setPrevStatTypes(stat_types);
      })
      .catch(console.error)
      .finally(() => setGameContextLoading(false));
  }, [jwt, selectedGameId, isNewInstallmentMode]);

  // ── OBS toggle handler ────────────────────────────────────────────────────
  const handleObsToggle = useCallback(
    async (val: boolean) => {
      setObsActiveState(val);
      try {
        await setObsActive(jwt, val);
      } catch {
        /* ignore */
      }
    },
    [jwt]
  );

  // ── Franchise select handler ──────────────────────────────────────────────
  function handleFranchiseChange(val: string) {
    setSelectedFranchise(val);
    setSelectedInstallment("");
    setSelectedGameId(null);
    setIsNewFranchiseMode(val === "(Enter New Franchise)");
    setIsNewInstallmentMode(val === "(Enter New Franchise)");
  }

  // ── Installment select handler ────────────────────────────────────────────
  function handleInstallmentChange(val: string) {
    setSelectedInstallment(val);
    setIsNewInstallmentMode(val === "(Add New Installment)");
    if (val === "(Add New Installment)") {
      setSelectedGameId(null);
    } else {
      const found = installments.find((i) => i.installment_name === val);
      setSelectedGameId(found?.game_id ?? null);
    }
  }

  // ── Stat row helpers ──────────────────────────────────────────────────────
  function addStatRow() {
    if (statRows.length < 10) setStatRows((r) => [...r, { type: "", value: "" }]);
  }
  function removeStatRow() {
    if (statRows.length > 1) setStatRows((r) => r.slice(0, -1));
  }
  function updateStatRow(idx: number, field: keyof StatInput, val: string | number) {
    setStatRows((rows) =>
      rows.map((r, i) => (i === idx ? { ...r, [field]: val } : r))
    );
  }

  // ── Validation ────────────────────────────────────────────────────────────
  const filledStats = statRows.filter((r) => r.type.trim());
  const types = filledStats.map((r) => r.type.trim().toLowerCase());
  const hasDuplicates = types.length !== new Set(types).size;
  const zeroStats = filledStats.filter((r) => r.value === "" || Number(r.value) === 0).map((r) => r.type);
  const negativeStats = filledStats.filter((r) => Number(r.value) < 0).map((r) => r.type);
  const rankedSameRank =
    isRanked &&
    (preRankCustom || preRank) !== "Unranked" &&
    (preRankCustom || preRank) === (postRankCustom || postRank);
  const rankedMissingPre =
    isRanked &&
    (gameRanks.length === 0
      ? !preRankCustom.trim()
      : preRank === "(Enter New Rank)" && !preRankCustom.trim());
  const rankedMissingPost =
    isRanked &&
    (gameRanks.length === 0
      ? !postRankCustom.trim()
      : postRank === "(Enter New Rank)" && !postRankCustom.trim());

  // Name / stat-type format checks
  const invalidStatTypes = filledStats
    .map((r) => r.type.trim())
    .filter((t) => t && !STAT_TYPE_RE.test(t));
  const blockedStatTypes = filledStats
    .map((r) => r.type.trim())
    .filter((t) => t && isBlockedStatName(t));
  const invalidNewPlayerName =
    addingNewPlayer && newPlayerName.trim() && !NAME_RE.test(newPlayerName.trim());
  const invalidNewFranchise =
    isNewFranchiseMode && newFranchiseName.trim() && !NAME_RE.test(newFranchiseName.trim());
  const invalidNewInstallment =
    isNewInstallmentMode && newInstallmentName.trim() && !NAME_RE.test(newInstallmentName.trim());
  const outOfRangeStats = filledStats.filter(
    (r) => r.value !== "" && (Number(r.value) < 0 || Number(r.value) > 100_000)
  ).map((r) => r.type);

  const issues: { level: "error" | "warning" | "info"; msg: string }[] = [];
  if (hasDuplicates) issues.push({ level: "error", msg: "⛔ Duplicate stat types" });
  if (invalidStatTypes.length > 0)
    issues.push({ level: "error", msg: `⛔ Invalid stat type (letters, numbers, spaces, hyphens only): ${invalidStatTypes.join(", ")}` });
  if (blockedStatTypes.length > 0)
    issues.push({ level: "error", msg: `⛔ Stat name not allowed: ${blockedStatTypes.join(", ")}` });
  if (outOfRangeStats.length > 0)
    issues.push({ level: "error", msg: `⛔ Stat value out of range (0–100,000): ${outOfRangeStats.join(", ")}` });
  if (invalidNewPlayerName)
    issues.push({ level: "error", msg: "⛔ Player name: letters, numbers, spaces, hyphens, underscores, periods only (max 100)" });
  if (invalidNewFranchise)
    issues.push({ level: "error", msg: "⛔ Game name: letters, numbers, spaces, hyphens, underscores, periods only (max 100)" });
  if (invalidNewInstallment)
    issues.push({ level: "error", msg: "⛔ Game installment: letters, numbers, spaces, hyphens, underscores, periods only (max 100)" });
  if (negativeStats.length > 0)
    issues.push({ level: "error", msg: `⛔ Negative stat value: ${negativeStats.join(", ")}` });
  if (rankedMissingPre)
    issues.push({ level: "error", msg: "⛔ Ranked: pre-match rank is required" });
  if (rankedMissingPost)
    issues.push({ level: "error", msg: "⛔ Ranked: post-match rank is required" });
  if (filledStats.length > 0) {
    if (zeroStats.length > 0)
      issues.push({ level: "warning", msg: `⚠️ Zero value: ${zeroStats.join(", ")}` });
    if (matchType === "Solo" && partySize !== "1")
      issues.push({ level: "warning", msg: `⚠️ Solo mode but Party Size is ${partySize}` });
    if (matchType === "Team" && partySize === "1")
      issues.push({ level: "warning", msg: "⚠️ Team mode but Party Size is 1" });
    if (!winLoss && !overtime)
      issues.push({ level: "warning", msg: "⚠️ Win/Loss not set (N/A)" });
    if (rankedSameRank)
      issues.push({ level: "warning", msg: `⚠️ Pre/Post rank unchanged: ${preRankCustom || preRank}` });
    if (isLive && !selectedGameId && !isNewInstallmentMode)
      issues.push({ level: "warning", msg: "⚠️ Live mode on but no game selected" });
    if (isLive && !obsActive)
      issues.push({ level: "warning", msg: "⚠️ Live mode on but OBS is not active" });
    if (gameModeIsCustom && !gameMode.trim())
      issues.push({ level: "warning", msg: "⚠️ Custom game mode selected but left blank — will default to 'Main'" });
    if (!firstSession)
      issues.push({ level: "info", msg: "ℹ️ Subsequent session — line chart will use this as the latest entry" });
    if (isLive && obsActive)
      issues.push({ level: "info", msg: "ℹ️ Live post — #Live hashtags and stream links included" });
  }
  const hasCritical =
    hasDuplicates ||
    negativeStats.length > 0 ||
    outOfRangeStats.length > 0 ||
    invalidStatTypes.length > 0 ||
    invalidNewPlayerName ||
    invalidNewFranchise ||
    invalidNewInstallment ||
    rankedMissingPre ||
    rankedMissingPost;

  // ── Final derived values ──────────────────────────────────────────────────
  const finalGameMode = gameMode.trim() || "Main";
  const finalFranchise = isNewFranchiseMode ? newFranchiseName.trim() : selectedFranchise;
  const finalInstallment =
    isNewInstallmentMode
      ? newInstallmentName.trim() || null
      : selectedInstallment === "- Select Installment -"
      ? null
      : selectedInstallment || null;

  const finalPreRank = preRankCustom.trim() || preRank;
  const finalPostRank = postRankCustom.trim() || postRank;

  // ── Submit ────────────────────────────────────────────────────────────────
  const SUBMIT_STAGES = [
    "Saving stats…",
    "Generating chart…",
    "Uploading to cloud…",
    "Almost there…",
  ];

  async function handleSubmit() {
    if (!confirmed || hasCritical || !playerName || !finalFranchise || filledStats.length === 0)
      return;

    const statsPayload: StatRow[] = filledStats.map((s) => ({
      stat_type: resolveAlias(s.type)?.canonical ?? s.type.trim(),
      stat_value: Number(s.value) || 0,
      game_mode: finalGameMode || "Main",
      solo_mode: matchType === "Solo" ? 1 : 0,
      party_size: partySize,
      game_level: gameLevel ? parseInt(gameLevel) : null,
      win: winLoss === "Win" ? 1 : winLoss === "Loss" ? 0 : null,
      ranked: isRanked ? 1 : 0,
      pre_match_rank_value: isRanked ? finalPreRank : null,
      post_match_rank_value: isRanked ? finalPostRank : null,
      overtime: overtime ? 1 : 0,
      difficulty: difficulty || null,
      input_device: inputDevice,
      platform,
      first_session_of_day: firstSession ? 1 : 0,
      was_streaming: isLive ? 1 : 0,
    }));

    const statCount = filledStats.length;
    setSubmitting(true);
    setSubmitResult(null);
    setSubmitStage(0);

    // Cycle through progress stages
    const durations = [5000, 15000, 25000];
    let stage = 0;
    function nextStage() {
      stage++;
      if (stage < SUBMIT_STAGES.length) {
        setSubmitStage(stage);
        if (stage < durations.length)
          stageTimer.current = setTimeout(nextStage, durations[stage]);
      }
    }
    stageTimer.current = setTimeout(nextStage, durations[0]);

    try {
      const result = await addStats(jwt, {
        player_name: playerName,
        game_name: finalFranchise,
        game_installment: finalInstallment,
        game_genre: isNewInstallmentMode ? gameGenre : null,
        game_subgenre: isNewInstallmentMode ? gameSubgenre : null,
        stats: statsPayload,
        is_live: isLive,
        queue_mode: queueMode,
        credit_style: CREDIT_STYLE_OPTIONS[creditStyle] ?? "shoutout",
      });

      setSubmitResult({ ok: true, msg: result.message, statCount });
      setConfirmed(false);
      setStatRows((rows) => rows.map((r) => ({ ...r, value: "" })));
      loadTodayStats();
    } catch (err) {
      setSubmitResult({
        ok: false,
        msg: err instanceof Error ? err.message : "Submit failed",
      });
    } finally {
      if (stageTimer.current) clearTimeout(stageTimer.current);
      stageTimer.current = null;
      setSubmitting(false);
      setSubmitStage(0);
    }
  }

  // Keep ref current so keyboard shortcut always calls latest handleSubmit
  handleSubmitRef.current = handleSubmit;

  // ── Keyboard shortcut: Ctrl+Enter to submit ───────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        handleSubmitRef.current();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────
  if (!isTrusted) {
    return <GuestPreview />;
  }

  return (
    <div className="space-y-6">
      {/* ── Player selection ───────────────────────────────────────────── */}
      <Section title="Player">
        {!playerConfirmed ? (
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="label">Player Name <Tooltip text="Select a past player profile or create a new one." /></label>
              <select
                className="input"
                disabled={playersLoading}
                value={addingNewPlayer ? "__new__" : playerName}
                onChange={(e) => {
                  if (e.target.value === "__new__") {
                    setAddingNewPlayer(true);
                    setPlayerName("");
                    setPlayerId(null);
                  } else {
                    setAddingNewPlayer(false);
                    const p = players.find((p) => p.player_name === e.target.value);
                    setPlayerName(p?.player_name ?? "");
                    setPlayerId(p?.player_id ?? null);
                  }
                }}
              >
                <option value="">
                  {playersLoading ? "Loading players…" : "— Select player —"}
                </option>
                {players.map((p) => (
                  <option key={p.player_id} value={p.player_name}>
                    {p.player_name}
                  </option>
                ))}
                {!playersLoading && (
                  <option value="__new__">Add a new player…</option>
                )}
              </select>
            </div>

            {addingNewPlayer && (
              <div className="flex-1 min-w-[200px]">
                <label className="label">New Player Name <Tooltip text="Enter a name for the new player profile." /></label>
                <input
                  className="input"
                  value={newPlayerName}
                  onChange={(e) => setNewPlayerName(e.target.value)}
                  placeholder="Enter name…"
                  maxLength={100}
                />
              </div>
            )}

            <button
              className="btn-primary"
              onClick={() => {
                const name = addingNewPlayer ? newPlayerName.trim() : playerName;
                if (!name) return;
                setPlayerName(name);
                setPlayerConfirmed(true);
              }}
            >
              Proceed
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <span className="text-sm">
              Player:{" "}
              <strong className="text-[var(--gold)]">{playerName}</strong>
            </span>
            <button
              className="text-xs text-[var(--muted)] hover:text-[var(--text)] underline"
              onClick={() => {
                setPlayerConfirmed(false);
                setPlayerName("");
                setPlayerId(null);
              }}
            >
              Change
            </button>
          </div>
        )}
      </Section>

      {/* Only show the rest once a player is confirmed */}
      {playerConfirmed && (
        <>
          {/* ── Game selection ──────────────────────────────────────────── */}
          <Section title="Game Selection">
            {/* Franchise */}
            <div>
              <label className="label">Game Name (Franchise) <Tooltip text="Select an existing game franchise or enter a new one." /></label>
              <select
                className="input"
                disabled={franchisesLoading}
                value={isNewFranchiseMode ? "(Enter New Franchise)" : selectedFranchise}
                onChange={(e) => handleFranchiseChange(e.target.value)}
              >
                <option value="">
                  {franchisesLoading ? "Loading franchises…" : "— Select Franchise —"}
                </option>
                {franchises.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
                {!franchisesLoading && (
                  <option value="(Enter New Franchise)">(Enter New Franchise)</option>
                )}
              </select>
            </div>

            {/* New franchise name input */}
            {isNewFranchiseMode && (
              <div className="mt-3 space-y-3">
                <div>
                  <label className="label">New Game Name (Franchise) * <Tooltip text="e.g. Call of Duty, Elden Ring, Final Fantasy" /></label>
                  <input
                    className="input"
                    value={newFranchiseName}
                    onChange={(e) => setNewFranchiseName(e.target.value)}
                    placeholder="e.g. Call of Duty, Elden Ring"
                    maxLength={100}
                  />
                </div>
                <div>
                  <label className="label">
                    New Game Installment{" "}
                    <span className="text-[var(--muted)]">(optional)</span>
                    <Tooltip text="e.g. Black Ops 7. Leave blank if this is a standalone game." />
                  </label>
                  <input
                    className="input"
                    value={newInstallmentName}
                    onChange={(e) => setNewInstallmentName(e.target.value)}
                    placeholder="e.g. Black Ops 7 — leave blank for standalone"
                    maxLength={100}
                  />
                </div>
              </div>
            )}

            {/* Installment dropdown for existing franchise */}
            {!isNewFranchiseMode && selectedFranchise && (
              <div className="mt-3">
                <label className="label">Game Installment <Tooltip text="Select an existing installment or add a new one." /></label>
                <select
                  className="input"
                  value={selectedInstallment}
                  onChange={(e) => handleInstallmentChange(e.target.value)}
                >
                  <option value="">— Select Installment —</option>
                  {installments.map((i) => (
                    <option key={i.game_id} value={i.installment_name}>
                      {i.installment_name}
                    </option>
                  ))}
                  <option value="(Add New Installment)">(Add New Installment)</option>
                </select>
              </div>
            )}

            {/* New installment name */}
            {!isNewFranchiseMode && isNewInstallmentMode && (
              <div className="mt-3">
                <label className="label">New Installment Name * <Tooltip text="e.g. Warzone, Black Ops 7." /></label>
                <input
                  className="input"
                  value={newInstallmentName}
                  onChange={(e) => setNewInstallmentName(e.target.value)}
                  placeholder="e.g. Warzone, Black Ops 7"
                  maxLength={100}
                />
              </div>
            )}

            {/* Genre/Subgenre for new games */}
            {isNewInstallmentMode && (
              <div className="mt-4 space-y-3 border-t border-[var(--border)] pt-4">
                <p className="text-sm font-semibold">New Game Genre Details</p>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="label">Game Genre * <Tooltip text="Select the primary genre of the game." /></label>
                    <select
                      className="input"
                      value={gameGenre}
                      onChange={(e) => {
                        setGameGenre(e.target.value);
                        setGameSubgenre("Select a Subgenre");
                      }}
                    >
                      {Object.keys(GENRES).map((g) => (
                        <option key={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Game Subgenre * <Tooltip text="Select the subgenre that best describes this game." /></label>
                    <select
                      className="input"
                      value={gameSubgenre}
                      onChange={(e) => setGameSubgenre(e.target.value)}
                    >
                      {(GENRES[gameGenre] ?? ["Select a Subgenre"]).map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
          </Section>

          {/* ── Credit style ────────────────────────────────────────────── */}
          <Section title="Credit Style">
            <div className="sm:w-64">
              <label className="label">
                Credit Style <Tooltip text="How the game is credited in your social media caption (e.g., 'S/O @CallOfDuty')." />
              </label>
              <select
                className="input"
                value={creditStyle}
                onChange={(e) => setCreditStyle(e.target.value)}
              >
                {Object.keys(CREDIT_STYLE_OPTIONS).map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </div>
          </Section>

          {/* ── Live / OBS ──────────────────────────────────────────────── */}
          <Section title="Streaming Status">
            <div className="grid sm:grid-cols-2 gap-4">
              <Toggle
                label="🔴 Live Now"
                value={isLive}
                onChange={setIsLive}
                hint="Enable when you're LIVE streaming. Posts will include #Live hashtags."
              />
              {obsLoaded && (
                <Toggle
                  label="🎬 OBS Active"
                  value={obsActive}
                  onChange={handleObsToggle}
                  hint="Enable when streaming/recording in OBS. Activates overlay and ticker."
                />
              )}
            </div>
            <p className="text-xs mt-1">
              {isLive ? (
                <span className="text-green-400">
                  🔴 LIVE — posts will include live stream links and hashtags
                </span>
              ) : (
                <span className="text-[var(--muted)]">
                  ⚪ Offline — posts will use standard format
                </span>
              )}
            </p>

            {/* Set Live Game for OBS — only shown when player + game are both selected */}
            {playerId !== null && selectedGameId !== null && (
              <div className="pt-3 border-t border-[var(--border)] flex items-center gap-3 flex-wrap">
                <button
                  className="btn-sm"
                  onClick={async () => {
                    try {
                      await setLiveState(jwt, playerId, selectedGameId);
                      setLiveSetMsg("✅ OBS dashboard updated.");
                    } catch {
                      setLiveSetMsg("❌ Failed to update OBS.");
                    }
                    setTimeout(() => setLiveSetMsg(null), 3000);
                  }}
                >
                  📺 Set as Live Game for OBS
                </button>
                {liveSetMsg && (
                  <span className="text-xs text-[var(--muted)]">{liveSetMsg}</span>
                )}
              </div>
            )}
          </Section>

          {/* ── Rank ────────────────────────────────────────────────────── */}
          <Section title="Rank Information">
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={isRanked}
                onChange={(e) => setIsRanked(e.target.checked)}
                className="accent-[var(--gold)]"
              />
              Ranked? <Tooltip text="Is this a ranked match? Enables pre/post rank tracking." />
            </label>

            {isRanked && (
              <div className="mt-3 grid sm:grid-cols-2 gap-3">
                {/* Pre-match rank */}
                <div>
                  <label className="label">Pre-match Rank <Tooltip text="Your rank before this match started." /></label>
                  {gameRanks.length > 0 ? (
                    <>
                      <select
                        className="input"
                        value={preRank}
                        onChange={(e) => {
                          setPreRank(e.target.value);
                          if (e.target.value !== "(Enter New Rank)")
                            setPreRankCustom("");
                        }}
                      >
                        <option>Unranked</option>
                        {gameRanks.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                        <option value="(Enter New Rank)">(Enter New Rank)</option>
                      </select>
                      {preRank === "(Enter New Rank)" && (
                        <input
                          className="input mt-2"
                          value={preRankCustom}
                          onChange={(e) => setPreRankCustom(e.target.value)}
                          placeholder="Type rank…"
                        />
                      )}
                    </>
                  ) : (
                    <input
                      className="input"
                      value={preRankCustom}
                      onChange={(e) => setPreRankCustom(e.target.value)}
                      placeholder="e.g. Gold II"
                    />
                  )}
                </div>

                {/* Post-match rank */}
                <div>
                  <label className="label">Post-match Rank <Tooltip text="Your rank after this match ended." /></label>
                  {gameRanks.length > 0 ? (
                    <>
                      <select
                        className="input"
                        value={postRank}
                        onChange={(e) => {
                          setPostRank(e.target.value);
                          if (e.target.value !== "(Enter New Rank)")
                            setPostRankCustom("");
                        }}
                      >
                        <option>Unranked</option>
                        {gameRanks.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                        <option value="(Enter New Rank)">(Enter New Rank)</option>
                      </select>
                      {postRank === "(Enter New Rank)" && (
                        <input
                          className="input mt-2"
                          value={postRankCustom}
                          onChange={(e) => setPostRankCustom(e.target.value)}
                          placeholder="Type rank…"
                        />
                      )}
                    </>
                  ) : (
                    <input
                      className="input"
                      value={postRankCustom}
                      onChange={(e) => setPostRankCustom(e.target.value)}
                      placeholder="e.g. Gold III"
                    />
                  )}
                </div>
              </div>
            )}
          </Section>

          {/* ── Match Context ────────────────────────────────────────────── */}
          <Section
            title={`Stats — ${playerName} | ${finalFranchise || "…"} | ${finalInstallment ?? "Main Game"}`}
          >
            {/* Previously used stat types hint */}
            {prevStatTypes.length > 0 && (
              <div className="text-xs text-blue-300 bg-blue-900/20 border border-blue-800 rounded px-3 py-2 mb-3">
                <strong>Tip:</strong> Previously used stat types for this game:{" "}
                {prevStatTypes.join(", ")}
              </div>
            )}

            {/* Game mode — dropdown for known games, free text for new games */}
            <div className="sm:w-64">
              <label className="label">Game Mode <Tooltip text="Select an existing mode or enter a custom one. Defaults to 'Main' if left blank." /></label>
              {isNewInstallmentMode || !selectedGameId ? (
                <input
                  className="input"
                  value={gameMode === "Main" ? "" : gameMode}
                  onChange={(e) => setGameMode(e.target.value || "Main")}
                  placeholder="e.g. Multiplayer, Battle Royale (default: Main)"
                />
              ) : gameContextLoading ? (
                <select className="input" disabled>
                  <option>Loading modes…</option>
                </select>
              ) : (
                <>
                  <select
                    className="input"
                    value={gameModeIsCustom ? "__custom__" : gameMode}
                    onChange={(e) => {
                      if (e.target.value === "__custom__") {
                        setGameModeIsCustom(true);
                        setGameMode("");
                      } else {
                        setGameModeIsCustom(false);
                        setGameMode(e.target.value);
                      }
                    }}
                  >
                    {gameModes.map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                    <option value="__custom__">(Enter Custom)</option>
                  </select>
                  {gameModeIsCustom && (
                    <input
                      className="input mt-2"
                      value={gameMode}
                      onChange={(e) => setGameMode(e.target.value)}
                      placeholder="Custom game mode…"
                      autoFocus
                    />
                  )}
                </>
              )}
            </div>

            {/* Match type + win/loss */}
            <div className="grid sm:grid-cols-3 gap-3 mt-3">
              <div>
                <label className="label">Match Type <Tooltip text="Solo = playing alone (no teammates). Team = playing with at least one other player." /></label>
                <select
                  className="input"
                  value={matchType}
                  onChange={(e) =>
                    setMatchType(e.target.value as typeof matchType)
                  }
                >
                  {MATCH_TYPES.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Win / Loss <Tooltip text="Select Win or Loss. Leave N/A if not applicable." /></label>
                <select
                  className="input"
                  value={winLoss}
                  onChange={(e) => setWinLoss(e.target.value as typeof winLoss)}
                >
                  {WIN_LOSS_OPTIONS.map((o) => (
                    <option key={o} value={o}>
                      {o === "" ? "N/A" : o}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Party Size <Tooltip text="Number of players in your party. 1 = Solo." /></label>
                <select
                  className="input"
                  value={partySize}
                  onChange={(e) => setPartySize(e.target.value as typeof partySize)}
                >
                  {PARTY_SIZES.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Level + difficulty + input + platform */}
            <div className="grid sm:grid-cols-4 gap-3 mt-3">
              <div>
                <label className="label">Game Level / Wave <Tooltip text="e.g. Wave 10, Episode 1, Mission 3. Leave 0 if not applicable." /></label>
                <input
                  className="input"
                  type="number"
                  min={0}
                  value={gameLevel}
                  onChange={(e) => setGameLevel(e.target.value)}
                  placeholder="0"
                />
              </div>
              <div>
                <label className="label">Difficulty <Tooltip text="Game difficulty setting. Leave N/A if not applicable (e.g. most multiplayer games)." /></label>
                <select
                  className="input"
                  value={difficulty}
                  onChange={(e) =>
                    setDifficulty(e.target.value as typeof difficulty)
                  }
                >
                  {DIFFICULTY_OPTIONS.map((d) => (
                    <option key={d} value={d}>
                      {d === "" ? "N/A" : d}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Input Device <Tooltip text="Primary input device used during this session." /></label>
                <select
                  className="input"
                  value={inputDevice}
                  onChange={(e) =>
                    setInputDevice(e.target.value as typeof inputDevice)
                  }
                >
                  {INPUT_DEVICES.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Platform <Tooltip text="Platform the game was played on." /></label>
                <select
                  className="input"
                  value={platform}
                  onChange={(e) =>
                    setPlatform(e.target.value as typeof platform)
                  }
                >
                  {PLATFORMS.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Toggles */}
            <div className="flex flex-wrap gap-6 mt-3">
              <Toggle
                label="Overtime / Sudden Death"
                value={overtime}
                onChange={setOvertime}
                hint="Did this match go to overtime or sudden death?"
              />
              <div>
                <Toggle
                  label="First Session of Day"
                  value={firstSession}
                  onChange={setFirstSession}
                  hint="Auto-detected per game · override if needed."
                />
                {firstSessionTodayCount !== null && (
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    {firstSessionTodayCount === 0
                      ? "✅ No entries today for this game — auto-set to first session"
                      : `🔄 ${firstSessionTodayCount} entr${firstSessionTodayCount === 1 ? "y" : "ies"} today for this game — auto-set to subsequent session`}
                  </p>
                )}
              </div>
            </div>

            {/* ── Stat rows ──────────────────────────────────────────────── */}
            <div className="mt-4 border-t border-[var(--border)] pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">Stats</p>
                <div className="flex gap-2">
                  <button
                    className="btn-sm"
                    onClick={addStatRow}
                    disabled={statRows.length >= 10}
                  >
                    ➕ Add Row
                  </button>
                  <button
                    className="btn-sm"
                    onClick={removeStatRow}
                    disabled={statRows.length <= 1}
                  >
                    ➖ Remove Row
                  </button>
                </div>
              </div>

              {/* Datalist feeds the stat type inputs with previously used types */}
              {prevStatTypes.length > 0 && (
                <datalist id="prev-stat-types">
                  {prevStatTypes.map((t) => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
              )}

              {statRows.map((row, i) => (
                <div key={i} className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="label">Stat Type {i + 1} <Tooltip text="e.g. Eliminations, Points, Kills, Assists. Start typing to see suggestions." /></label>
                    <input
                      className="input"
                      list="prev-stat-types"
                      value={row.type}
                      onChange={(e) => updateStatRow(i, "type", e.target.value)}
                      placeholder="e.g. Eliminations, Points, Wins"
                      maxLength={50}
                    />
                    {(() => {
                      const alias = resolveAlias(row.type);
                      return alias ? (
                        <p className="text-xs text-[var(--gold)] mt-0.5">
                          → Saved as &ldquo;{alias.display}&rdquo;
                        </p>
                      ) : null;
                    })()}
                  </div>
                  <div>
                    <label className="label">Stat Value {i + 1} <Tooltip text="Numeric value of this statistic." /></label>
                    <input
                      className="input"
                      type="number"
                      min={0}
                      max={100000}
                      value={row.value}
                      onChange={(e) => updateStatRow(i, "value", e.target.value)}
                      onFocus={(e) => e.target.select()}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Section>

          {/* ── Validation ──────────────────────────────────────────────── */}
          {issues.length > 0 && (
            <Section title="Review before submitting">
              <div className="grid sm:grid-cols-2 gap-2">
                {issues.map((issue, i) => (
                  <div
                    key={i}
                    className={`rounded px-3 py-2 text-sm ${
                      issue.level === "error"
                        ? "bg-red-900/30 border border-red-700 text-red-300"
                        : issue.level === "warning"
                        ? "bg-yellow-900/30 border border-yellow-700 text-yellow-200"
                        : "bg-blue-900/20 border border-blue-800 text-blue-200"
                    }`}
                  >
                    {issue.msg}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* ── Stats review ────────────────────────────────────────────── */}
          {filledStats.length > 0 && (
            <details
              open
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)]"
            >
              <summary className="px-4 py-3 cursor-pointer text-sm font-semibold">
                📋 Review your stats before submitting
              </summary>
              <ul className="px-4 pb-3 space-y-1 text-sm">
                {filledStats.map((s, i) => (
                  <li key={i}>
                    • <strong>{s.type}</strong>: {s.value}
                    {(s.value === "" || Number(s.value) === 0) && (
                      <span className="text-yellow-400"> ⚠️ zero</span>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* ── Confirm + Submit ─────────────────────────────────────────── */}
          <div className="space-y-3">
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="accent-[var(--gold)]"
              />
              ✅ I have reviewed my stats above and they are correct.
            </label>

            {/* Submit + Download — 1:2 ratio grid */}
            <div className="grid grid-cols-3 items-stretch gap-2">
              <button
                className="btn-primary col-span-1 disabled:opacity-40"
                disabled={!confirmed || hasCritical || submitting || filledStats.length === 0}
                onClick={handleSubmit}
                title="Ctrl+Enter"
              >
                {submitting ? SUBMIT_STAGES[submitStage] : "Submit Stats"}
              </button>

              {/* Download — locked until today's stats are submitted */}
              <div className="relative col-span-2">
                <button
                  className="flex items-center justify-center gap-1.5 w-full h-full px-4 rounded
                    border border-[var(--border)] bg-[var(--surface)] text-sm font-medium
                    transition-colors
                    disabled:opacity-30 disabled:cursor-not-allowed
                    enabled:hover:bg-[var(--border)] enabled:hover:text-[var(--gold)]"
                  disabled={!submitResult?.ok || downloading}
                  onClick={() => setShowDownloadMenu((p) => !p)}
                  title={!submitResult?.ok ? "Submit today's stats first to unlock download" : "Download chart image"}
                >
                  {downloading ? "⏳" : "⬇"} Download Chart
                </button>

                {showDownloadMenu && (
                  <div className="absolute left-0 top-full mt-1 z-20 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg overflow-hidden min-w-[160px]">
                    {(
                      [
                        { platform: "twitter",   label: "Twitter / X", icon: "𝕏", color: "#1DA1F2" },
                        { platform: "instagram", label: "Instagram",   icon: "📷", color: "#E1306C" },
                      ] as const
                    ).map(({ platform, label, icon, color }) => (
                      <button
                        key={platform}
                        className="flex items-center gap-2 w-full px-4 py-2.5 text-sm hover:bg-[var(--border)] transition-colors text-left"
                        onClick={async () => {
                          setShowDownloadMenu(false);
                          if (!selectedGameId) return;
                          setDownloading(true);
                          try {
                            await downloadChart(jwt, selectedGameId, playerName, platform);
                          } catch (e) {
                            console.error("Download failed:", e);
                          } finally {
                            setDownloading(false);
                          }
                        }}
                      >
                        <span style={{ color }}>{icon}</span>
                        <span style={{ color }}>{label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {submitResult?.ok && (
            <div className="rounded-lg border border-green-700 bg-green-900/20 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">✅</span>
                <span className="font-semibold text-green-300 text-sm">Stats Submitted!</span>
              </div>
              <div className="grid grid-cols-2 gap-1.5 text-xs text-[var(--muted)]">
                <div>👤 <span className="text-[var(--text)]">{playerName}</span></div>
                <div>📊 <span className="text-[var(--text)]">{submitResult.statCount} stat{submitResult.statCount !== 1 ? "s" : ""} saved</span></div>
                <div className="col-span-2">🎮 <span className="text-[var(--text)]">{finalFranchise}{finalInstallment ? ` — ${finalInstallment}` : ""}</span></div>
                <div className="col-span-2 text-[var(--muted)]">{queueMode ? "📬 Post queued for scheduled delivery" : "🚀 Post sent immediately via IFTTT"}</div>
              </div>
            </div>
          )}
          {submitResult?.ok === false && (
            <div className="rounded px-4 py-3 text-sm bg-red-900/30 border border-red-700 text-red-300">
              ❌ {submitResult.msg}
            </div>
          )}

          {/* ── Today's stats (client-side filter, no extra query) ─────── */}
          {todayStats.length > 0 && (
            <details className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
              <summary className="px-4 py-3 cursor-pointer text-sm font-semibold">
                📅 Today&apos;s entries ({todayStats.length})
              </summary>
              <div className="px-4 pb-3 overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="text-[var(--muted)] border-b border-[var(--border)]">
                      <th className="text-left py-1 pr-3">Game</th>
                      <th className="text-left py-1 pr-3">Stat</th>
                      <th className="text-right py-1 pr-3">Value</th>
                      <th className="text-left py-1">Mode</th>
                    </tr>
                  </thead>
                  <tbody>
                    {todayStats.map((s) => (
                      <tr
                        key={s.stat_id}
                        className="border-b border-[var(--border)] last:border-0"
                      >
                        <td className="py-1 pr-3 text-[var(--muted)]">
                          {s.game_name}
                        </td>
                        <td className="py-1 pr-3">{s.stat_type}</td>
                        <td className="py-1 pr-3 text-right font-mono text-[var(--gold)]">
                          {s.stat_value.toLocaleString()}
                        </td>
                        <td className="py-1 text-[var(--muted)]">
                          {s.game_mode ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}

// ── Guest preview (read-only) ─────────────────────────────────────────────────
function GuestPreview() {
  return (
    <div className="space-y-4 opacity-60 pointer-events-none select-none">
      <p className="text-sm text-yellow-300 font-semibold pointer-events-auto opacity-100">
        🔒 Form preview — sign in with a trusted account to submit stats.
      </p>
      <Section title="Game Selection">
        <select className="input" disabled>
          <option>— Select Franchise —</option>
        </select>
      </Section>
      <Section title="Stats">
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Stat Type 1</label>
            <input className="input" disabled placeholder="e.g. Kills" />
          </div>
          <div>
            <label className="label">Stat Value 1</label>
            <input className="input" type="number" disabled value={0} readOnly />
          </div>
        </div>
      </Section>
      <button className="btn-primary" disabled>
        Submit Stats
      </button>
    </div>
  );
}

// ── Shared UI primitives ──────────────────────────────────────────────────────
function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-[var(--gold)] border-b border-[var(--border)] pb-2">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Toggle({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <div>
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <div
          onClick={() => onChange(!value)}
          className={`relative w-10 h-5 rounded-full transition-colors ${
            value ? "bg-[var(--gold)]" : "bg-[var(--border)]"
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              value ? "translate-x-5" : ""
            }`}
          />
        </div>
        {label}
      </label>
      {hint && <p className="text-xs text-[var(--muted)] mt-0.5 ml-12">{hint}</p>}
    </div>
  );
}
