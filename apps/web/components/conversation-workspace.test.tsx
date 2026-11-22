import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { Interaction } from "@revenueos/shared";
import { useEffect, useState, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationWorkspace } from "@/components/conversation-workspace";

type ReviewSeedLoad = {
  interactionId: string;
  id: string | null;
  lifecycleStatus: string | null;
};

const state = vi.hoisted(() => ({
  aiCompanionEnabled: true,
  stopped: vi.fn(),
  reviewLoaded: vi.fn<(value: ReviewSeedLoad) => void>(),
}));

const verifiedOrganisation = vi.hoisted(() => ({
  state: {
    status: "available" as "available" | "loading" | "unavailable",
    organisationId: "organisation-1" as string | null,
    userId: "user-1" as string | null,
    identityKey: "external-session-one",
  },
  reload: vi.fn(),
}));

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => ({
    ...verifiedOrganisation.state,
    reload: verifiedOrganisation.reload,
  }),
}));

vi.mock("@/components/beta-feature-gate", () => ({
  BetaFeatureGate: ({
    children,
    feature,
  }: {
    children: ReactNode;
    feature: string;
  }) =>
    feature === "aiCompanion" && !state.aiCompanionEnabled ? null : children,
}));
vi.mock("@/components/pre-interaction-brief", () => ({
  PreInteractionBrief: ({ onBriefChange }: { onBriefChange?: () => void }) => (
    <div>
      <p>Prepared questions</p>
      <button type="button" onClick={onBriefChange}>
        Update prepared questions
      </button>
    </div>
  ),
}));
vi.mock("@/components/conversation-memory", () => ({
  ConversationMemory: () => <p>Previous conversations</p>,
}));
vi.mock("@/components/interaction-detail", () => ({
  InteractionDetail: ({
    initialInteraction,
    interactionId,
  }: {
    initialInteraction?: Interaction;
    interactionId: string;
  }) => {
    const [mountedSeed] = useState(() => ({
      id: initialInteraction?.id ?? null,
      lifecycleStatus: initialInteraction?.lifecycleStatus ?? null,
    }));
    useEffect(() => {
      state.reviewLoaded({ interactionId, ...mountedSeed });
    }, [interactionId, mountedSeed]);
    return (
      <div>
        <p>Conversation review</p>
        <p>
          Review seed {mountedSeed.id} · {mountedSeed.lifecycleStatus}
        </p>
      </div>
    );
  },
}));
vi.mock("@/components/face-to-face-companion", () => ({
  FaceToFaceCompanion: ({
    interactionId,
    initialInteraction,
    onInteractionChange,
    briefRefreshKey,
  }: {
    interactionId: string;
    initialInteraction?: Interaction;
    onInteractionChange: (value: Interaction) => void;
    briefRefreshKey: number;
  }) => {
    const current = initialInteraction ?? interaction({ id: interactionId });
    useEffect(() => () => state.stopped(), []);
    return (
      <div>
        <p>Brief refresh {briefRefreshKey}</p>
        <label>
          Private rough notes
          <input />
        </label>
        <button
          type="button"
          onClick={() =>
            onInteractionChange({
              ...current,
              lifecycleStatus: "completed",
              actualEndAt: "2026-11-22T01:00:00Z",
              updatedAt: "2026-11-22T01:00:00Z",
            })
          }
        >
          End call
        </button>
        <button
          type="button"
          onClick={() =>
            onInteractionChange({
              ...current,
              id: "foreign-interaction",
              organisationId: "organisation-foreign",
              title: "Foreign conversation",
              companyId: "company-foreign",
              lifecycleStatus: "completed",
              actualEndAt: "2026-11-22T01:00:00Z",
              updatedAt: "2026-11-22T01:00:00Z",
            })
          }
        >
          Emit mismatched interaction
        </button>
      </div>
    );
  },
}));

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function interaction(overrides: Partial<Interaction> = {}): Interaction {
  return {
    id: "call-1",
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId: null,
    contactId: null,
    meetingId: null,
    eventId: null,
    title: "Discovery",
    interactionType: "online_meeting",
    lifecycleStatus: "planned",
    scheduledStartAt: null,
    scheduledEndAt: null,
    actualStartAt: null,
    actualEndAt: null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    callDirection: null,
    callOutcome: null,
    meetingPlatform: "zoom",
    meetingUrl: "https://meeting.example.test/discovery",
    externalMeetingId: null,
    captureSource: null,
    ingestionState: null,
    durationSeconds: null,
    captureMethods: [],
    intelligenceState: "not_ready",
    recordingAvailable: false,
    createdByUserId: "user-1",
    briefState: "not_generated",
    briefGeneratedAt: null,
    createdAt: "2026-11-22T00:00:00Z",
    updatedAt: "2026-11-22T00:00:00Z",
    ...overrides,
  };
}

