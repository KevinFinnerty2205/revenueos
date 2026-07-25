import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { RevenueBrainTimeline } from "@/components/revenue-brain-timeline";

export default async function CompanyAccountPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <BetaFeatureGate feature="revenueBrain">
      <RevenueBrainTimeline accountId={id} />
    </BetaFeatureGate>
  );
}
