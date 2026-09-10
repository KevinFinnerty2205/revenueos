import type { Metadata } from "next";
import {
  PageIntro,
  ProductShot,
  SectionHeading,
  TrialCallout,
} from "@/components/marketing/marketing-components";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Sales platform",
  "Explore Oryntela across Prospect, Engage, Create, Native CRM, Opportunity Workspace, Sales Brain, Pipeline, Forecast, Analytics, Deal Room and Handover.",
  "/platform",
);

const productGroups = [
  {
    id: "sell",
    eyebrow: "Sell",
    title: "Find the right accounts and prepare relevant outreach.",
    description:
      "Move from a defined target market into reviewed account research, customer outreach and sales material without scattering context across point tools.",
    features: [
      {
        name: "Prospect",
        body: "Define target markets, research potential accounts and contacts, inspect sources, then explicitly add the right records to Sales. Provider-backed live research remains pending production activation.",
      },
      {
        name: "Engage",
        body: "Prepare and review individual outreach or small campaigns from connected business mailbox context. Oryntela keeps approval, recipient eligibility and delivery state visible; it is not autonomous spam.",
      },
      {
        name: "Create",
        body: "Build customer-ready presentations from approved source material, review each claim and download an editable PowerPoint.",
      },
      {
        name: "Business Cases",
        body: "Use approved assumptions and deterministic maths to create a transparent case with scenarios and sensitivity—without invented numbers.",
      },
    ],
  },
  {
    id: "run",
    eyebrow: "Run the deal",
    title: "Keep relationship context, deal work and buyer material together.",
    description:
      "Oryntela treats the CRM record as one part of a living opportunity workspace, with customer evidence, reviewed actions and buyer-facing material kept in their proper place.",
    features: [
      {
        name: "Oryntela CRM",
        body: "Manage companies, people and opportunities in a deliberate Native CRM designed for relationship-led B2B sales.",
      },
      {
        name: "Opportunity Workspace",
        body: "Bring the commercial record, relationship activity, methodology, evidence, decisions, risks, actions and change history into one deal view.",
      },
      {
        name: "Deal Room",
        body: "Publish a read-only buyer space with a reviewed overview, stakeholders, milestones and approved resources. Buyers do not edit, comment or e-sign in Oryntela.",
      },
    ],
  },
  {
    id: "manage",
    eyebrow: "Manage",
    title:
      "Know what is happening, what needs attention and how the number is built.",
    description:
      "Keep the team's operating rhythm connected while making the source and limits of every management view clear.",
    features: [
      {
        name: "Sales Brain",
        body: "Understand what is happening across customer interactions and deals, then see the next action that deserves attention.",
      },
      {
        name: "Pipeline",
        body: "See open opportunities by stage, owner and attention state, with the next action visible beside the commercial record.",
      },
      {
        name: "Forecast",
        body: "Record explicit Commit, Likely, Possible or Not this period judgement and retain its history without arbitrary percentage scoring.",
      },
      {
        name: "Targets & Analytics",
        body: "Compare canonical actuals and targets across useful sales views while keeping currencies and definitions clear.",
      },
      {
        name: "Manager Intelligence",
        body: "See which deals need attention, why the condition appears and which evidence-backed questions are worth discussing. Oryntela evaluates deals, not people.",
      },
    ],
  },
  {
    id: "transition",
    eyebrow: "Close and transition",
    title: "Carry reviewed commercial truth forward after the win.",
    description:
      "A closed deal should not become a new round of discovery. Oryntela prepares a source-pinned internal handover for review and administrator approval.",
    features: [
      {
        name: "Closed-Won Handover",
        body: "Package objectives, success criteria, stakeholders, commitments, risks and open actions into a reviewed immutable revision. Oryntela does not automatically execute implementation work.",
      },
    ],
  },
] as const;

function FeatureGrid({
  features,
}: Readonly<{ features: (typeof productGroups)[number]["features"] }>) {
  return (
    <div className="mt-9 grid gap-4 sm:grid-cols-2">
      {features.map((feature) => (
        <article
          key={feature.name}
          className="rounded-3xl border border-brand-primary/10 bg-white p-6 shadow-sm"
        >
          <h3 className="text-xl font-semibold tracking-[-0.025em] text-brand-primary">
            {feature.name}
          </h3>
          <p className="mt-3 text-sm leading-7 text-brand-muted">
            {feature.body}
          </p>
        </article>
      ))}
    </div>
  );
}

