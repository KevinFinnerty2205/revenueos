import type {
  VisualCandidateEvidence,
  VisualEvidence,
  VisualSourceOwnership,
  VisualType,
} from "@revenueos/shared";
import { isRecord } from "@/lib/private-response-identity";

export const VISUAL_RESPONSE_IDENTITY_ERROR =
  "Visual evidence could not be verified. Unverified data was not used; please try again.";

export const VISUAL_TYPES: readonly VisualType[] = [
  "whiteboard",
  "workshop_output",
  "architecture_diagram",
  "handwritten_notes",
  "agenda",
  "business_card",
  "presentation_slide",
  "presentation_deck_page",
  "customer_document_photo",
  "site_photo",
  "product_photo",
  "screenshot",
  "other",
];

export const VISUAL_SOURCE_OWNERSHIP: readonly VisualSourceOwnership[] = [
  "customer_created",
  "salesperson_created",
  "jointly_created",
  "unknown_origin",
];

const processingStatuses = [
  "uploading",
  "uploaded",
  "processing",
  "review",
  "completed",
  "failed",
  "cancelled",
  "deletion_pending",
  "deleted",
] as const satisfies readonly VisualEvidence["processingStatus"][];

const evidenceCategories = [
  "stakeholder",
  "customer_request",
  "decision",
  "action_item",
  "risk",
  "technical_constraint",
  "implementation_requirement",
  "timeline",
  "procurement",
  "security_legal",
  "budget",
  "objection",
  "commercial_intent",
  "contact_detail",
  "other",
] as const satisfies readonly VisualCandidateEvidence["category"][];

function isAllowed(value: unknown, options: readonly string[]): boolean {
  return typeof value === "string" && options.includes(value);
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isNullableIdentifier(value: unknown): boolean {
  return value === null || isIdentifier(value);
}

function isDate(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isNonnegativeInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isRegion(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const { x, y, width, height } = value;
  return (
    typeof x === "number" &&
    typeof y === "number" &&
    typeof width === "number" &&
    typeof height === "number" &&
    x >= 0 &&
    y >= 0 &&
    width > 0 &&
    height > 0 &&
    x + width <= 1 &&
    y + height <= 1
  );
}

function matchesVisualSource(
  candidate: unknown,
  visualId: unknown,
  sourceOwnership: unknown,
): candidate is Record<string, unknown> {
  return (
    isRecord(candidate) &&
    candidate.sourceVisualId === visualId &&
    candidate.sourceOwnership === sourceOwnership
  );
}

export function hasVisualCandidateSourceIdentity(
  visual: VisualEvidence,
): boolean {
  return (
    Array.isArray(visual.candidates) &&
    visual.candidates.every((candidate) =>
      matchesVisualSource(candidate, visual.id, visual.sourceOwnership),
    )
  );
}

function hasCandidateFields(candidate: Record<string, unknown>): boolean {
  return (
    isAllowed(candidate.category, evidenceCategories) &&
    typeof candidate.statement === "string" &&
    typeof candidate.originalStatement === "string" &&
    candidate.origin === "ai_inferred" &&
    isAllowed(candidate.supportClassification, [
      "direct",
      "observed",
      "context",
    ]) &&
    isAllowed(candidate.validationState, [
      "unreviewed",
      "verified",
      "rejected",
    ]) &&
    isAllowed(candidate.reviewState, ["pending", "accepted", "rejected"]) &&
    isAllowed(candidate.conflictState, ["not_assessed", "conflicting"]) &&
    (candidate.confidenceClass === null ||
      isAllowed(candidate.confidenceClass, ["low", "medium", "high"])) &&
    (candidate.evidenceRegion === null || isRegion(candidate.evidenceRegion)) &&
    isNullableString(candidate.relatedEntity) &&
    isNullableString(candidate.extractedTextSnippet) &&
    isNullableIdentifier(candidate.acceptedEvidenceId) &&
    typeof candidate.edited === "boolean"
  );
}

function hasVerifiedCandidates(visual: Record<string, unknown>): boolean {
  if (!Array.isArray(visual.candidates)) return false;

  const candidateIds = new Set<string>();
  for (const candidate of visual.candidates) {
    if (
      !matchesVisualSource(candidate, visual.id, visual.sourceOwnership) ||
      !isIdentifier(candidate.id) ||
      candidateIds.has(candidate.id) ||
      !hasCandidateFields(candidate)
    ) {
      return false;
    }
    candidateIds.add(candidate.id);
  }
  return true;
}

function isVisualEvidenceForInteraction(
  visual: unknown,
  interactionId: string,
): visual is VisualEvidence {
  return (
    isRecord(visual) &&
    isIdentifier(visual.id) &&
    visual.interactionId === interactionId &&
    visual.captureSessionId === visual.id &&
    isAllowed(visual.visualType, VISUAL_TYPES) &&
    isAllowed(visual.sourceOwnership, VISUAL_SOURCE_OWNERSHIP) &&
    isNullableString(visual.contextLabel) &&
    typeof visual.filename === "string" &&
    isAllowed(visual.mimeType, ["image/jpeg", "image/png"]) &&
    isNonnegativeInteger(visual.byteSize) &&
    (visual.width === null || isNonnegativeInteger(visual.width)) &&
    (visual.height === null || isNonnegativeInteger(visual.height)) &&
    typeof visual.checksumSha256 === "string" &&
    isDate(visual.capturedAt) &&
    isAllowed(visual.processingStatus, processingStatuses) &&
    isNonnegativeInteger(visual.processingAttempts) &&
    isNullableString(visual.failureCode) &&
    isAllowed(visual.providerMode, ["mock", "openai"]) &&
    typeof visual.externalProcessing === "boolean" &&
    hasVerifiedCandidates(visual) &&
    isNullableString(visual.downloadUrl) &&
    isNullableIdentifier(visual.interactionIntelligenceId) &&
    isNullableIdentifier(visual.revenueBrainSnapshotId) &&
    isDate(visual.createdAt) &&
    isDate(visual.updatedAt)
  );
}

export function validateVisualEvidenceListForInteraction(
  response: unknown,
  interactionId: string,
): VisualEvidence[] {
  if (!Array.isArray(response)) {
    throw new Error(VISUAL_RESPONSE_IDENTITY_ERROR);
  }

  const validated: VisualEvidence[] = [];
  const visualIds = new Set<string>();
  for (const visual of response) {
    if (
      !isVisualEvidenceForInteraction(visual, interactionId) ||
      visualIds.has(visual.id)
    ) {
      throw new Error(VISUAL_RESPONSE_IDENTITY_ERROR);
    }
    visualIds.add(visual.id);
    validated.push(visual);
  }
  return validated;
}
