"use client";

import type {
  ActionGenerationResponse,
  ActionListResponse,
  ActionPayload,
  ActionProposal,
  ActionRejectionReason,
  ActionStatus,
} from "@revenueos/shared";
import { FormEvent, useState } from "react";
import { apiRequest } from "@/lib/api";
import { ActionExecutionPanel } from "@/components/action-execution-panel";
import { humanise } from "@/lib/business-entities";

type ActionTab = "pending" | "approved" | "rejected";

const rejectionReasons: ActionRejectionReason[] = [
  "already_done",
  "incorrect",
  "not_relevant",
  "unsupported",
  "duplicate",
  "not_now",
  "other",
];

export function RecommendedActions({
  opportunityId,
  initialActions,
  initialError,
}: {
  opportunityId: string;
  initialActions: ActionProposal[];
  initialError?: string | null;
}) {
  const [actions, setActions] = useState(initialActions);
  const [tab, setTab] = useState<ActionTab>("pending");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(initialError ?? null);

  async function refresh() {
    const result = await apiRequest<ActionListResponse>(
      `/api/v1/opportunities/${opportunityId}/actions`,
    );
    setActions(result.items);
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<ActionGenerationResponse>(
        `/api/v1/opportunities/${opportunityId}/actions/generate`,
        { method: "POST" },
      );
      await refresh();
      setTab("pending");
      setMessage(
        result.createdCount > 0
          ? `${result.createdCount} next ${result.createdCount === 1 ? "action is" : "actions are"} prepared for review.`
          : "The current reviewed evidence produced no new actions.",
      );
    } catch (requestError: unknown) {
      setError(
        actionError(requestError, "Next actions could not be prepared."),
      );
    } finally {
      setGenerating(false);
    }
  }

  async function transition(
    action: ActionProposal,
    operation: "approve" | "reject" | "complete",
    reasonCode?: ActionRejectionReason,
  ) {
    setBusyId(action.id);
    setError(null);
    setMessage(null);
    try {
      await apiRequest<ActionProposal>(
        `/api/v1/actions/${action.id}/${operation}`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedVersion: action.currentVersion,
            ...(reasonCode ? { reasonCode } : {}),
          }),
        },
      );
      await refresh();
      setMessage(
        operation === "approve"
          ? "Action approved. Nothing was sent or updated."
          : operation === "reject"
            ? "Action rejected."
            : "Action marked complete from your confirmation.",
      );
    } catch (requestError: unknown) {
      setError(
        actionError(requestError, "The action review could not be saved."),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function saveEdit(
    action: ActionProposal,
    title: string,
    description: string,
    dueAt: string,
    payload: ActionPayload,
  ) {
    setBusyId(action.id);
    setError(null);
    setMessage(null);
    try {
      await apiRequest<ActionProposal>(`/api/v1/actions/${action.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: action.currentVersion,
          title,
          description,
          proposedDueAt: dueAt ? new Date(dueAt).toISOString() : null,
          proposedPayload: payload,
        }),
      });
      await refresh();
      setMessage("Your changes were saved for review.");
    } catch (requestError: unknown) {
      setError(actionError(requestError, "Your changes could not be saved."));
      throw requestError;
    } finally {
      setBusyId(null);
    }
  }

  const visible = actions.filter((action) => actionTab(action.status) === tab);

  return (
    <section
      id="recommended-actions"
      aria-labelledby="recommended-actions-title"
      className="form-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            RevenueOS suggestion
          </p>
          <h2 id="recommended-actions-title" className="form-legend mt-2">
            Next actions
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Prepared from reviewed customer evidence. You can edit, approve or
            reject each suggestion. Approval records your decision only—it does
            not send a message or update another system.
          </p>
        </div>
        <button
          type="button"
          className="primary-button"
          disabled={generating}
          onClick={() => void generate()}
        >
          {generating ? "Preparing…" : "Prepare next actions"}
        </button>
      </div>

      <div
        className="mt-5 flex flex-wrap gap-2"
        role="tablist"
        aria-label="Action status"
      >
        {(["pending", "approved", "rejected"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={
              tab === value
                ? "rounded-full bg-slate-950 px-4 py-2 text-sm font-bold text-white"
                : "rounded-full border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700"
            }
            onClick={() => setTab(value)}
          >
            {humanise(value)} (
            {
              actions.filter((action) => actionTab(action.status) === value)
                .length
            }
            )
          </button>
        ))}
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}

      {visible.length ? (
        <ul className="mt-5 grid gap-4">
          {visible.map((action) => (
            <li key={action.id}>
              <ActionCard
                action={action}
                busy={busyId === action.id}
                onSave={saveEdit}
                onApprove={(item) => transition(item, "approve")}
                onReject={(item, reason) => transition(item, "reject", reason)}
                onComplete={(item) => transition(item, "complete")}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-5 rounded-2xl border border-dashed border-slate-300 p-5 text-sm text-slate-600">
          {tab === "pending"
            ? "No actions are waiting for review. Prepare suggestions when reviewed evidence is available."
            : `No ${tab} actions.`}
        </p>
      )}
    </section>
  );
}

function ActionCard({
  action,
  busy,
  onSave,
  onApprove,
  onReject,
  onComplete,
}: {
  action: ActionProposal;
  busy: boolean;
  onSave: (
    action: ActionProposal,
    title: string,
    description: string,
    dueAt: string,
    payload: ActionPayload,
  ) => Promise<void>;
  onApprove: (action: ActionProposal) => Promise<void>;
  onReject: (
    action: ActionProposal,
    reason: ActionRejectionReason,
  ) => Promise<void>;
  onComplete: (action: ActionProposal) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(action.title);
  const [description, setDescription] = useState(action.description);
  const [dueAt, setDueAt] = useState(toLocalDateTime(action.proposedDueAt));
  const [reason, setReason] = useState<ActionRejectionReason>("not_relevant");
  const [subject, setSubject] = useState(
    action.proposedPayload.kind === "follow_up_email"
      ? action.proposedPayload.subject
      : "",
  );
  const [body, setBody] = useState(
    action.proposedPayload.kind === "follow_up_email"
      ? action.proposedPayload.body
      : "",
  );
  const pending = action.status === "proposed" || action.status === "edited";

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload =
      action.proposedPayload.kind === "follow_up_email"
        ? { ...action.proposedPayload, subject, body }
        : action.proposedPayload;
    await onSave(action, title, description, dueAt, payload);
    setEditing(false);
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
              {humanise(action.actionType)}
            </span>
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-900">
              {humanise(action.priority)} priority
            </span>
            {action.audience === "customer_facing" ? (
              <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-800">
                Customer-facing — review carefully
              </span>
            ) : null}
          </div>
          <h3 className="mt-3 text-lg font-bold text-slate-950">
            {action.title}
          </h3>
        </div>
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          {action.status === "approved"
            ? "Approved — not sent or updated"
            : action.status === "completed_manually"
              ? "Completed manually"
              : humanise(action.status)}
        </p>
      </div>

      {editing ? (
        <form
          className="mt-5 space-y-4"
          onSubmit={(event) => void submitEdit(event)}
        >
          <label className="block text-sm font-bold text-slate-800">
            Title
            <input
              className="form-control mt-2"
              required
              maxLength={240}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block text-sm font-bold text-slate-800">
            Description
            <textarea
              className="form-control mt-2 min-h-28"
              required
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label className="block text-sm font-bold text-slate-800">
            Proposed due date
            <input
              type="datetime-local"
              className="form-control mt-2"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
            />
          </label>
          {action.proposedPayload.kind === "follow_up_email" ? (
            <>
              <label className="block text-sm font-bold text-slate-800">
                Email subject
                <input
                  className="form-control mt-2"
                  required
                  maxLength={240}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </label>
              <label className="block text-sm font-bold text-slate-800">
                Email body
                <textarea
                  className="form-control mt-2 min-h-48"
                  required
                  maxLength={10000}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                />
              </label>
            </>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <button type="submit" className="primary-button" disabled={busy}>
              Save revision
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {action.description}
          </p>
          {action.proposedDueAt ? (
            <p className="mt-3 text-sm font-semibold text-slate-700">
              Proposed due{" "}
              {new Date(action.proposedDueAt).toLocaleString("en-AU")}
            </p>
          ) : null}
          {action.proposedPayload.kind === "follow_up_email" ? (
            <div className="mt-4 rounded-2xl bg-slate-50 p-4">
              <p className="text-sm font-bold text-slate-900">
                Draft: {action.proposedPayload.subject}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {action.proposedPayload.body}
              </p>
              <p className="mt-3 text-xs font-bold text-rose-800">
                Draft only — no recipient is treated as confirmed and no email
                can be sent here.
              </p>
            </div>
          ) : null}
          <details className="mt-4">
            <summary className="cursor-pointer text-sm font-bold text-slate-700">
              Why this was recommended
            </summary>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {action.provenanceSummary}
            </p>
            <ul className="mt-2 space-y-1 text-xs text-slate-500">
              {action.sourceRefs.map((source) => (
                <li key={`${source.sourceId}-${source.itemKey}`}>
                  {source.label} · {humanise(source.origin)}
                </li>
              ))}
            </ul>
          </details>
        </>
      )}

      {!editing && pending ? (
        <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => setEditing(true)}
          >
            Edit suggestion
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={busy}
            onClick={() => void onApprove(action)}
          >
            Approve action
          </button>
          <label className="text-sm font-bold text-slate-700">
            Rejection reason
            <select
              className="form-control mt-1"
              value={reason}
              onChange={(e) =>
                setReason(e.target.value as ActionRejectionReason)
              }
            >
              {rejectionReasons.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => void onReject(action, reason)}
          >
            Reject
          </button>
        </div>
      ) : null}

      {action.status === "approved" && action.audience === "internal" ? (
        <button
          type="button"
          className="secondary-button mt-5"
          disabled={busy}
          onClick={() => void onComplete(action)}
        >
          Mark complete manually
        </button>
      ) : null}
      {action.status === "approved" ? (
        <ActionExecutionPanel action={action} />
      ) : null}
    </article>
  );
}

function actionTab(status: ActionStatus): ActionTab | null {
  if (status === "proposed" || status === "edited") return "pending";
  if (status === "approved" || status === "completed_manually")
    return "approved";
  if (status === "rejected") return "rejected";
  return null;
}

function toLocalDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

function actionError(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
