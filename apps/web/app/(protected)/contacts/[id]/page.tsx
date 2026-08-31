import { ContactOutreachWorkspace } from "@/components/contact-outreach-workspace";
import { CRMRecordPanel } from "@/components/crm-record-panel";
import { ContactPublicProfessionalResearch } from "@/components/prospect-people";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-7">
      <CRMRecordPanel entityType="contact" entityId={id} />
      <ContactOutreachWorkspace contactId={id} />
      <ContactPublicProfessionalResearch contactId={id} />
    </div>
  );
}
