export type BrowserAudioCaptureMode =
  "microphone_only" | "shared_audio_microphone";

export type BrowserAudioSource = "microphone" | "shared_audio";
export type BrowserAudioSourceState = "inactive" | "active" | "muted" | "ended";

export type BrowserAudioInterruptionReason =
  | "microphone_ended"
  | "shared_audio_ended"
  | "display_share_ended"
  | "device_changed";

export type BrowserAudioCaptureErrorCode =
  | "microphone_unsupported"
  | "shared_audio_unsupported"
  | "audio_mixing_unsupported"
  | "display_permission_denied"
  | "display_capture_cancelled"
  | "display_capture_unavailable"
  | "shared_audio_missing"
  | "microphone_permission_denied"
  | "microphone_unavailable"
  | "microphone_missing"
  | "audio_output_missing";

export type BrowserAudioCaptureEvent =
  | {
      type: "source_state";
      source: BrowserAudioSource;
      state: BrowserAudioSourceState;
    }
  | {
      type: "interruption";
      reason: BrowserAudioInterruptionReason;
    };

export interface BrowserAudioCaptureSupport {
  microphoneOnly: boolean;
  sharedAudioMicrophone: boolean;
}

export interface BrowserAudioCaptureSession {
  mode: BrowserAudioCaptureMode;
  recorderStream: MediaStream;
  microphoneState: BrowserAudioSourceState;
  sharedAudioState: BrowserAudioSourceState;
  displaySurface: string | null;
  microphoneDeduplicated: boolean;
  subscribe(listener: (event: BrowserAudioCaptureEvent) => void): () => void;
  cleanup(): Promise<void>;
}

export interface BrowserAudioCaptureEnvironment {
  mediaDevices: MediaDevices;
  createMediaStream(tracks: MediaStreamTrack[]): MediaStream;
  createAudioContext(): AudioContext;
}

type ExtendedAudioConstraints = MediaTrackConstraints & {
  suppressLocalAudioPlayback?: boolean;
};

type ExtendedDisplayMediaStreamOptions = Omit<
  DisplayMediaStreamOptions,
  "audio"
> & {
  audio?: boolean | ExtendedAudioConstraints;
  monitorTypeSurfaces?: "include" | "exclude";
  selfBrowserSurface?: "include" | "exclude";
  surfaceSwitching?: "include" | "exclude";
  systemAudio?: "include" | "exclude";
};

export class BrowserAudioCaptureError extends Error {
  constructor(
    readonly code: BrowserAudioCaptureErrorCode,
    message: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "BrowserAudioCaptureError";
  }
}

function defaultEnvironment(): BrowserAudioCaptureEnvironment {
  return {
    mediaDevices: navigator.mediaDevices,
    createMediaStream: (tracks) => new MediaStream(tracks),
    createAudioContext: () => new AudioContext(),
  };
}

export function browserAudioCaptureSupport(): BrowserAudioCaptureSupport {
  const mediaDevices =
    typeof navigator === "undefined" ? undefined : navigator.mediaDevices;
  const microphoneOnly =
    typeof mediaDevices?.getUserMedia === "function" &&
    typeof MediaStream !== "undefined";
  return {
    microphoneOnly,
    sharedAudioMicrophone:
      microphoneOnly &&
      typeof mediaDevices?.getDisplayMedia === "function" &&
      typeof AudioContext !== "undefined",
  };
}

function isPermissionDenied(reason: unknown): boolean {
  return (
    typeof DOMException !== "undefined" &&
    reason instanceof DOMException &&
    ["NotAllowedError", "SecurityError"].includes(reason.name)
  );
}

function isDisplayCancelled(reason: unknown): boolean {
  return (
    typeof DOMException !== "undefined" &&
    reason instanceof DOMException &&
    reason.name === "AbortError"
  );
}

function isLive(track: MediaStreamTrack): boolean {
  return track.readyState !== "ended";
}

function sourceState(track: MediaStreamTrack): BrowserAudioSourceState {
  if (!isLive(track)) return "ended";
  return track.muted ? "muted" : "active";
}

function sameAudioSource(
  left: MediaStreamTrack,
  right: MediaStreamTrack,
): boolean {
  if (left === right || left.id === right.id) return true;
  const leftDevice = left.getSettings?.().deviceId;
  const rightDevice = right.getSettings?.().deviceId;
  return Boolean(leftDevice && rightDevice && leftDevice === rightDevice);
}

function stopTracks(streams: Array<MediaStream | null>): void {
  const tracks = new Set<MediaStreamTrack>();
  streams.forEach((stream) =>
    stream?.getTracks().forEach((track) => tracks.add(track)),
  );
  tracks.forEach((track) => track.stop());
}

function displayOptions(): ExtendedDisplayMediaStreamOptions {
  return {
    video: { displaySurface: "browser" },
    audio: { suppressLocalAudioPlayback: false },
    monitorTypeSurfaces: "include",
    selfBrowserSurface: "exclude",
    surfaceSwitching: "exclude",
    systemAudio: "include",
  };
}

