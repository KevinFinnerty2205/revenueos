"use client";

import type {
  BriefPriority,
  InteractionType,
  PreInteractionBriefContent,
  PreInteractionBriefRequestResponse,
  PreInteractionBriefResponse,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { formatInteractionDate } from "@/lib/interactions";

const priorityStyle: Record<BriefPriority, string> = {
  high: "bg-rose-50 text-rose-800",
  medium: "bg-amber-50 text-amber-900",
  low: "bg-slate-100 text-slate-700",
};

function Priority({ value }: { value: BriefPriority }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wide ${priorityStyle[value]}`}
    >
      {value}
    </span>
  );
}

function BriefSection({
  title,
  children,
  empty,
}: {
  title: string;
  children: React.ReactNode;
  empty?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
        {title}
      </h3>
      {empty ? (
        <p className="mt-3 text-sm text-slate-500">No validated items yet.</p>
      ) : (
        children
      )}
    </section>
  );
}

function BriefContent({ content }: { content: PreInteractionBriefContent }) {
  if (content.interactionType === "phone_call") {
    return <PhoneCallBriefContent content={content} />;
  }
  return (
    <div className="mt-6 space-y-4">
      <div className="rounded-2xl bg-slate-950 p-5 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-300">
          Account context
        </p>
        <p className="mt-3 text-sm leading-6 text-slate-100">
          {content.accountContext}
        </p>
        <p className="mt-4 text-xs text-slate-300">
          Source completeness {Math.round(content.confidence * 100)}%
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BriefSection title="Objectives">
          <ul className="mt-3 space-y-4">
            {content.objectives.map((item) => (
              <li key={item.objective}>
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-slate-900">
                    {item.objective}
                  </p>
                  <Priority value={item.priority} />
                </div>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  {item.reason}
                </p>
              </li>
            ))}
          </ul>
        </BriefSection>
        <BriefSection title="Questions to ask">
          <ol className="mt-3 space-y-4">
            {content.questionsToAsk.map((item, index) => (
              <li key={item.question} className="flex gap-3">
                <span className="font-bold text-teal-700">{index + 1}.</span>
                <div>
                  <div className="flex flex-wrap items-start gap-2">
                    <p className="font-semibold text-slate-900">
                      {item.question}
                    </p>
                    <Priority value={item.priority} />
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    {item.purpose}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </BriefSection>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BriefSection
          title="Recent changes"
          empty={content.recentChanges.length === 0}
        >
          <ul className="mt-3 space-y-3">
            {content.recentChanges.map((item) => (
              <li
                key={item.change}
                className="flex items-start justify-between gap-3 text-sm leading-6 text-slate-700"
              >
                <span>{item.change}</span>
                <Priority value={item.importance} />
              </li>
            ))}
          </ul>
        </BriefSection>
        <BriefSection
          title="Stakeholder focus"
          empty={content.stakeholderFocus.length === 0}
        >
          <ul className="mt-3 space-y-3">
            {content.stakeholderFocus.map((item) => (
              <li key={`${item.name}-${item.role}`}>
                <p className="font-semibold text-slate-900">
                  {item.name} · {item.role}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  {item.focus}
                </p>
              </li>
            ))}
          </ul>
        </BriefSection>
      </div>

      <details
        className="rounded-2xl border border-slate-200 bg-white p-5"
        open
      >
        <summary className="cursor-pointer font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-600">
          Commitments, risks and success criteria
        </summary>
        <div className="mt-5 grid gap-6 lg:grid-cols-3">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Open commitments
            </h3>
            {content.openCommitments.length ? (
              <ul className="mt-3 space-y-3 text-sm text-slate-700">
                {content.openCommitments.map((item) => (
                  <li key={`${item.commitment}-${item.owner ?? "unassigned"}`}>
                    <p>{item.commitment}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.owner ?? "Owner not confirmed"}
                      {item.dueDate ? ` · ${item.dueDate}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-slate-500">
                No validated items yet.
              </p>
            )}
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Risks to watch
            </h3>
            {content.risksToWatch.length ? (
              <ul className="mt-3 space-y-3">
                {content.risksToWatch.map((item) => (
                  <li
                    key={item.risk}
                    className="flex items-start justify-between gap-2 text-sm text-slate-700"
                  >
                    <span>{item.risk}</span>
                    <Priority value={item.severity} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-slate-500">
                No validated items yet.
              </p>
            )}
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Success criteria
            </h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">
              {content.successCriteria.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>

      <div className="rounded-2xl border border-teal-200 bg-teal-50 p-5">
        <h3 className="font-semibold text-teal-950">
          {content.interactionType === "presentation"
            ? "Presentation guidance"
            : "Interaction guidance"}
        </h3>
        <p className="mt-2 text-sm leading-6 text-teal-950">
          {content.interactionGuidance}
        </p>
      </div>
    </div>
  );
}

function PhoneCallBriefContent({
  content,
}: {
  content: PreInteractionBriefContent;
}) {
  return (
    <div className="mt-6 space-y-4">
      <div className="rounded-2xl bg-slate-950 p-5 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-300">
          Compact call brief
        </p>
        <p className="mt-3 text-lg font-semibold">{content.headline}</p>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {content.accountContext}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <BriefSection
          title="Contact and role"
          empty={!content.stakeholderFocus.length}
        >
          <ul className="mt-3 space-y-3">
            {content.stakeholderFocus.slice(0, 2).map((item) => (
              <li key={`${item.name}-${item.role}`}>
                <p className="font-semibold text-slate-900">
                  {item.name} · {item.role}
                </p>
                <p className="mt-1 text-sm text-slate-600">{item.focus}</p>
              </li>
            ))}
          </ul>
        </BriefSection>
        <BriefSection
          title="Purpose and desired next step"
          empty={!content.objectives.length && !content.successCriteria.length}
        >
          <p className="mt-3 font-semibold text-slate-900">
            {content.objectives[0]?.objective}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {content.successCriteria[0]}
          </p>
        </BriefSection>
        <BriefSection
          title="Latest commitment"
          empty={!content.openCommitments.length}
        >
          {content.openCommitments.slice(0, 1).map((item) => (
            <div className="mt-3" key={item.commitment}>
              <p className="font-semibold text-slate-900">{item.commitment}</p>
              <p className="mt-1 text-sm text-slate-600">
                {item.owner ?? "Owner not confirmed"}
                {item.dueDate ? ` · ${item.dueDate}` : ""}
              </p>
            </div>
          ))}
        </BriefSection>
        <BriefSection
          title="Objection or timeline issue"
          empty={!content.risksToWatch.length}
        >
          {content.risksToWatch.slice(0, 2).map((item) => (
            <p
              className="mt-3 text-sm leading-6 text-slate-700"
              key={item.risk}
            >
              {item.risk}
            </p>
          ))}
        </BriefSection>
      </div>
      {content.recentChanges.length ? (
        <p className="rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-950">
          <strong>Recent Revenue Brain change:</strong>{" "}
          {content.recentChanges[0].change}
        </p>
      ) : null}
      <BriefSection
        title="Recommended questions"
        empty={!content.questionsToAsk.length}
      >
        <ol className="mt-3 space-y-3">
          {content.questionsToAsk.slice(0, 3).map((item, index) => (
            <li
              key={item.question}
              className="flex gap-3 text-sm text-slate-800"
            >
              <span className="font-bold text-teal-700">{index + 1}.</span>
              <span>{item.question}</span>
            </li>
          ))}
        </ol>
      </BriefSection>
      <p className="rounded-2xl border border-teal-200 bg-teal-50 p-4 text-sm leading-6 text-teal-950">
        {content.interactionGuidance}
      </p>
    </div>
  );
}

export function PreInteractionBrief({
  interactionId,
  interactionType,
}: {
  interactionId: string;
  interactionType: InteractionType;
}) {
  const [response, setResponse] = useState<PreInteractionBriefResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<PreInteractionBriefResponse>(
      `/api/v1/interactions/${interactionId}/companion/brief`,
      { signal: controller.signal },
    )
      .then(setResponse)
      .catch((requestError: unknown) => {
        if (!(
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        )) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "The preparation brief could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interactionId]);

  async function generate() {
    setWorking(true);
    setError(null);
    try {
      setResponse(
        await apiRequest<PreInteractionBriefRequestResponse>(
          `/api/v1/interactions/${interactionId}/companion/brief`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The preparation brief could not be created.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function markReviewed() {
    setWorking(true);
    setError(null);
    try {
      setResponse(
        await apiRequest<PreInteractionBriefResponse>(
          `/api/v1/interactions/${interactionId}/companion/brief/review`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The review state could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <section
      aria-labelledby="preparation-brief-title"
      className="rounded-3xl border border-slate-200 bg-slate-50 p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            AI Companion · Before
          </p>
          <h2
            id="preparation-brief-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            Prepare for this interaction
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            A source-aware preparation view built from linked records and
            validated prior intelligence. It does not record or listen.
          </p>
        </div>
        {response?.state === "completed" ? (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-emerald-900">
            Brief ready
          </span>
        ) : null}
      </div>

      <div aria-live="polite" className="mt-5">
        {loading ? (
          <p role="status" className="text-sm text-slate-600">
            Loading preparation brief…
          </p>
        ) : null}
        {error ? (
          <p
            role="alert"
            className="rounded-xl bg-red-50 p-4 text-sm text-red-900"
          >
            {error}
          </p>
        ) : null}
        {!loading && response?.state === "unavailable" ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-5">
            <h3 className="font-semibold text-slate-900">
              Link account or opportunity context
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {response.safeMessage ??
                "A linked company or opportunity is required before a useful brief can be prepared."}
            </p>
          </div>
        ) : null}
        {!loading && response?.state === "not_generated" ? (
          <div className="rounded-2xl border border-dashed border-teal-300 bg-white p-5">
            <h3 className="font-semibold text-slate-900">
              Prepare for this{" "}
              {interactionType === "phone_call" ? "call" : "interaction"}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Build a concise brief from the current linked context. A new
              source version creates a new brief version.
            </p>
            <button
              type="button"
              className="primary-button mt-4"
              disabled={working || !response.generationAvailable}
              onClick={generate}
            >
              {working ? "Preparing…" : "Prepare brief"}
            </button>
          </div>
        ) : null}
        {!loading &&
        response &&
        ["queued", "running"].includes(response.state) ? (
          <p role="status" className="text-sm text-slate-600">
            Preparing the latest brief…
          </p>
        ) : null}
        {!loading &&
        response &&
        ["failed", "cancelled"].includes(response.state) ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-5">
            <p className="text-sm text-red-900">
              {response.safeMessage ??
                "The brief is not ready. You can try again."}
            </p>
            {response.generationAvailable ? (
              <button
                type="button"
                className="secondary-button mt-4"
                disabled={working}
                onClick={generate}
              >
                {working ? "Preparing…" : "Try again"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {response?.state === "completed" && response.brief ? (
        <>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-5">
            <div>
              <h3 className="text-xl font-semibold text-slate-950">
                {response.brief.headline}
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Version {response.brief.briefVersion} · prepared{" "}
                {formatInteractionDate(response.generatedAt)}
              </p>
              {response.sourceLabels.length ? (
                <p className="mt-2 text-xs text-slate-500">
                  Sources: {response.sourceLabels.join(" · ")}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              className="secondary-button"
              disabled={working || response.reviewed}
              onClick={markReviewed}
            >
              {response.reviewed
                ? "Reviewed"
                : working
                  ? "Saving…"
                  : "Mark as reviewed"}
            </button>
          </div>
          <BriefContent content={response.brief} />
        </>
      ) : null}
    </section>
  );
}
