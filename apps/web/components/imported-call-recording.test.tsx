import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ImportedCallRecording,
  selectedRecordingMimeType,
} from "@/components/imported-call-recording";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const recording = {
  id: "recording-1",
  interactionId: "interaction-1",
  captureSessionId: "capture-1",
  recordingType: "imported_audio_recording",
  recordingSource: "user_uploaded_recording",
  lifecycleStatus: "uploaded",
  consentState: "acknowledged",
  startedAt: "2026-08-15T00:00:00Z",
  stoppedAt: null,
  durationSeconds: 45,
  expectedMimeType: "audio/webm",
  finalMimeType: "audio/webm",
  totalBytes: 32,
  chunkCount: 1,
  uploadCompletedAt: "2026-08-15T00:01:00Z",
  transcriptionStatus: "queued",
  transcriptionAttempts: 0,
  failureCode: null,
  autoIntelligenceStatus: "disabled",
  sessionExpiresAt: "2026-08-16T00:00:00Z",
  providerMode: "mock",
  externalProcessing: false,
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:01:00Z",
};

describe("ImportedCallRecording", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("accepts only the existing recording allowlist", () => {
    expect(
      selectedRecordingMimeType(new File(["audio"], "call.m4a", { type: "" })),
    ).toBe("audio/m4a");
    expect(
      selectedRecordingMimeType(
        new File(["audio"], "call.wav", { type: "audio/wav" }),
      ),
    ).toBeNull();
    expect(
      selectedRecordingMimeType(
        new File(["audio"], "mislabelled.webm", { type: "audio/wav" }),
      ),
    ).toBeNull();
  });

  it("rejects an oversized authorised recording before any network request", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(jsonResponse([])),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ImportedCallRecording interactionId="interaction-1" />);
    const file = new File(["audio"], "call.webm", { type: "audio/webm" });
    Object.defineProperty(file, "size", { value: 512 * 1024 * 1024 + 1 });
    fireEvent.change(screen.getByLabelText("Audio file"), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Call duration in seconds"), {
      target: { value: "60" },
    });
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /authorised business interaction/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Import recording" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "no larger than 512 MiB",
    );
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);
  });

  it("requires authority and imports through the existing resumable recording path", async () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "request-id"),
      subtle: {
        digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
      },
    });
    const calls: Array<{ path: string; body: string }> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      calls.push({ path, body: String(init?.body ?? "") });
      if (path.endsWith("/recordings") && !init?.method) {
        return Promise.resolve(jsonResponse([]));
      }
      if (path.endsWith("/recordings") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(
            { ...recording, lifecycleStatus: "created", finalMimeType: null },
            201,
          ),
        );
      }
      if (path.endsWith("/start")) {
        return Promise.resolve(
          jsonResponse({
            ...recording,
            lifecycleStatus: "uploading",
            finalMimeType: null,
          }),
        );
      }
      if (path.endsWith("/chunks") && init?.method === "POST") {
        const request = JSON.parse(String(init.body)) as {
          sequenceNumber: number;
          byteSize: number;
          checksumSha256: string;
        };
        return Promise.resolve(
          jsonResponse(
            {
              id: "chunk-1",
              recordingSessionId: "recording-1",
              sequenceNumber: request.sequenceNumber,
              byteSize: request.byteSize,
              checksumSha256: request.checksumSha256,
              uploadState: "pending",
              uploadedAt: null,
              createdAt: "2026-08-15T00:00:00Z",
              uploadUrl: "/private-call-upload",
              uploadExpiresAt: "2026-08-15T00:05:00Z",
            },
            201,
          ),
        );
      }
      if (path.endsWith("/private-call-upload")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (path.endsWith("/complete")) {
        return Promise.resolve(jsonResponse({ uploadState: "verified" }));
      }
      if (path.endsWith("/finalize")) {
        return Promise.resolve(jsonResponse(recording));
      }
      return Promise.resolve(jsonResponse({ message: path }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ImportedCallRecording interactionId="interaction-1" />);
    const file = new File(
      [new Uint8Array([0x1a, 0x45, 0xdf, 0xa3])],
      "call.webm",
      {
        type: "audio/webm",
      },
    );
    fireEvent.change(screen.getByLabelText("Audio file"), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Call duration in seconds"), {
      target: { value: "45" },
    });
    const submit = screen.getByRole("button", { name: "Import recording" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /authorised business interaction/i,
      }),
    );
    fireEvent.click(submit);

    expect(
      await screen.findByText("Recording imported securely"),
    ).toBeVisible();
    const create = calls.find(
      (call) => call.path.endsWith("/recordings") && call.body.length > 0,
    );
    expect(JSON.parse(create?.body ?? "{}")).toMatchObject({
      recordingType: "imported_audio_recording",
      recordingSource: "user_uploaded_recording",
      consentMethod: "contractual_authority",
      userAttestedAuthority: true,
    });
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/finalize"))).toBe(true),
    );
    expect(
      screen.queryByRole("button", { name: /play/i }),
    ).not.toBeInTheDocument();
  });

  it.each(["create", "start"] as const)(
    "rejects a foreign %s response before reserving or uploading a chunk",
    async (mismatchStage) => {
      vi.stubGlobal("crypto", {
        randomUUID: vi.fn(() => "request-id"),
        subtle: {
          digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
        },
      });
      const foreignUploadUrl =
        "https://foreign-upload.example/imported-lifecycle-chunk";
      const validCreated = {
        ...recording,
        lifecycleStatus: "created",
        finalMimeType: null,
      };
      const foreignSession = {
        ...validCreated,
        id: "recording-foreign",
        interactionId: "interaction-foreign",
        captureSessionId: "capture-foreign",
      };
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const path = String(input);
          const method = init?.method ?? "GET";
          if (path.endsWith("/recordings") && method === "GET") {
            return Promise.resolve(jsonResponse([]));
          }
          if (path.endsWith("/recordings") && method === "POST") {
            return Promise.resolve(
              jsonResponse(
                mismatchStage === "create" ? foreignSession : validCreated,
                201,
              ),
            );
          }
          if (path.endsWith("/start") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...foreignSession,
                lifecycleStatus: "uploading",
              }),
            );
          }
          if (path.endsWith("/chunks") && method === "POST") {
            const request = JSON.parse(String(init?.body)) as {
              sequenceNumber: number;
              byteSize: number;
              checksumSha256: string;
            };
            return Promise.resolve(
              jsonResponse(
                {
                  id: "chunk-foreign",
                  recordingSessionId: foreignSession.id,
                  sequenceNumber: request.sequenceNumber,
                  byteSize: request.byteSize,
                  checksumSha256: request.checksumSha256,
                  uploadState: "pending",
                  uploadedAt: null,
                  createdAt: "2026-08-15T00:00:00Z",
                  uploadUrl: foreignUploadUrl,
                  uploadExpiresAt: "2026-08-15T00:05:00Z",
                },
                201,
              ),
            );
          }
          if (path.endsWith("/cancel") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...validCreated,
                lifecycleStatus: "cancelled",
              }),
            );
          }
          if (path === foreignUploadUrl && method === "PUT") {
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: path }, 500),
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(<ImportedCallRecording interactionId="interaction-1" />);
      const file = new File(
        [new Uint8Array([0x1a, 0x45, 0xdf, 0xa3])],
        "call.webm",
        { type: "audio/webm" },
      );
      fireEvent.change(screen.getByLabelText("Audio file"), {
        target: { files: [file] },
      });
      fireEvent.change(screen.getByLabelText("Call duration in seconds"), {
        target: { value: "45" },
      });
      fireEvent.click(
        screen.getByRole("checkbox", {
          name: /authorised business interaction/i,
        }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Import recording" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The recording response did not match this interaction. Try again.",
      );
      expect(screen.getByText("call.webm")).toBeVisible();
      expect(
        screen.getByRole("checkbox", {
          name: /authorised business interaction/i,
        }),
      ).toBeChecked();
      expect(
        screen.getByRole("button", { name: "Import recording" }),
      ).toBeEnabled();
      expect(
        screen.queryByText("Recording imported securely"),
      ).not.toBeInTheDocument();
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/chunks"),
        ),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(
          ([input]) => String(input) === foreignUploadUrl,
        ),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(([input]) =>
          /\/(complete|finalize)$/u.test(String(input)),
        ),
      ).toBe(false);
      const cancelPaths = fetchMock.mock.calls
        .filter(
          ([input, init]) =>
            String(input).endsWith("/cancel") && init?.method === "POST",
        )
        .map(([input]) => String(input));
      expect(cancelPaths).toHaveLength(mismatchStage === "start" ? 1 : 0);
      if (mismatchStage === "start") {
        expect(cancelPaths[0]).toMatch(
          /\/interactions\/interaction-1\/recordings\/recording-1\/cancel$/u,
        );
      }
      expect(
        cancelPaths.some((path) => path.includes("recording-foreign")),
      ).toBe(false);
    },
  );

  it.each([
    {
      mismatch: "foreign recording session",
      responseOverride: { recordingSessionId: "recording-foreign" },
    },
    {
      mismatch: "wrong sequence",
      responseOverride: { sequenceNumber: 1 },
    },
    {
      mismatch: "wrong checksum",
      responseOverride: { checksumSha256: "f".repeat(64) },
    },
  ])(
    "rejects a $mismatch chunk ticket before importing bytes",
    async ({ responseOverride }) => {
      vi.stubGlobal("crypto", {
        randomUUID: vi.fn(() => "request-id"),
        subtle: {
          digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
        },
      });
      const foreignUploadUrl =
        "https://foreign-upload.example/imported-recording-chunk";
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const path = String(input);
          const method = init?.method ?? "GET";
          if (path.endsWith("/recordings") && method === "GET") {
            return Promise.resolve(jsonResponse([]));
          }
          if (path.endsWith("/recordings") && method === "POST") {
            return Promise.resolve(
              jsonResponse(
                {
                  ...recording,
                  lifecycleStatus: "created",
                  finalMimeType: null,
                },
                201,
              ),
            );
          }
          if (path.endsWith("/start") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...recording,
                lifecycleStatus: "uploading",
                finalMimeType: null,
              }),
            );
          }
          if (path.endsWith("/chunks") && method === "POST") {
            const request = JSON.parse(String(init?.body)) as {
              sequenceNumber: number;
              byteSize: number;
              checksumSha256: string;
            };
            return Promise.resolve(
              jsonResponse(
                {
                  id: "chunk-foreign",
                  recordingSessionId: recording.id,
                  sequenceNumber: request.sequenceNumber,
                  byteSize: request.byteSize,
                  checksumSha256: request.checksumSha256,
                  uploadState: "pending",
                  uploadedAt: null,
                  createdAt: "2026-08-15T00:00:00Z",
                  uploadUrl: foreignUploadUrl,
                  uploadExpiresAt: "2026-08-15T00:05:00Z",
                  ...responseOverride,
                },
                201,
              ),
            );
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: path }, 500),
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(<ImportedCallRecording interactionId="interaction-1" />);
      const file = new File(
        [new Uint8Array([0x1a, 0x45, 0xdf, 0xa3])],
        "call.webm",
        { type: "audio/webm" },
      );
      fireEvent.change(screen.getByLabelText("Audio file"), {
        target: { files: [file] },
      });
      fireEvent.change(screen.getByLabelText("Call duration in seconds"), {
        target: { value: "45" },
      });
      fireEvent.click(
        screen.getByRole("checkbox", {
          name: /authorised business interaction/i,
        }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Import recording" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The recording upload could not be verified. Try again.",
      );
      expect(
        fetchMock.mock.calls.some(
          ([input]) => String(input) === foreignUploadUrl,
        ),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(([input]) =>
          /\/(complete|finalize)$/u.test(String(input)),
        ),
      ).toBe(false);
      expect(
        screen.getByRole("button", { name: "Import recording" }),
      ).toBeEnabled();
    },
  );
});
