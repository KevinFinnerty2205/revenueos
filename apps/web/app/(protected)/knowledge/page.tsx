import { CompanyKnowledgeSources } from "@/components/company-knowledge-sources";
import { PageHeader } from "@/components/page-header";
import { SellingProfileSettings } from "@/components/selling-profile-settings";

export default function KnowledgePage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Company knowledge"
        title="Teach Oryntela what your company knows"
        description="Add approved sources, then review and approve the company understanding used in conversation preparation. External website processing remains gated."
      />
      <CompanyKnowledgeSources />
      <div
        id="company-understanding"
        aria-label="Company understanding"
        className="scroll-mt-6"
      >
        <SellingProfileSettings />
      </div>
    </div>
  );
}
