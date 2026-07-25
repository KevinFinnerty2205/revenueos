import { OpportunityWorkspace } from "@/components/opportunity-workspace";

export default async function OpportunityWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OpportunityWorkspace opportunityId={id} />;
}
