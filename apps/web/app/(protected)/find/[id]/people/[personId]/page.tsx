import { ProspectPersonResearchView } from "@/components/prospect-people";

export default async function PersonResearchPage({
  params,
}: {
  params: Promise<{ id: string; personId: string }>;
}) {
  const { personId } = await params;
  return <ProspectPersonResearchView personId={personId} />;
}
