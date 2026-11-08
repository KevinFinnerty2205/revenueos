import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DebriefSession } from "@revenueos/shared";
import { PostInteractionCapture } from "@/components/post-interaction-capture";
import type {
  ConversationWorkspaceController,
  WorkspaceValues,
} from "@/lib/use-conversation-workspace";

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function session(overrides: Partial<DebriefSession> = {}): DebriefSession {
  return {
    id: "session-1",
    interactionId: "interaction-1",
    captureType: "ai_debrief",
    lifecycleStatus: "collecting",
    questionCount: 0,
    maxQuestions: 6,
    currentQuestion: {
      status: "ask",
      question: "How did it go?",
      reason: "Start naturally.",
      target: "other",
      priority: "high",
    },
    canFinish: false,
    finishedEarly: false,
    turns: [],
    candidates: [],
    interactionIntelligenceId: null,
    revenueBrainSnapshotId: null,
    startedAt: "2026-08-14T01:00:00Z",
    updatedAt: "2026-08-14T01:00:00Z",
    completedAt: null,
    ...overrides,
  };
}

describe("PostInteractionCapture", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows one immediate phone-call capture path and discloses alternatives on request", async () => {
    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Write what you noticed on this call",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Start personal notes" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Start AI Debrief" }),
    ).not.toBeVisible();
    fireEvent.click(await screen.findByText("Other debrief options"));
    expect(
      screen.getByRole("heading", { name: "Start AI Debrief" }),
    ).toBeVisible();
    expect(screen.getByText("Add Voice Journal")).toBeVisible();
    expect(screen.getByRole("link", { name: "Add Recording" })).toHaveAttribute(
      "href",
      "#recording",
    );
    expect(
      screen.getByRole("button", { name: "Finish for now" }),
    ).toBeVisible();
    expect(screen.queryByText("Record phone call")).not.toBeInTheDocument();
  });

  it("keeps a typed Voice Journal path when browser recording is unsupported", async () => {
    vi.stubGlobal("MediaRecorder", undefined);
    const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(
        response(
          session({
            captureType: "voice_journal",
            maxQuestions: 2,
          }),
          201,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );

    fireEvent.click(await screen.findByText("Other debrief options"));
    expect(await screen.findByText("Add Voice Journal")).toBeVisible();
    expect(screen.getByText(/browser cannot record audio/i)).toBeVisible();
    const typeJournal = screen.getByRole("button", {
      name: "Type a journal",
    });
    expect(typeJournal).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /safely stopped/i,
      }),
    );
    fireEvent.click(typeJournal);
    expect(await screen.findByText("How did it go?")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/interactions/interaction-1/debrief"),
      expect.objectContaining({ method: "POST" }),
    );
    const requestBody = JSON.parse(
      String((fetchMock.mock.calls[0]?.[1] as RequestInit).body),
    ) as { captureType: string };
    expect(requestBody.captureType).toBe("voice_journal");
  });

  it("completes the typed answer and review journey with editable reported evidence", async () => {
    const candidate = {
      id: "candidate-1",
      evidenceCategory: "stakeholder" as const,
      statement: "Jordan joined as the economic buyer.",
      originalStatement: "Jordan joined as the economic buyer.",
      origin: "salesperson_reported" as const,
      sourceLabel: "Reported by you" as const,
      supportClassification: "reported" as const,
      validationState: "unreviewed" as const,
      conflictState: "not_assessed" as const,
      userReviewState: "pending" as const,
      sourceCaptureSessionId: "session-1",
      evidenceFragmentId: "fragment-1",
      acceptedEvidenceId: null,
      entityReference: null,
      explicitlyReportedAt: null,
      edited: false,
    };
    const calls: Array<{ path: string; body: string }> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      calls.push({ path, body: String(init?.body ?? "") });
      if (path.endsWith("/finish")) {
        return Promise.resolve(
          response(
            session({
              lifecycleStatus: "review",
              currentQuestion: null,
              canFinish: false,
              candidates: [candidate],
            }),
          ),
        );
      }
      if (path.endsWith("/review")) {
        return Promise.resolve(
          response({
            ...session({
              lifecycleStatus: "completed",
              currentQuestion: null,
              candidates: [
                {
                  ...candidate,
                  statement: "Jordan is the confirmed economic buyer.",
                  validationState: "verified",
                  userReviewState: "accepted",
                  acceptedEvidenceId: "evidence-2",
                  edited: true,
                },
              ],
              interactionIntelligenceId: "intelligence-1",
              revenueBrainSnapshotId: "brain-1",
              completedAt: "2026-08-14T01:05:00Z",
            }),
            acceptedCount: 1,
            rejectedCount: 0,
            interactionUpdated: true,
            revenueBrainUpdated: true,
          }),
        );
      }
      if (path.endsWith("/response")) {
        return Promise.resolve(
          response(
            session({
              questionCount: 1,
              currentQuestion: {
                status: "complete",
                question: null,
                reason: "The reported evidence is sufficient for review.",
                target: null,
                priority: null,
              },
              canFinish: true,
              turns: [
                {
                  id: "turn-1",
                  turnNumber: 1,
                  question: session().currentQuestion!,
                  answerText: "Jordan joined as the economic buyer.",
                  inputMode: "text",
                  createdAt: "2026-08-14T01:01:00Z",
                },
              ],
            }),
          ),
        );
      }
      return Promise.resolve(response(session(), 201));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="presentation"
      />,
    );
    await screen.findByRole("button", { name: "Start personal notes" });
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /safely stopped/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Start personal notes" }),
    );
    await screen.findByText("How did it go?");
    fireEvent.change(screen.getByLabelText("Your answer"), {
      target: { value: "Jordan joined as the economic buyer." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save answer" }));
    expect(
      await screen.findByText("You have covered the material points."),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Review captured evidence" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Review before updating intelligence",
      }),
    ).toBeVisible();
    expect(screen.getByText("Reported by you")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Evidence statement"), {
      target: { value: "Jordan is the confirmed economic buyer." },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Finish review and update intelligence",
      }),
    );
    expect(await screen.findByText("Debrief complete")).toBeVisible();
    const review = calls.find((call) => call.path.endsWith("/review"));
    expect(review).toBeDefined();
    expect(JSON.parse(review?.body ?? "{}")).toMatchObject({
      decisions: [
        {
          candidateId: "candidate-1",
          decision: "accept",
          statement: "Jordan is the confirmed economic buyer.",
        },
      ],
    });
  });

  it("restores a persisted in-progress session after refresh", async () => {
    window.localStorage.setItem(
      "revenueos:post-interaction-capture:interaction-1",
      "session-1",
    );
    const fetchMock = vi.fn(() => Promise.resolve(response(session())));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="executive_lunch"
      />,
    );

    expect(
      await screen.findByText("Your in-progress capture was restored."),
    ).toBeVisible();
    expect(screen.getByText("How did it go?")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/interactions/interaction-1/debrief/session-1"),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("does not seed debrief defaults over dirty private draft fields", async () => {
    const completed = session({
      lifecycleStatus: "completed",
      currentQuestion: null,
      completedAt: "2026-08-14T01:05:00Z",
      candidates: [
        {
          id: "candidate-1",
          evidenceCategory: "decision",
          statement: "The customer selected the staged rollout.",
          originalStatement: "The customer selected the staged rollout.",
          origin: "salesperson_reported",
          sourceLabel: "Reported by you",
          supportClassification: "reported",
          validationState: "verified",
          conflictState: "not_assessed",
          userReviewState: "accepted",
          sourceCaptureSessionId: "session-1",
          evidenceFragmentId: "fragment-1",
          acceptedEvidenceId: "evidence-1",
          entityReference: null,
          explicitlyReportedAt: "2026-08-14T01:05:00Z",
          edited: false,
        },
      ],
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(completed)));
    let localValues: WorkspaceValues = {
      liveNotes: "Original rough note",
      enhancedNotes: "Keep my unsaved enhanced wording.",
      followUpDraft: "Keep my unsaved follow-up wording.",
      followUpReviewed: false,
    };
    const setValues = vi.fn(
      (
        update:
          WorkspaceValues | ((current: WorkspaceValues) => WorkspaceValues),
      ) => {
        localValues =
          typeof update === "function" ? update(localValues) : update;
      },
    );
    const workspaceController = {
      workspace: {
        exists: true,
        ownerUserId: "user-1",
        lockVersion: 2,
        liveNotes: "Original rough note",
        enhancedNotes: null,
        followUpDraft: null,
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
        updatedAt: "2026-08-14T01:00:00Z",
      },
      values: localValues,
      setValues,
      loading: false,
      saveState: "idle" as const,
      error: null,
      generationActionState: "idle" as const,
      generationError: null,
      dirtyFields: {
        liveNotes: false,
        enhancedNotes: true,
        followUpDraft: true,
        followUpReviewed: false,
      },
      isDirty: true,
      save: vi.fn(async () => true),
      retryGeneration: vi.fn(async () => false),
      applyGeneratedVersion: vi.fn(async () => false),
      refresh: vi.fn(async () => undefined),
      reload: vi.fn(async () => undefined),
    } satisfies ConversationWorkspaceController;

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="online_meeting"
        restoreLatest
        workspaceController={workspaceController}
      />,
    );

    expect(await screen.findByText("Debrief complete")).toBeVisible();
    await waitFor(() => expect(setValues).toHaveBeenCalled());
    expect(localValues.enhancedNotes).toBe("Keep my unsaved enhanced wording.");
    expect(localValues.followUpDraft).toBe(
      "Keep my unsaved follow-up wording.",
    );
  });
});
