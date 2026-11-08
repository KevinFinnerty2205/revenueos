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

function installApi(
  initialInteraction: Interaction,
  {
    personalWorkspaceSaveFails = false,
    personalWorkspaceSaveResponse,
  }: {
    personalWorkspaceSaveFails?: boolean;
    personalWorkspaceSaveResponse?: Promise<Response>;
  } = {},
) {
  let currentInteraction = initialInteraction;
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
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/beta/capabilities")) {
      return Promise.resolve(
        jsonResponse({
          featureFlags: {
            aiCompanion: true,
            aiDebrief: true,
            recordingCapture: true,
            visualEvidence: true,
          },
        }),
      );
    }
    if (url.endsWith("/companion/brief")) {
      return Promise.resolve(jsonResponse(completedBrief));
    }
    if (url.endsWith("/companion/markers") && method === "GET") {
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
      return Promise.resolve(jsonResponse(privateWorkspace));
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
      screen.getByRole("link", { name: "Open Revenue Brain" }),
    ).toHaveAttribute("href", "/companies/company-1");
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
});
