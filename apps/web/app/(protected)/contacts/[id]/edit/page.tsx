import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function EditContactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BusinessEntityForm entity="contacts" entityId={id} />;
}
