import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { RecordingSession } from "@revenueos/shared";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  reconcileProgressiveTranscriptEvents,
  RecordingFoundation,
  selectSupportedRecordingMimeType,
} from "@/components/recording-foundation";

const startProgressiveTranscriptionCaptureMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/progressive-transcription-capture", async (importOriginal) => {
  const original =
    await importOriginal<
      typeof import("@/lib/progressive-transcription-capture")
    >();
  return {
    ...original,
    startProgressiveTranscriptionCapture:
      startProgressiveTranscriptionCaptureMock,
  };
});

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, reject, resolve };
}

function transcriptionResponse(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    recordingId: "recording-1",
    status: "completed",
    transcriptVersionId: "transcript-version-1",
    transcriptId: "transcript-1",
    meetingId: "meeting-1",
    version: 1,
    source: "recorded_audio",
    language: "en-AU",
    text: "Verified synthetic transcript.",
    segments: [],
    completedAt: "2026-08-15T00:05:00Z",
    safeMessage: "Transcription is complete.",
    ...overrides,
  };
}

const baseRecording = {
  id: "recording-1",
  interactionId: "interaction-1",
  captureSessionId: "capture-1",
  recordingType: "live_audio_recording",
  recordingSource: null,
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
  sessionExpiresAt: "2099-08-16T00:00:00Z",
  providerMode: "mock",
  externalProcessing: false,
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:00:00Z",
} satisfies RecordingSession;

const stoppedRecording: RecordingSession = {
  ...baseRecording,
  lifecycleStatus: "uploading",
  startedAt: "2026-08-15T00:00:00Z",
  stoppedAt: "2026-08-15T00:01:00Z",
  durationSeconds: 60,
};

