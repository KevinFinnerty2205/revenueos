import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { Interaction } from "@revenueos/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InteractionDetail } from "@/components/interaction-detail";
import { PostConversationDraftStatus } from "@/components/conversation-notes-review";

vi.mock("@/components/conversation-memory", () => ({
  ConversationMemory: () => <div>Conversation memory</div>,
}));

vi.mock("@/components/pre-interaction-brief", () => ({
  PreInteractionBrief: () => <div>Preparation brief</div>,
}));

const conversationWorkspaceMock = vi.hoisted(() => ({
  use: vi.fn(),
}));

vi.mock("@/lib/use-conversation-workspace", () => ({
  useConversationWorkspace: conversationWorkspaceMock.use,
}));

vi.mock("@/components/meeting-intelligence-workspace", () => ({
  MeetingIntelligenceWorkspace: ({
    meetingId,
    workspaceRefreshKey = 0,
  }: {
    meetingId: string;
    workspaceRefreshKey?: number;
  }) => (
    <>
      <p>Meeting intelligence for {meetingId}</p>
      <textarea
        aria-label="Visible private follow-up editor"
        readOnly
        value={
          workspaceRefreshKey === 0
            ? "Edited follow-up"
            : "Corrected private follow-up"
        }
      />
    </>
  ),
}));

vi.mock("@/components/online-meeting-capture", () => ({
  OnlineMeetingCapture: ({
    onTranscriptImported,
  }: {
    onTranscriptImported?: (result: {
      interactionId: string;
      meetingId: string;
    }) => void;
  }) => (
    <div>
      Online meeting capture
      <button
        type="button"
        onClick={() =>
          onTranscriptImported?.({
            interactionId: "interaction-foreign",
            meetingId: "meeting-foreign",
          })
        }
      >
        Return foreign transcript
      </button>
    </div>
  ),
}));

function workspaceController(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    workspace: null,
    values: {
      liveNotes: "",
      enhancedNotes: "",
      followUpDraft: "",
      followUpReviewed: false,
    },
    setValues: vi.fn(),
    loading: false,
    saveState: "idle",
    error: null,
    generationActionState: "idle",
    generationError: null,
    conflictRecovery: {
      state: "idle",
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
    save: vi.fn(() => Promise.resolve(true)),
    loadLatestConflict: vi.fn(() => Promise.resolve(false)),
    useLatestConflict: vi.fn(() => false),
    saveReviewedConflict: vi.fn(() => Promise.resolve(false)),
    retryGeneration: vi.fn(() => Promise.resolve(true)),
    applyGeneratedVersion: vi.fn(() => Promise.resolve(false)),
    refresh: vi.fn(() => Promise.resolve()),
    reload: vi.fn(() => Promise.resolve()),
    ...overrides,
  };
}

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolvePromise: ((value: T) => void) | undefined;
  let rejectPromise: ((reason?: unknown) => void) | undefined;
  const promise = new Promise<T>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return {
    promise,
    resolve(value: T) {
      if (!resolvePromise)
        throw new Error("Deferred promise was not initialised.");
      resolvePromise(value);
    },
    reject(reason?: unknown) {
      if (!rejectPromise)
        throw new Error("Deferred promise was not initialised.");
      rejectPromise(reason);
    },
  };
}

const interaction: Interaction = {
  id: "interaction-1",
  organisationId: "organisation-1",
  companyId: null,
  opportunityId: null,
  contactId: null,
  meetingId: "meeting-1",
  interactionType: "online_meeting",
  lifecycleStatus: "planned",
  title: "Acme discovery",
  scheduledStartAt: "2026-08-01T00:00:00Z",
  scheduledEndAt: null,
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "meeting_compatibility",
  callDirection: null,
  callOutcome: null,
  durationSeconds: null,
  captureMethods: [],
  intelligenceState: "not_ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "not_generated",
  briefGeneratedAt: null,
  createdAt: "2026-07-26T00:00:00Z",
  updatedAt: "2026-07-26T00:00:00Z",
};

