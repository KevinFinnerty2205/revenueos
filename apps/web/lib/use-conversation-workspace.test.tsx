import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useConversationWorkspace } from "@/lib/use-conversation-workspace";

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const savedWorkspace = {
  exists: true,
  ownerUserId: "user-1",
  lockVersion: 4,
  liveNotes: "Notes retained if media capture stops",
  enhancedNotes: "Saved in another browser",
  followUpDraft: "Saved draft — never send automatically.",
  followUpReviewed: false,
  generationFingerprint: "a".repeat(64),
  generationState: "ready",
  generationId: "generation-1",
  generationTranscriptVersion: 1,
  generationPersonalNotesState: "current",
  generationFailureCode: null,
  generationRetryAvailable: false,
  generationUpdateAvailable: false,
  generationCompletedAt: "2026-10-31T00:00:00Z",
  importedFromBrowserAt: null,
  updatedAt: "2026-10-31T00:00:00Z",
};

afterEach(() => vi.unstubAllGlobals());

describe("useConversationWorkspace", () => {
  it("prefers durable user edits over regenerated defaults and saves with a lock version", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockResolvedValueOnce(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          enhancedNotes: "Edited in this browser",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({
        interactionId: "interaction-1",
        initialEnhancedNotes:
          "New generated output must not replace saved work",
      }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.enhancedNotes).toBe(
      "Saved in another browser",
    );

    act(() => {
      result.current.setValues((current) => ({
        ...current,
        enhancedNotes: "Edited in this browser",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(true);
    });
    expect(result.current.saveState).toBe("saved");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      expectedLockVersion: 4,
      liveNotes: "Notes retained if media capture stops",
      enhancedNotes: "Edited in this browser",
      followUpDraft: "Saved draft — never send automatically.",
    });
  });

  it("surfaces a stale-session conflict without replacing the local edit", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
          ...savedWorkspace,
          lockVersion: 5,
          followUpDraft: "Latest saved wording from the other session.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        followUpDraft: "Keep this unsaved browser edit visible.",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(result.current.saveState).toBe("conflict");
    expect(result.current.values.followUpDraft).toBe(
      "Keep this unsaved browser edit visible.",
    );
    expect(result.current.workspace?.lockVersion).toBe(4);
    expect(result.current.conflictRecovery).toMatchObject({
      state: "ready",
      latestWorkspace: { lockVersion: 5 },
      latestValues: {
        followUpDraft: "Latest saved wording from the other session.",
      },
      submittedValues: {
        followUpDraft: "Keep this unsaved browser edit visible.",
      },
      submittedFields: {
        liveNotes: false,
        enhancedNotes: false,
        followUpDraft: true,
        followUpReviewed: false,
      },
      error: null,
    });
  });

  it("explicitly adopts the separately loaded latest conflict version", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Latest saved note from the other session.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
          409,
        ),
      )
      .mockResolvedValueOnce(response(latestWorkspace));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Local note that must remain until I choose otherwise.",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });

    expect(result.current.values.liveNotes).toBe(
      "Local note that must remain until I choose otherwise.",
    );
    act(() => {
      expect(result.current.useLatestConflict()).toBe(true);
    });
    expect(result.current.values.liveNotes).toBe(
      "Latest saved note from the other session.",
    );
    expect(result.current.workspace?.lockVersion).toBe(5);
    expect(result.current.saveState).toBe("idle");
    expect(result.current.conflictRecovery.state).toBe("idle");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not let an unrelated refresh dismiss a conflict with no dirty visible fields", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      enhancedNotes: "Latest saved wording from the other session.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
          generationState: "processing",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isDirty).toBe(false);
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("ready");

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.saveState).toBe("conflict");
    expect(result.current.conflictRecovery).toMatchObject({
      state: "ready",
      latestWorkspace: { lockVersion: 5 },
    });
    expect(result.current.workspace?.lockVersion).toBe(4);
    expect(result.current.values.enhancedNotes).toBe(
      savedWorkspace.enhancedNotes,
    );
    expect(result.current.workspace?.generationState).toBe("processing");
  });

  it("rebases clean fields while keeping a submitted review bound to its follow-up draft", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Remote live note",
      enhancedNotes: "Remote enhanced note",
      followUpDraft: "Remote follow-up draft",
      followUpReviewed: false,
      generationFingerprint: "b".repeat(64),
    };
    const resolvedWorkspace = {
      ...latestWorkspace,
      lockVersion: 6,
      liveNotes: "Reviewed local live note",
      followUpDraft: savedWorkspace.followUpDraft,
      followUpReviewed: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
      .mockResolvedValueOnce(response(resolvedWorkspace));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Reviewed local live note",
      }));
    });
    await act(async () => {
      expect(await result.current.save({ followUpReviewed: true })).toBe(false);
    });
    expect(result.current.conflictRecovery.submittedFields).toEqual({
      liveNotes: true,
      enhancedNotes: false,
      followUpDraft: true,
      followUpReviewed: true,
    });

    const callsBeforeBlockedSave = fetchMock.mock.calls.length;
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeBlockedSave);

    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(true);
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
      expectedLockVersion: 5,
      liveNotes: "Reviewed local live note",
      enhancedNotes: "Remote enhanced note",
      followUpDraft: savedWorkspace.followUpDraft,
      followUpReviewed: true,
      generationFingerprint: "b".repeat(64),
      importFromBrowser: false,
    });
    expect(result.current.workspace?.lockVersion).toBe(6);
    expect(result.current.values).toMatchObject({
      liveNotes: "Reviewed local live note",
      enhancedNotes: "Remote enhanced note",
      followUpDraft: savedWorkspace.followUpDraft,
      followUpReviewed: true,
    });
    expect(result.current.saveState).toBe("saved");
    expect(result.current.conflictRecovery.state).toBe("idle");
  });

  it("preserves browser-import provenance through reviewed conflict recovery", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      followUpDraft: "Latest saved follow-up",
    };
    const importedDraft = "Verified owner-tagged browser draft";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
          followUpDraft: importedDraft,
          importedFromBrowserAt: "2026-10-31T00:02:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      expect(
        await result.current.save(
          { followUpDraft: importedDraft, followUpReviewed: false },
          { importFromBrowser: true },
        ),
      ).toBe(false);
    });
    expect(result.current.conflictRecovery.importFromBrowser).toBe(true);

    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(true);
    });
    expect(
      JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body)),
    ).toMatchObject({
      expectedLockVersion: 5,
      followUpDraft: importedDraft,
      importFromBrowser: true,
    });
  });

  it("requires a fresh read before using latest after a reviewed save request fails", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Latest saved note remains available after the failure.",
    };
    const refreshedWorkspace = {
      ...latestWorkspace,
      lockVersion: 6,
      liveNotes: "Freshly read note after the ambiguous save failure.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
        response(
          {
            code: "workspace_save_unavailable",
            message: "The reviewed version could not be saved.",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(response(refreshedWorkspace));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Local reviewed note",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("failed");
    expect(result.current.conflictRecovery.latestWorkspace?.lockVersion).toBe(
      5,
    );

    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(false);
    });
    act(() => {
      expect(result.current.useLatestConflict()).toBe(false);
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
    await act(async () => {
      expect(await result.current.loadLatestConflict()).toBe(true);
    });
    act(() => {
      expect(result.current.useLatestConflict()).toBe(true);
    });
    expect(result.current.values.liveNotes).toBe(refreshedWorkspace.liveNotes);
    expect(result.current.saveState).toBe("idle");
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it("keeps edits made while the latest conflict snapshot is loading", async () => {
    let resolveLatest!: (value: Response) => void;
    const pendingLatest = new Promise<Response>((resolve) => {
      resolveLatest = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed in another session.",
          },
          409,
        ),
      )
      .mockReturnValueOnce(pendingLatest)
      .mockResolvedValueOnce(
        response({
          ...savedWorkspace,
          lockVersion: 6,
          liveNotes: "Note submitted before the conflict.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Note submitted before the conflict.",
      }));
    });
    let savePromise!: Promise<boolean>;
    act(() => {
      savePromise = result.current.save();
    });
    await waitFor(() =>
      expect(result.current.conflictRecovery.state).toBe("loading"),
    );
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Newer note typed while the latest version loads.",
      }));
    });

    await act(async () => {
      resolveLatest(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          liveNotes: "Latest server note",
        }),
      );
      expect(await savePromise).toBe(false);
    });
    expect(result.current.values.liveNotes).toBe(
      "Newer note typed while the latest version loads.",
    );
    expect(result.current.conflictRecovery.latestValues?.liveNotes).toBe(
      "Latest server note",
    );
    expect(result.current.conflictRecovery.submittedValues?.liveNotes).toBe(
      "Note submitted before the conflict.",
    );
    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(true);
    });
    expect(result.current.values.liveNotes).toBe(
      "Newer note typed while the latest version loads.",
    );
    expect(result.current.dirtyFields.liveNotes).toBe(true);
    expect(
      JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body)),
    ).toMatchObject({
      expectedLockVersion: 5,
      liveNotes: "Note submitted before the conflict.",
    });
  });

  it("keeps newer edits made while a reviewed conflict resolution is saving", async () => {
    let resolveResolution!: (value: Response) => void;
    const pendingResolution = new Promise<Response>((resolve) => {
      resolveResolution = resolve;
    });
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Latest server note",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(savedWorkspace))
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
        .mockReturnValueOnce(pendingResolution),
    );
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Reviewed note submitted for conflict resolution.",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    let resolutionPromise!: Promise<boolean>;
    act(() => {
      resolutionPromise = result.current.saveReviewedConflict();
    });
    await waitFor(() =>
      expect(result.current.conflictRecovery.state).toBe("saving"),
    );
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Newer edit typed while conflict resolution saves.",
      }));
    });

    await act(async () => {
      resolveResolution(
        response({
          ...latestWorkspace,
          lockVersion: 6,
          liveNotes: "Reviewed note submitted for conflict resolution.",
        }),
      );
      expect(await resolutionPromise).toBe(true);
    });
    expect(result.current.workspace?.lockVersion).toBe(6);
    expect(result.current.values.liveNotes).toBe(
      "Newer edit typed while conflict resolution saves.",
    );
    expect(result.current.dirtyFields.liveNotes).toBe(true);
  });

  it("loads a fresh snapshot after a second conflict and after a recovery fetch failure", async () => {
    const firstLatest = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "First latest server note",
    };
    const secondLatest = {
      ...savedWorkspace,
      lockVersion: 6,
      liveNotes: "Second latest server note",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
        response(
          {
            code: "latest_workspace_unavailable",
            message: "The latest private workspace is temporarily unavailable.",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(response(firstLatest))
      .mockResolvedValueOnce(
        response(
          {
            code: "conversation_workspace_conflict",
            message: "This private workspace changed again.",
          },
          409,
        ),
      )
      .mockResolvedValueOnce(response(secondLatest));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Local text survives every recovery attempt.",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("failed");
    expect(result.current.conflictRecovery.latestWorkspace).toBeNull();
    expect(result.current.values.liveNotes).toBe(
      "Local text survives every recovery attempt.",
    );

    await act(async () => {
      expect(await result.current.loadLatestConflict()).toBe(true);
    });
    expect(result.current.conflictRecovery.latestWorkspace?.lockVersion).toBe(
      5,
    );
    await act(async () => {
      expect(await result.current.saveReviewedConflict()).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("ready");
    expect(result.current.conflictRecovery.latestWorkspace?.lockVersion).toBe(
      6,
    );
    expect(result.current.values.liveNotes).toBe(
      "Local text survives every recovery attempt.",
    );
  });

  it("keeps edits made while a save request is in flight", async () => {
    let resolveSave!: (value: Response) => void;
    const pendingSave = new Promise<Response>((resolve) => {
      resolveSave = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockReturnValueOnce(pendingSave);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        enhancedNotes: "Text submitted to the save request",
      }));
    });
    let savePromise!: Promise<boolean>;
    let duplicateSavePromise!: Promise<boolean>;
    act(() => {
      savePromise = result.current.save();
      duplicateSavePromise = result.current.save();
    });
    await expect(duplicateSavePromise).resolves.toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(result.current.saveState).toBe("saving"));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        enhancedNotes: "Newer text typed while the request was pending",
      }));
    });

    await act(async () => {
      resolveSave(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          enhancedNotes: "Text submitted to the save request",
        }),
      );
      expect(await savePromise).toBe(true);
    });

    expect(result.current.workspace?.lockVersion).toBe(5);
    expect(result.current.values.enhancedNotes).toBe(
      "Newer text typed while the request was pending",
    );
    expect(result.current.dirtyFields.enhancedNotes).toBe(true);
  });

  it("does not mark newer follow-up text reviewed when it changes during save", async () => {
    let resolveSave!: (value: Response) => void;
    const pendingSave = new Promise<Response>((resolve) => {
      resolveSave = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockReturnValueOnce(pendingSave);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    let savePromise!: Promise<boolean>;
    act(() => {
      savePromise = result.current.save({ followUpReviewed: true });
    });
    await waitFor(() => expect(result.current.saveState).toBe("saving"));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        followUpDraft: "New follow-up wording typed while review was saving",
        followUpReviewed: false,
      }));
    });

    await act(async () => {
      resolveSave(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          followUpReviewed: true,
        }),
      );
      expect(await savePromise).toBe(true);
    });

    expect(result.current.values.followUpDraft).toBe(
      "New follow-up wording typed while review was saving",
    );
    expect(result.current.values.followUpReviewed).toBe(false);
    expect(result.current.dirtyFields.followUpDraft).toBe(true);
    expect(result.current.dirtyFields.followUpReviewed).toBe(true);
  });

  it("keeps unsaved edits through regenerated defaults and persists an intentional clear", async () => {
    const clearedWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      enhancedNotes: "",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockResolvedValueOnce(response(clearedWorkspace))
      .mockResolvedValueOnce(response(clearedWorkspace));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ generated }: { generated: string }) =>
        useConversationWorkspace({
          interactionId: "interaction-1",
          initialEnhancedNotes: generated,
        }),
      { initialProps: { generated: "Generated version one" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        enhancedNotes: "",
      }));
    });
    rerender({ generated: "Regenerated version two" });
    expect(result.current.values.enhancedNotes).toBe("");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      expect(await result.current.save()).toBe(true);
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      enhancedNotes: "",
    });
    await act(async () => {
      await result.current.reload();
    });
    expect(result.current.values.enhancedNotes).toBe("");
  });

  it("uses field defaults when a saved live-note row has null draft fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          ...savedWorkspace,
          liveNotes: "A saved rough note",
          enhancedNotes: null,
          followUpDraft: null,
          generationFingerprint: null,
          generationState: "not_started",
          generationId: null,
          generationTranscriptVersion: null,
          generationPersonalNotesState: "not_included",
          generationCompletedAt: null,
        }),
      ),
    );
    const { result } = renderHook(() =>
      useConversationWorkspace({
        interactionId: "interaction-1",
        initialEnhancedNotes: "Reviewed debrief notes",
        initialFollowUpDraft: "Reviewed debrief follow-up",
      }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values).toMatchObject({
      liveNotes: "A saved rough note",
      enhancedNotes: "Reviewed debrief notes",
      followUpDraft: "Reviewed debrief follow-up",
    });
  });

  it("shows an authoritative empty latest field instead of a generated local default", async () => {
    const serverWithoutDraft = {
      ...savedWorkspace,
      followUpDraft: null,
      followUpReviewed: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(serverWithoutDraft))
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
          ...serverWithoutDraft,
          lockVersion: 5,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({
        interactionId: "interaction-1",
        initialFollowUpDraft: "Unsaved generated local follow-up",
      }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.followUpDraft).toBe(
      "Unsaved generated local follow-up",
    );
    await act(async () => {
      expect(await result.current.save({ followUpReviewed: false })).toBe(
        false,
      );
    });

    expect(result.current.values.followUpDraft).toBe(
      "Unsaved generated local follow-up",
    );
    expect(result.current.conflictRecovery.latestValues?.followUpDraft).toBe(
      "",
    );
    expect(result.current.conflictRecovery.submittedFields.followUpDraft).toBe(
      true,
    );
  });

  it("refreshes generation metadata without replacing dirty local text", async () => {
    const pendingWorkspace = {
      ...savedWorkspace,
      generationState: "processing",
      generationId: "generation-2",
      generationTranscriptVersion: 2,
      generationPersonalNotesState: "current",
      generationUpdateAvailable: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(pendingWorkspace))
      .mockResolvedValueOnce(
        response({
          ...pendingWorkspace,
          lockVersion: 5,
          enhancedNotes: "New server-generated notes",
          followUpDraft: "New server-generated follow-up",
          generationState: "ready",
          generationUpdateAvailable: true,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        enhancedNotes: "Keep my unsaved local edit",
      }));
    });
    expect(result.current.isDirty).toBe(true);

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.workspace?.generationState).toBe("ready");
    expect(result.current.workspace?.generationUpdateAvailable).toBe(true);
    expect(result.current.workspace?.lockVersion).toBe(4);
    expect(result.current.values.enhancedNotes).toBe(
      "Keep my unsaved local edit",
    );
    expect(result.current.values.followUpDraft).toBe(
      savedWorkspace.followUpDraft,
    );
  });

  it("retries a failed private generation without changing the current draft", async () => {
    const failedWorkspace = {
      ...savedWorkspace,
      generationState: "failed",
      generationFailureCode: "draft_intelligence_generation_failed",
      generationRetryAvailable: true,
      generationCompletedAt: "2026-10-31T00:01:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(failedWorkspace))
      .mockResolvedValueOnce(
        response({
          ...failedWorkspace,
          lockVersion: 5,
          enhancedNotes: "Changed in another session",
          generationState: "pending",
          generationFailureCode: null,
          generationRetryAvailable: false,
          generationCompletedAt: null,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      expect(await result.current.retryGeneration()).toBe(true);
    });

    expect(fetchMock.mock.calls[1][0]).toContain(
      "/personal-workspace/generation/retry",
    );
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
    expect(result.current.workspace?.generationState).toBe("pending");
    expect(result.current.workspace?.lockVersion).toBe(4);
    expect(result.current.values.enhancedNotes).toBe(
      savedWorkspace.enhancedNotes,
    );
  });

  it("explicitly applies a later generated version while preserving unsaved live notes", async () => {
    const updateWorkspace = {
      ...savedWorkspace,
      generationId: "generation-2",
      generationTranscriptVersion: 2,
      generationUpdateAvailable: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(updateWorkspace))
      .mockResolvedValueOnce(
        response({
          ...updateWorkspace,
          lockVersion: 5,
          enhancedNotes: "Corrected generated notes",
          followUpDraft: "Corrected private follow-up",
          generationFingerprint: "b".repeat(64),
          generationUpdateAvailable: false,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Unsaved rough-note wording stays in this browser",
      }));
    });
    await act(async () => {
      expect(await result.current.applyGeneratedVersion()).toBe(true);
    });

    expect(fetchMock.mock.calls[1][0]).toContain(
      "/personal-workspace/generation/apply",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      generationId: "generation-2",
      expectedLockVersion: 4,
    });
    expect(result.current.values).toMatchObject({
      liveNotes: "Unsaved rough-note wording stays in this browser",
      enhancedNotes: "Corrected generated notes",
      followUpDraft: "Corrected private follow-up",
    });
    expect(result.current.dirtyFields.liveNotes).toBe(true);
  });

  it("reloads another mounted editor when its refresh key changes", async () => {
    const refreshedWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: savedWorkspace.liveNotes,
      enhancedNotes: "Corrected generated notes",
      followUpDraft: "Corrected private follow-up",
      generationFingerprint: "b".repeat(64),
      generationUpdateAvailable: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockResolvedValueOnce(response(refreshedWorkspace));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ refreshKey }: { refreshKey: number }) =>
        useConversationWorkspace({
          interactionId: "interaction-1",
          refreshKey,
        }),
      { initialProps: { refreshKey: 0 } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ refreshKey: 1 });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(result.current.values).toMatchObject({
        liveNotes: savedWorkspace.liveNotes,
        enhancedNotes: "Corrected generated notes",
        followUpDraft: "Corrected private follow-up",
      }),
    );
  });

  it("keeps a conflict and local text when its refresh key changes", async () => {
    const latestWorkspace = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Latest note saved in another session",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
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
          generationState: "processing",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ refreshKey }: { refreshKey: number }) =>
        useConversationWorkspace({
          interactionId: "interaction-1",
          refreshKey,
        }),
      { initialProps: { refreshKey: 0 } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Unsaved local note that must stay visible",
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("ready");

    rerender({ refreshKey: 1 });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(result.current.saveState).toBe("conflict");
    expect(result.current.values.liveNotes).toBe(
      "Unsaved local note that must stay visible",
    );
    expect(result.current.workspace?.lockVersion).toBe(4);
    expect(result.current.workspace?.generationState).toBe("processing");
    expect(result.current.conflictRecovery).toMatchObject({
      state: "ready",
      latestWorkspace: { lockVersion: 5 },
      latestValues: {
        liveNotes: "Latest note saved in another session",
      },
    });
  });
});
