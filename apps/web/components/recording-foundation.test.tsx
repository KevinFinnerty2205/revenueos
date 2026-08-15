import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  RecordingFoundation,
  selectSupportedRecordingMimeType,
} from "@/components/recording-foundation";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const baseRecording = {
  id: "recording-1",
  interactionId: "interaction-1",
  captureSessionId: "capture-1",
  recordingType: "live_audio_recording",
  lifecycleStatus: "created",
  consentState: "acknowledged",
  startedAt: null,
  stoppedAt: null,
  durationSeconds: null,
  expectedMimeType: "audio/webm",
  finalMimeType: null,
  totalBytes: 0,
  chunkCount: 0,
  uploadCompletedAt: null,
  transcriptionStatus: "disabled",
  transcriptionAttempts: 0,
  failureCode: null,
  autoIntelligenceStatus: "disabled",
  sessionExpiresAt: "2026-08-16T00:00:00Z",
  providerMode: "mock",
  externalProcessing: false,
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:00:00Z",
};

class FakeMediaRecorder {
  static isTypeSupported(mimeType: string): boolean {
    return mimeType === "audio/webm;codecs=opus";
  }

  state: RecordingState = "inactive";
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onstop: ((event: Event) => void) | null = null;

  constructor(
    readonly stream: MediaStream,
    readonly options?: MediaRecorderOptions,
  ) {}

  start(): void {
    this.state = "recording";
  }

  pause(): void {
    this.state = "paused";
  }

  resume(): void {
    this.state = "recording";
  }

  stop(): void {
    this.state = "inactive";
    const bytes = new TextEncoder().encode("MOCK_TRANSCRIPT:Browser test.");
    const content = new Uint8Array(4 + bytes.length);
    content.set([0x1a, 0x45, 0xdf, 0xa3]);
    content.set(bytes, 4);
    const data = new Blob([content], { type: "audio/webm" });
    Object.defineProperty(data, "arrayBuffer", {
      value: () => Promise.resolve(content.buffer),
    });
    this.ondataavailable?.({ data } as BlobEvent);
    this.onstop?.(new Event("stop"));
  }
}

function installSupportedBrowser(
  getUserMedia: () => Promise<MediaStream>,
): void {
  vi.stubGlobal(
    "MediaRecorder",
    FakeMediaRecorder as unknown as typeof MediaRecorder,
  );
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia },
  });
}

