import { BetaFeedbackForm } from "@/components/beta-feedback-form";
import { PageHeader } from "@/components/page-header";

export default function FeedbackPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Private beta"
        title="Share feedback"
        description="Tell us what broke, felt confusing or produced an unhelpful result. RevenueOS never attaches transcript or generated content automatically."
      />
      <BetaFeedbackForm />
    </div>
  );
}
