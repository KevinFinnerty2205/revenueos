import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { AccountPublicResearch } from "@/components/account-public-research";
import { RevenueBrainTimeline } from "@/components/revenue-brain-timeline";
import Link from "next/link";
import { CRMRecordPanel } from "@/components/crm-record-panel";

export default async function CompanyAccountPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-7">
      <CRMRecordPanel entityType="account" entityId={id} />
      <section className="mb-7 flex flex-col gap-4 rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-teal-700">
            RevenueOS Create
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            Create Account content
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Build a transparent Business Case or a reviewed PowerPoint from
            approved company content.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <Link
            href={`/create/business-cases/new?accountId=${id}`}
            className="secondary-button"
          >
            Create Business Case
          </Link>
          <Link
            href={`/create/presentations/new?accountId=${id}`}
            className="secondary-button"
          >
            Plan presentation
          </Link>
        </div>
      </section>
      <AccountPublicResearch companyId={id} />
      <BetaFeatureGate feature="revenueBrain">
        <RevenueBrainTimeline accountId={id} />
      </BetaFeatureGate>
    </div>
  );
}