const verifiedChunk = {
  id: "chunk-1",
  recordingSessionId: baseRecording.id,
  sequenceNumber: 0,
  uploadState: "verified",
  byteSize: 5,
  checksumSha256: "a".repeat(64),
  createdAt: "2026-08-15T00:00:00Z",
  uploadedAt: "2026-08-15T00:00:50Z",
};

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  static onStart: () => void = () => undefined;

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
    FakeMediaRecorder.onStart();
    this.state = "recording";
  }

  pause(): void {
    this.state = "paused";
  }

  resume(): void {
    this.state = "recording";
  }

  emitData(): void {
    const bytes = new TextEncoder().encode("MOCK_TRANSCRIPT:Browser test.");
    const content = new Uint8Array(4 + bytes.length);
    content.set([0x1a, 0x45, 0xdf, 0xa3]);
    content.set(bytes, 4);
    const data = new Blob([content], { type: "audio/webm" });
    Object.defineProperty(data, "arrayBuffer", {
      value: () => Promise.resolve(content.buffer),
    });
    this.ondataavailable?.({ data } as BlobEvent);
  }

  stop(): void {
    this.stopCalls += 1;
    this.state = "inactive";
    this.emitData();
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
    FakeMediaRecorder.onStart = () => undefined;
    startProgressiveTranscriptionCaptureMock.mockReset();
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

  it("orders progressive text and replaces a partial with its final revision", () => {
    const base = {
      streamId: "stream-1",
      providerName: "fixture",
      itemIndex: 0,
      startMs: 0,
      endMs: 100,
      speakerLabel: null,
    } as const;
    const reconciled = reconcileProgressiveTranscriptEvents(
      [
        {
          ...base,
          eventId: "partial-1",
          itemId: "item-1",
          sourceAudioSequence: 0,
          revision: 1,
          kind: "partial",
          text: "First wor",
        },
      ],
      [
        {
          ...base,
          eventId: "item-2-final",
          itemId: "item-2",
          sourceAudioSequence: 1,
          revision: 1,
          kind: "final",
          text: "Second words.",
        },
        {
          ...base,
          eventId: "item-1-final",
          itemId: "item-1",
          sourceAudioSequence: 0,
          revision: 2,
          kind: "final",
          text: "First words.",
        },
      ],
    );

    expect(
      reconciled.map(({ itemId, revision, kind, text }) => ({
        itemId,
        revision,
        kind,
        text,
      })),
    ).toEqual([
      {
        itemId: "item-1",
        revision: 2,
        kind: "final",
        text: "First words.",
      },
      {
        itemId: "item-2",
        revision: 1,
        kind: "final",
        text: "Second words.",
      },
    ]);
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

  it("omits its nested notes editor when the conversation workspace owns private notes", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    vi.stubGlobal("navigator", {});
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
        liveNotes="The workspace owns this draft."
        onLiveNotesChange={vi.fn()}
        showLiveNotes={false}
      />,
    );

    expect(
      screen.queryByLabelText("Private live notes"),
    ).not.toBeInTheDocument();
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

  it.each([
    {
      progressiveTranscription: true,
      disclosure:
        "Oryntela may send audio during capture, with final batch processing after finalisation.",
      excludedDisclosure: "Oryntela sends audio only after finalisation.",
    },
    {
      progressiveTranscription: false,
      disclosure: "Oryntela sends audio only after finalisation.",
      excludedDisclosure: "Oryntela may send audio during capture",
    },
  ])(
    "discloses external-processing timing when progressive transcription is $progressiveTranscription",
    async ({ progressiveTranscription, disclosure, excludedDisclosure }) => {
      installSupportedBrowser(() => Promise.reject(new Error("not requested")));
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) => {
          const url = String(input);
          if (url.endsWith("/api/v1/beta/capabilities")) {
            return Promise.resolve(
              jsonResponse({
                featureFlags: { progressiveTranscription },
              }),
            );
          }
          if (url.endsWith("/recordings")) {
            return Promise.resolve(
              jsonResponse([
                {
                  ...baseRecording,
                  lifecycleStatus: "completed",
                  externalProcessing: true,
                },
              ]),
            );
          }
          if (url.endsWith("/transcription")) {
            return Promise.resolve(
              jsonResponse({
                recordingId: "recording-1",
                status: "completed",
                transcriptVersionId: "transcript-version-1",
                transcriptId: "transcript-1",
                meetingId: "meeting-1",
                version: 1,
                source: "recording",
                language: "en-AU",
                text: "Synthetic transcript.",
                segments: [],
                completedAt: "2026-08-15T00:05:00Z",
                safeMessage: "Transcription is complete.",
              }),
            );
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: url }, 500),
          );
        }),
      );

      render(
        <RecordingFoundation
          interactionId="interaction-1"
          interactionType="face_to_face_meeting"
          lifecycleStatus="completed"
        />,
      );

      expect(
        await screen.findByText(disclosure, { exact: false }),
      ).toBeVisible();
      expect(
        screen.queryByText(excludedDisclosure, { exact: false }),
      ).not.toBeInTheDocument();
    },
  );

  it("suppresses a foreign transcript returned during initial load", async () => {
    installSupportedBrowser(() => Promise.reject(new Error("not requested")));
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({
              featureFlags: { progressiveTranscription: false },
            }),
          );
        }
        if (url.endsWith("/recordings")) {
          return Promise.resolve(
            jsonResponse([
              {
                ...baseRecording,
                lifecycleStatus: "uploaded",
                finalMimeType: "audio/webm",
                transcriptionStatus: "processing",
              },
            ]),
          );
        }
        if (url.endsWith("/transcription")) {
          return Promise.resolve(
            jsonResponse(
              transcriptionResponse({
                recordingId: "recording-foreign",
                text: "Foreign private transcript must not render.",
              }),
            ),
          );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="planned"
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The recording response did not match this interaction. Try again.",
    );
    expect(
      screen.queryByText("Foreign private transcript must not render."),
    ).not.toBeInTheDocument();
  });

  it("clears a verified transcript when a refresh returns a foreign recording identity", async () => {
    installSupportedBrowser(() => Promise.reject(new Error("not requested")));
    let transcriptReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({
              featureFlags: { progressiveTranscription: false },
            }),
          );
        }
        if (url.endsWith("/recordings")) {
          return Promise.resolve(
            jsonResponse([
              {
                ...baseRecording,
                lifecycleStatus: "uploaded",
                finalMimeType: "audio/webm",
                transcriptionStatus: "processing",
              },
            ]),
          );
        }
        if (url.endsWith("/transcription")) {
          transcriptReads += 1;
          return Promise.resolve(
            jsonResponse(
              transcriptReads === 1
                ? transcriptionResponse({
                    status: "processing",
                    text: "Previously verified transcript.",
                    safeMessage: "Transcription is processing.",
                  })
                : transcriptionResponse({
                    recordingId: "recording-foreign",
                    text: "Foreign refresh text.",
                  }),
            ),
          );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="planned"
      />,
    );

    expect(
      await screen.findByText("Previously verified transcript."),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh transcription status" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The recording response did not match this interaction. Try again.",
    );
    expect(
      screen.queryByText("Previously verified transcript."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Foreign refresh text.")).not.toBeInTheDocument();
  });

  it("does not let an older transcript request overwrite a newer refresh", async () => {
    installSupportedBrowser(() => Promise.reject(new Error("not requested")));
    const olderTranscript = deferred<Response>();
    let transcriptReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({
              featureFlags: { progressiveTranscription: false },
            }),
          );
        }
        if (url.endsWith("/recordings")) {
          return Promise.resolve(
            jsonResponse([
              {
                ...baseRecording,
                lifecycleStatus: "uploaded",
                finalMimeType: "audio/webm",
                transcriptionStatus: "processing",
              },
            ]),
          );
        }
        if (url.endsWith("/transcription")) {
          transcriptReads += 1;
          return transcriptReads === 1
            ? olderTranscript.promise
            : Promise.resolve(
                jsonResponse(
                  transcriptionResponse({
                    status: "processing",
                    text: "Newer verified transcript.",
                    safeMessage: "Transcription is processing.",
                  }),
                ),
              );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="planned"
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Refresh transcription status",
      }),
    );
    expect(await screen.findByText("Newer verified transcript.")).toBeVisible();
    await act(async () => {
      olderTranscript.resolve(
        jsonResponse(
          transcriptionResponse({
            status: "processing",
            text: "Obsolete transcript.",
            safeMessage: "Transcription is processing.",
          }),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.getByText("Newer verified transcript.")).toBeVisible();
    expect(screen.queryByText("Obsolete transcript.")).not.toBeInTheDocument();
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
    let reservedChunk: Record<string, unknown> | null = null;
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
        const request = JSON.parse(String(init?.body)) as {
          sequenceNumber: number;
          byteSize: number;
          checksumSha256: string;
        };
        reservedChunk = {
          id: "chunk-1",
          recordingSessionId: "recording-1",
          sequenceNumber: request.sequenceNumber,
          byteSize: request.byteSize,
          checksumSha256: request.checksumSha256,
          uploadState: "pending",
          uploadedAt: null,
          createdAt: "2026-08-15T00:00:00Z",
          uploadUrl: "/recording-upload",
          uploadExpiresAt: "2026-08-15T00:05:00Z",
        };
        return Promise.resolve(jsonResponse(reservedChunk, 201));
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
            ...reservedChunk,
            uploadState: "verified",
            uploadedAt: "2026-08-15T00:01:00Z",
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
            finalMimeType: "audio/webm",
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

  it.each([
    { stage: "reservation", expectedPutCalls: 0 },
    { stage: "put", expectedPutCalls: 1 },
    { stage: "transient retry", expectedPutCalls: 1 },
  ] as const)(
    "stops chunk work when recording is cancelled during $stage",
    async ({ stage, expectedPutCalls }) => {
      installSupportedBrowser(() => Promise.resolve(microphoneStream()));
      vi.stubGlobal("crypto", {
        randomUUID: vi.fn(() => "request-id"),
        subtle: {
          digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
        },
      });
      const reservation = deferred<Response>();
      const upload = deferred<Response>();
      let reservedChunk: Record<string, unknown> | null = null;
      let uploadAttempts = 0;
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input);
          const method = init?.method ?? "GET";
          if (url.endsWith("/api/v1/beta/capabilities")) {
            return Promise.resolve(
              jsonResponse({
                featureFlags: { progressiveTranscription: false },
              }),
            );
          }
          if (url.endsWith("/recordings") && method === "GET") {
            return Promise.resolve(jsonResponse([]));
          }
          if (url.endsWith("/recordings") && method === "POST") {
            return Promise.resolve(jsonResponse(baseRecording, 201));
          }
          if (url.endsWith("/start") && method === "POST") {
            return Promise.resolve(
              jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
            );
          }
          if (url.endsWith("/chunks") && method === "POST") {
            const request = JSON.parse(String(init?.body)) as {
              sequenceNumber: number;
              byteSize: number;
              checksumSha256: string;
            };
            reservedChunk = {
              id: "chunk-1",
              recordingSessionId: baseRecording.id,
              sequenceNumber: request.sequenceNumber,
              byteSize: request.byteSize,
              checksumSha256: request.checksumSha256,
              uploadState: "pending",
              uploadedAt: null,
              createdAt: "2026-08-15T00:00:00Z",
              uploadUrl: "/recording-upload-cancel-test",
              uploadExpiresAt: "2026-08-15T00:05:00Z",
            };
            return stage === "reservation"
              ? reservation.promise
              : Promise.resolve(jsonResponse(reservedChunk, 201));
          }
          if (
            url.endsWith("/recording-upload-cancel-test") &&
            method === "PUT"
          ) {
            uploadAttempts += 1;
            if (stage === "put") return upload.promise;
            if (stage === "transient retry" && uploadAttempts === 1) {
              return Promise.resolve(
                jsonResponse(
                  { code: "temporary", message: "Temporary connection loss." },
                  503,
                ),
              );
            }
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          if (url.endsWith("/complete") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...reservedChunk,
                uploadState: "verified",
                uploadedAt: "2026-08-15T00:01:00Z",
              }),
            );
          }
          if (url.endsWith("/cancel") && method === "POST") {
            return Promise.resolve(
              jsonResponse({ ...baseRecording, lifecycleStatus: "cancelled" }),
            );
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: url }, 500),
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(
        <RecordingFoundation
          interactionId="interaction-1"
          interactionType="face_to_face_meeting"
          lifecycleStatus="in_progress"
        />,
      );
      fireEvent.click(await screen.findByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      expect(
        await screen.findByRole("button", { name: "Pause" }),
      ).toBeVisible();
      act(() => {
        FakeMediaRecorder.instances[0]?.emitData();
      });

      if (stage === "reservation") {
        await waitFor(() =>
          expect(
            fetchMock.mock.calls.some(([input]) =>
              String(input).endsWith("/chunks"),
            ),
          ).toBe(true),
        );
      } else {
        await waitFor(() => expect(uploadAttempts).toBe(1));
      }

      fireEvent.click(screen.getByRole("button", { name: "Cancel recording" }));
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(
            ([input, init]) =>
              String(input).endsWith("/cancel") && init?.method === "POST",
          ),
        ).toBe(true),
      );

      expect(
        await screen.findByRole("button", { name: "Start recording" }),
      ).toBeVisible();
      fireEvent.click(screen.getByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      expect(
        await screen.findByRole("button", { name: "Pause" }),
      ).toBeVisible();

      await act(async () => {
        if (stage === "reservation") {
          reservation.resolve(jsonResponse(reservedChunk ?? {}, 201));
        }
        if (stage === "put") {
          upload.resolve(new Response(null, { status: 204 }));
        }
        await Promise.resolve();
      });
      if (stage === "transient retry") {
        await new Promise((resolve) => setTimeout(resolve, 400));
      }

      const putCalls = fetchMock.mock.calls.filter(
        ([input, init]) =>
          String(input).endsWith("/recording-upload-cancel-test") &&
          init?.method === "PUT",
      );
      expect(putCalls).toHaveLength(expectedPutCalls);
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/complete"),
        ),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(([input]) =>
          /\/(?:stop|finalize)$/u.test(String(input)),
        ),
      ).toBe(false);
      if (stage !== "transient retry") {
        const activeRequest = fetchMock.mock.calls.find(([input]) =>
          String(input).endsWith(
            stage === "reservation"
              ? "/chunks"
              : "/recording-upload-cancel-test",
          ),
        );
        expect(activeRequest?.[1]?.signal?.aborted).toBe(true);
      }

      fireEvent.click(screen.getByRole("button", { name: "Cancel recording" }));
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.filter(
            ([input, init]) =>
              String(input).endsWith("/cancel") && init?.method === "POST",
          ),
        ).toHaveLength(2),
      );
    },
  );

  it.each(["create", "start"] as const)(
    "rejects a foreign %s response before browser audio can be reserved or uploaded",
    async (mismatchStage) => {
      installSupportedBrowser(() => Promise.resolve(microphoneStream()));
      vi.stubGlobal("crypto", {
        randomUUID: vi.fn(() => "request-id"),
        subtle: {
          digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
        },
      });
      const foreignUploadUrl =
        "https://foreign-upload.example/browser-lifecycle-chunk";
      const foreignSession = {
        ...baseRecording,
        id: "recording-foreign",
        interactionId: "interaction-foreign",
        captureSessionId: "capture-foreign",
      };
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input);
          const method = init?.method ?? "GET";
          if (url.endsWith("/api/v1/beta/capabilities")) {
            return Promise.resolve(
              jsonResponse({
                featureFlags: { progressiveTranscription: false },
              }),
            );
          }
          if (url.endsWith("/recordings") && method === "GET") {
            return Promise.resolve(jsonResponse([]));
          }
          if (url.endsWith("/recordings") && method === "POST") {
            return Promise.resolve(
              jsonResponse(
                mismatchStage === "create" ? foreignSession : baseRecording,
                201,
              ),
            );
          }
          if (url.endsWith("/start") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...foreignSession,
                lifecycleStatus: "recording",
              }),
            );
          }
          if (url.endsWith("/chunks") && method === "POST") {
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
          if (url.endsWith("/cancel") && method === "POST") {
            return Promise.resolve(
              jsonResponse({
                ...baseRecording,
                lifecycleStatus: "cancelled",
              }),
            );
          }
          if (url === foreignUploadUrl && method === "PUT") {
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: url }, 500),
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(
        <RecordingFoundation
          interactionId="interaction-1"
          interactionType="face_to_face_meeting"
          lifecycleStatus="in_progress"
        />,
      );
      fireEvent.click(await screen.findByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The recording response did not match this interaction. Try again.",
      );
      expect(
        screen.getByRole("button", { name: "Start recording" }),
      ).toBeEnabled();
      expect(
        screen.queryByRole("button", { name: "Pause" }),
      ).not.toBeInTheDocument();
      expect(FakeMediaRecorder.instances).toHaveLength(0);
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
        fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
      ).toBe(false);
      expect(
        fetchMock.mock.calls.some(([input]) =>
          /\/(complete|stop|finalize)$/u.test(String(input)),
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
      if (mismatchStage === "create") {
        expect(
          fetchMock.mock.calls.some(([input]) =>
            String(input).endsWith("/start"),
          ),
        ).toBe(false);
      }
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
    "rejects a $mismatch chunk ticket before browser audio leaves the client",
    async ({ responseOverride }) => {
      installSupportedBrowser(() => Promise.resolve(microphoneStream()));
      vi.stubGlobal("crypto", {
        randomUUID: vi.fn(() => "request-id"),
        subtle: {
          digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
        },
      });
      const foreignUploadUrl =
        "https://foreign-upload.example/browser-recording-chunk";
      const fetchMock = vi.fn(
        (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input);
          const method = init?.method ?? "GET";
          if (url.endsWith("/api/v1/beta/capabilities")) {
            return Promise.resolve(
              jsonResponse({
                featureFlags: { progressiveTranscription: false },
              }),
            );
          }
          if (url.endsWith("/recordings") && method === "GET") {
            return Promise.resolve(jsonResponse([]));
          }
          if (url.endsWith("/recordings") && method === "POST") {
            return Promise.resolve(jsonResponse(baseRecording, 201));
          }
          if (url.endsWith("/start") && method === "POST") {
            return Promise.resolve(
              jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
            );
          }
          if (url.endsWith("/chunks") && method === "POST") {
            const request = JSON.parse(String(init?.body)) as {
              sequenceNumber: number;
              byteSize: number;
              checksumSha256: string;
            };
            return Promise.resolve(
              jsonResponse(
                {
                  id: "chunk-foreign",
                  recordingSessionId: baseRecording.id,
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
          if (url.endsWith("/cancel") && method === "POST") {
            return Promise.resolve(
              jsonResponse({ ...baseRecording, lifecycleStatus: "cancelled" }),
            );
          }
          return Promise.resolve(
            jsonResponse({ code: "unexpected", message: url }, 500),
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      render(
        <RecordingFoundation
          interactionId="interaction-1"
          interactionType="face_to_face_meeting"
          lifecycleStatus="in_progress"
        />,
      );
      fireEvent.click(await screen.findByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      expect(
        await screen.findByRole("button", { name: "Pause" }),
      ).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: "Stop and upload" }));

      expect(
        await screen.findByRole(
          "button",
          { name: "Retry queued audio" },
          { timeout: 4_000 },
        ),
      ).toBeVisible();
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Some audio is still queued in this tab",
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
          /\/(complete|stop|finalize)$/u.test(String(input)),
        ),
      ).toBe(false);

      fireEvent.click(screen.getByRole("button", { name: "Cancel recording" }));
      await waitFor(() =>
        expect(
          fetchMock.mock.calls.some(
            ([input, init]) =>
              String(input).endsWith("/cancel") && init?.method === "POST",
          ),
        ).toBe(true),
      );
    },
  );

  it("rejects a mismatched chunk completion before stopping or finalising", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "request-id"),
      subtle: {
        digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
      },
    });
    let reservedChunk: Record<string, unknown> | null = null;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: { progressiveTranscription: false },
          }),
        );
      }
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/recordings") && method === "POST") {
        return Promise.resolve(jsonResponse(baseRecording, 201));
      }
      if (url.endsWith("/start") && method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
        );
      }
      if (url.endsWith("/chunks") && method === "POST") {
        const request = JSON.parse(String(init?.body)) as {
          sequenceNumber: number;
          byteSize: number;
          checksumSha256: string;
        };
        reservedChunk = {
          id: "chunk-1",
          recordingSessionId: baseRecording.id,
          sequenceNumber: request.sequenceNumber,
          byteSize: request.byteSize,
          checksumSha256: request.checksumSha256,
          uploadState: "pending",
          uploadedAt: null,
          createdAt: "2026-08-15T00:00:00Z",
          uploadUrl: "/recording-upload",
          uploadExpiresAt: "2026-08-15T00:05:00Z",
        };
        return Promise.resolve(jsonResponse(reservedChunk, 201));
      }
      if (url.endsWith("/recording-upload") && method === "PUT") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/complete") && method === "POST") {
        return Promise.resolve(
          jsonResponse({
            ...reservedChunk,
            recordingSessionId: "recording-foreign",
            uploadState: "verified",
            uploadedAt: "2026-08-15T00:01:00Z",
          }),
        );
      }
      if (url.endsWith("/cancel") && method === "POST") {
        return Promise.resolve(new Response(null, { status: 204 }));
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
        lifecycleStatus="in_progress"
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Stop and upload" }));

    expect(
      await screen.findByRole(
        "button",
        { name: "Retry queued audio" },
        { timeout: 4_000 },
      ),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        /\/(?:stop|finalize)$/u.test(String(input)),
      ),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/complete"),
      ),
    ).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Cancel recording" }));
  });

  it("keeps the validated stopped session retryable when finalisation returns a foreign response", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "request-id"),
      subtle: {
        digest: vi.fn(() => Promise.resolve(new Uint8Array(32).buffer)),
      },
    });
    const onFinalized = vi.fn();
    const foreignFinalized = {
      ...baseRecording,
      id: "recording-foreign",
      interactionId: "interaction-foreign",
      captureSessionId: "capture-foreign",
      lifecycleStatus: "uploaded",
      finalMimeType: "audio/webm",
      transcriptionStatus: "queued",
    };
    let reservedChunk: Record<string, unknown> | null = null;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/beta/capabilities")) {
        return Promise.resolve(
          jsonResponse({
            featureFlags: { progressiveTranscription: false },
          }),
        );
      }
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/recordings") && method === "POST") {
        return Promise.resolve(jsonResponse(baseRecording, 201));
      }
      if (url.endsWith("/start") && method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
        );
      }
      if (url.endsWith("/chunks") && method === "POST") {
        const request = JSON.parse(String(init?.body)) as {
          sequenceNumber: number;
          byteSize: number;
          checksumSha256: string;
        };
        reservedChunk = {
          id: "chunk-1",
          recordingSessionId: baseRecording.id,
          sequenceNumber: request.sequenceNumber,
          byteSize: request.byteSize,
          checksumSha256: request.checksumSha256,
          uploadState: "pending",
          uploadedAt: null,
          createdAt: "2026-08-15T00:00:00Z",
          uploadUrl: "/recording-upload",
          uploadExpiresAt: "2026-08-15T00:05:00Z",
        };
        return Promise.resolve(jsonResponse(reservedChunk, 201));
      }
      if (url.endsWith("/recording-upload") && method === "PUT") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/complete") && method === "POST") {
        return Promise.resolve(
          jsonResponse({
            ...reservedChunk,
            uploadState: "verified",
            uploadedAt: "2026-08-15T00:01:00Z",
          }),
        );
      }
      if (url.endsWith("/stop") && method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...baseRecording, lifecycleStatus: "uploading" }),
        );
      }
      if (url.endsWith("/finalize") && method === "POST") {
        return Promise.resolve(jsonResponse(foreignFinalized));
      }
      if (url.endsWith("/cancel") && method === "POST") {
        return Promise.resolve(
          jsonResponse({
            ...baseRecording,
            lifecycleStatus: "cancelled",
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
        lifecycleStatus="in_progress"
        onFinalized={onFinalized}
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Stop and upload" }));

    expect(
      await screen.findByRole("button", { name: "Retry finalisation" }),
    ).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The recording response did not match this interaction. Try again.",
    );
    expect(onFinalized).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Cancel recording" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/finalize"),
      ),
    ).toHaveLength(1);
  });

  it("prepares progressive capture before synchronously arming it with the batch recorder", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    const lifecycle: string[] = [];
    const resumeProgressiveCapture = vi.fn(() => {
      lifecycle.push("progressive_armed");
    });
    let releasePreparation: () => void = () => undefined;
    const preparation = new Promise<{
      pause: () => void;
      resume: () => void;
      finish: () => Promise<object>;
      cancel: () => Promise<void>;
    }>((resolve) => {
      releasePreparation = () => {
        lifecycle.push("progressive_prepared");
        resolve({
          pause: vi.fn(),
          resume: resumeProgressiveCapture,
          finish: vi.fn(() => Promise.resolve({})),
          cancel: vi.fn(() => Promise.resolve()),
        });
      };
    });
    startProgressiveTranscriptionCaptureMock.mockReturnValue(preparation);
    FakeMediaRecorder.onStart = () => {
      lifecycle.push("batch_armed");
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({ featureFlags: { progressiveTranscription: true } }),
          );
        }
        if (url.endsWith("/recordings") && method === "GET") {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/recordings") && method === "POST") {
          return Promise.resolve(jsonResponse(baseRecording, 201));
        }
        if (url.endsWith("/start") && method === "POST") {
          return Promise.resolve(
            jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
          );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    await waitFor(() =>
      expect(startProgressiveTranscriptionCaptureMock).toHaveBeenCalledWith(
        expect.objectContaining({ initiallyPaused: true }),
      ),
    );

    expect(FakeMediaRecorder.instances).toHaveLength(0);
    expect(
      screen.queryByRole("button", { name: "Pause" }),
    ).not.toBeInTheDocument();

    releasePreparation();

    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    expect(resumeProgressiveCapture).toHaveBeenCalledTimes(1);
    expect(lifecycle).toEqual([
      "progressive_prepared",
      "progressive_armed",
      "batch_armed",
    ]);
  });

  it("starts batch recording with a notice when progressive preparation fails", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    startProgressiveTranscriptionCaptureMock.mockRejectedValue(
      new Error("Synthetic progressive setup failure."),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({ featureFlags: { progressiveTranscription: true } }),
          );
        }
        if (url.endsWith("/recordings") && method === "GET") {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/recordings") && method === "POST") {
          return Promise.resolve(jsonResponse(baseRecording, 201));
        }
        if (url.endsWith("/start") && method === "POST") {
          return Promise.resolve(
            jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
          );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));

    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    expect(
      screen.getByText(
        "Live transcription is unavailable. Recording continues for normal batch transcription.",
      ),
    ).toBeVisible();
    expect(FakeMediaRecorder.instances[0]?.state).toBe("recording");
  });

  it("cancels progressive capture immediately when MediaRecorder fails", async () => {
    installSupportedBrowser(() => Promise.resolve(microphoneStream()));
    const cancelProgressiveCapture = vi.fn(() => Promise.resolve());
    startProgressiveTranscriptionCaptureMock.mockResolvedValue({
      pause: vi.fn(),
      resume: vi.fn(),
      finish: vi.fn(),
      cancel: cancelProgressiveCapture,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/v1/beta/capabilities")) {
          return Promise.resolve(
            jsonResponse({ featureFlags: { progressiveTranscription: true } }),
          );
        }
        if (url.endsWith("/recordings") && method === "GET") {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/recordings") && method === "POST") {
          return Promise.resolve(jsonResponse(baseRecording, 201));
        }
        if (url.endsWith("/start") && method === "POST") {
          return Promise.resolve(
            jsonResponse({ ...baseRecording, lifecycleStatus: "recording" }),
          );
        }
        return Promise.resolve(
          jsonResponse({ code: "unexpected", message: url }, 500),
        );
      }),
    );

    render(
      <RecordingFoundation
        interactionId="interaction-1"
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
      />,
    );
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
    await waitFor(() =>
      expect(startProgressiveTranscriptionCaptureMock).toHaveBeenCalledTimes(1),
    );

    const recorder = FakeMediaRecorder.instances[0];
    expect(recorder).toBeDefined();
    recorder?.onerror?.(new Event("error"));
    recorder?.onerror?.(new Event("error"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Browser recording stopped unexpectedly",
    );
    await waitFor(() =>
      expect(cancelProgressiveCapture).toHaveBeenCalledWith("capture_ended"),
    );
    expect(cancelProgressiveCapture).toHaveBeenCalledTimes(1);
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
    expect(activityChanges).toHaveBeenCalledWith(
      expect.objectContaining({
        state: "requesting_permission",
        active: false,
        blocksInteractionCompletion: true,
      }),
    );
    expect(screen.getByLabelText("Private live notes")).toHaveValue(
      "Keep the agreed renewal date.",
    );
    await waitFor(() =>
      expect(activityChanges).toHaveBeenLastCalledWith(
        expect.objectContaining({
          state: "recording",
          active: true,
          blocksInteractionCompletion: true,
          elapsedSeconds: 1,
          recording: expect.objectContaining({
            lifecycleStatus: "recording",
          }),
        }),
      ),
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
    const microphone = vi.fn(() => Promise.reject(new Error("not requested")));
    installSupportedBrowser(microphone);
    const onFinalized = vi.fn();
    const onRecoveryResolved = vi.fn();
    let finalized = false;
    let attempts = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/recordings") && method === "GET") {
        return Promise.resolve(
          jsonResponse([
            {
              ...stoppedRecording,
              lifecycleStatus: finalized ? "uploaded" : "uploading",
              durationSeconds: 60,
              finalMimeType: finalized ? "audio/webm" : null,
              chunkCount: 1,
            },
          ]),
        );
      }
      if (url.endsWith("/chunks")) {
        return Promise.resolve(jsonResponse([verifiedChunk]));
      }
      if (url.endsWith("/finalize")) {
        attempts += 1;
        finalized = attempts > 1;
        return Promise.resolve(
          jsonResponse({
            ...stoppedRecording,
            lifecycleStatus: finalized ? "uploaded" : "uploading",
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
      <StrictMode>
        <RecordingFoundation
          interactionId="interaction-1"
          interactionType="face_to_face_meeting"
          lifecycleStatus="in_progress"
          recoveryRecording={stoppedRecording}
          onFinalized={onFinalized}
          onRecoveryResolved={onRecoveryResolved}
        />
      </StrictMode>,
    );

    expect(screen.getByText(/finish it there/i)).toBeVisible();
    expect(microphone).not.toHaveBeenCalled();
    expect(onFinalized).not.toHaveBeenCalled();
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry finalisation" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The recording response did not match this interaction.",
    );
    expect(onRecoveryResolved).not.toHaveBeenCalled();
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
    expect(onFinalized).toHaveBeenCalledWith(
      expect.objectContaining({
        id: stoppedRecording.id,
        lifecycleStatus: "uploaded",
      }),
    );
    expect(onRecoveryResolved).toHaveBeenCalledTimes(1);
    expect(microphone).not.toHaveBeenCalled();
  });

  it("preserves restored details through a bad chunk refresh and requires a complete verified list before retrying finalisation", async () => {
    const microphone = vi.fn(() => Promise.reject(new Error("not requested")));
    installSupportedBrowser(microphone);
    const onActivityChange = vi.fn();
    const chunks = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([verifiedChunk]))
      .mockResolvedValueOnce(
        jsonResponse([
          { ...verifiedChunk, recordingSessionId: "foreign-recording" },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse([{ ...verifiedChunk, sequenceNumber: 2 }]),
      )
      .mockResolvedValueOnce(jsonResponse([verifiedChunk]));
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/recordings"))
        return Promise.resolve(jsonResponse([stoppedRecording]));
      if (url.endsWith("/chunks")) return chunks();
      return Promise.resolve(jsonResponse({ featureFlags: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RecordingFoundation
        interactionId={stoppedRecording.interactionId}
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
        recoveryRecording={stoppedRecording}
        onActivityChange={onActivityChange}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "Retry finalisation" }),
    ).toBeEnabled();
    const refresh = screen.getByRole("button", {
      name: "Refresh recording status",
    });
    fireEvent.click(refresh);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The saved recording chunks could not be verified.",
    );
    expect(screen.getByText("1 secure chunk uploaded")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry finalisation" }),
    ).not.toBeInTheDocument();
    expect(onActivityChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ blocksInteractionCompletion: true }),
    );

    fireEvent.click(refresh);
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Retry finalisation" }),
    ).not.toBeInTheDocument();
    fireEvent.click(refresh);
    expect(
      await screen.findByRole("button", { name: "Retry finalisation" }),
    ).toBeEnabled();
    expect(microphone).not.toHaveBeenCalled();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        /\/(start|stop|cancel|finalize)$/u.test(String(input)),
      ),
    ).toBe(false);
  });

  it("requires an exact cancellation acknowledgement before releasing the recovery block", async () => {
    const onRecoveryResolved = vi.fn();
    const onActivityChange = vi.fn();
    const cancel = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...stoppedRecording,
          id: "other-recording",
          lifecycleStatus: "cancelled",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ ...stoppedRecording, lifecycleStatus: "cancelled" }),
      );
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/recordings"))
          return Promise.resolve(jsonResponse([stoppedRecording]));
        if (url.endsWith("/chunks")) return Promise.resolve(jsonResponse([]));
        if (url.endsWith("/cancel")) return cancel();
        return Promise.resolve(jsonResponse({ featureFlags: {} }));
      }),
    );
    render(
      <RecordingFoundation
        interactionId={stoppedRecording.interactionId}
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
        recoveryRecording={stoppedRecording}
        onActivityChange={onActivityChange}
        onRecoveryResolved={onRecoveryResolved}
      />,
    );
    const cancelButton = await screen.findByRole("button", {
      name: "Cancel recording",
    });
    await waitFor(() => expect(cancelButton).toBeEnabled());
    fireEvent.click(cancelButton);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The recording response did not match this interaction.",
    );
    expect(onRecoveryResolved).not.toHaveBeenCalled();
    expect(onActivityChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ blocksInteractionCompletion: true }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel recording" }));
    await waitFor(() => expect(onRecoveryResolved).toHaveBeenCalledOnce());
    expect(onRecoveryResolved).toHaveBeenCalledWith(
      expect.objectContaining({
        id: stoppedRecording.id,
        lifecycleStatus: "cancelled",
      }),
    );
    expect(onActivityChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ blocksInteractionCompletion: false }),
    );
  });

  it("notifies Companion of verified absence when another tab removes the known recording", async () => {
    const onRecoveryListVerified = vi.fn();
    const onActivityChange = vi.fn();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/recordings")) return Promise.resolve(jsonResponse([]));
      return Promise.resolve(jsonResponse({ featureFlags: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RecordingFoundation
        interactionId={stoppedRecording.interactionId}
        interactionType="face_to_face_meeting"
        lifecycleStatus="in_progress"
        recoveryRecording={stoppedRecording}
        onActivityChange={onActivityChange}
        onRecoveryListVerified={onRecoveryListVerified}
      />,
    );
    await waitFor(() =>
      expect(onRecoveryListVerified).toHaveBeenCalledWith([]),
    );
    expect(onActivityChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        blocksInteractionCompletion: false,
        recording: null,
      }),
    );
    expect(
      screen.queryByRole("button", { name: "Cancel recording" }),
    ).not.toBeInTheDocument();
  });
});
