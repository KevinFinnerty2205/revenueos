import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { LiveIntelligenceResponse } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { suggestConversationQuestion } from "@/lib/conversation-guidance";
import { LiveInteractionIntelligence } from "@/components/live-interaction-intelligence";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function liveResponse(
  overrides: Partial<LiveIntelligenceResponse> = {},
): LiveIntelligenceResponse {
  return {
    availability: "available",
    state: "active",
    safeMessage:
      "Live signals are provisional, may change and need post-interaction review.",
    sourceKind: "progressive_transcript",
    sessionId: "live-session-1",
    signals: [
      {
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
          sequenceStart: 2,
          sequenceEnd: 2,
        },
        detectedAt: "2026-08-15T02:03:00Z",
        lastUpdatedAt: "2026-08-15T02:03:00Z",
        supersededBy: null,
      },
      {
        id: "signal-2",
        signalType: "risk",
        statement: "Security review may take four weeks.",
        lifecycleStatus: "detected",
        provisional: true,
        priority: "high",
        evidenceStrength: "speaker_uncertain",
        resolutionStatus: "pending",
        source: {
          transcriptVersionId: "transcript-1",
          sequenceStart: 3,
          sequenceEnd: 3,
        },
        detectedAt: "2026-08-15T02:04:00Z",
        lastUpdatedAt: "2026-08-15T02:04:00Z",
        supersededBy: null,
      },
    ],
    objectives: [
      {
        itemType: "objective",
        itemIndex: 0,
        label: "Confirm implementation timeline",
        progressStatus: "possibly_addressed",
      },
      {
        itemType: "objective",
        itemIndex: 1,
        label: "Meet economic buyer",
        progressStatus: "unresolved",
      },
    ],
    openQuestions: [
      {
        itemType: "open_question",
        itemIndex: 0,
        label: "Who owns security approval?",
        progressStatus: "unresolved",
      },
    ],
    reconciliation: null,
    generatedAt: "2026-08-15T02:04:00Z",
    updatedAt: "2026-08-15T02:04:00Z",
    nextPollSeconds: 15,
    ...overrides,
  };
}

describe("LiveInteractionIntelligence", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows a quiet provisional panel with conservative speaker wording", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(liveResponse()))),
    );
    render(
      <LiveInteractionIntelligence
        interactionId="interaction-1"
        interactionInProgress
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Live Companion" }),
    ).toBeVisible();
    expect(screen.getByText("Provisional · needs review")).toBeVisible();
    expect(
      screen.getByText("Confirm implementation timeline — Possibly addressed"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Live Companion" }),
    ).toBeVisible();
    expect(screen.getByText("Suggested next question")).toBeVisible();
    expect(
      screen.getByText("Who owns security approval? — Unresolved"),
    ).toBeVisible();
    expect(
      screen.getByText(/What would be the most useful next step for you/),
    ).toBeVisible();
    expect(screen.getByText("Why this question?")).toBeVisible();
    expect(
      screen.getAllByText("Customer asked about an October rollout.").at(-1),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Speaker identity is uncertain; treat this signal conservatively/i,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Collapse" }));
    expect(
      screen.queryByText("Customer asked about an October rollout."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("dismisses an individual provisional signal without a toast or alert", async () => {
    const dismissed = liveResponse({
      signals: [
        {
          ...liveResponse().signals[0],
          lifecycleStatus: "dismissed",
        },
      ],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/signal-1/dismiss") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(dismissed));
      }
      return Promise.resolve(jsonResponse(liveResponse()));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <LiveInteractionIntelligence
        interactionId="interaction-1"
        interactionInProgress
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Dismiss possible buying signal",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByText("Customer asked about an October rollout."),
      ).not.toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/signal-1/dismiss"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows unavailable fallback and a compact final reconciliation", async () => {
    const unavailable = liveResponse({
      availability: "unavailable",
      state: "unavailable",
      safeMessage:
        "Live Intelligence is unavailable without an authorised progressive source. Use Debrief afterwards.",
      sourceKind: null,
      sessionId: null,
      signals: [],
      objectives: [],
      reconciliation: null,
      generatedAt: null,
      updatedAt: null,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(unavailable))
      .mockResolvedValue(
        jsonResponse(
          liveResponse({
            state: "completed",
            reconciliation: {
              confirmed: 1,
              revised: 1,
              unsupported: 0,
              unresolved: 1,
            },
          }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const view = render(
      <LiveInteractionIntelligence interactionId="interaction-1" />,
    );
    expect(
      await screen.findByRole("heading", {
        name: "Live Intelligence unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Use Debrief afterwards/i)).toBeVisible();

    view.unmount();
    render(
      <LiveInteractionIntelligence
        interactionId="interaction-1"
        interactionCompleted
      />,
    );
    expect(await screen.findByText(/1 confirmed · 1 revised/i)).toBeVisible();
  });
});

describe("source-grounded conversation guidance", () => {
  it("adapts to an objection and cites its source without treating the suggestion as evidence", () => {
    const live = liveResponse();
    live.signals[0] = {
      ...live.signals[0]!,
      signalType: "objection",
      statement: "Customer is concerned about the price.",
    };
    const guidance = suggestConversationQuestion(live);
    expect(guidance?.question).toContain("main concern");
    expect(guidance?.signal?.source.sequenceStart).toBe(2);
    expect(guidance?.reason).toContain("possible customer signal");
  });

  it("selects a related unanswered framework question and moves on when it has possibly been answered", () => {
    const live = liveResponse();
    live.signals[0] = {
      ...live.signals[0]!,
      signalType: "security_legal",
      statement: "Customer asked about security approval.",
    };
    expect(suggestConversationQuestion(live)?.question).toBe(
      "Who owns security approval?",
    );
    live.openQuestions[0]!.progressStatus = "possibly_answered";
    expect(suggestConversationQuestion(live)?.question).toContain(
      "review need to cover",
    );
  });

  it("does not coach from dismissed, uncertain or unsupported signals, or after capture ends", () => {
    const live = liveResponse();
    live.signals[0]!.lifecycleStatus = "dismissed";
    expect(suggestConversationQuestion(live)?.signal).toBeNull();
    live.signals[0]!.lifecycleStatus = "detected";
    live.signals[0]!.resolutionStatus = "unsupported";
    expect(suggestConversationQuestion(live)?.signal).toBeNull();
    live.state = "completed";
    expect(suggestConversationQuestion(live)).toBeNull();
  });
});
