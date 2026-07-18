"use client";

import type {
  RisksBlockersRequestResponse,
  RisksBlockersResponse,
} from "@revenueos/shared";
import { type ReactNode, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

const POLLING_INTERVAL_MS = 3_000;
const TERMINAL_STATES = new Set(["empty", "completed", "failed", "cancelled"]);

export function RisksBlockersPanel({ meetingId }: { meetingId: string }) {
  const [result, setResult] = useState<RisksBlockersResponse | null>(null);
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
        const next = await apiRequest<RisksBlockersResponse>(
          `/api/v1/meetings/${meetingId}/intelligence/risks-blockers`,
          { signal: controller.signal },
        );
        if (stopped) return;
        setResult(next);
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
            : "Risks & Blockers status could not be loaded.",
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
    try {
      await apiRequest<RisksBlockersRequestResponse>(
        `/api/v1/meetings/${meetingId}/intelligence/risks-blockers`,
        { method: "POST" },
      );
      setResult((current) =>
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
          : "Risks & Blockers generation could not be requested.",
      );
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div role="status" className="form-card">
        Loading Risks &amp; Blockers…
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <h2 className="form-legend text-rose-950">Risks &amp; Blockers</h2>
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
        <h2 className="form-legend">Risks &amp; Blockers</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          {result?.unavailableReason ??
            "Identify transcript-grounded obstacles and conditions that could delay progress."}
        </p>
        {result?.generationAvailable ? (
          <button
            type="button"
            className="primary-button mt-5"
            disabled={generating}
            onClick={generate}
          >
            {generating ? "Requesting…" : "Generate Risks & Blockers"}
          </button>
        ) : null}
      </div>
    );
  }

  if (result.state === "queued" || result.state === "running") {
    return (
      <div className="form-card" aria-live="polite">
        <h2 className="form-legend">Risks &amp; Blockers</h2>
        <p role="status" className="mt-3 text-sm text-slate-700">
          {result.state === "queued"
            ? "Risks & Blockers generation is queued…"
            : "Generating Risks & Blockers…"}
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
        <h2 className="form-legend text-amber-950">Risks &amp; Blockers</h2>
        <p role="alert" className="mt-3 text-sm text-amber-900">
          {result.safeMessage ??
            "Risks & Blockers generation could not be completed."}
        </p>
        {result.generationAvailable ? (
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

  const content = result.risksBlockers;
  if (!content) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        Risks &amp; Blockers content is unavailable. Try refreshing the page.
      </div>
    );
  }

  return (
    <article className="form-card" aria-labelledby="risks-blockers-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id="risks-blockers-heading" className="form-legend">
          Risks &amp; Blockers
        </h2>
        <p className="text-xs font-medium text-slate-500">
          Generated{" "}
          {result.generatedAt
            ? formatMeetingDate(result.generatedAt)
            : "recently"}
        </p>
      </div>
      {content.risks.length === 0 ? (
        <p className="mt-5 text-sm text-slate-700">
          No risks or blockers were identified in this meeting.
        </p>
      ) : (
        <ol className="mt-5 grid gap-4">
          {content.risks.map((item, index) => (
            <li
              key={`${index}-${item.risk}`}
              className="rounded-xl border border-slate-200 bg-slate-50 p-4"
            >
              <p className="text-sm font-bold leading-6 text-slate-950">
                {item.risk}
              </p>
              <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
                <RiskDetail label="Category">
                  {humanise(item.category)}
                </RiskDetail>
                <RiskDetail label="Severity">
                  {humanise(item.severity)}
                </RiskDetail>
                {item.owner ? (
                  <RiskDetail label="Owner">{item.owner}</RiskDetail>
                ) : null}
                <RiskDetail label="Confidence">
                  {Math.round(item.confidence * 100)}%
                </RiskDetail>
              </dl>
              <p className="mt-4 text-sm leading-6 text-slate-600">
                <span className="font-bold text-slate-700">Evidence: </span>
                {item.evidence}
              </p>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

function RiskDetail({
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
      <dd className="mt-1 text-sm text-slate-800">{children}</dd>
    </div>
  );
}
