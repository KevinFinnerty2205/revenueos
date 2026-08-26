import { ContactOutreachWorkspace } from "@/components/contact-outreach-workspace";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ContactOutreachWorkspace contactId={id} />;
}
