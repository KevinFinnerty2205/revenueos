import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type {
  Interaction,
  InteractionMarker,
  PreInteractionBriefResponse,
  RecordingSession,
  VisualEvidence,
} from "@revenueos/shared";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FaceToFaceCompanion } from "@/components/face-to-face-companion";
import type { RecordingActivity } from "@/components/recording-foundation";

const verifiedOrganisation = vi.hoisted(() => ({
  state: {
    status: "available" as "available" | "loading" | "unavailable",
    organisationId: "organisation-1" as string | null,
    userId: "user-1" as string | null,
    identityKey: "organisation-1:user-1",
    reload: vi.fn(),
  },
}));

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => verifiedOrganisation.state,
}));

const recorderStub = vi.hoisted(() => ({
  enabled: false,
  activity: undefined as ((value: RecordingActivity) => void) | undefined,
  resolve: undefined as ((recording: RecordingSession) => void) | undefined,
  verifyList: undefined as
    ((recordings: RecordingSession[]) => void) | undefined,
}));

vi.mock(import("@/components/recording-foundation"), async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    RecordingFoundation(
      props: ComponentProps<typeof original.RecordingFoundation>,
    ) {
      if (!recorderStub.enabled)
        return <original.RecordingFoundation {...props} />;
      recorderStub.activity = props.onActivityChange;
      recorderStub.resolve = props.onRecoveryResolved;
      recorderStub.verifyList = props.onRecoveryListVerified;
      return (
        <button type="button" disabled={props.startDisabled}>
          Start recording
        </button>
      );
    },
  };
});

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

