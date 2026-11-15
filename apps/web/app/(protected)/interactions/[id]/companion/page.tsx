import { FaceToFaceCompanion } from "@/components/face-to-face-companion";

export default async function InteractionCompanionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FaceToFaceCompanion interactionId={id} />;
}
