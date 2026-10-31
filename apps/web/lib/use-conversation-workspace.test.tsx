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
  enhancedNotes: "Saved in another browser",
  followUpDraft: "Saved draft — never send automatically.",
  followUpReviewed: false,
  generationFingerprint: "a".repeat(64),
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
});
