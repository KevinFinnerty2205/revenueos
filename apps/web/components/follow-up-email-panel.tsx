"use client";

import type {
  FollowUpEmailContent,
  FollowUpEmailRequestResponse,
  FollowUpEmailResponse,
  FollowUpEmailTone,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

const POLLING_INTERVAL_MS = 3_000;
const TERMINAL_STATES = new Set(["empty", "completed", "failed", "cancelled"]);
const tones: FollowUpEmailTone[] = ["professional", "friendly", "executive"];

export function FollowUpEmailPanel({ meetingId }: { meetingId: string }) {
  const [result, setResult] = useState<FollowUpEmailResponse | null>(null);
  const [tone, setTone] = useState<FollowUpEmailTone>("professional");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    async function load() {
      controller = new AbortController();
      try {
        const next = await apiRequest<FollowUpEmailResponse>(
          `/api/v1/meetings/${meetingId}/intelligence/follow-up-email`,
          { signal: controller.signal },
        );
        if (stopped) return;
        setResult(next);
        if (next.tone) setTone(next.tone);
        setError(null);
        setLoading(false);
        if (!TERMINAL_STATES.has(next.state)) {
          timer = setTimeout(() => void load(), POLLING_INTERVAL_MS);
        }
      } catch (requestError: unknown) {
        if (stopped || controller.signal.aborted) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Follow-up Email status could not be loaded.",
        );
        setLoading(false);
      }
    }

    void load();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
    };
  }, [meetingId, refreshKey]);

  async function generate() {
    if (generating || result?.state === "queued" || result?.state === "running")
      return;
    setGenerating(true);
    setError(null);
    setCopyStatus(null);
    try {
      await apiRequest<FollowUpEmailRequestResponse>(
        `/api/v1/meetings/${meetingId}/intelligence/follow-up-email`,
        {
          method: "POST",
          body: JSON.stringify({ tone }),
        },
      );
      setResult((current) =>
        current
          ? {
              ...current,
              state: "queued",
              generationAvailable: false,
              safeMessage: null,
              tone,
            }
          : current,
      );
      setRefreshKey((value) => value + 1);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Follow-up Email generation could not be requested.",
      );
    } finally {
      setGenerating(false);
    }
  }

  async function copyEmail(content: FollowUpEmailContent) {
    setCopyStatus(null);
    try {
      await navigator.clipboard.writeText(renderFollowUpEmail(content));
      setCopyStatus("Email copied to clipboard.");
    } catch {
      setCopyStatus(
        "The email could not be copied. Select the text and copy it manually.",
      );
    }
  }

  if (loading) {
    return (
      <div role="status" className="form-card">
        Loading Follow-up Email…
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <h2 className="form-legend text-rose-950">Draft Follow-up Email</h2>
        <p className="mt-3 text-sm text-rose-900">{error}</p>
        <button
          type="button"
          className="mt-5 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
          onClick={() => {
            setLoading(true);
            setRefreshKey((value) => value + 1);
          }}
        >
          Try again
        </button>
      </div>
    );
  }

  if (!result || result.state === "empty") {
    return (
      <div className="form-card">
        <h2 className="form-legend">Draft Follow-up Email</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          {result?.unavailableReason ??
            "Compose a customer-ready email from validated Meeting Intelligence."}
        </p>
        {result?.generationAvailable ? (
          <ComposerControls
            tone={tone}
            generating={generating}
            buttonLabel="Draft Follow-up Email"
            onToneChange={setTone}
            onGenerate={generate}
          />
        ) : (
          <p className="mt-4 text-xs font-bold uppercase tracking-wide text-slate-500">
            Unavailable
          </p>
        )}
      </div>
    );
  }

  if (result.state === "queued" || result.state === "running") {
    return (
      <div className="form-card" aria-live="polite">
        <h2 className="form-legend">Draft Follow-up Email</h2>
        <p role="status" className="mt-3 text-sm text-slate-700">
          {result.state === "queued"
            ? "Follow-up Email composition is queued…"
            : "Composing Follow-up Email…"}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          This page checks for completion every three seconds.
        </p>
      </div>
    );
  }

  if (result.state === "failed" || result.state === "cancelled") {
    return (
      <div className="form-card border-amber-200 bg-amber-50">
        <h2 className="form-legend text-amber-950">Draft Follow-up Email</h2>
        <p role="alert" className="mt-3 text-sm text-amber-900">
          {result.safeMessage ??
            "Follow-up Email generation could not be completed."}
        </p>
        {result.generationAvailable ? (
          <ComposerControls
            tone={tone}
            generating={generating}
            buttonLabel="Try composition again"
            onToneChange={setTone}
            onGenerate={generate}
          />
        ) : null}
      </div>
    );
  }

  const content = result.followUpEmail;
  if (!content) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        Follow-up Email content is unavailable. Try refreshing the page.
      </div>
    );
  }

  return (
    <article className="form-card" aria-labelledby="follow-up-email-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="follow-up-email-heading" className="form-legend">
            Draft Follow-up Email
          </h2>
          <p className="mt-2 text-xs font-medium text-slate-500">
            {humanise(content.tone)} tone ·{" "}
            {Math.round(content.confidence * 100)}% confidence
          </p>
        </div>
        <p className="text-xs font-medium text-slate-500">
          Generated{" "}
          {result.generatedAt
            ? formatMeetingDate(result.generatedAt)
            : "recently"}
        </p>
      </div>

      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm leading-6 text-slate-800">
        <p>
          <span className="font-bold text-slate-950">Subject: </span>
          {content.subject}
        </p>
        <p className="mt-5">{content.greeting}</p>
        <p className="mt-4 whitespace-pre-wrap">{content.summary}</p>
        <EmailList title="Decisions" items={content.decisions} />
        <EmailList title="Action Items" items={content.actionItems} />
        <EmailList title="Open Questions" items={content.openQuestions} />
        <p className="mt-5 whitespace-pre-wrap">{content.closing}</p>
      </div>

      {copyStatus ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {copyStatus}
        </p>
      ) : null}
      <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <label className="text-sm font-bold text-slate-800">
          Tone
          <select
            className="form-control mt-2 block min-w-44"
            value={tone}
            onChange={(event) =>
              setTone(event.target.value as FollowUpEmailTone)
            }
          >
            {tones.map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void copyEmail(content)}
          >
            Copy
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={generating}
            onClick={generate}
          >
            {generating ? "Requesting…" : "Regenerate"}
          </button>
        </div>
      </div>
    </article>
  );
}

