import { PageHeader } from "@/components/page-header";
import { SalesMethodologySettings } from "@/components/sales-methodology-settings";

export default function FrameworksPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Conversation frameworks"
        title="Guide the conversation without forcing it"
        description="Choose BANT, SPICED, MEDDIC, MEDDICC or MEDDPICC, use notes only, or adapt a company-specific framework. Coverage is evidence—not win probability."
      />
      <div className="rounded-2xl border border-brand-secondary/15 bg-brand-secondary/10 p-5 text-sm leading-6 text-brand-primary">
        <strong>Coverage stays contextual.</strong> “Not discussed” remains
        unknown, early conversations are not penalised for later-stage fields,
        and every supported assessment keeps its evidence references.
      </div>
      <SalesMethodologySettings />
    </div>
  );
}
