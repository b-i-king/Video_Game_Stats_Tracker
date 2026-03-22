// Terms of Service page — mirrors pages/4_Terms_of_Service.py

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service | Game Tracker",
};

export default function TermsPage() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto space-y-6 py-4">
      <h1 className="text-3xl font-bold text-[var(--gold)]">
        Terms of Service
      </h1>
      <p className="text-[var(--muted)] text-sm">Last updated: 2026-03-22</p>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Acceptance of Terms</h2>
        <p>
          By using <strong>Video Game Stats Tracker</strong> ("the App") you
          agree to these Terms of Service. If you do not agree, please do not
          use the App.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Use of the App</h2>
        <ul className="list-disc pl-6 space-y-2 text-[var(--muted)]">
          <li>
            The App is provided for personal, non-commercial use to track your
            own gaming statistics.
          </li>
          <li>
            You are responsible for all data you submit. Do not submit
            misleading, harmful, or unlawful content.
          </li>
          <li>
            Automated or bulk submissions are not permitted without prior
            written approval.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Intellectual Property</h2>
        <p>
          All App code, graphics, and design elements are owned by BOL Group
          LLC. Game names and trademarks belong to their respective owners.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Disclaimer of Warranties</h2>
        <p>
          The App is provided &ldquo;as is&rdquo; without any warranties. We do
          not guarantee uptime, accuracy, or availability.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Limitation of Liability</h2>
        <p>
          BOL Group LLC is not liable for any indirect, incidental, or
          consequential damages arising from your use of the App.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Changes to These Terms</h2>
        <p>
          We may update these Terms at any time. Continued use of the App after
          changes constitutes acceptance.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Contact</h2>
        <p>
          Questions? Email{" "}
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
