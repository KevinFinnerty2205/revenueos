import { apiRequest, ApiClientError } from "@/lib/api";

export const PROGRESSIVE_PCM_SAMPLE_RATE = 24_000;
export const PROGRESSIVE_PCM_MIME_TYPE =
  "audio/pcm;rate=24000;channels=1;format=s16le" as const;

const BYTES_PER_SAMPLE = 2;
const SEGMENT_DURATION_MS = 4_000;
const SEGMENT_BYTES =
  (PROGRESSIVE_PCM_SAMPLE_RATE * BYTES_PER_SAMPLE * SEGMENT_DURATION_MS) /
  1_000;
const MAX_BUFFERED_PCM_BYTES = PROGRESSIVE_PCM_SAMPLE_RATE * 2 * 20;
const REQUEST_TIMEOUT_MS = 12_000;
const FINISH_TIMEOUT_MS = 45_000;
const WORKLET_DRAIN_TIMEOUT_MS = 2_000;
const RETRY_DELAYS_MS = [0, 150, 600] as const;

export interface ProgressiveTranscriptEvent {
  eventId: string;
  streamId: string;
  providerName: string;
  itemId: string;
  sourceAudioSequence: number;
  itemIndex: number;
  revision: number;
  kind: "partial" | "final";
  text: string;
  startMs: number;
  endMs: number;
  speakerLabel: string | null;
}

interface ProgressiveSessionResponse {
  sessionId: string;
  interactionId: string;
  recordingSessionId: string;
  lifecycle:
    | "idle"
    | "capturing"
    | "recovering"
    | "finishing"
    | "finished"
    | "cancelled"
    | "failed";
  nextAudioSequence: number;
  events: ProgressiveTranscriptEvent[];
}

type ProgressiveRequester = <T>(path: string, init?: RequestInit) => Promise<T>;

export interface MediaStreamPcmCapture {
  pause(): void;
  resume(): void;
  drainAndClose(): Promise<void>;
  close(): Promise<void>;
}

type MediaStreamPcmCaptureFactory = (
  stream: MediaStream,
  onPcm: (pcm: Uint8Array) => void,
  audioContextFactory?: () => AudioContext,
  initiallyPaused?: boolean,
) => Promise<MediaStreamPcmCapture>;

export interface ProgressiveTranscriptionCapture {
  pause(): void;
  resume(): void;
  finish(): Promise<ProgressiveSessionResponse>;
  cancel(
    reason?: "user_cancelled" | "consent_withdrawn" | "capture_ended",
  ): Promise<void>;
}

export interface StartProgressiveTranscriptionCaptureOptions {
  interactionId: string;
  recordingSessionId: string;
  stream: MediaStream;
  externalProcessingAcknowledged: boolean;
  initiallyPaused?: boolean;
  onEvents?: (events: readonly ProgressiveTranscriptEvent[]) => void;
  onRecoverableError?: (error: Error) => void;
  request?: ProgressiveRequester;
  audioContextFactory?: () => AudioContext;
  mediaStreamPcmCaptureFactory?: MediaStreamPcmCaptureFactory;
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds));
}

function randomKey(prefix: string): string {
  const suffix =
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `${prefix}-${suffix}`;
}

function encodeBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 16_384) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 16_384));
  }
  return globalThis.btoa(binary);
}

function isRetryable(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof ApiClientError &&
      (error.status === 0 ||
        error.status === 408 ||
        error.status === 429 ||
        error.status >= 500))
  );
}

async function requestWithTimeout<T>(
  request: ProgressiveRequester,
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await request<T>(path, { ...init, signal: controller.signal });
  } finally {
    globalThis.clearTimeout(timer);
  }
}

async function retryMutation<T>(operation: () => Promise<T>): Promise<T> {
  let failure: unknown = null;
  for (const delay of RETRY_DELAYS_MS) {
    if (delay) await wait(delay);
    try {
      return await operation();
    } catch (error: unknown) {
      failure = error;
      if (!isRetryable(error)) throw error;
    }
  }
  throw failure instanceof Error
    ? failure
    : new Error("Progressive transcription is temporarily unavailable.");
}

export class StreamingPcm16Encoder {
  private readonly sourcePerTargetSample: number;
  private remainder = new Float32Array(0);
  private sourcePosition = 0;

