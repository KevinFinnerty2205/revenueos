import { BetaOnboarding } from "@/components/beta-onboarding";
import { PageHeader } from "@/components/page-header";
import { TermsAcceptance } from "@/components/terms-acceptance";

export default function OnboardingPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Getting started"
        title="Get value from your first customer conversation"
        description="A short, skippable path from a deal and its next interaction to a clear, reviewable follow-through."
      />
      <TermsAcceptance source="trial_onboarding">
        <BetaOnboarding />
      </TermsAcceptance>
    </div>
  );
}
