import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ActionItemsContent,
  DecisionsContent,
  ExecutiveSummaryContent,
  MeetingIntelligenceCapability,
  MeetingIntelligenceResponse,
  OpenQuestionsContent,
  RisksBlockersContent,
} from "@revenueos/shared";
import { MeetingIntelligenceWorkspace } from "@/components/meeting-intelligence-workspace";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function capability<T>(
  state: MeetingIntelligenceCapability<T>["state"],
  content: T | null = null,
  overrides: Partial<MeetingIntelligenceCapability<T>> = {},
): MeetingIntelligenceCapability<T> {
  return {
    state,
    generationAvailable:
      state === "not_generated" || state === "failed" || state === "cancelled",
    message: state === "failed" ? "This section could not be completed." : null,
    generatedAt: state === "completed" ? "2026-07-20T01:00:00Z" : null,
    emptyResult: false,
    content,
    ...overrides,
  };
}

const summaryContent = {
  executiveSummary: "The customer confirmed the pilot scope and next steps.",
  meetingType: "sales_discovery" as const,
  sentiment: "positive" as const,
  confidence: 0.91,
};
const decisionsContent = {
  decisions: [
    {
      decision: "Proceed with the pilot.",
      owner: "Customer team",
      status: "confirmed" as const,
      confidence: 0.9,
      evidence: "The customer approved the pilot.",
    },
  ],
};
const actionItemsContent = {
  actionItems: [
    {
      task: "Send the implementation plan.",
      owner: "Alex",
      dueDate: "2026-07-30",
      priority: "high" as const,
      status: "open" as const,
      confidence: 0.89,
      evidence: "Alex committed to sending the plan.",
    },
  ],
};
const risksContent = {
  risks: [
    {
      risk: "Security review may delay the pilot.",
      category: "security" as const,
      severity: "high" as const,
      owner: "Customer security",
      confidence: 0.84,
      evidence: "The reviewer has not been assigned.",
    },
  ],
};
const questionsContent = {
  openQuestions: [
    {
      question: "Who will approve production access?",
      owner: null,
      importance: "high" as const,
      confidence: 0.88,
      evidence: "No approver was named.",
    },
  ],
};
const emailContent = {
  subject: "Pilot next steps",
  greeting: "Hello,",
  summary: summaryContent.executiveSummary,
  decisions: ["Proceed with the pilot. (Owner: Customer team)"],
  actionItems: ["Send the implementation plan. (Owner: Alex; Due: 2026-07-30)"],
  openQuestions: ["Who will approve production access?"],
  closing: "Kind regards,",
  tone: "professional" as const,
  confidence: 0.92,
};

function notStartedWorkspace(): MeetingIntelligenceResponse {
  return {
    overallState: "not_started",
    generationAvailable: true,
    retryAvailable: false,
    lastUpdatedAt: null,
    progress: {
      ready: 0,
      queued: 0,
      processing: 0,
      failed: 0,
      notGenerated: 6,
      total: 6,
      summary: "0 of 6 ready",
    },
    executiveSummary: capability("not_generated"),
    decisions: capability("not_generated"),
    actionItems: capability("not_generated"),
    risksBlockers: capability("not_generated"),
    openQuestions: capability("not_generated"),
    followUpEmail: {
      ...capability("unavailable", null, { generationAvailable: false }),
      tone: null,
    },
  };
}

function queuedWorkspace(): MeetingIntelligenceResponse {
  return {
    ...notStartedWorkspace(),
    overallState: "queued",
    generationAvailable: false,
    lastUpdatedAt: "2026-07-20T00:00:00Z",
    progress: {
      ready: 0,
      queued: 5,
      processing: 0,
      failed: 0,
      notGenerated: 1,
      total: 6,
      summary: "5 sections queued",
    },
    executiveSummary: capability<ExecutiveSummaryContent>("queued", null, {
      generationAvailable: false,
    }),
    decisions: capability<DecisionsContent>("queued", null, {
      generationAvailable: false,
    }),
    actionItems: capability<ActionItemsContent>("queued", null, {
      generationAvailable: false,
    }),
    risksBlockers: capability<RisksBlockersContent>("queued", null, {
      generationAvailable: false,
    }),
    openQuestions: capability<OpenQuestionsContent>("queued", null, {
      generationAvailable: false,
    }),
  };
}