export default function PlatformPage() {
  return (
    <>
      <section className="px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:px-12">
        <PageIntro
          eyebrow="The Oryntela platform"
          title="One operating system for the full sales process."
          description="From finding the right accounts to forecasting the number and handing over a win, Oryntela keeps the work connected and human decisions explicit."
        />
      </section>

      <section
        id={productGroups[0].id}
        className="marketing-section border-t border-brand-primary/10 bg-white px-5 sm:px-8 lg:px-12"
      >
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-start lg:gap-16">
          <div>
            <SectionHeading
              eyebrow={productGroups[0].eyebrow}
              title={productGroups[0].title}
              description={productGroups[0].description}
            />
            <FeatureGrid features={productGroups[0].features} />
          </div>
          <div className="grid gap-7">
            <ProductShot
              image="prospect"
              alt="Oryntela Prospect Find showing a synthetic Australian target market and account research list"
              caption="Prospect · actual Oryntela UI with synthetic account data"
            />
            <ProductShot
              image="create"
              alt="Oryntela Create Sales Content Studio showing synthetic business cases, presentations and approved templates"
              caption="Create and Business Cases · reviewed content workflow"
            />
          </div>
        </div>
      </section>

      <section
        id={productGroups[1].id}
        className="marketing-section px-5 sm:px-8 lg:px-12"
      >
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-start lg:gap-16">
          <div className="lg:order-2">
            <SectionHeading
              eyebrow={productGroups[1].eyebrow}
              title={productGroups[1].title}
              description={productGroups[1].description}
            />
            <FeatureGrid features={productGroups[1].features} />
          </div>
          <div className="grid gap-7 lg:order-1">
            <ProductShot
              image="opportunity"
              alt="Oryntela Opportunity Workspace showing a synthetic opportunity record and its relationship activity"
              caption="Opportunity Workspace · one deal record with connected activity"
            />
            <ProductShot
              image="dealRoom"
              alt="Oryntela Opportunity Deal Room editor showing a synthetic buyer-safe overview and publication controls"
              caption="Deal Room · seller controls for a reviewed, read-only buyer space"
            />
          </div>
        </div>
      </section>

      <section
        id={productGroups[2].id}
        className="marketing-section bg-brand-primary px-5 text-brand-primary-foreground sm:px-8 lg:px-12"
      >
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-start lg:gap-16">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-accent">
              {productGroups[2].eyebrow}
            </p>
            <h2 className="mt-4 text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl">
              {productGroups[2].title}
            </h2>
            <p className="mt-5 text-base leading-8 text-slate-300 sm:text-lg">
              {productGroups[2].description}
            </p>
            <div className="mt-9 grid gap-4 sm:grid-cols-2">
              {productGroups[2].features.map((feature) => (
                <article
                  key={feature.name}
                  className="rounded-3xl border border-white/10 bg-white/5 p-6"
                >
                  <h3 className="text-xl font-semibold tracking-[-0.025em] text-white">
                    {feature.name}
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    {feature.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
          <div className="grid gap-7">
            <ProductShot
              image="pipeline"
              alt="Oryntela Pipeline showing synthetic opportunities organised by sales stage with next actions visible"
              caption="Pipeline · synthetic commercial values in AUD and USD"
              captionOnDark
            />
            <ProductShot
              image="analytics"
              alt="Oryntela Analytics showing separate actual, target, seller, manager and historical values with synthetic data"
              caption="Analytics, Targets and Forecast · separate references, never a blended number"
              captionOnDark
            />
          </div>
        </div>
      </section>

      <section
        id={productGroups[3].id}
        className="marketing-section px-5 sm:px-8 lg:px-12"
      >
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-2 lg:items-center lg:gap-16">
          <div>
            <SectionHeading
              eyebrow={productGroups[3].eyebrow}
              title={productGroups[3].title}
              description={productGroups[3].description}
            />
            <FeatureGrid features={productGroups[3].features} />
          </div>
          <ProductShot
            image="handover"
            alt="Oryntela opportunity controls showing a synthetic Closed-Won Handover preparation step beside Deal Room and Forecast"
            caption="Closed-Won Handover · reviewed transition, not automated implementation"
          />
        </div>
      </section>

      <section className="marketing-section border-t border-brand-primary/10 bg-white px-5 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-2 lg:items-center lg:gap-16">
          <div>
            <SectionHeading
              eyebrow="Reviewed customer engagement"
              title="Keep outreach deliberate and inspectable."
              description="Engage is designed around controlled business-mailbox sending, suppression, review and delivery reconciliation. The production mailbox connections shown on the Integrations page are not active yet."
            />
          </div>
          <ProductShot
            image="engage"
            alt="Oryntela Engage campaign screen showing a synthetic paused campaign and the explicit pre-launch mailbox boundary"
            caption="Pre-launch Engage build · the screenshot deliberately shows that no production mailbox provider is active"
          />
        </div>
      </section>

      <TrialCallout />
    </>
  );
}
