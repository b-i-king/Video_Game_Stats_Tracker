"use client";

import { useRef, useState } from "react";
import { askBolt } from "@/lib/api";

interface Message {
  role: "user" | "bolt";
  text: string;
}

const SUGGESTIONS = [
  "What's my best session?",
  "Write an Instagram caption",
  "How's my KD trending?",
  "Summarize this week",
];

export default function BoltPanel({ jwt }: { jwt: string }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "bolt",
      text: "Hey! I'm Bolt ⚡ — your personal gaming analyst from Beacon of Light. Ask me about your stats, trends, or let me write a caption for your next post.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const reply = await askBolt(jwt, trimmed);
      setMessages((prev) => [...prev, { role: "bolt", text: reply }]);
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

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] flex flex-col h-full min-h-[420px]">
      {/* Header */}
      <div className="px-4 pt-4 pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚡</span>
          <span className="font-semibold text-sm text-[var(--gold)]">Bolt</span>
        </div>
        <p className="text-xs text-[var(--muted)] mt-0.5">
          by Beacon of Light · Powered by Gemini
        </p>
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
