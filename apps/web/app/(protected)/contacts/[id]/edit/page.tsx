import { BusinessEntityForm } from "@/components/business-entity-form";
import { ContactPublicProfessionalResearch } from "@/components/prospect-people";

export default async function EditContactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <>
      <BusinessEntityForm entity="contacts" entityId={id} />
      <ContactPublicProfessionalResearch contactId={id} />
    </>
  );
}
