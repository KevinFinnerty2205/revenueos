"use client";

import type {
  ActionExecution,
  ActionExecutionListResponse,
  ActionExecutionOptionListResponse,
  ActionProposal,
  ExecutionPreview,
  ExecutionPreviewContent,
} from "@revenueos/shared";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function ActionExecutionPanel({ action }: { action: ActionProposal }) {
  const [preview, setPreview] = useState<ExecutionPreview | null>(null);
  const [execution, setExecution] = useState<ActionExecution | null>(null);
  const [history, setHistory] = useState<ActionExecution[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reviewExecution() {
    setBusy(true);
    setError(null);
    try {
      const options = await apiRequest<ActionExecutionOptionListResponse>(
        `/api/v1/actions/${action.id}/execution-options`,
      );
      const option = options.items[0];
      if (!option) {
        throw new Error(
          "Ask an administrator to enable an authorised simulation connector for this Action.",
        );
      }
      const result = await apiRequest<ExecutionPreview>(
        `/api/v1/actions/${action.id}/execution-preview`,
        {
          method: "POST",
          body: JSON.stringify({ connectionId: option.connectionId }),
        },
      );
      setPreview(result);
      const previous = await apiRequest<ActionExecutionListResponse>(
        `/api/v1/actions/${action.id}/executions`,
      );
      setHistory(previous.items);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Execution preview could not be prepared.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmExecution() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<ActionExecution>(
        `/api/v1/actions/${action.id}/execute`,
        {
          method: "POST",
          body: JSON.stringify({
            previewId: preview.id,
            connectionId: preview.connectionId,
            confirmed: true,
          }),
        },
      );
      setExecution(result);
      setHistory((items) => [
        result,
        ...items.filter((item) => item.id !== result.id),
      ]);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The simulation could not be confirmed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function refreshExecution() {
    if (!execution) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<ActionExecution>(
        `/api/v1/executions/${execution.id}`,
      );
      setExecution(result);
      setHistory((items) => [
        result,
        ...items.filter((item) => item.id !== result.id),
      ]);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Simulation status could not be refreshed.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!preview) {
    return (
      <div className="mt-5 border-t border-slate-100 pt-4">
        <button
          type="button"
          className="primary-button"
          disabled={busy}
          onClick={() => void reviewExecution()}
        >
          {busy ? "Preparing preview…" : "Review execution"}
        </button>
        <p className="mt-2 text-xs font-bold text-amber-800">
          Simulation only — approval has not executed this Action.
        </p>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-900">
          Simulation — no external action will occur
        </p>
        <h4 className="mt-2 font-bold text-slate-950">
          {preview.connectorDisplayName}
        </h4>
        <p className="mt-1 text-sm text-slate-700">{preview.summary}</p>
        <PreviewContent content={preview.content} />
        {!execution ? (
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className="primary-button"
              disabled={busy}
              onClick={() => void confirmExecution()}
            >
              {busy ? "Confirming…" : preview.confirmationLabel}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => setPreview(null)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="mt-4 rounded-xl bg-white p-3" aria-live="polite">
            <p className="font-bold text-slate-900">
              {humanise(execution.executionStatus)}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {execution.safeMessage}
            </p>
            {execution.externalResultId ? (
              <p className="mt-2 break-all text-xs text-slate-500">
                Mock result ID: {execution.externalResultId}
              </p>
            ) : null}
            {execution.executionStatus === "queued" ||
            execution.executionStatus === "executing" ||
            execution.executionStatus === "failed_retryable" ? (
              <button
                type="button"
                className="secondary-button mt-3"
                disabled={busy}
                onClick={() => void refreshExecution()}
              >
                Refresh simulation status
              </button>
            ) : null}
          </div>
        )}
      </div>
      {history.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-bold text-slate-700">
            Execution history ({history.length})
          </summary>
          <ul className="mt-2 space-y-2 text-sm text-slate-600">
            {history.map((item) => (
              <li key={item.id}>
                {humanise(item.executionStatus)} · {item.connectorDisplayName} ·{" "}
                {new Date(item.confirmedAt).toLocaleString("en-AU")}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PreviewContent({ content }: { content: ExecutionPreviewContent }) {
  if (content.kind === "email") {
    return (
      <dl className="mt-4 grid gap-2 text-sm">
        <PreviewRow label="To" value={content.recipient} />
        <PreviewRow label="Subject" value={content.subject} />
        <PreviewRow label="Body" value={content.body} preserveWhitespace />
      </dl>
    );
  }
  if (content.kind === "calendar") {
    return (
      <dl className="mt-4 grid gap-2 text-sm">
        <PreviewRow label="Event" value={content.event} />
        <PreviewRow
          label="Time"
          value={new Date(content.scheduledAt).toLocaleString("en-AU")}
        />
        <PreviewRow label="Timezone" value={content.timezone} />
        <PreviewRow
          label="Participants"
          value={content.participants
            .map(
              (participant) =>
                `${participant.displayName} <${participant.email}>`,
            )
            .join(", ")}
        />
        <PreviewRow label="Purpose" value={content.purpose} />
      </dl>
    );
  }
  if (content.kind === "crm") {
    return (
      <dl className="mt-4 grid gap-2 text-sm">
        <PreviewRow label="Field" value={humanise(content.field)} />
        <PreviewRow
          label="Current"
          value={displayValue(content.currentExternalValue)}
        />
        <PreviewRow label="New" value={displayValue(content.newValue)} />
      </dl>
    );
  }
  return (
    <dl className="mt-4 grid gap-2 text-sm">
      <PreviewRow label="Create" value={content.title} />
      <PreviewRow
        label="Due"
        value={
          content.dueAt
            ? new Date(content.dueAt).toLocaleString("en-AU")
            : "No due date"
        }
      />
      <PreviewRow label="Context" value={content.context} />
    </dl>
  );
}

function PreviewRow({
  label,
  value,
  preserveWhitespace = false,
}: {
  label: string;
  value: string;
  preserveWhitespace?: boolean;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[7rem_1fr]">
      <dt className="font-bold text-slate-700">{label}</dt>
      <dd
        className={
          preserveWhitespace
            ? "whitespace-pre-wrap text-slate-900"
            : "text-slate-900"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function displayValue(value: string | number | null): string {
  if (value === null) return "Not set";
  return String(value);
}
