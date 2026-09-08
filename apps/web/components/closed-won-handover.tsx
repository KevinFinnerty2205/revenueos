"use client";

import type {
  HandoverContent,
  HandoverItem,
  HandoverRevision,
  HandoverSectionKey,
  HandoverSource,
  HandoverWorkspace,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const sections: Array<{
  key: HandoverSectionKey;
  label: string;
  help: string;
}> = [
  {
    key: "executiveSummary",
    label: "Executive summary",
    help: "A short, factual transition overview.",
  },
  {
    key: "customerObjectives",
    label: "Customer objectives",
    help: "Outcomes the customer directly stated or the seller confirmed.",
  },
  {
    key: "whyTheyBought",
    label: "Why they bought",
    help: "Use reviewed evidence; do not promote buying-signal inference to fact.",
  },
  {
    key: "commercialScope",
    label: "Commercial scope",
    help: "Canonical commercial records and reviewed customer-facing scope only.",
  },
  {
    key: "keyStakeholders",
    label: "Key stakeholders",
    help: "Named people and roles relevant to delivery and success.",
  },
  {
    key: "commitments",
    label: "Commitments",
    help: "Only customer evidence, commercial records, approved customer context or seller confirmation.",
  },
  {
    key: "successCriteria",
    label: "Success criteria",
    help: "The measures the customer and delivery team should use.",
  },
  {
    key: "implementationExpectations",
    label: "Implementation expectations",
    help: "High-risk claims must have explicit human or authoritative support.",
  },
  {
    key: "risks",
    label: "Risks",
    help: "Keep observed risks and seller concerns distinct from inference.",
  },
  {
    key: "openItems",
    label: "Open items",
    help: "Unresolved decisions, questions and dependencies.",
  },
  {
    key: "timeline",
    label: "Timeline",
    help: "Pinned milestones and canonical close dates.",
  },
  {
    key: "nextActions",
    label: "Next actions",
    help: "Owned transition work with a due date and status where known.",
  },
];

const authorityLabels = {
  customer_evidence: "Customer Evidence",
  seller_confirmed: "Seller confirmed",
  commercial_record: "Commercial record",
  customer_facing_approved: "Customer-facing approved",
  system_derived: "System-derived",
  inference: "Inference — review required",
  unknown: "Unknown — review required",
} as const;

function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function newItem(key: HandoverSectionKey): HandoverItem {
  return {
    id:
      globalThis.crypto?.randomUUID?.() ??
      `handover-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    text: "New handover item",
    authorityType: "unknown",
    sourceIds: [],
    confirmedByUserId: null,
    confirmedAt: null,
    owner: null,
    dueDate: null,
    actionStatus: key === "nextActions" ? "open" : null,
    riskKind: key === "risks" ? "system_inference" : null,
  };
}

function sourceLabel(source: HandoverSource): string {
  const revision = source.sourceVersion
    ? ` · revision ${source.sourceVersion}`
    : "";
  return `${source.label}${revision}`;
}

function StatusBadge({ status }: { status: HandoverRevision["status"] }) {
  const label = status.replaceAll("_", " ");
  const tone =
    status === "approved"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : status === "in_review"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : status === "retired" || status === "superseded"
          ? "border-slate-200 bg-slate-100 text-slate-700"
          : "border-sky-200 bg-sky-50 text-sky-800";
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold capitalize ${tone}`}
    >
      {label}
    </span>
  );
}