function ComposerControls({
  tone,
  generating,
  buttonLabel,
  onToneChange,
  onGenerate,
}: {
  tone: FollowUpEmailTone;
  generating: boolean;
  buttonLabel: string;
  onToneChange: (tone: FollowUpEmailTone) => void;
  onGenerate: () => void;
}) {
  return (
    <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end">
      <label className="text-sm font-bold text-slate-800">
        Tone
        <select
          className="form-control mt-2 block min-w-44"
          value={tone}
          onChange={(event) =>
            onToneChange(event.target.value as FollowUpEmailTone)
          }
        >
          {tones.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="primary-button"
        disabled={generating}
        onClick={onGenerate}
      >
        {generating ? "Requesting…" : buttonLabel}
      </button>
    </div>
  );
}

function EmailList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mt-5" aria-label={title}>
      <h3 className="font-bold text-slate-950">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {items.map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function renderFollowUpEmail(content: FollowUpEmailContent): string {
  const sections = [
    `Subject: ${content.subject}`,
    content.greeting,
    content.summary,
    renderPlainTextList("Decisions", content.decisions),
    renderPlainTextList("Action Items", content.actionItems),
    renderPlainTextList("Open Questions", content.openQuestions),
    content.closing,
  ];
  return sections.filter((section) => section.length > 0).join("\n\n");
}

function renderPlainTextList(title: string, items: string[]): string {
  if (items.length === 0) return "";
  return `${title}:\n${items.map((item) => `- ${item}`).join("\n")}`;
}