function microphoneOptions(): MediaStreamConstraints {
  return {
    audio: {
      autoGainControl: true,
      echoCancellation: true,
      noiseSuppression: true,
    },
    video: false,
  };
}

async function acquireMicrophone(
  environment: BrowserAudioCaptureEnvironment,
): Promise<MediaStream> {
  if (typeof environment.mediaDevices?.getUserMedia !== "function") {
    throw new BrowserAudioCaptureError(
      "microphone_unsupported",
      "This browser does not expose microphone capture.",
    );
  }
  try {
    return await environment.mediaDevices.getUserMedia(microphoneOptions());
  } catch (reason: unknown) {
    throw new BrowserAudioCaptureError(
      isPermissionDenied(reason)
        ? "microphone_permission_denied"
        : "microphone_unavailable",
      isPermissionDenied(reason)
        ? "Microphone access was denied."
        : "The microphone could not be started.",
      { cause: reason },
    );
  }
}

async function acquireDisplay(
  environment: BrowserAudioCaptureEnvironment,
): Promise<MediaStream> {
  if (typeof environment.mediaDevices?.getDisplayMedia !== "function") {
    throw new BrowserAudioCaptureError(
      "shared_audio_unsupported",
      "This browser does not expose shared display audio capture.",
    );
  }
  try {
    return await environment.mediaDevices.getDisplayMedia(displayOptions());
  } catch (reason: unknown) {
    const code: BrowserAudioCaptureErrorCode = isPermissionDenied(reason)
      ? "display_permission_denied"
      : isDisplayCancelled(reason)
        ? "display_capture_cancelled"
        : "display_capture_unavailable";
    throw new BrowserAudioCaptureError(
      code,
      code === "display_permission_denied"
        ? "Display sharing permission was denied."
        : code === "display_capture_cancelled"
          ? "Display sharing was cancelled."
          : "Shared display audio could not be started.",
      { cause: reason },
    );
  }
}

