import { Buffer } from "node:buffer";
import { expect, test } from "@playwright/test";

const sessionId = "00000000-0000-4000-8000-000000000333";
const interactionId = "00000000-0000-4000-8000-000000000111";
const recordingSessionId = "00000000-0000-4000-8000-000000000222";
const pcmMimeType = "audio/pcm;rate=24000;channels=1;format=s16le";

interface SubmittedAudio {
  sequenceNumber: number;
  startMs: number;
  endMs: number;
  mimeType: string;
  audioBase64: string;
  externalProcessingAcknowledged: boolean;
}

interface BrowserCaptureProof {
  lifecycle: string;
  eventIds: string[];
  batchBytes: number;
  batchDurationSeconds: number;
  batchMarkerRatio: number;
}

function event(revision: number, kind: "partial" | "final", text: string) {
  return {
    eventId: `fixture-event-${revision}`,
    streamId: sessionId,
    providerName: "local-browser-fixture",
    itemId: "fixture-item",
    sourceAudioSequence: 0,
    itemIndex: 0,
    revision,
    kind,
    text,
    startMs: 0,
    endMs: 1_250,
    speakerLabel: null,
  };
}

function response(
  lifecycle: "capturing" | "finished",
  events: ReturnType<typeof event>[],
) {
  return {
    sessionId,
    interactionId,
    recordingSessionId,
    lifecycle,
    mimeType: pcmMimeType,
    sampleRate: 24_000,
    channels: 1,
    nextAudioSequence: 0,
    bufferedAudioSegments: 0,
    reconnectAttempts: 0,
    lastErrorCode: null,
    expiresAt: "2026-11-01T01:00:00Z",
    events,
  };
}

interface WorkletDrainProof {
  sequences: number[];
  frameMeans: number[];
  finalSequence: number;
  pcmFramesAfterAck: number;
}

test("the real worklet crosses a render boundary and emits its trailing marker frame exactly once", async ({
  page,
}) => {
  await page.goto("/");
  const proof = await page.evaluate(async (): Promise<WorkletDrainProof> => {
    const context = new AudioContext({ sampleRate: 48_000 });
    const withTimeout = async <T>(promise: Promise<T>, label: string) => {
      let timer: number | undefined;
      try {
        return await Promise.race([
          promise,
          new Promise<T>((_resolve, reject) => {
            timer = window.setTimeout(
              () => reject(new Error(`Timed out waiting for ${label}.`)),
              2_000,
            );
          }),
        ]);
      } finally {
        if (timer !== undefined) window.clearTimeout(timer);
      }
    };
    await context.audioWorklet.addModule("/progressive-pcm-worklet.js");
    if (context.state === "suspended") await context.resume();
    const source = context.createConstantSource();
    source.offset.value = 0;
    const processor = new AudioWorkletNode(context, "oryntela-pcm-tap", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      channelCount: 1,
      channelCountMode: "explicit",
    });
    const silentOutput = context.createGain();
    silentOutput.gain.value = 0;
    source
      .connect(processor)
      .connect(silentOutput)
      .connect(context.destination);

    const sequences: number[] = [];
    const frameMeans: number[] = [];
    let pcmFramesAfterAck = 0;
    let acknowledged = false;
    let resolveInitialFrame: () => void = () => undefined;
    let resolveMarkerFrame: () => void = () => undefined;
    let resolveAck: (finalSequence: number) => void = () => undefined;
    const initialFrame = new Promise<void>((resolve) => {
      resolveInitialFrame = resolve;
    });
    const markerFrame = new Promise<void>((resolve) => {
      resolveMarkerFrame = resolve;
    });
    const ack = new Promise<number>((resolve) => {
      resolveAck = resolve;
    });
    const token = `browser-drain-${crypto.randomUUID()}`;
    processor.port.onmessage = (event: MessageEvent<unknown>) => {
      const message = event.data as {
        type?: unknown;
        sequence?: unknown;
        samples?: unknown;
        token?: unknown;
        finalSequence?: unknown;
      } | null;
      if (
        message?.type === "pcm" &&
        typeof message.sequence === "number" &&
        message.samples instanceof Float32Array
      ) {
        if (acknowledged) pcmFramesAfterAck += 1;
        const mean =
          message.samples.reduce((sum, sample) => sum + sample, 0) /
          message.samples.length;
        sequences.push(message.sequence);
        frameMeans.push(mean);
        resolveInitialFrame();
        if (mean > 0.7) resolveMarkerFrame();
        return;
      }
      if (
        message?.type === "drain_ack" &&
        message.token === token &&
        typeof message.finalSequence === "number"
      ) {
        acknowledged = true;
        resolveAck(message.finalSequence);
      }
    };

    source.start();
    await withTimeout(initialFrame, "the initial PCM frame");
    source.offset.setValueAtTime(0.8125, context.currentTime);
    await withTimeout(markerFrame, "the synthetic marker frame");
    processor.port.postMessage({ type: "drain", token });
    const finalSequence = await withTimeout(ack, "the render-boundary ack");
    await new Promise((resolve) => window.setTimeout(resolve, 50));

    source.stop();
    source.disconnect();
    processor.disconnect();
    silentOutput.disconnect();
    await context.close();
    return { sequences, frameMeans, finalSequence, pcmFramesAfterAck };
  });

  expect(proof.sequences).toEqual(
    Array.from({ length: proof.finalSequence + 1 }, (_, index) => index),
  );
  expect(proof.frameMeans.at(-1)).toBeCloseTo(0.8125, 4);
  expect(proof.pcmFramesAfterAck).toBe(0);
});

