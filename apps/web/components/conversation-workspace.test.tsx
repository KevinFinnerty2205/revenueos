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
    onInteractionChange,
    briefRefreshKey,
  }: {
    interactionId: string;
    onInteractionChange: (value: Interaction) => void;
    briefRefreshKey: number;
  }) => {
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
              id: interactionId,
              title: "Discovery",
              companyId: "company-1",
              lifecycleStatus: "completed",
            } as Interaction)
          }
        >
          End call
        </button>
        <button
          type="button"
          onClick={() =>
            onInteractionChange({
              id: "foreign-interaction",
              title: "Foreign conversation",
              companyId: "company-foreign",
              lifecycleStatus: "completed",
            } as Interaction)
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

function response(
  lifecycleStatus = "planned",
  id = "call-1",
  title = "Discovery",
) {
  return new Response(
    JSON.stringify({
      id,
      title,
      companyId: "company-1",
      interactionType: "online_meeting",
      lifecycleStatus,
      actualStartAt: null,
      scheduledStartAt: null,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("ConversationWorkspace", () => {
  afterEach(() => {
    state.aiCompanionEnabled = true;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
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
          new Response(
            JSON.stringify({
              id: "call-1",
              title: "Event notes",
              companyId: null,
              interactionType: "manual_interaction",
              lifecycleStatus: "planned",
              actualStartAt: null,
              scheduledStartAt: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
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

  it("fails closed on a mismatched child update and retries the requested conversation", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(response("planned", "call-1", "Conversation A")),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ConversationWorkspace interactionId="call-1" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Open notes & capture" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Emit mismatched interaction" }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
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
      await screen.findByRole("heading", { name: "Conversation A" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
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
