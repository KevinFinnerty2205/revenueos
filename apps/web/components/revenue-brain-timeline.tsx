"use client";

import type {
  Company,
  RevenueBrainReasoningRequestResponse,
  RevenueBrainReasoningResponse,
  RevenueBrainReportedSnapshot,
  RevenueBrainSourceSnapshot,
  RevenueBrainSnapshot,
  RevenueBrainVisualSnapshot,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { RevenueBrainInsightPanel } from "@/components/revenue-brain-insight";

export function RevenueBrainTimeline({ accountId }: { accountId: string }) {
  const [company, setCompany] = useState<Company | null>(null);
  const [snapshots, setSnapshots] = useState<RevenueBrainSnapshot[] | null>(
    null,
  );
  const [reasoning, setReasoning] =
    useState<RevenueBrainReasoningResponse | null>(null);
  const [visualSnapshots, setVisualSnapshots] = useState<
    RevenueBrainVisualSnapshot[] | null
  >(null);
  const [reportedSnapshots, setReportedSnapshots] = useState<
    RevenueBrainReportedSnapshot[] | null
  >(null);
  const [sourceSnapshots, setSourceSnapshots] = useState<
    RevenueBrainSourceSnapshot[] | null
  >(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reasoningError, setReasoningError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<Company>(`/api/v1/companies/${accountId}`, {
        signal: controller.signal,
      }),
      apiRequest<RevenueBrainSnapshot[]>(
        `/api/v1/accounts/${accountId}/brain`,
        { signal: controller.signal },
      ),
      apiRequest<RevenueBrainReasoningResponse>(
        `/api/v1/accounts/${accountId}/brain/reasoning`,
        { signal: controller.signal },
      ),
      apiRequest<RevenueBrainVisualSnapshot[]>(
        `/api/v1/accounts/${accountId}/brain/visual-evidence`,
        { signal: controller.signal },
      ),
      apiRequest<RevenueBrainReportedSnapshot[]>(
        `/api/v1/accounts/${accountId}/brain/reported-interactions`,
        { signal: controller.signal },
      ),
      apiRequest<RevenueBrainSourceSnapshot[]>(
        `/api/v1/evidence/accounts/${accountId}/brain`,
        { signal: controller.signal },
      )
        .then((loadedSourceSnapshots) => {
          setSourceError(null);
          return loadedSourceSnapshots;
        })
        .catch((requestError: unknown) => {
          if (
            requestError instanceof DOMException &&
            requestError.name === "AbortError"
          ) {
            throw requestError;
          }
          setSourceError("Document and email evidence could not be loaded.");
          return [];
        }),
    ])
      .then(
        ([
          loadedCompany,
          loadedSnapshots,
          loadedReasoning,
          loadedVisualSnapshots,
          loadedReportedSnapshots,
          loadedSourceSnapshots,
        ]) => {
          setCompany(loadedCompany);
          setSnapshots(loadedSnapshots);
          setReasoning(loadedReasoning);
          setVisualSnapshots(loadedVisualSnapshots);
          setReportedSnapshots(loadedReportedSnapshots);
          setSourceSnapshots(loadedSourceSnapshots);
        },
      )
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
            : "Revenue Brain could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [accountId, retryKey]);

  if (error) {
    return (
      <section aria-labelledby="revenue-brain-title">
        <h2
          id="revenue-brain-title"
          className="text-3xl font-semibold tracking-tight text-slate-950"
        >
          Account intelligence
        </h2>
        <div
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6"
        >
          <p className="font-semibold text-red-900">{error}</p>
          <button
            type="button"
            onClick={() => {
              setCompany(null);
              setSnapshots(null);
              setError(null);
              setRetryKey((key) => key + 1);
            }}
            className="mt-4 min-h-11 rounded-xl bg-red-800 px-5 py-2 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2"
          >
            Try again
          </button>
        </div>
      </section>
    );
  }

  async function requestReasoning() {
    setRequesting(true);
    setReasoningError(null);
    try {
      const response = await apiRequest<RevenueBrainReasoningRequestResponse>(
        `/api/v1/accounts/${accountId}/brain/reasoning?mode=recent_history`,
        { method: "POST" },
      );
      setReasoning(response);
    } catch (requestError: unknown) {
      setReasoningError(
        requestError instanceof Error
          ? requestError.message
          : "Longitudinal reasoning could not be generated.",
      );
    } finally {
      setRequesting(false);
    }
  }

  if (
    !company ||
    !snapshots ||
    !reasoning ||
    !visualSnapshots ||
    !reportedSnapshots ||
    !sourceSnapshots
  ) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <p className="font-semibold text-slate-700">Loading Revenue Brain…</p>
      </div>
    );
  }

  const insightsBySnapshot = new Map(
    reasoning.history.map((insight) => [insight.content.toSnapshotId, insight]),
  );

  return (
    <div className="space-y-6">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          Account
        </p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
          Account intelligence
        </h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href={`/assistant?mode=ask&scope=account&scopeId=${company.id}`}
            className="primary-button"
          >
            Ask about this account
          </Link>
          <Link
            href={`/companies/${company.id}/edit`}
            className="secondary-button"
          >
            Edit account
          </Link>
        </div>
      </header>

      <RevenueBrainInsightPanel
        reasoning={reasoning}
        heading="Latest Account Change"
        headingId="latest-account-change"
        requesting={requesting}
        requestError={reasoningError}
        onRequest={() => void requestReasoning()}
      />

      <section
        aria-labelledby="revenue-brain-source-evidence-title"
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          id="revenue-brain-source-evidence-title"
          className="text-2xl font-semibold tracking-tight text-slate-950"
        >
          Document and email evidence
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Only user-accepted findings appear here. Every item keeps its source,
          ownership, support class and location; seller-created material is not
          presented as customer-confirmed evidence.
        </p>
        {sourceError ? (
          <div
            role="alert"
            className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950"
          >
            <p>{sourceError}</p>
            <button
              type="button"
              onClick={() => setRetryKey((key) => key + 1)}
              className="mt-3 min-h-11 rounded-lg border border-amber-400 bg-white px-4 py-2 font-bold focus:outline-none focus:ring-2 focus:ring-amber-700 focus:ring-offset-2"
            >
              Retry evidence
            </button>
          </div>
        ) : sourceSnapshots.length === 0 ? (
          <p className="mt-5 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            No reviewed document or email evidence yet.
          </p>
        ) : (
          <ol
            aria-label="Document and email evidence timeline"
            className="mt-6 space-y-5"
          >
            {sourceSnapshots.slice(0, 10).map((snapshot) => (
              <li
                key={snapshot.id}
                className="border-l-2 border-amber-200 pl-5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-slate-950">
                    {snapshot.sourceLabel}
                  </p>
                  <time
                    dateTime={snapshot.occurredAt}
                    className="text-sm text-slate-600"
                  >
                    {formatMeetingDate(snapshot.occurredAt)}
                  </time>
                </div>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-amber-800">
                  {snapshot.sourceKind} ·{" "}
                  {snapshot.sourceType.replaceAll("_", " ")} ·{" "}
                  {snapshot.sourceOrigin.replaceAll("_", " ")}
                </p>
                <ul className="mt-3 space-y-2">
                  {snapshot.items.map((item) => (
                    <li
                      key={item.evidenceId}
                      className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700"
                    >
                      <span className="font-bold text-slate-900">
                        {item.category.replaceAll("_", " ")}:{" "}
                      </span>
                      {item.statement}
                      <span className="mt-1 block text-xs text-slate-500">
                        {item.location.reference} ·{" "}
                        {item.supportClass.replaceAll("_", " ")}
                      </span>
                    </li>
                  ))}
                </ul>
                {snapshot.opportunityId ? (
                  <Link
                    href={`/opportunities/${snapshot.opportunityId}`}
                    className="mt-3 inline-flex text-sm font-bold text-teal-800 underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                  >
                    Open opportunity
                  </Link>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section
        aria-labelledby="revenue-brain-reported-title"
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          id="revenue-brain-reported-title"
          className="text-2xl font-semibold tracking-tight text-slate-950"
        >
          Reviewed interaction intelligence
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Accepted post-interaction reports stay labelled as
          salesperson-reported evidence and are never promoted to
          customer-direct evidence.
        </p>
        {reportedSnapshots.length === 0 ? (
          <p className="mt-5 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            No reviewed post-interaction reports yet.
          </p>
        ) : (
          <ol
            aria-label="Reported interaction timeline"
            className="mt-6 space-y-5"
          >
            {reportedSnapshots.slice(0, 10).map((snapshot) => (
              <li
                key={snapshot.id}
                className="border-l-2 border-indigo-200 pl-5"
              >
                <p className="font-semibold text-slate-950">
                  {snapshot.interactionTitle}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-indigo-700">
                  {snapshot.sourceLabel} ·{" "}
                  {snapshot.interactionType.replaceAll("_", " ")}
                </p>
                <time
                  dateTime={snapshot.interactionDate}
                  className="mt-1 block text-sm text-slate-600"
                >
                  {formatMeetingDate(snapshot.interactionDate)}
                </time>
                <ul className="mt-3 space-y-2">
                  {snapshot.items.map((item) => (
                    <li
                      key={item.evidenceId}
                      className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700"
                    >
                      <span className="font-bold text-slate-900">
                        {item.category.replaceAll("_", " ")}:{" "}
                      </span>
                      {item.statement}
                      {item.conflictState !== "not_assessed" ? (
                        <span className="mt-1 block text-xs text-slate-500">
                          Recording comparison:{" "}
                          {item.conflictState.replaceAll("_", " ")}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
                <Link
                  href={`/interactions/${snapshot.interactionId}`}
                  className="mt-3 inline-flex text-sm font-bold text-teal-800 underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                >
                  Open interaction
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section
        aria-labelledby="revenue-brain-visual-title"
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          id="revenue-brain-visual-title"
          className="text-2xl font-semibold tracking-tight text-slate-950"
        >
          Reviewed visual evidence
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Source-labelled visual findings appear only after user review. Raw
          images stay in private evidence storage.
        </p>
        {visualSnapshots.length === 0 ? (
          <p className="mt-5 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            No reviewed visual evidence yet.
          </p>
        ) : (
          <ol aria-label="Visual evidence timeline" className="mt-6 space-y-5">
            {visualSnapshots.slice(0, 10).map((snapshot) => (
              <li
                key={snapshot.id}
                className="border-l-2 border-indigo-200 pl-5"
              >
                <p className="font-semibold text-slate-950">
                  {snapshot.interactionTitle}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-indigo-700">
                  {snapshot.sourceLabel} · AI-interpreted, user-reviewed
                </p>
                <time
                  dateTime={snapshot.interactionDate}
                  className="mt-1 block text-sm text-slate-600"
                >
                  {formatMeetingDate(snapshot.interactionDate)}
                </time>
                <ul className="mt-3 space-y-2">
                  {snapshot.items.map((item) => (
                    <li
                      key={item.evidenceId}
                      className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700"
                    >
                      <span className="font-bold text-slate-900">
                        {item.category.replaceAll("_", " ")}:{" "}
                      </span>
                      {item.statement}
                      <span className="mt-1 block text-xs text-slate-500">
                        {item.supportClassification === "observed"
                          ? "Observed; not customer-confirmed"
                          : item.supportClassification}
                      </span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={`/interactions/${snapshot.interactionId}`}
                  className="mt-3 inline-flex text-sm font-bold text-teal-800 underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                >
                  Open interaction
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section
        aria-labelledby="revenue-brain-title"
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2
          id="revenue-brain-title"
          className="text-2xl font-semibold tracking-tight text-slate-950"
        >
          Revenue Brain
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Snapshot timeline
        </p>

        {snapshots.length === 0 ? (
          <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6">
            <h3 className="font-semibold text-slate-900">No snapshots yet</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Completed meeting intelligence snapshots will appear here.
            </p>
          </div>
        ) : (
          <ol aria-label="Snapshot timeline" className="mt-7 space-y-5">
            {snapshots.slice(0, 10).map((snapshot) => {
              const insight = insightsBySnapshot.get(snapshot.id);
              return (
                <li
                  key={snapshot.id}
                  className="relative border-l-2 border-teal-200 pb-1 pl-6"
                >
                  <span
                    aria-hidden="true"
                    className="absolute -left-[7px] top-1.5 h-3 w-3 rounded-full bg-teal-700"
                  />
                  <p className="text-sm font-semibold text-slate-950">
                    Meeting snapshot
                  </p>
                  <time
                    dateTime={snapshot.meetingDate}
                    className="mt-1 block text-sm text-slate-600"
                  >
                    {formatMeetingDate(snapshot.meetingDate)}
                  </time>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-sm">
                    <Link
                      href={`/meetings/${snapshot.meetingId}`}
                      className="font-bold text-teal-800 underline decoration-teal-300 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                    >
                      Open meeting
                    </Link>
                    {snapshot.opportunityId ? (
                      <Link
                        href={`/opportunities/${snapshot.opportunityId}`}
                        className="font-bold text-teal-800 underline decoration-teal-300 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                      >
                        Open opportunity
                      </Link>
                    ) : null}
                  </div>
                  {insight ? (
                    <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                      <span className="font-bold text-slate-900">
                        Change from the previous eligible snapshot:{" "}
                      </span>
                      {insight.content.summary}
                    </p>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">
                      No adjacent reasoning insight has been generated.
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}

function formatMeetingDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "long",
  }).format(new Date(value));
}
