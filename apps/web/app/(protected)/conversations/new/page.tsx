import type { InteractionType } from "@revenueos/shared";
import { InteractionForm } from "@/components/interaction-form";
import { interactionTypes } from "@/lib/interactions";

export default async function NewConversationPage({
  searchParams,
}: {
  searchParams: Promise<{
    companyId?: string;
    opportunityId?: string;
    contactId?: string;
    interactionType?: string;
  }>;
}) {
  const parameters = await searchParams;
  const interactionType = interactionTypes.find(
    (value) => value === parameters.interactionType,
  ) as InteractionType | undefined;
  return (
    <InteractionForm
      initialCompanyId={parameters.companyId}
      initialOpportunityId={parameters.opportunityId}
      initialContactId={parameters.contactId}
      initialInteractionType={interactionType}
    />
  );
}
