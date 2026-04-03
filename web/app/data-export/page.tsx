// Data Export page — manual request now; self-service in Phase 3

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Export",
};

export default function DataExportPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-6 py-4">
      <h1 className="text-3xl font-bold text-[var(--gold)]">
        Export Your Data
      </h1>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Request a Manual Export</h2>
        <p>
          You can request a full export of all data associated with your
          account at any time. We will send you a file within{" "}
          <strong>5 business days</strong>.
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
            <em>&ldquo;Data Export Request&rdquo;</em>.
          </li>
          <li>
            <strong className="text-[var(--text)]">Include your account email</strong>{" "}
            — the Google address you use to sign in.
          </li>
          <li>
            <strong className="text-[var(--text)]">Specify a format</strong>{" "}
            — CSV (spreadsheet-friendly) or JSON (developer-friendly). If you
            don&apos;t specify, we&apos;ll send both.
          </li>
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">What&apos;s Included</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>All player profiles you created.</li>
          <li>
            All gaming session records — game name, stat type, value,
            timestamp, and session ID.
          </li>
          <li>Account metadata — email, tier, created date.</li>
          <li>Bolt AI usage history (prompt + response log).</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Self-Service Export — Coming in Phase 3</h2>
        <p className="text-[var(--muted)]">
          A one-click export tool is planned for Phase 3. It will let you
          download your stats directly from this page in CSV or JSON format
          without needing to email us.
        </p>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          Self-service export is not yet available. Please use the manual
          request process above.
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Want to delete your data instead?</h2>
        <p className="text-[var(--muted)]">
          See the{" "}
          <a href="/data-deletion" className="text-[var(--gold)] hover:underline">
            Data Deletion
          </a>{" "}
          page for instructions on requesting full account removal.
        </p>
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
