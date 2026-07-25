import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { OpportunityWorkspace } from "@/components/opportunity-workspace";

export default async function OpportunityWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <BetaFeatureGate feature="opportunityWorkspace">
      <OpportunityWorkspace opportunityId={id} />
    </BetaFeatureGate>
  );
}
