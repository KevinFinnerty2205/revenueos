import type { Metadata } from "next";
import Link from "next/link";
import {
  PageIntro,
  TrialCallout,
} from "@/components/marketing/marketing-components";
import { createMarketingMetadata, integrations } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Integrations",
  "See how Oryntela is built to work with Microsoft 365, Google Workspace, HubSpot and Salesforce, with honest pre-launch activation status.",
  "/integrations",
);

export default function IntegrationsPage() {
  return (
    <>
      <section className="px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:px-12">
        <PageIntro
          eyebrow="Integrations"
          title="Keep the systems your team already relies on."
          description="Oryntela is built to connect sales context with business mailboxes, calendars and supported CRMs—without hiding which system owns the record or whether an external action succeeded."
        />
      </section>

      <section className="px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="rounded-[1.75rem] border border-brand-accent/25 bg-brand-accent/8 p-6 sm:p-8">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
              Pre-launch status
            </p>
            <p className="mt-3 max-w-4xl text-base leading-8 text-brand-primary">
              Integration code is complete for the four providers below, but no
              production provider has been activated. Production connections
              will be enabled only after launch configuration, provider checks
              and the customer&apos;s authorisation are complete.
            </p>
          </div>

          <div className="mt-8 grid gap-5 md:grid-cols-2">
            {integrations.map((integration) => (
              <article
                key={integration.name}
                className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 shadow-sm sm:p-8"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div
                    aria-hidden="true"
                    className="grid size-12 place-items-center rounded-2xl bg-brand-primary text-lg font-bold text-white"
                  >
                    {integration.name.charAt(0)}
                  </div>
                  <span className="rounded-full border border-brand-secondary/20 bg-brand-secondary/8 px-3 py-1.5 text-xs font-bold text-brand-secondary">
                    Built · activation pending
                  </span>
                </div>
                <h2 className="mt-7 text-3xl font-semibold tracking-[-0.035em] text-brand-primary">
                  {integration.name}
                </h2>
                <p className="mt-4 text-sm leading-7 text-brand-muted">
                  {integration.scope}.
                </p>
                <p className="mt-5 border-t border-brand-primary/10 pt-5 text-xs leading-6 text-brand-muted">
                  Not yet production-active. Availability is subject to customer
                  account authority, provider approval and launch activation.
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-section bg-brand-primary px-5 text-brand-primary-foreground sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-2 lg:items-center lg:gap-16">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-accent">
              Native by default
            </p>
            <h2 className="mt-4 text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl">
              Oryntela CRM works without an external CRM.
            </h2>
          </div>
          <div>
            <p className="text-base leading-8 text-slate-300">
              Core includes companies, people, opportunities, Pipeline and the
              relationship context Sales Brain needs. Teams can choose Oryntela
              as their system of record instead of waiting for a connector.
            </p>
            <Link
              href="/platform#run"
              className="mt-7 inline-flex min-h-11 items-center rounded-lg text-sm font-bold text-white underline decoration-brand-accent decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-accent"
            >
              Explore Oryntela CRM →
            </Link>
          </div>
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-6 md:grid-cols-3">
          {[
            [
              "Authority stays visible",
              "Oryntela keeps provider-owned and Oryntela-owned fields distinct instead of silently overwriting records.",
            ],
            [
              "Writes stay reviewed",
              "Customer messages and CRM write-back are designed around explicit preview, confirmation and reconciliation.",
            ],
            [
              "Credentials stay server-side",
              "Connector tokens are encrypted and excluded from browser contracts, exports, audits and logs.",
            ],
          ].map(([title, body]) => (
            <article
              key={title}
              className="rounded-3xl border border-brand-primary/10 bg-white p-7"
            >
              <h2 className="text-xl font-semibold tracking-[-0.025em] text-brand-primary">
                {title}
              </h2>
              <p className="mt-3 text-sm leading-7 text-brand-muted">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <TrialCallout heading="Choose the right system-of-record path for your team." />
    </>
  );
}
