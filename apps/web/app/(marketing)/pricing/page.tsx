import type { Metadata } from "next";
import Link from "next/link";
import {
  PageIntro,
  TrialCallout,
} from "@/components/marketing/marketing-components";
import {
  createMarketingMetadata,
  formatAud,
  pricingPlans,
  trialOffer,
} from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Pricing",
  "Compare Oryntela Core, Growth, Complete and Enterprise plans in AUD, with transparent annual prepayment and a 14-day Complete trial.",
  "/pricing",
);

export default function PricingPage() {
  return (
    <>
      <section className="px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:px-12">
        <PageIntro
          eyebrow="Simple pricing in AUD"
          title="Choose the sales system your team needs now."
          description="Native CRM and the core operating loop start with Core. Add controlled prospecting and outreach with Growth, then customer-ready creation and supported CRM connectors with Complete."
        />
      </section>

      <section className="px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-5 md:grid-cols-2 xl:grid-cols-4">
          {pricingPlans.map((plan) => {
            const complete = plan.code === "complete";
            return (
              <article
                key={plan.code}
                className={`flex flex-col rounded-[1.75rem] border p-7 shadow-sm ${
                  complete
                    ? "border-brand-primary bg-brand-primary text-white"
                    : "border-brand-primary/10 bg-white text-brand-primary"
                }`}
              >
                <div>
                  <p
                    className={`text-xs font-bold uppercase tracking-[0.18em] ${
                      complete ? "text-brand-accent" : "text-brand-secondary"
                    }`}
                  >
                    {plan.name}
                  </p>
                  {plan.monthlyAmount === null ? (
                    <p className="mt-5 text-4xl font-semibold tracking-[-0.04em]">
                      Custom
                    </p>
                  ) : (
                    <p className="mt-5 text-4xl font-semibold tracking-[-0.04em]">
                      {formatAud(plan.monthlyAmount)}
                      <span
                        className={`ml-1 text-sm font-medium tracking-normal ${
                          complete ? "text-slate-300" : "text-brand-muted"
                        }`}
                      >
                        /month
                      </span>
                    </p>
                  )}
                  <p
                    className={`mt-3 min-h-14 text-sm leading-6 ${
                      complete ? "text-slate-300" : "text-brand-muted"
                    }`}
                  >
                    {plan.description}
                  </p>
                </div>

                <div
                  className={`mt-6 border-y py-5 ${
                    complete ? "border-white/10" : "border-brand-primary/10"
                  }`}
                >
                  {plan.annualAmount === null ? (
                    <p className="text-sm font-semibold">
                      Commercial terms agreed directly
                    </p>
                  ) : (
                    <>
                      <p className="text-lg font-semibold">
                        {formatAud(plan.annualAmount)}/year
                      </p>
                      <p
                        className={`mt-1 text-xs leading-5 ${
                          complete ? "text-slate-300" : "text-brand-muted"
                        }`}
                      >
                        Billed annually as an annual prepayment
                      </p>
                    </>
                  )}
                  <p
                    className={`mt-4 text-sm font-semibold ${
                      complete ? "text-white" : "text-brand-primary"
                    }`}
                  >
                    {plan.includedUsers === null
                      ? "Custom user limit"
                      : `${plan.includedUsers} users included`}
                  </p>
                </div>

                <ul className="mt-6 flex-1 space-y-3">
                  {plan.includes.map((item) => (
                    <li key={item} className="flex gap-3 text-sm leading-6">
                      <span
                        aria-hidden="true"
                        className={`mt-2 size-1.5 shrink-0 rounded-full ${
                          complete ? "bg-brand-accent" : "bg-brand-secondary"
                        }`}
                      />
                      <span
                        className={
                          complete ? "text-slate-200" : "text-brand-muted"
                        }
                      >
                        {item}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={
                    plan.code === "enterprise"
                      ? "/contact#demo"
                      : "/contact#trial"
                  }
                  className={`mt-8 inline-flex min-h-12 items-center justify-center rounded-full px-5 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-brand-focus ${
                    complete
                      ? "bg-white text-brand-primary hover:bg-brand-background"
                      : "bg-brand-primary text-white hover:bg-brand-secondary"
                  }`}
                >
                  {plan.code === "enterprise"
                    ? "Contact us"
                    : "Request trial access"}
                </Link>
              </article>
            );
          })}
        </div>
      </section>

      <section className="marketing-section border-y border-brand-primary/10 bg-white px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="marketing-eyebrow">Trial terms</p>
            <h2 className="marketing-section-title mt-4">
              {trialOffer.lengthDays} days with Complete-level modules.
            </h2>
          </div>
          <dl className="grid grid-cols-2 gap-4">
            {[
              ["Card required", "No"],
              ["Automatic charge", "No"],
              ["Automatic conversion", "No"],
              ["Public self-service", "Not active yet"],
            ].map(([term, value]) => (
              <div key={term} className="rounded-2xl bg-brand-background p-5">
                <dt className="text-xs font-bold uppercase tracking-[0.12em] text-brand-muted">
                  {term}
                </dt>
                <dd className="mt-2 text-lg font-semibold text-brand-primary">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-4xl rounded-[2rem] border border-brand-primary/10 bg-white p-7 sm:p-10">
          <p className="marketing-eyebrow">Credits and connectors</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-brand-primary">
            No invented add-on pricing.
          </h2>
          <p className="mt-5 text-base leading-8 text-brand-muted">
            Some eligible variable-cost research actions use Credits. Production
            Credit packs and prices have not been activated, so no pack table is
            published here. Optional connector pricing is also not publicly
            defined. Provider-backed research, external sending and CRM
            connections remain unavailable until their production activation is
            complete. Any applicable commercial terms will be clear before a
            customer is charged.
          </p>
        </div>
      </section>

      <TrialCallout heading="Start with the complete workflow—without a card." />
    </>
  );
}
