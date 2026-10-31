import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { OpportunityWorkspace } from "@/components/opportunity-workspace";
import { OpportunityPipelinePanel } from "@/components/opportunity-pipeline-panel";
import { CRMRecordPanel } from "@/components/crm-record-panel";
import { ManagerDealReviewPanel } from "@/components/manager-deal-review";

export default async function OpportunityWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-7">
      <div id="opportunity-workspace">
        <BetaFeatureGate feature="opportunityWorkspace">
          <OpportunityWorkspace opportunityId={id} />
        </BetaFeatureGate>
      </div>
      <div id="deal-workflow" className="scroll-mt-6">
        <OpportunityPipelinePanel opportunityId={id} />
      </div>
      <ManagerDealReviewPanel opportunityId={id} />
      <details
        id="crm-record-administration"
        className="scroll-mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <summary className="cursor-pointer text-sm font-bold text-slate-800">
          CRM record and administration
        </summary>
        <div className="mt-5">
          <CRMRecordPanel
            entityType="opportunity"
            entityId={id}
            headingLevel={2}
          />
        </div>
      </details>
    </div>
  );
}
