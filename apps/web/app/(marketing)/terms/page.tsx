import type { Metadata } from "next";
import Link from "next/link";
import { createMarketingMetadata } from "@/lib/marketing";

export const metadata: Metadata = createMarketingMetadata(
  "Terms status",
  "Current status of the Oryntela public Terms before launch.",
  "/terms",
  { index: false },
);

export default function TermsPage() {
  return (
    <section className="px-5 py-16 sm:px-8 sm:py-24 lg:px-12">
      <div className="mx-auto max-w-3xl rounded-[2rem] border border-brand-primary/10 bg-white p-7 shadow-sm sm:p-12">
        <p className="marketing-eyebrow">Legal content status</p>
        <h1 className="marketing-page-title mt-5">
          Service Terms not yet published.
        </h1>
        <p className="mt-6 text-base leading-8 text-brand-muted sm:text-lg">
          The repository does not contain owner-approved public Terms of Use or
          service terms. Oryntela will not fabricate contractual language or
          imply approval before the launch legal pack is complete.
        </p>
        <div className="mt-8 rounded-2xl bg-brand-background p-6">
          <h2 className="text-lg font-semibold text-brand-primary">
            Before launch
          </h2>
          <p className="mt-3 text-sm leading-7 text-brand-muted">
            Approved Terms must confirm the contracting treatment, service
            scope, commercial terms, acceptable use, customer responsibilities,
            data treatment, limitations, governing law, acceptance method,
            version and effective date.
          </p>
        </div>
        <p className="mt-8 text-sm leading-7 text-brand-muted">
          Commercial questions can be sent to{" "}
          <a
            className="font-bold text-brand-secondary underline decoration-2 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-brand-focus"
            href="mailto:hello@oryntela.com.au?subject=Oryntela%20commercial%20question"
          >
            hello@oryntela.com.au
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
