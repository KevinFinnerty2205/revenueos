import type { Interaction } from "@revenueos/shared";
import { isInteractionResponse } from "@/lib/private-response-identity";

export interface InteractionResponseExpectation {
  interactionId: string;
  organisationId: string;
  baseline?: Interaction;
  expectedLifecycleStatus?: Interaction["lifecycleStatus"];
}

function hasStableInteractionAnchors(
  response: Interaction,
  baseline: Interaction,
): boolean {
  return (
    response.companyId === baseline.companyId &&
    response.opportunityId === baseline.opportunityId &&
    response.contactId === baseline.contactId &&
    response.meetingId === baseline.meetingId &&
    (response.eventId ?? null) === (baseline.eventId ?? null) &&
    response.interactionType === baseline.interactionType &&
    response.creationOrigin === baseline.creationOrigin &&
    response.createdByUserId === baseline.createdByUserId
  );
}

export function decodeInteractionResponse(
  value: unknown,
  expectation: InteractionResponseExpectation,
): Interaction | null {
  if (
    !isInteractionResponse(value, expectation.organisationId) ||
    value.id !== expectation.interactionId ||
    (expectation.expectedLifecycleStatus !== undefined &&
      value.lifecycleStatus !== expectation.expectedLifecycleStatus)
  ) {
    return null;
  }

  const baseline = expectation.baseline;
  if (
    baseline !== undefined &&
    (baseline.id !== expectation.interactionId ||
      baseline.organisationId !== expectation.organisationId ||
      !hasStableInteractionAnchors(value, baseline))
  ) {
    return null;
  }

  return value;
}
