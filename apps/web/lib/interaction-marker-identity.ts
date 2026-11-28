import type {
  InteractionMarker,
  InteractionMarkerType,
} from "@revenueos/shared";
import { isRecord } from "@/lib/private-response-identity";

export const INTERACTION_MARKER_IDENTITY_ERROR =
  "The marker response did not match this conversation.";

const markerTypes = {
  buying_signal: true,
  objection: true,
  decision: true,
  action_item: true,
  risk: true,
  stakeholder: true,
  timeline: true,
  budget: true,
  procurement: true,
  follow_up: true,
  important_moment: true,
  customer_question: true,
  requested_material: true,
  strong_engagement: true,
} satisfies Record<InteractionMarkerType, true>;

const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isRecordingOffset(value: unknown): value is number | null {
  return (
    value === null ||
    (typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= 14_400_000)
  );
}

function isInteractionMarker(
  value: unknown,
  interactionId: string,
): value is InteractionMarker {
  return (
    isRecord(value) &&
    isIdentifier(value.id) &&
    isIdentifier(value.interactionId) &&
    value.interactionId === interactionId &&
    isIdentifier(value.createdByUserId) &&
    typeof value.markerType === "string" &&
    Object.hasOwn(markerTypes, value.markerType) &&
    isRecordingOffset(value.recordingOffsetMs) &&
    typeof value.createdAt === "string" &&
    timestampPattern.test(value.createdAt) &&
    !Number.isNaN(Date.parse(value.createdAt))
  );
}

export function validateInteractionMarkers(
  value: unknown,
  interactionId: string,
): InteractionMarker[] {
  if (!Array.isArray(value)) throw new Error(INTERACTION_MARKER_IDENTITY_ERROR);

  const markers: InteractionMarker[] = [];
  const ids = new Set<string>();
  for (const marker of value) {
    if (!isInteractionMarker(marker, interactionId) || ids.has(marker.id)) {
      throw new Error(INTERACTION_MARKER_IDENTITY_ERROR);
    }
    ids.add(marker.id);
    markers.push(marker);
  }
  return markers;
}

export function validateCreatedInteractionMarker(
  value: unknown,
  expected: Pick<
    InteractionMarker,
    "interactionId" | "createdByUserId" | "markerType" | "recordingOffsetMs"
  >,
): InteractionMarker {
  if (
    !isInteractionMarker(value, expected.interactionId) ||
    value.createdByUserId !== expected.createdByUserId ||
    value.markerType !== expected.markerType ||
    value.recordingOffsetMs !== expected.recordingOffsetMs
  ) {
    throw new Error(INTERACTION_MARKER_IDENTITY_ERROR);
  }
  return value;
}

export function validateDeletedInteractionMarker(
  value: unknown,
  markerId: string,
): void {
  if (
    !isRecord(value) ||
    !isIdentifier(value.id) ||
    value.id !== markerId ||
    value.deleted !== true
  ) {
    throw new Error(INTERACTION_MARKER_IDENTITY_ERROR);
  }
}
