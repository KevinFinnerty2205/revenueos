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
  NextBestActionContent,
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

function deferred<T>() {
  let resolvePromise: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });
  return {
    promise,
    resolve(value: T) {
      if (!resolvePromise)
        throw new Error("Deferred promise was not initialised.");
      resolvePromise(value);
    },
  };
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
const nextBestActionContent: NextBestActionContent = {
  overallRecommendation: "Identify the economic buyer.",
  priority: "high",
  confidence: 0.94,
  reasoning: [
    "Buying Signals: decision_maker_missing.",
    "Stakeholders: economic_buyer:not_identified.",
  ],
  recommendedActions: [
    {
      action: "Identify the economic buyer.",
      reason:
        "Buying Signals: decision_maker_missing. Stakeholders: economic_buyer:not_identified.",
      priority: "high",
      confidence: 0.94,
      dependsOn: ["buying_signals", "stakeholders"],
    },
  ],
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
      notGenerated: 10,
      total: 10,
      summary: "0 of 10 ready",
    },
    executiveSummary: capability("not_generated"),
    buyingSignals: capability("not_generated"),
    objectionsCompetitiveSignals: capability("not_generated"),
    stakeholderIntelligence: capability("not_generated"),
    decisions: capability("not_generated"),
    actionItems: capability("not_generated"),
    risksBlockers: capability("not_generated"),
    openQuestions: capability("not_generated"),
    nextBestAction: capability<NextBestActionContent>("unavailable", null, {
      generationAvailable: false,
    }),
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
      notGenerated: 2,
      total: 10,
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
      ready: 10,
      queued: 0,
      processing: 0,
      failed: 0,
      notGenerated: 0,
      total: 10,
      summary: "10 of 10 ready",
    },
    executiveSummary: capability("completed", summaryContent),
    buyingSignals: capability("completed", buyingSignalsContent),
    objectionsCompetitiveSignals: capability("completed", objectionsContent),
    stakeholderIntelligence: capability("completed", stakeholderContent),
    decisions: capability("completed", decisionsContent),
    actionItems: capability("completed", actionItemsContent),
    risksBlockers: capability("completed", risksContent),
    openQuestions: capability("completed", questionsContent),
    nextBestAction: capability("completed", nextBestActionContent),
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
    window.localStorage.clear();
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
    expect(screen.getByText("0 of 10 ready")).toBeVisible();
    const sectionNames = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(sectionNames).toEqual([
      "Executive Summary",
      "Buying Signals & Deal Momentum",
      "Objections & Competitive Signals",
      "Stakeholders",
      "Next Best Action",
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
    expect(screen.getByText("10 of 10 ready")).toBeVisible();
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

  it("renders grounded next actions without operational controls", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedWorkspace())),
    );

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    const section = await screen.findByRole("article", {
      name: "Next Best Action",
    });
    expect(within(section).getByText("Overall Recommendation")).toBeVisible();
    expect(
      within(section).getAllByText("Identify the economic buyer."),
    ).toHaveLength(2);
    expect(within(section).getByText("Reasoning")).toBeVisible();
    expect(within(section).getByText("Recommended Actions")).toBeVisible();
    expect(within(section).getAllByText("94%")).toHaveLength(2);
    expect(within(section).getByText("High priority")).toBeVisible();
    expect(
      within(section).getByText("Buying Signals, Stakeholders"),
    ).toBeVisible();
    expect(within(section).queryByRole("button")).not.toBeInTheDocument();
    expect(section).not.toHaveTextContent(/crm|automation|send email/i);
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
        notGenerated: 2,
        total: 10 as const,
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

  it("queues both validated composers only after the aggregate read marks prerequisites ready", async () => {
    const prerequisitesReady = {
      ...completedWorkspace(),
      overallState: "partially_generated" as const,
      generationAvailable: true,
      progress: {
        ready: 8,
        queued: 0,
        processing: 0,
        failed: 0,
        notGenerated: 2,
        total: 10 as const,
        summary: "8 of 10 ready",
      },
      nextBestAction: capability<NextBestActionContent>("not_generated", null, {
        generationAvailable: true,
      }),
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
        queued: 2,
        processing: 0,
        failed: 0,
        notGenerated: 0,
        total: 10 as const,
        summary: "2 sections queued",
      },
      nextBestAction: capability<NextBestActionContent>("queued", null, {
        generationAvailable: false,
      }),
      followUpEmail: {
        ...capability("queued", null, { generationAvailable: false }),
        tone: "professional" as const,
      },
      createdCapabilities: ["next_best_action", "follow_up_email"],
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

    expect(await screen.findByText("2 sections queued")).toBeVisible();
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
        ready: 9,
        queued: 0,
        processing: 0,
        failed: 1,
        notGenerated: 0,
        total: 10 as const,
        summary: "9 ready · 1 failed",
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

    expect(await screen.findByText("10 of 10 ready")).toBeVisible();
    await act(async () => {
      resolveFirst?.(jsonResponse(queuedWorkspace()));
      await Promise.resolve();
    });
    expect(screen.getByText("10 of 10 ready")).toBeVisible();
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

  it("keeps a completed manual follow-up visible read-only when the private editor is managed above", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(completedWorkspace())),
    );

    render(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-1"
        interactionId="interaction-1"
        privateFollowUpManagedExternally
      />,
    );

    const source = await screen.findByLabelText(
      "Generated transcript follow-up source",
    );
    expect(source).toHaveTextContent("Subject: Pilot next steps");
    expect(
      screen.getByText(/completed transcript result remains visible/i),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Editable follow-up draft"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy source" })).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Regenerate source" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Tone")).toHaveValue("professional");
  });

  it("blocks unowned browser drafts and owner-tags every newly saved draft", async () => {
    const draftKey = "revenueos:follow-up-draft:meeting-1";
    window.localStorage.setItem(
      draftKey,
      JSON.stringify({ draft: "Another user's private wording." }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).endsWith("/api/v1/me")
            ? jsonResponse({
                user: {
                  id: "user-1",
                  externalAuthId: "user_dev_001",
                  displayName: "Alex Morgan",
                  email: "alex@example.test",
                },
                organisation: {
                  id: "organisation-1",
                  name: "Example Revenue Team",
                  slug: "example-revenue-team",
                },
                role: "member",
                authMode: "mock",
                requestId: "request-1",
              })
            : jsonResponse(completedWorkspace()),
        ),
      ),
    );

    const first = render(
      <MeetingIntelligenceWorkspace meetingId="meeting-1" />,
    );

    const draft = await screen.findByLabelText("Editable follow-up draft");
    expect(draft).not.toHaveValue("Another user's private wording.");
    expect((draft as HTMLTextAreaElement).value).toContain(
      "Subject: Pilot next steps",
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Verify and load browser draft",
      }),
    );
    expect(await screen.findByText(/owner cannot be verified/i)).toBeVisible();
    first.unmount();

    render(<MeetingIntelligenceWorkspace meetingId="meeting-2" />);
    const newDraft = await screen.findByLabelText("Editable follow-up draft");
    fireEvent.change(newDraft, {
      target: { value: "My reviewed wording." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() =>
      expect(
        JSON.parse(
          String(
            window.localStorage.getItem("revenueos:follow-up-draft:meeting-2"),
          ),
        ),
      ).toEqual({
        draft: "My reviewed wording.",
        approved: false,
        ownerUserId: "user-1",
      }),
    );
  });

  it("keeps a reviewed browser-only draft reviewed when saving it unchanged", async () => {
    const draftKey = "revenueos:follow-up-draft:meeting-1";
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).endsWith("/api/v1/me")
            ? jsonResponse({
                user: {
                  id: "user-1",
                  externalAuthId: "user_dev_001",
                  displayName: "Alex Morgan",
                  email: "alex@example.test",
                },
                organisation: {
                  id: "organisation-1",
                  name: "Example Revenue Team",
                  slug: "example-revenue-team",
                },
                role: "member",
                authMode: "mock",
                requestId: "request-1",
              })
            : jsonResponse(completedWorkspace()),
        ),
      ),
    );

    render(<MeetingIntelligenceWorkspace meetingId="meeting-1" />);

    const draft = await screen.findByLabelText("Editable follow-up draft");
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    await waitFor(() =>
      expect(JSON.parse(String(window.localStorage.getItem(draftKey)))).toEqual(
        expect.objectContaining({ approved: true }),
      ),
    );
    expect(screen.getByText(/Review status: Reviewed/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Mark reviewed" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(JSON.parse(String(window.localStorage.getItem(draftKey)))).toEqual(
        expect.objectContaining({ approved: true }),
      ),
    );

    fireEvent.change(draft, { target: { value: "" } });
    expect(screen.getByText(/Review status: Needs review/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Mark reviewed" }),
    ).toBeDisabled();
  });

  it("preserves persisted review status on unchanged saves and failed reviews", async () => {
    const reviewedWorkspace = {
      exists: true,
      ownerUserId: "user-1",
      lockVersion: 2,
      liveNotes: "",
      enhancedNotes: "",
      followUpDraft: "Keep this reviewed private follow-up.",
      followUpReviewed: true,
      generationFingerprint: null,
      generationState: "not_started" as const,
      generationId: null,
      generationTranscriptVersion: null,
      generationPersonalNotesState: "not_included" as const,
      generationFailureCode: null,
      generationRetryAvailable: false,
      generationUpdateAvailable: false,
      generationCompletedAt: null,
      importedFromBrowserAt: null,
      updatedAt: "2026-10-31T00:00:00Z",
    };
    let putCount = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/personal-workspace")) {
        if (init?.method !== "PUT") {
          return Promise.resolve(jsonResponse(reviewedWorkspace));
        }
        putCount += 1;
        if (putCount === 1) {
          return Promise.resolve(
            jsonResponse({
              ...reviewedWorkspace,
              lockVersion: 3,
            }),
          );
        }
        return Promise.resolve(
          jsonResponse(
            {
              code: "conversation_workspace_unavailable",
              message: "Your private workspace could not be saved.",
            },
            503,
          ),
        );
      }
      return Promise.resolve(jsonResponse(completedWorkspace()));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-1"
        interactionId="interaction-1"
      />,
    );

    const draft = await screen.findByLabelText("Editable follow-up draft");
    await waitFor(() =>
      expect(draft).toHaveValue(reviewedWorkspace.followUpDraft),
    );
    expect(screen.getByText(/Review status: Reviewed/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Mark reviewed" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(putCount).toBe(1));
    const firstPut = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/personal-workspace") && init?.method === "PUT",
    );
    expect(JSON.parse(String(firstPut?.[1]?.body))).toMatchObject({
      followUpReviewed: true,
    });

    fireEvent.change(draft, {
      target: { value: "Edited private follow-up awaiting review." },
    });
    expect(screen.getByText(/Review status: Needs review/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));

    expect(
      await screen.findByText(/Your private workspace could not be saved/),
    ).toBeVisible();
    expect(screen.getByText(/Review status: Needs review/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeEnabled();
  });

  it("offers regenerated follow-up text without replacing the private draft", async () => {
    let intelligence = completedWorkspace();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/personal-workspace")) {
        return Promise.resolve(
          jsonResponse({
            exists: true,
            ownerUserId: "user-1",
            lockVersion: 2,
            enhancedNotes: null,
            followUpDraft: "Keep my reviewed private wording.",
            followUpReviewed: true,
            generationFingerprint: null,
            importedFromBrowserAt: null,
            updatedAt: "2026-10-31T00:00:00Z",
          }),
        );
      }
      if (init?.method === "POST" && url.endsWith("/follow-up-email")) {
        intelligence = {
          ...completedWorkspace(),
          followUpEmail: {
            ...completedWorkspace().followUpEmail,
            content: {
              ...emailContent,
              subject: "Regenerated next steps",
            },
          },
        };
        return Promise.resolve(jsonResponse({ accepted: true }, 202));
      }
      return Promise.resolve(jsonResponse(intelligence));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-1"
        interactionId="interaction-1"
      />,
    );

    const draft = await screen.findByLabelText("Editable follow-up draft");
    await waitFor(() =>
      expect(draft).toHaveValue("Keep my reviewed private wording."),
    );
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));

    const applyRegeneration = await screen.findByRole("button", {
      name: "Use regenerated draft",
    });
    expect(draft).toHaveValue("Keep my reviewed private wording.");
    fireEvent.click(applyRegeneration);
    expect((draft as HTMLTextAreaElement).value).toContain(
      "Regenerated next steps",
    );
  });

  it("removes regenerated private text before loading another meeting", async () => {
    const meetingBIntelligence = deferred<Response>();
    let meetingAIntelligence = {
      ...completedWorkspace(),
      followUpEmail: {
        ...completedWorkspace().followUpEmail,
        content: { ...emailContent, subject: "Initial A next steps" },
      },
    };
    const meetingBIntelligenceResponse = {
      ...completedWorkspace(),
      followUpEmail: {
        ...completedWorkspace().followUpEmail,
        content: { ...emailContent, subject: "Meeting B next steps" },
      },
    };
    const privateA = {
      exists: true,
      ownerUserId: "user-1",
      lockVersion: 2,
      liveNotes: "Private A rough notes",
      enhancedNotes: "Private A enhanced notes",
      followUpDraft: "Private A saved follow-up",
      followUpReviewed: true,
      generationFingerprint: null,
      generationState: "not_started" as const,
      generationId: null,
      generationTranscriptVersion: null,
      generationPersonalNotesState: "not_included" as const,
      generationFailureCode: null,
      generationRetryAvailable: false,
      generationUpdateAvailable: false,
      generationCompletedAt: null,
      importedFromBrowserAt: null,
      updatedAt: "2026-10-31T00:00:00Z",
    };
    const privateB = {
      ...privateA,
      lockVersion: 7,
      liveNotes: "Private B rough notes",
      enhancedNotes: "Private B enhanced notes",
      followUpDraft: "Private B saved follow-up",
      followUpReviewed: false,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/meetings/meeting-a/intelligence")) {
        if (init?.method === "POST" && url.endsWith("/follow-up-email")) {
          meetingAIntelligence = {
            ...meetingAIntelligence,
            followUpEmail: {
              ...meetingAIntelligence.followUpEmail,
              content: {
                ...emailContent,
                subject: "Regenerated private A next steps",
              },
            },
          };
          return Promise.resolve(jsonResponse({ accepted: true }, 202));
        }
        return Promise.resolve(jsonResponse(meetingAIntelligence));
      }
      if (url.includes("/meetings/meeting-b/intelligence")) {
        return meetingBIntelligence.promise;
      }
      if (url.includes("/interactions/interaction-a/personal-workspace")) {
        return Promise.resolve(jsonResponse(privateA));
      }
      if (url.includes("/interactions/interaction-b/personal-workspace")) {
        if (init?.method === "PUT") {
          const body = JSON.parse(String(init.body)) as {
            followUpDraft: string;
          };
          return Promise.resolve(
            jsonResponse({
              ...privateB,
              lockVersion: 8,
              followUpDraft: body.followUpDraft,
            }),
          );
        }
        return Promise.resolve(jsonResponse(privateB));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-a"
        interactionId="interaction-a"
      />,
    );

    const draftA = await screen.findByLabelText("Editable follow-up draft");
    await waitFor(() => expect(draftA).toHaveValue(privateA.followUpDraft));
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(
      await screen.findByRole("button", { name: "Use regenerated draft" }),
    ).toBeVisible();

    rerender(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-b"
        interactionId="interaction-b"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading Meeting Intelligence",
    );
    expect(
      screen.queryByRole("button", { name: "Use regenerated draft" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue(privateA.followUpDraft),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("interaction-b/personal-workspace"),
      ),
    ).toBe(false);

    await act(async () =>
      meetingBIntelligence.resolve(jsonResponse(meetingBIntelligenceResponse)),
    );
    const draftB = await screen.findByLabelText("Editable follow-up draft");
    await waitFor(() => expect(draftB).toHaveValue(privateB.followUpDraft));
    expect(draftB).not.toHaveValue(privateA.followUpDraft);
    expect(
      screen.queryByRole("button", { name: "Use regenerated draft" }),
    ).not.toBeInTheDocument();

    fireEvent.change(draftB, {
      target: { value: "Edited private B follow-up" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes(
              "/interactions/interaction-b/personal-workspace",
            ) && init?.method === "PUT",
        ),
      ).toBe(true),
    );
    const bPut = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).includes(
          "/interactions/interaction-b/personal-workspace",
        ) && init?.method === "PUT",
    );
    expect(JSON.parse(String(bPut?.[1]?.body))).toMatchObject({
      expectedLockVersion: privateB.lockVersion,
      followUpDraft: "Edited private B follow-up",
    });
    expect(String(bPut?.[1]?.body)).not.toContain("private A");
  });

  it("reviews a stale browser import without losing provenance or newer private fields", async () => {
    const initialWorkspace = {
      exists: true,
      ownerUserId: "user-1",
      lockVersion: 2,
      liveNotes: "Earlier rough notes",
      enhancedNotes: "Earlier enhanced notes",
      followUpDraft: "Earlier saved follow-up",
      followUpReviewed: false,
      generationFingerprint: null,
      generationState: "not_started" as const,
      generationId: null,
      generationTranscriptVersion: null,
      generationPersonalNotesState: "not_included" as const,
      generationFailureCode: null,
      generationRetryAvailable: false,
      generationUpdateAvailable: false,
      generationCompletedAt: null,
      importedFromBrowserAt: null,
      updatedAt: "2026-10-31T00:00:00Z",
    };
    const latestWorkspace = {
      ...initialWorkspace,
      lockVersion: 3,
      liveNotes: "Newer rough notes from the other session",
      enhancedNotes: "Newer enhanced notes from the other session",
      followUpDraft: "Latest saved follow-up from the other session",
      followUpReviewed: true,
      updatedAt: "2026-10-31T00:05:00Z",
    };
    const secondLatestWorkspace = {
      ...latestWorkspace,
      lockVersion: 4,
      liveNotes: "Newest rough notes after another remote save",
      enhancedNotes: "Newest enhanced notes after another remote save",
      updatedAt: "2026-10-31T00:06:00Z",
    };
    const localDraft = "My reviewed local follow-up wording.";
    const legacyKey = "revenueos:follow-up-draft:meeting-1";
    window.localStorage.setItem(
      legacyKey,
      JSON.stringify({
        draft: localDraft,
        approved: false,
        ownerUserId: "user-1",
      }),
    );
    let workspaceGetCount = 0;
    let workspacePutCount = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/personal-workspace") && method === "GET") {
        workspaceGetCount += 1;
        return Promise.resolve(
          jsonResponse(
            workspaceGetCount === 1
              ? initialWorkspace
              : workspaceGetCount === 2
                ? latestWorkspace
                : secondLatestWorkspace,
          ),
        );
      }
      if (url.endsWith("/personal-workspace") && method === "PUT") {
        workspacePutCount += 1;
        if (workspacePutCount <= 2) {
          return Promise.resolve(
            jsonResponse(
              {
                code: "conversation_workspace_conflict",
                message: "This private workspace changed in another session.",
              },
              409,
            ),
          );
        }
        return Promise.resolve(
          jsonResponse({
            ...secondLatestWorkspace,
            lockVersion: 5,
            followUpDraft: localDraft,
            followUpReviewed: false,
          }),
        );
      }
      return Promise.resolve(jsonResponse(completedWorkspace()));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MeetingIntelligenceWorkspace
        meetingId="meeting-1"
        interactionId="interaction-1"
      />,
    );

    const draft = await screen.findByLabelText("Editable follow-up draft");
    await waitFor(() => expect(draft).toHaveValue("Earlier saved follow-up"));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Import earlier browser draft",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Private notes changed in another session",
      }),
    ).toBeVisible();
    expect(draft).toBeEnabled();
    expect(draft).toHaveValue(localDraft);
    expect(
      await screen.findByLabelText("Latest saved follow-up draft"),
    ).toHaveValue(latestWorkspace.followUpDraft);
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();

    fireEvent.click(
      screen.getByRole("button", { name: "Use latest saved draft" }),
    );
    expect(draft).toHaveValue(latestWorkspace.followUpDraft);
    expect(window.localStorage.getItem(legacyKey)).not.toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Import earlier browser draft" }),
    );
    expect(
      await screen.findByLabelText("Latest saved follow-up draft"),
    ).toHaveValue(secondLatestWorkspace.followUpDraft);
    expect(draft).toHaveValue(localDraft);

    fireEvent.click(
      screen.getByRole("button", { name: "Save reviewed follow-up" }),
    );
    await waitFor(() => expect(workspacePutCount).toBe(3));

    const workspacePuts = fetchMock.mock.calls.filter(
      ([input, init]) =>
        String(input).endsWith("/personal-workspace") && init?.method === "PUT",
    );
    expect(JSON.parse(String(workspacePuts[2]?.[1]?.body))).toMatchObject({
      expectedLockVersion: 4,
      liveNotes: secondLatestWorkspace.liveNotes,
      enhancedNotes: secondLatestWorkspace.enhancedNotes,
      followUpDraft: localDraft,
      followUpReviewed: false,
      importFromBrowser: true,
    });
    expect(window.localStorage.getItem(legacyKey)).toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: "Private notes changed in another session",
      }),
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