function completedWorkspace(): MeetingIntelligenceResponse {
  return {
    overallState: "completed",
    generationAvailable: false,
    retryAvailable: false,
    lastUpdatedAt: "2026-07-20T01:00:00Z",
    progress: {
      ready: 6,
      queued: 0,
      processing: 0,
      failed: 0,
      notGenerated: 0,
      total: 6,
      summary: "6 of 6 ready",
    },
    executiveSummary: capability("completed", summaryContent),
    decisions: capability("completed", decisionsContent),
    actionItems: capability("completed", actionItemsContent),
    risksBlockers: capability("completed", risksContent),
    openQuestions: capability("completed", questionsContent),
    followUpEmail: {
      ...capability("completed", emailContent, { generationAvailable: true }),
      tone: "professional",
    },
  };
}

describe("MeetingIntelligenceWorkspace", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("renders one ordered workspace and prevents duplicate generation submissions", async () => {
    const generation = {
      ...queuedWorkspace(),
      createdCapabilities: [
        "executive_summary",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
      ],
      reusedCapabilities: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(notStartedWorkspace()))
      .mockResolvedValue(jsonResponse(generation, 202));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    expect(
      await screen.findByRole("heading", { name: "Meeting Intelligence" }),
    ).toBeVisible();
    expect(screen.getByText("0 of 6 ready")).toBeVisible();
    const sectionNames = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(sectionNames).toEqual([
      "Executive Summary",
      "Key Decisions",
      "Action Items",
      "Risks & Blockers",
      "Open Questions",
      "Follow-up Email",
    ]);

    const generate = screen.getByRole("button", {
      name: "Generate Meeting Intelligence",
    });
    fireEvent.click(generate);
    fireEvent.click(generate);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
      ).toHaveLength(1),
    );
  });

  it("uses one non-overlapping polling chain and stops when all sections are ready", async () => {
    vi.useFakeTimers();
    const processing = {
      ...queuedWorkspace(),
      overallState: "processing" as const,
      progress: {
        ...queuedWorkspace().progress,
        queued: 4,
        processing: 1,
        summary: "Generating 5 sections",
      },
      executiveSummary: capability("processing", null, {
        generationAvailable: false,
      }),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(queuedWorkspace()))
      .mockResolvedValueOnce(jsonResponse(processing))
      .mockResolvedValueOnce(jsonResponse(completedWorkspace()));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("5 sections queued")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(screen.getByText("Generating 5 sections")).toBeVisible();
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "previousOverallState=queued",
    );
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "pollingEvent=started",
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(screen.getByText("6 of 6 ready")).toBeVisible();
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain(
      "previousOverallState=processing",
    );
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain(
      "pollingEvent=continued",
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("queues Follow-up Email only after the aggregate read marks prerequisites ready", async () => {
    const prerequisitesReady = {
      ...completedWorkspace(),
      overallState: "partially_generated" as const,
      generationAvailable: true,
      progress: {
        ready: 5,
        queued: 0,
        processing: 0,
        failed: 0,
        notGenerated: 1,
        total: 6 as const,
        summary: "5 of 6 ready",
      },
      followUpEmail: {
        ...capability("not_generated", null, { generationAvailable: true }),
        tone: null,
      },
    };
    const emailQueued = {
      ...prerequisitesReady,
      overallState: "queued" as const,
      generationAvailable: false,
      progress: {
        ready: 5,
        queued: 1,
        processing: 0,
        failed: 0,
        notGenerated: 0,
        total: 6 as const,
        summary: "1 section queued",
      },
      followUpEmail: {
        ...capability("queued", null, { generationAvailable: false }),
        tone: "professional" as const,
      },
      createdCapabilities: ["follow_up_email"],
      reusedCapabilities: [
        "executive_summary",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
      ],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(prerequisitesReady))
      .mockResolvedValueOnce(jsonResponse(emailQueued, 202));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    expect(await screen.findByText("1 section queued")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "/intelligence/generate",
    );
  });

  it("keeps completed content visible during partial failure and offers a safe retry", async () => {
    const partialFailure = {
      ...completedWorkspace(),
      overallState: "partially_failed" as const,
      generationAvailable: true,
      retryAvailable: true,
      progress: {
        ready: 5,
        queued: 0,
        processing: 0,
        failed: 1,
        notGenerated: 0,
        total: 6 as const,
        summary: "5 ready · 1 failed",
      },
      risksBlockers: capability("failed", null, {
        generationAvailable: true,
        message: "Risks & Blockers could not be completed.",
      }),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(partialFailure))
      .mockResolvedValueOnce(
        jsonResponse({
          ...queuedWorkspace(),
          createdCapabilities: ["risks_blockers"],
          reusedCapabilities: [],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    expect(await screen.findByText("Proceed with the pilot.")).toBeVisible();
    expect(
      screen.getByText("Risks & Blockers could not be completed."),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry Risks & Blockers" }),
    );
    await waitFor(() => {
      expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
      expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
        "/intelligence/risks-blockers",
      );
    });
  });

  it("renders unavailable and valid empty-result states distinctly", async () => {
    const unavailable = {
      ...notStartedWorkspace(),
      overallState: "unavailable" as const,
      generationAvailable: false,
      executiveSummary: capability("unavailable", null, {
        generationAvailable: false,
        message: "Add a usable transcript before generating Executive Summary.",
      }),
    };
    const emptyResults = {
      ...completedWorkspace(),
      overallState: "completed_with_empty_results" as const,
      decisions: capability(
        "completed",
        { decisions: [] },
        { emptyResult: true },
      ),
      risksBlockers: capability(
        "completed",
        { risks: [] },
        { emptyResult: true },
      ),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(unavailable))
      .mockResolvedValueOnce(jsonResponse(emptyResults));
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-1" />,
    );
    expect((await screen.findAllByText("Unavailable"))[0]).toBeVisible();
    expect(
      screen.getByText(
        "Add a usable transcript before generating Executive Summary.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Generate Meeting Intelligence" }),
    ).toBeDisabled();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-2" />);
    expect(
      await screen.findByText("Ready — some sections are empty"),
    ).toBeVisible();
    expect(
      screen.getByText("No decisions were identified in this meeting."),
    ).toBeVisible();
    expect(
      screen.getByText("No risks or blockers were identified in this meeting."),
    ).toBeVisible();
  });

  it("prevents an aborted stale meeting response from replacing newer state", async () => {
    let resolveFirst: ((value: Response) => void) | undefined;
    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce(jsonResponse(completedWorkspace()));
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-1" />,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-2" />);

    expect(await screen.findByText("6 of 6 ready")).toBeVisible();
    await act(async () => {
      resolveFirst?.(jsonResponse(queuedWorkspace()));
      await Promise.resolve();
    });
    expect(screen.getByText("6 of 6 ready")).toBeVisible();
    expect(screen.queryByText("5 sections queued")).not.toBeInTheDocument();
  });

  it("copies the rendered Follow-up Email and never exposes a Send action", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedWorkspace())),
    );

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Copy" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(String(writeText.mock.calls[0]?.[0])).toContain(
      "Subject: Pilot next steps",
    );
    expect(
      screen.queryByRole("button", { name: /send/i }),
    ).not.toBeInTheDocument();
  });

  it("aborts an in-flight aggregate request when unmounted", () => {
    let capturedSignal: AbortSignal | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        capturedSignal = init?.signal ?? null;
        return new Promise<Response>(() => undefined);
      }),
    );

    const { unmount } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-1" />,
    );
    unmount();

    expect((capturedSignal as unknown as AbortSignal).aborted).toBe(true);
  });
});