describe("RecordingFoundation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("feature-detects the safest supported MIME type in preference order", () => {
    expect(
      selectSupportedRecordingMimeType({
        isTypeSupported: (mimeType) => mimeType.startsWith("audio/mp4"),
      }),
    ).toBe("audio/mp4;codecs=mp4a.40.2");
    expect(selectSupportedRecordingMimeType(undefined)).toBeNull();
  });

  it("shows an accessible Debrief fallback when browser recording is unsupported", async () => {
    vi.stubGlobal("MediaRecorder", undefined);
    vi.stubGlobal("navigator", {});
    render(
      <RecordingFoundation
        interactionId="interaction-1"
        lifecycleStatus="planned"
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "does not expose a supported audio recording format",
    );
    expect(
      screen.getByRole("link", { name: "Use AI Debrief instead" }),
    ).toHaveAttribute("href", "#debrief");
  });

  it("does not begin until consent succeeds and reports denied microphone permission", async () => {
    installSupportedBrowser(() =>
      Promise.reject(new DOMException("Denied", "NotAllowedError")),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    render(
      <RecordingFoundation
        interactionId="interaction-1"
        lifecycleStatus="planned"
      />,
    );
    const start = await screen.findByRole("button", {
      name: "Start recording",
    });
    expect(start).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(start).toBeEnabled();
    fireEvent.click(start);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Microphone access was denied",
    );
    expect(
      screen.getByRole("link", { name: "Use AI Debrief instead" }),
    ).toBeVisible();
  });

  it("starts, pauses, resumes, uploads a chunk and enters transcription processing", async () => {
    const stopTrack = vi.fn();
    installSupportedBrowser(() =>
      Promise.resolve({
        getTracks: () => [{ stop: stopTrack }],
      } as unknown as MediaStream),
    );
    let finalized = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(
          jsonResponse(
            finalized
              ? [
                  {
                    ...baseRecording,
                    lifecycleStatus: "uploaded",
                    transcriptionStatus: "queued",
                  },
                ]
              : [],
          ),
        );
      }
      if (url.endsWith("/recordings") && method === "POST") {
        return Promise.resolve(jsonResponse(baseRecording, 201));
      }
      if (url.endsWith("/start")) {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
        );
      }
      if (url.endsWith("/pause") || url.endsWith("/resume")) {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
        );
      }
      if (url.endsWith("/chunks") && method === "POST") {
        return Promise.resolve(
          jsonResponse(
            {
              id: "chunk-1",
              recordingSessionId: "recording-1",
              sequenceNumber: 0,
              byteSize: 32,
              checksumSha256: "a".repeat(64),
              uploadState: "pending",
              uploadedAt: null,
              createdAt: "2026-08-15T00:00:00Z",
              uploadUrl: "/recording-upload",
              uploadExpiresAt: "2026-08-15T00:05:00Z",
            },
            201,
          ),
        );
      }
      if (url.endsWith("/recording-upload") && method === "PUT") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/complete")) {
        return Promise.resolve(
          jsonResponse({
            id: "chunk-1",
            recordingSessionId: "recording-1",
            sequenceNumber: 0,
            byteSize: 32,
            checksumSha256: "a".repeat(64),
            uploadState: "verified",
            uploadedAt: "2026-08-15T00:01:00Z",
            createdAt: "2026-08-15T00:00:00Z",
          }),
        );
      }
      if (url.endsWith("/stop")) {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "uploading" }),
        );
      }
      if (url.endsWith("/finalize")) {
        finalized = true;
        return Promise.resolve(
          jsonResponse({
            ...baseRecording,
            lifecycleStatus: "uploaded",
            transcriptionStatus: "queued",
          }),
        );
      }
      if (url.endsWith("/transcription")) {
        return Promise.resolve(
          jsonResponse({
            recordingId: "recording-1",
            status: "queued",
            transcriptVersionId: null,
            transcriptId: null,
            meetingId: null,
            version: null,
            source: null,
            language: "en-AU",
            text: null,
            segments: [],
            completedAt: null,
            safeMessage: "The recording is queued for batch transcription.",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: url }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        lifecycleStatus="planned"
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    const pause = await screen.findByRole("button", { name: "Pause" });
    fireEvent.click(pause);
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop and upload" }));

    expect(
      await screen.findByText(
        "The recording is queued for batch transcription.",
      ),
    ).toBeVisible();
    await waitFor(() => expect(stopTrack).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/finalize"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("restores verified chunks and retries finalisation after an interrupted upload", async () => {
    installSupportedBrowser(() => Promise.reject(new Error("not requested")));
    let finalized = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(
          jsonResponse([
            {
              ...baseRecording,
              lifecycleStatus: finalized ? "uploaded" : "uploading",
              durationSeconds: 60,
              finalMimeType: "audio/webm",
              chunkCount: 1,
            },
          ]),
        );
      }
      if (url.endsWith("/chunks")) {
        return Promise.resolve(
          jsonResponse([{ sequenceNumber: 0, uploadState: "verified" }]),
        );
      }
      if (url.endsWith("/finalize")) {
        finalized = true;
        return Promise.resolve(
          jsonResponse({
            ...baseRecording,
            lifecycleStatus: "uploaded",
            durationSeconds: 60,
            finalMimeType: "audio/webm",
            chunkCount: 1,
            transcriptionStatus: "queued",
          }),
        );
      }
      if (url.endsWith("/transcription")) {
        return Promise.resolve(
          jsonResponse({
            recordingId: "recording-1",
            status: "queued",
            transcriptVersionId: null,
            transcriptId: null,
            meetingId: null,
            version: null,
            source: null,
            language: "en-AU",
            text: null,
            segments: [],
            completedAt: null,
            safeMessage: "The recording is queued for batch transcription.",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: url }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        lifecycleStatus="planned"
      />,
    );

    expect(await screen.findByText(/recording was interrupted/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry finalisation" }));
    expect(
      await screen.findByText(
        "The recording is queued for batch transcription.",
      ),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/finalize"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
