"use client";

import type {
  InteractionLifecycleStatus,
  InteractionType,
  RecordingChunkUpload,
  RecordingMimeType,
  RecordingSession,
  RecordingTranscription,
} from "@revenueos/shared";
import Link from "next/link";
import {
  type MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { apiRequest, apiUpload } from "@/lib/api";
import {
  acquireBrowserAudioCapture,
  BrowserAudioCaptureError,
  browserAudioCaptureSupport,
  type BrowserAudioCaptureMode,
  type BrowserAudioCaptureSession,
  type BrowserAudioCaptureSupport,
  type BrowserAudioInterruptionReason,
  type BrowserAudioSourceState,
} from "@/lib/browser-audio-capture";

const MIME_PREFERENCES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
] as const;
const CHUNK_INTERVAL_MS = 5_000;
const NOTICE_VERSION = 1;
const UPLOAD_RETRY_DELAYS_MS = [0, 300, 1_000] as const;
const CANCELLABLE_RECORDING_STATES = new Set<
  RecordingSession["lifecycleStatus"]
>(["created", "recording", "uploading", "failed"]);

export type RecorderState =
  | "checking"
  | "ready"
  | "requesting_permission"
  | "recording"
  | "paused"
  | "uploading"
  | "processing"
  | "completed"
  | "interrupted"
  | "unsupported"
  | "permission_denied"
  | "failed";

interface PendingChunk {
  blob: Blob;
  sequenceNumber: number;
  checksumSha256: string | null;
  createIdempotencyKey: string;
  completeIdempotencyKey: string;
}

export interface RecordingActivity {
  state: RecorderState;
  active: boolean;
  blocksInteractionCompletion: boolean;
  elapsedSeconds: number;
  recording: RecordingSession | null;
}

export interface ConversationLiveNotesProps {
  inputId: string;
  liveNotes: string;
  onLiveNotesChange: (value: string) => void;
  onSave?: () => void;
  saveDisabled?: boolean;
  status?: string | null;
}

export function ConversationLiveNotes({
  inputId,
  liveNotes,
  onLiveNotesChange,
  onSave,
  saveDisabled = false,
  status = null,
}: ConversationLiveNotesProps) {
  const descriptionId = `${inputId}-description`;
  const statusId = `${inputId}-status`;
  return (
    <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5">
      <label htmlFor={inputId} className="text-base font-bold text-slate-950">
        Private live notes
      </label>
      <p id={descriptionId} className="mt-1 text-sm leading-6 text-slate-600">
        Capture details in your own words while the conversation continues.
        Audio permission or source failures do not clear this field.
      </p>
      <textarea
        id={inputId}
        rows={5}
        className="mt-3 w-full rounded-xl border border-slate-300 px-3 py-3 text-base text-slate-950 shadow-inner focus:border-brand-secondary focus:outline-none focus:ring-2 focus:ring-brand-secondary/30"
        maxLength={20_000}
        value={liveNotes}
        onChange={(event) => onLiveNotesChange(event.target.value)}
        aria-describedby={
          status ? `${descriptionId} ${statusId}` : descriptionId
        }
        placeholder="Decisions, questions, commitments, context…"
      />
      {onSave ? (
        <button
          type="button"
          className="secondary-button mt-3"
          disabled={saveDisabled}
          onClick={onSave}
        >
          Save private notes
        </button>
      ) : null}
      {status ? (
        <p id={statusId} role="status" className="mt-2 text-xs text-slate-500">
          {status}
        </p>
      ) : null}
    </section>
  );
}

export function selectSupportedRecordingMimeType(
  mediaRecorder: Pick<typeof MediaRecorder, "isTypeSupported"> | undefined,
): string | null {
  if (!mediaRecorder) return null;
  return (
    MIME_PREFERENCES.find((mimeType) =>
      mediaRecorder.isTypeSupported(mimeType),
    ) ?? null
  );
}

