"use client";

import type {
  InteractionLifecycleStatus,
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

const MIME_PREFERENCES = [
  "audio/webm;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
] as const;
const CHUNK_INTERVAL_MS = 5_000;
const NOTICE_VERSION = 1;

type RecorderState =
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

export function RecordingFoundation({
  interactionId,
  lifecycleStatus,
}: {
  interactionId: string;
  lifecycleStatus: InteractionLifecycleStatus;
}) {
  const [state, setState] = useState<RecorderState>("checking");
  const [recording, setRecording] = useState<RecordingSession | null>(null);
  const [transcription, setTranscription] =
    useState<RecordingTranscription | null>(null);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [uploadedChunks, setUploadedChunks] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingRef = useRef<RecordingSession | null>(null);
  const mimeTypeRef = useRef<string | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const pausedAtRef = useRef<number | null>(null);
  const pausedDurationRef = useRef(0);
  const nextSequenceRef = useRef(0);
  const uploadQueueRef = useRef<Promise<void>>(Promise.resolve());
  const controlQueueRef = useRef<Promise<void>>(Promise.resolve());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    const recordings = await apiRequest<RecordingSession[]>(
      `/api/v1/interactions/${interactionId}/recordings`,
    );
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
      setTranscription(transcript);
      setState(transcript.status === "completed" ? "completed" : "processing");
    } else if (
      ["created", "recording", "uploading"].includes(latest.lifecycleStatus)
    ) {
      setState("interrupted");
      const chunks = await apiRequest<
        Array<{ sequenceNumber: number; uploadState: string }>
      >(`/api/v1/interactions/${interactionId}/recordings/${latest.id}/chunks`);
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
      const supported =
        typeof navigator !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        selectSupportedRecordingMimeType(globalThis.MediaRecorder) !== null;
      if (!supported) {
        if (!cancelled) setState("unsupported");
        return;
      }
      if (!cancelled) setState("ready");
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
  }, [load]);

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
      if (["recording", "paused", "uploading"].includes(state)) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state]);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

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
    setElapsedSeconds(measuredElapsedSeconds());
  }

  async function uploadChunk(
    blob: Blob,
    sequenceNumber: number,
  ): Promise<void> {
    const current = recordingRef.current;
    if (!current || blob.size === 0 || cancelledRef.current) return;
    const checksum = await sha256(blob);
    const chunk = await apiRequest<RecordingChunkUpload>(
      `/api/v1/interactions/${interactionId}/recordings/${current.id}/chunks`,
      {
        method: "POST",
        body: JSON.stringify({
          sequenceNumber,
          byteSize: blob.size,
          checksumSha256: checksum,
          idempotencyKey: requestKey(`recording-chunk-${sequenceNumber}`),
        }),
      },
    );
    await apiUpload(
      chunk.uploadUrl,
      blob,
      normaliseMimeType(mimeTypeRef.current ?? blob.type),
    );
    await apiRequest(
      `/api/v1/interactions/${interactionId}/recordings/${current.id}/chunks/${chunk.id}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          checksumSha256: checksum,
          idempotencyKey: requestKey(`recording-complete-${sequenceNumber}`),
        }),
      },
    );
    setUploadedChunks(sequenceNumber + 1);
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
    cancelledRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
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
      const started = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${created.id}/start`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey("recording-start"),
          }),
        },
      );
      setRecording(started);
      recordingRef.current = started;
      mimeTypeRef.current = mimeType;
      nextSequenceRef.current = 0;
      uploadQueueRef.current = Promise.resolve();
      controlQueueRef.current = Promise.resolve();
      const recorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond: 16_000,
      });
      recorderRef.current = recorder;
      recorder.ondataavailable = ({ data }) => {
        if (!data.size || cancelledRef.current) return;
        const sequence = nextSequenceRef.current++;
        uploadQueueRef.current = uploadQueueRef.current.then(() =>
          uploadChunk(data, sequence),
        );
      };
      recorder.onerror = () => {
        setError(
          "Browser recording stopped unexpectedly. Completed chunks remain on the server for recovery.",
        );
        setState("failed");
      };
      startedAtRef.current = Date.now();
      pausedDurationRef.current = 0;
      recorder.start(CHUNK_INTERVAL_MS);
      timerRef.current = setInterval(updateElapsed, 1_000);
      setElapsedSeconds(1);
      setState("recording");
    } catch (requestError: unknown) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const denied =
        requestError instanceof DOMException &&
        ["NotAllowedError", "SecurityError"].includes(requestError.name);
      setState(denied ? "permission_denied" : "failed");
      setError(
        denied
          ? "Microphone access was denied. You can use AI Debrief or text capture instead."
          : requestError instanceof Error
            ? requestError.message
            : "Recording could not start.",
      );
    }
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
      setError(
        requestError instanceof Error
          ? requestError.message
          : `The ${event} event could not be saved.`,
      );
    }
  }

  async function finishUpload() {
    const current = recordingRef.current;
    if (!current) return;
    setState("uploading");
    updateElapsed();
    try {
      await Promise.all([uploadQueueRef.current, controlQueueRef.current]);
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
      setRecording(finalized);
      recordingRef.current = finalized;
      setState("processing");
      await load();
    } catch (requestError: unknown) {
      setState("failed");
      setError(
        requestError instanceof Error
          ? `${requestError.message} Completed chunks remain available to retry until the session expires.`
          : "The recording upload could not be finalised.",
      );
    } finally {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
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
      setRecording(finalized);
      recordingRef.current = finalized;
      setState("processing");
      await load();
    } catch (requestError: unknown) {
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
    if (timerRef.current) clearInterval(timerRef.current);
    updateElapsed();
    recorder.onstop = () => void finishUpload();
    recorder.stop();
  }

  async function cancel() {
    cancelledRef.current = true;
    if (timerRef.current) clearInterval(timerRef.current);
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
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
      } catch (requestError: unknown) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The recording could not be cancelled.",
        );
      }
    }
    recordingRef.current = null;
    setRecording(null);
    setElapsedSeconds(0);
    setUploadedChunks(0);
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
  return (
    <section className="form-card" aria-labelledby="recording-foundation-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-teal-800">
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

      {!canRecord ? (
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
            href="#debrief"
            className="mt-3 inline-block font-bold text-teal-800 hover:underline"
          >
            Use AI Debrief instead
          </Link>
        </div>
      ) : (
        <>
          {state === "ready" || (state === "failed" && !recording) ? (
            <label className="mt-5 flex items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm leading-6">
              <input
                type="checkbox"
                className="mt-1 h-5 w-5"
                checked={consentConfirmed}
                onChange={(event) => setConsentConfirmed(event.target.checked)}
              />
              <span>
                I confirm participants have received any required notice and I
                have authority to record. Audio may capture customer
                participants and may be processed by the configured external
                transcription provider. Consent rules vary by jurisdiction.
              </span>
            </label>
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

          <div className="mt-5 rounded-2xl bg-slate-950 p-5 text-white">
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
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            {(state === "ready" || state === "failed") && !recording ? (
              <button
                type="button"
                className="primary-button min-h-12 px-6"
                disabled={!consentConfirmed}
                onClick={() => void start()}
              >
                Start recording
              </button>
            ) : null}
            {state === "recording" ? (
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
          External processing is configured for transcription. RevenueOS sends
          audio only after finalisation.
        </p>
      ) : null}
      {transcription ? (
        <div className="mt-5 rounded-xl border border-teal-200 bg-teal-50 p-4">
          <p role="status" className="font-semibold text-teal-950">
            {transcription.safeMessage}
          </p>
          {transcription.text ? (
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
