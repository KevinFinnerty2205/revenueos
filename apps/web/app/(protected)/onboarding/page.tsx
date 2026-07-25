import { BetaOnboarding } from "@/components/beta-onboarding";
import { PageHeader } from "@/components/page-header";

export default function OnboardingPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Private beta"
        title="Set up your safe first journey"
        description="A short, skippable guide using deliberate transcript input and reviewable intelligence. Production customer data remains prohibited."
      />
      <BetaOnboarding />
    </div>
  );
}