function emptyWorkspace(interactionId = "interaction-1") {
  return {
    exists: false,
    interactionId,
    organisationId: "organisation-1",
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

function emptyWorkspaceForUrl(url: string) {
  const match = url.match(/\/interactions\/([^/]+)\/personal-workspace$/);
  return emptyWorkspace(match ? decodeURIComponent(match[1]) : "interaction-1");
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

const priorMarker: InteractionMarker = {
  id: "marker-prior",
  interactionId: "interaction-1",
  createdByUserId: "colleague-1",
  markerType: "decision",
  recordingOffsetMs: null,
  createdAt: "2026-08-15T02:05:00Z",
};

const priorRecording: RecordingSession = {
  id: "recording-1",
  interactionId: "interaction-1",
  captureSessionId: "capture-1",
  recordingType: "live_audio_recording",
  recordingSource: null,
  lifecycleStatus: "uploaded",
  consentState: "acknowledged",
  startedAt: "2026-08-15T02:01:00Z",
  stoppedAt: "2026-08-15T02:02:00Z",
  durationSeconds: 60,
  expectedMimeType: "audio/webm",
  finalMimeType: "audio/webm",
  totalBytes: 72,
  chunkCount: 1,
  uploadCompletedAt: "2026-08-15T02:03:00Z",
  transcriptionStatus: "queued",
  transcriptionAttempts: 0,
  failureCode: null,
  autoIntelligenceStatus: "disabled",
  sessionExpiresAt: "2026-08-16T00:00:00Z",
  providerMode: "mock",
  externalProcessing: false,
  createdAt: "2026-08-15T02:01:00Z",
  updatedAt: "2026-08-15T02:03:00Z",
};

const interruptedRecording: RecordingSession = {
  ...priorRecording,
  lifecycleStatus: "uploading",
  finalMimeType: null,
  uploadCompletedAt: null,
  transcriptionStatus: "disabled",
  sessionExpiresAt: "2099-08-16T00:00:00Z",
};

const priorPhoto: VisualEvidence = {
  id: "visual-1",
  interactionId: "interaction-1",
  captureSessionId: "visual-1",
  visualType: "whiteboard",
  sourceOwnership: "unknown_origin",
  contextLabel: null,
  filename: "board.png",
  mimeType: "image/png",
  byteSize: 68,
  width: 1,
  height: 1,
  checksumSha256: "a".repeat(64),
  capturedAt: "2026-08-15T02:04:00Z",
  processingStatus: "review",
  processingAttempts: 1,
  failureCode: null,
  providerMode: "mock",
  externalProcessing: false,
  candidates: [],
  downloadUrl: null,
  interactionIntelligenceId: null,
  revenueBrainSnapshotId: null,
  createdAt: "2026-08-15T02:04:00Z",
  updatedAt: "2026-08-15T02:04:00Z",
};

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
    personalWorkspaceLoadResponses,
    briefResponses,
    interactionLoadResponses,
    startResponses,
    completeResponses,
    captureResponse,
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
    personalWorkspaceLoadResponses?: Response[];
    briefResponses?: PreInteractionBriefResponse[];
    interactionLoadResponses?: object[];
    startResponses?: object[];
    completeResponses?: object[];
    captureResponse?: (
      url: string,
      method: string,
    ) => Response | Promise<Response> | undefined;
  } = {},
) {
  let currentInteraction = initialInteraction;
  let workspaceConflictReturned = false;
  let workspaceLoadResponseIndex = 0;
  let interactionLoadResponseIndex = 0;
  let startResponseIndex = 0;
  let completeResponseIndex = 0;
  const markers: object[] = [];
  let privateWorkspace = {
    exists: false,
    interactionId: "interaction-1",
    organisationId: "organisation-1",
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
    const captureOverride = captureResponse?.(url, method);
    if (captureOverride) return Promise.resolve(captureOverride);
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
      if (personalWorkspaceLoadResponses?.length) {
        const response =
          personalWorkspaceLoadResponses[
            Math.min(
              workspaceLoadResponseIndex,
              personalWorkspaceLoadResponses.length - 1,
            )
          ];
        workspaceLoadResponseIndex += 1;
        return Promise.resolve(response);
      }
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
      if (startResponses?.length) {
        const response =
          startResponses[
            Math.min(startResponseIndex, startResponses.length - 1)
          ];
        startResponseIndex += 1;
        return Promise.resolve(jsonResponse(response));
      }
      currentInteraction = {
        ...currentInteraction,
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
        actualEndAt: null,
        updatedAt: "2026-08-15T02:00:00Z",
      };
      return Promise.resolve(jsonResponse(currentInteraction));
    }
    if (url.endsWith("/complete") && method === "POST") {
      if (completeResponses?.length) {
        const response =
          completeResponses[
            Math.min(completeResponseIndex, completeResponses.length - 1)
          ];
        completeResponseIndex += 1;
        return Promise.resolve(jsonResponse(response));
      }
      currentInteraction = {
        ...currentInteraction,
        lifecycleStatus: "completed",
        actualStartAt:
          currentInteraction.actualStartAt ?? "2026-08-15T02:00:00Z",
        actualEndAt: "2026-08-15T03:00:00Z",
        updatedAt: "2026-08-15T03:00:00Z",
      };
      return Promise.resolve(jsonResponse(currentInteraction));
    }
    if (url.endsWith("/interactions/interaction-1") && method === "GET") {
      if (interactionLoadResponses?.length) {
        const response =
          interactionLoadResponses[
            Math.min(
              interactionLoadResponseIndex,
              interactionLoadResponses.length - 1,
            )
          ];
        interactionLoadResponseIndex += 1;
        return Promise.resolve(jsonResponse(response));
      }
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
    recorderStub.enabled = false;
    recorderStub.activity = undefined;
    recorderStub.resolve = undefined;
    recorderStub.verifyList = undefined;
    window.sessionStorage.clear();
    verifiedOrganisation.state.status = "available";
    verifiedOrganisation.state.organisationId = "organisation-1";
    verifiedOrganisation.state.userId = "user-1";
    verifiedOrganisation.state.identityKey = "organisation-1:user-1";
    verifiedOrganisation.state.reload.mockClear();
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

  it("rejects an exact interaction load with foreign identity", async () => {
    const foreignInteraction = interaction({
      id: "interaction-from-another-tab",
      title: "Private foreign interaction sentinel",
    });
    const validInteraction = interaction({
      title: "Verified interaction after retry",
    });
    const onInteractionChange = vi.fn();
    installApi(interaction(), {
      interactionLoadResponses: [foreignInteraction, validInteraction],
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        onInteractionChange={onInteractionChange}
      />,
    );

    expect(
      await screen.findByText(
        "The interaction response did not match this conversation. Try again.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText("Private foreign interaction sentinel"),
    ).not.toBeInTheDocument();
    expect(onInteractionChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("heading", {
        name: "Verified interaction after retry",
      }),
    ).toBeVisible();
    expect(
      screen.queryByText("Private foreign interaction sentinel"),
    ).not.toBeInTheDocument();
    expect(onInteractionChange).toHaveBeenCalledTimes(1);
    expect(onInteractionChange).toHaveBeenCalledWith(validInteraction);
  });

  it("preserves verified notes and retries after an invalid start response", async () => {
    const initialInteraction = interaction();
    const invalidStarted = interaction({
      organisationId: "organisation-from-another-session",
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
      title: "Private foreign start sentinel",
    });
    const validStarted = interaction({
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const onInteractionChange = vi.fn();
    installApi(initialInteraction, {
      startResponses: [invalidStarted, validStarted],
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
        onInteractionChange={onInteractionChange}
      />,
    );

    const liveNotes = await screen.findByLabelText("Private live notes");
    await waitFor(() => expect(liveNotes).toBeEnabled());
    fireEvent.change(liveNotes, {
      target: { value: "Keep this private start note mounted." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start interaction" }));

    expect(
      await screen.findByText(
        "The interaction response did not match this conversation. Try again.",
      ),
    ).toBeVisible();
    expect(liveNotes).toHaveValue("Keep this private start note mounted.");
    expect(
      screen.getByRole("button", { name: "Start interaction" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Private foreign start sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Interaction started\./i),
    ).not.toBeInTheDocument();
    expect(onInteractionChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Start interaction" }));

    expect(
      await screen.findByRole("heading", {
        name: "How should Companion help?",
      }),
    ).toBeVisible();
    expect(liveNotes).toHaveValue("Keep this private start note mounted.");
    expect(onInteractionChange).toHaveBeenCalledTimes(1);
    expect(onInteractionChange).toHaveBeenCalledWith(validStarted);
  });

  it("preserves verified notes and skips refresh after an invalid completion", async () => {
    const initialInteraction = interaction({
      lifecycleStatus: "in_progress",
      actualStartAt: "2026-08-15T02:00:00Z",
    });
    const invalidCompleted = interaction({
      id: "interaction-from-another-tab",
      lifecycleStatus: "completed",
      actualStartAt: "2026-08-15T02:00:00Z",
      actualEndAt: "2026-08-15T03:00:00Z",
      title: "Private foreign completion sentinel",
    });
    const validCompleted = interaction({
      lifecycleStatus: "completed",
      actualStartAt: "2026-08-15T02:00:00Z",
      actualEndAt: "2026-08-15T03:00:00Z",
    });
    const onInteractionChange = vi.fn();
    const fetchMock = installApi(initialInteraction, {
      aiCompanionEnabled: false,
      completeResponses: [invalidCompleted, validCompleted],
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
        onInteractionChange={onInteractionChange}
        embedded
      />,
    );

    const liveNotes = await screen.findByLabelText("Private live notes");
    await waitFor(() => expect(liveNotes).toBeEnabled());
    fireEvent.change(liveNotes, {
      target: { value: "Keep this private completion note mounted." },
    });
    const end = await screen.findByRole("button", {
      name: "Save notes and end interaction",
    });
    fireEvent.click(end);

    expect(
      await screen.findByText(
        "The interaction response did not match this conversation. Try again.",
      ),
    ).toBeVisible();
    expect(liveNotes).toHaveValue("Keep this private completion note mounted.");
    expect(
      screen.getByRole("button", { name: "End interaction" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Private foreign completion sentinel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Interaction completed\./i),
    ).not.toBeInTheDocument();
    expect(onInteractionChange).not.toHaveBeenCalled();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/beta/capabilities"),
      ),
    ).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "End interaction" }));

    expect(
      await screen.findByRole("heading", { name: "Conversation ended" }),
    ).toBeVisible();
    expect(onInteractionChange).toHaveBeenCalledTimes(1);
    expect(onInteractionChange).toHaveBeenCalledWith(validCompleted);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          String(input).endsWith("/beta/capabilities"),
        ),
      ).toHaveLength(2),
    );
  });

  it("synchronously redacts the prior session when verified identity changes", async () => {
    const initialInteraction = interaction({
      title: "Private prior identity sentinel",
    });
    installApi(initialInteraction);

    const { rerender } = render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Private prior identity sentinel",
      }),
    ).toBeVisible();

    verifiedOrganisation.state.status = "loading";
    verifiedOrganisation.state.organisationId = null;
    verifiedOrganisation.state.userId = null;
    verifiedOrganisation.state.identityKey = "session-2";
    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    expect(
      screen.queryByText("Private prior identity sentinel"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Verifying access to notes & capture…",
    );

    verifiedOrganisation.state.status = "unavailable";
    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );
    expect(
      screen.queryByText("Private prior identity sentinel"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(verifiedOrganisation.state.reload).toHaveBeenCalledTimes(1);

    verifiedOrganisation.state.status = "available";
    verifiedOrganisation.state.organisationId = "organisation-2";
    verifiedOrganisation.state.userId = "user-2";
    verifiedOrganisation.state.identityKey = "organisation-2:user-2";
    rerender(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    expect(
      screen.queryByText("Private prior identity sentinel"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(
        "The interaction response did not match this conversation. Try again.",
      ),
    ).toBeVisible();
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
        "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
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

  it("keeps frozen live state readable without offering reconciliation on a cancelled conversation", async () => {
    const initialInteraction = interaction({ lifecycleStatus: "cancelled" });
    installApi(initialInteraction, {
      liveInteractionIntelligenceEnabled: true,
      captureResponse: (url) =>
        url.endsWith("/live-intelligence")
          ? jsonResponse({
              interactionId: initialInteraction.id,
              organisationId: initialInteraction.organisationId,
              availability: "available",
              state: "completed",
              safeMessage: "Live Intelligence is stopped and frozen.",
              sourceKind: "progressive_transcript",
              sessionId: "live-session-1",
              signals: [],
              objectives: [],
              openQuestions: [],
              reconciliation: null,
              generatedAt: null,
              updatedAt: "2026-08-15T02:05:00Z",
              nextPollSeconds: 15,
            })
          : undefined,
    });
    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    expect(
      await screen.findByText("Live Intelligence is stopped and frozen."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Compare with final intelligence" }),
    ).not.toBeInTheDocument();
  });

  it("rejects a mixed marker list and can recover without losing typed private notes", async () => {
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
      "passive",
    );
    const initialInteraction = interaction({ lifecycleStatus: "in_progress" });
    let reads = 0;
    installApi(initialInteraction, {
      captureResponse: (url, method) => {
        if (!url.endsWith("/companion/markers") || method !== "GET") return;
        reads += 1;
        return jsonResponse(
          reads === 1
            ? [
                priorMarker,
                {
                  ...priorMarker,
                  id: "marker-foreign",
                  interactionId: "foreign",
                  markerType: "risk",
                },
              ]
            : [priorMarker],
        );
      },
    });
    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    const notes = await screen.findByLabelText("Private live notes");
    await waitFor(() => expect(notes).toBeEnabled());
    fireEvent.change(notes, {
      target: { value: "Keep the handover private." },
    });
    expect(
      await screen.findByText(/Conversation markers could not be loaded/),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Remove Decision marker" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove Risk marker" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Refresh markers" }));
    expect(
      await screen.findByRole("button", { name: "Remove Decision marker" }),
    ).toBeEnabled();
    expect(
      screen.queryByText(/Conversation markers could not be loaded/),
    ).not.toBeInTheDocument();
    expect(notes).toBe(screen.getByLabelText("Private live notes"));
    expect(notes).toHaveValue("Keep the handover private.");
  });

  it("retains verified markers until an uncertain create or delete is reconciled", async () => {
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
      "passive",
    );
    const initialInteraction = interaction({ lifecycleStatus: "in_progress" });
    const savedMarker: InteractionMarker = {
      ...priorMarker,
      id: "marker-new",
      createdByUserId: "user-1",
      markerType: "important_moment",
    };
    let stored = [priorMarker];
    installApi(initialInteraction, {
      captureResponse: (url, method) => {
        if (url.endsWith("/companion/markers") && method === "GET")
          return jsonResponse(stored);
        if (url.endsWith("/companion/markers") && method === "POST") {
          stored = [...stored, savedMarker];
          return jsonResponse(
            { ...savedMarker, createdByUserId: "wrong-user" },
            201,
          );
        }
        if (
          url.endsWith("/companion/markers/marker-prior") &&
          method === "DELETE"
        ) {
          stored = stored.filter(({ id }) => id !== priorMarker.id);
          return jsonResponse({ id: savedMarker.id, deleted: true });
        }
      },
    });
    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Add marker" }));
    fireEvent.click(screen.getByRole("button", { name: "Important" }));
    const warning = /The marker change could not be confirmed/;
    expect(await screen.findByText(warning)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Remove Decision marker" }),
    ).toBeDisabled();
    expect(
      screen.queryByText("Important Moment marked."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove Important Moment marker" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh markers" }));
    expect(
      await screen.findByRole("button", {
        name: "Remove Important Moment marker",
      }),
    ).toBeEnabled();
    expect(screen.queryByText(warning)).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Remove Decision marker" }),
    );
    expect(await screen.findByText(warning)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Remove Decision marker" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Remove Important Moment marker" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Refresh markers" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Remove Decision marker" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Remove Important Moment marker" }),
    ).toBeEnabled();
  });

  it("keeps the verified capture summary when completion returns mixed or malformed lists", async () => {
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
      "passive",
    );
    const initialInteraction = interaction({ lifecycleStatus: "in_progress" });
    let completed = false;
    installApi(initialInteraction, {
      captureResponse: (url, method) => {
        if (url.endsWith("/complete") && method === "POST") completed = true;
        if (url.endsWith("/companion/markers"))
          return jsonResponse(
            completed
              ? [
                  priorMarker,
                  {
                    ...priorMarker,
                    id: "wrong-marker",
                    interactionId: "other",
                  },
                ]
              : [priorMarker],
          );
        if (url.endsWith("/recordings"))
          return jsonResponse(
            completed
              ? [
                  { ...priorRecording, durationSeconds: 180 },
                  {
                    ...priorRecording,
                    id: "wrong-recording",
                    interactionId: "other",
                  },
                ]
              : [priorRecording],
          );
        if (url.endsWith("/visual-evidence"))
          return jsonResponse(
            completed
              ? [
                  priorPhoto,
                  {
                    ...priorPhoto,
                    id: "wrong-photo",
                    captureSessionId: "wrong-photo",
                    candidates: null,
                  },
                ]
              : [priorPhoto],
          );
      },
    });
    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={initialInteraction}
      />,
    );

    expect(
      await screen.findByRole("button", { name: "Remove Decision marker" }),
    ).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "End interaction" }));
    expect(
      await screen.findByText(/Previous recording details could not be loaded/),
    ).toBeVisible();
    expect(
      screen.getByText(/Previous visual evidence could not be loaded/),
    ).toBeVisible();
    expect(
      screen.getByText(/Conversation markers could not be loaded/),
    ).toBeVisible();
    expect(
      screen.getByText("Recording", { selector: "dt" }).nextElementSibling,
    ).toHaveTextContent("1:00");
    expect(
      screen.getByText("Photos", { selector: "dt" }).nextElementSibling,
    ).toHaveTextContent("1");
    expect(
      screen.getByText("Markers", { selector: "dt" }).nextElementSibling,
    ).toHaveTextContent("1");
  });

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
        "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
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
          interactionId: "interaction-1",
          organisationId: "organisation-1",
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

  it("announces and retries an initial private-workspace load failure", async () => {
    const fetchMock = installApi(interaction(), {
      personalWorkspaceLoadResponses: [
        jsonResponse(
          {
            code: "private_workspace_unavailable",
            message: "Internal routing details must not be exposed.",
          },
          503,
        ),
        jsonResponse(emptyWorkspace()),
      ],
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={interaction()}
        embedded
      />,
    );

    const notes = await screen.findByLabelText("Private live notes");
    const recovery = await screen.findByRole("alert", {
      name: "Private notes are temporarily unavailable",
    });
    expect(notes).toBeDisabled();
    expect(recovery).toHaveTextContent(
      "Try again to load this private workspace before entering or saving notes.",
    );
    expect(
      screen.queryByText("Internal routing details must not be exposed."),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(notes).toBeEnabled());
    expect(
      screen.queryByRole("alert", {
        name: "Private notes are temporarily unavailable",
      }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(
        ([input, init]) =>
          String(input).endsWith("/personal-workspace") &&
          (init?.method ?? "GET") === "GET",
      ),
    ).toHaveLength(2);
  });

  it("keeps verified local notes mounted when a save response has foreign identity", async () => {
    installApi(interaction(), {
      personalWorkspaceSaveResponse: Promise.resolve(
        jsonResponse({
          ...emptyWorkspace(),
          exists: true,
          organisationId: "foreign-organisation",
          lockVersion: 1,
          liveNotes: "Foreign private note must not be displayed.",
          updatedAt: "2026-08-15T03:00:00Z",
        }),
      ),
    });

    render(
      <FaceToFaceCompanion
        interactionId="interaction-1"
        initialInteraction={interaction()}
        embedded
      />,
    );

    const notes = await screen.findByLabelText("Private live notes");
    await waitFor(() => expect(notes).toBeEnabled());
    fireEvent.change(notes, {
      target: { value: "Keep this verified local note visible." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save private notes" }));

    expect(
      await screen.findByText(
        "Private notes could not be saved. Your local text is still visible.",
      ),
    ).toBeVisible();
    expect(notes).toHaveValue("Keep this verified local note visible.");
    expect(
      screen.queryByDisplayValue("Foreign private note must not be displayed."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("alert", {
        name: "Private notes are temporarily unavailable",
      }),
    ).not.toBeInTheDocument();
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

  it("holds completion on an uncertain recorder update, including while a note save is pending", async () => {
    recorderStub.enabled = true;
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
      "recording",
    );
    const save = deferred<Response>();
    const fetchMock = installApi(
      interaction({ lifecycleStatus: "in_progress" }),
      {
        personalWorkspaceSaveResponse: save.promise,
      },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);
    const start = await screen.findByRole("button", {
      name: "Start recording",
    });
    const foreignActivity: RecordingActivity = {
      state: "ready",
      active: false,
      blocksInteractionCompletion: false,
      elapsedSeconds: 0,
      recording: { ...priorRecording, interactionId: "foreign-conversation" },
    };
    act(() => recorderStub.activity?.(foreignActivity));
    expect(
      screen.getByRole("button", { name: "End interaction" }),
    ).toBeDisabled();
    act(() => recorderStub.activity?.({ ...foreignActivity, recording: null }));
    expect(
      screen.getByRole("button", { name: "End interaction" }),
    ).toBeEnabled();

    const noteText = "Hand over the release checklist.";
    const notes = screen.getByLabelText("Private live notes");
    await waitFor(() => expect(notes).toBeEnabled());
    fireEvent.change(notes, { target: { value: noteText } });
    fireEvent.click(
      screen.getByRole("button", { name: "Save notes and end interaction" }),
    );
    expect(start).toBeDisabled();
    act(() => recorderStub.activity?.(foreignActivity));
    await act(async () =>
      save.resolve(
        jsonResponse({
          ...emptyWorkspace(),
          exists: true,
          lockVersion: 1,
          liveNotes: noteText,
          enhancedNotes: "",
          followUpDraft: "",
          updatedAt: "2026-08-15T03:00:00Z",
        }),
      ),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /before ending the interaction/,
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/complete"),
      ),
    ).toBe(false);
    expect(notes).toHaveValue(noteText);
  });

  it("recovers an unfinished recording in a passive tab without losing private notes", async () => {
    recorderStub.enabled = true;
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-1",
      "passive",
    );
    const fetchMock = installApi(
      interaction({ lifecycleStatus: "in_progress" }),
      {
        captureResponse: (url) =>
          url.endsWith("/recordings")
            ? jsonResponse([interruptedRecording])
            : undefined,
      },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);

    expect(
      await screen.findByRole("button", { name: "Start recording" }),
    ).toBeDisabled();
    const notes = screen.getByLabelText("Private live notes");
    const noteText = "Follow up about the pilot timeline.";
    await waitFor(() => expect(notes).toBeEnabled());
    fireEvent.change(notes, { target: { value: noteText } });
    const end = screen.getByRole("button", {
      name: "Save notes and end interaction",
    });
    expect(end).toBeDisabled();

    act(() =>
      recorderStub.resolve?.({
        ...priorRecording,
        captureSessionId: "foreign-capture",
      }),
    );
    expect(end).toBeDisabled();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/complete"),
      ),
    ).toBe(false);

    act(() =>
      recorderStub.activity?.({
        state: "uploading",
        active: true,
        blocksInteractionCompletion: true,
        elapsedSeconds: 60,
        recording: interruptedRecording,
      }),
    );
    act(() => recorderStub.resolve?.(priorRecording));
    expect(end).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Start recording" }),
    ).toBeVisible();
    act(() =>
      recorderStub.activity?.({
        state: "processing",
        active: false,
        blocksInteractionCompletion: false,
        elapsedSeconds: 60,
        recording: priorRecording,
      }),
    );
    expect(end).toBeEnabled();
    expect(notes).toHaveValue(noteText);
    expect(
      screen.getByRole("heading", { name: "No recording or listening" }),
    ).toBeVisible();
    fireEvent.click(end);
    expect(
      await screen.findByRole("heading", {
        name: "Fill the gaps while they are fresh",
      }),
    ).toBeVisible();
  });

  it("refreshes recording recovery after another tab prevents completion and the first lookup fails", async () => {
    recorderStub.enabled = true;
    let readingCount = 0;
    let blockedOnce = false;
    const fetchMock = installApi(
      interaction({ lifecycleStatus: "in_progress" }),
      {
        captureResponse: (url, method) => {
          if (url.endsWith("/recordings")) {
            readingCount += 1;
            if (readingCount === 1) return jsonResponse([]);
            if (readingCount === 2) return jsonResponse({ items: [] });
            return jsonResponse([interruptedRecording]);
          }
          if (url.endsWith("/complete") && method === "POST" && !blockedOnce) {
            blockedOnce = true;
            return jsonResponse(
              {
                code: "live_recording_in_progress",
                message: "A recording is in progress.",
              },
              409,
            );
          }
          return undefined;
        },
      },
    );
    render(<FaceToFaceCompanion interactionId="interaction-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Continue without recording" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "End interaction" }));

    const retry = await screen.findByRole("button", {
      name: "Refresh recording status",
    });
    fireEvent.click(retry);
    expect(
      await screen.findByRole("button", { name: "Start recording" }),
    ).toBeDisabled();
    const end = screen.getByRole("button", { name: "End interaction" });
    expect(end).toBeDisabled();

    act(() => recorderStub.verifyList?.([]));
    expect(end).toBeEnabled();
    fireEvent.click(end);
    expect(
      await screen.findByRole("heading", {
        name: "Fill the gaps while they are fresh",
      }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/complete"),
      ),
    ).toHaveLength(2);
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

    expect(liveNotes).toBeEnabled();
    fireEvent.change(liveNotes, {
      target: { value: "A newer note typed before the save finished." },
    });
    await act(async () => {
      resolveSave(
        jsonResponse({
          exists: true,
          interactionId: "interaction-1",
          organisationId: "organisation-1",
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

  it.each(["failed", "mismatched"] as const)(
    "protects private notes during completion and restores editing after a %s response",
    async (outcome) => {
      const active = interaction({
        lifecycleStatus: "in_progress",
        actualStartAt: "2026-08-15T02:00:00Z",
      });
      const pendingCompletion = deferred<Response>();
      const fetchMock = installApi(active, {
        captureResponse: (url, method) =>
          url.endsWith("/complete") && method === "POST"
            ? pendingCompletion.promise
            : undefined,
      });
      render(<FaceToFaceCompanion interactionId="interaction-1" />);

      fireEvent.click(
        await screen.findByRole("button", {
          name: "Continue without recording",
        }),
      );
      const liveNotes = screen.getByLabelText("Private live notes");
      const saveNotes = screen.getByRole("button", {
        name: "Save private notes",
      });
      await waitFor(() => expect(liveNotes).toBeEnabled());
      fireEvent.change(liveNotes, {
        target: { value: "Keep the review window in the follow-up." },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Save notes and end interaction" }),
      );
      await waitFor(() =>
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining("/complete"),
          expect.objectContaining({ method: "POST" }),
        ),
      );

      expect(liveNotes).toBeDisabled();
      expect(saveNotes).toBeDisabled();
      expect(liveNotes).toHaveValue("Keep the review window in the follow-up.");
      expect(screen.getByText("Ending the conversation…")).toBeVisible();

      await act(async () => {
        pendingCompletion.resolve(
          outcome === "failed"
            ? jsonResponse(
                {
                  code: "completion_unavailable",
                  message: "This conversation could not be ended.",
                },
                422,
              )
            : jsonResponse({
                ...active,
                organisationId: "other-organisation",
                lifecycleStatus: "completed",
                actualEndAt: "2026-08-15T03:00:00Z",
              }),
        );
      });

      expect(await screen.findByRole("alert")).toBeVisible();
      expect(liveNotes).toBeEnabled();
      expect(saveNotes).toBeEnabled();
      expect(liveNotes).toHaveValue("Keep the review window in the follow-up.");
      fireEvent.change(liveNotes, {
        target: { value: "Updated after the completion attempt." },
      });
      expect(liveNotes).toHaveValue("Updated after the completion attempt.");
      expect(
        screen.getByRole("button", { name: "Save notes and end interaction" }),
      ).toBeEnabled();
    },
  );

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
        return Promise.resolve(jsonResponse(emptyWorkspaceForUrl(url)));
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
        return Promise.resolve(jsonResponse(emptyWorkspaceForUrl(url)));
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
        return Promise.resolve(jsonResponse(emptyWorkspaceForUrl(url)));
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
        return Promise.resolve(jsonResponse(emptyWorkspaceForUrl(url)));
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
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-a",
      "passive",
    );
    window.sessionStorage.setItem(
      "revenueos:companion:capture-choice:organisation-1:user-1:interaction-b",
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