  constructor(readonly sourceSampleRate: number) {
    if (
      !Number.isFinite(sourceSampleRate) ||
      sourceSampleRate < PROGRESSIVE_PCM_SAMPLE_RATE
    ) {
      throw new Error(
        "The browser audio sample rate is incompatible with progressive transcription.",
      );
    }
    this.sourcePerTargetSample = sourceSampleRate / PROGRESSIVE_PCM_SAMPLE_RATE;
  }

  encode(input: Float32Array): Uint8Array {
    if (input.length === 0) return new Uint8Array(0);
    const combined = new Float32Array(this.remainder.length + input.length);
    combined.set(this.remainder);
    combined.set(input, this.remainder.length);
    const values: number[] = [];
    while (this.sourcePosition + 1 < combined.length) {
      const leftIndex = Math.floor(this.sourcePosition);
      const fraction = this.sourcePosition - leftIndex;
      const left = combined[leftIndex] ?? 0;
      const right = combined[leftIndex + 1] ?? left;
      values.push(left + (right - left) * fraction);
      this.sourcePosition += this.sourcePerTargetSample;
    }
    const consumed = Math.floor(this.sourcePosition);
    this.remainder = combined.slice(consumed);
    this.sourcePosition -= consumed;
    return this.toPcm16(values);
  }

  flush(): Uint8Array {
    const values: number[] = [];
    const lastAvailablePosition = this.remainder.length - 1;
    while (this.sourcePosition <= lastAvailablePosition) {
      const leftIndex = Math.floor(this.sourcePosition);
      const fraction = this.sourcePosition - leftIndex;
      const left = this.remainder[leftIndex] ?? 0;
      const right = this.remainder[leftIndex + 1] ?? left;
      values.push(left + (right - left) * fraction);
      this.sourcePosition += this.sourcePerTargetSample;
    }
    this.remainder = new Float32Array(0);
    this.sourcePosition = 0;
    return this.toPcm16(values);
  }

  private toPcm16(values: readonly number[]): Uint8Array {
    const output = new Uint8Array(values.length * BYTES_PER_SAMPLE);
    const view = new DataView(output.buffer);
    values.forEach((value, index) => {
      const clamped = Math.max(-1, Math.min(1, value));
      const integer = Math.round(
        clamped < 0 ? clamped * 32_768 : clamped * 32_767,
      );
      view.setInt16(index * BYTES_PER_SAMPLE, integer, true);
    });
    return output;
  }
}

