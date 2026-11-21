import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useLayoutEffect, useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationNotesReview } from "@/components/conversation-notes-review";
import {
  type ConversationWorkspaceController,
  useConversationWorkspace,
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

const readyWorkspace = {
  exists: true,
  ownerUserId: "user-1",
  lockVersion: 4,
  liveNotes: "Finance needs the implementation sequence before approval.",
  enhancedNotes:
    "Finance needs the implementation sequence. The transcript confirms a Friday review.",
  followUpDraft:
    "Subject: Friday review\n\nHere are the transcript-backed next steps.",
  followUpReviewed: false,
  generationFingerprint: "a".repeat(64),
  generationState: "ready" as const,
  generationId: "generation-1",
  generationTranscriptVersion: 1,
  generationPersonalNotesState: "current" as const,
  generationFailureCode: null,
  generationRetryAvailable: false,
  generationUpdateAvailable: false,
  generationCompletedAt: "2026-11-08T00:00:00Z",
  importedFromBrowserAt: null,
  updatedAt: "2026-11-08T00:00:00Z",
};

function ReviewHarness({
  interactionId = "interaction-1",
  probeOnCommit = false,
}: {
  interactionId?: string;
  probeOnCommit?: boolean;
}) {
  const controller = useConversationWorkspace({
    interactionId,
  });
  return (
    <>
      <LayoutMutationProbe
        active={probeOnCommit}
        controller={controller}
        interactionId={interactionId}
      />
      <ConversationNotesReview
        controller={controller}
        onApplyGeneratedVersion={async () => {
          await controller.applyGeneratedVersion();
        }}
      />
    </>
  );
}

function LayoutMutationProbe({
  active,
  controller,
  interactionId,
}: {
  active: boolean;
  controller: ConversationWorkspaceController;
  interactionId: string;
}) {
  const probedInteraction = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (!active || probedInteraction.current === interactionId) return;
    probedInteraction.current = interactionId;
    controller.setValues((current) => ({
      ...current,
      liveNotes: "Commit-time text must not cross interactions",
    }));
    void controller.save();
  }, [active, controller, interactionId]);
  return null;
}

const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
  if (originalScrollIntoView === undefined) {
    Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
  } else {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: originalScrollIntoView,
    });
  }
});

