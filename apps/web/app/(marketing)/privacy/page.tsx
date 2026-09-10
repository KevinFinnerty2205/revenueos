import type { Metadata } from "next";
import Link from "next/link";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Privacy status",
  "Current status of the Oryntela public Privacy Notice before launch.",
  "/privacy",
  { index: false },
);

export default function PrivacyPage() {
  return (
    <section className="px-5 py-16 sm:px-8 sm:py-24 lg:px-12">
      <div className="mx-auto max-w-3xl rounded-[2rem] border border-brand-primary/10 bg-white p-7 shadow-sm sm:p-12">
        <p className="marketing-eyebrow">Legal content status</p>
        <h1 className="marketing-page-title mt-5">
          Privacy Notice not yet published.
        </h1>
        <p className="mt-6 text-base leading-8 text-brand-muted sm:text-lg">
          The repository contains detailed technical privacy and security
          controls, but it does not contain an owner-approved public Privacy
          Notice. Oryntela will not present engineering guidance as a legally
          approved notice.
        </p>
        <div className="mt-8 rounded-2xl bg-brand-background p-6">
          <h2 className="text-lg font-semibold text-brand-primary">
            Before launch
          </h2>
          <p className="mt-3 text-sm leading-7 text-brand-muted">
            The approved notice must identify the publishing entity, purposes,
            data categories, providers, locations, retention, access,
            correction, export and deletion processes, with a version and
            effective date.
          </p>
        </div>
        <p className="mt-8 text-sm leading-7 text-brand-muted">
          Privacy questions can be sent to{" "}
          <a
            className="font-bold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
            href="mailto:support@oryntela.com.au?subject=Oryntela%20privacy%20question"
          >
            support@oryntela.com.au
          </a>
          .
        </p>
        <Link href="/" className="marketing-secondary-button mt-8">
          Return home
        </Link>
      </div>
    </section>
  );
}
