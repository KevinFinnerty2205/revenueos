import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
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

function privateWorkspaceController() {
  let currentValues: WorkspaceValues = {
    liveNotes: "",
    enhancedNotes: "",
    followUpDraft: "",
    followUpReviewed: false,
  };
  const setValues = vi.fn(
    (
      update: WorkspaceValues | ((current: WorkspaceValues) => WorkspaceValues),
    ) => {
      currentValues =
        typeof update === "function" ? update(currentValues) : update;
    },
  );
  const controller = {
    workspace: {
      exists: true,
      interactionId: "interaction-1",
      organisationId: "organisation-1",
      ownerUserId: "user-1",
      lockVersion: 2,
      liveNotes: null,
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
    values: currentValues,
    setValues,
    loading: false,
    saveState: "idle" as const,
    error: null,
    generationActionState: "idle" as const,
    generationError: null,
    conflictRecovery: {
      state: "idle" as const,
      latestWorkspace: null,
      latestValues: null,
      submittedValues: null,
      localValuesAtSubmission: null,
      submittedFields: {
        liveNotes: false,
        enhancedNotes: false,
        followUpDraft: false,
        followUpReviewed: false,
      },
      importFromBrowser: false,
      error: null,
    },
    dirtyFields: {
      liveNotes: false,
      enhancedNotes: false,
      followUpDraft: false,
      followUpReviewed: false,
    },
    isDirty: false,
    save: vi.fn(async () => true),
    loadLatestConflict: vi.fn(async () => false),
    useLatestConflict: vi.fn(() => false),
    saveReviewedConflict: vi.fn(async () => false),
    retryGeneration: vi.fn(async () => false),
    applyGeneratedVersion: vi.fn(async () => false),
    refresh: vi.fn(async () => undefined),
    reload: vi.fn(async () => undefined),
  } satisfies ConversationWorkspaceController;
  return {
    controller,
    setValues,
    currentValues: () => currentValues,
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

  it("rejects a start response that belongs to another interaction", async () => {
    const foreignQuestion = "Private prompt from another conversation";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response(
            session({
              id: "session-foreign",
              interactionId: "interaction-foreign",
              currentQuestion: {
                status: "ask",
                question: foreignQuestion,
                reason: "Private foreign context.",
                target: "other",
                priority: "high",
              },
            }),
            201,
          ),
        ),
      ),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );

    const start = await screen.findByRole("button", {
      name: "Start personal notes",
    });
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /safely stopped/i,
      }),
    );
    fireEvent.click(start);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(screen.queryByText(foreignQuestion)).not.toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        "revenueos:post-interaction-capture:interaction-1",
      ),
    ).toBeNull();
    expect(start).toBeEnabled();
  });

  it("keeps the saved session key private when restore returns another session", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    const foreignQuestion = "Question from the wrong private session";
    const retry = deferred<Response>();
    const foreignResponse = () =>
      response(
        session({
          id: "session-foreign",
          currentQuestion: {
            status: "ask",
            question: foreignQuestion,
            reason: "Private foreign context.",
            target: "other",
            priority: "high",
          },
        }),
      );
    window.localStorage.setItem(key, "session-expected");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(foreignResponse())
        .mockReturnValueOnce(retry.promise),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="online_meeting"
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(screen.queryByText(foreignQuestion)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Your in-progress capture was restored."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start personal notes" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start AI Debrief" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try restore again" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Restoring post-interaction capture…",
    );
    await act(async () => {
      retry.resolve(foreignResponse());
      await retry.promise;
    });
    expect(
      await screen.findByRole("button", { name: "Try restore again" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Start personal notes" }),
    ).not.toBeInTheDocument();
    expect(window.localStorage.getItem(key)).toBe("session-expected");
  });

  it("preserves an answer when its response swaps to another session", async () => {
    const answer = "Keep this private answer in the editor.";
    const foreignAnswer = "Foreign answer must never be shown.";
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/response")) {
        return Promise.resolve(
          response(
            session({
              id: "session-foreign",
              questionCount: 1,
              turns: [
                {
                  id: "turn-foreign",
                  turnNumber: 1,
                  question: session().currentQuestion!,
                  answerText: foreignAnswer,
                  inputMode: "text",
                  createdAt: "2026-08-14T01:01:00Z",
                },
              ],
            }),
          ),
        );
      }
      expect(init?.method).toBe("POST");
      return Promise.resolve(response(session(), 201));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="phone_call"
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
    const editor = await screen.findByLabelText("Your answer");
    fireEvent.change(editor, { target: { value: answer } });
    fireEvent.click(screen.getByRole("button", { name: "Save answer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(editor).toHaveValue(answer);
    expect(screen.queryByText(foreignAnswer)).not.toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        "revenueos:post-interaction-capture:interaction-1",
      ),
    ).toBe("session-1");
  });

  it("rejects a voice response that swaps to another private session", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    const foreignAnswer = "Foreign voice transcript must never be shown.";
    const trackStop = vi.fn();
    const stream = {
      getTracks: () => [{ stop: trackStop }],
    } as unknown as MediaStream;

    class FakeBlob {
      readonly size = 1;
      readonly type: string;

      constructor(_parts?: BlobPart[], options?: BlobPropertyBag) {
        this.type = options?.type ?? "";
      }

      arrayBuffer() {
        return Promise.resolve(new Uint8Array([1]).buffer);
      }
    }

    class FakeMediaRecorder {
      static isTypeSupported() {
        return true;
      }

      state = "inactive";
      private readonly listeners = new Map<string, EventListener[]>();

      addEventListener(
        type: string,
        listener: EventListenerOrEventListenerObject,
      ) {
        const callback: EventListener =
          typeof listener === "function"
            ? listener
            : (event) => listener.handleEvent(event);
        this.listeners.set(type, [
          ...(this.listeners.get(type) ?? []),
          callback,
        ]);
      }

      start() {
        this.state = "recording";
      }

      pause() {
        this.state = "paused";
      }

      resume() {
        this.state = "recording";
      }

      stop() {
        this.state = "inactive";
        for (const listener of this.listeners.get("dataavailable") ?? []) {
          listener({
            data: new Blob(["voice"], { type: "audio/webm" }),
          } as BlobEvent);
        }
        for (const listener of this.listeners.get("stop") ?? []) {
          listener(new Event("stop"));
        }
      }
    }

    vi.stubGlobal("Blob", FakeBlob);
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn(() => Promise.resolve(stream)),
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/voice-response")
          ? Promise.resolve(
              response(
                session({
                  id: "session-foreign",
                  captureType: "voice_journal",
                  questionCount: 1,
                  turns: [
                    {
                      id: "turn-foreign",
                      turnNumber: 1,
                      question: session().currentQuestion!,
                      answerText: foreignAnswer,
                      inputMode: "voice",
                      createdAt: "2026-08-14T01:01:00Z",
                    },
                  ],
                }),
              ),
            )
          : Promise.resolve(
              response(session({ captureType: "voice_journal" }), 201),
            ),
      ),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );

    fireEvent.click(await screen.findByText("Other debrief options"));
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /safely stopped/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /Voice Journal records only my post-interaction report/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Start Voice Journal" }),
    );
    expect(await screen.findByText("How did it go?")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start microphone" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Stop and transcribe" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(screen.queryByText(foreignAnswer)).not.toBeInTheDocument();
    expect(screen.getByText("How did it go?")).toBeVisible();
    expect(
      screen.queryByText(
        "Voice answer transcribed and saved. The audio was not retained.",
      ),
    ).not.toBeInTheDocument();
    expect(window.localStorage.getItem(key)).toBe("session-1");
    expect(trackStop).toHaveBeenCalled();
  });

  it("keeps the current session collecting when finish returns another session", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    const collecting = session({ canFinish: true });
    window.localStorage.setItem(key, collecting.id);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/finish")
          ? Promise.resolve(
              response(
                session({
                  id: "session-foreign",
                  lifecycleStatus: "review",
                  currentQuestion: null,
                }),
              ),
            )
          : Promise.resolve(response(collecting)),
      ),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="online_meeting"
      />,
    );

    expect(await screen.findByText("How did it go?")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Finish and review" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(screen.getByText("How did it go?")).toBeVisible();
    expect(
      screen.queryByRole("heading", {
        name: "Review before updating intelligence",
      }),
    ).not.toBeInTheDocument();
    expect(window.localStorage.getItem(key)).toBe("session-1");
  });

  it("rejects a review response that swaps the private session", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    const candidate = {
      id: "candidate-1",
      evidenceCategory: "decision" as const,
      statement: "The customer selected the staged rollout.",
      originalStatement: "The customer selected the staged rollout.",
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
    const foreignStatement = "Foreign reviewed evidence must stay private.";
    const reviewing = session({
      lifecycleStatus: "review",
      currentQuestion: null,
      candidates: [candidate],
    });
    window.localStorage.setItem(key, reviewing.id);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/review")
          ? Promise.resolve(
              response({
                ...session({
                  id: "session-foreign",
                  lifecycleStatus: "completed",
                  currentQuestion: null,
                  completedAt: "2026-08-14T01:05:00Z",
                  candidates: [
                    {
                      ...candidate,
                      id: "candidate-foreign",
                      statement: foreignStatement,
                      originalStatement: foreignStatement,
                      sourceCaptureSessionId: "session-foreign",
                    },
                  ],
                }),
                acceptedCount: 1,
                rejectedCount: 0,
                interactionUpdated: true,
                revenueBrainUpdated: true,
              }),
            )
          : Promise.resolve(response(reviewing)),
      ),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="online_meeting"
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Review before updating intelligence",
      }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Finish review and update intelligence",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(
      screen.getByRole("heading", {
        name: "Review before updating intelligence",
      }),
    ).toBeVisible();
    expect(screen.queryByText(foreignStatement)).not.toBeInTheDocument();
    expect(window.localStorage.getItem(key)).toBe("session-1");
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

  it("preserves a saved session and withholds a fresh start while restore is unavailable", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    window.localStorage.setItem(key, "session-1");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          {
            code: "debrief_unavailable",
            message: "Debrief restore is temporarily unavailable.",
            requestId: "request-restore-1",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(response(session()));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="executive_lunch"
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your capture could not be restored. Any saved capture remains preserved.",
    );
    expect(window.localStorage.getItem(key)).toBe("session-1");
    expect(
      screen.queryByRole("button", { name: "Start personal notes" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try restore again" }));

    expect(
      await screen.findByText("Your in-progress capture was restored."),
    ).toBeVisible();
    expect(window.localStorage.getItem(key)).toBe("session-1");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("falls back to the latest debrief after an explicitly stale saved session", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    window.localStorage.setItem(key, "stale-session");
    const latest = session({ id: "latest-session" });
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      String(input).endsWith("/debrief/stale-session")
        ? Promise.resolve(
            response(
              {
                code: "debrief_not_found",
                message: "The requested debrief session was not found.",
                requestId: "request-restore-2",
              },
              404,
            ),
          )
        : Promise.resolve(response(latest)),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="executive_lunch"
        restoreLatest
      />,
    );

    expect(
      await screen.findByText("Your in-progress capture was restored."),
    ).toBeVisible();
    expect(window.localStorage.getItem(key)).toBe("latest-session");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/debrief/stale-session"),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/debrief/latest"),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("blocks a foreign latest fallback after a saved session is confirmed missing", async () => {
    const key = "revenueos:post-interaction-capture:interaction-1";
    const foreignQuestion = "Private question from another conversation";
    window.localStorage.setItem(key, "stale-session");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/debrief/stale-session")
          ? Promise.resolve(
              response(
                {
                  code: "debrief_not_found",
                  message: "The requested debrief session was not found.",
                  requestId: "request-restore-foreign",
                },
                404,
              ),
            )
          : Promise.resolve(
              response(
                session({
                  id: "foreign-latest-session",
                  interactionId: "interaction-foreign",
                  currentQuestion: {
                    status: "ask",
                    question: foreignQuestion,
                    reason: "Private foreign context.",
                    target: "other",
                    priority: "high",
                  },
                }),
              ),
            ),
      ),
    );

    render(
      <PostInteractionCapture
        interactionId="interaction-1"
        interactionType="executive_lunch"
        restoreLatest
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The private capture response did not match this conversation. Try again.",
    );
    expect(screen.queryByText(foreignQuestion)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start personal notes" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start AI Debrief" }),
    ).not.toBeInTheDocument();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("ignores an old interaction restore failure after navigation", async () => {
    const keyA = "revenueos:post-interaction-capture:interaction-a";
    const keyB = "revenueos:post-interaction-capture:interaction-b";
    window.localStorage.setItem(keyA, "session-a");
    window.localStorage.setItem(keyB, "session-b");
    const interactionARestore = deferred<Response>();
    const restoredB = session({
      id: "session-b",
      interactionId: "interaction-b",
      currentQuestion: {
        status: "ask",
        question: "What changed for interaction B?",
        reason: "Keep B private and current.",
        target: "other",
        priority: "high",
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      String(input).includes("interaction-a")
        ? interactionARestore.promise
        : Promise.resolve(response(restoredB)),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <PostInteractionCapture
        interactionId="interaction-a"
        interactionType="executive_lunch"
      />,
    );
    rerender(
      <PostInteractionCapture
        interactionId="interaction-b"
        interactionType="executive_lunch"
      />,
    );

    expect(
      await screen.findByText("What changed for interaction B?"),
    ).toBeVisible();
    await act(async () =>
      interactionARestore.resolve(
        response(
          {
            code: "debrief_unavailable",
            message: "Old restore failed.",
            requestId: "request-restore-a",
          },
          503,
        ),
      ),
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("What changed for interaction B?")).toBeVisible();
    expect(window.localStorage.getItem(keyA)).toBe("session-a");
    expect(window.localStorage.getItem(keyB)).toBe("session-b");
  });

  it("ignores an old interaction not-found restore after navigation", async () => {
    const keyA = "revenueos:post-interaction-capture:interaction-a";
    const keyB = "revenueos:post-interaction-capture:interaction-b";
    window.localStorage.setItem(keyA, "session-a");
    window.localStorage.setItem(keyB, "session-b");
    const interactionARestore = deferred<Response>();
    const restoredB = session({
      id: "session-b",
      interactionId: "interaction-b",
      currentQuestion: {
        status: "ask",
        question: "What changed for interaction B?",
        reason: "Keep B private and current.",
        target: "other",
        priority: "high",
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("interaction-a/debrief/session-a")) {
        return interactionARestore.promise;
      }
      if (url.includes("interaction-a/debrief/latest")) {
        return Promise.resolve(
          response(
            session({
              id: "obsolete-latest-a",
              interactionId: "interaction-a",
            }),
          ),
        );
      }
      return Promise.resolve(response(restoredB));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <PostInteractionCapture
        interactionId="interaction-a"
        interactionType="executive_lunch"
        restoreLatest
      />,
    );
    rerender(
      <PostInteractionCapture
        interactionId="interaction-b"
        interactionType="executive_lunch"
        restoreLatest
      />,
    );

    expect(
      await screen.findByText("What changed for interaction B?"),
    ).toBeVisible();
    await act(async () =>
      interactionARestore.resolve(
        response(
          {
            code: "debrief_not_found",
            message: "The old saved capture was not found.",
            requestId: "request-restore-a-not-found",
          },
          404,
        ),
      ),
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("What changed for interaction B?")).toBeVisible();
    expect(window.localStorage.getItem(keyA)).toBe("session-a");
    expect(window.localStorage.getItem(keyB)).toBe("session-b");
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("interaction-a/debrief/latest"),
      ),
    ).toBe(false);
  });

  it("removes completed debrief seeds before restoring another interaction", async () => {
    const completedSession = (
      interactionId: string,
      statement: string,
    ): DebriefSession =>
      session({
        id: `session-${interactionId}`,
        interactionId,
        lifecycleStatus: "completed",
        currentQuestion: null,
        completedAt: "2026-08-14T01:05:00Z",
        candidates: [
          {
            id: `candidate-${interactionId}`,
            evidenceCategory: "decision",
            statement,
            originalStatement: statement,
            origin: "salesperson_reported",
            sourceLabel: "Reported by you",
            supportClassification: "reported",
            validationState: "verified",
            conflictState: "not_assessed",
            userReviewState: "accepted",
            sourceCaptureSessionId: `session-${interactionId}`,
            evidenceFragmentId: `fragment-${interactionId}`,
            acceptedEvidenceId: `evidence-${interactionId}`,
            entityReference: null,
            explicitlyReportedAt: "2026-08-14T01:05:00Z",
            edited: false,
          },
        ],
      });
    const statementA = "Private A selected the confidential rollout.";
    const statementB = "Private B approved the staged launch.";
    const restoredA = completedSession("interaction-a", statementA);
    const restoredB = completedSession("interaction-b", statementB);
    const interactionBRestore = deferred<Response>();
    const workspaceA = privateWorkspaceController();
    const workspaceB = privateWorkspaceController();
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      String(input).includes("interaction-a")
        ? Promise.resolve(response(restoredA))
        : interactionBRestore.promise,
    );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <PostInteractionCapture
        interactionId="interaction-a"
        interactionType="online_meeting"
        restoreLatest
        workspaceController={workspaceA.controller}
      />,
    );

    expect(await screen.findByText("Debrief complete")).toBeVisible();
    expect(screen.getAllByText(statementA).length).toBeGreaterThan(0);
    await waitFor(() => expect(workspaceA.setValues).toHaveBeenCalled());
    expect(workspaceA.currentValues().enhancedNotes).toContain(statementA);

    rerender(
      <PostInteractionCapture
        interactionId="interaction-b"
        interactionType="online_meeting"
        restoreLatest
        workspaceController={workspaceB.controller}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Restoring post-interaction capture",
    );
    expect(screen.queryByText(statementA)).not.toBeInTheDocument();
    expect(workspaceB.setValues).not.toHaveBeenCalled();

    await act(async () => interactionBRestore.resolve(response(restoredB)));
    expect(await screen.findByText("Debrief complete")).toBeVisible();
    expect(screen.getAllByText(statementB).length).toBeGreaterThan(0);
    await waitFor(() => expect(workspaceB.setValues).toHaveBeenCalled());
    expect(workspaceB.currentValues().enhancedNotes).toContain(statementB);
    expect(workspaceB.currentValues().followUpDraft).toContain(statementB);
    expect(JSON.stringify(workspaceB.currentValues())).not.toContain(
      statementA,
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
        interactionId: "interaction-1",
        organisationId: "organisation-1",
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
      conflictRecovery: {
        state: "idle" as const,
        latestWorkspace: null,
        latestValues: null,
        submittedValues: null,
        localValuesAtSubmission: null,
        submittedFields: {
          liveNotes: false,
          enhancedNotes: false,
          followUpDraft: false,
          followUpReviewed: false,
        },
        importFromBrowser: false,
        error: null,
      },
      dirtyFields: {
        liveNotes: false,
        enhancedNotes: true,
        followUpDraft: true,
        followUpReviewed: false,
      },
      isDirty: true,
      save: vi.fn(async () => true),
      loadLatestConflict: vi.fn(async () => false),
      useLatestConflict: vi.fn(() => false),
      saveReviewedConflict: vi.fn(async () => false),
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
