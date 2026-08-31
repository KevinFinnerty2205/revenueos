"use client";

import type {
  ActionExecution,
  ActionExecutionOptionListResponse,
  ContactOutreachWorkspace as ContactWorkspace,
  ExecutionPreview,
  OutreachMessage,
  OutreachPurpose,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const purposes: Array<{ value: OutreachPurpose; label: string }> = [
  { value: "introduction", label: "Introduce myself" },
  { value: "request_meeting", label: "Request a meeting" },
  {
    value: "share_relevant_information",
    label: "Share relevant information",
  },
  { value: "re_engage", label: "Re-engage" },
];

export function ContactOutreachWorkspace({ contactId }: { contactId: string }) {
  const [workspace, setWorkspace] = useState<ContactWorkspace | null>(null);
  const [outreach, setOutreach] = useState<OutreachMessage | null>(null);
  const [purpose, setPurpose] = useState<OutreachPurpose>("introduction");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [preview, setPreview] = useState<ExecutionPreview | null>(null);
  const [execution, setExecution] = useState<ActionExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    const result = await apiRequest<ContactWorkspace>(
      `/api/v1/engage/contacts/${contactId}`,
    );
    setWorkspace(result);
  }, [contactId]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ContactWorkspace>(`/api/v1/engage/contacts/${contactId}`, {
      signal: controller.signal,
    })
      .then(setWorkspace)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The Contact workspace could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [contactId]);

  function applyOutreach(next: OutreachMessage) {
    setOutreach(next);
    setSubject(next.version.subject);
    setBody(next.version.body);
    setPreview(null);
    setExecution(null);
  }

  async function createOutreach() {
    setBusy("create");
    setError(null);
    setNotice(null);
    try {
      const created = await apiRequest<OutreachMessage>(
        `/api/v1/engage/contacts/${contactId}/outreach`,
        { method: "POST", body: JSON.stringify({ purpose }) },
      );
      applyOutreach(created);
      setNotice(
        created.version.personalizationUsed
          ? "Draft created from approved seller context and cited professional research."
          : "Draft created without a personalised research hook because no reliable hook was available.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The outreach draft could not be created.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function openOutreach(outreachId: string) {
    setBusy("open");
    setError(null);
    setNotice(null);
    try {
      const existing = await apiRequest<OutreachMessage>(
        `/api/v1/engage/outreach/${outreachId}`,
      );
      applyOutreach(existing);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The outreach message could not be opened.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!outreach) return;
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      const edited = await apiRequest<OutreachMessage>(
        `/api/v1/engage/outreach/${outreach.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expectedVersion: outreach.currentVersion,
            subject,
            body,
          }),
        },
      );
      applyOutreach(edited);
      setNotice(
        "Your changes were saved as a new version. Review is required again.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The outreach changes could not be saved.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function approveOutreach() {
    if (!outreach) return;
    setBusy("approve");
    setError(null);
    setNotice(null);
    try {
      const approved = await apiRequest<OutreachMessage>(
        `/api/v1/engage/outreach/${outreach.id}/approve`,
        {
          method: "POST",
          body: JSON.stringify({ expectedVersion: outreach.currentVersion }),
        },
      );
      applyOutreach(approved);
      setNotice(
        "Current version approved. Nothing has been sent; review the exact execution preview next.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The outreach could not be approved.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function preparePreview() {
    if (!outreach) return;
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      const options = await apiRequest<ActionExecutionOptionListResponse>(
        `/api/v1/actions/${outreach.actionId}/execution-options`,
      );
      const option = options.items[0];
      if (!option) {
        throw new Error(
          "No sender-bound mailbox is available. Production mailbox sending is not enabled in this release.",
        );
      }
      const result = await apiRequest<ExecutionPreview>(
        `/api/v1/engage/outreach/${outreach.id}/execution-preview`,
        {
          method: "POST",
          body: JSON.stringify({ connectionId: option.connectionId }),
        },
      );
      setPreview(result);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The exact send preview could not be prepared.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function confirmPreview() {
    if (!outreach || !preview) return;
    setBusy("send");
    setError(null);
    setNotice(null);
    try {
      const result = await apiRequest<ActionExecution>(
        `/api/v1/engage/outreach/${outreach.id}/send`,
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
      setNotice(result.safeMessage);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The reviewed email could not be submitted.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function refreshExecution() {
    if (!execution || !outreach) return;
    setBusy("refresh");
    setError(null);
    try {
      const result = await apiRequest<ActionExecution>(
        `/api/v1/executions/${execution.id}`,
      );
      setExecution(result);
      setNotice(result.safeMessage);
      const refreshed = await apiRequest<OutreachMessage>(
        `/api/v1/engage/outreach/${outreach.id}`,
      );
      setOutreach(refreshed);
      await loadWorkspace();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The email status could not be refreshed.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function suppressContact() {
    if (!workspace) return;
    setBusy("suppress");
    setError(null);
    setNotice(null);
    try {
      await apiRequest(`/api/v1/engage/contacts/${contactId}/suppression`, {
        method: "POST",
        body: JSON.stringify({ reason: "manual_do_not_contact" }),
      });
      await loadWorkspace();
      if (outreach) {
        const refreshed = await apiRequest<OutreachMessage>(
          `/api/v1/engage/outreach/${outreach.id}`,
        );
        setOutreach(refreshed);
      }
      setPreview(null);
      setNotice(
        "Contact marked Do not contact. Approval and sending are now blocked.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Contact could not be suppressed.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <p
        role="status"
        className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600"
      >
        Loading Contact outreach…
      </p>
    );
  }

  if (!workspace) {
    return (
      <section className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
        <h2 className="text-xl font-semibold text-rose-950">
          Contact unavailable
        </h2>
        <p role="alert" className="mt-2 text-sm text-rose-900">
          {error ?? "The Contact workspace could not be loaded."}
        </p>
        <Link href="/contacts" className="secondary-button mt-4">
          Return to Contacts
        </Link>
      </section>
    );
  }

  const emailPreview =
    preview?.content.kind === "email" ? preview.content : null;
  const canDraft =
    workspace.availability.enabled &&
    workspace.email !== null &&
    workspace.emailTrust !== "unknown" &&
    workspace.policyConfigured;

  return (
    <div className="space-y-7">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Contact
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
            Contact and outreach
          </h2>
          <p className="mt-3 text-base text-slate-600">
            {workspace.jobTitle ? `${workspace.jobTitle} · ` : ""}
            <Link
              href={`/companies/${workspace.companyId}`}
              className="font-semibold text-teal-700"
            >
              {workspace.companyName}
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/contacts/${contactId}/edit`}
            className="secondary-button"
          >
            Edit Contact
          </Link>
          <Link href="/contacts" className="secondary-button">
            All Contacts
          </Link>
        </div>
      </header>

      {error ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-950"
        >
          {notice}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.55fr)]">
        <aside className="space-y-5">
          <section className="form-card" aria-labelledby="contactability-title">
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
              Business contact
            </p>
            <h2 id="contactability-title" className="form-legend mt-2">
              Contactability
            </h2>
            <dl className="mt-5 space-y-4 text-sm">
              <Detail
                label="Business email"
                value={workspace.email ?? "Not established"}
              />
              <Detail
                label="Address trust"
                value={humanise(workspace.emailTrust)}
              />
              <Detail
                label="Permission"
                value={
                  workspace.permissionStatus ===
                  "assessed_by_organisation_policy"
                    ? "Assessed separately by organisation policy"
                    : "Not assessed"
                }
              />
            </dl>
            <div
              className={`mt-5 rounded-xl border p-4 text-sm ${workspace.contactability.allowed ? "border-teal-200 bg-teal-50 text-teal-950" : "border-amber-200 bg-amber-50 text-amber-950"}`}
            >
              <p className="font-bold">
                {workspace.contactability.allowed
                  ? "Ready for review"
                  : humanise(workspace.contactability.state)}
              </p>
              <p className="mt-1 leading-6">
                {workspace.contactability.reason}
              </p>
            </div>
            {workspace.availability.enabled ? (
              <button
                type="button"
                disabled={
                  busy !== null ||
                  workspace.contactability.state === "suppressed" ||
                  workspace.email === null
                }
                onClick={() => void suppressContact()}
                className="secondary-button mt-4 w-full"
              >
                {busy === "suppress" ? "Saving…" : "Mark Do not contact"}
              </button>
            ) : null}
          </section>

          <OutreachHistory
            items={workspace.history}
            busy={busy !== null}
            onOpen={(outreachId) => void openOutreach(outreachId)}
          />
        </aside>

        <main>
          {!workspace.availability.enabled ? (
            <section
              className="form-card"
              aria-labelledby="engage-unavailable-title"
            >
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-teal-700">
                RevenueOS Engage
              </p>
              <h2 id="engage-unavailable-title" className="form-legend mt-2">
                Personalised outreach is not enabled
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {workspace.availability.message}
              </p>
              {workspace.availability.canManage ? (
                <Link href="/settings" className="primary-button mt-5">
                  Review Engage settings
                </Link>
              ) : null}
            </section>
          ) : !outreach ? (
            <section className="form-card" aria-labelledby="new-outreach-title">
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-teal-700">
                One-to-one email
              </p>
              <h2 id="new-outreach-title" className="form-legend mt-2">
                Create personalised outreach
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                RevenueOS uses only approved seller context and eligible cited
                professional research. You review every word before any
                execution step.
              </p>
              <label
                htmlFor="outreach-purpose"
                className="mt-6 block text-sm font-bold text-slate-800"
              >
                Purpose
              </label>
              <select
                id="outreach-purpose"
                value={purpose}
                onChange={(event) =>
                  setPurpose(event.target.value as OutreachPurpose)
                }
                className="form-control mt-2 w-full"
              >
                {purposes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="primary-button mt-5"
                disabled={!canDraft || busy !== null}
                onClick={() => void createOutreach()}
              >
                {busy === "create"
                  ? "Creating draft…"
                  : "Create outreach draft"}
              </button>
              {!canDraft ? (
                <p className="mt-3 text-sm text-amber-900">
                  A sendable business email, clear address trust and an
                  administrator-approved offering are required.
                </p>
              ) : null}
            </section>
          ) : (
            <OutreachEditor
              outreach={outreach}
              subject={subject}
              body={body}
              preview={preview}
              execution={execution}
              emailPreview={emailPreview}
              busy={busy}
              onSubject={setSubject}
              onBody={setBody}
              onSave={saveEdit}
              onApprove={() => void approveOutreach()}
              onPreview={() => void preparePreview()}
              onConfirm={() => void confirmPreview()}
              onRefresh={() => void refreshExecution()}
              onCancelPreview={() => {
                setPreview(null);
                setExecution(null);
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function OutreachEditor({
  outreach,
  subject,
  body,
  preview,
  execution,
  emailPreview,
  busy,
  onSubject,
  onBody,
  onSave,
  onApprove,
  onPreview,
  onConfirm,
  onRefresh,
  onCancelPreview,
}: {
  outreach: OutreachMessage;
  subject: string;
  body: string;
  preview: ExecutionPreview | null;
  execution: ActionExecution | null;
  emailPreview: Extract<ExecutionPreview["content"], { kind: "email" }> | null;
  busy: string | null;
  onSubject: (value: string) => void;
  onBody: (value: string) => void;
  onSave: (event: FormEvent<HTMLFormElement>) => void;
  onApprove: () => void;
  onPreview: () => void;
  onConfirm: () => void;
  onRefresh: () => void;
  onCancelPreview: () => void;
}) {
  const hasUnsavedChanges =
    subject !== outreach.version.subject || body !== outreach.version.body;

  if (preview && emailPreview) {
    return (
      <section className="form-card" aria-labelledby="send-preview-title">
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
          <p className="text-xs font-bold uppercase tracking-[0.15em]">
            Simulation only
          </p>
          <p className="mt-1 text-sm">
            No external email will be sent by this connection.
          </p>
        </div>
        <h2 id="send-preview-title" className="form-legend mt-5">
          Review exact email
        </h2>
        <dl className="mt-5 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-slate-50 text-sm">
          <PreviewRow
            label="From"
            value={`${emailPreview.senderName ?? "Sender"} <${emailPreview.senderEmail ?? "Unavailable"}>`}
          />
          <PreviewRow
            label="To"
            value={`${emailPreview.recipientName ?? "Recipient"} <${emailPreview.recipient}>`}
          />
          <PreviewRow label="Subject" value={emailPreview.subject} />
        </dl>
        <div className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-5 text-sm leading-7 text-slate-800">
          {emailPreview.body}
        </div>
        {execution ? (
          <div
            className="mt-5 rounded-xl border border-teal-200 bg-teal-50 p-4"
            aria-live="polite"
          >
            <p className="font-bold text-teal-950">
              {humanise(execution.executionStatus)}
            </p>
            <p className="mt-1 text-sm text-teal-900">
              {execution.safeMessage}
            </p>
            {execution.executionStatus === "queued" ||
            execution.executionStatus === "executing" ? (
              <button
                type="button"
                className="secondary-button mt-4"
                disabled={busy !== null}
                onClick={onRefresh}
              >
                {busy === "refresh" ? "Refreshing…" : "Refresh status"}
              </button>
            ) : null}
          </div>
        ) : (
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              className="primary-button"
              disabled={busy !== null}
              onClick={onConfirm}
            >
              {busy === "send" ? "Submitting…" : "Run email simulation"}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={busy !== null}
              onClick={onCancelPreview}
            >
              Back to draft
            </button>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="form-card" aria-labelledby="outreach-editor-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-teal-700">
            {humanise(outreach.purpose)} · Version {outreach.currentVersion}
          </p>
          <h2 id="outreach-editor-title" className="form-legend mt-2">
            Review personalised email
          </h2>
        </div>
        <span
          className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${outreach.state === "approved" ? "bg-teal-100 text-teal-900" : "bg-slate-100 text-slate-700"}`}
        >
          {humanise(outreach.state)}
        </span>
      </div>
      {outreach.relationshipWarning ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          {outreach.relationshipWarning}
        </p>
      ) : null}
      <form onSubmit={onSave} className="mt-6 space-y-5">
        <div>
          <label
            htmlFor="outreach-subject"
            className="text-sm font-bold text-slate-800"
          >
            Subject
          </label>
          <input
            id="outreach-subject"
            value={subject}
            maxLength={200}
            required
            onChange={(event) => onSubject(event.target.value)}
            className="form-control mt-2 w-full"
          />
        </div>
        <div>
          <label
            htmlFor="outreach-body"
            className="text-sm font-bold text-slate-800"
          >
            Email body
          </label>
          <textarea
            id="outreach-body"
            value={body}
            maxLength={10000}
            required
            rows={14}
            onChange={(event) => onBody(event.target.value)}
            className="form-control mt-2 w-full resize-y py-3 leading-7"
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            className="secondary-button"
            disabled={busy !== null || !hasUnsavedChanges}
          >
            {busy === "save" ? "Saving…" : "Save as new version"}
          </button>
          {outreach.state !== "approved" ? (
            <button
              type="button"
              className="primary-button"
              disabled={
                busy !== null ||
                !outreach.contactability.allowed ||
                hasUnsavedChanges
              }
              onClick={onApprove}
            >
              {busy === "approve" ? "Approving…" : "Approve current version"}
            </button>
          ) : (
            <button
              type="button"
              className="primary-button"
              disabled={busy !== null || hasUnsavedChanges}
              onClick={onPreview}
            >
              {busy === "preview" ? "Preparing preview…" : "Review before send"}
            </button>
          )}
        </div>
        {hasUnsavedChanges ? (
          <p className="text-sm text-amber-900">
            Save your changes as a new version before approval or execution
            preview.
          </p>
        ) : null}
      </form>

      <details className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer font-bold text-slate-800">
          Why this message?
        </summary>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Address trust and outreach permission are separate. The copy below
          uses only the listed sources; user edits are clearly marked and
          require a new approval.
        </p>
        {!outreach.version.personalizationUsed ? (
          <p className="mt-3 rounded-lg bg-white p-3 text-sm font-semibold text-slate-700">
            No reliable personalised hook was available, so RevenueOS used a
            transparent role-and-company introduction.
          </p>
        ) : null}
        <ul className="mt-4 space-y-3">
          {outreach.version.sources.map((source) => (
            <li key={source.id} className="rounded-lg bg-white p-3 text-sm">
              <p className="font-semibold text-slate-900">{source.label}</p>
              <p className="mt-1 text-xs text-slate-500">
                {humanise(source.sourceType)} · {humanise(source.trustState)}
                {source.publisher ? ` · ${source.publisher}` : ""}
                {source.publishedAt
                  ? ` · ${new Date(source.publishedAt).toLocaleDateString("en-AU")}`
                  : ""}
              </p>
              {source.url ? (
                <a
                  className="mt-2 inline-flex font-semibold text-teal-700"
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open public source
                </a>
              ) : null}
            </li>
          ))}
        </ul>
        {outreach.version.warnings.map((warning) => (
          <p
            key={warning}
            className="mt-3 text-sm font-semibold text-amber-900"
          >
            {warning}
          </p>
        ))}
      </details>
      <p className="mt-5 text-xs leading-5 text-slate-500">
        Approval alone never sends email. Contactability, recipient, sender,
        current version and suppression are checked again at preview,
        confirmation and worker execution.
      </p>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-slate-950">{value}</dd>
    </div>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 p-3 sm:grid-cols-[5rem_1fr]">
      <dt className="font-bold text-slate-500">{label}</dt>
      <dd className="break-words text-slate-900">{value}</dd>
    </div>
  );
}

function OutreachHistory({
  items,
  busy,
  onOpen,
}: {
  items: ContactWorkspace["history"];
  busy: boolean;
  onOpen: (outreachId: string) => void;
}) {
  return (
    <section className="form-card" aria-labelledby="outreach-history-title">
      <h2 id="outreach-history-title" className="form-legend">
        Outreach history
      </h2>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">
          No outreach has been created for this Contact.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li
              key={item.id}
              className="rounded-xl border border-slate-200 p-3 text-sm"
            >
              <button
                type="button"
                className="text-left font-semibold text-teal-700 hover:text-teal-900 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
                disabled={busy}
                onClick={() => onOpen(item.id)}
              >
                {item.subject}
              </button>
              <p className="mt-1 text-xs text-slate-500">
                {humanise(item.status)} ·{" "}
                {new Date(item.createdAt).toLocaleDateString("en-AU")}
                {item.simulationOnly ? " · Simulation" : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
