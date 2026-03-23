"use client";

// Fires a single GET /health ping on every page load to wake the Render
// service before the user clicks Sign In. No auth needed, no UI rendered.
import { useEffect } from "react";
import { pingHealth } from "@/lib/api";

export default function RenderWarmup() {
  useEffect(() => {
    pingHealth();
  }, []);

  return null;
}
