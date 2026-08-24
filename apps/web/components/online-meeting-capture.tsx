"use client";

import type {
  Interaction,
  OnlineMeetingCapabilities,
  OnlineMeetingTranscriptImport,
  TranscriptProvenance,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { ImportedCallRecording } from "@/components/imported-call-recording";

const MAX_TRANSCRIPT_BYTES = 512 * 1024;
const transcriptExtensions = new Set(["txt", "vtt", "srt"]);

function requestKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `online-transcript-${crypto.randomUUID()}`
    : `online-transcript-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function base64(bytes: Uint8Array): string {
  let encoded = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    encoded += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(encoded);
}

export function OnlineMeetingCapture({
  interaction,
}: {
  interaction: Interaction;
}) {
  const [capabilities, setCapabilities] =
    useState<OnlineMeetingCapabilities | null>(null);
  const [imports, setImports] = useState<OnlineMeetingTranscriptImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [provenance, setProvenance] =
    useState<TranscriptProvenance>("platform_generated");
  const [authorityConfirmed, setAuthorityConfirmed] = useState(false);
  const [processingConfirmed, setProcessingConfirmed] = useState(false);
  const [importing, setImporting] = useState(false);
  const [completed, setCompleted] =
    useState<OnlineMeetingTranscriptImport | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<OnlineMeetingCapabilities>(
        `/api/v1/interactions/${interaction.id}/online-meeting/capabilities`,
        { signal: controller.signal },
      ),
      apiRequest<OnlineMeetingTranscriptImport[]>(
        `/api/v1/interactions/${interaction.id}/online-meeting/transcripts`,
        { signal: controller.signal },
      ),
    ])
      .then(([nextCapabilities, nextImports]) => {
        setCapabilities(nextCapabilities);
        setImports(nextImports);
      })
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
            : "Online meeting capture options could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interaction.id]);

  async function importTranscript(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!authorityConfirmed || !processingConfirmed) {
      setError("Confirm both authority and processing acknowledgements.");
      return;
    }
    let fileName = "pasted-transcript.txt";
    let bytes: Uint8Array;
    if (file !== null) {
      const extension = file.name.toLowerCase().split(".").pop() ?? "";
      if (!transcriptExtensions.has(extension)) {
        setError("Choose a TXT, VTT or SRT transcript.");
        return;
      }
      if (file.size < 1 || file.size > MAX_TRANSCRIPT_BYTES) {
        setError(
          "The transcript must be non-empty and no larger than 512 KiB.",
        );
        return;
      }
      fileName = file.name;
      bytes = new Uint8Array(await file.arrayBuffer());
    } else {
      const content = pastedText.trim();
      if (!content) {
        setError("Choose a transcript file or paste transcript text.");
        return;
      }
      bytes = new TextEncoder().encode(content);
      if (bytes.byteLength > MAX_TRANSCRIPT_BYTES) {
        setError("The transcript must be no larger than 512 KiB.");
        return;
      }
    }
    setImporting(true);
    try {
      const result = await apiRequest<OnlineMeetingTranscriptImport>(
        `/api/v1/interactions/${interaction.id}/online-meeting/transcript`,
        {
          method: "POST",
          body: JSON.stringify({
            fileName,
            contentBase64: base64(bytes),
            provenance,
            language: "en-AU",
            userAttestedAuthority: true,
            externalProcessingAcknowledged: true,
            idempotencyKey: requestKey(),
          }),
        },
      );
      setCompleted(result);
      setImports((current) => [
        result,
        ...current.filter((item) => item.id !== result.id),
      ]);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The transcript could not be imported.",
      );
    } finally {
      setImporting(false);
    }
  }

  if (loading) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading online meeting capture choices…
      </p>
    );
  }

  if (!capabilities) {
    return (
      <section className="form-card" aria-labelledby="online-capture-error">
        <h2 id="online-capture-error" className="form-legend">
          Capture this meeting
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error ?? "Online meeting capture is unavailable."}
        </p>
      </section>
    );
  }

  return (
    <div className="grid gap-6">
      <section className="form-card" aria-labelledby="online-capture-title">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          {humanise(capabilities.meetingPlatform)} · passive Companion
        </p>
        <h2 id="online-capture-title" className="mt-2 text-2xl font-semibold">
          Capture this meeting
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {capabilities.safeMessage} RevenueOS never joins this meeting or
          captures browser system audio. Choose an authorised source below, or
          report what happened while the context is fresh.
        </p>
        <ul className="mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-xl bg-slate-50 p-4">
            Recording import:{" "}
            {capabilities.recordingImport ? "available" : "unavailable"}
          </li>
          <li className="rounded-xl bg-slate-50 p-4">
            Transcript import:{" "}
            {capabilities.transcriptImport ? "available" : "unavailable"}
          </li>
          <li className="rounded-xl bg-slate-50 p-4">
            Native fetch: not configured
          </li>
          <li className="rounded-xl bg-slate-50 p-4">
            Debrief fallback:{" "}
            {capabilities.aiDebrief ? "available" : "unavailable"}
          </li>
        </ul>
        <div className="mt-5 flex flex-wrap gap-3">
          {capabilities.aiDebrief ? (
            <a className="secondary-button" href="#debrief">
              Use AI Debrief
            </a>
          ) : null}
          {capabilities.voiceJournal ? (
            <a className="secondary-button" href="#debrief">
              Use Voice Journal
            </a>
          ) : null}
          {interaction.meetingId ? (
            <Link
              className="secondary-button"
              href={`/meetings/${interaction.meetingId}`}
            >
              Open Interaction Intelligence
            </Link>
          ) : null}
        </div>
      </section>

      {capabilities.transcriptImport ? (
        <section
          className="form-card"
          aria-labelledby="transcript-import-title"
        >
          <h2 id="transcript-import-title" className="form-legend">
            Import transcript
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Import UTF-8 TXT, VTT or SRT. Timestamps and speaker labels are
            preserved where present; labels remain unverified and are never
            treated as identity matches.
          </p>
          {completed ? (
            <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
              <p role="status" className="font-semibold text-emerald-950">
                Transcript ready
              </p>
              <p className="mt-2 text-sm text-emerald-900">
                Version {completed.version} · {humanise(completed.provenance)} ·{" "}
                {completed.characterCount.toLocaleString()} characters
              </p>
              <Link
                className="secondary-button mt-4"
                href={`/meetings/${completed.meetingId}`}
              >
                Generate Interaction Intelligence
              </Link>
            </div>
          ) : (
            <form className="mt-5 grid gap-5" onSubmit={importTranscript}>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Transcript file
                <input
                  type="file"
                  accept=".txt,.vtt,.srt,text/plain,text/vtt,application/x-subrip"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null);
                    setError(null);
                  }}
                />
              </label>
              <p className="text-center text-xs font-bold uppercase tracking-wide text-slate-500">
                or
              </p>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Paste transcript text
                <textarea
                  className="form-control min-h-36"
                  maxLength={500_000}
                  value={pastedText}
                  disabled={file !== null}
                  onChange={(event) => setPastedText(event.target.value)}
                />
              </label>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Transcript provenance
                <select
                  className="form-control"
                  value={provenance}
                  onChange={(event) =>
                    setProvenance(event.target.value as TranscriptProvenance)
                  }
                >
                  <option value="platform_generated">
                    Generated by the meeting platform
                  </option>
                  <option value="user_uploaded">Uploaded by a user</option>
                  <option value="externally_generated">
                    Generated by another approved service
                  </option>
                  <option value="manually_pasted">
                    Manually pasted notes or transcript
                  </option>
                </select>
              </label>
              <label className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5"
                  checked={authorityConfirmed}
                  onChange={(event) =>
                    setAuthorityConfirmed(event.target.checked)
                  }
                />
                <span>
                  I confirm I am authorised to upload and process this
                  transcript, including required participant notice or consent.
                </span>
              </label>
              <label className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5"
                  checked={processingConfirmed}
                  onChange={(event) =>
                    setProcessingConfirmed(event.target.checked)
                  }
                />
                <span>
                  I understand approved processing may send transcript content
                  to the configured external AI service; transcript content is
                  not written to application logs.
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
              <button
                type="submit"
                className="primary-button justify-self-start"
                disabled={importing || (!file && !pastedText.trim())}
              >
                {importing ? "Importing…" : "Import transcript"}
              </button>
            </form>
          )}
          {imports.length > 0 ? (
            <p className="mt-5 text-sm text-slate-600">
              {imports.length} authorised transcript{" "}
              {imports.length === 1 ? "version" : "versions"} imported.
            </p>
          ) : null}
        </section>
      ) : null}

      {capabilities.recordingImport ? (
        <ImportedCallRecording
          interactionId={interaction.id}
          context="online_meeting"
        />
      ) : null}
    </div>
  );
}
