import { ConversationWorkspace } from "@/components/conversation-workspace";

export default async function ConversationPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ view?: string }>;
}) {
  const { id } = await params;
  const { view } = await searchParams;
  return (
    <ConversationWorkspace
      interactionId={id}
      initialView={view === "capture" ? "capture" : undefined}
    />
  );
}
