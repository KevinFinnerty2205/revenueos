import type {
  LiveBriefProgress,
  LiveIntelligenceResponse,
  LiveReconciliationSummary,
  LiveSourceReference,
  ProvisionalLiveSignal,
} from "@revenueos/shared";
import { isRecord } from "@/lib/private-response-identity";

export const LIVE_INTELLIGENCE_IDENTITY_ERROR =
  "The Live Intelligence response could not be verified. Try again.";

const states = [
  "available",
  "unavailable",
  "disabled",
  "active",
  "processing",
  "completed",
  "failed",
] as const;

const signalTypes = [
  "buying_signal",
  "objection",
  "stakeholder",
  "decision",
  "action_item",
  "risk",
  "timeline",
  "procurement",
  "security_legal",
  "customer_request",
  "commercial_intent",
  "objective_progress",
  "open_question_progress",
  "other",
] as const;

const signalLifecycles = [
  "detected",
  "updated",
  "superseded",
  "dismissed",
  "promoted_candidate",
  "expired",
] as const;

const responseKeys = [
  "interactionId",
  "organisationId",
  "availability",
  "state",
  "safeMessage",
  "sourceKind",
  "sessionId",
  "signals",
  "objectives",
  "openQuestions",
  "reconciliation",
  "generatedAt",
  "updatedAt",
  "nextPollSeconds",
];

type ResponseKind = "process" | "reconcile";

type ExpectedLiveIdentity = {
  interactionId: string;
  organisationId: string;
  sessionId?: string;
};

function invalidResponse(): never {
  throw new Error(LIVE_INTELLIGENCE_IDENTITY_ERROR);
}

function hasExactKeys(
  value: Record<string, unknown>,
  fields: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === fields.length && keys.every((key) => fields.includes(key))
  );
}

function isOneOf<T extends string>(
  value: unknown,
  options: readonly T[],
): value is T {
  return options.some((option) => option === value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isIntegerInRange(
  value: unknown,
  minimum: number,
  maximum = Number.MAX_SAFE_INTEGER,
): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/u.test(
      value,
    ) &&
    Number.isFinite(Date.parse(value))
  );
}

function isSourceReference(value: unknown): value is LiveSourceReference {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "transcriptVersionId",
      "sequenceStart",
      "sequenceEnd",
    ]) &&
    isText(value.transcriptVersionId) &&
    isIntegerInRange(value.sequenceStart, 0) &&
    isIntegerInRange(value.sequenceEnd, value.sequenceStart)
  );
}

function isSignal(value: unknown): value is ProvisionalLiveSignal {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "id",
      "signalType",
      "statement",
      "lifecycleStatus",
      "provisional",
      "priority",
      "evidenceStrength",
      "resolutionStatus",
      "source",
      "detectedAt",
      "lastUpdatedAt",
      "supersededBy",
    ]) &&
    isText(value.id) &&
    isOneOf(value.signalType, signalTypes) &&
    isText(value.statement) &&
    isOneOf(value.lifecycleStatus, signalLifecycles) &&
    value.provisional === true &&
    isOneOf(value.priority, ["high", "normal"]) &&
    isOneOf(value.evidenceStrength, [
      "customer_attributed",
      "speaker_uncertain",
      "context_only",
    ]) &&
    isOneOf(value.resolutionStatus, [
      "pending",
      "confirmed",
      "revised",
      "unsupported",
      "unresolved",
    ]) &&
    isSourceReference(value.source) &&
    isTimestamp(value.detectedAt) &&
    isTimestamp(value.lastUpdatedAt) &&
    (value.supersededBy === null || isText(value.supersededBy))
  );
}

function isProgressItem(
  value: unknown,
  itemType: LiveBriefProgress["itemType"],
): value is LiveBriefProgress {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["itemType", "itemIndex", "label", "progressStatus"]) &&
    value.itemType === itemType &&
    isIntegerInRange(value.itemIndex, 0, 20) &&
    isText(value.label) &&
    isOneOf(value.progressStatus, [
      "unresolved",
      "possibly_addressed",
      "possibly_answered",
    ])
  );
}