function response(
  lifecycleStatus: Interaction["lifecycleStatus"] = "planned",
  id = "call-1",
  title = "Discovery",
  overrides: Partial<Interaction> = {},
) {
  return new Response(
    JSON.stringify(
      interaction({
        id,
        title,
        lifecycleStatus,
        ...overrides,
      }),
    ),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("ConversationWorkspace", () => {
  afterEach(() => {
    state.aiCompanionEnabled = true;
    verifiedOrganisation.state = {
      status: "available",
      organisationId: "organisation-1",
      userId: "user-1",
      identityKey: "external-session-one",
    };
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("shows only generic identity verification and recovery states", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    verifiedOrganisation.state = {
      status: "loading",
      organisationId: null,
      userId: null,
      identityKey: "external-session-pending",
    };

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Verifying your secure workspace",
    );
    expect(fetchMock).not.toHaveBeenCalled();

    verifiedOrganisation.state = {
      status: "unavailable",
      organisationId: null,
      userId: null,
      identityKey: "external-session-pending",
    };
    rendered.rerender(<ConversationWorkspace interactionId="call-1" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your identity could not be verified.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(verifiedOrganisation.reload).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("synchronously redacts the previous conversation when verified identity changes", async () => {
    const nextIdentityConversation = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response("planned", "call-1", "Organisation one conversation"),
      )
      .mockReturnValueOnce(nextIdentityConversation.promise);
    vi.stubGlobal("fetch", fetchMock);

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Open notes & capture" }),
    );
    fireEvent.change(screen.getByLabelText("Private rough notes"), {
      target: { value: "Organisation one private note" },
    });

    verifiedOrganisation.state = {
      status: "available",
      organisationId: "organisation-2",
      userId: "user-2",
      identityKey: "external-session-two",
    };
    rendered.rerender(<ConversationWorkspace interactionId="call-1" />);

    expect(
      screen.queryByRole("heading", { name: "Organisation one conversation" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Organisation one private note"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );

    await act(async () => {
      nextIdentityConversation.resolve(
        response("planned", "call-1", "Organisation two conversation", {
          organisationId: "organisation-2",
          createdByUserId: "user-2",
        }),
      );
      await nextIdentityConversation.promise;
    });
    expect(
      await screen.findByRole("heading", {
        name: "Organisation two conversation",
      }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keeps capture and unsaved notes mounted while moving between sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(response())),
    );
    render(<ConversationWorkspace interactionId="call-1" />);

    expect(await screen.findByText("Prepared questions")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Back to conversations" }),
    ).toHaveAttribute("href", "/conversations/accounts/company-1");
    fireEvent.click(screen.getByRole("button", { name: "Notes & capture" }));
    expect(screen.getByText("Brief refresh 0")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Private rough notes"), {
      target: { value: "Ask about rollout" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Review & follow-up" }));
    expect(window.location.search).toBe("?view=review");
    expect(screen.getByText("Conversation review")).toBeVisible();
    expect(screen.getByText("Review seed call-1 · planned")).toBeVisible();
    expect(screen.getByLabelText("Private rough notes")).not.toBeVisible();
    expect(state.stopped).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Notes & capture" }));
    expect(screen.getByLabelText("Private rough notes")).toHaveValue(
      "Ask about rollout",
    );
    fireEvent.click(screen.getByRole("button", { name: "Preparation" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Update prepared questions" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Notes & capture" }));
    expect(screen.getByText("Brief refresh 1")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "End call" }));
    await waitFor(() => expect(state.reviewLoaded).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Review & follow-up" }));
    expect(screen.getByText("Review seed call-1 · completed")).toBeVisible();
    expect(state.stopped).not.toHaveBeenCalled();
  });

  it("opens a simple note directly when AI Companion is disabled and CRM context is absent", async () => {
    state.aiCompanionEnabled = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response("planned", "call-1", "Event notes", {
            companyId: null,
            interactionType: "manual_interaction",
            meetingPlatform: null,
            meetingUrl: null,
          }),
        ),
      ),
    );

    render(<ConversationWorkspace interactionId="call-1" />);

    expect(await screen.findByLabelText("Private rough notes")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Notes & capture" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Prepared questions")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Preparation" }));
    expect(screen.queryByText("Prepared questions")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Open notes & capture" }),
    );
    expect(screen.getByLabelText("Private rough notes")).toBeVisible();
  });

  it("opens completed conversations in review and honours preparation links", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(response("completed"))),
    );
    const first = render(<ConversationWorkspace interactionId="call-1" />);
    expect(await screen.findByText("Conversation review")).toBeVisible();
    first.unmount();

    window.history.replaceState({}, "", "/#preparation");
    render(<ConversationWorkspace interactionId="call-1" />);
    expect(await screen.findByText("Prepared questions")).toBeVisible();
  });

  it("opens a planned conversation in review for a follow-up deep link", async () => {
    window.history.replaceState({}, "", "/conversations/call-1#follow-up");
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(response("planned"))),
    );

    render(<ConversationWorkspace interactionId="call-1" />);

    expect(await screen.findByText("Conversation review")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Review & follow-up" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Prepared questions")).not.toBeInTheDocument();
  });

  it("remounts seeded review state when the interaction id changes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const id = String(input).endsWith("/call-2") ? "call-2" : "call-1";
        return Promise.resolve(response("completed", id));
      }),
    );

    const rendered = render(
      <ConversationWorkspace interactionId="call-1" initialView="review" />,
    );
    expect(
      await screen.findByText("Review seed call-1 · completed"),
    ).toBeVisible();

    rendered.rerender(
      <ConversationWorkspace interactionId="call-2" initialView="review" />,
    );
    expect(
      screen.queryByText("Review seed call-1 · completed"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText("Review seed call-2 · completed"),
    ).toBeVisible();
    expect(state.reviewLoaded).toHaveBeenCalledWith({
      interactionId: "call-1",
      id: "call-1",
      lifecycleStatus: "completed",
    });
    expect(state.reviewLoaded).toHaveBeenLastCalledWith({
      interactionId: "call-2",
      id: "call-2",
      lifecycleStatus: "completed",
    });
    expect(
      state.reviewLoaded.mock.calls.every(
        ([loaded]) => loaded.interactionId === loaded.id,
      ),
    ).toBe(true);
  });

  it("hides an earlier load error synchronously while the next conversation loads", async () => {
    const nextConversation = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/call-1")
          ? Promise.reject(new Error("Conversation A could not be loaded."))
          : nextConversation.promise,
      ),
    );

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not reach the service/i,
    );

    rendered.rerender(<ConversationWorkspace interactionId="call-2" />);
    expect(
      screen.queryByText(/could not reach the service/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );

    await act(async () => {
      nextConversation.resolve(response("planned", "call-2", "Conversation B"));
      await nextConversation.promise;
    });
    expect(
      await screen.findByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();
  });

  it("fails closed on a mismatched conversation response and retries safely", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response("planned", "call-1", "Foreign conversation"),
      )
      .mockResolvedValueOnce(response("planned", "call-2", "Conversation B"));
    vi.stubGlobal("fetch", fetchMock);

    render(<ConversationWorkspace interactionId="call-2" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This conversation could not be loaded.",
    );
    expect(
      screen.queryByRole("heading", { name: "Foreign conversation" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );
    expect(
      await screen.findByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("fails closed on a conversation response from another organisation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response("planned", "call-1", "Foreign organisation", {
            organisationId: "organisation-foreign",
          }),
        ),
      ),
    );

    render(<ConversationWorkspace interactionId="call-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This conversation could not be loaded.",
    );
    expect(
      screen.queryByRole("heading", { name: "Foreign organisation" }),
    ).not.toBeInTheDocument();
  });

  it("fails closed on a malformed conversation response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response("planned", "call-1", "Malformed conversation", {
            createdAt: "not-a-date",
          }),
        ),
      ),
    );

    render(<ConversationWorkspace interactionId="call-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This conversation could not be loaded.",
    );
    expect(
      screen.queryByRole("heading", { name: "Malformed conversation" }),
    ).not.toBeInTheDocument();
  });

  it("preserves verified conversation state and private notes when a child update is rejected", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(response("planned", "call-1", "Conversation A")),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ConversationWorkspace interactionId="call-1" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Open notes & capture" }),
    );
    fireEvent.change(screen.getByLabelText("Private rough notes"), {
      target: { value: "Keep this private draft" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Emit mismatched interaction" }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your verified conversation and private notes are unchanged.",
    );
    expect(
      screen.getByRole("heading", { name: "Conversation A" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Private rough notes")).toHaveValue(
      "Keep this private draft",
    );
    expect(
      screen.queryByRole("heading", { name: "Foreign conversation" }),
    ).not.toBeInTheDocument();
    expect(state.stopped).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "End call" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Conversation A" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review & follow-up" }));
    expect(
      await screen.findByText("Review seed call-1 · completed"),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("ignores a late successful response from the previous conversation", async () => {
    const firstConversation = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/call-1")
          ? firstConversation.promise
          : Promise.resolve(response("planned", "call-2", "Conversation B")),
      ),
    );

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversation",
    );
    rendered.rerender(<ConversationWorkspace interactionId="call-2" />);
    expect(
      await screen.findByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();

    await act(async () => {
      firstConversation.resolve(
        response("planned", "call-1", "Conversation A"),
      );
      await firstConversation.promise;
    });
    expect(
      screen.getByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Conversation A" }),
    ).not.toBeInTheDocument();
  });

  it("ignores a late failure from the previous conversation", async () => {
    const firstConversation = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).endsWith("/call-1")
          ? firstConversation.promise
          : Promise.resolve(response("planned", "call-2", "Conversation B")),
      ),
    );

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    rendered.rerender(<ConversationWorkspace interactionId="call-2" />);
    expect(
      await screen.findByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();

    await act(async () => {
      firstConversation.reject(new Error("Conversation A failed late."));
      await firstConversation.promise.catch(() => undefined);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Conversation B" }),
    ).toBeVisible();
  });

  it("resets the preparation refresh sequence for the next conversation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const second = String(input).endsWith("/call-2");
        return Promise.resolve(
          response(
            "planned",
            second ? "call-2" : "call-1",
            second ? "Conversation B" : "Conversation A",
          ),
        );
      }),
    );

    const rendered = render(<ConversationWorkspace interactionId="call-1" />);
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Update prepared questions",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Open notes & capture" }),
    );
    expect(screen.getByText("Brief refresh 1")).toBeVisible();

    rendered.rerender(<ConversationWorkspace interactionId="call-2" />);
    expect(screen.queryByText("Brief refresh 1")).not.toBeInTheDocument();
    fireEvent.click(
      await screen.findByRole("button", { name: "Open notes & capture" }),
    );
    expect(screen.getByText("Brief refresh 0")).toBeVisible();
  });
});
