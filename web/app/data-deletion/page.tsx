// Data Deletion page — mirrors pages/5_Data_Deletion.py

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Deletion | Game Tracker",
};

export default function DataDeletionPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-6 py-4">
      <h1 className="text-3xl font-bold text-[var(--gold)]">
        Data Deletion Instructions
      </h1>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">How to Delete Your Data</h2>
        <p>
          You can request deletion of all personal data associated with your
          account at any time. Follow the steps below:
        </p>

        <ol className="list-decimal pl-6 space-y-3 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--text)]">
              Email us directly:
            </strong>{" "}
            Send an email to{" "}
            <a
              href="mailto:thebolgroup.llc@gmail.com"
              className="text-[var(--gold)] hover:underline"
            >
              thebolgroup.llc@gmail.com
            </a>{" "}
            with the subject line{" "}
            <em>&ldquo;Data Deletion Request&rdquo;</em> and include the Google
            email address linked to your account.
          </li>
          <li>
            <strong className="text-[var(--text)]">
              We will confirm within 5 business days
            </strong>{" "}
            and delete all data (player profiles, game stats, session records)
            associated with your account within 30 days.
          </li>
          <li>
            <strong className="text-[var(--text)]">
              Revoke app permissions in Google
            </strong>{" "}
            by going to{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--gold)] hover:underline"
            >
              myaccount.google.com/permissions
            </a>{" "}
            and removing <em>Video Game Stats Tracker</em>.
          </li>
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">What Gets Deleted</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>Your Google email address from our records.</li>
          <li>All player profiles you created.</li>
          <li>All gaming session statistics you submitted.</li>
          <li>All associated chart images stored in Google Cloud Storage.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Facebook / Meta</h2>
        <p>
          If you connected this app via a Facebook/Meta integration, you can
          also use Meta&apos;s built-in data deletion flow. Visit{" "}
          <a
            href="https://www.facebook.com/settings?tab=applications"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--gold)] hover:underline"
          >
            Facebook App Settings
          </a>{" "}
          and remove the app, then email us at the address above to confirm
          server-side deletion.
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
