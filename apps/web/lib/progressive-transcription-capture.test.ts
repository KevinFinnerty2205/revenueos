import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api";
import {
  PROGRESSIVE_PCM_SAMPLE_RATE,
  StreamingPcm16Encoder,
  startMediaStreamPcmCapture,
  startProgressiveTranscriptionCapture,
} from "@/lib/progressive-transcription-capture";

function sine(sampleRate: number, durationSeconds: number): Float32Array {
  return Float32Array.from(
    { length: sampleRate * durationSeconds },
    (_, index) => Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 0.25,
  );
}

interface FakeWorkletMessage {
  type: "pcm" | "drain_ack";
  sequence?: number;
  samples?: Float32Array;
  token?: string;
  finalSequence?: number;
}

function mediaStreamCaptureEnvironment(
  drainMessages: (token: string) => readonly FakeWorkletMessage[],
) {
  const lifecycle: string[] = [];
  const source = {
    connect: vi.fn((destination: unknown) => destination),
    disconnect: vi.fn(() => lifecycle.push("source_disconnected")),
  };
  const silentOutput = {
    gain: { value: 1 },
    connect: vi.fn((destination: unknown) => destination),
    disconnect: vi.fn(),
  };
  const port: {
    onmessage: ((event: MessageEvent<unknown>) => void) | null;
    postMessage: ReturnType<typeof vi.fn>;
  } = {
    onmessage: null,
    postMessage: vi.fn((message: { type?: unknown; token?: unknown }) => {
      if (message.type !== "drain" || typeof message.token !== "string") return;
      const token = message.token;
      lifecycle.push("drain_requested");
      globalThis.queueMicrotask(() => {
        for (const response of drainMessages(token)) {
          if (response.type === "drain_ack") lifecycle.push("ack_emitted");
          port.onmessage?.({ data: response } as MessageEvent<unknown>);
        }
      });
    }),
  };
  const processor = {
    port,
    connect: vi.fn((destination: unknown) => destination),
    disconnect: vi.fn(),
  };
  class FakeAudioWorkletNode {
    readonly port = port;
    readonly connect = processor.connect;
    readonly disconnect = processor.disconnect;
  }
  vi.stubGlobal("AudioWorkletNode", FakeAudioWorkletNode);
  const context = {
    audioWorklet: { addModule: vi.fn(() => Promise.resolve()) },
    sampleRate: 24_000,
    state: "running",
    destination: {},
    createMediaStreamSource: vi.fn(() => source),
    createGain: vi.fn(() => silentOutput),
    resume: vi.fn(() => Promise.resolve()),
    close: vi.fn(() => {
      lifecycle.push("context_closed");
      return Promise.resolve();
    }),
  };
  const stream = {
    getAudioTracks: () => [{}],
    getVideoTracks: () => [],
  } as unknown as MediaStream;
  return { context, lifecycle, port, source, stream };
}

