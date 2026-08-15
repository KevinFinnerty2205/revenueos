"use client";

import type {
  RecordingChunkUpload,
  RecordingMimeType,
  RecordingSession,
  RecordingSource,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest, apiUpload } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const MAX_RECORDING_BYTES = 512 * 1024 * 1024;
const CHUNK_BYTES = 8 * 1024 * 1024;
const NOTICE_VERSION = 1;

const callRecordingSources: RecordingSource[] = [
  "user_uploaded_recording",
  "customer_call_recording",
  "business_phone_recording",
  "external_provider_recording",
];

const onlineMeetingRecordingSources: RecordingSource[] = [
  "platform_recording",
  "user_uploaded_recording",
  "external_provider_recording",
];

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function sha256(blob: Blob): Promise<string> {
  const bytes =
    typeof blob.arrayBuffer === "function"
      ? await blob.arrayBuffer()
      : await new Promise<ArrayBuffer>((resolve, reject) => {
          const reader = new FileReader();
          reader.addEventListener("load", () => {
            if (reader.result instanceof ArrayBuffer) {
              resolve(reader.result);
              return;
            }
            reject(new Error("The recording chunk could not be read."));
          });
          reader.addEventListener("error", () =>
            reject(new Error("The recording chunk could not be read.")),
          );
          reader.readAsArrayBuffer(blob);
        });
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export function selectedRecordingMimeType(
  file: File,
): RecordingMimeType | null {
  const mimeType = file.type.toLowerCase().split(";", 1)[0];
  if (mimeType === "audio/webm") return "audio/webm";
  if (["audio/mp4", "video/mp4"].includes(mimeType)) return "audio/mp4";
  if (["audio/m4a", "audio/x-m4a"].includes(mimeType)) return "audio/m4a";
  if (mimeType && mimeType !== "application/octet-stream") return null;
  const extension = file.name.toLowerCase().split(".").pop();
  if (extension === "webm") return "audio/webm";
  if (extension === "mp4") return "audio/mp4";
  if (extension === "m4a") return "audio/m4a";
  return null;
}

export function ImportedCallRecording({
  interactionId,
  context = "phone_call",
}: {
  interactionId: string;
  context?: "phone_call" | "online_meeting";
}) {
  const [file, setFile] = useState<File | null>(null);
  const [durationSeconds, setDurationSeconds] = useState("");
  const [recordingSource, setRecordingSource] = useState<RecordingSource>(
    context === "online_meeting"
      ? "platform_recording"
      : "user_uploaded_recording",
  );
  const [authorityConfirmed, setAuthorityConfirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<RecordingSession | null>(null);
  const [recordings, setRecordings] = useState<RecordingSession[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const mimeType = file ? selectedRecordingMimeType(file) : null;
  const duration = Number(durationSeconds);

  const refreshRecordings = useCallback(
    async (signal?: AbortSignal) => {
      setRefreshing(true);
      try {
        setRecordings(
          await apiRequest<RecordingSession[]>(
            `/api/v1/interactions/${interactionId}/recordings`,
            { signal },
          ),
        );
      } catch (requestError: unknown) {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Recording status could not be loaded.",
        );
      } finally {
        if (!signal?.aborted) setRefreshing(false);
      }
    },
    [interactionId],
  );

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<RecordingSession[]>(
      `/api/v1/interactions/${interactionId}/recordings`,
      { signal: controller.signal },
    )
      .then(setRecordings)
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Recording status could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [interactionId]);

  async function upload() {
    if (!file || !mimeType) {
      setError("Choose a supported WebM, MP4 or M4A audio file.");
      return;
    }
    if (file.size === 0 || file.size > MAX_RECORDING_BYTES) {
      setError("The recording must be non-empty and no larger than 512 MiB.");
      return;
    }
    if (!Number.isInteger(duration) || duration < 1 || duration > 10_800) {
      setError("Enter a duration from 1 second to 3 hours.");
      return;
    }
    if (!authorityConfirmed) {
      setError("Confirm your authority to process this business recording.");
      return;
    }
    setWorking(true);
    setError(null);
    setProgress(0);
    try {
      const recording = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings`,
        {
          method: "POST",
          body: JSON.stringify({
            recordingType: "imported_audio_recording",
            recordingSource,
            expectedMimeType: mimeType,
            language: "en-AU",
            noticeVersion: NOTICE_VERSION,
            consentMethod: "contractual_authority",
            userAttestedAuthority: true,
            idempotencyKey: requestKey(`${context}-import`),
          }),
        },
      );
      await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${recording.id}/start`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey(`${context}-import-start`),
          }),
        },
      );
      const chunkCount = Math.ceil(file.size / CHUNK_BYTES);
      for (
        let sequenceNumber = 0;
        sequenceNumber < chunkCount;
        sequenceNumber += 1
      ) {
        const chunkBlob = file.slice(
          sequenceNumber * CHUNK_BYTES,
          Math.min(file.size, (sequenceNumber + 1) * CHUNK_BYTES),
          mimeType,
        );
        const checksumSha256 = await sha256(chunkBlob);
        const chunk = await apiRequest<RecordingChunkUpload>(
          `/api/v1/interactions/${interactionId}/recordings/${recording.id}/chunks`,
          {
            method: "POST",
            body: JSON.stringify({
              sequenceNumber,
              byteSize: chunkBlob.size,
              checksumSha256,
              idempotencyKey: requestKey(
                `${context}-import-chunk-${sequenceNumber}`,
              ),
            }),
          },
        );
        await apiUpload(chunk.uploadUrl, chunkBlob, mimeType);
        await apiRequest(
          `/api/v1/interactions/${interactionId}/recordings/${recording.id}/chunks/${chunk.id}/complete`,
          {
            method: "POST",
            body: JSON.stringify({
              checksumSha256,
              idempotencyKey: requestKey(
                `${context}-import-complete-${sequenceNumber}`,
              ),
            }),
          },
        );
        setProgress(Math.round(((sequenceNumber + 1) / chunkCount) * 100));
      }
      const finalised = await apiRequest<RecordingSession>(
        `/api/v1/interactions/${interactionId}/recordings/${recording.id}/finalize`,
        {
          method: "POST",
          body: JSON.stringify({
            lastSequenceNumber: chunkCount - 1,
            durationSeconds: duration,
            finalMimeType: mimeType,
            idempotencyKey: requestKey(`${context}-import-finalise`),
          }),
        },
      );
      setCompleted(finalised);
      setRecordings((current) => [
        finalised,
        ...current.filter((item) => item.id !== finalised.id),
      ]);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The recording could not be imported.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <section
      aria-labelledby={`add-${context}-recording-title`}
      className="form-card"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Compliant recording import
      </p>
      <h2
        id={`add-${context}-recording-title`}
        className="mt-2 text-2xl font-semibold text-slate-950"
      >
        Add Recording
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        {context === "online_meeting"
          ? "Add an authorised recording exported from your meeting platform. RevenueOS privately uploads it for batch transcription; it does not join the meeting, capture system audio or run a bot."
          : "Add an existing authorised business-call recording. This uses the same private upload and transcription path as other Interaction recordings; it does not record or monitor your phone."}
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="secondary-button"
          disabled={refreshing}
          onClick={() => void refreshRecordings()}
        >
          {refreshing ? "Refreshing…" : "Refresh recording status"}
        </button>
        {recordings.length > 0 ? (
          <p role="status" className="text-sm text-slate-700">
            Latest:{" "}
            {humanise(recordings[0].recordingSource ?? "unknown source")} ·
            transcription {humanise(recordings[0].transcriptionStatus)}
          </p>
        ) : null}
      </div>

      {completed ? (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p role="status" className="font-semibold text-emerald-950">
            Recording imported securely
          </p>
          <p className="mt-2 text-sm leading-6 text-emerald-900">
            Provenance: {humanise(completed.recordingSource ?? recordingSource)}
            . Batch transcription is {completed.transcriptionStatus}.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-5">
          <label className="grid gap-2 text-sm font-bold text-slate-800">
            Audio file
            <input
              type="file"
              accept=".webm,.mp4,.m4a,audio/webm,audio/mp4,audio/m4a,audio/x-m4a"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setError(null);
              }}
            />
          </label>
          {file ? (
            <dl className="grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="font-semibold text-slate-600">File</dt>
                <dd className="mt-1 break-all text-slate-900">{file.name}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-600">Format</dt>
                <dd className="mt-1 text-slate-900">
                  {mimeType ?? "Unsupported"}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-600">Size</dt>
                <dd className="mt-1 text-slate-900">
                  {(file.size / (1024 * 1024)).toFixed(1)} MiB
                </dd>
              </div>
            </dl>
          ) : null}
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Recording source
              <select
                className="form-control"
                value={recordingSource}
                onChange={(event) =>
                  setRecordingSource(event.target.value as RecordingSource)
                }
              >
                {(context === "online_meeting"
                  ? onlineMeetingRecordingSources
                  : callRecordingSources
                ).map((source) => (
                  <option key={source} value={source}>
                    {humanise(source)}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              {context === "online_meeting"
                ? "Meeting duration in seconds"
                : "Call duration in seconds"}
              <input
                className="form-control"
                type="number"
                min={1}
                max={10_800}
                inputMode="numeric"
                value={durationSeconds}
                onChange={(event) => setDurationSeconds(event.target.value)}
              />
            </label>
          </div>
          <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-950">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5"
              checked={authorityConfirmed}
              onChange={(event) => setAuthorityConfirmed(event.target.checked)}
            />
            <span>
              I confirm this is an authorised business interaction and I have
              authority to upload and process this recording, including any
              required participant notice or consent.
            </span>
          </label>
          {error ? (
            <p
              role="alert"
              className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
            >
              {error}
            </p>
          ) : null}
          {working ? (
            <p role="status" className="text-sm font-semibold text-teal-800">
              Secure upload {progress}%
            </p>
          ) : null}
          <button
            type="button"
            className="primary-button justify-self-start"
            disabled={working || !file || !mimeType || !authorityConfirmed}
            onClick={() => void upload()}
          >
            {working ? "Importing…" : "Import recording"}
          </button>
        </div>
      )}
    </section>
  );
}
