"use client";

import { useState } from "react";

// msg is passed from the Server Component (layout.tsx) which reads it from
// Vercel Edge Config. When empty the banner renders nothing.
export default function MaintenanceBanner({ msg }: { msg: string }) {
  const [dismissed, setDismissed] = useState(false);
  if (!msg || dismissed) return null;

  return (
    <div className="w-full bg-yellow-900/80 border-b border-yellow-700 px-4 py-2 flex items-center justify-between gap-3 text-sm text-yellow-200">
      <span>
        <span className="font-semibold mr-2">🔧 Maintenance:</span>
        {msg}
      </span>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="shrink-0 text-yellow-400 hover:text-yellow-100 transition-colors text-lg leading-none"
      >
        ×
      </button>
    </div>
  );
}
