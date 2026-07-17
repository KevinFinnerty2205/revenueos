import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function EditCompanyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BusinessEntityForm entity="companies" entityId={id} />;
}
