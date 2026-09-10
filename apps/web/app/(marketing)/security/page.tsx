import type { Metadata } from "next";
import Link from "next/link";
import {
  PageIntro,
  TrialCallout,
} from "@/components/marketing/marketing-components";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Security and trust",
  "Understand Oryntela's tenant isolation, role-aware access, reviewed actions, encrypted connector credentials, Deal Room controls and data lifecycle boundaries.",
  "/security",
);

const controls = [
  {
    title: "Tenant isolation",
    body: "Organisation scope is derived from verified identity and membership context. Repository predicates and forced PostgreSQL row-level security provide separate layers of tenant isolation.",
  },
  {
    title: "Role-aware access",
    body: "Administrative and high-consequence workflows use explicit role checks. Missing organisation or membership context fails closed.",
  },
  {
    title: "Human approval",
    body: "Suggested claims, customer communication, CRM write-back and Closed-Won Handover remain reviewable. Oryntela does not let an internal inference approve its own consequence.",
  },
  {
    title: "Credential protection",
    body: "Connector credentials use AES-256-GCM envelopes with tenant- and connection-bound associated data. Token material stays out of browser contracts, logs, audits and exports.",
  },
  {
    title: "Buyer-safe Deal Rooms",
    body: "Deal Room links use high-entropy one-time token delivery with only a SHA-256 digest stored. Published snapshots are read-only, positive allow-listed, revocable and excluded from search indexing.",
  },
  {
    title: "Data minimisation",
    body: "Oryntela separates customer Evidence, seller judgement, public research and generated material. It does not copy private deal intelligence into buyer views automatically.",
  },
] as const;

export default function SecurityPage() {
  return (
    <>
      <section className="px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:px-12">
        <PageIntro
          eyebrow="Security and trust"
          title="Trust comes from product behaviour, not a badge."
          description="Oryntela is designed to keep organisations separate, evidence traceable, consequential actions reviewed and customer-facing material deliberately selected."
        />
      </section>

      <section className="px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-5 md:grid-cols-2 lg:grid-cols-3">
          {controls.map((control, index) => (
            <article
              key={control.title}
              className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 shadow-sm"
            >
              <span className="text-xs font-bold tracking-[0.18em] text-brand-secondary">
                0{index + 1}
              </span>
              <h2 className="mt-8 text-2xl font-semibold tracking-[-0.03em] text-brand-primary">
                {control.title}
              </h2>
              <p className="mt-4 text-sm leading-7 text-brand-muted">
                {control.body}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section bg-brand-primary px-5 text-brand-primary-foreground sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:items-start lg:gap-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-accent">
              Clear boundaries
            </p>
            <h2 className="mt-4 text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl">
              We will not claim assurance that does not exist.
            </h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              "No SOC 2 claim",
              "No ISO 27001 claim",
              "No penetration-test claim",
              "No Australian data-residency claim",
              "No production provider is active",
              "No customer data is in the current build",
            ].map((boundary) => (
              <div
                key={boundary}
                className="rounded-2xl border border-white/10 bg-white/5 p-5 text-sm font-semibold text-slate-200"
              >
                {boundary}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-2">
          <article className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 sm:p-9">
            <p className="marketing-eyebrow">Export and deletion</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-brand-primary">
              Data lifecycle workflows are built into the product.
            </h2>
            <p className="mt-5 text-sm leading-7 text-brand-muted">
              Organisation-scoped export and reviewed deletion workflows cover
              current product data. Production retention, backup expiry and
              provider-processing terms must still be approved and published
              before customer data is accepted.
            </p>
          </article>
          <article className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 sm:p-9">
            <p className="marketing-eyebrow">Ask a security question</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-brand-primary">
              Get a direct, evidence-based answer.
            </h2>
            <p className="mt-5 text-sm leading-7 text-brand-muted">
              We would rather explain an implemented control and its limits than
              hide behind broad security language.
            </p>
            <a
              className="mt-6 inline-flex min-h-11 items-center rounded-lg text-sm font-bold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
              href="mailto:support@oryntela.com.au?subject=Oryntela%20security%20question"
            >
              support@oryntela.com.au
            </a>
          </article>
        </div>
        <p className="mx-auto mt-8 max-w-7xl text-xs leading-6 text-brand-muted">
          Looking for legal notices? The current repository does not yet contain
          owner-approved public Privacy or Terms content. See the honest status
          on the{" "}
          <Link className="font-bold underline" href="/privacy">
            Privacy
          </Link>{" "}
          and{" "}
          <Link className="font-bold underline" href="/terms">
            Terms
          </Link>{" "}
          pages.
        </p>
      </section>

      <TrialCallout heading="Bring security and commercial questions into the first conversation." />
    </>
  );
}
