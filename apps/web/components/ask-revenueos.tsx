"use client";

import type {
  AskAnswer,
  AskCapabilities,
  AskScopeType,
} from "@revenueos/shared";
import Link from "next/link";
import {
  FormEvent,
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { apiRequest } from "@/lib/api";

const suggestedQuestions: Record<AskScopeType, string[]> = {
  opportunity: [
    "What is holding this deal back?",
    "Who is the economic buyer?",
    "What changed recently?",
    "What should I do next?",
  ],
  account: [
    "What changed recently?",
    "Who are the key stakeholders?",
    "What commitments are open?",
    "What opportunities are active?",
  ],
  workspace: [
    "Which deals need my attention?",
    "What do I need to do today?",
    "What should I do next?",
    "What are the biggest deal risks?",
    "Which deals don’t have an economic buyer?",
    "Which commitments are overdue?",
  ],
};

export function AskRevenueOS({
  scopeType = "workspace",
  scopeId = null,
  initialQuestion = "",
}: {
  scopeType?: AskScopeType;
  scopeId?: string | null;
  initialQuestion?: string;
}) {
  const [capabilities, setCapabilities] = useState<AskCapabilities | null>(
    null,
  );
  const [question, setQuestion] = useState(initialQuestion);
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryQuestion, setRetryQuestion] = useState<string | null>(null);
  const answerRef = useRef<HTMLElement>(null);
  const answerTitleId = useId();

  useEffect(() => {
    const controller = new AbortController();
    const parameters = new URLSearchParams({ scopeType });
    if (scopeId) parameters.set("scopeId", scopeId);
    apiRequest<AskCapabilities>(
      `/api/v1/ask/capabilities?${parameters.toString()}`,
      { signal: controller.signal },
    )
      .then((loaded) => {
        setCapabilities(loaded);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Ask RevenueOS is unavailable right now.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
  }, [scopeId, scopeType]);

  async function submitQuestion(value: string) {
    const trimmed = value.trim();
    if (trimmed.length < 2) {
      setError("Enter a question with at least two characters.");
      return;
    }
    setLoading(true);
    setError(null);
    setRetryQuestion(trimmed);
    try {
      const loaded = await apiRequest<AskAnswer>("/api/v1/ask", {
        method: "POST",
        body: JSON.stringify({
          question: trimmed,
          scopeType,
          scopeId,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      });
      setAnswer(loaded);
      window.requestAnimationFrame(() => answerRef.current?.focus());
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "RevenueOS couldn’t answer that right now.",
      );
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion(question);
  }

  if (checking) {
    return (
      <p role="status" className="form-card text-sm text-slate-600">
        Checking Ask RevenueOS availability…
      </p>
    );
  }

  if (!capabilities) {
    return (
      <div role="alert" className="form-card border-rose-200 bg-rose-50">
        <p className="font-semibold text-rose-950">
          {error ?? "Ask RevenueOS is unavailable right now."}
        </p>
        <p className="mt-2 text-sm text-rose-800">
          Normal record Search is still available.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="form-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <label htmlFor="ask-revenueos-question" className="form-label">
              Ask RevenueOS
            </label>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Ask a sales question about what RevenueOS already knows. Every
              factual answer shows its authorised sources.
            </p>
          </div>
          <span className="rounded-full bg-teal-50 px-3 py-1.5 text-xs font-bold text-teal-900">
            About: {capabilities.scope.label}
          </span>
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <textarea
              id="ask-revenueos-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              className="form-input min-h-28 resize-y"
              placeholder="What is holding this deal back?"
              maxLength={capabilities.maxQuestionCharacters}
              aria-describedby="ask-boundary"
            />
          </div>
          <button
            type="submit"
            className="primary-button min-h-11"
            disabled={loading}
          >
            {loading ? "Checking RevenueOS…" : "Ask"}
          </button>
        </div>
        <p id="ask-boundary" className="mt-3 text-xs leading-5 text-slate-500">
          RevenueOS does not search the public web or perform actions from an
          answer.
        </p>
        {error ? (
          <div
            role="alert"
            className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
          >
            <p>{error}</p>
            {retryQuestion ? (
              <button
                type="button"
                disabled={loading}
                className="mt-3 font-bold underline underline-offset-4"
                onClick={() => void submitQuestion(retryQuestion)}
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
      </form>

      {!answer ? (
        <section aria-labelledby="ask-starters-title" className="form-card">
          <h2 id="ask-starters-title" className="form-legend">
            Useful questions to start with
          </h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {suggestedQuestions[scopeType].map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                disabled={loading}
                onClick={() => {
                  setQuestion(suggestion);
                  void submitQuestion(suggestion);
                }}
                className="min-h-11 rounded-full border border-slate-300 bg-white px-4 py-2 text-left text-sm font-semibold text-slate-700 hover:border-teal-500 hover:text-teal-900 focus:outline-none focus:ring-2 focus:ring-teal-600"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </section>
      ) : (
        <AskAnswerView
          ref={answerRef}
          titleId={answerTitleId}
          answer={answer}
          busy={loading}
          onFollowUp={(followUp) => {
            setQuestion(followUp);
            void submitQuestion(followUp);
            void recordTelemetry(answer.askRequestId, "follow_up_selected");
          }}
        />
      )}
    </div>
  );
}

const AskAnswerView = forwardRef<
  HTMLElement,
  {
    titleId: string;
    answer: AskAnswer;
    busy: boolean;
    onFollowUp: (question: string) => void;
  }
>(function AskAnswerView({ titleId, answer, busy, onFollowUp }, ref) {
  const sourceById = new Map(
    answer.sources.map((source) => [source.id, source]),
  );
  return (
    <section
      ref={ref}
      tabIndex={-1}
      aria-labelledby={titleId}
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm outline-none focus:ring-2 focus:ring-teal-600 sm:p-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            RevenueOS answer
          </p>
          <h2
            id={titleId}
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            {statusLabel(answer.answerStatus)}
          </h2>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700">
          About: {answer.scope.label}
        </span>
      </div>
      <p className="mt-5 max-w-3xl text-base leading-7 text-slate-800">
        {answer.answer}
      </p>

      {answer.summaryPoints.length ? (
        <div className="mt-7">
          <h3 className="font-semibold text-slate-950">
            Why RevenueOS believes it
          </h3>
          <ul className="mt-3 space-y-3">
            {answer.summaryPoints.map((point, index) => (
              <li
                key={`${point.text}-${index}`}
                className="text-sm leading-6 text-slate-700"
              >
                <span aria-hidden="true" className="mr-2 text-teal-700">
                  •
                </span>
                {point.text}{" "}
                {point.sourceIds
                  .map((sourceId) => sourceById.get(sourceId))
                  .filter((source) => source !== undefined)
                  .map((source) => (
                    <Link
                      key={source.id}
                      href={source.href}
                      onClick={() =>
                        void recordTelemetry(
                          answer.askRequestId,
                          "source_opened",
                          source.id,
                        )
                      }
                      className="ml-1 font-semibold text-teal-800 underline decoration-teal-300 underline-offset-4"
                    >
                      Source
                    </Link>
                  ))}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {answer.uncertainties.length ? (
        <div className="mt-7 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="font-semibold text-amber-950">Needs clarification</h3>
          <ul className="mt-2 space-y-2 text-sm leading-6 text-amber-900">
            {answer.uncertainties.map((uncertainty) => (
              <li key={uncertainty}>{uncertainty}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {answer.sources.length ? (
        <details className="mt-7 rounded-2xl border border-slate-200 p-4">
          <summary className="cursor-pointer font-semibold text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600">
            Sources ({answer.sources.length})
          </summary>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {answer.sources.map((source) => (
              <li key={source.id}>
                <Link
                  href={source.href}
                  onClick={() =>
                    void recordTelemetry(
                      answer.askRequestId,
                      "source_opened",
                      source.id,
                    )
                  }
                  className="block min-h-20 rounded-xl border border-slate-200 p-4 hover:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-600"
                >
                  <span className="block font-semibold text-slate-950">
                    {source.label}
                  </span>
                  <span className="mt-1 block text-xs font-semibold text-teal-800">
                    {provenanceLabel(source.provenance)}
                  </span>
                  {source.excerpt ? (
                    <span className="mt-2 block text-sm leading-5 text-slate-600">
                      {source.excerpt}
                    </span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {answer.suggestedAction ? (
        <div className="mt-7 border-t border-slate-100 pt-5">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
            Next step
          </p>
          <Link
            href={answer.suggestedAction.href}
            className="secondary-button mt-3"
          >
            {answer.suggestedAction.label}
          </Link>
        </div>
      ) : null}

      {answer.followUpQuestions.length ? (
        <div className="mt-7">
          <p className="text-sm font-semibold text-slate-950">
            Ask a follow-up
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {answer.followUpQuestions.map((followUp) => (
              <button
                key={followUp}
                type="button"
                disabled={busy}
                onClick={() => onFollowUp(followUp)}
                className="min-h-11 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-600"
              >
                {followUp}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
});

function statusLabel(status: AskAnswer["answerStatus"]) {
  return {
    supported: "Supported by current evidence",
    partially_supported: "Partially supported",
    conflicting: "Conflicting evidence",
    unknown: "Not enough reliable evidence",
  }[status];
}

function provenanceLabel(
  provenance: AskAnswer["sources"][number]["provenance"],
) {
  return {
    customer_direct: "Customer-direct",
    salesperson_reported: "Reported by salesperson",
    seller_prepared: "Seller-prepared context",
    imported_external: "Imported evidence",
    validated_intelligence: "Validated RevenueOS intelligence",
    system_metadata: "RevenueOS record",
  }[provenance];
}

async function recordTelemetry(
  askRequestId: string,
  eventType: "source_opened" | "follow_up_selected",
  sourceId?: string,
) {
  try {
    await apiRequest<void>("/api/v1/ask/telemetry", {
      method: "POST",
      body: JSON.stringify({
        eventType,
        askRequestId,
        ...(sourceId ? { sourceId } : {}),
      }),
    });
  } catch {
    // Product telemetry is best-effort and must never block the seller's task.
  }
}
