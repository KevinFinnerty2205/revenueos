import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { LiveIntelligenceResponse } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveInteractionIntelligence } from "@/components/live-interaction-intelligence";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

const identity = { interactionId: "interaction-1", organisationId: "org-1" };

function liveResponse(
  overrides: Partial<LiveIntelligenceResponse> = {},
): LiveIntelligenceResponse {
  return {
    ...identity,
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

function availableResponse(): LiveIntelligenceResponse {
  return liveResponse({
    state: "available",
    sessionId: null,
    signals: [],
    objectives: [],
    openQuestions: [],
    generatedAt: null,
    updatedAt: null,
  });
}

function processResponse(overrides: Partial<LiveIntelligenceResponse> = {}) {
  return {
    ...liveResponse(overrides),
    processed: true,
    newSegmentCount: 1,
  };
}

async function advancePolling(ms = 15_000): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
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
    render(<LiveInteractionIntelligence {...identity} interactionInProgress />);

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
    expect(screen.getAllByText("Who owns security approval?")[0]).toBeVisible();
    expect(screen.getByText(/From your preparation/i)).toBeVisible();
    expect(
      screen.getByText("Customer asked about an October rollout."),
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
    render(<LiveInteractionIntelligence {...identity} interactionInProgress />);

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
      openQuestions: [],
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
    const view = render(<LiveInteractionIntelligence {...identity} />);
    expect(
      await screen.findByRole("heading", {
        name: "Live Intelligence unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Use Debrief afterwards/i)).toBeVisible();

    view.unmount();
    render(<LiveInteractionIntelligence {...identity} interactionCompleted />);
    expect(await screen.findByText(/1 confirmed · 1 revised/i)).toBeVisible();
  });

  it("keeps a mismatched exact response hidden and recovers on explicit retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          liveResponse({
            interactionId: "other-interaction",
            safeMessage: "Foreign conversation detail",
          }),
        ),
      )
      .mockResolvedValueOnce(jsonResponse(availableResponse()));
    vi.stubGlobal("fetch", fetchMock);
    render(<LiveInteractionIntelligence {...identity} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live Intelligence could not be loaded.",
    );
    expect(
      screen.queryByText("Foreign conversation detail"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", {
        name: "Live Intelligence is available",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reports an invalid start without replacing availability and accepts a valid retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(availableResponse()))
      .mockResolvedValueOnce(
        jsonResponse(liveResponse({ organisationId: "other-org" })),
      )
      .mockResolvedValueOnce(jsonResponse(liveResponse()));
    vi.stubGlobal("fetch", fetchMock);
    render(<LiveInteractionIntelligence {...identity} interactionInProgress />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Enable Live Intelligence" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live Intelligence could not be enabled.",
    );
    expect(
      screen.queryByText("Customer asked about an October rollout."),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Enable Live Intelligence" }),
    );
    expect(
      await screen.findByText("Customer asked about an October rollout."),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the verified signal when a dismissal acknowledgement leaves it visible", async () => {
    const payload = liveResponse();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(payload))
      .mockResolvedValueOnce(
        jsonResponse({ ...payload, safeMessage: "Unverified acknowledgement" }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ ...payload, signals: [payload.signals[1]] }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<LiveInteractionIntelligence {...identity} interactionInProgress />);
    const buttonName = "Dismiss possible buying signal";
    fireEvent.click(await screen.findByRole("button", { name: buttonName }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The provisional signal could not be dismissed.",
    );
    expect(
      screen.getByText("Customer asked about an October rollout."),
    ).toBeVisible();
    expect(
      screen.queryByText("Unverified acknowledgement"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: buttonName }));
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByText("Customer asked about an October rollout."),
    ).not.toBeInTheDocument();
  });

  it("keeps the verified panel when processing returns a different session and recovers on the next poll", async () => {
    const updatedSignal = {
      ...liveResponse().signals[0],
      statement: "A verified later update",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(liveResponse()))
      .mockResolvedValueOnce(
        jsonResponse(
          processResponse({
            sessionId: "other-session",
            safeMessage: "Unverified polling detail",
          }),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(processResponse({ signals: [updatedSignal] })),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();
    await act(async () => {
      render(
        <LiveInteractionIntelligence {...identity} interactionInProgress />,
      );
    });

    await advancePolling();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The latest provisional update is unavailable.",
    );
    expect(
      screen.getByText("Customer asked about an October rollout."),
    ).toBeVisible();
    expect(
      screen.queryByText("Unverified polling detail"),
    ).not.toBeInTheDocument();

    await advancePolling();
    expect(screen.getByText("A verified later update")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("binds the completion refresh to the verified session and allows an explicit retry", async () => {
    const foreign = liveResponse({
      sessionId: "other-session",
      state: "completed",
      safeMessage: "Unverified completed session",
    });
    const completed = liveResponse({
      state: "completed",
      safeMessage: "Verified completed session",
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(liveResponse()))
        .mockResolvedValueOnce(jsonResponse(foreign))
        .mockResolvedValueOnce(jsonResponse(completed)),
    );

    const view = render(
      <LiveInteractionIntelligence {...identity} interactionInProgress />,
    );
    await screen.findByText("Customer asked about an October rollout.");
    view.rerender(
      <LiveInteractionIntelligence {...identity} interactionCompleted />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live Intelligence could not be loaded.",
    );
    expect(
      screen.getByText("Customer asked about an October rollout."),
    ).toBeVisible();
    expect(
      screen.queryByText("Unverified completed session"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Verified completed session")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([
    {
      action: "stop",
      button: "Disable for this interaction",
      acknowledgement: {
        ...liveResponse({ state: "completed" }),
        safeMessage: "Verified stopped state",
      },
      confirmation: "Verified stopped state",
    },
    {
      action: "dismiss",
      button: "Dismiss possible buying signal",
      acknowledgement: liveResponse({
        safeMessage: "Verified dismissal state",
        signals: [liveResponse().signals[1]],
      }),
      confirmation: "Verified dismissal state",
    },
  ])(
    "ignores an older process response after $action",
    async ({ action, button, acknowledgement, confirmation }) => {
      const process = deferred<Response>();
      const command = deferred<Response>();
      const poll = vi.fn(() => process.promise);
      const fetchMock = vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith("/process")) return poll();
        if (path.endsWith(`/${action}`)) return command.promise;
        return Promise.resolve(jsonResponse(liveResponse()));
      });
      vi.stubGlobal("fetch", fetchMock);
      vi.useFakeTimers();
      render(
        <LiveInteractionIntelligence {...identity} interactionInProgress />,
      );
      await act(async () => {});
      await advancePolling();
      expect(poll).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole("button", { name: button }));
      await act(async () => {
        command.resolve(jsonResponse(acknowledgement));
      });
      expect(screen.getByText(confirmation)).toBeVisible();

      await act(async () => {
        process.resolve(
          jsonResponse(
            processResponse({ safeMessage: "Stale processing state" }),
          ),
        );
      });
      expect(screen.getByText(confirmation)).toBeVisible();
      expect(
        screen.queryByText("Stale processing state"),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      if (action === "dismiss") {
        expect(
          screen.queryByText("Customer asked about an October rollout."),
        ).not.toBeInTheDocument();
      } else {
        await advancePolling();
        expect(poll).toHaveBeenCalledTimes(1);
      }
    },
  );

  it("stops polling at completion and keeps reconciliation ahead of an older refresh", async () => {
    const process = deferred<Response>();
    const completionRefresh = deferred<Response>();
    const poll = vi.fn(() => process.promise);
    const reconciled = {
      ...liveResponse({
        state: "completed",
        reconciliation: {
          confirmed: 2,
          revised: 0,
          unsupported: 0,
          unresolved: 0,
        },
      }),
      reconciled: true,
    };
    const load = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(liveResponse()))
      .mockReturnValueOnce(completionRefresh.promise);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith("/process")) return poll();
        if (path.endsWith("/reconcile"))
          return Promise.resolve(jsonResponse(reconciled));
        return load();
      }),
    );
    vi.useFakeTimers();
    const view = render(
      <LiveInteractionIntelligence {...identity} interactionInProgress />,
    );
    await act(async () => {});
    await advancePolling();
    expect(poll).toHaveBeenCalledTimes(1);
    view.rerender(
      <LiveInteractionIntelligence {...identity} interactionCompleted />,
    );

    await act(async () => {
      process.resolve(
        jsonResponse(
          processResponse({ safeMessage: "Stale processing state" }),
        ),
      );
    });
    await advancePolling();
    expect(poll).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByText("Stale processing state"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disable for this interaction" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Compare with final intelligence" }),
      );
    });
    const summary = "2 confirmed · 0 revised · 0 unsupported · 0 unresolved";
    expect(screen.getByText(summary)).toBeVisible();
    await act(async () => {
      completionRefresh.resolve(
        jsonResponse(
          liveResponse({
            state: "completed",
            safeMessage: "Stale completion refresh",
          }),
        ),
      );
    });
    expect(
      screen.queryByText("Stale completion refresh"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(summary)).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ignores a stale polling error and issues no new process request while dismissal is pending", async () => {
    const process = deferred<Response>();
    const command = deferred<Response>();
    const poll = vi.fn(() => process.promise);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith("/process")) return poll();
        if (path.endsWith("/dismiss")) return command.promise;
        return Promise.resolve(jsonResponse(liveResponse()));
      }),
    );
    vi.useFakeTimers();
    await act(async () => {
      render(
        <LiveInteractionIntelligence {...identity} interactionInProgress />,
      );
    });
    await advancePolling();
    fireEvent.click(
      screen.getByRole("button", { name: "Dismiss possible buying signal" }),
    );
    await act(async () => {
      process.resolve(
        jsonResponse({ code: "test_poll", message: "Stale poll warning" }, 409),
      );
    });
    await advancePolling(45_000);
    expect(poll).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => {
      command.resolve(jsonResponse(liveResponse({ signals: [] })));
    });
    expect(
      screen.getByText(/No material provisional signal yet/),
    ).toBeVisible();
  });

  it.each([
    { interactionId: "interaction-2", organisationId: identity.organisationId },
    { interactionId: identity.interactionId, organisationId: "org-2" },
  ])(
    "clears private state on a conversation or organisation change",
    async (nextIdentity) => {
      const poll = deferred<Response>();
      const nextConversation = deferred<Response>();
      const initial = liveResponse();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(initial))
        .mockReturnValueOnce(poll.promise)
        .mockReturnValueOnce(nextConversation.promise);
      vi.stubGlobal("fetch", fetchMock);
      vi.useFakeTimers();
      const view = render(
        <LiveInteractionIntelligence {...identity} interactionInProgress />,
      );
      await act(async () => {});
      expect(screen.getByText(initial.signals[0].statement)).toBeVisible();
      await advancePolling();

      view.rerender(
        <LiveInteractionIntelligence {...nextIdentity} interactionInProgress />,
      );
      expect(
        screen.queryByText(initial.signals[0].statement),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Checking Live Intelligence…")).toBeVisible();
      await act(async () => {
        poll.resolve(
          jsonResponse(
            processResponse({ safeMessage: "Stale conversation detail" }),
          ),
        );
      });
      expect(
        screen.queryByText("Stale conversation detail"),
      ).not.toBeInTheDocument();
      await act(async () => {
        nextConversation.resolve(
          jsonResponse(
            liveResponse({
              ...nextIdentity,
              safeMessage: "Verified current conversation",
              signals: [],
            }),
          ),
        );
      });
      expect(screen.getByText("Verified current conversation")).toBeVisible();
    },
  );
});