export async function startMediaStreamPcmCapture(
  stream: MediaStream,
  onPcm: (pcm: Uint8Array) => void,
  audioContextFactory: () => AudioContext = () => new AudioContext(),
  initiallyPaused = false,
): Promise<MediaStreamPcmCapture> {
  if (
    stream.getAudioTracks().length !== 1 ||
    stream.getVideoTracks().length !== 0
  ) {
    throw new Error(
      "Progressive transcription requires one audio-only browser stream.",
    );
  }
  const context = audioContextFactory();
  if (!context.audioWorklet) {
    await context.close().catch(() => undefined);
    throw new Error(
      "This browser does not support the progressive audio processor.",
    );
  }
  const encoder = new StreamingPcm16Encoder(context.sampleRate);
  await context.audioWorklet.addModule("/progressive-pcm-worklet.js");
  if (context.state === "suspended") await context.resume();
  if (context.state !== "running") {
    await context.close().catch(() => undefined);
    throw new Error(
      "The browser could not activate progressive audio processing.",
    );
  }
  const source = context.createMediaStreamSource(stream);
  const processor = new AudioWorkletNode(context, "oryntela-pcm-tap", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    channelCount: 1,
    channelCountMode: "explicit",
  });
  const silentOutput = context.createGain();
  silentOutput.gain.value = 0;
  source.connect(processor).connect(silentOutput).connect(context.destination);
  let accepting = !initiallyPaused;
  let closed = false;
  let sourceConnected = true;
  let nextWorkletSequence = 0;
  let protocolError: Error | null = null;
  let drainPromise: Promise<void> | null = null;
  let pendingDrain: {
    token: string;
    timer: ReturnType<typeof setTimeout>;
    resolve: () => void;
    reject: (error: Error) => void;
  } | null = null;

  const failProtocol = (message: string) => {
    protocolError ??= new Error(message);
    accepting = false;
    if (pendingDrain) {
      const drain = pendingDrain;
      pendingDrain = null;
      globalThis.clearTimeout(drain.timer);
      drain.reject(protocolError);
    }
  };

  const closeNodes = async () => {
    if (closed) return;
    closed = true;
    if (pendingDrain) {
      const drain = pendingDrain;
      pendingDrain = null;
      globalThis.clearTimeout(drain.timer);
      drain.reject(
        new Error("The browser audio processor closed before its final drain."),
      );
    }
    processor.port.onmessage = null;
    if (sourceConnected) source.disconnect();
    sourceConnected = false;
    processor.disconnect();
    silentOutput.disconnect();
    await context.close().catch(() => undefined);
  };
  processor.port.onmessage = (event: MessageEvent<unknown>) => {
    if (closed) return;
    const message = event.data as {
      type?: unknown;
      sequence?: unknown;
      samples?: unknown;
      token?: unknown;
      finalSequence?: unknown;
    } | null;
    if (message?.type === "pcm") {
      if (
        !Number.isSafeInteger(message.sequence) ||
        Number(message.sequence) < 0 ||
        !(message.samples instanceof Float32Array)
      ) {
        failProtocol("The browser audio processor returned invalid PCM data.");
        return;
      }
      const sequence = Number(message.sequence);
      if (sequence < nextWorkletSequence) return;
      if (sequence > nextWorkletSequence) {
        failProtocol("The browser audio processor skipped a PCM frame.");
        return;
      }
      nextWorkletSequence += 1;
      if (!accepting) return;
      const pcm = encoder.encode(message.samples);
      if (pcm.length > 0) onPcm(pcm);
      return;
    }
    if (message?.type === "drain_ack" && pendingDrain) {
      if (message.token !== pendingDrain.token) return;
      if (
        !Number.isSafeInteger(message.finalSequence) ||
        Number(message.finalSequence) !== nextWorkletSequence - 1
      ) {
        failProtocol(
          "The browser audio processor did not drain every final PCM frame.",
        );
        return;
      }
      const drain = pendingDrain;
      pendingDrain = null;
      globalThis.clearTimeout(drain.timer);
      const pcm = encoder.flush();
      if (pcm.length > 0) onPcm(pcm);
      drain.resolve();
    }
  };
  return {
    pause() {
      accepting = false;
    },
    resume() {
      accepting = true;
    },
    async drainAndClose() {
      if (closed) return;
      if (drainPromise) return drainPromise;
      drainPromise = (async () => {
        try {
          if (protocolError) throw protocolError;
          const token = randomKey("pcm-drain");
          await new Promise<void>((resolve, reject) => {
            const timer = globalThis.setTimeout(() => {
              if (pendingDrain?.token === token) pendingDrain = null;
              reject(
                new Error(
                  "The browser audio processor did not acknowledge its final PCM drain.",
                ),
              );
            }, WORKLET_DRAIN_TIMEOUT_MS);
            pendingDrain = { token, timer, resolve, reject };
            processor.port.postMessage({ type: "drain", token });
          });
        } finally {
          await closeNodes();
        }
      })();
      return drainPromise;
    },
    async close() {
      await closeNodes();
    },
  };
}

class ProgressiveTransport implements ProgressiveTranscriptionCapture {
  private readonly path: string;
  private readonly seenEventIds = new Set<string>();
  private readonly seenEventOrder: string[] = [];
  private readonly chunks: Uint8Array[] = [];
  private operation = Promise.resolve();
  private capture: MediaStreamPcmCapture | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private pollQueued = false;
  private bufferedBytes = 0;
  private stagedBytes = 0;
  private nextSequence = 0;
  private emittedSamples = 0;
  private failed: Error | null = null;
  private terminal = false;
  private finishing = false;
  private serverFinished = false;
  private cancelPromise: Promise<void> | null = null;
  private cancelled = false;
  private paused: boolean;

  constructor(
    private readonly request: ProgressiveRequester,
    private readonly interactionId: string,
    private readonly sessionId: string,
    private readonly onEvents: (
      events: readonly ProgressiveTranscriptEvent[],
    ) => void,
    private readonly onRecoverableError: (error: Error) => void,
    initiallyPaused: boolean,
  ) {
    this.path = `/api/v1/interactions/${interactionId}/progressive-transcription/sessions/${sessionId}`;
    this.paused = initiallyPaused;
  }

  attach(capture: MediaStreamPcmCapture): void {
    this.capture = capture;
    this.pollTimer = globalThis.setInterval(() => this.queuePoll(), 750);
  }

