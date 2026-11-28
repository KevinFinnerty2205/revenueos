import type {
  LiveBriefProgress,
  LiveIntelligenceResponse,
  ProvisionalLiveSignal,
} from "@revenueos/shared";
import { describe, expect, it } from "vitest";
import {
  decodeLiveIntelligenceResponse,
  LIVE_INTELLIGENCE_IDENTITY_ERROR,
} from "@/lib/live-intelligence-response-identity";

const interactionIdentity = {
  interactionId: "interaction-1",
  organisationId: "organisation-1",
};
const identity = { ...interactionIdentity, sessionId: "session-1" };
const timestamp = "2026-08-15T02:04:00.123456Z";
const signal: ProvisionalLiveSignal = {
  id: "signal-1",
  signalType: "buying_signal",
  statement: "Customer asked about an October rollout.",
  lifecycleStatus: "detected",
  provisional: true,
  priority: "high",
  evidenceStrength: "customer_attributed",
  resolutionStatus: "pending",
  source: {
    transcriptVersionId: "transcript-1",
    sequenceStart: 3,
    sequenceEnd: 4,
  },
  detectedAt: timestamp,
  lastUpdatedAt: timestamp,
  supersededBy: null,
};
const objective: LiveBriefProgress = {
  itemType: "objective",
  itemIndex: 0,
  label: "Agree a rollout plan",
  progressStatus: "possibly_addressed",
};
const question: LiveBriefProgress = {
  itemType: "open_question",
  itemIndex: 0,
  label: "Who owns security approval?",
  progressStatus: "unresolved",
};
const active: LiveIntelligenceResponse = {
  ...identity,
  availability: "available",
  state: "active",
  safeMessage: "Provisional guidance.",
  sourceKind: "progressive_transcript",
  signals: [signal],
  objectives: [objective],
  openQuestions: [question],
  reconciliation: null,
  generatedAt: timestamp,
  updatedAt: "2026-08-15T02:05:00+00:00",
  nextPollSeconds: 15,
};
const completed: LiveIntelligenceResponse = {
  ...active,
  state: "completed",
  reconciliation: { confirmed: 1, revised: 0, unsupported: 0, unresolved: 0 },
};

function inactive(
  state: "available" | "unavailable" | "disabled",
): LiveIntelligenceResponse {
  return {
    ...active,
    availability: state,
    state,
    sourceKind: state === "available" ? "progressive_transcript" : null,
    sessionId: null,
    signals: [],
    objectives: [],
    openQuestions: [],
    reconciliation: null,
    generatedAt: null,
    updatedAt: null,
  };
}

describe("decodeLiveIntelligenceResponse", () => {
  it.each(["available", "unavailable", "disabled"] as const)(
    "accepts the canonical %s response without a session",
    (state) => {
      const value = inactive(state);
      expect(
        decodeLiveIntelligenceResponse(value, interactionIdentity),
      ).toEqual(value);
    },
  );

  it.each(["active", "processing", "failed", "completed"] as const)(
    "accepts a verified %s session with bounded polling",
    (state) => {
      const response = {
        ...active,
        state,
        nextPollSeconds: state === "active" ? 5 : 60,
      };
      expect(decodeLiveIntelligenceResponse(response, identity)).toEqual(
        response,
      );
    },
  );

  it.each([
    ["another organisation", { ...active, organisationId: "organisation-2" }],
    ["another interaction", { ...active, interactionId: "interaction-2" }],
    ["another session", { ...active, sessionId: "session-2" }],
    ["a missing session", { ...active, sessionId: null }],
    ["an unknown state", { ...active, state: "ready" }],
    ["a session with no source", { ...active, sourceKind: null }],
    [
      "a session with incompatible availability",
      { ...active, availability: "disabled" },
    ],
    [
      "premature reconciliation",
      { ...active, reconciliation: completed.reconciliation },
    ],
    ["a fractional interval", { ...active, nextPollSeconds: 5.2 }],
    ["a too-fast interval", { ...active, nextPollSeconds: 4 }],
    ["a too-slow interval", { ...active, nextPollSeconds: 61 }],
    [
      "a timestamp missing its timezone",
      { ...active, updatedAt: "2026-08-15T02:05:00" },
    ],
    [
      "a raw transcript in the envelope",
      { ...active, rawTranscript: "Hidden source" },
    ],
    ["duplicate signal IDs", { ...active, signals: [signal, signal] }],
    [
      "a non-provisional signal",
      { ...active, signals: [{ ...signal, provisional: false }] },
    ],
    [
      "a malformed source range",
      {
        ...active,
        signals: [{ ...signal, source: { ...signal.source, sequenceEnd: 1 } }],
      },
    ],
    [
      "raw text in a source",
      {
        ...active,
        signals: [
          { ...signal, source: { ...signal.source, text: "Hidden source" } },
        ],
      },
    ],
    [
      "an objective in the question lane",
      { ...active, openQuestions: [objective] },
    ],
    [
      "duplicated objectives",
      { ...active, objectives: [objective, objective] },
    ],
    [
      "a malformed reconciliation count",
      {
        ...completed,
        reconciliation: { ...completed.reconciliation, confirmed: -1 },
      },
    ],
  ])("rejects %s", (_name, value) => {
    expect(() => decodeLiveIntelligenceResponse(value, identity)).toThrow(
      LIVE_INTELLIGENCE_IDENTITY_ERROR,
    );
  });

  it("rejects progress data with no session", () => {
    expect(() =>
      decodeLiveIntelligenceResponse(
        { ...inactive("available"), openQuestions: [question] },
        interactionIdentity,
      ),
    ).toThrow(LIVE_INTELLIGENCE_IDENTITY_ERROR);
  });

  it("validates the process receipt before returning live state", () => {
    expect(
      decodeLiveIntelligenceResponse(
        { ...active, processed: false, newSegmentCount: 2 },
        identity,
        "process",
      ),
    ).toEqual(active);
    expect(
      decodeLiveIntelligenceResponse(
        { ...active, processed: true, newSegmentCount: 0 },
        identity,
        "process",
      ),
    ).toEqual(active);
    // A concurrent stop can win after process commits and before it reads back state.
    expect(
      decodeLiveIntelligenceResponse(
        { ...completed, processed: true, newSegmentCount: 2 },
        { ...identity, sessionId: completed.sessionId ?? undefined },
        "process",
      ),
    ).toEqual(completed);
    for (const receipt of [
      active,
      { ...active, processed: "yes", newSegmentCount: 2 },
      { ...active, processed: true, newSegmentCount: -1 },
    ]) {
      expect(() =>
        decodeLiveIntelligenceResponse(receipt, identity, "process"),
      ).toThrow(LIVE_INTELLIGENCE_IDENTITY_ERROR);
    }
  });

  it("validates the completed reconciliation and confirmation together", () => {
    expect(
      decodeLiveIntelligenceResponse(
        { ...completed, reconciled: true },
        identity,
        "reconcile",
      ),
    ).toEqual(completed);
    for (const receipt of [
      { ...completed, reconciled: false },
      { ...completed, reconciliation: null, reconciled: true },
      { ...active, reconciled: true },
    ]) {
      expect(() =>
        decodeLiveIntelligenceResponse(receipt, identity, "reconcile"),
      ).toThrow(LIVE_INTELLIGENCE_IDENTITY_ERROR);
    }
  });
});
