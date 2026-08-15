import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  Meeting,
  MeetingIntelligenceCapability,
  MeetingIntelligenceResponse,
  OpportunityWorkspaceResponse,
} from "@revenueos/shared";
import { OpportunityWorkspace } from "@/components/opportunity-workspace";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function capability<T>(content: T): MeetingIntelligenceCapability<T> {
  return {
    state: "completed",
    generationAvailable: false,
    message: null,
    generatedAt: "2026-07-24T01:00:00Z",
    emptyResult: false,
    content,
  };
}

function completedIntelligence(): MeetingIntelligenceResponse {
  return {
    overallState: "completed",
    generationAvailable: false,
    retryAvailable: false,
    lastUpdatedAt: "2026-07-24T01:00:00Z",
    progress: {
      ready: 10,
      queued: 0,
      processing: 0,
      failed: 0,
      notGenerated: 0,
      total: 10,
      summary: "10 of 10 ready",
    },
    executiveSummary: capability({
      executiveSummary: "The customer confirmed the commercial path.",
      meetingType: "sales_discovery",
      sentiment: "positive",
      confidence: 0.9,
    }),
    buyingSignals: capability({
      signals: [
        {
          signalType: "budget_confirmed",
          polarity: "positive",
          strength: "strong",
          confidence: 0.92,
          evidence: "The customer confirmed budget.",
        },
      ],
      overallMomentum: "positive",
      momentumSummary:
        "The latest meeting contains positive commercial intent.",
      confidence: 0.9,
    }),
    objectionsCompetitiveSignals: capability({
      objections: [
        {
          objection: "Security timing remains uncertain.",
          category: "security",
          status: "unresolved",
          strength: "moderate",
          owner: null,
          confidence: 0.8,
          evidence: "A security date was not confirmed.",
        },
      ],
      competitors: [],
      overallObjectionPressure: "medium",
      summary: "Security timing creates moderate pressure.",
    }),
    stakeholderIntelligence: capability({
      stakeholders: [
        {
          name: "Jordan Lee",
          organisation: "Acme Australia",
          role: "champion",
          influence: "high",
          stance: "supportive",
          engagement: "active",
          confidence: 0.9,
          evidence: "Jordan advocated for the proposal.",
        },
      ],
      roleCoverage: {
        economicBuyer: "not_identified",
        decisionMaker: "unclear",
        champion: "identified",
        technicalBuyer: "not_discussed",
        procurement: "identified",
        legalSecurity: "unclear",
      },
      stakeholderSummary:
        "A champion is active; the economic buyer is not identified.",
      confidence: 0.88,
    }),
    nextBestAction: capability({
      overallRecommendation:
        "Confirm the economic buyer and procurement owner.",
      priority: "high",
      confidence: 0.91,
      reasoning: ["The economic buyer is not identified."],
      recommendedActions: [
        {
          action: "Confirm the economic buyer.",
          reason: "Commercial approval ownership remains unclear.",
          priority: "high",
          confidence: 0.91,
          dependsOn: ["stakeholders"],
        },
      ],
    }),
    decisions: capability({
      decisions: [
        {
          decision: "Proceed to procurement review.",
          owner: "Customer team",
          status: "confirmed",
          confidence: 0.9,
          evidence: "The customer agreed to procurement review.",
        },
      ],
    }),
    actionItems: capability({
      actionItems: [
        {
          task: "Send the security pack.",
          owner: "Alex",
          dueDate: "2026-08-10",
          priority: "high",
          status: "open",
          confidence: 0.9,
          evidence: "Alex committed to sending it.",
        },
      ],
    }),
    risksBlockers: capability({
      risks: [
        {
          risk: "Security review may delay signature.",
          category: "security",
          severity: "high",
          owner: null,
          confidence: 0.86,
          evidence: "No review date was confirmed.",
        },
      ],
    }),
    openQuestions: capability({
      openQuestions: [
        {
          question: "Who is the final approver?",
          owner: null,
          importance: "high",
          confidence: 0.87,
          evidence: "The final approver was not named.",
        },
      ],
    }),
    followUpEmail: {
      ...capability({
        subject: "Procurement next steps",
        greeting: "Hello Jordan,",
        summary: "Thank you for confirming the procurement review.",
        decisions: ["Proceed to procurement review."],
        actionItems: ["Send the security pack."],
        openQuestions: ["Who is the final approver?"],
        closing: "Kind regards,",
        tone: "professional",
        confidence: 0.9,
      }),
      tone: "professional",
    },
  };
}