  accept(pcm: Uint8Array): void {
    if (this.terminal || this.paused || this.failed || pcm.length === 0) return;
    this.bufferedBytes += pcm.length;
    this.stagedBytes += pcm.length;
    if (this.bufferedBytes > MAX_BUFFERED_PCM_BYTES) {
      this.fail(
        new Error(
          "Progressive transcription stopped because its bounded audio buffer filled.",
        ),
      );
      return;
    }
    this.chunks.push(pcm);
    while (this.stagedBytes >= SEGMENT_BYTES)
      this.queueSegment(this.consume(SEGMENT_BYTES));
  }

  pause(): void {
    this.paused = true;
    this.capture?.pause();
  }

  resume(): void {
    if (this.terminal) return;
    this.paused = false;
    this.capture?.resume();
  }

  async finish(): Promise<ProgressiveSessionResponse> {
    if (this.terminal || this.finishing)
      throw new Error("Progressive transcription has already ended.");
    this.finishing = true;
    this.clearPoll();
    try {
      await this.capture?.drainAndClose();
    } catch (error: unknown) {
      this.finishing = false;
      await this.cancel("capture_ended");
      throw error;
    }
    this.capture = null;
    this.terminal = true;
    try {
      if (this.stagedBytes > 0)
        this.queueSegment(this.consume(this.stagedBytes));
      await this.operation;
      if (this.failed) throw this.failed;
      const response = await retryMutation(() =>
        requestWithTimeout<ProgressiveSessionResponse>(
          this.request,
          `${this.path}/finish`,
          {
            method: "POST",
            body: JSON.stringify({ externalProcessingAcknowledged: true }),
          },
          FINISH_TIMEOUT_MS,
        ),
      );
      this.serverFinished = true;
      this.publish(response);
      return response;
    } catch (error: unknown) {
      this.fail(error);
      await this.cancel("capture_ended");
      throw this.failed ?? error;
    }
  }

  async cancel(
    reason:
      | "user_cancelled"
      | "consent_withdrawn"
      | "capture_ended" = "user_cancelled",
  ): Promise<void> {
    if (this.serverFinished) return;
    if (this.cancelPromise) return this.cancelPromise;
    this.terminal = true;
    this.cancelled = true;
    this.clearPoll();
    this.cancelPromise = (async () => {
      await this.capture?.close();
      this.capture = null;
      await requestWithTimeout<ProgressiveSessionResponse>(
        this.request,
        `${this.path}/cancel`,
        { method: "POST", body: JSON.stringify({ reason }) },
        REQUEST_TIMEOUT_MS,
      ).catch(() => undefined);
    })();
    return this.cancelPromise;
  }

  private queueSegment(bytes: Uint8Array): void {
    const sequenceNumber = this.nextSequence++;
    const sampleCount = bytes.length / BYTES_PER_SAMPLE;
    const startMs = Math.round(
      (this.emittedSamples * 1_000) / PROGRESSIVE_PCM_SAMPLE_RATE,
    );
    this.emittedSamples += sampleCount;
    const endMs = Math.round(
      (this.emittedSamples * 1_000) / PROGRESSIVE_PCM_SAMPLE_RATE,
    );
    this.operation = this.operation
      .then(async () => {
        if (this.failed || this.cancelled) return;
        const response = await retryMutation(() =>
          requestWithTimeout<ProgressiveSessionResponse>(
            this.request,
            `${this.path}/audio`,
            {
              method: "POST",
              body: JSON.stringify({
                sequenceNumber,
                startMs,
                endMs,
                mimeType: PROGRESSIVE_PCM_MIME_TYPE,
                audioBase64: encodeBase64(bytes),
                externalProcessingAcknowledged: true,
              }),
            },
            REQUEST_TIMEOUT_MS,
          ),
        );
        if (!this.cancelled) this.publish(response);
      })
      .catch((error: unknown) => {
        if (!this.cancelled) this.fail(error);
      })
      .finally(() => {
        this.bufferedBytes -= bytes.length;
      });
  }

  private queuePoll(): void {
    if (this.pollQueued || this.terminal || this.failed) return;
    this.pollQueued = true;
    this.operation = this.operation
      .then(async () => {
        if (this.terminal || this.failed) return;
        const response = await retryMutation(() =>
          requestWithTimeout<ProgressiveSessionResponse>(
            this.request,
            `${this.path}/poll`,
            {
              method: "POST",
              body: JSON.stringify({ externalProcessingAcknowledged: true }),
            },
            REQUEST_TIMEOUT_MS,
          ),
        );
        if (!this.cancelled) this.publish(response);
      })
      .catch((error: unknown) => {
        if (!this.cancelled) this.fail(error);
      })
      .finally(() => {
        this.pollQueued = false;
      });
  }

