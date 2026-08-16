import { BetaAdmin } from "@/components/beta-admin";
import { PageHeader } from "@/components/page-header";
import { SalesMethodologySettings } from "@/components/sales-methodology-settings";

export default function SettingsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Private beta administration"
        title="Organisation controls"
        description="Review members, consent, retention, usage, feature flags and controlled privacy requests. Generated content and transcripts are deliberately excluded."
      />
      <SalesMethodologySettings />
      <BetaAdmin />
    </div>
  );
}
