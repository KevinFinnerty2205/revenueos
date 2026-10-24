import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function NewContactPage({
  searchParams,
}: {
  searchParams: Promise<{ companyId?: string }>;
}) {
  const { companyId } = await searchParams;
  return <BusinessEntityForm entity="contacts" initialCompanyId={companyId} />;
}
