import type { Interaction } from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import { decodeInteractionResponse } from "@/lib/interaction-response-identity";

function interaction(overrides: Partial<Interaction> = {}): Interaction {
  return {
    id: "interaction-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    contactId: "contact-1",
    meetingId: "meeting-1",
    eventId: "event-1",
    interactionType: "face_to_face_meeting",
    lifecycleStatus: "planned",
    title: "Harbour renewal workshop",
    scheduledStartAt: "2026-08-15T02:00:00Z",
    scheduledEndAt: "2026-08-15T03:00:00Z",
    actualStartAt: null,
    actualEndAt: null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    callDirection: null,
    callOutcome: null,
    durationSeconds: null,
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    createdByUserId: "user-1",
    briefState: "completed",
    briefGeneratedAt: "2026-08-15T00:00:00Z",
    createdAt: "2026-08-15T00:00:00Z",
    updatedAt: "2026-08-15T00:00:00Z",
    ...overrides,
  };
}

const expectation = {
  interactionId: "interaction-1",
  organisationId: "organisation-1",
} as const;

describe("decodeInteractionResponse", () => {
  it("accepts a complete response with the requested tenant identity and lifecycle", () => {
    const response: unknown = interaction({
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });

    expect(
      decodeInteractionResponse(response, {
        ...expectation,
        baseline: interaction(),
        expectedLifecycleStatus: "in_progress",
      }),
    ).toEqual(response);
  });

  it.each([
    ["interaction", { id: "interaction-2" }],
    ["organisation", { organisationId: "organisation-2" }],
    ["schema", { lifecycleStatus: "not-a-lifecycle" }],
  ])("rejects a response with the wrong %s", (_caseName, overrides) => {
    expect(
      decodeInteractionResponse(
        interaction(overrides as Partial<Interaction>),
        {
          ...expectation,
        },
      ),
    ).toBeNull();
  });

  it.each([
    ["company", { companyId: "company-2" }],
    ["opportunity", { opportunityId: "opportunity-2" }],
    ["contact", { contactId: "contact-2" }],
    ["meeting", { meetingId: "meeting-2" }],
    ["event", { eventId: "event-2" }],
    ["type", { interactionType: "workshop" }],
    ["origin", { creationOrigin: "imported_external" }],
    ["creator", { createdByUserId: "user-2" }],
  ])("rejects a changed stable %s anchor", (_caseName, overrides) => {
    expect(
      decodeInteractionResponse(
        interaction(overrides as Partial<Interaction>),
        {
          ...expectation,
          baseline: interaction(),
        },
      ),
    ).toBeNull();
  });

  it("rejects an unexpected lifecycle without rejecting mutable lifecycle fields", () => {
    expect(
      decodeInteractionResponse(
        interaction({
          lifecycleStatus: "completed",
          title: "Updated title",
          actualStartAt: "2026-08-15T02:00:00Z",
          actualEndAt: "2026-08-15T03:00:00Z",
          callOutcome: "connected",
          durationSeconds: 3_600,
        }),
        {
          ...expectation,
          baseline: interaction(),
          expectedLifecycleStatus: "in_progress",
        },
      ),
    ).toBeNull();

    expect(
      decodeInteractionResponse(
        interaction({
          lifecycleStatus: "completed",
          title: "Updated title",
          actualStartAt: "2026-08-15T02:00:00Z",
          actualEndAt: "2026-08-15T03:00:00Z",
          callOutcome: "connected",
          durationSeconds: 3_600,
        }),
        {
          ...expectation,
          baseline: interaction(),
          expectedLifecycleStatus: "completed",
        },
      ),
    ).not.toBeNull();
  });
});
