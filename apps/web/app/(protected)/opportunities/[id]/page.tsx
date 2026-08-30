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
      <CRMRecordPanel entityType="opportunity" entityId={id} />
      <OpportunityPipelinePanel opportunityId={id} />
      <ManagerDealReviewPanel opportunityId={id} />
      <div id="opportunity-workspace">
        <BetaFeatureGate feature="opportunityWorkspace">
          <OpportunityWorkspace opportunityId={id} />
        </BetaFeatureGate>
      </div>
    </div>
  );
}
