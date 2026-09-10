import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowLink,
  ProductShot,
  SectionHeading,
  TrialCallout,
} from "@/components/marketing/marketing-components";
import {
  createMarketingMetadata,
  hero,
  pricingPlans,
  trialOffer,
} from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "End-to-end sales platform for Australian B2B teams",
  "Run your sales process from prospecting and reviewed outreach through CRM, forecasting, Deal Room and clean handover with Oryntela.",
  "/",
);

const workflow = [
  ["01", "Know what to do next", "Sales Brain"],
  ["02", "Find who to sell to", "Prospect"],
  ["03", "Prepare the outreach", "Engage"],
  ["04", "Build the case", "Create"],
  ["05", "Run the deal", "Oryntela CRM"],
  ["06", "Manage the number", "Forecast & Analytics"],
  ["07", "Hand over cleanly", "Closed-Won Handover"],
] as const;

const outcomes = [
  {
    label: "For leaders",
    title: "See the real state of the number.",
    body: "Keep Actual, Target, seller judgement, manager judgement and the historical baseline separate—then see which deals deserve attention.",
  },
  {
    label: "For managers",
    title: "Coach the deal, not the activity count.",
    body: "Manager Intelligence explains why an opportunity needs attention and gives the team practical questions to discuss.",
  },
  {
    label: "For sellers",
    title: "Move from context to the next action.",
    body: "Prepare, capture what changed, review the evidence and carry approved context into the next customer step.",
  },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="relative isolate overflow-hidden px-5 pb-20 pt-14 sm:px-8 sm:pb-28 sm:pt-20 lg:px-12 lg:pb-32 lg:pt-24">
        <div
          aria-hidden="true"
          className="absolute -right-24 top-8 -z-10 size-[30rem] rounded-full bg-brand-secondary/10 blur-3xl"
        />
        <div className="mx-auto grid max-w-7xl gap-14 lg:grid-cols-[1.04fr_0.96fr] lg:items-center lg:gap-16">
          <div className="min-w-0">
            <p className="marketing-eyebrow">{hero.category}</p>
            <h1 className="mt-6 max-w-3xl text-5xl font-semibold leading-[0.98] tracking-[-0.055em] text-brand-primary sm:text-6xl lg:text-7xl">
              {hero.headline}
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-brand-muted sm:text-xl sm:leading-9">
              {hero.supportingCopy}
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link href="/contact#trial" className="marketing-primary-button">
                {hero.primaryCta}
              </Link>
              <Link href="/platform" className="marketing-secondary-button">
                {hero.secondaryCta}
              </Link>
            </div>
            <p className="mt-5 text-sm leading-6 text-brand-muted">
              {trialOffer.lengthDays} days · Complete-level modules · no card ·
              no automatic charge
            </p>
          </div>

          <div className="relative mx-auto min-w-0 w-full max-w-[610px] lg:mx-0">
            <div
              aria-hidden="true"
              className="absolute -inset-5 -z-10 rotate-2 rounded-[2.25rem] bg-brand-primary"
            />
            <ProductShot
              alt="Oryntela Sales Brain home showing manager deal review, a top-priority action, open pipeline and recommended focus in a synthetic workspace"
              image="salesBrain"
              priority
              caption="Real Oryntela product UI · synthetic demonstration data"
            />
          </div>
        </div>
      </section>

      <section className="border-y border-brand-primary/10 bg-white px-5 py-10 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <p className="max-w-3xl text-xl font-semibold leading-8 tracking-[-0.02em] text-brand-primary sm:text-2xl sm:leading-9">
            Sales gets harder when the CRM, prospecting, outreach, deal context,
            forecasts and handover all live in different places.
          </p>
          <p className="mt-4 max-w-3xl text-base leading-8 text-brand-muted">
            Oryntela connects the work without hiding human judgement or turning
            every customer decision into an automated action.
          </p>
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <SectionHeading
            eyebrow="One connected process"
            title="The whole sales journey, with a clear next step at every stage."
            description="Start with the right accounts. Build context carefully. Keep the deal moving. Give leaders a trustworthy view of the number. Finish with a reviewed transition."
          />
          <ol className="mt-12 grid overflow-hidden rounded-[2rem] border border-brand-primary/10 bg-white sm:grid-cols-2 lg:grid-cols-4">
            {workflow.map(([number, action, product], index) => (
              <li
                key={product}
                className={`min-h-52 p-6 sm:p-7 ${
                  index === workflow.length - 1
                    ? "bg-brand-primary text-white"
                    : "border-b border-brand-primary/10 text-brand-primary sm:border-r lg:border-b-0"
                }`}
              >
                <span
                  className={`text-xs font-bold tracking-[0.18em] ${
                    index === workflow.length - 1
                      ? "text-brand-accent"
                      : "text-brand-secondary"
                  }`}
                >
                  {number}
                </span>
                <h3 className="mt-12 text-xl font-semibold tracking-[-0.025em]">
                  {action}
                </h3>
                <p
                  className={`mt-2 text-sm ${
                    index === workflow.length - 1
                      ? "text-slate-300"
                      : "text-brand-muted"
                  }`}
                >
                  {product}
                </p>
              </li>
            ))}
          </ol>
          <div className="mt-6">
            <ArrowLink href="/platform">
              See how the platform fits together
            </ArrowLink>
          </div>
        </div>
      </section>

      <section className="marketing-section bg-brand-primary px-5 text-brand-primary-foreground sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.82fr_1.18fr] lg:items-center lg:gap-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-accent">
              Sales Brain
            </p>
            <h2 className="mt-4 text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl">
              Know what deserves attention next.
            </h2>
            <p className="mt-6 text-base leading-8 text-slate-300 sm:text-lg">
              Oryntela organises the signals already in the sales process and
              brings the most useful next step forward. Suggested claims and
              actions remain reviewable; the system does not quietly turn an
              inference into customer truth.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-4 border-t border-white/10 pt-7 text-sm text-slate-300">
              <p>Evidence stays distinct from seller judgement.</p>
              <p>Consequential actions require human approval.</p>
            </div>
          </div>
          <ProductShot
            alt="Oryntela opportunity workspace showing a synthetic opportunity record and relationship activity"
            image="opportunity"
            caption="Opportunity Workspace · actual product UI with synthetic records"
            captionOnDark
          />
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <SectionHeading
            eyebrow="Built for the whole team"
            title="Clarity for the people carrying the number."
          />
          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            {outcomes.map((outcome) => (
              <article
                key={outcome.label}
                className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 shadow-sm sm:p-8"
              >
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                  {outcome.label}
                </p>
                <h3 className="mt-5 text-2xl font-semibold leading-8 tracking-[-0.03em] text-brand-primary">
                  {outcome.title}
                </h3>
                <p className="mt-4 text-sm leading-7 text-brand-muted">
                  {outcome.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-section border-y border-brand-primary/10 bg-white px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-2 lg:items-start lg:gap-16">
          <div>
            <SectionHeading
              eyebrow="Manage the number"
              title="A forecast people can understand and discuss."
              description="Pipeline, Forecast, Targets, Analytics and Manager Intelligence stay connected while preserving separate sources of judgement. There is no blended certainty theatre."
            />
            <div className="mt-8">
              <ArrowLink href="/platform#manage">
                Explore sales management
              </ArrowLink>
            </div>
          </div>
          <ProductShot
            alt="Oryntela sales insights showing separate actual, target, seller forecast, manager forecast and historical baseline values using synthetic data"
            image="analytics"
          />
        </div>
      </section>

      <section className="marketing-section px-5 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <SectionHeading
            eyebrow="Your CRM, your choice"
            title="Run Oryntela CRM—or connect the system your team already uses."
            description="Native Oryntela CRM is included in Core. Oryntela is also built to connect with Microsoft 365, Google Workspace, HubSpot and Salesforce. Those production connections remain activation-dependent before launch."
          />
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            <article className="rounded-[1.75rem] bg-brand-primary p-7 text-white sm:p-9">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-accent">
                Native Oryntela CRM
              </p>
              <h3 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">
                One place from account to opportunity.
              </h3>
              <p className="mt-4 text-sm leading-7 text-slate-300">
                Keep companies, people, opportunities, pipeline and sales
                intelligence together without adopting a sprawling CRM.
              </p>
            </article>
            <article className="rounded-[1.75rem] border border-brand-primary/10 bg-white p-7 sm:p-9">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
                Connected mode
              </p>
              <h3 className="mt-5 text-3xl font-semibold tracking-[-0.035em] text-brand-primary">
                Keep external record authority visible.
              </h3>
              <p className="mt-4 text-sm leading-7 text-brand-muted">
                Provider-owned fields, reviewed write-back and uncertain
                outcomes remain explicit. Oryntela does not pretend every sync
                is truth.
              </p>
              <div className="mt-6">
                <ArrowLink href="/integrations">
                  See integration status
                </ArrowLink>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="px-5 pb-6 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl rounded-[2rem] border border-brand-primary/10 bg-white p-7 sm:p-10">
          <div className="grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
            <div>
              <p className="marketing-eyebrow">Clear commercial plans</p>
              <h2 className="marketing-section-title mt-4">
                Start at AUD ${pricingPlans[0].monthlyAmount} per month for five
                users.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-brand-muted">
                Core includes the Oryntela operating loop and Native CRM. Growth
                adds Prospect and Engage workflows, with external research and
                sending only when activated. Complete adds Create and supported
                CRM connectors when activated.
              </p>
            </div>
            <ArrowLink href="/pricing">See all plans</ArrowLink>
          </div>
        </div>
      </section>

      <TrialCallout heading="See your sales process as one connected system." />
    </>
  );
}