const meeting: Meeting = {
  id: "meeting-1",
  interactionId: "interaction-1",
  organisationId: "organisation-1",
  title: "Expansion review",
  description: null,
  meetingDate: "2026-08-01T00:00:00Z",
  meetingType: "remote",
  status: "completed",
  companyId: "company-1",
  opportunityId: "opportunity-1",
  ownerUserId: "user-1",
  createdBy: "user-1",
  updatedBy: "user-1",
  createdAt: "2026-07-20T00:00:00Z",
  updatedAt: "2026-07-24T00:00:00Z",
};

function workspace(
  overrides: Partial<OpportunityWorkspaceResponse> = {},
): OpportunityWorkspaceResponse {
  const insight = {
    id: "insight-1",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    reasoningVersion: 1,
    createdAt: "2026-08-01T02:00:00Z",
    content: {
      scope: "opportunity" as const,
      fromSnapshotId: "snapshot-1",
      toSnapshotId: "snapshot-2",
      fromMeetingId: "meeting-0",
      toMeetingId: "meeting-1",
      fromMeetingDate: "2026-07-20",
      toMeetingDate: "2026-08-01",
      changes: [
        {
          changeType: "champion_strengthened" as const,
          direction: "improved" as const,
          importance: "high" as const,
          title: "Champion evidence strengthened",
          description: "The matched champion's explicit influence changed.",
          confidence: 0.9,
          sourceCapabilities: ["stakeholder_intelligence" as const],
          evidence: [
            {
              snapshotId: "snapshot-2",
              artefactId: "stakeholders-2",
              artefactType: "stakeholder_intelligence" as const,
              entityKey: "stakeholder:abc",
              field: "influence",
              value: "high",
            },
          ],
        },
      ],
      summary:
        "The most important supported change was: Champion evidence strengthened. 1 material supported change was identified.",
      confidence: 0.9,
    },
  };
  return {
    opportunity: {
      id: "opportunity-1",
      companyId: "company-1",
      companyName: "Acme Australia",
      name: "Platform expansion",
      stage: "proposal",
      status: "open",
      estimatedValue: "125000.50",
      currency: "AUD",
      expectedCloseDate: "2026-09-30",
      ownerUserId: "user-1",
      ownerName: "Alex Morgan",
      description: "Expand the platform across the revenue team.",
      createdAt: "2026-07-20T00:00:00Z",
      updatedAt: "2026-07-24T00:00:00Z",
    },
    reportedIntelligence: null,
    visualIntelligence: null,
    latestInteractionCapture: null,
    latestMeeting: {
      id: "meeting-1",
      title: "Expansion review",
      meetingDate: "2026-08-01T00:00:00Z",
      status: "completed",
      companyId: "company-1",
      companyName: "Acme Australia",
      participantCount: 2,
      transcriptAvailable: true,
      transcriptVersion: 1,
      intelligenceReadiness: "ready",
      intelligenceSectionsAvailable: 10,
      updatedAt: "2026-07-24T00:00:00Z",
    },
    recentMeetings: [
      {
        id: "meeting-1",
        title: "Expansion review",
        meetingDate: "2026-08-01T00:00:00Z",
        status: "completed",
        companyId: "company-1",
        companyName: "Acme Australia",
        participantCount: 2,
        transcriptAvailable: true,
        transcriptVersion: 1,
        intelligenceReadiness: "ready",
        intelligenceSectionsAvailable: 10,
        updatedAt: "2026-07-24T00:00:00Z",
      },
    ],
    reasoning: {
      state: "completed",
      message: "Longitudinal reasoning is available.",
      latest: insight,
      history: [insight],
    },
    intelligence: completedIntelligence(),
    intelligenceSectionsAvailable: 10,
    partialData: false,
    generatedAt: "2026-07-24T02:00:00Z",
    ...overrides,
  };
}

function meetingPage(items: Meeting[] = [meeting]) {
  return {
    items,
    page: 1,
    pageSize: 100,
    total: items.length,
    pages: items.length ? 1 : 0,
  };
}

function evidenceCapabilities() {
  return {
    documentEvidence: true,
    emailEvidence: true,
    supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
    emailProviderImport: false,
    documentProviderImport: false,
    safeMessage:
      "Select only evidence you are authorised to process. Gmail, Outlook and drive synchronisation are not connected.",
  };
}

