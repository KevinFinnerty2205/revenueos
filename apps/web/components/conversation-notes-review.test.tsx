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

vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => ({
    status: "available",
    organisationId: "organisation-1",
    userId: "user-1",
    identityKey: "organisation-1:user-1",
    reload: vi.fn(),
  }),
}));

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
  interactionId: "interaction-1",
  organisationId: "organisation-1",
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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockResolvedValueOnce(
        response({
          ...readyWorkspace,
          lockVersion: readyWorkspace.lockVersion + 1,
        }),
      );
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
    expect(
      await screen.findByText(/Saved privately to your Oryntela workspace/),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
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

  it("reloads a stale generated-version choice before a new deliberate apply", async () => {
    const applicable = { ...readyWorkspace, generationUpdateAvailable: true };
    const latest = {
      ...applicable,
      lockVersion: 5,
      liveNotes: "Rough notes saved in another tab",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(applicable))
      .mockResolvedValueOnce(
        response({ code: "conversation_workspace_conflict" }, 409),
      )
      .mockResolvedValueOnce(response(latest))
      .mockResolvedValueOnce(
        response({
          ...latest,
          lockVersion: 6,
          generationUpdateAvailable: false,
          enhancedNotes: "The newly applied notes",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const apply = await screen.findByRole("button", {
      name: "Use generated version 1",
    });
    fireEvent.click(apply);
    const refresh = await screen.findByRole("button", {
      name: "Load latest saved draft",
    });
    expect(
      screen.queryByRole("button", { name: "Check status" }),
    ).not.toBeInTheDocument();
    expect(apply).toBeDisabled();
    fireEvent.click(refresh);
    await waitFor(() => expect(apply).toBeEnabled());
    expect(screen.getByLabelText("Your rough notes (original)")).toHaveValue(
      latest.liveNotes,
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2]?.[0]).toMatch(/personal-workspace$/);

    fireEvent.click(apply);
    await waitFor(() =>
      expect(screen.getByLabelText("Enhanced conversation notes")).toHaveValue(
        "The newly applied notes",
      ),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
      generationId: applicable.generationId,
      expectedLockVersion: latest.lockVersion,
    });
  });

  it("preserves text entered while applying for comparison with the latest saved draft", async () => {
    const pendingApply = deferred<Response>();
    const applicable = { ...readyWorkspace, generationUpdateAvailable: true };
    const latest = {
      ...applicable,
      lockVersion: 5,
      enhancedNotes: "Newer notes saved in another tab",
      followUpDraft: "A separately saved follow-up",
    };
    const localEdit =
      "A new enhanced-note edit made while the request was pending";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(applicable))
      .mockImplementationOnce(() => pendingApply.promise)
      .mockResolvedValueOnce(response(latest))
      .mockResolvedValueOnce(
        response({ ...latest, lockVersion: 6, enhancedNotes: localEdit }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const apply = await screen.findByRole("button", {
      name: "Use generated version 1",
    });
    fireEvent.click(apply);
    expect(screen.getByRole("button", { name: "Check status" })).toBeDisabled();
    const enhanced = screen.getByLabelText("Enhanced conversation notes");
    fireEvent.change(enhanced, { target: { value: localEdit } });
    await act(async () => {
      pendingApply.resolve(
        response({ code: "conversation_workspace_conflict" }, 409),
      );
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "Load latest saved draft" }),
    );

    expect(
      await screen.findByLabelText("Latest saved enhanced notes"),
    ).toHaveValue(latest.enhancedNotes);
    expect(enhanced).toHaveValue(localEdit);
    expect(apply).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Save reviewed changes" }),
    );
    await waitFor(() => expect(apply).toBeEnabled());

    expect(
      JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body)),
    ).toMatchObject({
      expectedLockVersion: latest.lockVersion,
      enhancedNotes: localEdit,
      followUpDraft: latest.followUpDraft,
    });
    expect(enhanced).toHaveValue(localEdit);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("preserves a reviewed follow-up when saving unchanged text", async () => {
    const reviewedWorkspace = {
      ...readyWorkspace,
      followUpReviewed: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewedWorkspace))
      .mockResolvedValueOnce(
        response({
          ...reviewedWorkspace,
          lockVersion: reviewedWorkspace.lockVersion + 1,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewHarness />);

    expect(await screen.findByText("Review status: Reviewed")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Mark reviewed" }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Save follow-up draft" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      followUpDraft: reviewedWorkspace.followUpDraft,
      followUpReviewed: true,
    });
    expect(screen.getByText("Review status: Reviewed")).toBeVisible();
  });

  it("reopens review when the follow-up text changes", async () => {
    const reviewedWorkspace = {
      ...readyWorkspace,
      followUpReviewed: true,
    };
    const editedDraft =
      "Subject: Updated Friday review\n\nPlease review the changes.";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(reviewedWorkspace))
      .mockResolvedValueOnce(
        response({
          ...reviewedWorkspace,
          lockVersion: reviewedWorkspace.lockVersion + 1,
          followUpDraft: editedDraft,
          followUpReviewed: false,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewHarness />);

    const draft = await screen.findByLabelText("Private follow-up draft");
    expect(screen.getByText("Review status: Reviewed")).toBeVisible();
    fireEvent.change(draft, { target: { value: editedDraft } });

    expect(screen.getByText("Review status: Needs review")).toBeVisible();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeEnabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Save follow-up draft" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      followUpDraft: editedDraft,
      followUpReviewed: false,
    });
  });

  it("keeps a failed review visibly pending", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_unavailable",
            message: "Your private workspace could not be saved.",
          },
          503,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewHarness />);

    expect(
      await screen.findByText("Review status: Needs review"),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));

    expect(
      await screen.findByText(/Your private workspace could not be saved/),
    ).toBeVisible();
    expect(screen.getByText("Review status: Needs review")).toBeVisible();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeEnabled();
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({ followUpReviewed: true });
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

  it("discovers the first generated draft after opening review before preparation begins", async () => {
    const pendingRefresh = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          ...readyWorkspace,
          lockVersion: 3,
          enhancedNotes: null,
          followUpDraft: null,
          generationFingerprint: null,
          generationState: "not_started",
          generationId: null,
          generationTranscriptVersion: null,
          generationPersonalNotesState: "not_included",
          generationCompletedAt: null,
        }),
      )
      .mockImplementationOnce(() => pendingRefresh.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    expect(
      await screen.findByText(
        /No automatic transcript version has been prepared yet/i,
      ),
    ).toBeVisible();
    const enhanced = screen.getByLabelText("Enhanced conversation notes");
    expect(enhanced).toHaveValue("");
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();

    await act(async () => {
      pendingRefresh.resolve(response(readyWorkspace));
    });
    expect(
      await screen.findByText(
        /Your private draft for transcript version 1 is ready/i,
      ),
    ).toBeVisible();
    expect(enhanced).toHaveValue(readyWorkspace.enhancedNotes);
    expect(screen.getByLabelText("Private follow-up draft")).toHaveValue(
      readyWorkspace.followUpDraft,
    );
    expect(screen.getByRole("button", { name: "Check status" })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
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
    expect(screen.getByRole("button", { name: "Check status" })).toBeDisabled();
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

  it("requires a verified refresh after an uncertain reviewed save before allowing resolution", async () => {
    const comparedWorkspace = {
      ...readyWorkspace,
      lockVersion: 5,
      enhancedNotes: "First verified comparison.",
    };
    const refreshedWorkspace = {
      ...comparedWorkspace,
      lockVersion: 6,
      enhancedNotes: "Newer verified comparison.",
      followUpDraft: "Newer private follow-up.",
    };
    const reviewedNotes = "My reconciled enhanced notes.";
    const newerLocalNotes = "My additional edits after the uncertain save.";
    const latestRead = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(readyWorkspace))
      .mockResolvedValueOnce(
        response({ code: "conversation_workspace_conflict" }, 409),
      )
      .mockResolvedValueOnce(response(comparedWorkspace))
      .mockResolvedValueOnce(
        response({ ...comparedWorkspace, enhancedNotes: reviewedNotes }),
      )
      .mockImplementationOnce(() => latestRead.promise)
      .mockResolvedValueOnce(
        response({
          ...refreshedWorkspace,
          lockVersion: 7,
          enhancedNotes: newerLocalNotes,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewHarness />);

    const enhanced = await screen.findByLabelText(
      "Enhanced conversation notes",
    );
    fireEvent.change(enhanced, { target: { value: reviewedNotes } });
    fireEvent.click(
      screen.getByRole("button", { name: "Save enhanced notes" }),
    );
    const comparison = await screen.findByLabelText(
      "Latest saved enhanced notes",
    );
    expect(comparison).toHaveValue(comparedWorkspace.enhancedNotes);
    fireEvent.click(
      screen.getByRole("button", { name: "Save reviewed changes" }),
    );

    const notice = await screen.findByText(
      "Your private workspace save could not be verified. Your local changes are still safe.",
    );
    expect(notice).toHaveAttribute("role", "alert");
    expect(comparison).toBeVisible();
    expect(comparison).toHaveValue(comparedWorkspace.enhancedNotes);
    expect(enhanced).toBeEnabled();
    expect(enhanced).toHaveValue(reviewedNotes);
    expect(
      screen.getByRole("button", { name: "Save reviewed changes" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Use latest saved version" }),
    ).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(4);

    fireEvent.change(enhanced, { target: { value: newerLocalNotes } });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Try loading the latest version again",
      }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(
      screen.getByText("Loading the latest saved private notes…"),
    ).toHaveAttribute("role", "status");
    await act(async () => {
      latestRead.resolve(response(refreshedWorkspace));
    });

    expect(
      await screen.findByLabelText("Latest saved enhanced notes"),
    ).toHaveValue(refreshedWorkspace.enhancedNotes);
    expect(enhanced).toHaveValue(newerLocalNotes);
    expect(notice).not.toBeInTheDocument();
    const saveReviewed = screen.getByRole("button", {
      name: "Save reviewed changes",
    });
    expect(saveReviewed).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Use latest saved version" }),
    ).toBeEnabled();
    fireEvent.click(saveReviewed);

    expect(
      await screen.findByText(/Saved privately to your Oryntela workspace/i),
    ).toBeVisible();
    expect(enhanced).toHaveValue(newerLocalNotes);
    expect(
      JSON.parse(String(fetchMock.mock.calls[5]?.[1]?.body)),
    ).toMatchObject({
      expectedLockVersion: refreshedWorkspace.lockVersion,
      enhancedNotes: newerLocalNotes,
      followUpDraft: refreshedWorkspace.followUpDraft,
    });
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
      .mockResolvedValueOnce(
        response({ ...readyWorkspace, interactionId: "interaction-a" }),
      )
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
          interactionId: "interaction-b",
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
