import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type {
  Interaction,
  PreInteractionBriefResponse,
} from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FaceToFaceCompanion } from "@/components/face-to-face-companion";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function emptyWorkspace() {
  return {
    exists: false,
    ownerUserId: "user-1",
    lockVersion: 0,
    liveNotes: null,
    enhancedNotes: null,
    followUpDraft: null,
    followUpReviewed: false,
    generationFingerprint: null,
    generationState: "not_started",
    generationId: null,
    generationTranscriptVersion: null,
    generationPersonalNotesState: "not_included",
    generationFailureCode: null,
    generationRetryAvailable: false,
    generationUpdateAvailable: false,
    generationCompletedAt: null,
    importedFromBrowserAt: null,
    updatedAt: null,
  };
}

function interaction(overrides: Partial<Interaction> = {}): Interaction {
  return {
    id: "interaction-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId: "opportunity-1",
    contactId: null,
    meetingId: null,
    interactionType: "face_to_face_meeting",
    lifecycleStatus: "planned",
    title: "Harbour renewal workshop",
    scheduledStartAt: "2026-08-15T02:00:00Z",
    scheduledEndAt: "2026-08-15T03:00:00Z",
    actualStartAt: null,
    actualEndAt: null,
    callDirection: null,
    callOutcome: null,
    durationSeconds: null,
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    createdByUserId: "user-1",
    briefState: "completed",
    briefGeneratedAt: "2026-08-15T00:00:00Z",
    createdAt: "2026-08-15T00:00:00Z",
    updatedAt: "2026-08-15T00:00:00Z",
    ...overrides,
  };
}

const completedBrief: PreInteractionBriefResponse = {
  interactionId: "interaction-1",
  state: "completed",
  generationAvailable: true,
  unavailableReason: null,
  safeMessage: null,
  generatedAt: "2026-08-15T00:00:00Z",
  reviewed: false,
  reviewedAt: null,
  priorVersions: [],
  sourceLabels: ["Opportunity workspace"],
  brief: {
    interactionId: "interaction-1",
    interactionType: "face_to_face_meeting",
    briefVersion: 2,
    headline: "Confirm the renewal path",
    accountContext: "A renewal is in evaluation.",
    recentChanges: [
      {
        change: "Security review opened",
        source: "revenue_brain",
        importance: "high",
      },
    ],
    objectives: [
      {
        objective: "Confirm decision process",
        priority: "high",
        reason: "Open",
      },
      { objective: "Agree next step", priority: "high", reason: "Required" },
    ],
    questionsToAsk: [
      {
        question: "Who signs the renewal?",
        purpose: "Confirm authority",
        priority: "high",
      },
    ],
    stakeholderFocus: [],
    openCommitments: [],
    risksToWatch: [{ risk: "Security timing", severity: "high" }],
    successCriteria: ["A dated next step"],
    interactionGuidance: "Keep it concise.",
    confidence: 0.8,
    companyName: "Harbour Health",
    opportunityName: "2026 renewal",
    participants: [{ name: "Avery", role: "CFO" }],
    nextBestAction: "Book the security review",
  },
};

function emptyBrief(interactionId: string): PreInteractionBriefResponse {
  return {
    interactionId,
    state: "not_generated",
    generationAvailable: true,
    unavailableReason: null,
    safeMessage: null,
    generatedAt: null,
    reviewed: false,
    reviewedAt: null,
    priorVersions: [],
    sourceLabels: [],
    brief: null,
  };
}