export async function acquireBrowserAudioCapture(
  mode: BrowserAudioCaptureMode,
  environment: BrowserAudioCaptureEnvironment = defaultEnvironment(),
): Promise<BrowserAudioCaptureSession> {
  let microphoneStream: MediaStream | null = null;
  let displayStream: MediaStream | null = null;
  let recorderStream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  const audioNodes: AudioNode[] = [];
  const listeners = new Set<(event: BrowserAudioCaptureEvent) => void>();
  const removers: Array<() => void> = [];
  let cleaned = false;
  let interrupted = false;

  const emit = (event: BrowserAudioCaptureEvent) => {
    listeners.forEach((listener) => listener(event));
  };
  const interrupt = (reason: BrowserAudioInterruptionReason) => {
    if (cleaned || interrupted) return;
    interrupted = true;
    emit({ type: "interruption", reason });
  };
  const observeTrack = (
    track: MediaStreamTrack,
    source: BrowserAudioSource,
    endedReason: BrowserAudioInterruptionReason,
  ) => {
    const muted = () => emit({ type: "source_state", source, state: "muted" });
    const unmuted = () =>
      emit({ type: "source_state", source, state: "active" });
    const ended = () => {
      emit({ type: "source_state", source, state: "ended" });
      interrupt(endedReason);
    };
    track.addEventListener("mute", muted);
    track.addEventListener("unmute", unmuted);
    track.addEventListener("ended", ended);
    removers.push(() => {
      track.removeEventListener("mute", muted);
      track.removeEventListener("unmute", unmuted);
      track.removeEventListener("ended", ended);
    });
  };

  const cleanup = async () => {
    if (cleaned) return;
    cleaned = true;
    removers.splice(0).forEach((remove) => remove());
    listeners.clear();
    audioNodes.splice(0).forEach((node) => {
      try {
        node.disconnect();
      } catch {
        // The node may already have been disconnected by the browser.
      }
    });
    stopTracks([recorderStream, microphoneStream, displayStream]);
    if (audioContext && audioContext.state !== "closed") {
      await audioContext.close().catch(() => undefined);
    }
  };

  try {
    if (mode === "shared_audio_microphone") {
      displayStream = await acquireDisplay(environment);
      const [sharedTrack, ...extraSharedTracks] =
        displayStream.getAudioTracks();
      extraSharedTracks.forEach((track) => track.stop());
      if (!sharedTrack || !isLive(sharedTrack)) {
        throw new BrowserAudioCaptureError(
          "shared_audio_missing",
          "The selected display did not provide a shared audio track.",
        );
      }
      microphoneStream = await acquireMicrophone(environment);
      const [microphoneTrack, ...extraMicrophoneTracks] =
        microphoneStream.getAudioTracks();
      extraMicrophoneTracks.forEach((track) => track.stop());
      if (!microphoneTrack || !isLive(microphoneTrack)) {
        throw new BrowserAudioCaptureError(
          "microphone_missing",
          "The browser did not provide a live microphone audio track.",
        );
      }
      if (!isLive(sharedTrack)) {
        throw new BrowserAudioCaptureError(
          "shared_audio_missing",
          "The shared audio track ended before recording could start.",
        );
      }

      audioContext = environment.createAudioContext();
      if (audioContext.state === "suspended") await audioContext.resume();
      if (audioContext.state !== "running") {
        throw new BrowserAudioCaptureError(
          "audio_mixing_unsupported",
          "The browser could not activate audio mixing.",
        );
      }
      const destination = audioContext.createMediaStreamDestination();
      const sharedSource = audioContext.createMediaStreamSource(
        environment.createMediaStream([sharedTrack]),
      );
      sharedSource.connect(destination);
      audioNodes.push(sharedSource, destination);
      const microphoneDeduplicated = sameAudioSource(
        sharedTrack,
        microphoneTrack,
      );
      if (!microphoneDeduplicated) {
        const microphoneSource = audioContext.createMediaStreamSource(
          environment.createMediaStream([microphoneTrack]),
        );
        microphoneSource.connect(destination);
        audioNodes.push(microphoneSource);
      }
      recorderStream = destination.stream;
      const [outputTrack] = recorderStream.getAudioTracks();
      if (
        !outputTrack ||
        !isLive(outputTrack) ||
        recorderStream.getAudioTracks().length !== 1 ||
        recorderStream.getVideoTracks().length !== 0
      ) {
        throw new BrowserAudioCaptureError(
          "audio_output_missing",
          "The browser did not create one audio-only recording track.",
        );
      }

      observeTrack(sharedTrack, "shared_audio", "shared_audio_ended");
      observeTrack(microphoneTrack, "microphone", "microphone_ended");
      displayStream.getVideoTracks().forEach((videoTrack) => {
        const ended = () => interrupt("display_share_ended");
        videoTrack.addEventListener("ended", ended);
        removers.push(() => videoTrack.removeEventListener("ended", ended));
      });
      const deviceChanged = () => interrupt("device_changed");
      environment.mediaDevices.addEventListener?.(
        "devicechange",
        deviceChanged,
      );
      removers.push(() =>
        environment.mediaDevices.removeEventListener?.(
          "devicechange",
          deviceChanged,
        ),
      );
      const displaySurface = displayStream
        .getVideoTracks()[0]
        ?.getSettings?.().displaySurface;
      return {
        mode,
        recorderStream,
        microphoneState: sourceState(microphoneTrack),
        sharedAudioState: sourceState(sharedTrack),
        displaySurface:
          typeof displaySurface === "string" ? displaySurface : null,
        microphoneDeduplicated,
        subscribe(listener) {
          listeners.add(listener);
          return () => listeners.delete(listener);
        },
        cleanup,
      };
    }

    microphoneStream = await acquireMicrophone(environment);
    const [microphoneTrack, ...extraMicrophoneTracks] =
      microphoneStream.getAudioTracks();
    extraMicrophoneTracks.forEach((track) => track.stop());
    if (!microphoneTrack || !isLive(microphoneTrack)) {
      throw new BrowserAudioCaptureError(
        "microphone_missing",
        "The browser did not provide a live microphone audio track.",
      );
    }
    if (microphoneStream.getVideoTracks().length > 0) {
      microphoneStream.getVideoTracks().forEach((track) => track.stop());
      recorderStream = environment.createMediaStream([microphoneTrack]);
    } else {
      recorderStream = microphoneStream;
    }
    const [outputTrack] = recorderStream.getAudioTracks();
    if (
      !outputTrack ||
      !isLive(outputTrack) ||
      recorderStream.getAudioTracks().length !== 1 ||
      recorderStream.getVideoTracks().length !== 0
    ) {
      throw new BrowserAudioCaptureError(
        "audio_output_missing",
        "The browser did not create one audio-only recording track.",
      );
    }
    observeTrack(microphoneTrack, "microphone", "microphone_ended");
    const deviceChanged = () => interrupt("device_changed");
    environment.mediaDevices.addEventListener?.("devicechange", deviceChanged);
    removers.push(() =>
      environment.mediaDevices.removeEventListener?.(
        "devicechange",
        deviceChanged,
      ),
    );
    return {
      mode,
      recorderStream,
      microphoneState: sourceState(microphoneTrack),
      sharedAudioState: "inactive",
      displaySurface: null,
      microphoneDeduplicated: false,
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      cleanup,
    };
  } catch (reason: unknown) {
    await cleanup();
    if (reason instanceof BrowserAudioCaptureError) throw reason;
    throw new BrowserAudioCaptureError(
      "audio_mixing_unsupported",
      "The browser could not prepare the requested audio capture.",
      { cause: reason },
    );
  }
}