test("a prepared real MediaStream capture arms without losing its first batch interval", async ({
  page,
}) => {
  const submitted: SubmittedAudio[] = [];
  let starts = 0;
  let finishes = 0;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = {
      "access-control-allow-origin": "*",
      "access-control-allow-headers": "content-type,x-request-id",
      "access-control-allow-methods": "POST,OPTIONS",
      "content-type": "application/json",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers, body: "" });
      return;
    }
    if (url.pathname.endsWith("/progressive-transcription/sessions")) {
      starts += 1;
      const body = request.postDataJSON() as {
        externalProcessingAcknowledged?: boolean;
      };
      expect(body.externalProcessingAcknowledged).toBe(true);
      await new Promise((resolve) => setTimeout(resolve, 750));
      await route.fulfill({
        status: 200,
        headers,
        body: JSON.stringify(response("capturing", [])),
      });
      return;
    }
    if (url.pathname.endsWith("/audio")) {
      submitted.push(request.postDataJSON() as SubmittedAudio);
      await route.fulfill({
        status: 200,
        headers,
        body: JSON.stringify(
          response("capturing", [event(1, "partial", "Synthetic")]),
        ),
      });
      return;
    }
    if (url.pathname.endsWith("/poll")) {
      await route.fulfill({
        status: 200,
        headers,
        body: JSON.stringify(response("capturing", [])),
      });
      return;
    }
    if (url.pathname.endsWith("/finish")) {
      finishes += 1;
      await route.fulfill({
        status: 200,
        headers,
        body: JSON.stringify(
          response("finished", [
            event(1, "partial", "Synthetic"),
            event(2, "final", "Synthetic audio."),
          ]),
        ),
      });
      return;
    }
    if (url.pathname.endsWith("/cancel")) {
      await route.fulfill({
        status: 200,
        headers,
        body: JSON.stringify(response("capturing", [])),
      });
      return;
    }
    await route.abort();
  });

  await page.goto("/progressive-pcm-browser-proof");
  await page.getByRole("button", { name: "Capture synthetic audio" }).click();
  const output = page.getByLabel("Capture result");
  await expect(output).toContainText('"lifecycle":"finished"');
  await expect(output).toContainText("fixture-event-1");
  await expect(output).toContainText("fixture-event-2");
  const browserProof = JSON.parse(
    (await output.textContent()) ?? "{}",
  ) as BrowserCaptureProof;
  expect(browserProof.batchBytes).toBeGreaterThan(0);
  expect(browserProof.batchDurationSeconds).toBeGreaterThan(0.92);
  expect(browserProof.batchDurationSeconds).toBeLessThan(1.15);
  expect(browserProof.batchMarkerRatio).toBeGreaterThan(4);

  expect(starts).toBe(1);
  expect(finishes).toBe(1);
  expect(submitted.length).toBeGreaterThanOrEqual(1);
  const ordered = submitted.toSorted(
    (left, right) => left.sequenceNumber - right.sequenceNumber,
  );
  const pcmSegments: Buffer[] = [];
  let expectedStartMs = 0;
  for (const segment of ordered) {
    expect(segment.mimeType).toBe(pcmMimeType);
    expect(segment.externalProcessingAcknowledged).toBe(true);
    expect(segment.startMs).toBe(expectedStartMs);
    const pcm = Buffer.from(segment.audioBase64, "base64");
    pcmSegments.push(pcm);
    expect(pcm.length % 2).toBe(0);
    const sampleCount = pcm.length / 2;
    const encodedDurationMs = (sampleCount * 1_000) / 24_000;
    expect(segment.endMs - segment.startMs).toBeCloseTo(encodedDurationMs, 0);
    expectedStartMs = segment.endMs;
  }
  const pcm = Buffer.concat(pcmSegments);
  const totalSamples = pcm.length / 2;
  expect(totalSamples / 24_000).toBeGreaterThan(0.94);
  expect(totalSamples / 24_000).toBeLessThan(1.12);

  const windowRms = (startSeconds: number, endSeconds: number) => {
    const start = Math.floor(startSeconds * 24_000);
    const end = Math.min(totalSamples, Math.floor(endSeconds * 24_000));
    let energy = 0;
    for (let index = start; index < end; index += 1) {
      const sample = pcm.readInt16LE(index * 2);
      energy += sample * sample;
    }
    return Math.sqrt(energy / Math.max(1, end - start));
  };
  const openingMarkerRms = windowRms(0, 0.15);
  const tailRms = windowRms(0.55, 0.85);
  expect(openingMarkerRms).toBeGreaterThan(8_000);
  expect(tailRms).toBeLessThan(2_000);
  expect(openingMarkerRms / Math.max(tailRms, 1)).toBeGreaterThan(4);
});
