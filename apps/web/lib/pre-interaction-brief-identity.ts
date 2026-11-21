type PreInteractionBriefIdentity = {
  interactionId: string;
  brief: null | { interactionId: string };
};

export const PRE_INTERACTION_BRIEF_IDENTITY_ERROR =
  "The preparation response did not match this conversation. Try again.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function assertPreInteractionBriefIdentity(
  response: unknown,
  expectedInteractionId: string,
): asserts response is PreInteractionBriefIdentity {
  if (
    !isRecord(response) ||
    response.interactionId !== expectedInteractionId ||
    (response.brief !== null &&
      (!isRecord(response.brief) ||
        response.brief.interactionId !== expectedInteractionId))
  ) {
    throw new Error(PRE_INTERACTION_BRIEF_IDENTITY_ERROR);
  }
}
