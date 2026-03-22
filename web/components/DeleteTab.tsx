"use client";
// DeleteTab — mirrors the Delete tab from pages/2_Stats.py (trusted users only).
// Sub-tabs: Delete Player | Delete Game | Delete Stat

import { useState } from "react";
import {
  getPlayers,
  getAllGames,
  getRecentStats,
  deletePlayer,
  deleteGame,
  deleteStats,
  type Player,
  type GameDetails,
  type StatEntry,
} from "@/lib/api";

interface Props {
  jwt: string;
}

type SubTab = "player" | "game" | "stat";

export default function DeleteTab({ jwt }: Props) {
  const [subTab, setSubTab] = useState<SubTab>("player");

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Delete Data</h2>
      <div className="flex gap-2 border-b border-[var(--border)] pb-2">
        {(["player", "game", "stat"] as SubTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setSubTab(t)}
            className={`px-3 py-1 rounded text-sm capitalize transition-colors ${
              subTab === t
                ? "bg-red-800 text-white font-semibold"
                : "bg-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            Delete {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {subTab === "player" && <DeletePlayer jwt={jwt} />}
      {subTab === "game" && <DeleteGame jwt={jwt} />}
      {subTab === "stat" && <DeleteStat jwt={jwt} />}
    </div>
  );
}

// ── Delete Player ─────────────────────────────────────────────────────────────
function DeletePlayer({ jwt }: Props) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<"select" | "confirm" | "final">("select");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    const data = await getPlayers(jwt);
    setPlayers(data);
    setLoaded(true);
    setStep("select");
    setSelectedId(null);
    setMsg(null);
  }

  const selected = players.find((p) => p.player_id === selectedId);

  async function handleDelete() {
    if (!selectedId) return;
    try {
      await deletePlayer(jwt, selectedId);
      setMsg({ ok: true, text: `"${selected?.player_name}" and all stats deleted.` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-red-400 font-semibold">
        ⚠️ Warning: This will delete the player AND all associated stats forever.
      </p>
      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Players" : "Load Players to Delete"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => {
              setSelectedId(Number(e.target.value) || null);
              setStep("select");
              setMsg(null);
            }}
          >
            <option value="">— Select player —</option>
            {players.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                {p.player_name}
              </option>
            ))}
          </select>

          {selectedId && step === "select" && (
            <>
              <p className="text-sm text-yellow-300">
                About to delete{" "}
                <strong>{selected?.player_name}</strong> (ID: {selectedId}) and
                all their stats.
              </p>
              <button
                className="btn-sm border-yellow-600 text-yellow-300 hover:bg-yellow-900/30"
                onClick={() => setStep("confirm")}
              >
                Confirm Delete Player
              </button>
            </>
          )}

          {step === "confirm" && (
            <>
              <p className="text-sm text-red-400 font-bold">
                This action is permanent and cannot be undone.
              </p>
              <button
                className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-bold transition-colors"
                onClick={handleDelete}
              >
                DELETE PLAYER FOREVER
              </button>
            </>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </div>
      )}
    </div>
  );
}

// ── Delete Game ───────────────────────────────────────────────────────────────
function DeleteGame({ jwt }: Props) {
  const [games, setGames] = useState<GameDetails[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<"select" | "confirm">("select");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    const data = await getAllGames(jwt);
    setGames(data);
    setLoaded(true);
    setStep("select");
    setSelectedId(null);
    setMsg(null);
  }

  const selected = games.find((g) => g.game_id === selectedId);

  async function handleDelete() {
    if (!selectedId) return;
    try {
      await deleteGame(jwt, selectedId);
      setMsg({ ok: true, text: `Game "${selected?.game_name}" deleted.` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        You can only delete games that have zero associated stats.
      </p>
      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Games" : "Load Games to Delete"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => {
              setSelectedId(Number(e.target.value) || null);
              setStep("select");
              setMsg(null);
            }}
          >
            <option value="">— Select game —</option>
            {games.map((g) => (
              <option key={g.game_id} value={g.game_id}>
                {g.game_name}
              </option>
            ))}
          </select>

          {selectedId && step === "select" && (
            <>
              <p className="text-sm text-yellow-300">
                Attempting to delete{" "}
                <strong>{selected?.game_name}</strong> — this will only succeed
                if all stats have been removed first.
              </p>
              <button
                className="btn-sm border-yellow-600 text-yellow-300 hover:bg-yellow-900/30"
                onClick={() => setStep("confirm")}
              >
                Confirm Delete Game
              </button>
            </>
          )}

          {step === "confirm" && (
            <>
              <p className="text-sm text-red-400 font-bold">
                This action is permanent.
              </p>
              <button
                className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-bold transition-colors"
                onClick={handleDelete}
              >
                DELETE GAME FOREVER
              </button>
            </>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </div>
      )}
    </div>
  );
}

// ── Delete Stat ───────────────────────────────────────────────────────────────
function DeleteStat({ jwt }: Props) {
  const [stats, setStats] = useState<StatEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<"select" | "confirm">("select");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    try {
      const data = await getRecentStats(jwt);
      setStats(data);
      setLoaded(true);
      setStep("select");
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  const selected = stats.find((s) => s.stat_id === selectedId);

  async function handleDelete() {
    if (!selectedId) return;
    try {
      await deleteStats(jwt, selectedId);
      setMsg({
        ok: true,
        text: `Stat ID ${selectedId} deleted.`,
      });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        Delete individual stat entries (e.g. a single match).
      </p>
      <div className="text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-700 rounded px-3 py-2">
        ⚠️ This feature requires a{" "}
        <code>GET /api/get_recent_stats</code> endpoint in Flask — see{" "}
        <code>lib/api.ts</code> for details.
      </div>
      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Stats" : "Load Data for Deletion"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => {
              setSelectedId(Number(e.target.value) || null);
              setStep("select");
              setMsg(null);
            }}
          >
            <option value="">— Select entry —</option>
            {stats.map((s) => (
              <option key={s.stat_id} value={s.stat_id}>
                ({s.stat_id}) {s.game_name} — {s.stat_type}: {s.stat_value} @{" "}
                {s.played_at}
              </option>
            ))}
          </select>

          {selectedId && step === "select" && (
            <>
              <p className="text-sm text-yellow-300">
                Delete stat ID {selectedId} —{" "}
                <strong>
                  {selected?.game_name}: {selected?.stat_type} ={" "}
                  {selected?.stat_value}
                </strong>
                ?
              </p>
              <button
                className="btn-sm border-yellow-600 text-yellow-300 hover:bg-yellow-900/30"
                onClick={() => setStep("confirm")}
              >
                Confirm Delete
              </button>
            </>
          )}

          {step === "confirm" && (
            <button
              className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-bold transition-colors"
              onClick={handleDelete}
            >
              DELETE STAT FOREVER
            </button>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </div>
      )}
    </div>
  );
}

// ── Shared feedback ───────────────────────────────────────────────────────────
function Feedback({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div
      className={`rounded px-3 py-2 text-sm ${
        ok
          ? "bg-green-900/30 border border-green-700 text-green-300"
          : "bg-red-900/30 border border-red-700 text-red-300"
      }`}
    >
      {ok ? "✅ " : "❌ "} {text}
    </div>
  );
}
