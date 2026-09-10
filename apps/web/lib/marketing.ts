import type { Metadata } from "next";

const fallbackSiteOrigin = "https://oryntela.com.au";

function resolveSiteOrigin(): string {
  const configuredOrigin = process.env.NEXT_PUBLIC_SITE_URL;
  if (!configuredOrigin) return fallbackSiteOrigin;

  try {
    const url = new URL(configuredOrigin);
    if (url.protocol !== "https:" && url.hostname !== "localhost") {
      return fallbackSiteOrigin;
    }
    return url.origin;
  } catch {
    return fallbackSiteOrigin;
  }
}

export const siteOrigin = resolveSiteOrigin();

export const siteDescription =
  "Oryntela is the end-to-end sales platform for Australian B2B teams, connecting prospecting, reviewed outreach, CRM, deal execution, forecasting and handover.";

export const hero = {
  category: "End-to-end sales platform",
  secondaryCategory: "Sales operating system",
  headline: "One sales system from prospect to handover.",
  supportingCopy:
    "Oryntela gives Australian B2B teams one clear way to find accounts, prepare reviewed outreach, run deals, forecast the number and hand over wins cleanly.",
  primaryCta: "Request trial access",
  secondaryCta: "Explore the platform",
} as const;

export const trialOffer = {
  lengthDays: 14,
  planName: "Complete",
  paymentMethodRequired: false,
  automaticCharge: false,
  automaticConversion: false,
} as const;

export const pricingPlans = [
  {
    code: "core",
    name: "Core",
    monthlyAmount: 200,
    annualAmount: 2_000,
    includedUsers: 5,
    description: "The complete operating loop for a focused sales team.",
    includes: [
      "Sales Brain and recommended actions",
      "Oryntela CRM and Opportunity Workspace",
      "Pipeline, Forecast, Targets and Analytics",
      "Manager Intelligence, Deal Room and Handover",
    ],
  },
  {
    code: "growth",
    name: "Growth",
    monthlyAmount: 350,
    annualAmount: 3_500,
    includedUsers: 10,
    description: "Core, with controlled prospecting and reviewed outreach.",
    includes: [
      "Everything in Core",
      "Prospect target markets and account research",
      "Engage outreach and campaign workflows",
      "Credits apply to eligible variable-cost research actions",
    ],
  },
  {
    code: "complete",
    name: "Complete",
    monthlyAmount: 500,
    annualAmount: 5_000,
    includedUsers: 15,
    description: "The end-to-end platform, including customer-ready creation.",
    includes: [
      "Everything in Growth",
      "Create sales presentations",
      "Business Cases with reviewed assumptions",
      "Supported external CRM connectors when activated",
    ],
  },
  {
    code: "enterprise",
    name: "Enterprise",
    monthlyAmount: null,
    annualAmount: null,
    includedUsers: null,
    description: "A tailored commercial plan for larger organisations.",
    includes: [
      "Complete-level module availability",
      "Custom user limits",
      "Commercial terms agreed with your organisation",
      "Provider activation remains separately assessed",
    ],
  },
] as const;

export const integrations = [
  {
    name: "Microsoft 365",
    scope:
      "Reviewed Outlook sending, reply reconciliation and calendar context",
  },
  {
    name: "Google Workspace",
    scope: "Reviewed Gmail sending, reply reconciliation and calendar context",
  },
  {
    name: "HubSpot",
    scope: "Account, contact and opportunity sync with reviewed write-back",
  },
  {
    name: "Salesforce",
    scope: "Account, contact and opportunity sync with reviewed write-back",
  },
] as const;

export function formatAud(amount: number): string {
  const formatted = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  }).format(amount);
  return `AUD ${formatted}`;
}

export function createMarketingMetadata(
  title: string,
  description: string,
  path: string,
  options: { index?: boolean } = {},
): Metadata {
  const canonical = path === "/" ? siteOrigin : `${siteOrigin}${path}`;
  const index = options.index ?? true;

  return {
    title,
    description,
    alternates: { canonical },
    robots: { index, follow: index },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: "Oryntela",
      locale: "en_AU",
      type: "website",
      images: [
        {
          url: "/opengraph-image",
          width: 1_200,
          height: 630,
          alt: "Oryntela — one sales system from prospect to handover",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/opengraph-image"],
    },
  };
}
