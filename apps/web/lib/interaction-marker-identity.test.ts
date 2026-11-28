import type { InteractionMarker } from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import {
  INTERACTION_MARKER_IDENTITY_ERROR,
  validateCreatedInteractionMarker,
  validateDeletedInteractionMarker,
  validateInteractionMarkers,
} from "@/lib/interaction-marker-identity";

const marker = {
  id: "marker-1",
  interactionId: "interaction-1",
  createdByUserId: "user-1",
  markerType: "important_moment",
  recordingOffsetMs: null,
  createdAt: "2026-08-15T00:00:00.123456Z",
} satisfies InteractionMarker;

const secondMarker = { ...marker, id: "marker-2" };

describe("validateInteractionMarkers", () => {
  it("accepts an empty list and a conversation's markers from multiple users in order", () => {
    const otherUserMarker = {
      ...secondMarker,
      createdByUserId: "user-2",
      markerType: "budget",
      recordingOffsetMs: 14_400_000,
      createdAt: "2026-08-15T03:00:00+00:00",
    };

    expect(validateInteractionMarkers([], marker.interactionId)).toEqual([]);
    expect(
      validateInteractionMarkers(
        [marker, otherUserMarker],
        marker.interactionId,
      ),
    ).toEqual([marker, otherUserMarker]);
  });

  it.each([
    ["a non-list", marker],
    ["a duplicate ID", [marker, marker]],
    [
      "another conversation",
      [marker, { ...secondMarker, interactionId: "other" }],
    ],
    ["an incomplete marker", [marker, { id: "marker-2" }]],
    [
      "a missing offset",
      [marker, { ...secondMarker, recordingOffsetMs: undefined }],
    ],
    ["an invalid offset", [marker, { ...secondMarker, recordingOffsetMs: -1 }]],
    [
      "a fractional offset",
      [marker, { ...secondMarker, recordingOffsetMs: 0.5 }],
    ],
    [
      "an out-of-range offset",
      [marker, { ...secondMarker, recordingOffsetMs: 14_400_001 }],
    ],
    [
      "an invalid type",
      [marker, { ...secondMarker, markerType: "constructor" }],
    ],
    ["a missing creator", [marker, { ...secondMarker, createdByUserId: " " }]],
    ["a missing identifier", [marker, { ...secondMarker, id: "" }]],
    ["an invalid timestamp", [marker, { ...secondMarker, createdAt: "2026" }]],
  ])("rejects the whole response with %s", (_reason, response) => {
    expect(() =>
      validateInteractionMarkers(response, marker.interactionId),
    ).toThrow(INTERACTION_MARKER_IDENTITY_ERROR);
  });
});

describe("validateCreatedInteractionMarker", () => {
  it("accepts the requested creator, conversation, type and offset", () => {
    expect(validateCreatedInteractionMarker(marker, marker)).toEqual(marker);

    const timedMarker = { ...marker, recordingOffsetMs: 0 };
    expect(validateCreatedInteractionMarker(timedMarker, timedMarker)).toEqual(
      timedMarker,
    );
  });

  it.each([
    ["conversation", { interactionId: "interaction-2" }],
    ["creator", { createdByUserId: "user-2" }],
    ["type", { markerType: "decision" }],
    ["offset", { recordingOffsetMs: 0 }],
  ])("rejects a different %s", (_reason, override) => {
    expect(() =>
      validateCreatedInteractionMarker({ ...marker, ...override }, marker),
    ).toThrow(INTERACTION_MARKER_IDENTITY_ERROR);
  });
});

describe("validateDeletedInteractionMarker", () => {
  it("accepts positive confirmation for the requested marker", () => {
    expect(() =>
      validateDeletedInteractionMarker(
        { id: marker.id, deleted: true },
        marker.id,
      ),
    ).not.toThrow();
  });

  it.each([
    { id: "marker-2", deleted: true },
    { id: marker.id, deleted: false },
    { id: marker.id, deleted: "true" },
    { id: marker.id },
    null,
  ])("rejects an unverified acknowledgement", (response) => {
    expect(() => validateDeletedInteractionMarker(response, marker.id)).toThrow(
      INTERACTION_MARKER_IDENTITY_ERROR,
    );
  });
});
