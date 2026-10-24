import { ContactOutreachWorkspace } from "@/components/contact-outreach-workspace";
import { CRMRecordPanel } from "@/components/crm-record-panel";
import { ContactPublicProfessionalResearch } from "@/components/prospect-people";
import Link from "next/link";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-7">
      <CRMRecordPanel entityType="contact" entityId={id} />
      <section className="flex flex-col gap-4 rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-secondary">
            Relationship activity
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            Plan the next interaction
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Start a deliberately supplied phone interaction with this person
            already selected.
          </p>
        </div>
        <Link
          className="primary-button shrink-0"
          href={`/interactions/new?contactId=${id}&interactionType=phone_call`}
        >
          Plan phone call
        </Link>
      </section>
      <ContactOutreachWorkspace contactId={id} />
      <ContactPublicProfessionalResearch contactId={id} />
    </div>
  );
}
