import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Interaction } from "@revenueos/shared";
import { useEffect, useState, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationWorkspace } from "@/components/conversation-workspace";

const state = vi.hoisted(() => ({
  aiCompanionEnabled: true,
  stopped: vi.fn(),
  reviewLoaded: vi.fn(),
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
    onInteractionChange,
    briefRefreshKey,
  }: {
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
              id: "call-1",
              title: "Discovery",
              companyId: "company-1",
              lifecycleStatus: "completed",
            } as Interaction)
          }
        >
          End call
        </button>
      </div>
    );
  },
}));

function response(lifecycleStatus = "planned", id = "call-1") {
  return new Response(
    JSON.stringify({
      id,
      title: "Discovery",
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
    expect(state.reviewLoaded).toHaveBeenCalledTimes(2);
  });
});
