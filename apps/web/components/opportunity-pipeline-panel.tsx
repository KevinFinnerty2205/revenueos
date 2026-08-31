"use client";

import type { OpportunityPipeline, PipelineStage } from "@revenueos/shared";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { notifyOpportunityChanged } from "@/lib/opportunity-events";

type CloseMode = "won" | "lost" | null;

export function OpportunityPipelinePanel({
  opportunityId,
}: {
  opportunityId: string;
}) {
  const [pipeline, setPipeline] = useState<OpportunityPipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [closeMode, setCloseMode] = useState<CloseMode>(null);
  const [reopening, setReopening] = useState(false);
  const [targetStageId, setTargetStageId] = useState("");
  const [actualCloseDate, setActualCloseDate] = useState(todayInput());
  const [outcomeReason, setOutcomeReason] = useState("");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      void apiRequest<OpportunityPipeline>(
        `/api/v1/opportunities/${opportunityId}/pipeline`,
        { signal: controller.signal },
      )
        .then((response) => {
          setPipeline(response);
          setTargetStageId(firstOpenStage(response)?.id ?? "");
          setError(null);
        })
        .catch((reason: unknown) => {
          if (reason instanceof DOMException && reason.name === "AbortError")
            return;
          setError(
            reason instanceof Error
              ? reason.message
              : "Pipeline state could not be loaded.",
          );
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [opportunityId, retryKey]);

  const openStages = useMemo(
    () =>
      pipeline?.availablePipelines.flatMap((definition) =>
        definition.stages
          .filter((stage) => stage.active && stage.stageType === "open")
          .map((stage) => ({ ...stage, pipelineName: definition.name })),
      ) ?? [],
    [pipeline],
  );

  async function move(target: string) {
    if (!pipeline || !target || target === pipeline.stage.id) return;
    await mutate(`/api/v1/opportunities/${opportunityId}/stage`, {
      targetStageId: target,
      expectedCurrentStageId: pipeline.stage.id,
      idempotencyKey: requestKey("move"),
    });
  }

  async function close(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pipeline || !closeMode) return;
    const saved = await mutate(
      `/api/v1/opportunities/${opportunityId}/close-${closeMode}`,
      {
        expectedCurrentStageId: pipeline.stage.id,
        actualCloseDate,
        outcomeReason:
          outcomeReason || (closeMode === "lost" ? "unknown" : null),
        outcomeNote: outcomeNote.trim() || null,
        idempotencyKey: requestKey(`close-${closeMode}`),
      },
    );
    if (saved) {
      setCloseMode(null);
      setOutcomeReason("");
      setOutcomeNote("");
    }
  }

  async function reopen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pipeline || !targetStageId) return;
    const saved = await mutate(
      `/api/v1/opportunities/${opportunityId}/reopen`,
      {
        targetStageId,
        expectedCurrentStageId: pipeline.stage.id,
        idempotencyKey: requestKey("reopen"),
      },
    );
    if (saved) setReopening(false);
  }

  async function mutate(path: string, body: Record<string, unknown>) {
    setSaving(true);
    setError(null);
    try {
      const response = await apiRequest<OpportunityPipeline>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setPipeline(response);
      setTargetStageId(firstOpenStage(response)?.id ?? "");
      notifyOpportunityChanged(opportunityId);
      return true;
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The pipeline change could not be saved.",
      );
      return false;
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="form-card" aria-label="Opportunity pipeline">
        <p role="status" className="text-sm text-slate-600">
          Loading opportunity stage…
        </p>
      </section>
    );
  }
  if (!pipeline) {
    return (
      <section className="form-card" aria-label="Opportunity pipeline">
        <p role="alert" className="text-sm text-rose-800">
          {error ?? "Pipeline state is unavailable."}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </section>
    );
  }

  const closed = pipeline.status === "won" || pipeline.status === "lost";
  return (
    <section className="form-card" aria-labelledby="opportunity-pipeline-title">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Deal workflow
          </p>
          <h2
            id="opportunity-pipeline-title"
            className="mt-2 text-xl font-semibold text-slate-950"
          >
            {pipeline.stage.name}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {pipeline.pipeline.name} · {timingLabel(pipeline)}
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Stage changes record workflow progress only. They do not confirm
            customer Evidence, Methodology or forecast likelihood.
          </p>
        </div>
        {!closed && pipeline.stageChangesAllowed ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="secondary-button"
              onClick={() => setCloseMode("won")}
            >
              Mark Won
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setCloseMode("lost")}
            >
              Mark Lost
            </button>
          </div>
        ) : null}
        {closed && pipeline.stageChangesAllowed ? (
          <button
            type="button"
            className="secondary-button"
            onClick={() => setReopening(true)}
          >
            Reopen opportunity
          </button>
        ) : null}
      </div>

      {pipeline.authorityMessage ? (
        <p className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950">
          {pipeline.authorityMessage}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}

      {!closed && pipeline.stageChangesAllowed ? (
        <label className="mt-5 block max-w-sm text-sm font-bold text-slate-700">
          Change stage
          <select
            className="form-control mt-2 w-full"
            value={pipeline.stage.id}
            disabled={saving}
            onChange={(event) => void move(event.target.value)}
          >
            {openStages.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.pipelineName} · {stage.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {closed ? (
        <dl className="mt-5 grid gap-3 rounded-2xl bg-slate-50 p-4 text-sm sm:grid-cols-3">
          <Value label="Outcome">
            {pipeline.status === "won" ? "Won" : "Lost"}
          </Value>
          <Value label="Actual close">
            {formatDate(pipeline.actualCloseDate)}
          </Value>
          <Value label="Reason">
            {pipeline.outcomeReason
              ? `${humanise(pipeline.outcomeReason)} · seller reported`
              : "Not recorded"}
          </Value>
        </dl>
      ) : null}

      <details className="mt-5 border-t border-slate-200 pt-5">
        <summary className="cursor-pointer font-semibold text-slate-950">
          Stage history
        </summary>
        <div className="mt-4 grid gap-3">
          {pipeline.history.map((event) => (
            <article
              key={event.id}
              className="rounded-xl border border-slate-200 p-3 text-sm"
            >
              <p className="font-semibold text-slate-950">
                {event.fromStageName ? `${event.fromStageName} → ` : "Entered "}
                {event.toStageName}
              </p>
              <p className="mt-1 text-slate-600">
                {formatDateTime(event.changedAt)}
                {event.changedByName ? ` · ${event.changedByName}` : ""}
              </p>
              {event.previousStageEnteredAt ? (
                <p className="mt-1 text-xs text-slate-500">
                  {previousStageDuration(
                    event.previousStageEnteredAt,
                    event.changedAt,
                  )}
                </p>
              ) : null}
              {event.isBaseline ? (
                <p className="mt-2 text-xs text-amber-800">
                  Earlier stage history is unavailable. Tracking began here; no
                  earlier duration was inferred.
                </p>
              ) : null}
              {event.outcomeReason ? (
                <p className="mt-2 text-xs text-slate-600">
                  Outcome: {humanise(event.outcomeReason)} · seller reported
                </p>
              ) : null}
              {event.actualCloseDate ? (
                <p className="mt-1 text-xs text-slate-600">
                  Actual close {formatDate(event.actualCloseDate)}
                  {event.finalAmount && event.finalCurrency
                    ? ` · ${formatCurrency(event.finalAmount, event.finalCurrency)}`
                    : ""}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </details>

      {closeMode ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="close-dialog-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <form
            onSubmit={(event) => void close(event)}
            className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-xl"
          >
            <h2
              id="close-dialog-title"
              className="text-2xl font-semibold text-slate-950"
            >
              Mark as {closeMode === "won" ? "Won" : "Lost"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              This closes the opportunity and preserves its expected close date
              and full stage history.
            </p>
            <label className="mt-5 block text-sm font-bold text-slate-700">
              Actual close date
              <input
                required
                max={todayInput()}
                type="date"
                className="form-control mt-2 w-full"
                value={actualCloseDate}
                onChange={(event) => setActualCloseDate(event.target.value)}
              />
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">
              {closeMode === "lost"
                ? "Why was this opportunity lost?"
                : "What helped us win? (optional)"}
              <select
                required={closeMode === "lost"}
                className="form-control mt-2 w-full"
                value={outcomeReason}
                onChange={(event) => setOutcomeReason(event.target.value)}
              >
                <option value="">
                  {closeMode === "lost" ? "Select a reason" : "Not recorded"}
                </option>
                {(closeMode === "lost" ? lossReasons : winReasons).map(
                  (reason) => (
                    <option key={reason} value={reason}>
                      {humanise(reason)}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">
              Internal outcome note (optional)
              <textarea
                maxLength={500}
                rows={3}
                className="form-control mt-2 w-full py-3"
                value={outcomeNote}
                onChange={(event) => setOutcomeNote(event.target.value)}
              />
            </label>
            <p className="mt-2 text-xs text-slate-500">
              Outcome reason and note are seller reported; they do not become
              customer Evidence.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setCloseMode(null)}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="primary-button"
              >
                {saving
                  ? "Saving…"
                  : closeMode === "won"
                    ? "Close Won"
                    : "Close Lost"}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {reopening ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="reopen-dialog-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <form
            onSubmit={(event) => void reopen(event)}
            className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-xl"
          >
            <h2
              id="reopen-dialog-title"
              className="text-2xl font-semibold text-slate-950"
            >
              Reopen opportunity
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Choose an open stage. The earlier closure remains in stage
              history.
            </p>
            <label className="mt-5 block text-sm font-bold text-slate-700">
              Open stage
              <select
                required
                className="form-control mt-2 w-full"
                value={targetStageId}
                onChange={(event) => setTargetStageId(event.target.value)}
              >
                {openStages.map((stage) => (
                  <option key={stage.id} value={stage.id}>
                    {stage.pipelineName} · {stage.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setReopening(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="primary-button"
              >
                {saving ? "Saving…" : "Reopen"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}

const lossReasons = [
  "price",
  "competitor",
  "no_decision",
  "budget",
  "timing",
  "requirements_fit",
  "procurement",
  "relationship",
  "other",
  "unknown",
] as const;
const winReasons = [
  "solution_fit",
  "commercial",
  "relationship",
  "implementation",
  "existing_customer",
  "other",
  "unknown",
] as const;

function firstOpenStage(value: OpportunityPipeline): PipelineStage | null {
  return (
    value.availablePipelines
      .flatMap((pipeline) => pipeline.stages)
      .find((stage) => stage.active && stage.stageType === "open") ?? null
  );
}

function timingLabel(value: OpportunityPipeline) {
  if (value.daysInStage !== null) return `${value.daysInStage} days in stage`;
  return value.stageTrackingStartedAt
    ? `tracking since ${formatDateTime(value.stageTrackingStartedAt)}`
    : "stage timing unavailable";
}

function Value({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-slate-900">{children}</dd>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function previousStageDuration(enteredAt: string, changedAt: string) {
  const elapsed = Math.max(
    0,
    new Date(changedAt).getTime() - new Date(enteredAt).getTime(),
  );
  const days = Math.floor(elapsed / 86_400_000);
  if (days === 0) return "Less than a day in the previous stage";
  return `${days} ${days === 1 ? "day" : "days"} in the previous stage`;
}

function formatCurrency(value: string, currency: string) {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function todayInput() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function requestKey(prefix: string) {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
  return `${prefix}:${suffix}`;
}
