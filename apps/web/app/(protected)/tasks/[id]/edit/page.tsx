import { BusinessEntityForm } from "@/components/business-entity-form";

export default async function EditTaskPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BusinessEntityForm entity="tasks" entityId={id} />;
}
