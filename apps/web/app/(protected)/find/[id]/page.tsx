import { ProspectResearchBriefView } from "@/components/prospect-research-brief";

export default async function AccountResearchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProspectResearchBriefView targetId={id} />;
}
