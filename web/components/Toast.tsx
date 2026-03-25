"use client";

import { createContext, useCallback, useContext, useState, ReactNode } from "react";

type ToastLevel = "success" | "error" | "info";

interface ToastItem {
  id: number;
  msg: string;
  level: ToastLevel;
}

interface ToastCtx {
  showToast: (msg: string, level?: ToastLevel) => void;
}

const ToastContext = createContext<ToastCtx>({ showToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((msg: string, level: ToastLevel = "success") => {
    const id = ++_nextId;
    setToasts((prev) => [...prev, { id, msg, level }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-20 right-4 z-50 flex flex-col gap-2 pointer-events-none lg:bottom-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-lg text-sm font-medium shadow-lg pointer-events-auto border ${
              t.level === "success"
                ? "bg-green-900 text-green-100 border-green-600"
                : t.level === "error"
                ? "bg-red-900 text-red-100 border-red-600"
                : "bg-[var(--surface)] text-[var(--text)] border-[var(--border)]"
            }`}
          >
            {t.level === "success" ? "✅ " : t.level === "error" ? "❌ " : "ℹ️ "}
            {t.msg}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