function isReconciliation(value: unknown): value is LiveReconciliationSummary {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "confirmed",
      "revised",
      "unsupported",
      "unresolved",
    ]) &&
    isIntegerInRange(value.confirmed, 0) &&
    isIntegerInRange(value.revised, 0) &&
    isIntegerInRange(value.unsupported, 0) &&
    isIntegerInRange(value.unresolved, 0)
  );
}

function isUniqueList<T>(
  value: unknown,
  limit: number,
  isItem: (item: unknown) => item is T,
  identity: (item: T) => string | number,
): value is T[] {
  if (!Array.isArray(value) || value.length > limit) return false;
  const identities = new Set<string | number>();
  for (const item of value) {
    if (!isItem(item)) return false;
    const id = identity(item);
    if (identities.has(id)) return false;
    identities.add(id);
  }
  return true;
}

export function decodeLiveIntelligenceResponse(
  value: unknown,
  expected: ExpectedLiveIdentity,
  kind?: ResponseKind,
): LiveIntelligenceResponse {
  const extensionKeys =
    kind === "process"
      ? ["processed", "newSegmentCount"]
      : kind === "reconcile"
        ? ["reconciled"]
        : [];
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [...responseKeys, ...extensionKeys])
  ) {
    invalidResponse();
  }

  const {
    interactionId,
    organisationId,
    availability,
    state,
    safeMessage,
    sourceKind,
    sessionId,
    signals,
    objectives,
    openQuestions,
    reconciliation,
    generatedAt,
    updatedAt,
    nextPollSeconds,
  } = value;
  if (
    !isText(interactionId) ||
    interactionId !== expected.interactionId ||
    !isText(organisationId) ||
    organisationId !== expected.organisationId ||
    !isOneOf(availability, ["available", "unavailable", "disabled"]) ||
    !isOneOf(state, states) ||
    !isText(safeMessage) ||
    !(sourceKind === null || sourceKind === "progressive_transcript") ||
    !(sessionId === null || isText(sessionId)) ||
    (expected.sessionId !== undefined && sessionId !== expected.sessionId) ||
    !isUniqueList(signals, 100, isSignal, (signal) => signal.id) ||
    !isUniqueList(
      objectives,
      20,
      (item): item is LiveBriefProgress => isProgressItem(item, "objective"),
      (item) => item.itemIndex,
    ) ||
    !isUniqueList(
      openQuestions,
      20,
      (item): item is LiveBriefProgress =>
        isProgressItem(item, "open_question"),
      (item) => item.itemIndex,
    ) ||
    !(reconciliation === null || isReconciliation(reconciliation)) ||
    !(generatedAt === null || isTimestamp(generatedAt)) ||
    !(updatedAt === null || isTimestamp(updatedAt)) ||
    !isIntegerInRange(nextPollSeconds, 5, 60)
  ) {
    invalidResponse();
  }

  if (
    state === "available" ||
    state === "unavailable" ||
    state === "disabled"
  ) {
    if (
      availability !== state ||
      sourceKind !==
        (state === "available" ? "progressive_transcript" : null) ||
      sessionId !== null ||
      signals.length > 0 ||
      objectives.length > 0 ||
      openQuestions.length > 0 ||
      reconciliation !== null ||
      generatedAt !== null ||
      updatedAt !== null
    ) {
      invalidResponse();
    }
  } else if (
    availability !== "available" ||
    sourceKind !== "progressive_transcript" ||
    sessionId === null ||
    (state !== "completed" && reconciliation !== null)
  ) {
    invalidResponse();
  }

  if (
    (kind === "process" &&
      (sessionId === null ||
        typeof value.processed !== "boolean" ||
        !isIntegerInRange(value.newSegmentCount, 0))) ||
    (kind === "reconcile" &&
      (state !== "completed" ||
        reconciliation === null ||
        value.reconciled !== true))
  ) {
    invalidResponse();
  }

  return {
    interactionId,
    organisationId,
    availability,
    state,
    safeMessage,
    sourceKind,
    sessionId,
    signals,
    objectives,
    openQuestions,
    reconciliation,
    generatedAt,
    updatedAt,
    nextPollSeconds,
  };
}
