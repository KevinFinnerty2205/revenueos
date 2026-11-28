import type {
  VisualCandidateEvidence,
  VisualEvidence,
} from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import {
  validateVisualEvidenceListForInteraction,
  VISUAL_RESPONSE_IDENTITY_ERROR,
} from "@/lib/visual-evidence-identity";

const interactionId = "interaction-1";
const timestamp = "2026-08-14T02:00:00Z";
const candidate: VisualCandidateEvidence = {
  id: "candidate-1",
  category: "customer_request",
  statement: "Arrange a workshop.",
  originalStatement: "Arrange a workshop.",
  sourceVisualId: "visual-1",
  sourceOwnership: "jointly_created",
  origin: "ai_inferred",
  supportClassification: "observed",
  validationState: "unreviewed",
  reviewState: "pending",
  conflictState: "not_assessed",
  confidenceClass: null,
  evidenceRegion: { x: 0, y: 0, width: 1, height: 1 },
  relatedEntity: null,
  extractedTextSnippet: null,
  acceptedEvidenceId: null,
  edited: false,
};
const visual: VisualEvidence = {
  id: "visual-1",
  interactionId,
  captureSessionId: "visual-1",
  visualType: "workshop_output",
  sourceOwnership: "jointly_created",
  contextLabel: null,
  filename: "whiteboard.png",
  mimeType: "image/png",
  byteSize: 68,
  width: 1,
  height: 1,
  checksumSha256: "a".repeat(64),
  capturedAt: timestamp,
  processingStatus: "review",
  processingAttempts: 1,
  failureCode: null,
  providerMode: "mock",
  externalProcessing: false,
  candidates: [candidate],
  downloadUrl:
    "/api/v1/interactions/interaction-1/visual-evidence/visual-1/content?token=test",
  interactionIntelligenceId: null,
  revenueBrainSnapshotId: null,
  createdAt: timestamp,
  updatedAt: timestamp,
};
const unprocessed: VisualEvidence = {
  ...visual,
  id: "visual-2",
  captureSessionId: "visual-2",
  processingStatus: "uploading",
  processingAttempts: 0,
  width: null,
  height: null,
  downloadUrl: null,
  candidates: [],
};

describe("validateVisualEvidenceListForInteraction", () => {
  it("accepts an empty list and preserves the order of valid photos", () => {
    expect(validateVisualEvidenceListForInteraction([], interactionId)).toEqual(
      [],
    );
    expect(
      validateVisualEvidenceListForInteraction(
        [unprocessed, visual],
        interactionId,
      ),
    ).toEqual([unprocessed, visual]);
  });

  it.each([
    ["an unexpected envelope", { items: [visual] }],
    ["a non-object item", [unprocessed, null]],
    [
      "a foreign interaction",
      [unprocessed, { ...visual, interactionId: "other" }],
    ],
    [
      "a mismatched capture session",
      [unprocessed, { ...visual, captureSessionId: "other" }],
    ],
    [
      "a malformed visual field",
      [unprocessed, { ...visual, processingStatus: "unknown" }],
    ],
    ["duplicate visual IDs", [visual, visual]],
    [
      "a malformed candidate",
      [
        unprocessed,
        { ...visual, candidates: [{ ...candidate, statement: {} }] },
      ],
    ],
    [
      "a foreign candidate source",
      [
        unprocessed,
        { ...visual, candidates: [{ ...candidate, sourceVisualId: "other" }] },
      ],
    ],
    [
      "a foreign candidate owner",
      [
        unprocessed,
        {
          ...visual,
          candidates: [
            { ...candidate, sourceOwnership: "salesperson_created" },
          ],
        },
      ],
    ],
    [
      "duplicate candidate IDs",
      [unprocessed, { ...visual, candidates: [candidate, candidate] }],
    ],
  ])("rejects the whole response for %s", (_case, response) => {
    expect(() =>
      validateVisualEvidenceListForInteraction(response, interactionId),
    ).toThrow(VISUAL_RESPONSE_IDENTITY_ERROR);
  });
});
