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
  static instances: FakeMediaRecorder[] = [];

  static isTypeSupported(mimeType: string): boolean {
    return mimeType === "audio/webm;codecs=opus";
  }

  state: RecordingState = "inactive";
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onstop: ((event: Event) => void) | null = null;
  stopCalls = 0;

  constructor(
    readonly stream: MediaStream,
    readonly options?: MediaRecorderOptions,
  ) {
    FakeMediaRecorder.instances.push(this);
  }

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
    this.stopCalls += 1;
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

class FakeMediaStreamTrack extends EventTarget {
  readonly id = "microphone-track";
  readonly kind = "audio";
  muted = false;
  readyState: MediaStreamTrackState = "live";

  constructor(private readonly onStop: () => void = () => undefined) {
    super();
  }

  getSettings(): MediaTrackSettings {
    return {};
  }

  stop(): void {
    this.readyState = "ended";
    this.onStop();
  }
}

class FakeVideoTrack extends EventTarget {
  readonly id = "display-video-track";
  readonly kind = "video";
  muted = false;
  readyState: MediaStreamTrackState = "live";

  constructor(private readonly onStop: () => void = () => undefined) {
    super();
  }

  getSettings(): MediaTrackSettings {
    return { displaySurface: "browser" };
  }

  stop(): void {
    this.readyState = "ended";
    this.onStop();
  }
}

class FakeMediaStream {
  constructor(private readonly tracks: MediaStreamTrack[] = []) {}

  getTracks(): MediaStreamTrack[] {
    return [...this.tracks];
  }

  getAudioTracks(): MediaStreamTrack[] {
    return this.tracks.filter((track) => track.kind === "audio");
  }

  getVideoTracks(): MediaStreamTrack[] {
    return this.tracks.filter((track) => track.kind === "video");
  }
}

function microphoneStream(onStop?: () => void): MediaStream {
  return new FakeMediaStream([
    new FakeMediaStreamTrack(onStop) as unknown as MediaStreamTrack,
  ]) as unknown as MediaStream;
}

function installSupportedBrowser(
  getUserMedia: () => Promise<MediaStream>,
  getDisplayMedia?: () => Promise<MediaStream>,
): void {
  vi.stubGlobal(
    "MediaRecorder",
    FakeMediaRecorder as unknown as typeof MediaRecorder,
  );
  vi.stubGlobal(
    "MediaStream",
    FakeMediaStream as unknown as typeof MediaStream,
  );
  if (getDisplayMedia) {
    vi.stubGlobal("AudioContext", class FakeAudioContext {});
  }
  vi.stubGlobal("navigator", {
    mediaDevices: Object.assign(
      new EventTarget(),
      getDisplayMedia ? { getUserMedia, getDisplayMedia } : { getUserMedia },
    ),
  });
}

