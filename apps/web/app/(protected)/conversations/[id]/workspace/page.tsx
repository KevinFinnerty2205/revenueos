import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { FaceToFaceCompanion } from "@/components/face-to-face-companion";

export default async function ConversationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <BetaFeatureGate feature="aiCompanion">
      <FaceToFaceCompanion interactionId={id} />
    </BetaFeatureGate>
  );
}