function normaliseMimeType(mimeType: string): RecordingMimeType {
  return mimeType.startsWith("audio/webm") ? "audio/webm" : "audio/mp4";
}

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function sha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await blob.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function elapsedLabel(seconds: number): string {
  const hours = Math.floor(seconds / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  const remainder = seconds % 60;
  return [hours, minutes, remainder]
    .map((part) => part.toString().padStart(2, "0"))
    .join(":");
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function captureErrorMessage(error: BrowserAudioCaptureError): string {
  switch (error.code) {
    case "shared_audio_unsupported":
    case "audio_mixing_unsupported":
      return "Shared meeting audio is not supported by this browser. Switch to microphone-only capture or use AI Debrief.";
    case "shared_audio_missing":
      return "The selected share did not include audio. Choose the meeting tab and enable the browser's share-audio option, or switch to microphone-only capture.";
    case "display_permission_denied":
      return "Screen or tab sharing permission was denied. Allow sharing to capture meeting audio, or switch to microphone-only capture.";
    case "display_capture_cancelled":
      return "Screen or tab sharing was cancelled. Choose shared meeting audio again, or switch to microphone-only capture.";
    case "display_capture_unavailable":
      return "The browser could not start shared meeting audio. Try selecting the meeting tab again, or switch to microphone-only capture.";
    case "microphone_permission_denied":
      return "Microphone access was denied. You can use AI Debrief or text capture instead.";
    case "microphone_unsupported":
      return "This browser does not expose microphone capture.";
    case "microphone_missing":
    case "microphone_unavailable":
      return "The browser did not provide a working microphone. Check the selected input device and try again.";
    case "audio_output_missing":
      return "The browser could not prepare a verified audio-only recording stream.";
  }
}

function interruptionMessage(reason: BrowserAudioInterruptionReason): string {
  switch (reason) {
    case "microphone_ended":
      return "The microphone stopped. Captured audio is being safely finalised.";
    case "shared_audio_ended":
      return "Shared meeting audio stopped. Captured audio is being safely finalised.";
    case "display_share_ended":
      return "Screen or tab sharing ended. Captured audio is being safely finalised.";
    case "device_changed":
      return "An audio device changed. Captured audio is being safely finalised before you choose sources again.";
  }
}

function displaySurfaceLabel(surface: string | null): string {
  switch (surface) {
    case "browser":
      return "Browser tab";
    case "window":
      return "Application window";
    case "monitor":
      return "Screen";
    default:
      return surface ?? "Not shared";
  }
}

export function RecordingFoundation({
  interactionId,
  interactionType,
  lifecycleStatus,
  showTranscript = true,
  fallbackHref = "#debrief",
  fallbackLabel = "Use AI Debrief instead",
  onActivityChange,
  onElapsedSecondsChange,
  onFinalized,
  liveNotes,
  onLiveNotesChange,
  onSaveLiveNotes,
  liveNotesSaveDisabled,
  liveNotesStatus,
}: {
  interactionId: string;
  interactionType: InteractionType;
  lifecycleStatus: InteractionLifecycleStatus;
  showTranscript?: boolean;
  fallbackHref?: string;
  fallbackLabel?: string;
  onActivityChange?: (activity: RecordingActivity) => void;
  onElapsedSecondsChange?: (seconds: number) => void;
  onFinalized?: (recording: RecordingSession) => void;
  liveNotes?: string;
  onLiveNotesChange?: (value: string) => void;
  onSaveLiveNotes?: () => void;
  liveNotesSaveDisabled?: boolean;
  liveNotesStatus?: string | null;
}) {
  const [state, setState] = useState<RecorderState>("checking");
  const [recording, setRecording] = useState<RecordingSession | null>(null);
  const [transcription, setTranscription] =
    useState<RecordingTranscription | null>(null);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [uploadedChunks, setUploadedChunks] = useState(0);
  const [pendingChunkCount, setPendingChunkCount] = useState(0);
  const [online, setOnline] = useState(
    typeof navigator === "undefined" || navigator.onLine !== false,
  );
  const [microphoneState, setMicrophoneState] =
    useState<BrowserAudioSourceState>("inactive");
  const [sharedAudioState, setSharedAudioState] =
    useState<BrowserAudioSourceState>("inactive");
  const [captureMode, setCaptureMode] = useState<BrowserAudioCaptureMode>(
    interactionType === "online_meeting"
      ? "shared_audio_microphone"
      : "microphone_only",
  );
  const [captureSupport, setCaptureSupport] =
    useState<BrowserAudioCaptureSupport>({
      microphoneOnly: false,
      sharedAudioMicrophone: false,
    });
  const [displaySurface, setDisplaySurface] = useState<string | null>(null);
  const [microphoneDeduplicated, setMicrophoneDeduplicated] = useState(false);
  const [sourceNotice, setSourceNotice] = useState<string | null>(null);
  const [draftLiveNotes, setDraftLiveNotes] = useState("");
  const [wakeLockActive, setWakeLockActive] = useState(false);
  const [pauseSupported, setPauseSupported] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioCaptureRef = useRef<BrowserAudioCaptureSession | null>(null);
  const unsubscribeCaptureRef = useRef<(() => void) | null>(null);
  const recordingRef = useRef<RecordingSession | null>(null);
  const mimeTypeRef = useRef<string | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const pausedAtRef = useRef<number | null>(null);
  const pausedDurationRef = useRef(0);
  const nextSequenceRef = useRef(0);
  const uploadQueueRef = useRef<Promise<void>>(Promise.resolve());
  const pendingChunksRef = useRef<Map<number, PendingChunk>>(new Map());
  const controlQueueRef = useRef<Promise<void>>(Promise.resolve());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const recorderActiveRef = useRef(false);
  const captureInterruptedRef = useRef(false);
  const captureInterruptionMessageRef = useRef<string | null>(null);
  const interruptionHandledRef = useRef(false);
  const mountedRef = useRef(true);
  const locallyStartedSessionRef = useRef(false);
  const teardownCancellationStartedRef = useRef(false);
  const teardownCancellationKeyRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    const recordings = await apiRequest<RecordingSession[]>(
      `/api/v1/interactions/${interactionId}/recordings`,
    );
    if (!mountedRef.current) return;
    const latest = recordings[0] ?? null;
    setRecording(latest);
    recordingRef.current = latest;
    if (!latest) return;
    if (
      ["uploaded", "transcribing", "completed", "failed"].includes(
        latest.lifecycleStatus,
      )
    ) {
      const transcript = await apiRequest<RecordingTranscription>(
        `/api/v1/interactions/${interactionId}/recordings/${latest.id}/transcription`,
      );
      if (!mountedRef.current) return;
      setTranscription(transcript);
      setState(transcript.status === "completed" ? "completed" : "processing");
    } else if (
      ["created", "recording", "uploading"].includes(latest.lifecycleStatus)
    ) {
      setState("interrupted");
      const chunks = await apiRequest<
        Array<{ sequenceNumber: number; uploadState: string }>
      >(`/api/v1/interactions/${interactionId}/recordings/${latest.id}/chunks`);
      if (!mountedRef.current) return;
      const verified = chunks.filter(
        (chunk) => chunk.uploadState === "verified",
      );
      setUploadedChunks(verified.length);
      nextSequenceRef.current =
        verified.length === 0
          ? 0
          : Math.max(...verified.map((chunk) => chunk.sequenceNumber)) + 1;
      setElapsedSeconds(latest.durationSeconds ?? 0);
    }
  }, [interactionId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const support = browserAudioCaptureSupport();
      if (!cancelled) {
        setCaptureSupport(support);
        if (
          interactionType === "online_meeting" &&
          !support.sharedAudioMicrophone &&
          support.microphoneOnly
        ) {
          setCaptureMode("microphone_only");
          setSourceNotice(
            "Shared meeting audio is not supported by this browser. Microphone-only capture remains available.",
          );
        }
      }
      const supported =
        support.microphoneOnly &&
        selectSupportedRecordingMimeType(globalThis.MediaRecorder) !== null;
      if (!supported) {
        if (!cancelled) setState("unsupported");
      } else if (!cancelled) {
        setState("ready");
      }
      try {
        await load();
      } catch (requestError: unknown) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Recordings could not be loaded.",
          );
        }
      }
    });
    return () => {
      cancelled = true;
    };
  }, [interactionType, load]);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    if (
      !recording ||
      !["uploaded", "transcribing"].includes(recording.lifecycleStatus)
    )
      return;
    const poll = setInterval(() => {
      load().catch(() => undefined);
    }, 3_000);
    return () => clearInterval(poll);
  }, [load, recording]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (
        ["recording", "paused", "uploading"].includes(state) ||
        pendingChunkCount > 0
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [pendingChunkCount, state]);

  const releaseWakeLock = useCallback(async (updateState = true) => {
    const sentinel = wakeLockRef.current;
    wakeLockRef.current = null;
    if (updateState && mountedRef.current) setWakeLockActive(false);
    if (sentinel && !sentinel.released) {
      await sentinel.release().catch(() => undefined);
    }
  }, []);

  const releaseAudioCapture = useCallback(async (updateState = true) => {
    unsubscribeCaptureRef.current?.();
    unsubscribeCaptureRef.current = null;
    const capture = audioCaptureRef.current;
    audioCaptureRef.current = null;
    if (capture) await capture.cleanup();
    if (updateState && mountedRef.current) {
      setMicrophoneState("inactive");
      setSharedAudioState("inactive");
      setDisplaySurface(null);
      setMicrophoneDeduplicated(false);
    }
  }, []);

  const requestWakeLock = useCallback(async () => {
    const wakeLock = navigator.wakeLock;
    if (!wakeLock || document.visibilityState !== "visible") return;
    try {
      const sentinel = await wakeLock.request("screen");
      if (!mountedRef.current) {
        if (!sentinel.released) await sentinel.release().catch(() => undefined);
        return;
      }
      wakeLockRef.current = sentinel;
      setWakeLockActive(true);
      sentinel.addEventListener(
        "release",
        () => {
          if (mountedRef.current) setWakeLockActive(false);
        },
        { once: true },
      );
    } catch {
      if (mountedRef.current) setWakeLockActive(false);
    }
  }, []);

  const cancelServerSessionOnTeardown = useCallback(
    (current: RecordingSession): void => {
      if (
        teardownCancellationStartedRef.current ||
        !CANCELLABLE_RECORDING_STATES.has(current.lifecycleStatus)
      ) {
        return;
      }
      teardownCancellationStartedRef.current = true;
      const idempotencyKey =
        teardownCancellationKeyRef.current ??
        requestKey("recording-unmount-cancel");
      teardownCancellationKeyRef.current = idempotencyKey;
      void apiRequest(
        `/api/v1/interactions/${interactionId}/recordings/${current.id}/cancel`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey }),
          keepalive: true,
        },
      ).catch(() => undefined);
    },
    [interactionId],
  );

  useEffect(() => {
    const handleVisibility = () => {
      if (
        document.visibilityState === "visible" &&
        recorderActiveRef.current &&
        !wakeLockRef.current
      ) {
        void requestWakeLock();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, [requestWakeLock]);

  useEffect(() => {
    const active = ["recording", "paused", "uploading"].includes(state);
    onActivityChange?.({
      state,
      active,
      blocksInteractionCompletion: active || pendingChunkCount > 0,
      elapsedSeconds,
      recording,
    });
  }, [elapsedSeconds, onActivityChange, pendingChunkCount, recording, state]);

  useEffect(() => {
    onElapsedSecondsChange?.(elapsedSeconds);
  }, [elapsedSeconds, onElapsedSecondsChange]);

  useEffect(() => {
    mountedRef.current = true;
    const pendingChunks = pendingChunksRef.current;
    return () => {
      mountedRef.current = false;
      cancelledRef.current = true;
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
      const recorder = recorderRef.current;
      recorderRef.current = null;
      recorderActiveRef.current = false;
      interruptionHandledRef.current = true;
      if (recorder) {
        recorder.ondataavailable = null;
        recorder.onerror = null;
        recorder.onstop = null;
        if (recorder.state !== "inactive") recorder.stop();
      }
      const current = recordingRef.current;
      if (current && locallyStartedSessionRef.current) {
        cancelServerSessionOnTeardown(current);
      }
      locallyStartedSessionRef.current = false;
      recordingRef.current = null;
      pendingChunks.clear();
      void releaseAudioCapture(false);
      void releaseWakeLock(false);
    };
  }, [cancelServerSessionOnTeardown, releaseAudioCapture, releaseWakeLock]);

  function measuredElapsedSeconds(): number {
    if (startedAtRef.current === null) return Math.max(1, elapsedSeconds);
    const pendingPause = pausedAtRef.current
      ? Date.now() - pausedAtRef.current
      : 0;
    return Math.max(
      1,
      Math.floor(
        (Date.now() -
          startedAtRef.current -
          pausedDurationRef.current -
          pendingPause) /
          1_000,
      ),
    );
  }

  function updateElapsed() {
    if (mountedRef.current) setElapsedSeconds(measuredElapsedSeconds());
  }

  async function uploadChunkOnce(item: PendingChunk): Promise<void> {
    const current = recordingRef.current;
    if (!current || item.blob.size === 0 || cancelledRef.current) return;
    const checksum = item.checksumSha256 ?? (await sha256(item.blob));
    item.checksumSha256 = checksum;
    const chunk = await apiRequest<RecordingChunkUpload>(
      `/api/v1/interactions/${interactionId}/recordings/${current.id}/chunks`,
      {
        method: "POST",
        body: JSON.stringify({
          sequenceNumber: item.sequenceNumber,
          byteSize: item.blob.size,
          checksumSha256: checksum,
          idempotencyKey: item.createIdempotencyKey,
        }),
      },
    );
    await apiUpload(
      chunk.uploadUrl,
      item.blob,
      normaliseMimeType(mimeTypeRef.current ?? item.blob.type),
    );
    await apiRequest(
      `/api/v1/interactions/${interactionId}/recordings/${current.id}/chunks/${chunk.id}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          checksumSha256: checksum,
          idempotencyKey: item.completeIdempotencyKey,
        }),
      },
    );
    if (mountedRef.current) {
      setUploadedChunks((count) => Math.max(count, item.sequenceNumber + 1));
    }
  }

  async function uploadChunkWithRetry(item: PendingChunk): Promise<void> {
    let lastError: unknown = null;
    for (const delay of UPLOAD_RETRY_DELAYS_MS) {
      if (cancelledRef.current) return;
      if (delay) await wait(delay);
      try {
        await uploadChunkOnce(item);
        pendingChunksRef.current.delete(item.sequenceNumber);
        if (mountedRef.current) {
          setPendingChunkCount(pendingChunksRef.current.size);
        }
        return;
      } catch (requestError: unknown) {
        lastError = requestError;
      }
    }
    throw lastError instanceof Error
      ? lastError
      : new Error("An audio chunk could not be uploaded.");
  }

  function queueChunk(blob: Blob, sequenceNumber: number) {
    const item: PendingChunk = {
      blob,
      sequenceNumber,
      checksumSha256: null,
      createIdempotencyKey: requestKey(`recording-chunk-${sequenceNumber}`),
      completeIdempotencyKey: requestKey(
        `recording-complete-${sequenceNumber}`,
      ),
    };
    pendingChunksRef.current.set(sequenceNumber, item);
    setPendingChunkCount(pendingChunksRef.current.size);
    uploadQueueRef.current = uploadQueueRef.current
      .catch(() => undefined)
      .then(() => uploadChunkWithRetry(item))
      .catch((requestError: unknown) => {
        if (mountedRef.current) {
          setError(
            requestError instanceof Error
              ? `${requestError.message} The audio remains queued in this tab.`
              : "Audio is queued in this tab and needs another upload attempt.",
          );
        }
      });
  }

  async function retryQueuedChunks() {
    setState("uploading");
    setError(null);
    for (const item of [...pendingChunksRef.current.values()].sort(
      (left, right) => left.sequenceNumber - right.sequenceNumber,
    )) {
      try {
        await uploadChunkWithRetry(item);
      } catch (requestError: unknown) {
        if (!mountedRef.current) return;
        setState("failed");
        setError(
          requestError instanceof Error
            ? `${requestError.message} Keep this tab open and retry when the connection is stable.`
            : "Queued audio could not be uploaded yet.",
        );
        return;
      }
    }
    await finishUpload();
  }

  async function start() {
    if (!consentConfirmed) {
      setError("Confirm consent and authority before recording.");
      return;
    }
    const mimeType = selectSupportedRecordingMimeType(globalThis.MediaRecorder);
    if (!mimeType) {
      setState("unsupported");
      return;
    }
    setState("requesting_permission");
    setError(null);
    setSourceNotice(null);
    cancelledRef.current = false;
    locallyStartedSessionRef.current = false;
    teardownCancellationStartedRef.current = false;
    teardownCancellationKeyRef.current = requestKey("recording-unmount-cancel");
    captureInterruptedRef.current = false;
    captureInterruptionMessageRef.current = null;
    interruptionHandledRef.current = false;
    let createdSession: RecordingSession | null = null;
    try {
      const audioCapture = await acquireBrowserAudioCapture(captureMode);
      if (!mountedRef.current) {
        await audioCapture.cleanup();
        return;
      }
      audioCaptureRef.current = audioCapture;
      setMicrophoneState(audioCapture.microphoneState);
      setSharedAudioState(audioCapture.sharedAudioState);
      setDisplaySurface(audioCapture.displaySurface);
      setMicrophoneDeduplicated(audioCapture.microphoneDeduplicated);
      if (audioCapture.microphoneDeduplicated) {
        setSourceNotice(
          "The browser identified shared audio and microphone as the same source, so it is included once to prevent duplicate audio.",
        );
      }
      unsubscribeCaptureRef.current = audioCapture.subscribe((event) => {
        if (!mountedRef.current) return;
        if (event.type === "source_state") {
          if (event.source === "microphone") {
            setMicrophoneState(event.state);
          } else {
            setSharedAudioState(event.state);
          }
          return;
        }
        stopForCaptureInterruption(event.reason);
      });
      if (captureInterruptedRef.current) {
        throw new Error("An audio source ended before recording could start.");
      }
      const created = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings`,
        {
          method: "POST",
          body: JSON.stringify({
            recordingType: "live_audio_recording",
            expectedMimeType: mimeType,
            language: "en-AU",
            noticeVersion: NOTICE_VERSION,
            consentMethod: "participant_notice_confirmed",
            userAttestedAuthority: true,
            idempotencyKey: requestKey("browser-recording"),
          }),
        },
      );
      createdSession = created;
      recordingRef.current = created;
      locallyStartedSessionRef.current = true;
      if (!mountedRef.current) {
        cancelServerSessionOnTeardown(created);
        return;
      }
      if (captureInterruptedRef.current) {
        throw new Error("An audio source ended before recording could start.");
      }
      const started = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${created.id}/start`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey("recording-start"),
          }),
        },
      );
      createdSession = started;
      recordingRef.current = started;
      if (!mountedRef.current) {
        cancelServerSessionOnTeardown(started);
        return;
      }
      if (captureInterruptedRef.current) {
        throw new Error("An audio source ended before recording could start.");
      }
      setRecording(started);
      recordingRef.current = started;
      mimeTypeRef.current = mimeType;
      nextSequenceRef.current = 0;
      pendingChunksRef.current.clear();
      setPendingChunkCount(0);
      uploadQueueRef.current = Promise.resolve();
      controlQueueRef.current = Promise.resolve();
      const recorder = new MediaRecorder(audioCapture.recorderStream, {
        mimeType,
        audioBitsPerSecond: 16_000,
      });
      recorderRef.current = recorder;
      setPauseSupported(
        typeof recorder.pause === "function" &&
          typeof recorder.resume === "function",
      );
      recorder.ondataavailable = ({ data }) => {
        if (!data.size || cancelledRef.current) return;
        const sequence = nextSequenceRef.current++;
        queueChunk(data, sequence);
      };
      recorder.onerror = () => {
        if (!mountedRef.current) return;
        setError(
          "Browser recording stopped unexpectedly. Completed chunks remain on the server for recovery.",
        );
        setState("failed");
        recorderActiveRef.current = false;
        void releaseAudioCapture();
        void releaseWakeLock();
      };
      startedAtRef.current = Date.now();
      pausedDurationRef.current = 0;
      recorder.start(CHUNK_INTERVAL_MS);
      timerRef.current = setInterval(updateElapsed, 1_000);
      setElapsedSeconds(1);
      recorderActiveRef.current = true;
      void requestWakeLock();
      setState("recording");
    } catch (requestError: unknown) {
      recorderRef.current = null;
      recorderActiveRef.current = false;
      await releaseAudioCapture(mountedRef.current);
      if (createdSession) {
        if (!mountedRef.current) {
          cancelServerSessionOnTeardown(createdSession);
          return;
        }
        await apiRequest(
          `/api/v1/interactions/${interactionId}/recordings/${createdSession.id}/cancel`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotencyKey: requestKey("recording-start-cancel"),
            }),
          },
        ).catch(() => undefined);
        locallyStartedSessionRef.current = false;
        recordingRef.current = null;
        setRecording(null);
      }
      if (!mountedRef.current) return;
      const captureError =
        requestError instanceof BrowserAudioCaptureError ? requestError : null;
      const denied = captureError?.code === "microphone_permission_denied";
      setState(denied ? "permission_denied" : "failed");
      setError(
        captureInterruptionMessageRef.current ??
          (captureError
            ? captureErrorMessage(captureError)
            : requestError instanceof Error
              ? requestError.message
              : "Recording could not start."),
      );
    }
  }

  function stopForCaptureInterruption(reason: BrowserAudioInterruptionReason) {
    captureInterruptedRef.current = true;
    const notice = interruptionMessage(reason);
    captureInterruptionMessageRef.current = notice;
    setSourceNotice(notice);
    if (interruptionHandledRef.current) return;
    interruptionHandledRef.current = true;
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setState("failed");
      setError(notice);
      void releaseAudioCapture();
      return;
    }
    if (timerRef.current) clearInterval(timerRef.current);
    updateElapsed();
    recorder.onstop = () => void finishUpload();
    recorder.stop();
  }

  function pause(event: ReactMouseEvent<HTMLButtonElement>) {
    if (recorderRef.current?.state !== "recording") return;
    recorderRef.current.pause();
    pausedAtRef.current = performance.timeOrigin + event.timeStamp;
    setState("paused");
    const current = recordingRef.current;
    if (!current) return;
    controlQueueRef.current = controlQueueRef.current.then(() =>
      saveControlEvent(current, "pause"),
    );
  }

  function resume(event: ReactMouseEvent<HTMLButtonElement>) {
    if (recorderRef.current?.state !== "paused") return;
    recorderRef.current.resume();
    if (pausedAtRef.current !== null)
      pausedDurationRef.current +=
        performance.timeOrigin + event.timeStamp - pausedAtRef.current;
    pausedAtRef.current = null;
    setState("recording");
    const current = recordingRef.current;
    if (!current) return;
    controlQueueRef.current = controlQueueRef.current.then(() =>
      saveControlEvent(current, "resume"),
    );
  }

  async function saveControlEvent(
    current: RecordingSession,
    event: "pause" | "resume",
  ) {
    try {
      await apiRequest(
        `/api/v1/interactions/${interactionId}/recordings/${current.id}/${event}`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey(`recording-${event}`),
          }),
        },
      );
    } catch (requestError) {
      if (!mountedRef.current) return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : `The ${event} event could not be saved.`,
      );
    }
  }

  async function finishUpload() {
    const current = recordingRef.current;
    if (!current) {
      recorderActiveRef.current = false;
      recorderRef.current = null;
      await releaseWakeLock();
      await releaseAudioCapture();
      return;
    }
    setState("uploading");
    updateElapsed();
    try {
      await Promise.all([uploadQueueRef.current, controlQueueRef.current]);
      if (!mountedRef.current || cancelledRef.current) return;
      if (pendingChunksRef.current.size > 0) {
        throw new Error(
          "Some audio is still queued in this tab and must upload before finalisation.",
        );
      }
      const durationSeconds = measuredElapsedSeconds();
      const stopped = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${current.id}/stop`,
        {
          method: "POST",
          body: JSON.stringify({
            durationSeconds,
            idempotencyKey: requestKey("recording-stop"),
          }),
        },
      );
      if (!mountedRef.current || cancelledRef.current) return;
      setRecording(stopped);
      recordingRef.current = stopped;
      const finalized = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${current.id}/finalize`,
        {
          method: "POST",
          body: JSON.stringify({
            lastSequenceNumber: nextSequenceRef.current - 1,
            durationSeconds,
            finalMimeType: normaliseMimeType(
              mimeTypeRef.current ?? "audio/webm",
            ),
            idempotencyKey: requestKey("recording-finalize"),
          }),
        },
      );
      if (!mountedRef.current || cancelledRef.current) return;
      setRecording(finalized);
      recordingRef.current = finalized;
      locallyStartedSessionRef.current = false;
      setState("processing");
      onFinalized?.(finalized);
      await load();
    } catch (requestError: unknown) {
      if (!mountedRef.current) return;
      setState("failed");
      setError(
        requestError instanceof Error
          ? `${requestError.message} Completed chunks remain available to retry until the session expires.`
          : "The recording upload could not be finalised.",
      );
    } finally {
      recorderActiveRef.current = false;
      recorderRef.current = null;
      await releaseWakeLock();
      await releaseAudioCapture();
    }
  }

  async function retryFinalization() {
    const current = recordingRef.current;
    if (
      !current ||
      current.lifecycleStatus !== "uploading" ||
      nextSequenceRef.current === 0
    )
      return;
    setState("uploading");
    setError(null);
    try {
      const finalized = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${current.id}/finalize`,
        {
          method: "POST",
          body: JSON.stringify({
            lastSequenceNumber: nextSequenceRef.current - 1,
            durationSeconds:
              current.durationSeconds ?? Math.max(1, elapsedSeconds),
            finalMimeType: current.finalMimeType ?? current.expectedMimeType,
            idempotencyKey: requestKey("recording-finalize-retry"),
          }),
        },
      );
      if (!mountedRef.current) return;
      setRecording(finalized);
      recordingRef.current = finalized;
      locallyStartedSessionRef.current = false;
      setState("processing");
      await load();
    } catch (requestError: unknown) {
      if (!mountedRef.current) return;
      setState("failed");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The recording upload could not be finalised.",
      );
    }
  }

  function stop() {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    interruptionHandledRef.current = true;
    if (timerRef.current) clearInterval(timerRef.current);
    updateElapsed();
    recorder.onstop = () => void finishUpload();
    recorder.stop();
  }

  async function cancel() {
    cancelledRef.current = true;
    setError(null);
    setSourceNotice(null);
    recorderActiveRef.current = false;
    if (timerRef.current) clearInterval(timerRef.current);
    const recorder = recorderRef.current;
    interruptionHandledRef.current = true;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    recorderRef.current = null;
    await releaseAudioCapture();
    await releaseWakeLock();
    const current = recordingRef.current;
    if (current) {
      try {
        await apiRequest(
          `/api/v1/interactions/${interactionId}/recordings/${current.id}/cancel`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotencyKey: requestKey("recording-cancel"),
            }),
          },
        );
        locallyStartedSessionRef.current = false;
      } catch (requestError: unknown) {
        if (!mountedRef.current) return;
        setState("failed");
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The recording could not be cancelled.",
        );
        return;
      }
    }
    if (!mountedRef.current) return;
    recordingRef.current = null;
    setRecording(null);
    setElapsedSeconds(0);
    setUploadedChunks(0);
    pendingChunksRef.current.clear();
    setPendingChunkCount(0);
    setConsentConfirmed(false);
    setState("ready");
  }

  const active = ["recording", "paused", "uploading"].includes(state);
  const canCancel =
    active ||
    (recording !== null &&
      ["created", "recording", "uploading", "failed"].includes(
        recording.lifecycleStatus,
      ));
  const canRecord = ["planned", "in_progress"].includes(lifecycleStatus);
  const browserCaptureApplies = interactionType !== "phone_call";
  const currentLiveNotes = liveNotes ?? draftLiveNotes;
  const updateLiveNotes = (value: string) => {
    setDraftLiveNotes(value);
    onLiveNotesChange?.(value);
  };
  return (
    <section className="form-card" aria-labelledby="recording-foundation-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
            Browser beta
          </p>
          <h2
            id="recording-foundation-title"
            className="mt-1 text-2xl font-semibold text-slate-950"
          >
            Record interaction
          </h2>
        </div>
        <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-900">
          Keep this page open
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        Browser recording may stop if this page closes, your device locks, or
        the browser moves to the background. Completed chunks can be retried
        until the session expires.
      </p>

      <ConversationLiveNotes
        inputId={`recording-live-notes-${interactionId}`}
        liveNotes={currentLiveNotes}
        onLiveNotesChange={updateLiveNotes}
        onSave={onSaveLiveNotes}
        saveDisabled={liveNotesSaveDisabled}
        status={liveNotesStatus}
      />

      {!browserCaptureApplies ? (
        <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
          <p role="status" className="font-semibold">
            A browser cannot reliably record the same phone call running on this
            device.
          </p>
          <p className="mt-2">
            Continue without recording, then use AI Debrief, Voice Journal, or
            an authorised import when available.
          </p>
        </div>
      ) : !canRecord ? (
        <p
          role="status"
          className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-700"
        >
          Live recording is available while an interaction is planned or in
          progress. Use AI Debrief for completed interactions.
        </p>
      ) : state === "unsupported" || state === "permission_denied" ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p role="alert" className="text-sm font-semibold text-amber-950">
            {state === "unsupported"
              ? "This browser does not expose a supported audio recording format."
              : error}
          </p>
          <Link
            href={fallbackHref}
            className="mt-3 inline-block font-bold text-brand-secondary hover:underline"
          >
            {fallbackLabel}
          </Link>
        </div>
      ) : (
        <>
          {state === "ready" || (state === "failed" && !recording) ? (
            <>
              {interactionType === "online_meeting" ? (
                <fieldset className="mt-5 rounded-xl border border-slate-200 p-4">
                  <legend className="px-1 text-sm font-bold text-slate-950">
                    Audio sources
                  </legend>
                  <label className="flex items-start gap-3 text-sm leading-6">
                    <input
                      type="radio"
                      name={`recording-source-${interactionId}`}
                      className="mt-1 h-5 w-5"
                      checked={captureMode === "shared_audio_microphone"}
                      disabled={!captureSupport.sharedAudioMicrophone}
                      onChange={() => {
                        setCaptureMode("shared_audio_microphone");
                        setError(null);
                        setSourceNotice(null);
                      }}
                    />
                    <span>
                      <strong>Shared meeting audio + microphone</strong>
                      <span className="block text-slate-600">
                        Choose the meeting tab or screen and enable its
                        share-audio option. The browser-supplied audio track and
                        your microphone are combined; display video is never
                        recorded or uploaded.
                      </span>
                    </span>
                  </label>
                  <label className="mt-3 flex items-start gap-3 text-sm leading-6">
                    <input
                      type="radio"
                      name={`recording-source-${interactionId}`}
                      className="mt-1 h-5 w-5"
                      checked={captureMode === "microphone_only"}
                      onChange={() => {
                        setCaptureMode("microphone_only");
                        setError(null);
                      }}
                    />
                    <span>
                      <strong>Microphone only</strong>
                      <span className="block text-slate-600">
                        Other participants are not captured unless their audio
                        is audible through your microphone.
                      </span>
                    </span>
                  </label>
                  {!captureSupport.sharedAudioMicrophone ? (
                    <p
                      role="status"
                      className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950"
                    >
                      Shared meeting audio is unsupported in this browser.
                      Microphone-only capture remains available.
                    </p>
                  ) : null}
                </fieldset>
              ) : null}
              <label className="mt-5 flex items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm leading-6">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5"
                  checked={consentConfirmed}
                  onChange={(event) =>
                    setConsentConfirmed(event.target.checked)
                  }
                />
                <span>
                  I confirm participants have received any required notice and I
                  have authority to record. Audio may capture customer
                  participants and may be processed by the configured external
                  transcription service. Consent rules vary by jurisdiction.
                </span>
              </label>
            </>
          ) : null}

          {state === "interrupted" ? (
            <p
              role="status"
              className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"
            >
              This recording was interrupted. Verified chunks are still
              available. If stopping had completed, retry finalisation;
              otherwise cancel this session and start again.
            </p>
          ) : null}

          <div className="mt-5 rounded-2xl bg-brand-primary p-5 text-white">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-300">
              Recording status
            </p>
            <p aria-live="polite" className="mt-2 text-lg font-semibold">
              {state.replaceAll("_", " ")}
            </p>
            <p
              aria-label="Elapsed recording time"
              className="mt-2 font-mono text-4xl tabular-nums"
            >
              {elapsedLabel(elapsedSeconds)}
            </p>
            {uploadedChunks > 0 ? (
              <p className="mt-2 text-sm text-slate-300">
                {uploadedChunks} secure chunk{uploadedChunks === 1 ? "" : "s"}{" "}
                uploaded
              </p>
            ) : null}
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-300 sm:grid-cols-4">
              <div>
                <dt>Connection</dt>
                <dd className="mt-1 font-bold text-white">
                  {online ? "Online" : "Offline"}
                </dd>
              </div>
              <div>
                <dt>Capture mode</dt>
                <dd className="mt-1 font-bold text-white">
                  {captureMode === "shared_audio_microphone"
                    ? "Shared + microphone"
                    : "Microphone only"}
                </dd>
              </div>
              <div>
                <dt>Microphone</dt>
                <dd className="mt-1 font-bold capitalize text-white">
                  {microphoneDeduplicated ? "Included once" : microphoneState}
                </dd>
              </div>
              {interactionType === "online_meeting" &&
              captureMode === "shared_audio_microphone" ? (
                <>
                  <div>
                    <dt>Shared audio</dt>
                    <dd className="mt-1 font-bold capitalize text-white">
                      {sharedAudioState}
                    </dd>
                  </div>
                  <div>
                    <dt>Shared surface</dt>
                    <dd className="mt-1 font-bold text-white">
                      {displaySurfaceLabel(displaySurface)}
                    </dd>
                  </div>
                </>
              ) : null}
              <div>
                <dt>Screen wake</dt>
                <dd className="mt-1 font-bold text-white">
                  {wakeLockActive ? "Requested" : "Not guaranteed"}
                </dd>
              </div>
            </dl>
            {sourceNotice ? (
              <p
                role="status"
                className="mt-3 rounded-lg bg-white/10 p-3 text-sm font-semibold text-white"
              >
                {sourceNotice}
              </p>
            ) : null}
            {pendingChunkCount > 0 ? (
              <p className="mt-3 text-sm font-semibold text-amber-200">
                {pendingChunkCount} audio chunk
                {pendingChunkCount === 1 ? "" : "s"} queued in this tab
              </p>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            {(state === "ready" || state === "failed") && !recording ? (
              <button
                type="button"
                className="primary-button min-h-12 px-6"
                disabled={!consentConfirmed}
                onClick={() => void start()}
              >
                {interactionType === "online_meeting"
                  ? captureMode === "shared_audio_microphone"
                    ? "Start shared audio capture"
                    : "Start microphone capture"
                  : "Start recording"}
              </button>
            ) : null}
            {state === "recording" && pauseSupported ? (
              <button
                type="button"
                className="secondary-button min-h-12 px-6"
                onClick={pause}
              >
                Pause
              </button>
            ) : null}
            {state === "paused" ? (
              <button
                type="button"
                className="secondary-button min-h-12 px-6"
                onClick={resume}
              >
                Resume
              </button>
            ) : null}
            {state === "recording" || state === "paused" ? (
              <button
                type="button"
                className="primary-button min-h-12 px-6"
                onClick={stop}
              >
                Stop and upload
              </button>
            ) : null}
            {(state === "interrupted" || state === "failed") &&
            recording?.lifecycleStatus === "uploading" &&
            uploadedChunks > 0 ? (
              <button
                type="button"
                className="primary-button min-h-12 px-6"
                onClick={() => void retryFinalization()}
              >
                Retry finalisation
              </button>
            ) : null}
            {state === "failed" && pendingChunkCount > 0 ? (
              <button
                type="button"
                className="primary-button min-h-12 px-6"
                disabled={!online}
                onClick={() => void retryQueuedChunks()}
              >
                Retry queued audio
              </button>
            ) : null}
            {canCancel ? (
              <button
                type="button"
                className="secondary-button min-h-12 px-6"
                onClick={() => void cancel()}
              >
                Cancel recording
              </button>
            ) : null}
            {state === "processing" ? (
              <button
                type="button"
                className="secondary-button min-h-12 px-6"
                onClick={() => void load()}
              >
                Refresh transcription status
              </button>
            ) : null}
          </div>
        </>
      )}

      {recording?.externalProcessing ? (
        <p className="mt-4 text-xs leading-5 text-slate-500">
          External processing is configured for transcription. Oryntela sends
          audio only after finalisation.
        </p>
      ) : null}
      {transcription ? (
        <div className="mt-5 rounded-xl border border-brand-secondary/25 bg-brand-secondary/10 p-4">
          <p role="status" className="font-semibold text-brand-primary">
            {transcription.safeMessage}
          </p>
          {showTranscript && transcription.text ? (
            <div className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-slate-800">
              {transcription.text}
            </div>
          ) : null}
        </div>
      ) : null}
      {error && state !== "permission_denied" ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
    </section>
  );
}
