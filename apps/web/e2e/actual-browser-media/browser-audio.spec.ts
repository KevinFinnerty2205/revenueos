import { expect, test } from "@playwright/test";

interface CaptureResult {
  error: string | null;
  displayAudioTracks: number;
  displayVideoTracks: number;
  microphoneAudioTracks: number;
  mixedAudioTracks: number;
  mixedVideoTracks: number;
  sharedAudioRms: number;
  microphoneRms: number;
  mixedAudioRms: number;
  recordedBytes: number;
}

test("Chrome captures a synthetic shared tab audio track and mixes one microphone track", async ({
  context,
  page,
}) => {
  const source = await context.newPage();
  await source.goto("/");
  await source.setContent(`
    <!doctype html>
    <html lang="en">
      <head><title>Synthetic shared audio source</title></head>
      <body>
        <button id="start" type="button">Start synthetic tone</button>
        <script>
          document.querySelector('#start').addEventListener('click', async () => {
            const context = new AudioContext();
            await context.resume();
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            oscillator.frequency.value = 440;
            gain.gain.value = 0.025;
            oscillator.connect(gain).connect(context.destination);
            oscillator.start();
            window.syntheticAudio = { context, oscillator };
          });
        </script>
      </body>
    </html>
  `);
  await source.getByRole("button", { name: "Start synthetic tone" }).click();

  await page.goto("/");
  await page.setContent(`
    <!doctype html>
    <html lang="en">
      <head><title>Oryntela browser audio verifier</title></head>
      <body><button id="capture" type="button">Capture shared tab</button></body>
    </html>
  `);
  await page.evaluate(() => {
    const sampleRms = async (track: MediaStreamTrack): Promise<number> => {
      const context = new AudioContext();
      const sourceNode = context.createMediaStreamSource(
        new MediaStream([track]),
      );
      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      sourceNode.connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      let peak = 0;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(
          samples.reduce((sum, value) => sum + value * value, 0) /
            samples.length,
        );
        peak = Math.max(peak, rms);
        await new Promise((resolve) => window.setTimeout(resolve, 50));
      }
      sourceNode.disconnect();
      await context.close();
      return peak;
    };

    const result = new Promise<CaptureResult>((resolve) => {
      document.querySelector("#capture")?.addEventListener(
        "click",
        async () => {
          let display: MediaStream | null = null;
          let microphone: MediaStream | null = null;
          let mixer: AudioContext | null = null;
          try {
            display = await navigator.mediaDevices.getDisplayMedia({
              video: { displaySurface: "browser" },
              audio: true,
            });
            microphone = await navigator.mediaDevices.getUserMedia({
              audio: {
                echoCancellation: true,
                noiseSuppression: true,
              },
              video: false,
            });
            const [sharedTrack] = display.getAudioTracks();
            const [microphoneTrack] = microphone.getAudioTracks();
            if (!sharedTrack || !microphoneTrack) {
              throw new Error(
                "Browser did not expose both requested audio tracks.",
              );
            }

            mixer = new AudioContext();
            const destination = mixer.createMediaStreamDestination();
            mixer
              .createMediaStreamSource(new MediaStream([sharedTrack]))
              .connect(destination);
            mixer
              .createMediaStreamSource(new MediaStream([microphoneTrack]))
              .connect(destination);
            const [mixedTrack] = destination.stream.getAudioTracks();
            if (!mixedTrack)
              throw new Error("Mixer did not expose an audio track.");

            const recorder = new MediaRecorder(destination.stream);
            const chunks: Blob[] = [];
            recorder.addEventListener("dataavailable", (event) => {
              if (event.data.size > 0) chunks.push(event.data);
            });
            const stopped = new Promise<void>((stoppedResolve) =>
              recorder.addEventListener("stop", () => stoppedResolve(), {
                once: true,
              }),
            );
            recorder.start(100);
            const [sharedAudioRms, microphoneRms, mixedAudioRms] =
              await Promise.all([
                sampleRms(sharedTrack),
                sampleRms(microphoneTrack),
                sampleRms(mixedTrack),
              ]);
            recorder.stop();
            await stopped;
            resolve({
              error: null,
              displayAudioTracks: display.getAudioTracks().length,
              displayVideoTracks: display.getVideoTracks().length,
              microphoneAudioTracks: microphone.getAudioTracks().length,
              mixedAudioTracks: destination.stream.getAudioTracks().length,
              mixedVideoTracks: destination.stream.getVideoTracks().length,
              sharedAudioRms,
              microphoneRms,
              mixedAudioRms,
              recordedBytes: chunks.reduce(
                (total, chunk) => total + chunk.size,
                0,
              ),
            });
          } catch (reason: unknown) {
            resolve({
              error:
                reason instanceof Error
                  ? `${reason.name}: ${reason.message}`
                  : String(reason),
              displayAudioTracks: display?.getAudioTracks().length ?? 0,
              displayVideoTracks: display?.getVideoTracks().length ?? 0,
              microphoneAudioTracks: microphone?.getAudioTracks().length ?? 0,
              mixedAudioTracks: 0,
              mixedVideoTracks: 0,
              sharedAudioRms: 0,
              microphoneRms: 0,
              mixedAudioRms: 0,
              recordedBytes: 0,
            });
          } finally {
            display?.getTracks().forEach((track) => track.stop());
            microphone?.getTracks().forEach((track) => track.stop());
            if (mixer && mixer.state !== "closed") await mixer.close();
          }
        },
        { once: true },
      );
    });
    Object.assign(globalThis, { browserAudioCaptureResult: result });
  });

  await page.getByRole("button", { name: "Capture shared tab" }).click();
  const result = await page.evaluate(
    () =>
      (
        globalThis as typeof globalThis & {
          browserAudioCaptureResult: Promise<CaptureResult>;
        }
      ).browserAudioCaptureResult,
  );

  expect(result.error).toBeNull();
  expect(result.displayAudioTracks).toBe(1);
  expect(result.displayVideoTracks).toBeGreaterThanOrEqual(1);
  expect(result.microphoneAudioTracks).toBe(1);
  expect(result.mixedAudioTracks).toBe(1);
  expect(result.mixedVideoTracks).toBe(0);
  expect(result.sharedAudioRms).toBeGreaterThan(0.001);
  expect(result.microphoneRms).toBeGreaterThan(0.001);
  expect(result.mixedAudioRms).toBeGreaterThan(0.001);
  expect(result.recordedBytes).toBeGreaterThan(0);

  await source.evaluate(async () => {
    const fixture = (
      globalThis as typeof globalThis & {
        syntheticAudio?: {
          context: AudioContext;
          oscillator: OscillatorNode;
        };
      }
    ).syntheticAudio;
    fixture?.oscillator.stop();
    await fixture?.context.close();
  });
});
