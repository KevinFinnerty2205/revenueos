"use client";

import type {
  Company,
  RevenueBrainReasoningRequestResponse,
  RevenueBrainReasoningResponse,
  RevenueBrainSnapshot,
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
    ])
      .then(([loadedCompany, loadedSnapshots, loadedReasoning]) => {
        setCompany(loadedCompany);
        setSnapshots(loadedSnapshots);
        setReasoning(loadedReasoning);
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
            : "Revenue Brain could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [accountId, retryKey]);

  if (error) {
    return (
      <section aria-labelledby="revenue-brain-title">
        <h1
          id="revenue-brain-title"
          className="text-4xl font-semibold tracking-tight text-slate-950"
        >
          Revenue Brain
        </h1>
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

  if (!company || !snapshots || !reasoning) {
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
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
          {company.name}
        </h1>
        <Link
          href={`/companies/${company.id}/edit`}
          className="mt-4 inline-flex text-sm font-bold text-teal-700 hover:text-teal-900 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          Edit account
        </Link>
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