const generatedWorkspace = {
  exists: true,
  interactionId: "interaction-1",
  organisationId: "organisation-1",
  ownerUserId: "user-1",
  lockVersion: 3,
  liveNotes: "Original live notes",
  enhancedNotes: "Edited enhanced notes",
  followUpDraft: "Edited follow-up",
  followUpReviewed: false,
  generationFingerprint: "a".repeat(64),
  generationState: "ready" as const,
  generationId: "generation-2",
  generationTranscriptVersion: 2,
  generationPersonalNotesState: "current" as const,
  generationFailureCode: null,
  generationRetryAvailable: false,
  generationUpdateAvailable: true,
  generationCompletedAt: "2026-11-01T00:00:00Z",
  importedFromBrowserAt: null,
  updatedAt: "2026-11-01T00:00:00Z",
};

describe("InteractionDetail", () => {
  beforeEach(() => {
    conversationWorkspaceMock.use.mockReturnValue(workspaceController());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    conversationWorkspaceMock.use.mockReset();
  });

  it("completes a planned interaction and keeps Meeting Intelligence available", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/start") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...interaction, lifecycleStatus: "in_progress" }),
        );
      }
      if (path.endsWith("/complete") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            ...interaction,
            lifecycleStatus: "completed",
            actualEndAt: "2026-08-01T01:00:00Z",
          }),
        );
      }
      return Promise.resolve(jsonResponse(interaction));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionDetail interactionId="interaction-1" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );
    expect(
      await screen.findByRole("heading", { name: "Acme discovery" }),
    ).toBeVisible();
    expect(
      screen.getByRole("status", { name: "Conversation lifecycle status" }),
    ).toHaveTextContent("Planned");
    expect(
      screen.getByRole("link", { name: "Prepare and start" }),
    ).toHaveAttribute("href", "/conversations/interaction-1?view=capture");
    fireEvent.click(screen.getByRole("button", { name: "Start meeting" }));
    expect(
      await screen.findByRole("button", { name: "End meeting" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "End meeting" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "End meeting" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("status", { name: "Conversation lifecycle status" }),
    ).toHaveTextContent("Completed");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/interactions/interaction-1/complete"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("keeps the standalone detail failure retryable", async () => {
    let detailAttempts = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/v1/interactions/interaction-1")) {
        detailAttempts += 1;
        if (detailAttempts === 1) {
          return Promise.resolve(
            jsonResponse(
              {
                code: "interaction_not_found",
                message: "Interaction not found.",
                requestId: "request-3",
              },
              404,
            ),
          );
        }
      }
      return Promise.resolve(jsonResponse(interaction));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionDetail interactionId="interaction-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interaction not found.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "Acme discovery" }),
    ).toBeVisible();
    expect(detailAttempts).toBe(2);
  });

  it("keeps the next conversation visible when a late start response settles", async () => {
    const startResponse = deferred<Response>();
    const interactionA: Interaction = {
      ...interaction,
      id: "interaction-a",
      title: "Alpha discovery",
    };
    const interactionB: Interaction = {
      ...interaction,
      id: "interaction-b",
      title: "Bravo discovery",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/interactions/interaction-a/start")) {
        return startResponse.promise;
      }
      if (path.endsWith("/interactions/interaction-a") && !init?.method) {
        return Promise.resolve(jsonResponse(interactionA));
      }
      if (path.endsWith("/interactions/interaction-b") && !init?.method) {
        return Promise.resolve(jsonResponse(interactionB));
      }
      return Promise.resolve(jsonResponse({ featureFlags: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <InteractionDetail interactionId="interaction-a" />,
    );
    await screen.findByRole("heading", { name: "Alpha discovery" });
    fireEvent.click(screen.getByRole("button", { name: "Start meeting" }));
    expect(screen.getByRole("button", { name: "Starting…" })).toBeDisabled();

    rerender(<InteractionDetail interactionId="interaction-b" />);
    expect(
      screen.queryByRole("heading", { name: "Alpha discovery" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );
    await screen.findByRole("heading", { name: "Bravo discovery" });

    await act(async () => {
      startResponse.resolve(
        jsonResponse({
          ...interactionA,
          lifecycleStatus: "in_progress",
        }),
      );
      await Promise.resolve();
    });

    expect(
      screen.getByRole("heading", { name: "Bravo discovery" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Start meeting" })).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each(["success", "failure"] as const)(
    "keeps the next conversation isolated from a late completion %s",
    async (outcome) => {
      const completionResponse = deferred<Response>();
      const interactionA: Interaction = {
        ...interaction,
        id: "interaction-a",
        title: "Alpha active meeting",
        lifecycleStatus: "in_progress",
      };
      const interactionB: Interaction = {
        ...interaction,
        id: "interaction-b",
        title: "Bravo discovery",
      };
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
          const path = String(input);
          if (path.endsWith("/interactions/interaction-a/complete")) {
            return completionResponse.promise;
          }
          if (path.endsWith("/interactions/interaction-a") && !init?.method) {
            return Promise.resolve(jsonResponse(interactionA));
          }
          if (path.endsWith("/interactions/interaction-b") && !init?.method) {
            return Promise.resolve(jsonResponse(interactionB));
          }
          return Promise.resolve(jsonResponse({ featureFlags: {} }));
        }),
      );

      const { rerender } = render(
        <InteractionDetail interactionId="interaction-a" />,
      );
      await screen.findByRole("heading", { name: "Alpha active meeting" });
      fireEvent.click(screen.getByRole("button", { name: "End meeting" }));
      expect(screen.getByRole("button", { name: "Ending…" })).toBeDisabled();

      rerender(<InteractionDetail interactionId="interaction-b" />);
      expect(
        screen.queryByRole("heading", { name: "Alpha active meeting" }),
      ).not.toBeInTheDocument();
      await screen.findByRole("heading", { name: "Bravo discovery" });

      await act(async () => {
        if (outcome === "success") {
          completionResponse.resolve(
            jsonResponse({
              ...interactionA,
              lifecycleStatus: "completed",
              actualEndAt: "2026-08-01T01:00:00Z",
            }),
          );
        } else {
          completionResponse.reject(
            new Error("Alpha completion must stay private to Alpha."),
          );
        }
        await Promise.resolve();
      });

      expect(
        screen.getByRole("heading", { name: "Bravo discovery" }),
      ).toBeVisible();
      expect(
        screen.getByRole("button", { name: "Start meeting" }),
      ).toBeEnabled();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
  );

  it("rejects a mismatched interaction returned by the detail endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/api/v1/interactions/interaction-1")
          ? Promise.resolve(
              jsonResponse({
                ...interaction,
                id: "interaction-foreign",
                title: "Foreign conversation",
              }),
            )
          : Promise.resolve(jsonResponse({ featureFlags: {} })),
      ),
    );

    render(<InteractionDetail interactionId="interaction-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The conversation could not be loaded. Try again.",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Foreign conversation" }),
    ).not.toBeInTheDocument();
  });

  it("rejects a mismatched interaction returned after starting", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/start") && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse({
              ...interaction,
              id: "interaction-foreign",
              title: "Foreign conversation",
              lifecycleStatus: "in_progress",
            }),
          );
        }
        if (path.endsWith("/api/v1/interactions/interaction-1")) {
          return Promise.resolve(jsonResponse(interaction));
        }
        return Promise.resolve(jsonResponse({ featureFlags: {} }));
      }),
    );

    render(<InteractionDetail interactionId="interaction-1" />);
    await screen.findByRole("heading", { name: "Acme discovery" });
    fireEvent.click(screen.getByRole("button", { name: "Start meeting" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The conversation could not be started. Try again.",
    );
    expect(screen.getByRole("button", { name: "Start meeting" })).toBeEnabled();
    expect(
      screen.queryByRole("heading", { name: "Foreign conversation" }),
    ).not.toBeInTheDocument();
  });

  it("rejects a mismatched interaction returned after completion", async () => {
    const activeInteraction: Interaction = {
      ...interaction,
      lifecycleStatus: "in_progress",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/complete") && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse({
              ...activeInteraction,
              id: "interaction-foreign",
              title: "Foreign conversation",
              lifecycleStatus: "completed",
            }),
          );
        }
        if (path.endsWith("/api/v1/interactions/interaction-1")) {
          return Promise.resolve(jsonResponse(activeInteraction));
        }
        return Promise.resolve(jsonResponse({ featureFlags: {} }));
      }),
    );

    render(<InteractionDetail interactionId="interaction-1" />);
    await screen.findByRole("heading", { name: "Acme discovery" });
    fireEvent.click(screen.getByRole("button", { name: "End meeting" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The conversation could not be completed. Try again.",
    );
    expect(screen.getByRole("button", { name: "End meeting" })).toBeEnabled();
    expect(
      screen.getByRole("status", { name: "Conversation lifecycle status" }),
    ).toHaveTextContent("In Progress");
    expect(
      screen.queryByRole("heading", { name: "Foreign conversation" }),
    ).not.toBeInTheDocument();
  });

  it("ignores a transcript callback returned for another interaction", () => {
    const completedInteraction: Interaction = {
      ...interaction,
      lifecycleStatus: "completed",
      actualEndAt: "2026-08-01T01:00:00Z",
    };

    render(
      <InteractionDetail
        interactionId={completedInteraction.id}
        initialInteraction={completedInteraction}
      />,
    );

    expect(
      screen.getByText("Meeting intelligence for meeting-1"),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Return foreign transcript" }),
    );
    expect(
      screen.getByText("Meeting intelligence for meeting-1"),
    ).toBeVisible();
    expect(
      screen.queryByText("Meeting intelligence for meeting-foreign"),
    ).not.toBeInTheDocument();
  });

  it("uses a matching seeded interaction without repeating the detail request", async () => {
    conversationWorkspaceMock.use.mockReturnValue(
      workspaceController({
        workspace: generatedWorkspace,
        values: {
          liveNotes: generatedWorkspace.liveNotes,
          enhancedNotes: generatedWorkspace.enhancedNotes,
          followUpDraft: generatedWorkspace.followUpDraft,
          followUpReviewed: false,
        },
      }),
    );
    const fetchMock = vi.fn((_input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          {
            code: "interaction_unavailable",
            message: "Conversation temporarily unavailable.",
            requestId: "request-seeded",
          },
          503,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionDetail
        interactionId="interaction-1"
        initialInteraction={{
          ...interaction,
          lifecycleStatus: "completed",
          actualEndAt: "2026-08-01T01:00:00Z",
        }}
        reviewOnly
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Conversation notes" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Your rough notes (original)")).toHaveValue(
      "Original live notes",
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/api/v1/interactions/interaction-1"),
      ),
    ).toBe(false);
  });

  it("ignores a seed belonging to another interaction", async () => {
    const completedInteraction: Interaction = {
      ...interaction,
      lifecycleStatus: "completed",
      actualEndAt: "2026-08-01T01:00:00Z",
    };
    conversationWorkspaceMock.use.mockReturnValue(
      workspaceController({
        workspace: generatedWorkspace,
        values: {
          liveNotes: generatedWorkspace.liveNotes,
          enhancedNotes: generatedWorkspace.enhancedNotes,
          followUpDraft: generatedWorkspace.followUpDraft,
          followUpReviewed: false,
        },
      }),
    );
    const fetchMock = vi.fn((_input: RequestInfo | URL) =>
      Promise.resolve(jsonResponse(completedInteraction)),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InteractionDetail
        interactionId="interaction-1"
        initialInteraction={{ ...completedInteraction, id: "interaction-2" }}
        reviewOnly
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Conversation notes" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/api/v1/interactions/interaction-1"),
      ),
    ).toBe(true);
  });

  it("starts and ends a normal phone-system call without offering browser call recording", async () => {
    let phone: Record<string, unknown> = {
      ...interaction,
      id: "phone-1",
      meetingId: null,
      interactionType: "phone_call",
      lifecycleStatus: "planned",
      title: "Jordan commercial call",
      contactId: "contact-1",
      callDirection: "outbound",
      callOutcome: null,
      durationSeconds: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/start") && init?.method === "POST") {
        phone = { ...phone, lifecycleStatus: "in_progress" };
      }
      if (path.endsWith("/complete") && init?.method === "POST") {
        phone = {
          ...phone,
          lifecycleStatus: "completed",
          callOutcome: "connected",
          durationSeconds: 62,
        };
      }
      if (path.includes("/beta/capabilities")) {
        return Promise.resolve(jsonResponse({ featureFlags: {} }));
      }
      return Promise.resolve(jsonResponse(phone));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionDetail interactionId="phone-1" />);
    await screen.findByRole("heading", { name: "Jordan commercial call" });
    expect(screen.getByText("Use your normal phone")).toBeVisible();
    expect(
      screen.getByText(/does not intercept cellular calls/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /record phone call/i }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start call" }));
    expect(
      await screen.findByRole("button", { name: "End connected call" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "End connected call" }));
    await waitFor(() =>
      expect(
        screen.getByRole("status", { name: "Conversation lifecycle status" }),
      ).toHaveTextContent("Completed"),
    );
    const completion = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/complete"),
    );
    expect(JSON.parse(String(completion?.[1]?.body))).toEqual({
      callOutcome: "connected",
    });
  });

  it("refreshes the visible private editor after applying a generated version", async () => {
    const applyGeneratedVersion = vi.fn(() => Promise.resolve(true));
    conversationWorkspaceMock.use.mockReturnValue(
      workspaceController({
        workspace: generatedWorkspace,
        values: {
          liveNotes: generatedWorkspace.liveNotes,
          enhancedNotes: generatedWorkspace.enhancedNotes,
          followUpDraft: generatedWorkspace.followUpDraft,
          followUpReviewed: false,
        },
        applyGeneratedVersion,
      }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...interaction,
            lifecycleStatus: "completed",
            actualEndAt: "2026-08-01T01:00:00Z",
          }),
        ),
      ),
    );

    render(<InteractionDetail interactionId="interaction-1" />);

    expect(
      await screen.findByRole("textbox", {
        name: "Visible private follow-up editor",
      }),
    ).toHaveValue("Edited follow-up");
    fireEvent.click(
      screen.getByRole("button", { name: "Use generated version 2" }),
    );

    await waitFor(() => expect(applyGeneratedVersion).toHaveBeenCalledOnce());
    await waitFor(() =>
      expect(
        screen.getByRole("textbox", {
          name: "Visible private follow-up editor",
        }),
      ).toHaveValue("Corrected private follow-up"),
    );
    expect(generatedWorkspace.liveNotes).toBe("Original live notes");
  });
});

