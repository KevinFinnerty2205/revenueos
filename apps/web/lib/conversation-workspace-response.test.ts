import { describe, expect, it } from "vitest";
import { decodeConversationWorkspaceResponse } from "@/lib/conversation-workspace-response";

const identity = {
  interactionId: "interaction-1",
  organisationId: "organisation-1",
  ownerUserId: "user-1",
};

const workspace = {
  exists: true,
  ...identity,
  lockVersion: 4,
  liveNotes: "Private rough notes",
  enhancedNotes: "Private enhanced notes",
  followUpDraft: "Private follow-up",
  followUpReviewed: false,
  generationFingerprint: "a".repeat(64),
  generationState: "ready",
  generationId: "generation-1",
  generationTranscriptVersion: 2,
  generationPersonalNotesState: "current",
  generationFailureCode: null,
  generationRetryAvailable: false,
  generationUpdateAvailable: true,
  generationCompletedAt: "2026-11-22T00:00:00Z",
  importedFromBrowserAt: null,
  updatedAt: "2026-11-22T00:00:00Z",
};

describe("decodeConversationWorkspaceResponse", () => {
  it("returns a completely decoded workspace for the expected private identity", () => {
    expect(decodeConversationWorkspaceResponse(workspace, identity)).toEqual(
      workspace,
    );
  });

  it.each([
    ["interaction", { interactionId: "interaction-foreign" }],
    ["organisation", { organisationId: "organisation-foreign" }],
    ["owner", { ownerUserId: "user-foreign" }],
    ["boolean", { followUpReviewed: "false" }],
    ["lock version", { lockVersion: -1 }],
    ["generation version", { generationTranscriptVersion: 1.5 }],
    ["generation state", { generationState: "complete" }],
    ["personal-notes state", { generationPersonalNotesState: "stale" }],
    ["timestamp", { updatedAt: "22 November 2026" }],
  ])("rejects a mismatched or malformed %s", (_case, overrides) => {
    expect(
      decodeConversationWorkspaceResponse(
        { ...workspace, ...overrides },
        identity,
      ),
    ).toBeNull();
  });
});
