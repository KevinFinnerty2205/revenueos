import { InteractionDetail } from "@/components/interaction-detail";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <InteractionDetail interactionId={id} />;
}
