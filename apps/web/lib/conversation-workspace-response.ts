import type { ConversationWorkspaceResponse } from "@revenueos/shared";

export interface ConversationWorkspaceIdentity {
  interactionId: string;
  organisationId: string;
  ownerUserId: string;
}

type ConversationWorkspaceSave = Pick<
  ConversationWorkspaceResponse,
  | "liveNotes"
  | "enhancedNotes"
  | "followUpDraft"
  | "followUpReviewed"
  | "generationFingerprint"
> & {
  expectedLockVersion: number;
};

const generationStates = new Set([
  "not_started",
  "pending",
  "processing",
  "failed",
  "ready",
]);
const personalNotesStates = new Set(["not_included", "current", "changed"]);

function isGenerationState(
  value: unknown,
): value is ConversationWorkspaceResponse["generationState"] {
  return typeof value === "string" && generationStates.has(value);
}

function isPersonalNotesState(
  value: unknown,
): value is ConversationWorkspaceResponse["generationPersonalNotesState"] {
  return typeof value === "string" && personalNotesStates.has(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNonNegativeInteger(value: unknown): value is number | null {
  return value === null || isNonNegativeInteger(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isNullableTimestamp(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      /(?:Z|[+-]\d{2}:\d{2})$/u.test(value) &&
      !Number.isNaN(Date.parse(value)))
  );
}

/**
 * Decodes the complete private-workspace payload before any private text or
 * mutation metadata is allowed into browser state.
 */
export function decodeConversationWorkspaceResponse(
  value: unknown,
  expected: ConversationWorkspaceIdentity,
): ConversationWorkspaceResponse | null {
  if (
    !isRecord(value) ||
    typeof value.exists !== "boolean" ||
    value.interactionId !== expected.interactionId ||
    value.organisationId !== expected.organisationId ||
    value.ownerUserId !== expected.ownerUserId ||
    !isNonNegativeInteger(value.lockVersion) ||
    !isNullableString(value.liveNotes) ||
    !isNullableString(value.enhancedNotes) ||
    !isNullableString(value.followUpDraft) ||
    typeof value.followUpReviewed !== "boolean" ||
    !isNullableString(value.generationFingerprint) ||
    !isGenerationState(value.generationState) ||
    !isNullableString(value.generationId) ||
    !isNullableNonNegativeInteger(value.generationTranscriptVersion) ||
    !isNullableString(value.generationFailureCode) ||
    typeof value.generationRetryAvailable !== "boolean" ||
    typeof value.generationUpdateAvailable !== "boolean" ||
    !isPersonalNotesState(value.generationPersonalNotesState) ||
    !isNullableTimestamp(value.generationCompletedAt) ||
    !isNullableTimestamp(value.importedFromBrowserAt) ||
    !isNullableTimestamp(value.updatedAt)
  ) {
    return null;
  }

  return {
    exists: value.exists,
    interactionId: expected.interactionId,
    organisationId: expected.organisationId,
    ownerUserId: expected.ownerUserId,
    lockVersion: value.lockVersion,
    liveNotes: value.liveNotes,
    enhancedNotes: value.enhancedNotes,
    followUpDraft: value.followUpDraft,
    followUpReviewed: value.followUpReviewed,
    generationFingerprint: value.generationFingerprint,
    generationState: value.generationState,
    generationId: value.generationId,
    generationTranscriptVersion: value.generationTranscriptVersion,
    generationPersonalNotesState: value.generationPersonalNotesState,
    generationFailureCode: value.generationFailureCode,
    generationRetryAvailable: value.generationRetryAvailable,
    generationUpdateAvailable: value.generationUpdateAvailable,
    generationCompletedAt: value.generationCompletedAt,
    importedFromBrowserAt: value.importedFromBrowserAt,
    updatedAt: value.updatedAt,
  };
}

export function decodeConversationWorkspaceSaveResponse(
  value: unknown,
  expected: ConversationWorkspaceIdentity,
  submitted: ConversationWorkspaceSave,
): ConversationWorkspaceResponse | null {
  const response = decodeConversationWorkspaceResponse(value, expected);
  if (
    response === null ||
    !response.exists ||
    response.lockVersion !== submitted.expectedLockVersion + 1 ||
    response.liveNotes !== submitted.liveNotes ||
    response.enhancedNotes !== submitted.enhancedNotes ||
    response.followUpDraft !== submitted.followUpDraft ||
    response.followUpReviewed !== submitted.followUpReviewed ||
    response.generationFingerprint !== submitted.generationFingerprint
  ) {
    return null;
  }
  return response;
}
