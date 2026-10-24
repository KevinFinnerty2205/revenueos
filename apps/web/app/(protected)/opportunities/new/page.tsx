import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function NewOpportunityPage({
  searchParams,
}: {
  searchParams: Promise<{ companyId?: string }>;
}) {
  const { companyId } = await searchParams;
  return (
    <BusinessEntityForm entity="opportunities" initialCompanyId={companyId} />
  );
}