function installApi(
  initialInteraction: Interaction,
  {
    aiCompanionEnabled = true,
    liveInteractionIntelligenceEnabled = false,
    capabilitiesResponse,
    failedCompanionEndpoint,
    personalWorkspaceSaveFails = false,
    personalWorkspaceConflictsOnce,
    personalWorkspaceSaveResponse,
    personalWorkspaceLoadResponse,
    briefResponses,
  }: {
    aiCompanionEnabled?: boolean;
    liveInteractionIntelligenceEnabled?: boolean;
    capabilitiesResponse?: Promise<Response>;
    failedCompanionEndpoint?: "capabilities" | "brief" | "markers";
    personalWorkspaceSaveFails?: boolean;
    personalWorkspaceConflictsOnce?: {
      liveNotes: string;
      enhancedNotes?: string;
      followUpDraft?: string;
      followUpReviewed?: boolean;
    };
    personalWorkspaceSaveResponse?: Promise<Response>;
    personalWorkspaceLoadResponse?: Promise<Response>;
    briefResponses?: PreInteractionBriefResponse[];
  } = {},
) {
  let currentInteraction = initialInteraction;
  let workspaceConflictReturned = false;
  const markers: object[] = [];
  let privateWorkspace = {
    exists: false,
    ownerUserId: "user-1",
    lockVersion: 0,
    liveNotes: null as string | null,
    enhancedNotes: null as string | null,
    followUpDraft: null as string | null,
    followUpReviewed: false,
    generationFingerprint: null,
    generationState: "not_started",
    generationId: null,
    generationTranscriptVersion: null,
    generationPersonalNotesState: "not_included",
    generationFailureCode: null,
    generationRetryAvailable: false,
    generationUpdateAvailable: false,
    generationCompletedAt: null,
    importedFromBrowserAt: null,
    updatedAt: null as string | null,
  };
  let briefResponseIndex = 0;
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/beta/capabilities")) {
      if (capabilitiesResponse) return capabilitiesResponse;
      if (failedCompanionEndpoint === "capabilities") {
        return Promise.resolve(
          jsonResponse(
            {
              code: "companion_unavailable",
              message: "Companion controls are temporarily unavailable.",
            },
            503,
          ),
        );
      }
      return Promise.resolve(
        jsonResponse({
          featureFlags: {
            aiCompanion: aiCompanionEnabled,
            aiDebrief: true,
            recordingCapture: true,
            visualEvidence: true,
            liveInteractionIntelligence: liveInteractionIntelligenceEnabled,
          },
        }),
      );
    }
    if (url.endsWith("/companion/brief")) {
      if (failedCompanionEndpoint === "brief") {
        return Promise.resolve(
          jsonResponse(
            {
              code: "brief_unavailable",
              message: "Preparation guidance is temporarily unavailable.",
            },
            503,
          ),
        );
      }
      if (briefResponses?.length) {
        const response =
          briefResponses[
            Math.min(briefResponseIndex, briefResponses.length - 1)
          ];
        briefResponseIndex += 1;
        return Promise.resolve(jsonResponse(response));
      }
      return Promise.resolve(jsonResponse(completedBrief));
    }
    if (url.endsWith("/companion/markers") && method === "GET") {
      if (failedCompanionEndpoint === "markers") {
        return Promise.resolve(
          jsonResponse(
            {
              code: "markers_unavailable",
              message: "Conversation markers are temporarily unavailable.",
            },
            503,
          ),
        );
      }
      return Promise.resolve(jsonResponse(markers));
    }
    if (url.endsWith("/companion/markers") && method === "POST") {
      const body = JSON.parse(String(init?.body)) as {
        markerType: string;
        recordingOffsetMs: number | null;
      };
      const marker = {
        id: `marker-${markers.length + 1}`,
        interactionId: "interaction-1",
        createdByUserId: "user-1",
        markerType: body.markerType,
        recordingOffsetMs: body.recordingOffsetMs,
        createdAt: "2026-08-15T02:05:00Z",
      };
      markers.push(marker);
      return Promise.resolve(jsonResponse(marker, 201));
    }
    if (url.endsWith("/recordings") || url.endsWith("/visual-evidence")) {
      return Promise.resolve(jsonResponse([]));
    }
    if (url.endsWith("/personal-workspace") && method === "GET") {
      return (
        personalWorkspaceLoadResponse ??
        Promise.resolve(jsonResponse(privateWorkspace))
      );
    }
    if (url.endsWith("/personal-workspace") && method === "PUT") {
      if (personalWorkspaceSaveResponse) {
        return personalWorkspaceSaveResponse;
      }
      if (personalWorkspaceSaveFails) {
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
      if (personalWorkspaceConflictsOnce && !workspaceConflictReturned) {
        workspaceConflictReturned = true;
        privateWorkspace = {
          ...privateWorkspace,
          exists: true,
          lockVersion: privateWorkspace.lockVersion + 1,
          liveNotes: personalWorkspaceConflictsOnce.liveNotes,
          enhancedNotes:
            personalWorkspaceConflictsOnce.enhancedNotes ??
            privateWorkspace.enhancedNotes,
          followUpDraft:
            personalWorkspaceConflictsOnce.followUpDraft ??
            privateWorkspace.followUpDraft,
          followUpReviewed:
            personalWorkspaceConflictsOnce.followUpReviewed ??
            privateWorkspace.followUpReviewed,
          updatedAt: "2026-08-15T02:55:00Z",
        };
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
      const body = JSON.parse(String(init?.body)) as {
        liveNotes: string;
        enhancedNotes: string;
        followUpDraft: string;
        followUpReviewed: boolean;
      };
      privateWorkspace = {
        ...privateWorkspace,
        exists: true,
        lockVersion: privateWorkspace.lockVersion + 1,
        liveNotes: body.liveNotes,
        enhancedNotes: body.enhancedNotes,
        followUpDraft: body.followUpDraft,
        followUpReviewed: body.followUpReviewed,
        updatedAt: "2026-08-15T03:00:00Z",
      };
      return Promise.resolve(jsonResponse(privateWorkspace));
    }
    if (url.endsWith("/start") && method === "POST") {
      currentInteraction = interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      });
      return Promise.resolve(jsonResponse(currentInteraction));
    }
    if (url.endsWith("/complete") && method === "POST") {
      currentInteraction = interaction({
        lifecycleStatus: "completed",
        actualStartAt: "2026-08-15T02:00:00Z",
        actualEndAt: "2026-08-15T03:00:00Z",
      });
      return Promise.resolve(jsonResponse(currentInteraction));
    }
    if (url.endsWith("/interactions/interaction-1") && method === "GET") {
      return Promise.resolve(jsonResponse(currentInteraction));
    }
    return Promise.resolve(
      jsonResponse({ code: "unexpected", message: url }, 500),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("FaceToFaceCompanion", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("shows a concise before brief and enters passive during capture deliberately", async () => {
    const fetchMock = installApi(interaction());
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    expect(await screen.findByText("30-second brief")).toBeVisible();
    expect(screen.getByText("Harbour Health · 2026 renewal")).toBeVisible();
    expect(screen.getByText("Who signs the renewal?")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start interaction" }));
    expect(
      await screen.findByRole("heading", {
        name: "How should Companion help?",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Continue without recording" }),
    );
    expect(
      screen.getByRole("heading", { name: "No recording or listening" }),
    ).toBeVisible();
    const liveNotes = screen.getByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "Finance will confirm the signer on Friday." },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add marker" }));
    fireEvent.click(screen.getByRole("button", { name: "Objection" }));
    expect(await screen.findByText("Objection marked.")).toBeVisible();
    expect(liveNotes).toHaveValue("Finance will confirm the signer on Friday.");
    fireEvent.click(
      screen.getByRole("button", {
        name: "Save notes and end interaction",
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Fill the gaps while they are fresh",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/Use the debrief to capture the outcome/i),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Capture what happened" }),
    ).toBeVisible();
    fireEvent.click(screen.getByText("More options"));
    expect(
      screen.getByRole("link", { name: "Open conversation history" }),
    ).toHaveAttribute("href", "/conversations/accounts/company-1");
    expect(screen.getByText("1", { selector: "dd" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/complete"),
      expect.objectContaining({ method: "POST" }),
    );
    const privateSaveIndex = fetchMock.mock.calls.findIndex(
      ([input, init]) =>
        String(input).endsWith("/personal-workspace") && init?.method === "PUT",
    );
    const completionIndex = fetchMock.mock.calls.findIndex(([input]) =>
      String(input).endsWith("/complete"),
    );
    expect(privateSaveIndex).toBeGreaterThan(-1);
    expect(completionIndex).toBeGreaterThan(privateSaveIndex);
    expect(
      JSON.parse(String(fetchMock.mock.calls[privateSaveIndex]?.[1]?.body)),
    ).toMatchObject({
      liveNotes: "Finance will confirm the signer on Friday.",
    });
  });

  it("rejects initial preparation guidance from another interaction", async () => {
    installApi(interaction(), {
      briefResponses: [
        {
          ...completedBrief,
          interactionId: "interaction-from-another-tab",
          brief: {
            ...completedBrief.brief!,
            interactionId: "interaction-from-another-tab",
            headline: "Private brief from another interaction",
          },
        },
      ],
    });

    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    expect(
      await screen.findByText(
        "Preparation guidance could not be loaded. Your private notes remain available.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText("Private brief from another interaction"),
    ).not.toBeInTheDocument();
  });

  it("preserves a verified brief when refresh returns another interaction", async () => {
    installApi(interaction(), {
      briefResponses: [
        completedBrief,
        {
          ...completedBrief,
          interactionId: "interaction-from-another-tab",
          brief: {
            ...completedBrief.brief!,
            interactionId: "interaction-from-another-tab",
            headline: "Private refreshed brief from another interaction",
          },
        },
      ],
    });

    const { rerender } = render(
      <FaceToFaceCompanion interactionId="interaction-1" briefRefreshKey={0} />,
    );
    expect(await screen.findByText("Confirm the renewal path")).toBeVisible();

    rerender(
      <FaceToFaceCompanion interactionId="interaction-1" briefRefreshKey={1} />,
    );

    expect(
      await screen.findByText(
        "The refreshed preparation brief could not be loaded. Your private notes remain available.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Confirm the renewal path")).toBeVisible();
    expect(
      screen.queryByText("Private refreshed brief from another interaction"),
    ).not.toBeInTheDocument();
  });

  it("preserves the empty brief when preparation returns another interaction", async () => {
    installApi(interaction(), {
      briefResponses: [
        emptyBrief("interaction-1"),
        {
          ...completedBrief,
          interactionId: "interaction-from-another-tab",
          brief: {
            ...completedBrief.brief!,
            interactionId: "interaction-from-another-tab",
            headline: "Private generated brief from another interaction",
          },
        },
      ],
    });

    render(<FaceToFaceCompanion interactionId="interaction-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare brief" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The preparation response did not match this conversation. Try again.",
    );
    expect(screen.getByRole("button", { name: "Prepare brief" })).toBeVisible();
    expect(
      screen.queryByText("Private generated brief from another interaction"),
    ).not.toBeInTheDocument();
  });

  it("forces a phone call into honest passive mode", async () => {
    installApi(
      interaction({
        interactionType: "phone_call",
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      }),
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    expect(
      await screen.findByRole("heading", { name: "No recording or listening" }),
    ).toBeVisible();
    expect(
      screen.getByText(/cannot reliably record the same phone call/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Record interaction" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Recording status")).not.toBeInTheDocument();
  });

  it("keeps one private-notes editor usable when AI Companion is disabled", async () => {
    const initialInteraction = interaction({
      companyId: null,
      opportunityId: null,
      interactionType: "manual_interaction",
      title: "Event notes",
    });
    const fetchMock = installApi(initialInteraction, {
      aiCompanionEnabled: false,
      liveInteractionIntelligenceEnabled: true,
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
        embedded
      />,
    );

    const notes = await screen.findByLabelText("Private live notes");
    await waitFor(() => expect(notes).toBeEnabled());
    expect(screen.getAllByLabelText("Private live notes")).toHaveLength(1);
    fireEvent.change(notes, {
      target: { value: "Met the operations team at the industry event." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save private notes" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).endsWith("/personal-workspace") &&
            init?.method === "PUT",
        ),
      ).toBe(true),
    );
    const saveCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/personal-workspace") && init?.method === "PUT",
    );
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      liveNotes: "Met the operations team at the industry event.",
    });
    expect(
      await screen.findByText("Private notes are still available"),
    ).toBeVisible();
    const start = screen.getByRole("button", { name: "Start interaction" });
    expect(start).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Record interaction" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Continue without recording" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add marker" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Checking Live Intelligence…"),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/companion/brief"),
      ),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/companion/markers"),
      ),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        /\/(recordings|visual-evidence)$/.test(String(input)),
      ),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/live-intelligence"),
      ),
    ).toBe(false);

    fireEvent.click(start);
    const end = await screen.findByRole("button", { name: "End interaction" });
    expect(end).toBeEnabled();
    expect(screen.getAllByLabelText("Private live notes")).toHaveLength(1);
    expect(
      screen.queryByRole("heading", { name: "How should Companion help?" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add marker" }),
    ).not.toBeInTheDocument();

    fireEvent.click(end);
    expect(
      await screen.findByRole("heading", { name: "Conversation ended" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/start"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/complete"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it.each([
    {
      endpoint: "capabilities" as const,
      warning: /Companion availability could not be checked/i,
    },
    {
      endpoint: "brief" as const,
      warning: /Preparation guidance could not be loaded/i,
    },
    {
      endpoint: "markers" as const,
      warning: /Conversation markers could not be loaded/i,
    },
  ])(
    "keeps private notes usable when the $endpoint request fails",
    async ({ endpoint, warning }) => {
      window.sessionStorage.setItem(
        "revenueos:companion:capture-choice:interaction-1",
        "passive",
      );
      const initialInteraction = interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      });
      const fetchMock = installApi(initialInteraction, {
        failedCompanionEndpoint: endpoint,
      });

      render(
        <FaceToFaceCompanion
          interactionId="interaction-1"
          initialInteraction={initialInteraction}
          embedded
        />,
      );

      const notes = await screen.findByLabelText("Private live notes");
      await waitFor(() => expect(notes).toBeEnabled());
      expect(screen.getAllByLabelText("Private live notes")).toHaveLength(1);
      expect(await screen.findByText(warning)).toBeVisible();
      fireEvent.change(notes, {
        target: { value: `Notes survive a ${endpoint} failure.` },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Save private notes" }),
      );
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(
            ([input, init]) =>
              String(input).endsWith("/personal-workspace") &&
              init?.method === "PUT",
          ),
        ).toBe(true),
      );
      expect(notes).toHaveValue(`Notes survive a ${endpoint} failure.`);

      if (endpoint === "capabilities") {
        expect(
          screen.queryByRole("heading", {
            name: "How should Companion help?",
          }),
        ).not.toBeInTheDocument();
        expect(
          screen.getByRole("button", { name: "End interaction" }),
        ).toBeEnabled();
        expect(
          screen.queryByRole("button", { name: "Record interaction" }),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole("button", { name: "Continue without recording" }),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole("button", { name: "Add marker" }),
        ).not.toBeInTheDocument();
        expect(
          fetchMock.mock.calls.some(([input]) =>
            String(input).includes("/companion/brief"),
          ),
        ).toBe(false);
        expect(
          fetchMock.mock.calls.some(([input]) =>
            String(input).includes("/companion/markers"),
          ),
        ).toBe(false);
        expect(
          fetchMock.mock.calls.some(([input]) =>
            /\/(recordings|visual-evidence)$/.test(String(input)),
          ),
        ).toBe(false);
        expect(
          fetchMock.mock.calls.some(([input]) =>
            String(input).includes("/live-intelligence"),
          ),
        ).toBe(false);
        expect(
          screen.queryByText("Checking Live Intelligence…"),
        ).not.toBeInTheDocument();
      }

      if (endpoint === "markers") {
        expect(
          screen.queryByRole("button", { name: "Add marker" }),
        ).not.toBeInTheDocument();
      }
    },
  );

  it.each([
    { embedded: true, route: "conversation workspace" },
    { embedded: false, route: "direct Companion route" },
  ])(
    "keeps one canonical private-notes editor in the $route while capture controls change",
    async ({ embedded }) => {
      let resolveCapabilities!: (value: Response) => void;
      const pendingCapabilities = new Promise<Response>((resolve) => {
        resolveCapabilities = resolve;
      });
      window.sessionStorage.setItem(
        "revenueos:companion:capture-choice:interaction-1",
        "passive",
      );
      const initialInteraction = interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      });
      installApi(initialInteraction, {
        capabilitiesResponse: pendingCapabilities,
      });

      render(
        <FaceToFaceCompanion
          interactionId="interaction-1"
          initialInteraction={initialInteraction}
          embedded={embedded}
        />,
      );

      const notesBeforeCapabilityCheck =
        await screen.findByLabelText("Private live notes");
      await waitFor(() => expect(notesBeforeCapabilityCheck).toBeEnabled());
      fireEvent.change(notesBeforeCapabilityCheck, {
        target: { value: "Keep this draft mounted." },
      });
      await act(async () => {
        resolveCapabilities(
          jsonResponse({
            featureFlags: {
              aiCompanion: true,
              aiDebrief: false,
              recordingCapture: false,
              visualEvidence: false,
              liveInteractionIntelligence: false,
            },
          }),
        );
        await pendingCapabilities;
      });
      expect(
        await screen.findByRole("heading", {
          name: "No recording or listening",
        }),
      ).toBeVisible();
      expect(screen.getAllByLabelText("Private live notes")).toHaveLength(1);
      expect(screen.getByLabelText("Private live notes")).toBe(
        notesBeforeCapabilityCheck,
      );
      expect(notesBeforeCapabilityCheck).toHaveValue(
        "Keep this draft mounted.",
      );
    },
  );

  it("keeps direct notes disabled until the private workspace has loaded", async () => {
    let resolveWorkspace!: (value: Response) => void;
    const pendingWorkspace = new Promise<Response>((resolve) => {
      resolveWorkspace = resolve;
    });
    installApi(interaction(), {
      personalWorkspaceLoadResponse: pendingWorkspace,
    });

    render(<FaceToFaceCompanion interactionId="interaction-1" embedded />);

    const notes = await screen.findByLabelText("Private live notes");
    expect(notes).toBeDisabled();
    await act(async () => {
      resolveWorkspace(
        jsonResponse({
          exists: false,
          ownerUserId: "user-1",
          lockVersion: 0,
          liveNotes: null,
          enhancedNotes: null,
          followUpDraft: null,
          followUpReviewed: false,
          generationFingerprint: null,
          generationState: "not_started",
          generationId: null,
          generationTranscriptVersion: null,
          generationPersonalNotesState: "not_included",
          generationFailureCode: null,
          generationRetryAvailable: false,
          generationUpdateAvailable: false,
          generationCompletedAt: null,
          importedFromBrowserAt: null,
          updatedAt: null,
        }),
      );
      await pendingWorkspace;
    });
    await waitFor(() => expect(notes).toBeEnabled());
  });

  it("keeps the interaction open when dirty private notes cannot be saved", async () => {
    const fetchMock = installApi(
      interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      }),
      { personalWorkspaceSaveFails: true },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    await screen.findByRole("heading", { name: "How should Companion help?" });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue without recording" }),
    );
    const liveNotes = screen.getByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "Do not lose this unresolved signer note." },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Save notes and end interaction",
      }),
    );

    expect(await screen.findByText(/interaction remains open/i)).toBeVisible();
    expect(liveNotes).toHaveValue("Do not lose this unresolved signer note.");
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/complete") && init?.method === "POST",
      ),
    ).toBe(false);
    expect(
      screen.getByRole("button", { name: "Save notes and end interaction" }),
    ).toBeVisible();
  });

  it("compares and safely saves a stale private note before ending", async () => {
    const latestSavedNote =
      "The first session saved a Friday implementation review.";
    const latestEnhancedNotes =
      "The first session also refined the private enhanced notes.";
    const latestFollowUp =
      "Private follow-up wording saved by the first session.";
    const fetchMock = installApi(
      interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      }),
      {
        personalWorkspaceConflictsOnce: {
          liveNotes: latestSavedNote,
          enhancedNotes: latestEnhancedNotes,
          followUpDraft: latestFollowUp,
          followUpReviewed: true,
        },
      },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    await screen.findByRole("heading", { name: "How should Companion help?" });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue without recording" }),
    );
    const liveNotes = screen.getByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "My unsaved note from the second session." },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Save notes and end interaction",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Private notes changed in another session",
      }),
    ).toBeVisible();
    expect(liveNotes).toBeEnabled();
    expect(liveNotes).toHaveValue("My unsaved note from the second session.");
    expect(
      await screen.findByLabelText("Latest saved private note"),
    ).toHaveValue(latestSavedNote);
    expect(
      screen.getByRole("button", {
        name: "Save notes and end interaction",
      }),
    ).toBeDisabled();
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/complete") && init?.method === "POST",
      ),
    ).toBe(false);

    const mergedNote = `${latestSavedNote}\n\nMy note: signer confirmation is still open.`;
    fireEvent.change(liveNotes, { target: { value: mergedNote } });
    fireEvent.click(screen.getByRole("button", { name: "Save reviewed note" }));

    expect(
      await screen.findByText("Private notes saved.", { exact: true }),
    ).toBeVisible();
    const workspacePutCalls = fetchMock.mock.calls.filter(
      ([input, init]) =>
        String(input).endsWith("/personal-workspace") && init?.method === "PUT",
    );
    expect(workspacePutCalls).toHaveLength(2);
    expect(
      JSON.parse(
        String(workspacePutCalls[workspacePutCalls.length - 1]?.[1]?.body),
      ),
    ).toMatchObject({
      expectedLockVersion: 1,
      liveNotes: mergedNote,
      enhancedNotes: latestEnhancedNotes,
      followUpDraft: latestFollowUp,
      followUpReviewed: true,
    });
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/complete") && init?.method === "POST",
      ),
    ).toBe(false);

    const end = screen.getByRole("button", { name: "End interaction" });
    expect(end).toBeEnabled();
    fireEvent.click(end);
    expect(
      await screen.findByRole("heading", {
        name: "Fill the gaps while they are fresh",
      }),
    ).toBeVisible();
  });

  it("keeps a newer note edit open when it changes during save-before-end", async () => {
    let resolveSave!: (value: Response) => void;
    const pendingSave = new Promise<Response>((resolve) => {
      resolveSave = resolve;
    });
    const fetchMock = installApi(
      interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      }),
      { personalWorkspaceSaveResponse: pendingSave },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    await screen.findByRole("heading", { name: "How should Companion help?" });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue without recording" }),
    );
    const liveNotes = screen.getByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "The note submitted when End was selected." },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Save notes and end interaction",
      }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).endsWith("/personal-workspace") &&
            init?.method === "PUT",
        ),
      ).toBe(true),
    );

    fireEvent.change(liveNotes, {
      target: { value: "A newer note typed before the save finished." },
    });
    await act(async () => {
      resolveSave(
        jsonResponse({
          exists: true,
          ownerUserId: "user-1",
          lockVersion: 1,
          liveNotes: "The note submitted when End was selected.",
          enhancedNotes: "",
          followUpDraft: "",
          followUpReviewed: false,
          generationFingerprint: null,
          generationState: "not_started",
          generationId: null,
          generationTranscriptVersion: null,
          generationPersonalNotesState: "not_included",
          generationFailureCode: null,
          generationRetryAvailable: false,
          generationUpdateAvailable: false,
          generationCompletedAt: null,
          importedFromBrowserAt: null,
          updatedAt: "2026-08-15T03:00:00Z",
        }),
      );
      await pendingSave;
    });

    expect(
      await screen.findByText(/notes changed while saving/i),
    ).toBeVisible();
    expect(liveNotes).toHaveValue(
      "A newer note typed before the save finished.",
    );
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/complete") && init?.method === "POST",
      ),
    ).toBe(false);
    expect(
      screen.getByRole("button", { name: "Save notes and end interaction" }),
    ).toBeVisible();
  });

  it("ignores an initial interaction load that settles during the next interaction commit", async () => {
    const first = interaction({
      id: "interaction-a",
      title: "Private interaction A sentinel",
    });
    const second = interaction({
      id: "interaction-b",
      title: "Interaction B",
    });
    const firstLoad = deferred<Response>();
    const secondLoad = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: {
              aiCompanion: false,
              aiDebrief: false,
              recordingCapture: false,
              visualEvidence: false,
              liveInteractionIntelligence: false,
            },
          }),
        );
      }
      if (url.endsWith("/personal-workspace") && method === "GET") {
        return Promise.resolve(jsonResponse(emptyWorkspace()));
      }
      if (url.endsWith("/interactions/interaction-a") && method === "GET") {
        return firstLoad.promise;
      }
      if (url.endsWith("/interactions/interaction-b") && method === "GET") {
        return secondLoad.promise;
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: `${method} ${url}` }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const onInteractionChange = vi.fn();

    const { rerender } = render(
      <FaceToFaceCompanion
        interactionId="interaction-a"
        onInteractionChange={onInteractionChange}
      />,
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/interactions/interaction-a"),
        ),
      ).toBe(true),
    );

    await act(async () => {
      rerender(
        <FaceToFaceCompanion
          interactionId="interaction-b"
          onInteractionChange={onInteractionChange}
        />,
      );
      firstLoad.resolve(jsonResponse(first));
      secondLoad.resolve(jsonResponse(second));
      await Promise.all([firstLoad.promise, secondLoad.promise]);
    });

    expect(
      await screen.findByRole("heading", { name: "Interaction B" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Private interaction A sentinel"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onInteractionChange).toHaveBeenCalledTimes(1);
    expect(onInteractionChange).toHaveBeenLastCalledWith(second);
  });

  it("removes the previous interaction while the next interaction loads or fails", async () => {
    const first = interaction({
      id: "interaction-a",
      title: "Private interaction A sentinel",
    });
    const second = interaction({
      id: "interaction-b",
      title: "Interaction B",
    });
    const secondLoad = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: {
              aiCompanion: false,
              aiDebrief: false,
              recordingCapture: false,
              visualEvidence: false,
              liveInteractionIntelligence: false,
            },
          }),
        );
      }
      if (url.endsWith("/personal-workspace") && method === "GET") {
        return Promise.resolve(jsonResponse(emptyWorkspace()));
      }
      if (url.endsWith("/interactions/interaction-b") && method === "GET") {
        return secondLoad.promise;
      }
      if (url.endsWith("/interactions/interaction-c") && method === "GET") {
        return Promise.resolve(
          jsonResponse(
            {
              code: "interaction_unavailable",
              message: "Interaction C could not be loaded.",
            },
            503,
          ),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: `${method} ${url}` }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const onInteractionChange = vi.fn();

    const { rerender } = render(
      <FaceToFaceCompanion
        interactionId="interaction-a"
        initialInteraction={first}
        onInteractionChange={onInteractionChange}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Private interaction A sentinel",
      }),
    ).toBeVisible();

    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-b"
        initialInteraction={first}
        onInteractionChange={onInteractionChange}
      />,
    );

    expect(
      screen.queryByText("Private interaction A sentinel"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading notes & capture…",
    );
    expect(
      screen.queryByRole("button", { name: "Start interaction" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      secondLoad.resolve(jsonResponse(second));
      await secondLoad.promise;
    });
    expect(
      await screen.findByRole("heading", { name: "Interaction B" }),
    ).toBeVisible();
    expect(onInteractionChange).toHaveBeenCalledTimes(1);
    expect(onInteractionChange).toHaveBeenLastCalledWith(second);

    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-c"
        initialInteraction={second}
        onInteractionChange={onInteractionChange}
      />,
    );
    expect(screen.queryByText("Interaction B")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interaction C could not be loaded.",
    );
    expect(screen.queryByText("Interaction B")).not.toBeInTheDocument();
  });

  it("ignores a late completion from the previous interaction and targets the rendered session", async () => {
    const first = interaction({
      id: "interaction-a",
      title: "Private interaction A sentinel",
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const second = interaction({
      id: "interaction-b",
      title: "Interaction B",
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const completedFirst = interaction({
      ...first,
      lifecycleStatus: "completed",
      actualEndAt: "2026-08-15T03:00:00Z",
    });
    const completedSecond = interaction({
      ...second,
      lifecycleStatus: "completed",
      actualEndAt: "2026-08-15T03:00:00Z",
    });
    const firstCompletion = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: {
              aiCompanion: false,
              aiDebrief: false,
              recordingCapture: false,
              visualEvidence: false,
              liveInteractionIntelligence: false,
            },
          }),
        );
      }
      if (url.endsWith("/personal-workspace") && method === "GET") {
        return Promise.resolve(jsonResponse(emptyWorkspace()));
      }
      if (url.endsWith("/interactions/interaction-a/complete")) {
        return firstCompletion.promise;
      }
      if (url.endsWith("/interactions/interaction-b/complete")) {
        return Promise.resolve(jsonResponse(completedSecond));
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: `${method} ${url}` }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const onInteractionChange = vi.fn();

    const { rerender } = render(
      <FaceToFaceCompanion
        interactionId="interaction-a"
        initialInteraction={first}
        onInteractionChange={onInteractionChange}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "End interaction" }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).endsWith("/interactions/interaction-a/complete") &&
            init?.method === "POST",
        ),
      ).toBe(true),
    );

    await act(async () => {
      rerender(
        <FaceToFaceCompanion
          interactionId="interaction-b"
          initialInteraction={second}
          onInteractionChange={onInteractionChange}
        />,
      );
      firstCompletion.resolve(jsonResponse(completedFirst));
      await firstCompletion.promise;
    });
    expect(
      screen.queryByText("Private interaction A sentinel"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Interaction B" }),
    ).toBeVisible();

    expect(onInteractionChange).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Interaction B" }),
    ).toBeVisible();
    expect(
      screen.queryByText(/Interaction completed/i),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "End interaction" }));
    await waitFor(() =>
      expect(onInteractionChange).toHaveBeenCalledWith(completedSecond),
    );
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/interactions/interaction-b/complete") &&
          init?.method === "POST",
      ),
    ).toBe(true);
  });

  it("does not apply a late marker to the next interaction and posts new markers to that interaction", async () => {
    const first = interaction({
      id: "interaction-a",
      title: "Private interaction A sentinel",
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const second = interaction({
      id: "interaction-b",
      title: "Interaction B",
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const firstMarker = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: {
              aiCompanion: true,
              aiDebrief: false,
              recordingCapture: false,
              visualEvidence: false,
              liveInteractionIntelligence: false,
            },
          }),
        );
      }
      if (url.endsWith("/personal-workspace") && method === "GET") {
        return Promise.resolve(jsonResponse(emptyWorkspace()));
      }
      if (url.endsWith("/companion/brief") && method === "GET") {
        const requestedInteractionId = url.includes("interaction-a")
          ? "interaction-a"
          : "interaction-b";
        return Promise.resolve(
          jsonResponse({
            ...completedBrief,
            interactionId: requestedInteractionId,
            brief: {
              ...completedBrief.brief,
              interactionId: requestedInteractionId,
              headline: `${requestedInteractionId} brief`,
            },
          }),
        );
      }
      if (url.endsWith("/companion/markers") && method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }
      if (
        url.endsWith("/interactions/interaction-a/companion/markers") &&
        method === "POST"
      ) {
        return firstMarker.promise;
      }
      if (
        url.endsWith("/interactions/interaction-b/companion/markers") &&
        method === "POST"
      ) {
        return Promise.resolve(
          jsonResponse(
            {
              id: "marker-b",
              interactionId: "interaction-b",
              createdByUserId: "user-1",
              markerType: "action_item",
              recordingOffsetMs: null,
              createdAt: "2026-08-15T02:05:00Z",
            },
            201,
          ),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: `${method} ${url}` }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:interaction-a",
      "passive",
    );
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:interaction-b",
      "passive",
    );

    const { rerender } = render(
      <FaceToFaceCompanion
        interactionId="interaction-a"
        initialInteraction={first}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Add marker" }));
    fireEvent.click(screen.getByRole("button", { name: "Objection" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).endsWith(
              "/interactions/interaction-a/companion/markers",
            ) && init?.method === "POST",
        ),
      ).toBe(true),
    );

    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-b"
        initialInteraction={second}
      />,
    );
    expect(
      screen.queryByText("Private interaction A sentinel"),
    ).not.toBeInTheDocument();
    await act(async () => {
      firstMarker.resolve(
        jsonResponse(
          {
            id: "marker-a",
            interactionId: "interaction-a",
            createdByUserId: "user-1",
            markerType: "objection",
            recordingOffsetMs: 42_000,
            createdAt: "2026-08-15T02:04:00Z",
          },
          201,
        ),
      );
      await firstMarker.promise;
    });
    expect(screen.queryByText("Objection marked.")).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "Add marker" }));
    fireEvent.click(screen.getByRole("button", { name: "Action" }));
    expect(await screen.findByText("Action Item marked.")).toBeVisible();
    const secondMarkerCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith(
          "/interactions/interaction-b/companion/markers",
        ) && init?.method === "POST",
    );
    expect(JSON.parse(String(secondMarkerCall?.[1]?.body))).toMatchObject({
      markerType: "action_item",
      recordingOffsetMs: null,
    });
  });
});
