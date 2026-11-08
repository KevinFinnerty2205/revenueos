import { afterEach, describe, expect, it, vi } from "vitest";
import {
  acquireBrowserAudioCapture,
  type BrowserAudioCaptureEnvironment,
  type BrowserAudioCaptureEvent,
} from "@/lib/browser-audio-capture";

class FakeTrack extends EventTarget {
  readonly stop = vi.fn(() => {
    this.readyState = "ended";
  });
  muted = false;
  readyState: MediaStreamTrackState = "live";

  constructor(
    readonly kind: "audio" | "video",
    readonly id: string,
    private readonly settings: MediaTrackSettings = {},
  ) {
    super();
  }

  getSettings(): MediaTrackSettings {
    return this.settings;
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.dispatchEvent(new Event(muted ? "mute" : "unmute"));
  }

  end(): void {
    this.readyState = "ended";
    this.dispatchEvent(new Event("ended"));
  }
}

class FakeStream {
  constructor(private readonly tracks: FakeTrack[]) {}

  getTracks(): MediaStreamTrack[] {
    return [...this.tracks] as unknown as MediaStreamTrack[];
  }

  getAudioTracks(): MediaStreamTrack[] {
    return this.tracks.filter(
      (track) => track.kind === "audio",
    ) as unknown as MediaStreamTrack[];
  }

  getVideoTracks(): MediaStreamTrack[] {
    return this.tracks.filter(
      (track) => track.kind === "video",
    ) as unknown as MediaStreamTrack[];
  }
}

function stream(...tracks: FakeTrack[]): MediaStream {
  return new FakeStream(tracks) as unknown as MediaStream;
}

function environment({
  microphoneStream,
  displayStream,
  outputStream = stream(new FakeTrack("audio", "mixed-output")),
}: {
  microphoneStream: MediaStream;
  displayStream?: MediaStream;
  outputStream?: MediaStream;
}) {
  const mediaDevices = Object.assign(new EventTarget(), {
    getUserMedia: vi.fn(() => Promise.resolve(microphoneStream)),
    getDisplayMedia: vi.fn(() =>
      displayStream
        ? Promise.resolve(displayStream)
        : Promise.reject(new Error("Display stream not configured")),
    ),
  }) as unknown as MediaDevices;
  const sources: Array<{
    stream: MediaStream;
    connect: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
  }> = [];
  const destination = {
    stream: outputStream,
    disconnect: vi.fn(),
  };
  const audioContext = {
    state: "running",
    createMediaStreamDestination: vi.fn(() => destination),
    createMediaStreamSource: vi.fn((sourceStream: MediaStream) => {
      const source = {
        stream: sourceStream,
        connect: vi.fn(),
        disconnect: vi.fn(),
      };
      sources.push(source);
      return source;
    }),
    resume: vi.fn(() => Promise.resolve()),
    close: vi.fn(() => Promise.resolve()),
  };
  const captureEnvironment: BrowserAudioCaptureEnvironment = {
    mediaDevices,
    createMediaStream: (tracks) =>
      new FakeStream(
        tracks as unknown as FakeTrack[],
      ) as unknown as MediaStream,
    createAudioContext: () => audioContext as unknown as AudioContext,
  };
  return {
    audioContext,
    captureEnvironment,
    destination,
    mediaDevices,
    sources,
  };
}

