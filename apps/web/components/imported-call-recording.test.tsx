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
          jsonResponse({ ...recording, lifecycleStatus: "created" }, 201),
        );
      }
      if (path.endsWith("/start")) {
        return Promise.resolve(
          jsonResponse({ ...recording, lifecycleStatus: "uploading" }),
        );
      }
      if (path.endsWith("/chunks") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(
            {
              id: "chunk-1",
              recordingSessionId: "recording-1",
              sequenceNumber: 0,
              byteSize: 8,
              checksumSha256: "0".repeat(64),
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
});