function AuthorityBadge({ item }: { item: HandoverItem }) {
  const warning =
    item.authorityType === "inference" || item.authorityType === "unknown";
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${
        warning
          ? "border-amber-300 bg-amber-50 text-amber-900"
          : "border-slate-200 bg-white text-slate-700"
      }`}
    >
      {authorityLabels[item.authorityType]}
    </span>
  );
}

function SourceBadges({
  item,
  sources,
}: {
  item: HandoverItem;
  sources: HandoverSource[];
}) {
  const cited = item.sourceIds
    .map((sourceId) => sources.find((source) => source.id === sourceId))
    .filter((source): source is HandoverSource => source !== undefined);
  if (cited.length === 0) {
    return <span className="text-xs text-slate-500">No pinned source</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Pinned sources">
      {cited.map((source) => (
        <span
          key={source.id}
          title={sourceLabel(source)}
          className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700"
        >
          {source.sourceType.replaceAll("_", " ")}
          {source.sourceVersion ? ` v${source.sourceVersion}` : ""}
        </span>
      ))}
    </div>
  );
}

export function ClosedWonHandover({
  opportunityId,
}: {
  opportunityId: string;
}) {
  const [workspace, setWorkspace] = useState<HandoverWorkspace | null>(null);
  const [content, setContent] = useState<HandoverContent | null>(null);
  const [viewing, setViewing] = useState<HandoverRevision | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<HandoverWorkspace>(
      `/api/v1/opportunities/${opportunityId}/handover`,
      { signal: controller.signal },
    )
      .then((response) => {
        if (!Array.isArray(response.history)) {
          throw new Error(
            "The Closed-Won Handover service returned an invalid response.",
          );
        }
        setWorkspace(response);
        setContent(response.activeRevision?.content ?? null);
        setViewing(null);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The Closed-Won Handover could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [opportunityId]);

  function applyWorkspace(next: HandoverWorkspace, success: string): void {
    setWorkspace(next);
    setContent(next.activeRevision?.content ?? null);
    setViewing(null);
    setConfirmed(false);
    setMessage(success);
    setError(null);
  }

  async function prepare(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<HandoverWorkspace>(
        `/api/v1/opportunities/${opportunityId}/handover/prepare`,
        { method: "POST" },
      );
      applyWorkspace(
        next,
        "Handover draft prepared from the bounded, pinned source pack. No AI drafting was used.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The handover draft could not be prepared.",
      );
    } finally {
      setBusy(false);
    }
  }

  function updateItem(
    section: HandoverSectionKey,
    itemId: string,
    update: Partial<HandoverItem>,
  ): void {
    if (!content) return;
    setContent({
      ...content,
      [section]: content[section].map((item) =>
        item.id === itemId ? { ...item, ...update } : item,
      ),
    });
  }

  function addItem(section: HandoverSectionKey): void {
    if (!content) return;
    setContent({
      ...content,
      [section]: [...content[section], newItem(section)],
    });
  }

  function removeItem(section: HandoverSectionKey, itemId: string): void {
    if (!content) return;
    setContent({
      ...content,
      [section]: content[section].filter((item) => item.id !== itemId),
    });
  }

  async function save(): Promise<void> {
    const revision = workspace?.activeRevision;
    if (!workspace || !revision || !content) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<HandoverWorkspace>(
        `/api/v1/opportunities/${opportunityId}/handover/revisions/${revision.id}/draft`,
        {
          method: "PUT",
          body: JSON.stringify({
            expectedHandoverVersion: workspace.handoverLockVersion,
            expectedRevisionVersion: revision.lockVersion,
            content,
          }),
        },
      );
      applyWorkspace(
        next,
        "Draft saved. Changed claims are now recorded as seller confirmed with your identity and timestamp.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The draft could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function lifecycle(
    action: "submit" | "refresh-sources" | "approve" | "retire",
  ): Promise<void> {
    const revision = workspace?.activeRevision;
    if (!workspace || !revision || !confirmed) return;
    setBusy(true);
    setError(null);
    const success = {
      submit: "Handover submitted for administrator review.",
      "refresh-sources":
        "Pinned sources refreshed. Review the draft again before submission.",
      approve:
        "Handover approved as the current immutable Closed-Won revision.",
      retire: "The current approved handover has been retired.",
    }[action];
    try {
      const next = await apiRequest<HandoverWorkspace>(
        `/api/v1/opportunities/${opportunityId}/handover/revisions/${revision.id}/${action}`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedHandoverVersion: workspace.handoverLockVersion,
            expectedRevisionVersion: revision.lockVersion,
            confirmed: true,
          }),
        },
      );
      applyWorkspace(next, success);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The handover lifecycle change could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmClaim(itemId: string): Promise<void> {
    const revision = workspace?.activeRevision;
    if (!workspace || !revision) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<HandoverWorkspace>(
        `/api/v1/opportunities/${opportunityId}/handover/revisions/${revision.id}/confirm-claim`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedHandoverVersion: workspace.handoverLockVersion,
            expectedRevisionVersion: revision.lockVersion,
            confirmed: true,
            itemId,
          }),
        },
      );
      applyWorkspace(next, "Claim recorded as seller confirmed.");
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The claim could not be confirmed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function showRevision(revisionId: string): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const revision = await apiRequest<HandoverRevision>(
        `/api/v1/opportunities/${opportunityId}/handover/revisions/${revisionId}`,
      );
      setViewing(revision);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The historical revision could not be loaded.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="form-card" role="status">
        Loading Closed-Won Handover…
      </section>
    );
  }

  if (!workspace) {
    return (
      <section className="form-card" aria-labelledby="handover-title">
        <h2 id="handover-title" className="form-legend">
          Closed-Won Handover
        </h2>
        <p className="mt-3 text-sm text-rose-800" role="alert">
          {error ?? "The Closed-Won Handover could not be loaded."}
        </p>
      </section>
    );
  }

  if (!workspace.activeRevision || !content) {
    return (
      <section
        id="closed-won-handover"
        aria-labelledby="handover-title"
        className="rounded-3xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm sm:p-8"
      >
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-700">
          Reviewed transition
        </p>
        <h2
          id="handover-title"
          className="mt-2 text-2xl font-semibold text-indigo-950"
        >
          Prepare a Closed-Won Handover
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-indigo-950">
          Build an internal, source-pinned handover while the Opportunity is
          open or Closed Won. RevenueOS uses deterministic extraction only: it
          does not call an AI provider or treat inferred intelligence as
          customer fact.
        </p>
        {workspace.currentApprovedRevision ? (
          <p className="mt-3 text-sm font-semibold text-slate-700">
            Revision {workspace.currentApprovedRevision.revision} is retained as{" "}
            {workspace.currentApprovedRevision.status}. Prepare a new draft to
            make a reviewed correction.
          </p>
        ) : null}
        {error ? (
          <p className="mt-3 text-sm text-rose-800" role="alert">
            {error}
          </p>
        ) : null}
        {workspace.canManage &&
        ["open", "won"].includes(workspace.opportunityStatus) ? (
          <button
            className="primary-button mt-5"
            type="button"
            disabled={busy}
            onClick={() => void prepare()}
          >
            {busy
              ? "Preparing…"
              : workspace.handoverId
                ? "Prepare new revision"
                : "Prepare handover draft"}
          </button>
        ) : (
          <p className="mt-4 text-sm font-semibold text-indigo-900">
            No current approved handover is available to you.
          </p>
        )}
        <p className="mt-3 text-xs font-semibold text-indigo-800">
          Included with Create · No Credits required · No AI drafting
        </p>
        {workspace.history.length > 0 ? (
          <History
            history={workspace.history}
            busy={busy}
            onSelect={(id) => void showRevision(id)}
          />
        ) : null}
      </section>
    );
  }

  const active = workspace.activeRevision;
  const displayed = viewing ?? active;
  const editable =
    !viewing &&
    workspace.canManage &&
    ["draft", "in_review"].includes(active.status);
  const dirty =
    !viewing && JSON.stringify(content) !== JSON.stringify(active.content);
  const isReview = !viewing && active.status === "in_review";

  return (
    <section
      id="closed-won-handover"
      aria-labelledby="handover-title"
      className="form-card scroll-mt-6"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-700">
            Reviewed transition
          </p>
          <h2
            id="handover-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            Closed-Won Handover · revision {displayed.revision}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">
            Internal handover assembled from exact, pinned source versions. An
            authority badge on each claim shows whether it is customer evidence,
            a commercial record, approved customer context, seller confirmation,
            system-derived context or unresolved inference.
          </p>
        </div>
        <StatusBadge status={displayed.status} />
      </div>

      {message ? (
        <p
          className="mt-4 text-sm font-semibold text-emerald-800"
          role="status"
        >
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm font-semibold text-rose-800" role="alert">
          {error}
        </p>
      ) : null}

      {!viewing && active.approvalBlockers.length > 0 ? (
        <aside
          className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4"
          aria-labelledby="handover-blockers-title"
        >
          <h3
            id="handover-blockers-title"
            className="font-semibold text-amber-950"
          >
            Review required before approval
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-950">
            {active.approvalBlockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </aside>
      ) : null}

      <div className="mt-7 space-y-7">
        {sections.map((section) => {
          const items = displayed.content[section.key];
          return (
            <fieldset
              key={section.key}
              className="rounded-2xl border border-slate-200 p-4 sm:p-5"
            >
              <legend className="px-1 text-lg font-semibold text-slate-950">
                {section.label}
              </legend>
              <p className="mb-4 text-sm text-slate-600">{section.help}</p>
              {items.length === 0 ? (
                <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">
                  Nothing recorded.
                </p>
              ) : (
                <div className="space-y-4">
                  {items.map((item, index) => (
                    <article
                      key={item.id}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                    >
                      {editable ? (
                        <label className="block text-sm font-semibold text-slate-800">
                          {section.label} item {index + 1}
                          <textarea
                            className="form-input mt-2 min-h-24 w-full"
                            maxLength={2000}
                            value={
                              content[section.key].find(
                                (candidate) => candidate.id === item.id,
                              )?.text ?? item.text
                            }
                            onChange={(event) =>
                              updateItem(section.key, item.id, {
                                text: event.target.value,
                              })
                            }
                          />
                        </label>
                      ) : (
                        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">
                          {item.text}
                        </p>
                      )}
                      {section.key === "nextActions" && editable ? (
                        <div className="mt-3 grid gap-3 sm:grid-cols-3">
                          <label className="text-xs font-semibold text-slate-700">
                            Owner
                            <input
                              className="form-input mt-1 w-full"
                              maxLength={160}
                              value={item.owner ?? ""}
                              onChange={(event) =>
                                updateItem(section.key, item.id, {
                                  owner: event.target.value || null,
                                })
                              }
                            />
                          </label>
                          <label className="text-xs font-semibold text-slate-700">
                            Due date
                            <input
                              className="form-input mt-1 w-full"
                              type="date"
                              value={item.dueDate ?? ""}
                              onChange={(event) =>
                                updateItem(section.key, item.id, {
                                  dueDate: event.target.value || null,
                                })
                              }
                            />
                          </label>
                          <label className="text-xs font-semibold text-slate-700">
                            Status
                            <select
                              className="form-input mt-1 w-full"
                              value={item.actionStatus ?? "open"}
                              onChange={(event) =>
                                updateItem(section.key, item.id, {
                                  actionStatus: event.target
                                    .value as HandoverItem["actionStatus"],
                                })
                              }
                            >
                              <option value="open">Open</option>
                              <option value="in_progress">In progress</option>
                              <option value="completed">Completed</option>
                              <option value="cancelled">Cancelled</option>
                            </select>
                          </label>
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <AuthorityBadge item={item} />
                        <SourceBadges item={item} sources={displayed.sources} />
                      </div>
                      {item.confirmedAt ? (
                        <p className="mt-2 text-xs text-slate-500">
                          Seller confirmation recorded{" "}
                          {formatDate(item.confirmedAt)}
                        </p>
                      ) : null}
                      {editable ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {item.authorityType === "inference" ||
                          item.authorityType === "unknown" ? (
                            <button
                              className="secondary-button"
                              type="button"
                              disabled={busy || dirty}
                              onClick={() => void confirmClaim(item.id)}
                            >
                              Confirm as seller
                            </button>
                          ) : null}
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => removeItem(section.key, item.id)}
                          >
                            Remove item
                          </button>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              )}
              {editable ? (
                <button
                  className="secondary-button mt-4"
                  type="button"
                  onClick={() => addItem(section.key)}
                >
                  Add {section.label.toLowerCase()} item
                </button>
              ) : null}
            </fieldset>
          );
        })}
      </div>

      <details className="mt-7 rounded-2xl border border-slate-200 p-4">
        <summary className="cursor-pointer font-semibold text-slate-900">
          Pinned source pack ({displayed.sources.length})
        </summary>
        <ul className="mt-4 space-y-3">
          {displayed.sources.map((source) => (
            <li key={source.id} className="rounded-xl bg-slate-50 p-3 text-sm">
              <p className="font-semibold text-slate-900">
                {sourceLabel(source)}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {source.sourceType.replaceAll("_", " ")} ·{" "}
                {authorityLabels[source.authorityType]} · pinned{" "}
                {formatDate(source.pinnedAt)}
              </p>
            </li>
          ))}
        </ul>
      </details>

      {viewing ? (
        <button
          className="secondary-button mt-5"
          type="button"
          onClick={() => setViewing(null)}
        >
          Return to current revision
        </button>
      ) : workspace.canManage ? (
        <div className="mt-7 rounded-2xl border border-indigo-200 bg-indigo-50 p-4">
          {editable ? (
            <div className="flex flex-wrap gap-3">
              <button
                className="primary-button"
                type="button"
                disabled={busy || !dirty}
                onClick={() => void save()}
              >
                {busy ? "Saving…" : "Save reviewed draft"}
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={busy || dirty}
                onClick={() => void lifecycle("refresh-sources")}
              >
                Refresh pinned sources
              </button>
            </div>
          ) : null}
          <label className="mt-4 flex items-start gap-3 text-sm font-semibold text-indigo-950">
            <input
              className="mt-1 size-4"
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              I reviewed the claims, authority labels and pinned sources. I
              understand inferred or unknown claims must be confirmed or removed
              before approval.
            </span>
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            {active.status === "draft" ? (
              <button
                className="primary-button"
                type="button"
                disabled={busy || dirty || !confirmed}
                onClick={() => void lifecycle("submit")}
              >
                Submit for review
              </button>
            ) : null}
            {isReview && workspace.canApprove ? (
              <button
                className="primary-button"
                type="button"
                disabled={
                  busy ||
                  !confirmed ||
                  active.approvalBlockers.length > 0 ||
                  workspace.opportunityStatus !== "won"
                }
                onClick={() => void lifecycle("approve")}
              >
                Approve immutable handover
              </button>
            ) : null}
            {active.status === "approved" ? (
              <>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={busy || !confirmed}
                  onClick={() => void lifecycle("retire")}
                >
                  Retire current handover
                </button>
                {["open", "won"].includes(workspace.opportunityStatus) ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busy}
                    onClick={() => void prepare()}
                  >
                    Prepare new revision
                  </button>
                ) : null}
              </>
            ) : null}
          </div>
          {isReview && workspace.opportunityStatus !== "won" ? (
            <p className="mt-3 text-sm font-semibold text-amber-900">
              Approval is unavailable until the canonical Opportunity status is
              Closed Won.
            </p>
          ) : null}
          {isReview && !workspace.canApprove ? (
            <p className="mt-3 text-sm font-semibold text-indigo-900">
              Submitted. An organisation administrator must perform the final
              approval.
            </p>
          ) : null}
        </div>
      ) : null}

      <p className="mt-4 text-xs font-semibold text-slate-600">
        Included with Create · No Credits required · Server-built source pack ·
        No AI provider call
      </p>
      <History
        history={workspace.history}
        busy={busy}
        onSelect={(id) => void showRevision(id)}
      />
    </section>
  );
}

function History({
  history,
  busy,
  onSelect,
}: {
  history: HandoverWorkspace["history"];
  busy: boolean;
  onSelect: (id: string) => void;
}) {
  if (history.length === 0) return null;
  return (
    <details className="mt-7 rounded-2xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer font-semibold text-slate-900">
        Revision history ({history.length})
      </summary>
      <ul className="mt-4 space-y-2">
        {history.map((revision) => (
          <li
            key={revision.id}
            className="flex flex-col gap-2 rounded-xl bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold text-slate-900">
                Revision {revision.revision}
              </span>
              <StatusBadge status={revision.status} />
              <span className="text-slate-500">
                Updated {formatDate(revision.updatedAt)}
              </span>
            </div>
            <button
              className="secondary-button"
              type="button"
              disabled={busy}
              onClick={() => onSelect(revision.id)}
            >
              View revision {revision.revision}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