describe("ConversationNotesReview", () => {
  it("focuses the async follow-up target once for a direct deep link", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    window.history.replaceState(
      {},
      "",
      "/conversations/interaction-1?view=review#follow-up",
    );
    const fetchMock = vi.fn(() => Promise.resolve(response(readyWorkspace)));
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewHarness />);

    const followUp = await screen.findByRole("region", {
      name: "Follow-up review",
    });
    await waitFor(() => expect(followUp).toHaveFocus());
    expect(scrollIntoView).toHaveBeenCalledOnce();
    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "start",
      behavior: "auto",
    });

    fireEvent.click(screen.getByRole("button", { name: "Save rough notes" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(scrollIntoView).toHaveBeenCalledOnce();
  });

  it("shows an automatic private draft without requiring a completed debrief", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(readyWorkspace)));

    render(<ReviewHarness />);

    expect(
      await screen.findByLabelText("Your rough notes (original)"),
    ).toHaveValue(readyWorkspace.liveNotes);
    expect(screen.getByLabelText("Enhanced conversation notes")).toHaveValue(
      readyWorkspace.enhancedNotes,
    );
    expect(screen.getByLabelText("Private follow-up draft")).toHaveValue(
      readyWorkspace.followUpDraft,
    );
    expect(
      screen.getByText(/used the saved rough notes shown below/i),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Automatic transcript drafts use transcript evidence only/i,
      ),
    ).toBeVisible();
  });

  it("distinguishes unsaved rough-note edits from the saved note used for generation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          ...readyWorkspace,
          generationId: "generation-2",
          generationTranscriptVersion: 2,
          generationUpdateAvailable: true,
        }),
      ),
    );

    render(<ReviewHarness />);

    fireEvent.change(
      await screen.findByLabelText("Your rough notes (original)"),
      {
        target: { value: "A new rough-note edit that has not been saved." },
      },
    );

    expect(screen.getByText(/used your last saved rough notes/i)).toBeVisible();
    expect(
      screen.getByText(/unsaved rough-note changes were not included/i),
    ).toBeVisible();
    expect(
      screen.queryByText(/used the saved rough notes shown below/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Save or discard your unsaved changes/i),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Use generated version 2" }),
    ).toBeDisabled();
  });

  it("checks generation status without replacing a dirty enhanced-note edit", async () => {
    const pending = {
      ...readyWorkspace,
      generationState: "processing",
      enhancedNotes: "Earlier generated notes",
      generationUpdateAvailable: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(pending))
      .mockResolvedValueOnce(
        response({
          ...readyWorkspace,
          lockVersion: 5,
          enhancedNotes: "New server version",
          generationId: "generation-2",
          generationTranscriptVersion: 2,
          generationUpdateAvailable: true,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const enhanced = await screen.findByLabelText(
      "Enhanced conversation notes",
    );
    fireEvent.change(enhanced, {
      target: { value: "My unsaved wording stays visible." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Use generated version 2" }),
      ).toBeVisible(),
    );
    expect(enhanced).toHaveValue("My unsaved wording stays visible.");
    expect(screen.getByText("Unsaved changes")).toBeVisible();
  });

  it("keeps local text beside the latest version until it is explicitly used", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
          409,
        ),
      )
      .mockResolvedValueOnce(
        response({
          ...readyWorkspace,
          lockVersion: 5,
          enhancedNotes: "Latest saved wording from the other session.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const enhanced = await screen.findByLabelText(
      "Enhanced conversation notes",
    );
    fireEvent.change(enhanced, {
      target: { value: "Keep this local wording after the 409." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save enhanced notes" }),
    );

    expect(
      await screen.findByText(/changed in another session/i),
    ).toBeVisible();
    expect(enhanced).toHaveValue("Keep this local wording after the 409.");
    expect(
      await screen.findByLabelText("Latest saved enhanced notes"),
    ).toHaveValue("Latest saved wording from the other session.");
    fireEvent.click(
      screen.getByRole("button", {
        name: "Use latest saved version",
      }),
    );
    expect(enhanced).toHaveValue(
      "Latest saved wording from the other session.",
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("blocks generated-version replacement while a no-dirty-fields conflict is unresolved", async () => {
    const generatedUpdate = {
      ...readyWorkspace,
      generationUpdateAvailable: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(generatedUpdate))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
          409,
        ),
      )
      .mockResolvedValueOnce(
        response({
          ...generatedUpdate,
          lockVersion: 5,
          enhancedNotes: "Latest saved enhanced version.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    await screen.findByLabelText("Enhanced conversation notes");
    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Save enhanced notes" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Private notes changed in another session",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Use generated version 1" }),
    ).toBeDisabled();
  });

  it("saves reviewed conflict edits without replacing newer unrelated fields", async () => {
    const latestWorkspace = {
      ...readyWorkspace,
      lockVersion: 5,
      liveNotes: "Newer rough notes saved in the other session.",
      enhancedNotes: "Newer enhanced wording from the other session.",
      followUpDraft: "Newer private follow-up from the other session.",
      followUpReviewed: true,
      generationFingerprint: "b".repeat(64),
    };
    const reviewedEnhanced =
      "My reviewed enhanced wording, reconciled with the latest version.";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
          409,
        ),
      )
      .mockResolvedValueOnce(response(latestWorkspace))
      .mockResolvedValueOnce(
        response({
          ...latestWorkspace,
          lockVersion: 6,
          enhancedNotes: reviewedEnhanced,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const enhanced = await screen.findByLabelText(
      "Enhanced conversation notes",
    );
    fireEvent.change(enhanced, {
      target: { value: "My local enhanced wording." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save enhanced notes" }),
    );

    expect(
      await screen.findByLabelText("Latest saved enhanced notes"),
    ).toHaveValue(latestWorkspace.enhancedNotes);
    expect(enhanced).toHaveValue("My local enhanced wording.");
    fireEvent.change(enhanced, { target: { value: reviewedEnhanced } });
    fireEvent.click(
      screen.getByRole("button", { name: "Save reviewed changes" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(enhanced).toHaveValue(reviewedEnhanced);
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
      expectedLockVersion: 5,
      liveNotes: latestWorkspace.liveNotes,
      enhancedNotes: reviewedEnhanced,
      followUpDraft: latestWorkspace.followUpDraft,
      followUpReviewed: true,
      generationFingerprint: latestWorkspace.generationFingerprint,
      importFromBrowser: false,
    });
    expect(
      screen.queryByRole("heading", {
        name: "Private notes changed in another session",
      }),
    ).not.toBeInTheDocument();
  });

  it("does not claim changed rough notes match the generated version", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          ...readyWorkspace,
          generationPersonalNotesState: "changed",
        }),
      ),
    );

    render(<ReviewHarness />);

    expect(
      await screen.findByText(/used an earlier saved rough-note version/i),
    ).toBeVisible();
    expect(
      screen.getByText(/Your current rough notes remain unchanged/i),
    ).toBeVisible();
  });

  it("removes the previous conversation's private text immediately on navigation", async () => {
    const interactionB = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockImplementationOnce(() => interactionB.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(
      <ReviewHarness interactionId="interaction-a" />,
    );

    expect(
      await screen.findByLabelText("Your rough notes (original)"),
    ).toHaveValue(readyWorkspace.liveNotes);
    expect(screen.getByLabelText("Enhanced conversation notes")).toHaveValue(
      readyWorkspace.enhancedNotes,
    );
    expect(screen.getByLabelText("Private follow-up draft")).toHaveValue(
      readyWorkspace.followUpDraft,
    );

    rerender(
      <ReviewHarness interactionId="interaction-b" probeOnCommit={true} />,
    );

    expect(screen.getByText("Loading your private notes…")).toBeVisible();
    expect(
      screen.queryByText(readyWorkspace.liveNotes),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue(readyWorkspace.enhancedNotes),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue(readyWorkspace.followUpDraft),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(false);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await act(async () =>
      interactionB.resolve(
        response({
          ...readyWorkspace,
          lockVersion: 7,
          liveNotes: "Interaction B private notes",
          enhancedNotes: "Interaction B enhanced notes",
          followUpDraft: "Interaction B follow-up",
        }),
      ),
    );
    expect(
      await screen.findByDisplayValue("Interaction B private notes"),
    ).toBeVisible();
  });
});
