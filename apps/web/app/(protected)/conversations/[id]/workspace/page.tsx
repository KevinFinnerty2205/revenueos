import { redirect } from "next/navigation";

export default async function ConversationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/conversations/${id}?view=capture`);
}
