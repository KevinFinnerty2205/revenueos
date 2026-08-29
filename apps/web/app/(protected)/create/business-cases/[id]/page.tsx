import { BusinessCaseReview } from "@/components/business-case-review";

export default async function BusinessCasePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BusinessCaseReview caseId={id} />;
}
