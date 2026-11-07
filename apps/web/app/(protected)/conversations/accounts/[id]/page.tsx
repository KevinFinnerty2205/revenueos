import { AccountConversations } from "@/components/account-conversations";

export default async function AccountConversationsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AccountConversations companyId={id} />;
}
