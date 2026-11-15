import {
  ConversationWorkspace,
  type ConversationView,
} from "@/components/conversation-workspace";

const conversationViews: ConversationView[] = [
  "prepare",
  "capture",
  "review",
  "history",
];

function isConversationView(
  value: string | undefined,
): value is ConversationView {
  return (
    value !== undefined &&
    conversationViews.some((candidate) => candidate === value)
  );
}

export default async function ConversationPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ view?: string }>;
}) {
  const { id } = await params;
  const { view } = await searchParams;
  const initialView = isConversationView(view) ? view : undefined;
  return <ConversationWorkspace interactionId={id} initialView={initialView} />;
}
