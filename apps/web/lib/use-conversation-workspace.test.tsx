import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useConversationWorkspace } from "@/lib/use-conversation-workspace";

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

  it("redacts the previous interaction synchronously and blocks a pre-load save", async () => {
    const interactionB = deferred<Response>();
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 9,
      liveNotes: null,
      enhancedNotes: null,
      followUpDraft: null,
    };
    const savedB = {
      ...workspaceB,
      lockVersion: 10,
      liveNotes: "New B note",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => interactionB.promise)
      .mockResolvedValueOnce(response(savedB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({
        interactionId,
        initialLiveNotes,
        initialEnhancedNotes,
        initialFollowUpDraft,
      }) =>
        useConversationWorkspace({
          interactionId,
          initialLiveNotes,
          initialEnhancedNotes,
          initialFollowUpDraft,
        }),
      {
        initialProps: {
          interactionId: "interaction-a",
          initialLiveNotes: "Stale A rough notes",
          initialEnhancedNotes: "Stale A enhanced notes",
          initialFollowUpDraft: "Stale A follow-up",
        },
      },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(savedWorkspace.liveNotes);

    rerender({
      interactionId: "interaction-b",
      initialLiveNotes: "Stale A rough notes",
      initialEnhancedNotes: "Stale A enhanced notes",
      initialFollowUpDraft: "Stale A follow-up",
    });

    expect(result.current.loading).toBe(true);
    expect(result.current.workspace).toBeNull();
    expect(result.current.values).toEqual({
      liveNotes: "",
      enhancedNotes: "",
      followUpDraft: "",
      followUpReviewed: false,
    });
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(false);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await act(async () => interactionB.resolve(response(workspaceB)));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values).toEqual({
      liveNotes: "",
      enhancedNotes: "",
      followUpDraft: "",
      followUpReviewed: false,
    });
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: savedB.liveNotes,
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(true);
    });
    const bBody = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body));
    expect(bBody).toMatchObject({
      liveNotes: savedB.liveNotes,
      enhancedNotes: "",
      followUpDraft: "",
    });
    expect(JSON.stringify(bBody)).not.toContain("Stale A");
  });

  it("does not promote a new interaction before its blank state is committed", async () => {
    const interactionBReads: Array<ReturnType<typeof deferred<Response>>> = [];
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 8,
      liveNotes: "Interaction B notes",
      enhancedNotes: "Interaction B enhanced notes",
      followUpDraft: "Interaction B follow-up",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(response(workspaceB));
      }
      if (String(input).includes("interaction-a")) {
        return Promise.resolve(response(savedWorkspace));
      }
      const read = deferred<Response>();
      interactionBReads.push(read);
      return read.promise;
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ interactionId: "interaction-b" });

    let reloadPromise: Promise<void> | undefined;
    let savePromise: Promise<boolean> | undefined;
    act(() => {
      reloadPromise = result.current.reload();
      savePromise = result.current.save();
    });

    await expect(savePromise).resolves.toBe(false);
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(false);

    await waitFor(() => expect(interactionBReads.length).toBeGreaterThan(0));
    await act(async () => {
      for (const read of interactionBReads) read.resolve(response(workspaceB));
      await reloadPromise;
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(false);
  });

  it("ignores a delayed load from the previous interaction", async () => {
    const interactionA = deferred<Response>();
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 8,
      liveNotes: "Interaction B remains authoritative",
    };
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => interactionA.promise)
      .mockResolvedValueOnce(response(workspaceB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);

    await act(async () => interactionA.resolve(response(savedWorkspace)));
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);
    expect(result.current.workspace?.lockVersion).toBe(8);
  });

  it("starts a fresh session when navigating away and back to the same interaction", async () => {
    const interactionB = deferred<Response>();
    const secondInteractionA = deferred<Response>();
    const refreshedA = {
      ...savedWorkspace,
      lockVersion: 10,
      liveNotes: "Fresh A notes after returning",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => interactionB.promise)
      .mockImplementationOnce(() => secondInteractionA.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Unsaved A text that must not be restored",
      }));
    });

    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    rerender({ interactionId: "interaction-a" });

    expect(result.current.workspace).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(result.current.values.liveNotes).toBe("");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await act(async () => secondInteractionA.resolve(response(refreshedA)));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(refreshedA.liveNotes);

    await act(async () =>
      interactionB.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 99,
          liveNotes: "Late B text",
        }),
      ),
    );
    expect(result.current.values.liveNotes).toBe(refreshedA.liveNotes);
  });

  it("ignores an old save completion and keeps later saves bound to the new interaction", async () => {
    const saveA = deferred<Response>();
    const saveB = deferred<Response>();
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 11,
      liveNotes: "Interaction B notes",
      enhancedNotes: "Interaction B enhanced notes",
      followUpDraft: "Interaction B follow-up",
    };
    const savedB = {
      ...workspaceB,
      lockVersion: 12,
      liveNotes: "Interaction B edited notes",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => saveA.promise)
      .mockResolvedValueOnce(response(workspaceB))
      .mockImplementationOnce(() => saveB.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: "Unsaved A notes",
      }));
    });
    let oldSave: Promise<boolean> | undefined;
    act(() => {
      oldSave = result.current.save();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);

    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: savedB.liveNotes,
      }));
    });
    let newSave: Promise<boolean> | undefined;
    act(() => {
      newSave = result.current.save();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));

    await act(async () =>
      saveA.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          liveNotes: "Saved A notes",
        }),
      ),
    );
    await expect(oldSave).resolves.toBe(false);
    await act(async () => {
      expect(await result.current.save()).toBe(false);
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);

    await act(async () => saveB.resolve(response(savedB)));
    await expect(newSave).resolves.toBe(true);
    expect(result.current.values.liveNotes).toBe(savedB.liveNotes);
    const bSaveBody = JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body));
    expect(fetchMock.mock.calls[3]?.[0]).toContain("interaction-b");
    expect(bSaveBody).toMatchObject({
      expectedLockVersion: 11,
      liveNotes: savedB.liveNotes,
      enhancedNotes: workspaceB.enhancedNotes,
      followUpDraft: workspaceB.followUpDraft,
    });
    expect(JSON.stringify(bSaveBody)).not.toContain("Unsaved A notes");
  });

  it("ignores a delayed conflict snapshot from the previous interaction", async () => {
    const conflictA = deferred<Response>();
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 15,
      liveNotes: "Private B notes",
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
      .mockImplementationOnce(() => conflictA.promise)
      .mockResolvedValueOnce(response(workspaceB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    let oldSave: Promise<boolean> | undefined;
    act(() => {
      oldSave = result.current.save({ liveNotes: "Conflicting A text" });
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () =>
      conflictA.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 6,
          liveNotes: "Latest A conflict text",
        }),
      ),
    );
    await expect(oldSave).resolves.toBe(false);
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);
    expect(result.current.saveState).toBe("idle");
    expect(result.current.conflictRecovery.state).toBe("idle");
  });

  it("keeps retained conflict actions bound to their original interaction", async () => {
    const latestA = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Latest private A conflict text",
    };
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 15,
      liveNotes: "Private B notes",
      enhancedNotes: "Private B enhanced notes",
      followUpDraft: "Private B follow-up",
    };
    const savedB = {
      ...workspaceB,
      lockVersion: 16,
      liveNotes: "Edited private B notes",
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
      .mockResolvedValueOnce(response(latestA))
      .mockResolvedValueOnce(response(workspaceB))
      .mockResolvedValueOnce(response(savedB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      expect(
        await result.current.save({ liveNotes: "Submitted private A text" }),
      ).toBe(false);
    });
    expect(result.current.conflictRecovery.state).toBe("ready");
    const useOldLatest = result.current.useLatestConflict;
    const reloadOldLatest = result.current.loadLatestConflict;

    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);

    act(() => {
      expect(useOldLatest()).toBe(false);
    });
    await act(async () => {
      expect(await reloadOldLatest()).toBe(false);
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);
    expect(result.current.workspace?.lockVersion).toBe(workspaceB.lockVersion);

    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: savedB.liveNotes,
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(true);
    });
    const bBody = JSON.parse(String(fetchMock.mock.calls[4]?.[1]?.body));
    expect(fetchMock.mock.calls[4]?.[0]).toContain("interaction-b");
    expect(bBody).toMatchObject({
      expectedLockVersion: workspaceB.lockVersion,
      liveNotes: savedB.liveNotes,
      enhancedNotes: workspaceB.enhancedNotes,
      followUpDraft: workspaceB.followUpDraft,
    });
    expect(JSON.stringify(bBody)).not.toContain("private A");
  });

  it("ignores a delayed generation retry from the previous interaction", async () => {
    const retryA = deferred<Response>();
    const retryableA = {
      ...savedWorkspace,
      generationState: "failed" as const,
      generationRetryAvailable: true,
    };
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 20,
      liveNotes: "B remains visible after A retry",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(retryableA))
      .mockImplementationOnce(() => retryA.promise)
      .mockResolvedValueOnce(response(workspaceB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    let oldRetry: Promise<boolean> | undefined;
    act(() => {
      oldRetry = result.current.retryGeneration();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () =>
      retryA.resolve(
        response({
          ...retryableA,
          generationState: "pending",
          generationRetryAvailable: false,
        }),
      ),
    );
    await expect(oldRetry).resolves.toBe(false);
    expect(result.current.values.liveNotes).toBe(workspaceB.liveNotes);
    expect(result.current.workspace?.lockVersion).toBe(20);
  });

  it("ignores a delayed generated-version apply from the previous interaction", async () => {
    const applyA = deferred<Response>();
    const applicableA = {
      ...savedWorkspace,
      generationId: "generation-2",
      generationUpdateAvailable: true,
    };
    const workspaceB = {
      ...savedWorkspace,
      lockVersion: 21,
      enhancedNotes: "B enhanced notes stay visible",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(applicableA))
      .mockImplementationOnce(() => applyA.promise)
      .mockResolvedValueOnce(response(workspaceB));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(
      ({ interactionId }) => useConversationWorkspace({ interactionId }),
      { initialProps: { interactionId: "interaction-a" } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    let oldApply: Promise<boolean> | undefined;
    act(() => {
      oldApply = result.current.applyGeneratedVersion();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    rerender({ interactionId: "interaction-b" });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () =>
      applyA.resolve(
        response({
          ...applicableA,
          lockVersion: 5,
          enhancedNotes: "Applied A enhanced notes",
          generationUpdateAvailable: false,
        }),
      ),
    );
    await expect(oldApply).resolves.toBe(false);
    expect(result.current.values.enhancedNotes).toBe(workspaceB.enhancedNotes);
    expect(result.current.workspace?.lockVersion).toBe(21);
  });

  it("keeps the newest same-interaction refresh authoritative", async () => {
    const firstRefresh = deferred<Response>();
    const secondRefresh = deferred<Response>();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => firstRefresh.promise)
      .mockImplementationOnce(() => secondRefresh.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      void result.current.refresh();
      void result.current.refresh();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    await act(async () =>
      secondRefresh.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 6,
          liveNotes: "Newest refresh",
        }),
      ),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.values.liveNotes).toBe("Newest refresh");

    await act(async () =>
      firstRefresh.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 5,
          liveNotes: "Older refresh",
        }),
      ),
    );
    expect(result.current.values.liveNotes).toBe("Newest refresh");
    expect(result.current.workspace?.lockVersion).toBe(6);
  });

  it("does not let an older refresh overwrite a later save", async () => {
    const staleRefresh = deferred<Response>();
    const savedAfterRefresh = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Saved after refresh started",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => staleRefresh.promise)
      .mockResolvedValueOnce(response(savedAfterRefresh));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      void result.current.refresh();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: savedAfterRefresh.liveNotes,
      }));
    });
    await act(async () => {
      expect(await result.current.save()).toBe(true);
    });
    expect(result.current.workspace?.lockVersion).toBe(5);

    await act(async () =>
      staleRefresh.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 99,
          liveNotes: "Stale refresh text",
        }),
      ),
    );
    expect(result.current.values.liveNotes).toBe(savedAfterRefresh.liveNotes);
    expect(result.current.workspace?.lockVersion).toBe(5);
  });

  it("ignores a refresh snapshot that started while a save was in flight", async () => {
    const pendingSave = deferred<Response>();
    const overlappingRefresh = deferred<Response>();
    const saved = {
      ...savedWorkspace,
      lockVersion: 5,
      liveNotes: "Authoritative saved text",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(savedWorkspace))
      .mockImplementationOnce(() => pendingSave.promise)
      .mockImplementationOnce(() => overlappingRefresh.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useConversationWorkspace({ interactionId: "interaction-1" }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.setValues((current) => ({
        ...current,
        liveNotes: saved.liveNotes,
      }));
    });
    let savePromise: Promise<boolean> | undefined;
    let refreshPromise: Promise<void> | undefined;
    act(() => {
      savePromise = result.current.save();
      refreshPromise = result.current.refresh();
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    await act(async () => pendingSave.resolve(response(saved)));
    await expect(savePromise).resolves.toBe(true);
    expect(result.current.workspace?.lockVersion).toBe(5);

    await act(async () =>
      overlappingRefresh.resolve(
        response({
          ...savedWorkspace,
          lockVersion: 4,
          liveNotes: "Stale pre-save snapshot",
        }),
      ),
    );
    await refreshPromise;
    expect(result.current.values.liveNotes).toBe(saved.liveNotes);
    expect(result.current.workspace?.lockVersion).toBe(5);
  });
});
