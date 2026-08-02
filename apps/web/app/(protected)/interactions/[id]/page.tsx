import { InteractionDetail } from "@/components/interaction-detail";

export default async function InteractionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <InteractionDetail interactionId={id} />;
}
