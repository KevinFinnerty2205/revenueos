"use client";

import type {
  Interaction,
  OnlineMeetingCapabilities,
  OnlineMeetingTranscriptImport,
  TranscriptProvenance,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { ImportedCallRecording } from "@/components/imported-call-recording";

const MAX_TRANSCRIPT_BYTES = 512 * 1024;
const transcriptExtensions = new Set(["txt", "vtt", "srt"]);

type CapabilitiesState =
  | { interactionId: string; status: "loading" }
  | {
      interactionId: string;
      status: "available";
      value: OnlineMeetingCapabilities;
    }
  | { interactionId: string; status: "unavailable"; message: string };

type HistoryState = {
  interactionId: string;
  status: "loading" | "available" | "unavailable";
  items: OnlineMeetingTranscriptImport[];
};

type InteractionValue<T> = {
  interactionId: string;
  value: T;
};

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

function mergeImports(
  first: OnlineMeetingTranscriptImport[],
  second: OnlineMeetingTranscriptImport[],
): OnlineMeetingTranscriptImport[] {
  const byId = new Map<string, OnlineMeetingTranscriptImport>();
  for (const item of [...first, ...second]) {
    if (!byId.has(item.id)) byId.set(item.id, item);
  }
  return [...byId.values()];
}

type OnlineMeetingCaptureProps = {
  interaction: Interaction;
  onTranscriptImported?: (result: OnlineMeetingTranscriptImport) => void;
};

export function OnlineMeetingCapture(props: OnlineMeetingCaptureProps) {
  return (
    <OnlineMeetingCaptureForInteraction key={props.interaction.id} {...props} />
  );
}

function OnlineMeetingCaptureForInteraction({
  interaction,
  onTranscriptImported,
}: OnlineMeetingCaptureProps) {
  const [capabilitiesState, setCapabilitiesState] = useState<CapabilitiesState>(
    {
      interactionId: interaction.id,
      status: "loading",
    },
  );
  const [historyState, setHistoryState] = useState<HistoryState>({
    interactionId: interaction.id,
    status: "loading",
    items: [],
  });
  const [importError, setImportError] =
    useState<InteractionValue<string> | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [provenance, setProvenance] =
    useState<TranscriptProvenance>("platform_generated");
  const [authorityConfirmed, setAuthorityConfirmed] = useState(false);
  const [processingConfirmed, setProcessingConfirmed] = useState(false);
  const [importingInteractionId, setImportingInteractionId] = useState<
    string | null
  >(null);
  const [completedState, setCompletedState] =
    useState<InteractionValue<OnlineMeetingTranscriptImport> | null>(null);
  const mounted = useRef(true);
  const loadGeneration = useRef(0);
  const mutationGeneration = useRef(0);
  const importController = useRef<AbortController | null>(null);

  useEffect(() => {
    mounted.current = true;
    const requestedInteractionId = interaction.id;
    const generation = ++loadGeneration.current;
    const controller = new AbortController();
    importController.current?.abort();
    importController.current = null;
    mutationGeneration.current += 1;
    const isCurrent = () =>
      mounted.current &&
      !controller.signal.aborted &&
      loadGeneration.current === generation;

    void apiRequest<OnlineMeetingCapabilities>(
      `/api/v1/interactions/${requestedInteractionId}/online-meeting/capabilities`,
      { signal: controller.signal },
    ).then(
      (nextCapabilities) => {
        if (!isCurrent()) return;
        setCapabilitiesState({
          interactionId: requestedInteractionId,
          status: "available",
          value: nextCapabilities,
        });
      },
      (requestError: unknown) => {
        if (
          !isCurrent() ||
          (requestError instanceof DOMException &&
            requestError.name === "AbortError")
        ) {
          return;
        }
        setCapabilitiesState({
          interactionId: requestedInteractionId,
          status: "unavailable",
          message:
            requestError instanceof Error
              ? requestError.message
              : "Online meeting capture options could not be loaded.",
        });
      },
    );

    void apiRequest<OnlineMeetingTranscriptImport[]>(
      `/api/v1/interactions/${requestedInteractionId}/online-meeting/transcripts`,
      { signal: controller.signal },
    ).then(
      (nextImports) => {
        if (!isCurrent()) return;
        setHistoryState((current) => {
          if (current.interactionId !== requestedInteractionId) return current;
          return {
            interactionId: requestedInteractionId,
            status: "available",
            items: mergeImports(current.items, nextImports),
          };
        });
      },
      (requestError: unknown) => {
        if (
          !isCurrent() ||
          (requestError instanceof DOMException &&
            requestError.name === "AbortError")
        ) {
          return;
        }
        setHistoryState((current) => {
          if (current.interactionId !== requestedInteractionId) return current;
          return { ...current, status: "unavailable" };
        });
      },
    );

    return () => {
      mounted.current = false;
      controller.abort();
      loadGeneration.current += 1;
      mutationGeneration.current += 1;
      importController.current?.abort();
      importController.current = null;
    };
  }, [interaction.id]);

  async function importTranscript(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestedInteractionId = interaction.id;
    setImportError(null);
    const setCurrentError = (message: string) => {
      if (!mounted.current) return;
      setImportError({ interactionId: requestedInteractionId, value: message });
    };
    if (!authorityConfirmed || !processingConfirmed) {
      setCurrentError(
        "Confirm both authority and processing acknowledgements.",
      );
      return;
    }
    let fileName = "pasted-transcript.txt";
    let bytes: Uint8Array;
    if (file !== null) {
      const extension = file.name.toLowerCase().split(".").pop() ?? "";
      if (!transcriptExtensions.has(extension)) {
        setCurrentError("Choose a TXT, VTT or SRT transcript.");
        return;
      }
      if (file.size < 1 || file.size > MAX_TRANSCRIPT_BYTES) {
        setCurrentError(
          "The transcript must be non-empty and no larger than 512 KiB.",
        );
        return;
      }
      fileName = file.name;
      bytes = new Uint8Array(await file.arrayBuffer());
    } else {
      const content = pastedText.trim();
      if (!content) {
        setCurrentError("Choose a transcript file or paste transcript text.");
        return;
      }
      bytes = new TextEncoder().encode(content);
      if (bytes.byteLength > MAX_TRANSCRIPT_BYTES) {
        setCurrentError("The transcript must be no larger than 512 KiB.");
        return;
      }
    }
    if (!mounted.current) return;
    const controller = new AbortController();
    importController.current?.abort();
    importController.current = controller;
    const generation = ++mutationGeneration.current;
    const isCurrent = () =>
      mounted.current &&
      !controller.signal.aborted &&
      mutationGeneration.current === generation;
    setImportingInteractionId(requestedInteractionId);
    try {
      const result = await apiRequest<OnlineMeetingTranscriptImport>(
        `/api/v1/interactions/${requestedInteractionId}/online-meeting/transcript`,
        {
          method: "POST",
          signal: controller.signal,
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
      if (!isCurrent()) return;
      setCompletedState({
        interactionId: requestedInteractionId,
        value: result,
      });
      setHistoryState((current) =>
        current.interactionId === requestedInteractionId
          ? { ...current, items: mergeImports([result], current.items) }
          : current,
      );
      onTranscriptImported?.(result);
    } catch (requestError: unknown) {
      if (
        !isCurrent() ||
        (requestError instanceof DOMException &&
          requestError.name === "AbortError")
      ) {
        return;
      }
      setCurrentError(
        requestError instanceof Error
          ? requestError.message
          : "The transcript could not be imported.",
      );
    } finally {
      if (mutationGeneration.current === generation) {
        importController.current = null;
        if (mounted.current) {
          setImportingInteractionId(null);
        }
      }
    }
  }

  const visibleCapabilitiesState =
    capabilitiesState.interactionId === interaction.id
      ? capabilitiesState
      : ({ interactionId: interaction.id, status: "loading" } as const);
  const visibleHistoryState =
    historyState.interactionId === interaction.id
      ? historyState
      : ({
          interactionId: interaction.id,
          status: "loading",
          items: [],
        } as const);
  const error =
    importError?.interactionId === interaction.id ? importError.value : null;
  const completed =
    completedState?.interactionId === interaction.id
      ? completedState.value
      : null;
  const importing = importingInteractionId === interaction.id;

  if (visibleCapabilitiesState.status === "loading") {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading online meeting capture choices…
      </p>
    );
  }

  if (visibleCapabilitiesState.status === "unavailable") {
    return (
      <section className="form-card" aria-labelledby="online-capture-error">
        <h2 id="online-capture-error" className="form-legend">
          Capture this meeting
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {visibleCapabilitiesState.message}
        </p>
      </section>
    );
  }

  const capabilities = visibleCapabilitiesState.value;

  return (
    <div className="grid gap-6">
      <section className="form-card" aria-labelledby="online-capture-title">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
          {humanise(capabilities.meetingPlatform)} · passive Companion
        </p>
        <h2 id="online-capture-title" className="mt-2 text-2xl font-semibold">
          Capture this meeting
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {capabilities.safeMessage} Oryntela never joins this meeting or runs a
          meeting bot. Browser audio is captured only during an explicit
          Companion session; after the meeting, choose an authorised source
          below or report what happened while the context is fresh.
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
              href={`/conversations/${interaction.id}#enhanced-notes`}
            >
              Open conversation review
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
          {visibleHistoryState.status === "loading" ? (
            <p className="mt-4 text-sm text-slate-600" role="status">
              Loading previous transcript import history…
            </p>
          ) : null}
          {visibleHistoryState.status === "unavailable" ? (
            <p
              className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
              role="status"
            >
              Previous transcript import history is temporarily unavailable. You
              can still import an authorised transcript.
            </p>
          ) : null}
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
                href={`/conversations/${interaction.id}#enhanced-notes`}
              >
                Review notes and follow-up
              </Link>
            </div>
          ) : (
            <form className="mt-5 grid gap-5" onSubmit={importTranscript}>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Transcript file
                <input
                  key={interaction.id}
                  type="file"
                  accept=".txt,.vtt,.srt,text/plain,text/vtt,application/x-subrip"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null);
                    setImportError(null);
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
          {visibleHistoryState.status === "available" &&
          visibleHistoryState.items.length > 0 ? (
            <p className="mt-5 text-sm text-slate-600">
              {visibleHistoryState.items.length} authorised transcript{" "}
              {visibleHistoryState.items.length === 1 ? "version" : "versions"}{" "}
              imported.
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
