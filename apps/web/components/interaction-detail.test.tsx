import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InteractionDetail } from "@/components/interaction-detail";
import { PostConversationDraftStatus } from "@/components/conversation-notes-review";

vi.mock("@/components/conversation-memory", () => ({
  ConversationMemory: () => <div>Conversation memory</div>,
}));

const conversationWorkspaceMock = vi.hoisted(() => ({
  use: vi.fn(),
}));

vi.mock("@/lib/use-conversation-workspace", () => ({
  useConversationWorkspace: conversationWorkspaceMock.use,
}));

vi.mock("@/components/meeting-intelligence-workspace", () => ({
  MeetingIntelligenceWorkspace: ({
    workspaceRefreshKey = 0,
  }: {
    workspaceRefreshKey?: number;
  }) => (
    <textarea
      aria-label="Visible private follow-up editor"
      readOnly
      value={
        workspaceRefreshKey === 0
          ? "Edited follow-up"
          : "Corrected private follow-up"
      }
    />
  ),
}));

vi.mock("@/components/online-meeting-capture", () => ({
  OnlineMeetingCapture: () => <div>Online meeting capture</div>,
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
    dirtyFields: {
      liveNotes: false,
      enhancedNotes: false,
      followUpDraft: false,
      followUpReviewed: false,
    },
    isDirty: false,
    save: vi.fn(() => Promise.resolve(true)),
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

const interaction = {
  id: "interaction-1",
  organisationId: "organisation-1",
  companyId: null,
  opportunityId: null,
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
  createdByUserId: "user-1",
  createdAt: "2026-07-26T00:00:00Z",
  updatedAt: "2026-07-26T00:00:00Z",
};

const generatedWorkspace = {
  exists: true,
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
    ).toHaveAttribute("href", "/conversations/interaction-1/workspace");
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

  it("renders a safe error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              code: "interaction_not_found",
              message: "Interaction not found.",
              requestId: "request-3",
            },
            404,
          ),
        ),
      ),
    );

    render(<InteractionDetail interactionId="missing" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interaction not found.",
    );
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
