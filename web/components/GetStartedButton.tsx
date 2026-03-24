"use client";

import { signIn } from "next-auth/react";

export default function GetStartedButton() {
  return (
    <button
      className="px-5 py-2 rounded bg-[var(--gold)] text-black font-semibold hover:opacity-90 transition-opacity"
      onClick={() => signIn("google", { callbackUrl: "/stats" })}
    >
      Get Started →
    </button>
  );
}
