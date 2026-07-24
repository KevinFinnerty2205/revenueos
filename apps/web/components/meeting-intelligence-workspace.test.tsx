import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ActionItemsContent,
  BuyingSignalsContent,
  DecisionsContent,
  ExecutiveSummaryContent,
  MeetingIntelligenceCapability,
  MeetingIntelligenceResponse,
  ObjectionsCompetitiveSignalsContent,
  OpenQuestionsContent,
  RisksBlockersContent,
  StakeholderIntelligenceContent,
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
const buyingSignalsContent: BuyingSignalsContent = {
  signals: [
    {
      signalType: "budget_confirmed",
      polarity: "positive",
      strength: "strong",
      confidence: 0.94,
      evidence: "The customer confirmed that budget is approved.",
    },
    {
      signalType: "procurement_unclear",
      polarity: "neutral",
      strength: "weak",
      confidence: 0.72,
      evidence: "The procurement path was discussed but remains unclear.",
    },
    {
      signalType: "security_or_legal_blocker",
      polarity: "negative",
      strength: "moderate",
      confidence: 0.86,
      evidence: "Outstanding legal approval blocks contract signature.",
    },
  ],
  overallMomentum: "neutral",
  momentumSummary:
    "The current meeting contains mixed positive and negative signals, so momentum is neutral.",
  confidence: 0.88,
};
const objectionsContent: ObjectionsCompetitiveSignalsContent = {
  objections: [
    {
      objection:
        "The customer believes implementation needs too many resources.",
      category: "implementation",
      status: "unresolved",
      strength: "strong",
      owner: "Customer IT",
      confidence: 0.93,
      evidence: "Customer IT said it could not support the proposed rollout.",
    },
  ],
  competitors: [
    {
      name: "Competitor X",
      position: "stronger",
      confidence: 0.88,
      evidence: "The competitor already integrates with the customer's stack.",
    },
  ],
  overallObjectionPressure: "high",
  summary:
    "Implementation capacity and Competitor X create meaningful pressure.",
};
const stakeholderContent: StakeholderIntelligenceContent = {
  stakeholders: [
    {
      name: "Jane Smith",
      organisation: "Customer",
      role: "champion",
      influence: "high",
      stance: "supportive",
      engagement: "active",
      confidence: 0.93,
      evidence:
        "Jane advocated for the solution and committed to presenting it internally.",
    },
    {
      name: "Customer procurement representative",
      organisation: null,
      role: "procurement",
      influence: "medium",
      stance: "neutral",
      engagement: "absent_but_referenced",
      confidence: 0.82,
      evidence:
        "The procurement representative was referenced as part of the approval process.",
    },
  ],
  roleCoverage: {
    economicBuyer: "not_identified",
    decisionMaker: "unclear",
    champion: "identified",
    technicalBuyer: "not_discussed",
    procurement: "identified",
    legalSecurity: "not_discussed",
  },
  stakeholderSummary:
    "A likely champion and procurement involvement are present, but the economic buyer remains unidentified.",
  confidence: 0.89,
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
      notGenerated: 9,
      total: 9,
      summary: "0 of 9 ready",
    },
    executiveSummary: capability("not_generated"),
    buyingSignals: capability("not_generated"),
    objectionsCompetitiveSignals: capability("not_generated"),
    stakeholderIntelligence: capability("not_generated"),
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
      queued: 8,
      processing: 0,
      failed: 0,
      notGenerated: 1,
      total: 9,
      summary: "8 sections queued",
    },
    executiveSummary: capability<ExecutiveSummaryContent>("queued", null, {
      generationAvailable: false,
    }),
    buyingSignals: capability<BuyingSignalsContent>("queued", null, {
      generationAvailable: false,
    }),
    objectionsCompetitiveSignals:
      capability<ObjectionsCompetitiveSignalsContent>("queued", null, {
        generationAvailable: false,
      }),
    stakeholderIntelligence: capability<StakeholderIntelligenceContent>(
      "queued",
      null,
      { generationAvailable: false },
    ),
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
      ready: 9,
      queued: 0,
      processing: 0,
      failed: 0,
      notGenerated: 0,
      total: 9,
      summary: "9 of 9 ready",
    },
    executiveSummary: capability("completed", summaryContent),
    buyingSignals: capability("completed", buyingSignalsContent),
    objectionsCompetitiveSignals: capability("completed", objectionsContent),
    stakeholderIntelligence: capability("completed", stakeholderContent),
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
        "buying_signals",
        "objections_competitive_signals",
        "stakeholder_intelligence",
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
    expect(screen.getByText("0 of 9 ready")).toBeVisible();
    const sectionNames = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(sectionNames).toEqual([
      "Executive Summary",
      "Buying Signals & Deal Momentum",
      "Objections & Competitive Signals",
      "Stakeholders",
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
        queued: 7,
        processing: 1,
        summary: "Generating 8 sections",
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
    expect(screen.getByText("8 sections queued")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(screen.getByText("Generating 8 sections")).toBeVisible();
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "previousOverallState=queued",
    );
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      "pollingEvent=started",
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(screen.getByText("9 of 9 ready")).toBeVisible();
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

  it("renders grounded deal momentum and supports capability-level generation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(notStartedWorkspace()))
      .mockResolvedValueOnce(jsonResponse({ status: "queued" }, 202));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Buying signals have not been analysed for this meeting.",
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Generate Buying Signals & Deal Momentum",
      }),
    );
    await waitFor(() => {
      expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
      expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
        "/intelligence/buying-signals",
      );
    });
  });

  it("shows momentum, positive neutral and negative signals without predictive scoring", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedWorkspace())),
    );

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    const section = await screen.findByRole("article", {
      name: "Buying Signals & Deal Momentum",
    });
    expect(within(section).getByText("Current meeting momentum")).toBeVisible();
    expect(within(section).getByText("Budget Confirmed")).toBeVisible();
    expect(within(section).getByText("Positive signal")).toBeVisible();
    expect(within(section).getByText("Neutral signal")).toBeVisible();
    expect(within(section).getByText("Negative signal")).toBeVisible();
    expect(within(section).getByText("Strong")).toBeVisible();
    expect(within(section).getByText("94%")).toBeVisible();
    expect(
      within(section).getByText(
        "The customer confirmed that budget is approved.",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/win probability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/deal score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/deal will close/i)).not.toBeInTheDocument();
  });

  it("renders objection and competitor evidence without predictive scoring", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedWorkspace())),
    );

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    const section = await screen.findByRole("article", {
      name: "Objections & Competitive Signals",
    });
    expect(section).toHaveTextContent("Current meeting objection pressure");
    expect(section).toHaveTextContent("High");
    expect(section).toHaveTextContent(
      "The customer believes implementation needs too many resources.",
    );
    expect(section).toHaveTextContent("Implementation");
    expect(section).toHaveTextContent("Unresolved");
    expect(section).toHaveTextContent("Strong");
    expect(section).toHaveTextContent("Customer IT");
    expect(section).toHaveTextContent("93%");
    expect(section).toHaveTextContent("Competitor X");
    expect(section).toHaveTextContent("Stronger");
    expect(section).toHaveTextContent("88%");
    expect(section).not.toHaveTextContent(/close probability/i);
    expect(section).not.toHaveTextContent(/deal score/i);
    expect(section).not.toHaveTextContent(/win probability/i);
  });

  it("requests Objections & Competitive Signals through the unified workspace", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(notStartedWorkspace()))
      .mockResolvedValueOnce(jsonResponse({ status: "queued" }, 202));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "Objections and competitive signals have not been analysed for this meeting.",
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Generate Objections & Competitive Signals",
      }),
    );
    await waitFor(() => {
      expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
      expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
        "/intelligence/objections-competitive-signals",
      );
    });
  });

  it("renders cautious stakeholder evidence and requests it through the unified workspace", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(completedWorkspace()))
      .mockResolvedValueOnce(jsonResponse(notStartedWorkspace()))
      .mockResolvedValueOnce(jsonResponse({ status: "queued" }, 202));
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-completed" />,
    );
    const section = await screen.findByRole("article", {
      name: "Stakeholders",
    });
    expect(section).toHaveTextContent("Stakeholder summary");
    expect(section).toHaveTextContent("Current meeting evidence");
    expect(section).toHaveTextContent("Likely Champion");
    expect(section).toHaveTextContent("Jane Smith");
    expect(section).toHaveTextContent("Customer");
    expect(section).toHaveTextContent("High");
    expect(section).toHaveTextContent("Supportive");
    expect(section).toHaveTextContent("Active");
    expect(section).toHaveTextContent("93%");
    expect(section).toHaveTextContent("Role not discussed");
    expect(section).not.toHaveTextContent(/deal score/i);
    expect(section).not.toHaveTextContent(/relationship graph/i);
    expect(section).not.toHaveTextContent(/crm/i);

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-not-started" />);
    expect(
      await screen.findByText(
        "Stakeholder roles have not been analysed for this meeting.",
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Generate Stakeholders" }),
    );
    await waitFor(() => {
      expect(fetchMock.mock.calls[2]?.[1]?.method).toBe("POST");
      expect(String(fetchMock.mock.calls[2]?.[0])).toContain(
        "/intelligence/stakeholders",
      );
    });
  });

  it("renders every stakeholder generation state with a safe message", async () => {
    const stakeholderState = (
      state: "queued" | "processing" | "failed" | "cancelled" | "unavailable",
      message: string | null,
    ): MeetingIntelligenceResponse => ({
      ...notStartedWorkspace(),
      overallState:
        state === "processing"
          ? "processing"
          : state === "queued"
            ? "queued"
            : state === "unavailable"
              ? "unavailable"
              : "partially_failed",
      generationAvailable: false,
      retryAvailable: state === "failed" || state === "cancelled",
      stakeholderIntelligence: capability<StakeholderIntelligenceContent>(
        state,
        null,
        {
          generationAvailable: state === "failed" || state === "cancelled",
          message,
        },
      ),
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(stakeholderState("queued", null)))
      .mockResolvedValueOnce(jsonResponse(stakeholderState("processing", null)))
      .mockResolvedValueOnce(
        jsonResponse(
          stakeholderState(
            "failed",
            "Stakeholder Intelligence could not be completed.",
          ),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          stakeholderState(
            "cancelled",
            "Stakeholder Intelligence generation was cancelled.",
          ),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          stakeholderState(
            "unavailable",
            "Add a usable transcript before generating Stakeholder Intelligence.",
          ),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-queued" />,
    );
    let section = (
      await screen.findByRole("heading", { name: "Stakeholders" })
    ).closest("article");
    expect(section).not.toBeNull();
    expect(within(section!).getByText("This section is queued.")).toBeVisible();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-processing" />);
    section = (
      await screen.findByText("This section is being generated…")
    ).closest("article");
    expect(section).not.toBeNull();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-failed" />);
    expect(
      await screen.findByText(
        "Stakeholder Intelligence could not be completed.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Retry Stakeholders" }),
    ).toBeVisible();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-cancelled" />);
    expect(
      await screen.findByText(
        "Stakeholder Intelligence generation was cancelled.",
      ),
    ).toBeVisible();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-unavailable" />);
    expect(
      await screen.findByText(
        "Add a usable transcript before generating Stakeholder Intelligence.",
      ),
    ).toBeVisible();
  });

  it("renders every active and terminal objection capability state accessibly", async () => {
    const unavailable = {
      ...notStartedWorkspace(),
      overallState: "unavailable" as const,
      generationAvailable: false,
      objectionsCompetitiveSignals:
        capability<ObjectionsCompetitiveSignalsContent>("unavailable", null, {
          generationAvailable: false,
          message:
            "Add a usable transcript before generating objections and competitive signals.",
        }),
    };
    const processing = {
      ...queuedWorkspace(),
      overallState: "processing" as const,
      progress: {
        ready: 0,
        queued: 7,
        processing: 1,
        failed: 0,
        notGenerated: 1,
        total: 9 as const,
        summary: "Generating 1 section",
      },
      objectionsCompetitiveSignals:
        capability<ObjectionsCompetitiveSignalsContent>("processing", null, {
          generationAvailable: false,
        }),
    };
    const failed = {
      ...completedWorkspace(),
      overallState: "partially_failed" as const,
      retryAvailable: true,
      objectionsCompetitiveSignals:
        capability<ObjectionsCompetitiveSignalsContent>("failed", null, {
          message: "Objections & Competitive Signals could not be completed.",
        }),
    };
    const cancelled = {
      ...failed,
      objectionsCompetitiveSignals:
        capability<ObjectionsCompetitiveSignalsContent>("cancelled", null, {
          message: "Objections & Competitive Signals was cancelled.",
        }),
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(unavailable))
        .mockResolvedValueOnce(jsonResponse(queuedWorkspace()))
        .mockResolvedValueOnce(jsonResponse(processing))
        .mockResolvedValueOnce(jsonResponse(failed))
        .mockResolvedValueOnce(jsonResponse(cancelled)),
    );

    const { rerender } = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-unavailable" />,
    );
    expect(
      await screen.findByText(
        "Add a usable transcript before generating objections and competitive signals.",
      ),
    ).toBeVisible();

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-queued" />);
    expect(
      await screen.findByRole("article", {
        name: "Objections & Competitive Signals",
      }),
    ).toHaveTextContent("This section is queued.");

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-processing" />);
    await waitFor(() => {
      expect(
        screen.getByRole("article", {
          name: "Objections & Competitive Signals",
        }),
      ).toHaveTextContent("This section is being generated…");
    });

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-failed" />);
    expect(
      await screen.findByText(
        "Objections & Competitive Signals could not be completed.",
      ),
    ).toHaveAttribute("role", "alert");

    rerender(<MeetingIntelligenceWorkspace meetingId="meeting-cancelled" />);
    expect(
      await screen.findByText(
        "Objections & Competitive Signals was cancelled.",
      ),
    ).toHaveAttribute("role", "alert");
  });

  it("queues Follow-up Email only after the aggregate read marks prerequisites ready", async () => {
    const prerequisitesReady = {
      ...completedWorkspace(),
      overallState: "partially_generated" as const,
      generationAvailable: true,
      progress: {
        ready: 8,
        queued: 0,
        processing: 0,
        failed: 0,
        notGenerated: 1,
        total: 9 as const,
        summary: "8 of 9 ready",
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
        ready: 8,
        queued: 1,
        processing: 0,
        failed: 0,
        notGenerated: 0,
        total: 9 as const,
        summary: "1 section queued",
      },
      followUpEmail: {
        ...capability("queued", null, { generationAvailable: false }),
        tone: "professional" as const,
      },
      createdCapabilities: ["follow_up_email"],
      reusedCapabilities: [
        "executive_summary",
        "buying_signals",
        "objections_competitive_signals",
        "stakeholder_intelligence",
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
        ready: 8,
        queued: 0,
        processing: 0,
        failed: 1,
        notGenerated: 0,
        total: 9 as const,
        summary: "8 ready · 1 failed",
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
      buyingSignals: capability(
        "completed",
        {
          signals: [],
          overallMomentum: "insufficient_evidence" as const,
          momentumSummary:
            "There was not enough transcript evidence to assess deal momentum reliably.",
          confidence: 0.3,
        },
        { emptyResult: true },
      ),
      objectionsCompetitiveSignals: capability(
        "completed",
        {
          objections: [],
          competitors: [],
          overallObjectionPressure: "none" as const,
          summary:
            "No objections or competitive signals were identified in this meeting.",
        },
        { emptyResult: true },
      ),
      stakeholderIntelligence: capability(
        "completed",
        {
          stakeholders: [],
          roleCoverage: {
            economicBuyer: "not_discussed" as const,
            decisionMaker: "not_discussed" as const,
            champion: "not_discussed" as const,
            technicalBuyer: "not_discussed" as const,
            procurement: "not_discussed" as const,
            legalSecurity: "not_discussed" as const,
          },
          stakeholderSummary:
            "There was not enough evidence to identify stakeholder roles reliably.",
          confidence: 0.3,
        },
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
    expect(
      screen.getByText(
        "There was not enough transcript evidence to assess deal momentum reliably.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No objections or competitive signals were identified in this meeting.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "There was not enough evidence to identify stakeholder roles reliably.",
      ),
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

    expect(await screen.findByText("9 of 9 ready")).toBeVisible();
    await act(async () => {
      resolveFirst?.(jsonResponse(queuedWorkspace()));
      await Promise.resolve();
    });
    expect(screen.getByText("9 of 9 ready")).toBeVisible();
    expect(screen.queryByText("8 sections queued")).not.toBeInTheDocument();
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
