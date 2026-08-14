import { afterEach, describe, expect, it, vi } from "vitest";
import { apiUpload, configureApiTokenProvider } from "@/lib/api";

describe("private object upload", () => {
  afterEach(() => {
    configureApiTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("never sends the RevenueOS bearer token to an absolute signed object URL", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiTokenProvider(async () => "revenueos-session-token");

    await apiUpload(
      "https://objects.example.test/private.png?X-Amz-Signature=signed",
      new Blob([new Uint8Array([1, 2, 3])]),
      "image/png",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "https://objects.example.test/private.png?X-Amz-Signature=signed",
      expect.objectContaining({
        method: "PUT",
        headers: { "Content-Type": "image/png" },
      }),
    );
  });
});
