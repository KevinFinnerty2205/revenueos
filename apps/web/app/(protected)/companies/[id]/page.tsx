import { AccountConversationPanel } from "@/components/account-conversation-panel";
import { AccountPublicResearch } from "@/components/account-public-research";
import { AccountRelationshipHeader } from "@/components/account-relationship-header";

export default async function CompanyAccountPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-7">
      <AccountRelationshipHeader companyId={id} />
      <AccountConversationPanel companyId={id} />
      <AccountPublicResearch companyId={id} />
    </div>
  );
}
