"use client";

import type {
  MethodologyGenerationResponse,
  MethodologyHistoryResponse,
  MethodologyProjectionItem,
  MethodologyState,
  OpportunityMethodologyResponse,
} from "@revenueos/shared";
import { useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

type ReviewAction =
  "confirm_interpretation" | "clarify" | "mark_not_known" | "mark_incorrect";

interface ReviewResponse {
  reviewId: string;
  clarificationEvidenceId: string | null;
  methodology: OpportunityMethodologyResponse;
}

const STATE_STYLES: Record<MethodologyState, string> = {
  confirmed: "border-emerald-200 bg-emerald-50 text-emerald-900",
  partially_supported: "border-sky-200 bg-sky-50 text-sky-900",
  unknown: "border-slate-200 bg-slate-100 text-slate-800",
  conflicting: "border-rose-200 bg-rose-50 text-rose-900",
  stale: "border-amber-200 bg-amber-50 text-amber-950",
};

export function OpportunityMethodology({
  opportunityId,
  initialMethodology,
}: {
  opportunityId: string;
  initialMethodology: OpportunityMethodologyResponse;
}) {
  const [methodology, setMethodology] =
    useState<OpportunityMethodologyResponse>(initialMethodology);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [clarifyingField, setClarifyingField] = useState<string | null>(null);
  const [clarification, setClarification] = useState("");
  const [history, setHistory] = useState<MethodologyHistoryResponse | null>(
    null,
  );
  const [historyLoading, setHistoryLoading] = useState(false);

  const orderedItems = useMemo(() => {
    const items = methodology.projection?.items ?? [];
    return [...items].sort(
      (left, right) =>
        statePriority(left.state) - statePriority(right.state) ||
        Number(right.required) - Number(left.required),
    );
  }, [methodology.projection]);
  const visibleItems = showAll ? orderedItems : orderedItems.slice(0, 3);

  async function generate() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiRequest<MethodologyGenerationResponse>(
        `/api/v1/opportunities/${opportunityId}/methodology/generate`,
        { method: "POST" },
      );
      setMethodology(response);
      setHistory(null);
      setMessage(
        response.reused
          ? "The current evidence-backed view was already up to date."
          : "Methodology view refreshed from current validated evidence.",
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The methodology view could not be generated.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function review(fieldKey: string, action: ReviewAction) {
    if (!methodology.projectionId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiRequest<ReviewResponse>(
        `/api/v1/opportunities/${opportunityId}/methodology/${fieldKey}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedProjectionId: methodology.projectionId,
            action,
            clarification: action === "clarify" ? clarification : null,
            idempotencyKey: reviewKey(fieldKey, action),
          }),
        },
      );
      setMethodology(response.methodology);
      setClarifyingField(null);
      setClarification("");
      setMessage(
        action === "clarify"
          ? "Your clarification was saved as salesperson-reported evidence. Refresh to rebuild the view."
          : "Your review was recorded. Refresh to rebuild the evidence-backed view.",
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Your review could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory() {
    setHistoryLoading(true);
    setError(null);
    try {
      setHistory(
        await apiRequest<MethodologyHistoryResponse>(
          `/api/v1/opportunities/${opportunityId}/methodology/history`,
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Methodology history could not be loaded.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <section aria-labelledby="deal-methodology-title" className="form-card">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Deal · evidence view
          </p>
          <h2 id="deal-methodology-title" className="form-legend mt-2">
            Sales Methodology
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {methodology.definition
              ? `${methodology.definition.name} organises current validated evidence without scoring or blocking deal stages.`
              : methodology.safeMessage}
          </p>
        </div>
        {methodology.generationAvailable ? (
          <button
            type="button"
            className="primary-button shrink-0"
            disabled={busy}
            onClick={() => void generate()}
          >
            {busy
              ? "Refreshing…"
              : methodology.state === "not_generated"
                ? "Generate view"
                : "Refresh evidence"}
          </button>
        ) : null}
      </div>

      {methodology.state === "needs_refresh" ? (
        <p
          role="status"
          className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          {methodology.safeMessage} The previous view remains in history but its
          conclusions are hidden here.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm font-semibold text-teal-800">
          {message}
        </p>
      ) : null}

      {methodology.projection ? (
        <>
          <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StateCount
              label="Confirmed"
              value={methodology.projection.stateCounts.confirmed}
            />
            <StateCount
              label="Partial"
              value={methodology.projection.stateCounts.partiallySupported}
            />
            <StateCount
              label="Unknown"
              value={methodology.projection.stateCounts.unknown}
            />
            <StateCount
              label="Conflicting"
              value={methodology.projection.stateCounts.conflicting}
            />
            <StateCount
              label="Stale"
              value={methodology.projection.stateCounts.stale}
            />
          </dl>
          <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-950">
                Most important gaps and fields
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                View v{methodology.projection.projectionVersion} · definition v
                {methodology.projection.definitionVersion} ·{" "}
                {formatMeetingDate(methodology.projection.generatedAt)}
              </p>
            </div>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setShowAll((value) => !value)}
            >
              {showAll
                ? "Show priority fields"
                : `View all ${orderedItems.length} fields`}
            </button>
          </div>
          <ul className="mt-4 grid gap-4 lg:grid-cols-2">
            {visibleItems.map((item) => (
              <MethodologyItem
                key={item.fieldKey}
                item={item}
                busy={busy}
                clarifying={clarifyingField === item.fieldKey}
                clarification={clarification}
                onClarificationChange={setClarification}
                onStartClarification={() => {
                  setClarifyingField(item.fieldKey);
                  setClarification("");
                }}
                onCancelClarification={() => setClarifyingField(null)}
                onReview={(action) => void review(item.fieldKey, action)}
              />
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
          {methodology.safeMessage}
        </p>
      )}

      {methodology.projectionId ? (
        <details className="mt-6 border-t border-slate-200 pt-5">
          <summary className="cursor-pointer text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-600">
            Methodology history
          </summary>
          <button
            type="button"
            className="secondary-button mt-4"
            disabled={historyLoading}
            onClick={() => void loadHistory()}
          >
            {historyLoading ? "Loading history…" : "Load history"}
          </button>
          {history ? (
            <ol className="mt-4 space-y-2 text-sm text-slate-700">
              {history.items.map((item) => (
                <li
                  key={item.id}
                  className="rounded-xl border border-slate-200 p-3"
                >
                  <details>
                    <summary className="cursor-pointer font-semibold focus:outline-none focus:ring-2 focus:ring-teal-600">
                      {item.methodologyName} · view v{item.projectionVersion} ·{" "}
                      {formatMeetingDate(item.generatedAt)}
                      {item.id === history.currentProjectionId
                        ? " · current"
                        : " · historical"}
                    </summary>
                    <ul className="mt-3 space-y-2">
                      {item.projection.items.map((field) => (
                        <li
                          key={field.fieldKey}
                          className="rounded-lg bg-slate-50 p-3"
                        >
                          <span className="font-bold">{field.displayName}</span>{" "}
                          · {humanise(field.state)}
                          {field.conclusion ? (
                            <span className="mt-1 block">
                              {field.conclusion}
                            </span>
                          ) : null}
                          <span className="mt-1 block text-xs text-slate-500">
                            {field.sources.length} supporting source
                            {field.sources.length === 1 ? "" : "s"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              ))}
            </ol>
          ) : null}
        </details>
      ) : null}
    </section>
  );
}

function MethodologyItem({
  item,
  busy,
  clarifying,
  clarification,
  onClarificationChange,
  onStartClarification,
  onCancelClarification,
  onReview,
}: {
  item: MethodologyProjectionItem;
  busy: boolean;
  clarifying: boolean;
  clarification: string;
  onClarificationChange: (value: string) => void;
  onStartClarification: () => void;
  onCancelClarification: () => void;
  onReview: (action: ReviewAction) => void;
}) {
  return (
    <li className="rounded-2xl border border-slate-200 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-bold text-slate-950">{item.displayName}</h4>
          <p className="mt-1 text-xs text-slate-500">
            {item.required ? "Core field" : "Optional field"}
          </p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-bold ${STATE_STYLES[item.state]}`}
        >
          {humanise(item.state)}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">
        {item.conclusion ??
          "No current evidence supports a conclusion for this field."}
      </p>
      {item.suggestedQuestion ? (
        <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-800">
          <span className="font-bold">Suggested question:</span>{" "}
          {item.suggestedQuestion}
        </p>
      ) : null}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-bold text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600">
          Why this state · {item.sources.length} source
          {item.sources.length === 1 ? "" : "s"}
        </summary>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          {item.explanation}
        </p>
        {item.sources.length ? (
          <ul className="mt-3 space-y-2">
            {item.sources.map((source) => (
              <li
                key={`${source.sourceType}-${source.sourceId}-${source.itemKey}`}
                className="rounded-xl border border-slate-200 p-3 text-xs text-slate-700"
              >
                <span className="font-bold text-slate-900">{source.label}</span>
                <span className="block mt-1">
                  {humanise(source.origin)} · {source.sourceClassification} ·{" "}
                  {formatMeetingDate(source.supportedAt)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-600">
            No eligible final evidence is linked.
          </p>
        )}
      </details>
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-bold text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600">
          Review or correct
        </summary>
        <div
          className="mt-3 flex flex-wrap gap-2"
          aria-label={`Review ${item.displayName}`}
        >
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => onReview("confirm_interpretation")}
          >
            Confirm interpretation
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={onStartClarification}
          >
            Add clarification
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => onReview("mark_not_known")}
          >
            Mark not known
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => onReview("mark_incorrect")}
          >
            Mark incorrect
          </button>
        </div>
        {clarifying ? (
          <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50 p-4">
            <label
              className="block text-sm font-bold text-sky-950"
              htmlFor={`clarification-${item.fieldKey}`}
            >
              Salesperson-reported clarification
            </label>
            <p className="mt-1 text-xs text-sky-900">
              This preserves its origin and does not become customer-confirmed
              evidence.
            </p>
            <textarea
              id={`clarification-${item.fieldKey}`}
              className="form-control mt-3 min-h-28"
              maxLength={1000}
              value={clarification}
              onChange={(event) => onClarificationChange(event.target.value)}
            />
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="primary-button"
                disabled={busy || clarification.trim().length === 0}
                onClick={() => onReview("clarify")}
              >
                Save clarification
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={onCancelClarification}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}
      </details>
    </li>
  );
}

function StateCount({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-2xl font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

function statePriority(state: MethodologyState): number {
  return {
    conflicting: 0,
    stale: 1,
    unknown: 2,
    partially_supported: 3,
    confirmed: 4,
  }[state];
}

function reviewKey(fieldKey: string, action: ReviewAction): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}`;
  return `methodology-${fieldKey}-${action}-${random}`;
}
