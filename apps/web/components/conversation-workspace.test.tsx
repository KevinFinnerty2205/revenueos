import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Interaction } from "@revenueos/shared";
import { useEffect, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationWorkspace } from "@/components/conversation-workspace";

const state = vi.hoisted(() => ({ stopped: vi.fn(), reviewLoaded: vi.fn() }));
vi.mock("@/components/beta-feature-gate", () => ({
  BetaFeatureGate: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/components/pre-interaction-brief", () => ({
  PreInteractionBrief: () => <p>Prepared questions</p>,
}));
vi.mock("@/components/conversation-memory", () => ({
  ConversationMemory: () => <p>Previous conversations</p>,
}));
vi.mock("@/components/interaction-detail", () => ({
  InteractionDetail: () => {
    useEffect(() => {
      state.reviewLoaded();
    }, []);
    return <p>Conversation review</p>;
  },
}));
vi.mock("@/components/face-to-face-companion", () => ({
  FaceToFaceCompanion: ({
    onInteractionChange,
  }: {
    onInteractionChange: (value: Interaction) => void;
  }) => {
    useEffect(() => () => state.stopped(), []);
    return (
      <div>
        <label>
          Private rough notes
          <input />
        </label>
        <button
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

const response = (lifecycleStatus = "planned") =>
  new Response(
    JSON.stringify({
      id: "call-1",
      title: "Discovery",
      companyId: "company-1",
      interactionType: "online_meeting",
      lifecycleStatus,
      actualStartAt: null,
      scheduledStartAt: null,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );

describe("ConversationWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("keeps capture and unsaved notes alive while moving between sections and refreshes review after completion", async () => {
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
    fireEvent.change(screen.getByLabelText("Private rough notes"), {
      target: { value: "Ask about rollout" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Review & follow-up" }));
    expect(screen.getByText("Conversation review")).toBeVisible();
    expect(screen.getByLabelText("Private rough notes")).not.toBeVisible();
    expect(state.stopped).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Notes & capture" }));
    expect(screen.getByLabelText("Private rough notes")).toHaveValue(
      "Ask about rollout",
    );
    fireEvent.click(screen.getByRole("button", { name: "End call" }));
    await waitFor(() => expect(state.reviewLoaded).toHaveBeenCalledTimes(2));
    expect(state.stopped).not.toHaveBeenCalled();
  });

  it("opens a simple note directly in the editor without requiring a CRM record", async () => {
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
            { status: 200 },
          ),
        ),
      ),
    );
    render(<ConversationWorkspace interactionId="call-1" />);
    expect(await screen.findByLabelText("Private rough notes")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Notes & capture" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("opens completed conversations in review and honours an explicit preparation link", async () => {
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
});
