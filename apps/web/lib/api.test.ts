import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClientError, apiRequest } from "@/lib/api";

describe("apiRequest reliability", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("does not preflight bodyless reads with a JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/example");

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.has("Content-Type")).toBe(false);
    expect(headers.get("X-Request-ID")).toBeTruthy();
  });

  it("retries transient reads within a three-attempt bound using one safe request ID", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/api/v1/example")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const first = new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get(
      "X-Request-ID",
    );
    const second = new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get(
      "X-Request-ID",
    );
    const third = new Headers(fetchMock.mock.calls[2]?.[1]?.headers).get(
      "X-Request-ID",
    );
    expect(second).toBe(first);
    expect(third).toBe(first);
  });

  it("does not retry writes and exposes a correlation ID safely", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/api/v1/example", {
      method: "POST",
      body: JSON.stringify({ safe: true }),
    }).catch((reason: unknown) => reason);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(error).toBeInstanceOf(ApiClientError);
    expect(error).toMatchObject({ status: 0, code: "network_error" });
    expect((error as Error).message).toMatch(/Request ID:/u);
  });

  it("normalises an aborted browser read to AbortError", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockImplementation(() => {
      controller.abort();
      return Promise.reject(new TypeError("Failed to fetch"));
    });
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/api/v1/example", {
      signal: controller.signal,
    }).catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(DOMException);
    expect((error as DOMException).name).toBe("AbortError");
  });
});
