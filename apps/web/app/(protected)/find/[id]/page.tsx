import { ProspectResearchBriefView } from "@/components/prospect-research-brief";

export default async function AccountResearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ returnToPerson?: string }>;
}) {
  const { id } = await params;
  const { returnToPerson } = await searchParams;
  return (
    <ProspectResearchBriefView
      targetId={id}
      returnToPersonId={returnToPerson ?? null}
    />
  );
}