describe("progressive transcription PCM capture", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("statefully resamples browser frames to mono 24 kHz little-endian PCM16", () => {
    const encoder = new StreamingPcm16Encoder(48_000);
    const input = sine(48_000, 1);
    const chunks: Uint8Array[] = [];
    for (let offset = 0; offset < input.length; offset += 128) {
      chunks.push(encoder.encode(input.subarray(offset, offset + 128)));
    }
    const byteLength = chunks.reduce((total, chunk) => total + chunk.length, 0);
    expect(byteLength).toBeGreaterThanOrEqual(
      PROGRESSIVE_PCM_SAMPLE_RATE * 2 - 4,
    );
    expect(byteLength).toBeLessThanOrEqual(PROGRESSIVE_PCM_SAMPLE_RATE * 2);
    const pcm = new Uint8Array(byteLength);
    let offset = 0;
    chunks.forEach((chunk) => {
      pcm.set(chunk, offset);
      offset += chunk.length;
    });
    const view = new DataView(pcm.buffer);
    const firstQuarterCycle = view.getInt16(
      Math.round(PROGRESSIVE_PCM_SAMPLE_RATE / (440 * 4)) * 2,
      true,
    );
    expect(firstQuarterCycle).toBeGreaterThan(7_000);
    const rms = Math.sqrt(
      Array.from(
        { length: pcm.length / 2 },
        (_, index) => view.getInt16(index * 2, true) ** 2,
      ).reduce((sum, value) => sum + value, 0) /
        (pcm.length / 2),
    );
    expect(rms).toBeGreaterThan(5_000);
  });

  it("flushes the final available source sample exactly once", () => {
    const encoder = new StreamingPcm16Encoder(48_000);
    expect(encoder.encode(Float32Array.of(0.5))).toHaveLength(0);
    const trailingPcm = encoder.flush();
    expect(trailingPcm).toHaveLength(2);
    expect(new DataView(trailingPcm.buffer).getInt16(0, true)).toBe(16_384);
    expect(encoder.flush()).toHaveLength(0);
  });

  it("crosses a sequenced worklet render boundary and keeps the trailing frame exactly once", async () => {
    const firstFrame = new Float32Array(128);
    const trailingFrame = new Float32Array(128).fill(0.75);
    const setup = mediaStreamCaptureEnvironment((token) => [
      { type: "pcm", sequence: 0, samples: firstFrame },
      { type: "pcm", sequence: 1, samples: trailingFrame },
      { type: "pcm", sequence: 1, samples: trailingFrame },
      { type: "drain_ack", token, finalSequence: 1 },
    ]);
    const chunks: Uint8Array[] = [];
    const capture = await startMediaStreamPcmCapture(
      setup.stream,
      (pcm) => {
        setup.lifecycle.push("pcm_emitted");
        chunks.push(pcm);
      },
      () => setup.context as unknown as AudioContext,
    );

    await capture.drainAndClose();

    const pcm = new Uint8Array(
      chunks.reduce((total, chunk) => total + chunk.length, 0),
    );
    let offset = 0;
    for (const chunk of chunks) {
      pcm.set(chunk, offset);
      offset += chunk.length;
    }
    expect(pcm).toHaveLength(256 * 2);
    const samples = Array.from({ length: pcm.length / 2 }, (_, index) =>
      new DataView(pcm.buffer).getInt16(index * 2, true),
    );
    expect(samples.filter((sample) => sample === 24_575)).toHaveLength(128);
    expect(setup.port.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "drain" }),
    );
    expect(setup.lifecycle.indexOf("ack_emitted")).toBeLessThan(
      setup.lifecycle.indexOf("source_disconnected"),
    );
    expect(setup.source.disconnect).toHaveBeenCalledTimes(1);
    expect(setup.context.close).toHaveBeenCalledTimes(1);
  });

  it("fails the final worklet boundary within a bounded timeout", async () => {
    vi.useFakeTimers();
    try {
      const setup = mediaStreamCaptureEnvironment(() => []);
      const capture = await startMediaStreamPcmCapture(
        setup.stream,
        () => undefined,
        () => setup.context as unknown as AudioContext,
      );

      const assertion = expect(capture.drainAndClose()).rejects.toThrow(
        /did not acknowledge its final PCM drain/u,
      );
      await vi.advanceTimersByTimeAsync(2_000);
      await assertion;

      expect(setup.source.disconnect).toHaveBeenCalledTimes(1);
      expect(setup.context.close).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("rejects missing external-processing acknowledgement before API or audio access", async () => {
    const request = vi.fn();
    await expect(
      startProgressiveTranscriptionCapture({
        interactionId: "interaction",
        recordingSessionId: "recording",
        stream: {} as MediaStream,
        externalProcessingAcknowledged: false,
        request,
      }),
    ).rejects.toThrow(/acknowledgement/u);
    expect(request).not.toHaveBeenCalled();
  });

  it("reuses the start key and drains queued worklet PCM before finalising", async () => {
    const paths: string[] = [];
    const startKeys: string[] = [];
    let submittedAudio: { audioBase64: string; endMs: number } | null = null;
    let startAttempt = 0;
    const response = (lifecycle: "capturing" | "finished") => ({
      sessionId: "session-1",
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      lifecycle,
      nextAudioSequence: 0,
      events: [],
    });
    const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
      paths.push(path);
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      if (path.endsWith("/sessions")) {
        startKeys.push(String(body.idempotencyKey));
        startAttempt += 1;
        if (startAttempt === 1) {
          throw new ApiClientError(
            "Synthetic lost response.",
            0,
            "network_error",
          );
        }
        return response("capturing") as T;
      }
      if (path.endsWith("/audio")) {
        submittedAudio = {
          audioBase64: String(body.audioBase64),
          endMs: Number(body.endMs),
        };
      }
      return response(path.endsWith("/finish") ? "finished" : "capturing") as T;
    };
    const capture = await startProgressiveTranscriptionCapture({
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      stream: {} as MediaStream,
      externalProcessingAcknowledged: true,
      request,
      mediaStreamPcmCaptureFactory: async (_stream, onPcm) => ({
        pause() {},
        resume() {},
        async drainAndClose() {
          await Promise.resolve();
          onPcm(new Uint8Array(96).fill(1));
        },
        async close() {},
      }),
    });

    await capture.finish();

    expect(startKeys).toHaveLength(2);
    expect(new Set(startKeys).size).toBe(1);
    const audioIndex = paths.findIndex((path) => path.endsWith("/audio"));
    const finishIndex = paths.findIndex((path) => path.endsWith("/finish"));
    expect(audioIndex).toBeGreaterThan(0);
    expect(finishIndex).toBeGreaterThan(audioIndex);
    expect(submittedAudio).not.toBeNull();
    expect(atob(submittedAudio!.audioBase64)).toHaveLength(96);
    expect(submittedAudio!.endMs).toBeGreaterThan(0);
  });

  it("buffers bounded PCM captured while the authenticated provider session starts", async () => {
    let releaseStart: () => void = () => undefined;
    const startGate = new Promise<void>((resolve) => {
      releaseStart = resolve;
    });
    let markCaptureAttached: () => void = () => undefined;
    const captureAttached = new Promise<void>((resolve) => {
      markCaptureAttached = resolve;
    });
    let submittedBytes = 0;
    const response = {
      sessionId: "session-bootstrapped",
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      lifecycle: "capturing" as const,
      nextAudioSequence: 0,
      events: [],
    };
    const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
      if (path.endsWith("/sessions")) await startGate;
      if (path.endsWith("/audio")) {
        const body = JSON.parse(String(init?.body)) as { audioBase64: string };
        submittedBytes += atob(body.audioBase64).length;
      }
      return response as T;
    };
    const starting = startProgressiveTranscriptionCapture({
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      stream: {} as MediaStream,
      externalProcessingAcknowledged: true,
      request,
      mediaStreamPcmCaptureFactory: async (_stream, onPcm) => {
        onPcm(new Uint8Array(192).fill(7));
        markCaptureAttached();
        return {
          pause() {},
          resume() {},
          async drainAndClose() {},
          async close() {},
        };
      },
    });

    await captureAttached;
    expect(submittedBytes).toBe(0);
    releaseStart();
    const capture = await starting;
    await capture.finish();

    expect(submittedBytes).toBe(192);
  });

  it("drops pre-arm PCM and keeps samples emitted immediately when an initially paused capture resumes", async () => {
    const submittedAudio: string[] = [];
    let providerPrepared = false;
    const response = (lifecycle: "capturing" | "finished") => ({
      sessionId: "session-paused",
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      lifecycle,
      nextAudioSequence: 0,
      events: [],
    });
    const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
      if (path.endsWith("/sessions")) providerPrepared = true;
      if (path.endsWith("/audio")) {
        const body = JSON.parse(String(init?.body)) as { audioBase64: string };
        submittedAudio.push(body.audioBase64);
      }
      return response(path.endsWith("/finish") ? "finished" : "capturing") as T;
    };
    const capture = await startProgressiveTranscriptionCapture({
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      stream: {} as MediaStream,
      externalProcessingAcknowledged: true,
      initiallyPaused: true,
      request,
      mediaStreamPcmCaptureFactory: async (
        _stream,
        onPcm,
        _audioContextFactory,
        initiallyPaused,
      ) => {
        expect(initiallyPaused).toBe(true);
        onPcm(new Uint8Array(96).fill(1));
        return {
          pause() {},
          resume() {
            onPcm(new Uint8Array(96).fill(2));
          },
          async drainAndClose() {},
          async close() {},
        };
      },
    });

    expect(providerPrepared).toBe(true);
    expect(submittedAudio).toHaveLength(0);
    capture.resume();
    await capture.finish();

    expect(submittedAudio).toHaveLength(1);
    expect(
      Array.from(
        Uint8Array.from(atob(submittedAudio[0]!), (value) =>
          value.charCodeAt(0),
        ),
      ),
    ).toEqual(Array.from(new Uint8Array(96).fill(2)));
  });

  it("sends one server cancellation when the final queued audio upload fails", async () => {
    let audioRequests = 0;
    let cancelRequests = 0;
    let finishRequests = 0;
    const response = {
      sessionId: "session-1",
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      lifecycle: "capturing" as const,
      nextAudioSequence: 0,
      events: [],
    };
    const request = async <T>(path: string): Promise<T> => {
      if (path.endsWith("/audio")) {
        audioRequests += 1;
        throw new ApiClientError(
          "Synthetic rejected audio.",
          422,
          "invalid_progressive_audio",
        );
      }
      if (path.endsWith("/cancel")) cancelRequests += 1;
      if (path.endsWith("/finish")) finishRequests += 1;
      return response as T;
    };
    const capture = await startProgressiveTranscriptionCapture({
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      stream: {} as MediaStream,
      externalProcessingAcknowledged: true,
      request,
      mediaStreamPcmCaptureFactory: async (_stream, onPcm) => ({
        pause() {},
        resume() {},
        async drainAndClose() {
          onPcm(new Uint8Array(96).fill(1));
        },
        async close() {},
      }),
    });

    await expect(capture.finish()).rejects.toThrow(/rejected audio/u);
    await capture.cancel("capture_ended");

    expect(audioRequests).toBe(1);
    expect(finishRequests).toBe(0);
    expect(cancelRequests).toBe(1);
  });

  it("drops queued PCM after cancellation while one audio request is in flight", async () => {
    let audioRequests = 0;
    let cancelRequests = 0;
    const audioGate: { release: () => void } = { release: () => undefined };
    let markAudioStarted: (() => void) | null = null;
    const audioStarted = new Promise<void>((resolve) => {
      markAudioStarted = resolve;
    });
    const audioRelease = new Promise<void>((resolve) => {
      audioGate.release = resolve;
    });
    const recoverableError = vi.fn();
    const response = {
      sessionId: "session-1",
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      lifecycle: "capturing" as const,
      nextAudioSequence: 0,
      events: [],
    };
    const request = async <T>(path: string): Promise<T> => {
      if (path.endsWith("/audio")) {
        audioRequests += 1;
        markAudioStarted?.();
        await audioRelease;
      }
      if (path.endsWith("/cancel")) cancelRequests += 1;
      return response as T;
    };
    const capture = await startProgressiveTranscriptionCapture({
      interactionId: "interaction-1",
      recordingSessionId: "recording-1",
      stream: {} as MediaStream,
      externalProcessingAcknowledged: true,
      request,
      onRecoverableError: recoverableError,
      mediaStreamPcmCaptureFactory: async (_stream, onPcm) => {
        onPcm(new Uint8Array(24_000 * 2 * 4 * 3).fill(1));
        return {
          pause() {},
          resume() {},
          async drainAndClose() {},
          async close() {},
        };
      },
    });

    await audioStarted;
    const cancelled = capture.cancel("consent_withdrawn");
    audioGate.release();
    await cancelled;
    await new Promise((resolve) => globalThis.setTimeout(resolve, 0));

    expect(audioRequests).toBe(1);
    expect(cancelRequests).toBe(1);
    expect(recoverableError).not.toHaveBeenCalled();
  });

  it("suppresses an in-flight poll result and error callbacks after cancellation", async () => {
    vi.useFakeTimers();
    try {
      let releasePoll: (response: object) => void = () => undefined;
      let markPollStarted: () => void = () => undefined;
      const pollStarted = new Promise<void>((resolve) => {
        markPollStarted = resolve;
      });
      const pollResponse = new Promise<object>((resolve) => {
        releasePoll = resolve;
      });
      const onEvents = vi.fn();
      const onRecoverableError = vi.fn();
      const response = {
        sessionId: "session-1",
        interactionId: "interaction-1",
        recordingSessionId: "recording-1",
        lifecycle: "capturing" as const,
        nextAudioSequence: 0,
        events: [],
      };
      const request = async <T>(path: string): Promise<T> => {
        if (path.endsWith("/poll")) {
          markPollStarted();
          return (await pollResponse) as T;
        }
        return response as T;
      };
      const capture = await startProgressiveTranscriptionCapture({
        interactionId: "interaction-1",
        recordingSessionId: "recording-1",
        stream: {} as MediaStream,
        externalProcessingAcknowledged: true,
        request,
        onEvents,
        onRecoverableError,
        mediaStreamPcmCaptureFactory: async () => ({
          pause() {},
          resume() {},
          async drainAndClose() {},
          async close() {},
        }),
      });

      await vi.advanceTimersByTimeAsync(750);
      await pollStarted;
      const cancelled = capture.cancel("consent_withdrawn");
      releasePoll({
        ...response,
        events: [
          {
            eventId: "late-event",
            streamId: "session-1",
            providerName: "fixture",
            itemId: "late-item",
            sourceAudioSequence: 0,
            itemIndex: 0,
            revision: 1,
            kind: "final",
            text: "Must not publish",
            startMs: 0,
            endMs: 1,
            speakerLabel: null,
          },
        ],
      });
      await cancelled;
      await vi.runAllTimersAsync();

      expect(onEvents).not.toHaveBeenCalled();
      expect(onRecoverableError).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