describe("OpportunityWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the opportunity hierarchy and all latest-meeting evidence without infrastructure controls", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(workspace()))
        .mockResolvedValueOnce(response(meetingPage()))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", { name: "Platform expansion" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Latest Next Best Action" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Longitudinal Changes" }),
    ).toBeVisible();
    expect(screen.getByText("Champion evidence strengthened")).toBeVisible();
    expect(screen.getByRole("link", { name: "20 July 2026" })).toHaveAttribute(
      "href",
      "/meetings/meeting-0",
    );
    expect(screen.queryByText(/snapshot-1|stakeholders-2/i)).toBeNull();
    expect(
      screen.getByText("Confirm the economic buyer and procurement owner."),
    ).toBeVisible();
    for (const heading of [
      "Latest Meeting Momentum & Buying Signals",
      "Objections & Competitive Signals",
      "Latest Meeting Stakeholders",
      "Latest Meeting Risks & Blockers",
      "Open Questions",
      "Action Items",
      "Key Decisions",
      "Latest Executive Summary",
      "Latest Follow-up Email",
      "Recent Meetings",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    }
    expect(
      screen.getByRole("link", { name: "Open latest meeting intelligence" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    expect(
      screen.getByRole("link", { name: "Expansion review" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    expect(
      screen.queryByRole("button", { name: /generate|regenerate/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /probability|forecast|health score|provider|prompt|worker/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps metadata useful with no associated meetings", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response(
            workspace({
              latestMeeting: null,
              recentMeetings: [],
              intelligence: null,
              intelligenceSectionsAvailable: 0,
            }),
          ),
        )
        .mockResolvedValueOnce(response(meetingPage([])))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", { name: "Platform expansion" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No meetings associated" }),
    ).toBeVisible();
    expect(screen.getByText("Acme Australia")).toBeVisible();
    expect(screen.queryByText(/could not be loaded/i)).not.toBeInTheDocument();
  });

  it("labels reviewed debrief evidence separately from customer-direct meeting evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response(
            workspace({
              latestMeeting: null,
              recentMeetings: [],
              intelligence: null,
              intelligenceSectionsAvailable: 0,
              reportedIntelligence: {
                id: "reported-1",
                interactionId: "interaction-1",
                generatedAt: "2026-08-14T02:00:00Z",
                sourceLabel: "Reported by you",
                items: [
                  {
                    evidenceId: "evidence-1",
                    category: "stakeholder",
                    statement: "Jordan is the confirmed economic buyer.",
                    origin: "salesperson_reported",
                    sourceLabel: "Reported by you",
                    validationState: "verified",
                    conflictState: "not_assessed",
                  },
                ],
              },
            }),
          ),
        )
        .mockResolvedValueOnce(response(meetingPage([])))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Latest post-interaction report",
      }),
    ).toBeVisible();
    expect(screen.getByText("Reported by you")).toBeVisible();
    expect(
      screen.getByText("Jordan is the confirmed economic buyer."),
    ).toBeVisible();
    expect(screen.getByText(/distinct from customer-direct/i)).toBeVisible();
  });

  it("labels reviewed visual evidence by ownership and support without overstating site observations", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response(
            workspace({
              latestMeeting: null,
              recentMeetings: [],
              intelligence: null,
              intelligenceSectionsAvailable: 0,
              visualIntelligence: {
                id: "visual-intelligence-1",
                interactionId: "interaction-1",
                generatedAt: "2026-08-14T02:00:00Z",
                sourceLabel: "reviewed site photo",
                visualType: "site_photo",
                items: [
                  {
                    evidenceId: "visual-evidence-1",
                    category: "technical_constraint",
                    statement: "The loading bay may require a narrower frame.",
                    origin: "ai_inferred",
                    sourceOwnership: "unknown_origin",
                    supportClassification: "observed",
                    sourceLabel: "reviewed site photo",
                    validationState: "verified",
                    conflictState: "not_assessed",
                  },
                ],
              },
            }),
          ),
        )
        .mockResolvedValueOnce(response(meetingPage([])))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Latest visual interaction intelligence",
      }),
    ).toBeVisible();
    expect(screen.getByText(/AI interpreted this site photo/i)).toBeVisible();
    expect(screen.getByText(/not customer-confirmed facts/i)).toBeVisible();
    expect(
      screen.getByText("The loading bay may require a narrower frame."),
    ).toBeVisible();
    expect(screen.queryByText(/buying probability/i)).not.toBeInTheDocument();
  });

  it("shows the latest interaction capture status and Companion navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response(
            workspace({
              latestInteractionCapture: {
                interactionId: "interaction-1",
                title: "On-site renewal workshop",
                interactionType: "face_to_face_meeting",
                lifecycleStatus: "completed",
                captureStatus: "processing_transcription",
                recordingStatus: "transcribing",
                recordingDurationSeconds: 840,
                debriefStatus: null,
                visualCount: 2,
                markerCount: 3,
                updatedAt: "2026-08-15T03:00:00Z",
              },
            }),
          ),
        )
        .mockResolvedValueOnce(response(meetingPage([])))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "On-site renewal workshop",
      }),
    ).toBeVisible();
    expect(screen.getByText("Processing Transcription")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open interaction Companion" }),
    ).toHaveAttribute("href", "/interactions/interaction-1/companion");
  });

  it("associates a selected same-organisation meeting with an optimistic token", async () => {
    const available = { ...meeting, opportunityId: null };
    const noMeeting = workspace({
      latestMeeting: null,
      recentMeetings: [],
      intelligence: null,
      intelligenceSectionsAvailable: 0,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(noMeeting))
      .mockResolvedValueOnce(response(meetingPage([available])))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(evidenceCapabilities()))
      .mockResolvedValueOnce(
        response({ ...available, opportunityId: "opportunity-1" }),
      )
      .mockResolvedValueOnce(response(workspace()))
      .mockResolvedValueOnce(response(meetingPage()));
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    fireEvent.change(await screen.findByLabelText("Meeting"), {
      target: { value: "meeting-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Associate meeting" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
    const patchCall = fetchMock.mock.calls[4];
    expect(String(patchCall?.[0])).toContain(
      "/api/v1/meetings/meeting-1/opportunity",
    );
    expect(patchCall?.[1]).toMatchObject({ method: "PATCH" });
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      opportunityId: "opportunity-1",
      expectedUpdatedAt: meeting.updatedAt,
    });
  });

  it("keeps completed sections visible when another latest-meeting section is unavailable", async () => {
    const partial = completedIntelligence();
    partial.risksBlockers = {
      state: "failed",
      generationAvailable: true,
      message: "Risks & Blockers could not be completed.",
      generatedAt: null,
      emptyResult: false,
      content: null,
    };
    partial.progress = { ...partial.progress, ready: 9, failed: 1 };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response(
            workspace({
              intelligence: partial,
              intelligenceSectionsAvailable: 9,
              partialData: true,
            }),
          ),
        )
        .mockResolvedValueOnce(response(meetingPage()))
        .mockResolvedValueOnce(response([]))
        .mockResolvedValueOnce(response(evidenceCapabilities())),
    );
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    expect(
      await screen.findByText("The customer confirmed the commercial path."),
    ).toBeVisible();
    const risks = screen
      .getByRole("heading", { name: "Latest Meeting Risks & Blockers" })
      .closest("section");
    expect(risks).not.toBeNull();
    expect(
      within(risks as HTMLElement).getByText(
        "Risks & Blockers could not be completed.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(/Some latest-meeting intelligence is not available/),
    ).toBeInTheDocument();
  });

  it("generates longitudinal reasoning on demand and keeps the result after refresh", async () => {
    const notGenerated = workspace({
      reasoning: {
        state: "not_generated",
        message:
          "Longitudinal reasoning has not been generated for the latest snapshots.",
        latest: null,
        history: [],
      },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(notGenerated))
      .mockResolvedValueOnce(response(meetingPage()))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(evidenceCapabilities()))
      .mockResolvedValueOnce(
        response({
          ...workspace().reasoning,
          created: true,
        }),
      )
      .mockResolvedValueOnce(response(workspace()))
      .mockResolvedValueOnce(response(meetingPage()));
    vi.stubGlobal("fetch", fetchMock);
    render(<OpportunityWorkspace opportunityId="opportunity-1" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Generate changes" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain(
      "/api/v1/opportunities/opportunity-1/brain/reasoning",
    );
    expect(fetchMock.mock.calls[4]?.[1]).toMatchObject({ method: "POST" });
    expect(
      await screen.findByText("Champion evidence strengthened"),
    ).toBeVisible();
  });
});
