"use client";

import { useState } from "react";
import {
  type ProgressiveTranscriptEvent,
  startProgressiveTranscriptionCapture,
} from "@/lib/progressive-transcription-capture";

interface BrowserProofResult {
  lifecycle: string;
  eventIds: string[];
  batchBytes: number;
  batchDurationSeconds: number;
  batchMarkerRatio: number;
}

function rms(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  return Math.sqrt(
    samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length,
  );
}

export function ProgressivePcmBrowserProof() {
  const [result, setResult] = useState<BrowserProofResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const run = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    const sourceContext = new AudioContext({ sampleRate: 48_000 });
    let oscillator: OscillatorNode | null = null;
    let oscillatorStarted = false;
    let progressiveCapture: Awaited<
      ReturnType<typeof startProgressiveTranscriptionCapture>
    > | null = null;
    let recorder: MediaRecorder | null = null;
    try {
      await sourceContext.resume();
      const destination = sourceContext.createMediaStreamDestination();
      oscillator = sourceContext.createOscillator();
      const gain = sourceContext.createGain();
      oscillator.frequency.value = 440;
      gain.gain.value = 0;
      oscillator.connect(gain).connect(destination);
      const events: ProgressiveTranscriptEvent[] = [];
      oscillator.start();
      oscillatorStarted = true;
      progressiveCapture = await startProgressiveTranscriptionCapture({
        interactionId: "00000000-0000-4000-8000-000000000111",
        recordingSessionId: "00000000-0000-4000-8000-000000000222",
        stream: destination.stream,
        externalProcessingAcknowledged: true,
        initiallyPaused: true,
        onEvents: (fresh) => events.push(...fresh),
      });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const batchChunks: Blob[] = [];
      recorder = new MediaRecorder(destination.stream, { mimeType });
      recorder.ondataavailable = ({ data }) => {
        if (data.size) batchChunks.push(data);
      };
      const batchStopped = new Promise<void>((resolve, reject) => {
        recorder!.onstop = () => resolve();
        recorder!.onerror = () =>
          reject(new Error("The synthetic batch recorder failed."));
      });

      // This is the production arming order: reveal a distinctive opening
      // marker, accept worklet PCM, then start MediaRecorder in one task.
      const armedAt = sourceContext.currentTime;
      gain.gain.setValueAtTime(0.65, armedAt);
      gain.gain.setValueAtTime(0.04, armedAt + 0.2);
      progressiveCapture.resume();
      recorder.start();
      await new Promise((resolve) => window.setTimeout(resolve, 1_000));
      oscillator.stop();
      oscillator = null;
      recorder.stop();
      await batchStopped;
      const finished = await progressiveCapture.finish();
      progressiveCapture = null;

      const batchBlob = new Blob(batchChunks, { type: recorder.mimeType });
      const decoded = await sourceContext.decodeAudioData(
        await batchBlob.arrayBuffer(),
      );
      const samples = decoded.getChannelData(0);
      const firstEnd = Math.min(samples.length, decoded.sampleRate * 0.15);
      const tailStart = Math.min(samples.length, decoded.sampleRate * 0.55);
      const tailEnd = Math.min(samples.length, decoded.sampleRate * 0.85);
      const firstRms = rms(samples.slice(0, firstEnd));
      const tailRms = rms(samples.slice(tailStart, tailEnd));
      setResult({
        lifecycle: finished.lifecycle,
        eventIds: events.map((event) => event.eventId),
        batchBytes: batchBlob.size,
        batchDurationSeconds: decoded.duration,
        batchMarkerRatio: firstRms / Math.max(tailRms, 0.000_001),
      });
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (progressiveCapture) {
        await progressiveCapture.cancel("capture_ended").catch(() => undefined);
      }
      if (recorder?.state !== "inactive") recorder?.stop();
      if (oscillator && oscillatorStarted) oscillator.stop();
      await sourceContext.close().catch(() => undefined);
      setRunning(false);
    }
  };

  return (
    <main>
      <h1>Progressive PCM browser proof</h1>
      <button type="button" disabled={running} onClick={() => void run()}>
        {running ? "Capturing synthetic audio…" : "Capture synthetic audio"}
      </button>
      {result ? (
        <output aria-label="Capture result">{JSON.stringify(result)}</output>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