describe("PostConversationDraftStatus", () => {
  it("shows pending work as private and lets the user check status", () => {
    const reload = vi.fn();
    render(
      <PostConversationDraftStatus
        workspace={{
          ...generatedWorkspace,
          generationState: "processing",
          generationUpdateAvailable: false,
        }}
        actionState="idle"
        actionError={null}
        onRetry={vi.fn()}
        onApply={vi.fn()}
        onRefresh={reload}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      /stays private to you and is never sent or shared automatically/i,
    );
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    expect(reload).toHaveBeenCalledOnce();
  });

  it("offers a retry after a retryable failure", () => {
    const retry = vi.fn();
    render(
      <PostConversationDraftStatus
        workspace={{
          ...generatedWorkspace,
          generationState: "failed",
          generationRetryAvailable: true,
          generationUpdateAvailable: false,
        }}
        actionState="idle"
        actionError={null}
        onRetry={retry}
        onApply={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      /edited drafts were preserved/i,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Retry private draft" }),
    );
    expect(retry).toHaveBeenCalledOnce();
  });

  it("requires an explicit choice before replacing draft fields with a late version", () => {
    const apply = vi.fn();
    render(
      <PostConversationDraftStatus
        workspace={generatedWorkspace}
        actionState="idle"
        actionError={null}
        onRetry={vi.fn()}
        onApply={apply}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      /edited enhanced notes.*preserved/i,
    );
    expect(
      screen.getByText(/keeps your original rough notes/i),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Use generated version 2" }),
    );
    expect(apply).toHaveBeenCalledOnce();
  });
});
