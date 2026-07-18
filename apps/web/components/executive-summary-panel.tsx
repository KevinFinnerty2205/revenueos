"use client";

import type {
  ExecutiveSummaryRequestResponse,
  ExecutiveSummaryResponse,
} from "@revenueos/shared";
import { type ReactNode, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

const POLLING_INTERVAL_MS = 3_000;
const TERMINAL_STATES = new Set(["empty", "completed", "failed", "cancelled"]);

export function ExecutiveSummaryPanel({ meetingId }: { meetingId: string }) {
  const [summary, setSummary] = useState<ExecutiveSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    async function load() {
      controller = new AbortController();
      try {
        const next = await apiRequest<ExecutiveSummaryResponse>(
          `/api/v1/meetings/${meetingId}/intelligence/executive-summary`,
          { signal: controller.signal },
        );
        if (stopped) return;
        setSummary(next);
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
            : "Executive Summary status could not be loaded.",
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
    if (
      generating ||
      summary?.state === "queued" ||
      summary?.state === "running"
    )
      return;
    setGenerating(true);
    setError(null);
    try {
      await apiRequest<ExecutiveSummaryRequestResponse>(
        `/api/v1/meetings/${meetingId}/intelligence/executive-summary`,
        { method: "POST" },
      );
      setSummary((current) =>
        current
          ? {
              ...current,
              state: "queued",
              generationAvailable: false,
              safeMessage: null,
            }
          : current,
      );
      setRefreshKey((value) => value + 1);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Executive Summary generation could not be requested.",
      );
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div role="status" className="form-card">
        Loading Executive Summary…
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <h2 className="form-legend text-rose-950">Executive Summary</h2>
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

  if (!summary || summary.state === "empty") {
    return (
      <div className="form-card">
        <h2 className="form-legend">Executive Summary</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          {summary?.unavailableReason ??
            "Generate a concise, transcript-grounded overview of this meeting."}
        </p>
        {summary?.generationAvailable ? (
          <button
            type="button"
            className="primary-button mt-5"
            disabled={generating}
            onClick={generate}
          >
            {generating ? "Requesting…" : "Generate Executive Summary"}
          </button>
        ) : null}
      </div>
    );
  }

  if (summary.state === "queued" || summary.state === "running") {
    return (
      <div className="form-card" aria-live="polite">
        <h2 className="form-legend">Executive Summary</h2>
        <p role="status" className="mt-3 text-sm text-slate-700">
          {summary.state === "queued"
            ? "Executive Summary is queued…"
            : "Generating Executive Summary…"}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          This page checks for completion every three seconds.
        </p>
      </div>
    );
  }

  if (summary.state === "failed" || summary.state === "cancelled") {
    return (
      <div className="form-card border-amber-200 bg-amber-50">
        <h2 className="form-legend text-amber-950">Executive Summary</h2>
        <p role="alert" className="mt-3 text-sm text-amber-900">
          {summary.safeMessage ??
            "Executive Summary generation could not be completed."}
        </p>
        {summary.generationAvailable ? (
          <button
            type="button"
            className="primary-button mt-5"
            disabled={generating}
            onClick={generate}
          >
            {generating ? "Requesting…" : "Try generation again"}
          </button>
        ) : null}
      </div>
    );
  }

  const content = summary.executiveSummary;
  if (!content) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        Executive Summary content is unavailable. Try refreshing the page.
      </div>
    );
  }

  return (
    <article className="form-card" aria-labelledby="executive-summary-heading">
      <h2 id="executive-summary-heading" className="form-legend">
        Executive Summary
      </h2>
      <p className="mt-5 whitespace-pre-wrap text-base leading-7 text-slate-800">
        {content.executiveSummary}
      </p>
      <dl className="mt-7 grid gap-5 border-t border-slate-200 pt-5 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryDetail label="Meeting Type">
          {humanise(content.meetingType)}
        </SummaryDetail>
        <SummaryDetail label="Sentiment">
          {humanise(content.sentiment)}
        </SummaryDetail>
        <SummaryDetail label="Confidence">
          {Math.round(content.confidence * 100)}%
        </SummaryDetail>
        <SummaryDetail label="Generated">
          {summary.generatedAt
            ? formatMeetingDate(summary.generatedAt)
            : "Recently"}
        </SummaryDetail>
      </dl>
    </article>
  );
}

function SummaryDetail({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-bold text-slate-900">{children}</dd>
    </div>
  );
}