describe("RecordingFoundation", () => {
  afterEach(() => {
    FakeMediaRecorder.instances = [];
    vi.unstubAllGlobals();
  });

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
        interactionType="face_to_face_meeting"
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

  it("does not offer misleading browser audio capture for a phone call", async () => {
    installSupportedBrowser(() => Promise.reject(new Error("not requested")));
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="phone_call"
        lifecycleStatus="in_progress"
      />,
    );

    expect(
      await screen.findByText(/cannot reliably record the same phone call/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Start recording" }),
    ).not.toBeInTheDocument();
  });

  it("offers microphone-only capture when shared meeting audio is unsupported", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="online_meeting"
        lifecycleStatus="in_progress"
      />,
    );

    const shared = await screen.findByRole("radio", {
      name: /shared meeting audio \+ microphone/i,
    });
    expect(shared).toBeDisabled();
    expect(
      screen.getByRole("radio", { name: /microphone only/i }),
    ).toBeChecked();
    expect(
      screen.getByText(/shared meeting audio is unsupported/i),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Start microphone capture" }),
    ).toBeDisabled();
  });

  it("distinguishes a selected share that has no audio and stops its video", async () => {
    const stopDisplayVideo = vi.fn();
    const getUserMedia = vi.fn(() => Promise.resolve(microphoneStream()));
    installSupportedBrowser(getUserMedia, () =>
      Promise.resolve(
        new FakeMediaStream([
          new FakeVideoTrack(stopDisplayVideo) as unknown as MediaStreamTrack,
        ]) as unknown as MediaStream,
      ),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="online_meeting"
        lifecycleStatus="in_progress"
      />,
    );

    const liveNotes = await screen.findByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "Customer needs security approval by Friday." },
    });
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: "Start shared audio capture" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "selected share did not include audio",
    );
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(stopDisplayVideo).toHaveBeenCalledTimes(1);
    expect(liveNotes).toHaveValue(
      "Customer needs security approval by Friday.",
    );
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
        interactionType="face_to_face_meeting"
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

  it("safely finalises captured audio when an audio device changes", async () => {
    const stopTrack = vi.fn();
    installSupportedBrowser(() => Promise.resolve(microphoneStream(stopTrack)));
    const releaseWakeLock = vi.fn(() => Promise.resolve());
    const requestWakeLock = vi.fn(() =>
      Promise.resolve({
        released: false,
        release: releaseWakeLock,
        addEventListener: vi.fn(),
      }),
    );
    Object.defineProperty(navigator, "wakeLock", {
      configurable: true,
      value: { request: requestWakeLock },
    });
    let finalized = false;
    let uploadAttempts = 0;
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
        uploadAttempts += 1;
        if (uploadAttempts === 1) {
          return Promise.resolve(
            jsonResponse(
              { code: "temporary", message: "Temporary connection loss." },
              503,
            ),
          );
        }
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
        interactionType="face_to_face_meeting"
        lifecycleStatus="planned"
      />,
    );
    const liveNotes = await screen.findByLabelText("Private live notes");
    fireEvent.change(liveNotes, {
      target: { value: "Do not lose this note if the microphone changes." },
    });
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    const pause = await screen.findByRole("button", { name: "Pause" });
    fireEvent.click(pause);
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    navigator.mediaDevices.dispatchEvent(new Event("devicechange"));

    expect(await screen.findByText(/an audio device changed/i)).toBeVisible();

    expect(
      await screen.findByText(
        "The recording is queued for batch transcription.",
      ),
    ).toBeVisible();
    expect(liveNotes).toHaveValue(
      "Do not lose this note if the microphone changes.",
    );
    await waitFor(() => expect(stopTrack).toHaveBeenCalled());
    expect(requestWakeLock).toHaveBeenCalledWith("screen");
    expect(releaseWakeLock).toHaveBeenCalled();
    const chunkCreateBodies = fetchMock.mock.calls
      .filter(
        ([input, init]) =>
          String(input).endsWith("/chunks") && init?.method === "POST",
      )
      .map(
        ([, init]) =>
          JSON.parse(String(init?.body)) as { idempotencyKey: string },
      );
    expect(chunkCreateBodies).toHaveLength(2);
    expect(
      new Set(chunkCreateBodies.map((body) => body.idempotencyKey)).size,
    ).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/finalize"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("cancels its active server session and releases audio when unmounted", async () => {
    const stopTrack = vi.fn();
    installSupportedBrowser(() => Promise.resolve(microphoneStream(stopTrack)));
    let serverLifecycle = "none";
    const noteChanges = vi.fn();
    const activityChanges = vi.fn();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/recordings") && method === "POST") {
        serverLifecycle = "created";
        return Promise.resolve(jsonResponse(baseRecording, 201));
      }
      if (url.endsWith("/start") && method === "POST") {
        serverLifecycle = "recording";
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
        );
      }
      if (url.endsWith("/cancel") && method === "POST") {
        serverLifecycle = "cancelled";
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "cancelled" }),
        );
      }
      return Promise.resolve(
        jsonResponse({ code: "unexpected", message: url }, 500),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
        liveNotes="Keep the agreed renewal date."
        onLiveNotesChange={noteChanges}
        onActivityChange={activityChanges}
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    expect(serverLifecycle).toBe("recording");
    expect(screen.getByLabelText("Private live notes")).toHaveValue(
      "Keep the agreed renewal date.",
    );
    const activityCountBeforeUnmount = activityChanges.mock.calls.length;

    view.unmount();

    await waitFor(() => expect(serverLifecycle).toBe("cancelled"));
    expect(FakeMediaRecorder.instances).toHaveLength(1);
    expect(FakeMediaRecorder.instances[0]?.stopCalls).toBe(1);
    expect(
      FakeMediaRecorder.instances[0]?.stream.getVideoTracks(),
    ).toHaveLength(0);
    expect(stopTrack).toHaveBeenCalledTimes(1);
    const cancelCalls = fetchMock.mock.calls.filter(
      ([input, init]) =>
        String(input).endsWith("/cancel") && init?.method === "POST",
    );
    expect(cancelCalls).toHaveLength(1);
    expect(cancelCalls[0]?.[1]).toEqual(
      expect.objectContaining({ keepalive: true }),
    );
    expect(JSON.parse(String(cancelCalls[0]?.[1]?.body))).toMatchObject({
      idempotencyKey: expect.stringMatching(/^recording-unmount-cancel-/u),
    });
    expect(
      fetchMock.mock.calls.some(([input]) =>
        /\/(chunks|stop|finalize)$/u.test(String(input)),
      ),
    ).toBe(false);
    expect(noteChanges).not.toHaveBeenCalled();
    expect(activityChanges).toHaveBeenCalledTimes(activityCountBeforeUnmount);
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
        interactionType="face_to_face_meeting"
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