  private consume(byteCount: number): Uint8Array {
    const output = new Uint8Array(byteCount);
    let written = 0;
    while (written < byteCount) {
      const chunk = this.chunks[0];
      if (!chunk) throw new Error("Progressive audio buffer underflowed.");
      const take = Math.min(chunk.length, byteCount - written);
      output.set(chunk.subarray(0, take), written);
      written += take;
      if (take === chunk.length) this.chunks.shift();
      else this.chunks[0] = chunk.subarray(take);
    }
    this.stagedBytes -= byteCount;
    return output;
  }

  private publish(response: ProgressiveSessionResponse): void {
    const fresh = response.events.filter((event) => {
      if (this.seenEventIds.has(event.eventId)) return false;
      this.seenEventIds.add(event.eventId);
      this.seenEventOrder.push(event.eventId);
      while (this.seenEventOrder.length > 480) {
        const oldest = this.seenEventOrder.shift();
        if (oldest) this.seenEventIds.delete(oldest);
      }
      return true;
    });
    if (fresh.length > 0) this.onEvents(fresh);
  }

  private fail(error: unknown): void {
    if (this.failed) return;
    this.failed =
      error instanceof Error
        ? error
        : new Error("Progressive transcription became unavailable.");
    this.clearPoll();
    this.capture?.pause();
    this.onRecoverableError(this.failed);
    void this.cancel("capture_ended");
  }

  private clearPoll(): void {
    if (this.pollTimer !== null) globalThis.clearInterval(this.pollTimer);
    this.pollTimer = null;
  }
}

export async function startProgressiveTranscriptionCapture(
  options: StartProgressiveTranscriptionCaptureOptions,
): Promise<ProgressiveTranscriptionCapture> {
  if (!options.externalProcessingAcknowledged) {
    throw new Error(
      "External-processing acknowledgement is required before progressive transcription starts.",
    );
  }
  const request = options.request ?? apiRequest;
  const basePath = `/api/v1/interactions/${options.interactionId}/progressive-transcription/sessions`;
  const idempotencyKey = randomKey("progressive-transcription");
  const bufferedPcm: Uint8Array[] = [];
  let bufferedPcmBytes = 0;
  let bootstrapFailure: Error | null = null;
  let capture: MediaStreamPcmCapture | null = null;
  let transport: ProgressiveTransport | null = null;
  try {
    capture = await (
      options.mediaStreamPcmCaptureFactory ?? startMediaStreamPcmCapture
    )(
      options.stream,
      (pcm) => {
        if (transport) {
          transport.accept(pcm);
          return;
        }
        if (options.initiallyPaused) return;
        if (bootstrapFailure || pcm.length === 0) return;
        if (bufferedPcmBytes + pcm.length > MAX_BUFFERED_PCM_BYTES) {
          bootstrapFailure = new Error(
            "Progressive transcription stopped because its bounded startup audio buffer filled.",
          );
          capture?.pause();
          return;
        }
        bufferedPcm.push(pcm);
        bufferedPcmBytes += pcm.length;
      },
      options.audioContextFactory,
      options.initiallyPaused,
    );
    if (bootstrapFailure) capture.pause();
    const started = await retryMutation(() =>
      requestWithTimeout<ProgressiveSessionResponse>(
        request,
        basePath,
        {
          method: "POST",
          body: JSON.stringify({
            recordingSessionId: options.recordingSessionId,
            externalProcessingAcknowledged: true,
            idempotencyKey,
          }),
        },
        REQUEST_TIMEOUT_MS,
      ),
    );
    transport = new ProgressiveTransport(
      request,
      options.interactionId,
      started.sessionId,
      options.onEvents ?? (() => undefined),
      options.onRecoverableError ?? (() => undefined),
      options.initiallyPaused ?? false,
    );
    if (bootstrapFailure) throw bootstrapFailure;
    for (const pcm of bufferedPcm) transport.accept(pcm);
    bufferedPcm.length = 0;
    bufferedPcmBytes = 0;
    transport.attach(capture);
    return transport;
  } catch (error: unknown) {
    await capture?.close();
    await transport?.cancel("capture_ended");
    throw error;
  }
}
