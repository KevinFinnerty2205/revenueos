import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function EditOpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BusinessEntityForm entity="opportunities" entityId={id} />;
}
