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
    expect(result.current.values.enhancedNotes).toBe(
      savedWorkspace.enhancedNotes,
    );
  });

  it("explicitly applies a later generated version while preserving live notes", async () => {
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
      liveNotes: savedWorkspace.liveNotes,
      enhancedNotes: "Corrected generated notes",
      followUpDraft: "Corrected private follow-up",
    });
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
});
