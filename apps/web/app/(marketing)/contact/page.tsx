import type { Metadata } from "next";
import { PageIntro } from "@/components/marketing/marketing-components";
import { createMarketingMetadata, trialOffer } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Contact",
  "Contact Oryntela to request trial access, book a product demo, ask a commercial question or reach support.",
  "/contact",
);

const contactOptions = [
  {
    id: "trial",
    eyebrow: "Trial access",
    title: `Request a ${trialOffer.lengthDays}-day Complete trial`,
    body: "Tell us about your team and what you want to improve. We will confirm availability and activation readiness before any workspace is opened.",
    label: "Request trial access",
    href: "mailto:hello@oryntela.com.au?subject=Oryntela%20trial%20access%20request",
  },
  {
    id: "demo",
    eyebrow: "Product demo",
    title: "See the full process in context",
    body: "Book a practical conversation about Prospect, Sales Brain, Native CRM, forecasting, Deal Room and Handover—based on the parts relevant to your team.",
    label: "Book a demo by email",
    href: "mailto:hello@oryntela.com.au?subject=Oryntela%20demo%20request",
  },
  {
    id: "support",
    eyebrow: "Customer support",
    title: "Get help with Oryntela",
    body: "For product, access, privacy or security support, contact the approved Oryntela support address.",
    label: "Contact support",
    href: "mailto:support@oryntela.com.au",
  },
] as const;

export default function ContactPage() {
  return (
    <>
      <section className="px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:px-12">
        <PageIntro
          eyebrow="Contact Oryntela"
          title="Start with the conversation your team needs."
          description="We are preparing Oryntela for Australian B2B teams. Public self-service signup is not active yet, so every trial and demo request starts with a direct Oryntela conversation."
        />
      </section>

      <section className="px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-3">
          {contactOptions.map((option) => (
            <article
              id={option.id}
              key={option.id}
              className="scroll-mt-28 rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 shadow-sm sm:p-8"
            >
              <p className="marketing-eyebrow">{option.eyebrow}</p>
              <h2 className="mt-5 text-2xl font-semibold leading-8 tracking-[-0.03em] text-brand-primary">
                {option.title}
              </h2>
              <p className="mt-4 text-sm leading-7 text-brand-muted">
                {option.body}
              </p>
              <a
                className="marketing-primary-button mt-8 w-full"
                href={option.href}
              >
                {option.label}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section border-y border-brand-primary/10 bg-white px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-2 md:items-start">
          <div>
            <p className="marketing-eyebrow">About Oryntela</p>
            <h2 className="marketing-section-title mt-4">
              Built for relationship-driven sales teams.
            </h2>
            <p className="mt-5 text-base leading-8 text-brand-muted">
              Oryntela is an Australian end-to-end sales platform. Its purpose
              is simple: connect the work around a sale so leaders, managers and
              sellers know what is happening and what to do next.
            </p>
          </div>
          <dl className="rounded-[1.75rem] bg-brand-background p-7 sm:p-8">
            <div>
              <dt className="text-xs font-bold uppercase tracking-[0.14em] text-brand-muted">
                Product brand
              </dt>
              <dd className="mt-2 text-lg font-semibold text-brand-primary">
                Oryntela
              </dd>
            </div>
            <div className="mt-6 border-t border-brand-primary/10 pt-6">
              <dt className="text-xs font-bold uppercase tracking-[0.14em] text-brand-muted">
                Operated by
              </dt>
              <dd className="mt-2 text-lg font-semibold text-brand-primary">
                Management Services Australia Pty. Ltd.
              </dd>
            </div>
            <div className="mt-6 border-t border-brand-primary/10 pt-6">
              <dt className="text-xs font-bold uppercase tracking-[0.14em] text-brand-muted">
                ABN
              </dt>
              <dd className="mt-2 text-lg font-semibold tabular-nums text-brand-primary">
                15 113 119 556
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </>
  );
}
