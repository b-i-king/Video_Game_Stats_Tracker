// Privacy Policy page — mirrors pages/3_Privacy_Policy.py

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "🔒 Privacy Policy",
};

export default function PrivacyPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-6 py-4">
      <h1 className="text-3xl font-bold text-[var(--gold)]">Privacy Policy</h1>
      <p className="text-[var(--muted)] text-sm">Last updated: 2026-04-03</p>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Introduction</h2>
        <p>
          Welcome to <strong>Video Game Stats Tracker</strong> (&quot;the App&quot;),
          operated by <strong>BOL Group LLC</strong>. This Privacy Policy
          describes how we collect, use, and share information when you use our
          application.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Information We Collect</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--text)]">
              Google Account Information
            </strong>{" "}
            — When you sign in with Google we receive your email address and
            public profile. We use this only to authenticate you and determine
            your access level (trusted user vs. registered guest).
          </li>
          <li>
            <strong className="text-[var(--text)]">Gaming Stats</strong> — Stat
            values, game names, session details, and timestamps that you
            voluntarily submit.
          </li>
          <li>
            <strong className="text-[var(--text)]">Usage Data</strong> — Basic
            server logs (IP address, request timestamps) for debugging. We do
            not sell or share this data with third parties.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">How We Use Your Information</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>To authenticate you and manage your access level.</li>
          <li>To store and display your gaming statistics.</li>
          <li>
            To generate chart graphics and social-media posts on your behalf
            (only for trusted users).
          </li>
          <li>
            To improve the App. We do not use your data for advertising.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Data Sharing</h2>
        <p>
          We do not sell or rent your personal data. We may share data with:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--text)]">Google</strong> — for OAuth
            authentication.
          </li>
          <li>
            <strong className="text-[var(--text)]">Supabase</strong> —
            for database storage (hosted on AWS infrastructure).
          </li>
          <li>
            <strong className="text-[var(--text)]">IFTTT / Meta</strong> — to
            post content to Twitter and Instagram at your direction.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Data Retention</h2>
        <p>
          Your data is retained as long as your account is active. You may
          request deletion at any time — see the{" "}
          <a href="/data-deletion" className="text-[var(--gold)] hover:underline">
            Data Deletion
          </a>{" "}
          page.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Contact</h2>
        <p>
          Questions? Email us at{" "}
          <a
            href="mailto:thebolgroup.llc@gmail.com"
            className="text-[var(--gold)] hover:underline"
          >
            thebolgroup.llc@gmail.com
          </a>
          .
        </p>
      </section>
    </div>
  );
}