describe("browser audio capture", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("acquires one microphone track, reports source changes, and cleans up once", async () => {
    const microphone = new FakeTrack("audio", "microphone");
    const setup = environment({ microphoneStream: stream(microphone) });

    const capture = await acquireBrowserAudioCapture(
      "microphone_only",
      setup.captureEnvironment,
    );
    const events: BrowserAudioCaptureEvent[] = [];
    capture.subscribe((event) => events.push(event));

    expect(capture.recorderStream.getAudioTracks()).toHaveLength(1);
    expect(capture.recorderStream.getVideoTracks()).toHaveLength(0);
    expect(capture.microphoneState).toBe("active");
    expect(capture.sharedAudioState).toBe("inactive");

    microphone.setMuted(true);
    microphone.end();
    expect(events).toEqual([
      { type: "source_state", source: "microphone", state: "muted" },
      { type: "source_state", source: "microphone", state: "ended" },
      { type: "interruption", reason: "microphone_ended" },
    ]);

    await capture.cleanup();
    await capture.cleanup();
    expect(microphone.stop).toHaveBeenCalledTimes(1);
  });

  it("mixes shared audio and microphone exactly once without recording display video", async () => {
    const shared = new FakeTrack("audio", "shared-audio", {
      deviceId: "shared-device",
    });
    const displayVideo = new FakeTrack("video", "display-video", {
      displaySurface: "browser",
    });
    const microphone = new FakeTrack("audio", "microphone", {
      deviceId: "microphone-device",
    });
    const mixedOutput = new FakeTrack("audio", "mixed-output");
    const setup = environment({
      microphoneStream: stream(microphone),
      displayStream: stream(shared, displayVideo),
      outputStream: stream(mixedOutput),
    });

    const capture = await acquireBrowserAudioCapture(
      "shared_audio_microphone",
      setup.captureEnvironment,
    );
    const events: BrowserAudioCaptureEvent[] = [];
    capture.subscribe((event) => events.push(event));

    expect(setup.sources).toHaveLength(2);
    expect(setup.sources[0]?.connect).toHaveBeenCalledTimes(1);
    expect(setup.sources[1]?.connect).toHaveBeenCalledTimes(1);
    expect(capture.recorderStream.getAudioTracks()).toEqual([
      mixedOutput as unknown as MediaStreamTrack,
    ]);
    expect(capture.recorderStream.getVideoTracks()).toEqual([]);
    expect(capture.displaySurface).toBe("browser");
    expect(capture.microphoneDeduplicated).toBe(false);

    setup.mediaDevices.dispatchEvent(new Event("devicechange"));
    expect(events).toContainEqual({
      type: "interruption",
      reason: "device_changed",
    });

    await capture.cleanup();
    expect(shared.stop).toHaveBeenCalledTimes(1);
    expect(displayVideo.stop).toHaveBeenCalledTimes(1);
    expect(microphone.stop).toHaveBeenCalledTimes(1);
    expect(mixedOutput.stop).toHaveBeenCalledTimes(1);
    expect(setup.audioContext.close).toHaveBeenCalledTimes(1);
  });

  it("rejects a display share with no audio and stops its video track", async () => {
    const displayVideo = new FakeTrack("video", "display-video");
    const microphone = new FakeTrack("audio", "microphone");
    const setup = environment({
      microphoneStream: stream(microphone),
      displayStream: stream(displayVideo),
    });

    await expect(
      acquireBrowserAudioCapture(
        "shared_audio_microphone",
        setup.captureEnvironment,
      ),
    ).rejects.toMatchObject({
      code: "shared_audio_missing",
    });
    expect(setup.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    expect(displayVideo.stop).toHaveBeenCalledTimes(1);
  });

  it("deduplicates microphone input when display and microphone tracks identify the same device", async () => {
    const shared = new FakeTrack("audio", "shared-audio", {
      deviceId: "same-device",
    });
    const microphone = new FakeTrack("audio", "microphone", {
      deviceId: "same-device",
    });
    const setup = environment({
      microphoneStream: stream(microphone),
      displayStream: stream(shared),
    });

    const capture = await acquireBrowserAudioCapture(
      "shared_audio_microphone",
      setup.captureEnvironment,
    );

    expect(capture.microphoneDeduplicated).toBe(true);
    expect(setup.sources).toHaveLength(1);
    await capture.cleanup();
  });

  it("distinguishes unsupported shared capture before requesting a source", async () => {
    const microphone = new FakeTrack("audio", "microphone");
    const setup = environment({ microphoneStream: stream(microphone) });
    Object.defineProperty(setup.mediaDevices, "getDisplayMedia", {
      configurable: true,
      value: undefined,
    });

    await expect(
      acquireBrowserAudioCapture(
        "shared_audio_microphone",
        setup.captureEnvironment,
      ),
    ).rejects.toMatchObject({
      code: "shared_audio_unsupported",
    });
  });
});
