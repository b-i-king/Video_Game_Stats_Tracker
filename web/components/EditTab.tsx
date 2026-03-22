"use client";
// EditTab — mirrors the Edit tab from pages/2_Stats.py (trusted users only).
// Sub-tabs: Edit Player | Edit Game | Edit Stats

import { useState } from "react";
import {
  getPlayers,
  getAllGames,
  getRecentStats,
  updatePlayer,
  updateGame,
  updateStats,
  type Player,
  type GameDetails,
  type StatEntry,
} from "@/lib/api";
import { GENRES } from "@/lib/constants";

interface Props {
  jwt: string;
}

type SubTab = "player" | "game" | "stats";

export default function EditTab({ jwt }: Props) {
  const [subTab, setSubTab] = useState<SubTab>("player");

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Edit Data</h2>
      <div className="flex gap-2 border-b border-[var(--border)] pb-2">
        {(["player", "game", "stats"] as SubTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setSubTab(t)}
            className={`px-3 py-1 rounded text-sm capitalize transition-colors ${
              subTab === t
                ? "bg-[var(--gold)] text-black font-semibold"
                : "bg-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            Edit {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {subTab === "player" && <EditPlayer jwt={jwt} />}
      {subTab === "game" && <EditGame jwt={jwt} />}
      {subTab === "stats" && <EditStats jwt={jwt} />}
    </div>
  );
}

// ── Edit Player ───────────────────────────────────────────────────────────────
function EditPlayer({ jwt }: Props) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [newName, setNewName] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    const data = await getPlayers(jwt);
    setPlayers(data);
    setLoaded(true);
    setConfirmed(false);
    setSelectedId(null);
    setMsg(null);
  }

  const selected = players.find((p) => p.player_id === selectedId);

  async function handleUpdate() {
    if (!selectedId || !newName.trim()) return;
    try {
      await updatePlayer(jwt, selectedId, newName.trim());
      setMsg({ ok: true, text: `Renamed to "${newName.trim()}"` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        Select a player profile to rename.
      </p>
      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Players" : "Load Players to Edit"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => {
              setSelectedId(Number(e.target.value) || null);
              setConfirmed(false);
              setNewName("");
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

          {selectedId && !confirmed && (
            <button
              className="btn-sm"
              onClick={() => {
                setConfirmed(true);
                setNewName(selected?.player_name ?? "");
              }}
            >
              Confirm Edit Player
            </button>
          )}

          {confirmed && selected && (
            <div className="space-y-2">
              <p className="text-sm">
                Editing:{" "}
                <strong className="text-[var(--gold)]">
                  {selected.player_name}
                </strong>{" "}
                (ID: {selected.player_id})
              </p>
              <label className="label">New Player Name</label>
              <input
                className="input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <button
                className="btn-primary"
                onClick={handleUpdate}
                disabled={!newName.trim() || newName === selected.player_name}
              >
                Update Player Name
              </button>
            </div>
          )}

          {msg && (
            <Feedback ok={msg.ok} text={msg.text} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Edit Game ─────────────────────────────────────────────────────────────────
function EditGame({ jwt }: Props) {
  const [games, setGames] = useState<GameDetails[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [form, setForm] = useState({
    game_name: "",
    game_series: "",
    game_genre: "Select a Genre",
    game_subgenre: "Select a Subgenre",
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    const data = await getAllGames(jwt);
    setGames(data);
    setLoaded(true);
    setConfirmed(false);
    setSelectedId(null);
    setMsg(null);
  }

  function handleSelect(id: number) {
    setSelectedId(id);
    setConfirmed(false);
    setMsg(null);
    const g = games.find((g) => g.game_id === id);
    if (g) {
      setForm({
        game_name: g.game_name,
        game_series: g.game_series ?? "",
        game_genre: g.game_genre ?? "Select a Genre",
        game_subgenre: g.game_subgenre ?? "Select a Subgenre",
      });
    }
  }

  async function handleUpdate() {
    if (!selectedId) return;
    try {
      await updateGame(jwt, selectedId, form);
      setMsg({ ok: true, text: "Game updated successfully." });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  const subgenreOptions =
    GENRES[form.game_genre] ?? ["Select a Subgenre"];

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        Select a game to edit its details.
      </p>
      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Games" : "Load Games to Edit"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => handleSelect(Number(e.target.value))}
          >
            <option value="">— Select game —</option>
            {games.map((g) => (
              <option key={g.game_id} value={g.game_id}>
                {g.game_name}
              </option>
            ))}
          </select>

          {selectedId && !confirmed && (
            <button className="btn-sm" onClick={() => setConfirmed(true)}>
              Confirm Edit Game
            </button>
          )}

          {confirmed && selectedId && (
            <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <p className="text-sm">
                Editing game ID:{" "}
                <strong className="text-[var(--gold)]">{selectedId}</strong>
              </p>

              <div>
                <label className="label">Game Name</label>
                <input
                  className="input"
                  value={form.game_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, game_name: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Game Series</label>
                <input
                  className="input"
                  value={form.game_series}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, game_series: e.target.value }))
                  }
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Game Genre *</label>
                  <select
                    className="input"
                    value={form.game_genre}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        game_genre: e.target.value,
                        game_subgenre: "Select a Subgenre",
                      }))
                    }
                  >
                    {Object.keys(GENRES).map((g) => (
                      <option key={g}>{g}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Game Subgenre *</label>
                  <select
                    className="input"
                    value={form.game_subgenre}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, game_subgenre: e.target.value }))
                    }
                  >
                    {subgenreOptions.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <button className="btn-primary" onClick={handleUpdate}>
                Update Game Details
              </button>
            </div>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </div>
      )}
    </div>
  );
}

// ── Edit Stats ────────────────────────────────────────────────────────────────
function EditStats({ jwt }: Props) {
  const [stats, setStats] = useState<StatEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [form, setForm] = useState<Partial<StatEntry>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    try {
      const data = await getRecentStats(jwt);
      setStats(data);
      setLoaded(true);
      setConfirmed(false);
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  function handleSelect(id: number) {
    setSelectedId(id);
    setConfirmed(false);
    const entry = stats.find((s) => s.stat_id === id);
    if (entry) setForm({ ...entry });
  }

  async function handleUpdate() {
    if (!selectedId) return;
    try {
      await updateStats(jwt, selectedId, form);
      setMsg({ ok: true, text: "Entry updated successfully." });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  }

  const selected = stats.find((s) => s.stat_id === selectedId);

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--muted)]">
        Edit individual stat entries (e.g. a single match).
      </p>
      <div className="text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-700 rounded px-3 py-2">
        ⚠️ This feature requires a{" "}
        <code className="text-xs">GET /api/get_recent_stats</code> and{" "}
        <code className="text-xs">PUT /api/update_stats/:id</code> endpoint in
        Flask — see <code className="text-xs">lib/api.ts</code> for details.
      </div>

      <button className="btn-sm" onClick={load}>
        {loaded ? "Reload Stats" : "Load Data for Editing"}
      </button>

      {loaded && (
        <div className="space-y-3">
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => handleSelect(Number(e.target.value))}
          >
            <option value="">— Select entry —</option>
            {stats.map((s) => (
              <option key={s.stat_id} value={s.stat_id}>
                ({s.stat_id}) {s.game_name} — {s.stat_type}: {s.stat_value} @{" "}
                {s.played_at}
              </option>
            ))}
          </select>

          {selectedId && !confirmed && (
            <button className="btn-sm" onClick={() => setConfirmed(true)}>
              Confirm Edit Selection
            </button>
          )}

          {confirmed && selected && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
              <p className="text-sm">
                Editing:{" "}
                <strong className="text-[var(--gold)]">
                  ({selected.stat_id}) {selected.game_name} — {selected.stat_type}
                </strong>
              </p>

              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Stat Type</label>
                  <input
                    className="input"
                    value={form.stat_type ?? ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, stat_type: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="label">Stat Value</label>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    value={form.stat_value ?? 0}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        stat_value: parseInt(e.target.value) || 0,
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="label">Game Mode</label>
                  <input
                    className="input"
                    value={form.game_mode ?? ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, game_mode: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="label">Game Level / Wave</label>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    value={form.game_level ?? 0}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        game_level: parseInt(e.target.value) || 0,
                      }))
                    }
                  />
                </div>
              </div>

              <button className="btn-primary" onClick={handleUpdate}>
                Update Entry
              </button>
            </div>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </div>
      )}
    </div>
  );
}

// ── Shared feedback component ─────────────────────────────────────────────────
function Feedback({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div
      className={`rounded px-3 py-2 text-sm ${
        ok
          ? "bg-green-900/30 border border-green-700 text-green-300"
          : "bg-red-900/30 border border-red-700 text-red-300"
      }`}
    >
      {ok ? "✅ " : "❌ "}
      {text}
    </div>
  );
}
