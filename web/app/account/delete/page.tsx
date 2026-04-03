// Delete Account page — manual flow now; automated cascade in Phase 3

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Delete Account",
};

export default function DeleteAccountPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-6 py-4">
      <h1 className="text-3xl font-bold text-red-400">Delete Your Account</h1>

      <div className="not-prose rounded-lg border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-300">
        <strong>This action is permanent.</strong> Deleting your account
        removes all personal data and cannot be undone. Export your data first
        if you want a copy.
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Before You Delete</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>
            <a href="/data-export" className="text-[var(--gold)] hover:underline">
              Request a data export
            </a>{" "}
            if you want a copy of your stats in CSV or JSON format.
          </li>
          <li>
            If you connected a Riot Games account, your Riot data is not
            stored by us — it is only fetched on demand. No action needed
            there.
          </li>
          <li>
            Revoke Google OAuth access at{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--gold)] hover:underline"
            >
              myaccount.google.com/permissions
            </a>{" "}
            to remove the app from your Google account.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">How to Delete Your Account</h2>
        <p>
          Automated account deletion is coming in Phase 3. For now, submit a
          manual request:
        </p>

        <ol className="list-decimal pl-6 space-y-3 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--text)]">Email us:</strong> Send a
            message to{" "}
            <a
              href="mailto:thebolgroup.llc@gmail.com"
              className="text-[var(--gold)] hover:underline"
            >
              thebolgroup.llc@gmail.com
            </a>{" "}
            with the subject line{" "}
            <em>&ldquo;Account Deletion Request&rdquo;</em>.
          </li>
          <li>
            <strong className="text-[var(--text)]">Include your account email</strong>{" "}
            — the Google address you use to sign in.
          </li>
          <li>
            We will confirm within <strong className="text-[var(--text)]">5 business days</strong> and
            complete deletion within <strong className="text-[var(--text)]">30 days</strong>.
          </li>
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">What Gets Deleted</h2>
        <p>
          See the{" "}
          <a href="/data-deletion" className="text-[var(--gold)] hover:underline">
            Data Deletion
          </a>{" "}
          page for a full list of what is and is not removed.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Self-Service Deletion — Coming in Phase 3</h2>
        <p className="text-[var(--muted)]">
          Phase 3 will add a one-click account deletion flow directly on this
          page. It will cascade across all tables — player profiles, session
          stats, Bolt usage, social post logs, and connected integrations —
          with a 24-hour grace period before data is permanently erased.
        </p>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          Self-service deletion is not yet available. Please use the manual
          request process above.
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Contact</h2>
        <p>
          <a
            href="mailto:thebolgroup.llc@gmail.com"
            className="text-[var(--gold)] hover:underline"
          >
            thebolgroup.llc@gmail.com
          </a>
        </p>
      </section>
    </div>
  );
}
