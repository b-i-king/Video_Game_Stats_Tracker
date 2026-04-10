"use client";

import { useEffect, useRef, useState } from "react";
import { askBolt, getAiUsage, AiUsage } from "@/lib/api";

interface Message {
  role: "user" | "bolt";
  text: string;
}

const SUGGESTIONS = [
  "What's my best session?",
  "Write an Instagram caption",
  "How's my Eliminations trending?",
  "Summarize this week",
];

export default function BoltPanel({
  jwt,
  isOwner = false,
}: {
  jwt: string;
  isOwner?: boolean;
}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "bolt",
      text: "Hey! I'm Bolt ⚡ — your personal gaming analyst from BOL Group. Ask me about your stats, trends, or let me write a caption for your next post.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [usage, setUsage] = useState<AiUsage | null>(null);
  const [simulateRole, setSimulateRole] = useState<
    "free" | "premium" | "trusted" | undefined
  >(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAiUsage(jwt, simulateRole)
      .then(setUsage)
      .catch(() => {});
  }, [jwt, simulateRole]);

  async function send(text: string) {
    const trimmed = text.trim().slice(0, 500);
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const reply = await askBolt(jwt, trimmed);
      setMessages((prev) => [...prev, { role: "bolt", text: reply }]);
      // Optimistic: instant UI update
      setUsage((prev) => prev ? { ...prev, used: prev.used + 1 } : prev);
      // Sync: re-fetch real DB value after backend INSERT commits
      setTimeout(() => {
        getAiUsage(jwt, simulateRole).then(setUsage).catch(() => {});
      }, 1000);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "bolt",
          text: "I couldn't reach the server right now. Try again in a moment.",
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  // Derive bar colour: gold < 70%, yellow 70–90%, red > 90%
  function barColor(used: number, limit: number): string {
    const pct = used / limit;
    if (pct >= 0.9) return "bg-red-500";
    if (pct >= 0.7) return "bg-yellow-400";
    return "bg-[var(--gold)]";
  }

  return (
    <div className="h-full rounded-lg border border-[var(--border)] bg-[var(--surface)] flex flex-col">
      {/* Header */}
      <div className="px-4 pt-4 pb-2 border-b border-[var(--border)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚡</span>
            <span className="font-semibold text-sm text-[var(--gold)]">Bolt</span>
          </div>
          {/* Owner simulate-role picker */}
          {isOwner && (
            <select
              value={simulateRole ?? ""}
              onChange={(e) =>
                setSimulateRole(
                  (e.target.value as "free" | "premium" | "trusted") || undefined
                )
              }
              className="text-[10px] rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] px-1 py-0.5 focus:outline-none focus:border-[var(--gold)]"
            >
              <option value="">Owner view</option>
              <option value="trusted">Simulate: Trusted</option>
              <option value="premium">Simulate: Premium</option>
              <option value="free">Simulate: Free</option>
            </select>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <p className="text-xs text-[var(--muted)]">by BOL · Powered by Gemini</p>
          {usage?.simulating && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-400/20 text-yellow-400 border border-yellow-400/40">
              simulating {usage.simulating}
            </span>
          )}
        </div>

        {/* Usage bar */}
        {usage && (
          <div className="mt-2">
            {usage.is_unlimited ? (
              <p className="text-[10px] text-[var(--muted)]">
                {usage.used} quer{usage.used === 1 ? "y" : "ies"} this month · unlimited
              </p>
            ) : (
              <>
                <div className="flex justify-between text-[10px] text-[var(--muted)] mb-1">
                  <span>{usage.used} / {usage.limit} queries</span>
                  <span>resets {usage.reset_date}</span>
                </div>
                <div className="h-1 rounded-full bg-[var(--border)] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barColor(usage.used, usage.limit!)}`}
                    style={{ width: `${Math.min((usage.used / usage.limit!) * 100, 100)}%` }}
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-xs rounded-lg px-3 py-2 max-w-[95%] leading-relaxed whitespace-pre-wrap ${
              m.role === "user"
                ? "ml-auto bg-[var(--gold)] text-black font-medium"
                : "bg-[var(--border)] text-[var(--text)]"
            }`}
          >
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="bg-[var(--border)] text-[var(--muted)] text-xs rounded-lg px-3 py-2 w-fit animate-pulse">
            Bolt is thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions — shown only before first user message */}
      {messages.length <= 1 && (
        <div className="px-3 pb-2 flex flex-col gap-1">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-left text-xs px-2 py-1.5 rounded border border-[var(--border)] hover:border-[var(--gold)] text-[var(--muted)] hover:text-[var(--gold)] transition-colors truncate"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 pb-3 pt-2 flex gap-2 border-t border-[var(--border)]">
        <input
          className="flex-1 text-xs rounded border border-[var(--border)] bg-transparent px-2 py-1.5 text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--gold)]"
          placeholder="Ask Bolt…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={loading}
          maxLength={500}
        />
        <button
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          className="text-xs px-2 py-1.5 rounded bg-[var(--gold)] text-black font-semibold disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
