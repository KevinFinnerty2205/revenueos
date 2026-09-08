"use client";

import type {
  DealRoomDraftContent,
  DealRoomMilestoneDraft,
  DealRoomMutation,
  DealRoomResourceDraft,
  DealRoomStakeholderDraft,
  DealRoomWorkspace,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

function newId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `deal-room-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function shareUrl(token: string): string {
  return `${window.location.origin}/deal-room#access=${encodeURIComponent(token)}`;
}

export function DealRoomEditor({ opportunityId }: { opportunityId: string }) {
  const [workspace, setWorkspace] = useState<DealRoomWorkspace | null>(null);
  const [draft, setDraft] = useState<DealRoomDraftContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [expiry, setExpiry] = useState("");
  const [issuedLink, setIssuedLink] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<DealRoomWorkspace>(
      `/api/v1/opportunities/${opportunityId}/deal-room`,
      { signal: controller.signal },
    )
      .then((response) => {
        setWorkspace(response);
        setDraft(response.room?.draft ?? null);
        setExpiry(toDateTimeLocal(response.room?.link.expiresAt ?? null));
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The Deal Room could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [opportunityId]);

  async function reload(): Promise<void> {
    setLoading(true);
    try {
      const response = await apiRequest<DealRoomWorkspace>(
        `/api/v1/opportunities/${opportunityId}/deal-room`,
      );
      setWorkspace(response);
      setDraft(response.room?.draft ?? null);
      setExpiry(toDateTimeLocal(response.room?.link.expiresAt ?? null));
      setError(null);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Deal Room could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  function applyMutation(result: DealRoomMutation, success: string): void {
    setWorkspace(result.workspace);
    setDraft(result.workspace.room?.draft ?? null);
    setExpiry(toDateTimeLocal(result.workspace.room?.link.expiresAt ?? null));
    setReviewed(false);
    setMessage(success);
    setError(null);
    if (result.shareToken) setIssuedLink(shareUrl(result.shareToken));
  }

  async function createRoom(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<DealRoomMutation>(
        `/api/v1/opportunities/${opportunityId}/deal-room`,
        { method: "POST" },
      );
      applyMutation(result, "Deal Room draft created. Nothing is public yet.");
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Deal Room could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft(): Promise<void> {
    if (!workspace?.room || !draft) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<DealRoomMutation>(
        `/api/v1/opportunities/${opportunityId}/deal-room/draft`,
        {
          method: "PUT",
          body: JSON.stringify({
            expectedDraftVersion: workspace.room.draftVersion,
            expectedLockVersion: workspace.room.lockVersion,
            content: draft,
          }),
        },
      );
      applyMutation(
        result,
        workspace.room.status === "published"
          ? "Draft saved. Buyers still see the previously published revision."
          : "Draft saved. Nothing is public until you publish.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Deal Room draft could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function publish(): Promise<void> {
    if (!workspace?.room || !reviewed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<DealRoomMutation>(
        `/api/v1/opportunities/${opportunityId}/deal-room/publish`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedDraftVersion: workspace.room.draftVersion,
            expectedLockVersion: workspace.room.lockVersion,
            confirmed: true,
            linkExpiresAt: expiry ? new Date(expiry).toISOString() : null,
          }),
        },
      );
      applyMutation(
        result,
        result.shareToken
          ? "Published. Copy the new secure link now; RevenueOS will not display it again."
          : "Published as a new immutable revision. The current secure link is unchanged.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Deal Room could not be published.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function lifecycle(action: "pause" | "revoke"): Promise<void> {
    if (!workspace?.room) return;
    const confirmed = window.confirm(
      action === "pause"
        ? "Pause buyer access now? You can republish this Deal Room later."
        : "Revoke this Deal Room and invalidate its current link now?",
    );
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<DealRoomMutation>(
        `/api/v1/opportunities/${opportunityId}/deal-room/${action}`,
        {
          method: "POST",
          body: JSON.stringify({
            confirmed: true,
            expectedLockVersion: workspace.room.lockVersion,
          }),
        },
      );
      setIssuedLink(null);
      applyMutation(
        result,
        action === "pause"
          ? "Buyer access paused immediately."
          : "Deal Room revoked and the current link invalidated.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : `The Deal Room could not be ${action}d.`,
      );
    } finally {
      setBusy(false);
    }
  }

  async function rotateLink(): Promise<void> {
    if (!workspace?.room) return;
    if (
      !window.confirm(
        "Rotate the secure link now? The old link will stop working immediately.",
      )
    )
      return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<DealRoomMutation>(
        `/api/v1/opportunities/${opportunityId}/deal-room/rotate-link`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedLockVersion: workspace.room.lockVersion,
            expiresAt: expiry ? new Date(expiry).toISOString() : null,
          }),
        },
      );
      applyMutation(
        result,
        "Link rotated. Copy the new secure link now; the old link no longer works.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The secure link could not be rotated.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function copyIssuedLink(): Promise<void> {
    if (!issuedLink) return;
    try {
      await navigator.clipboard.writeText(issuedLink);
      setMessage("Secure buyer link copied to the clipboard.");
    } catch {
      setError(
        "The link could not be copied. Select the link and copy it manually.",
      );
    }
  }

  if (loading) {
    return (
      <section role="status" className="form-card">
        Loading Deal Room…
      </section>
    );
  }

  if (!workspace) {
    return (
      <section aria-labelledby="deal-room-title" className="form-card">
        <h2 id="deal-room-title" className="form-legend">
          Customer Deal Room
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error ?? "The Deal Room could not be loaded."}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => void reload()}
        >
          Try again
        </button>
      </section>
    );
  }

  if (!workspace.room || !draft) {
    return (
      <section
        aria-labelledby="deal-room-title"
        className="rounded-3xl border border-teal-200 bg-teal-50 p-6 shadow-sm sm:p-8"
      >
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Customer collaboration
        </p>
        <h2
          id="deal-room-title"
          className="mt-2 text-2xl font-semibold text-teal-950"
        >
          Create a simple Deal Room
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-teal-900">
          Share a reviewed, read-only snapshot of agreed context, milestones and
          approved resources. Internal deal intelligence is never copied
          automatically. Nothing is public yet.
        </p>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          className="primary-button mt-5"
          disabled={busy}
          onClick={() => void createRoom()}
        >
          {busy ? "Creating…" : "Create Deal Room draft"}
        </button>
        <p className="mt-3 text-xs font-semibold text-teal-800">
          Included with Create · No Credits required
        </p>
      </section>
    );
  }

  const room = workspace.room;
  const draftHasUnsavedChanges =
    JSON.stringify(draft) !== JSON.stringify(room.draft);
  return (
    <section
      id="deal-room"
      aria-labelledby="deal-room-title"
      className="form-card scroll-mt-6"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Customer collaboration
          </p>
          <h2 id="deal-room-title" className="form-legend mt-2">
            Opportunity Deal Room
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Buyers see only the immutable revision you explicitly publish. Keep
            manager notes, forecasts, risks, sales methodology and private
            evidence out of these fields.
          </p>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Deal Room status">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-slate-800">
            {room.status}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-bold ${room.effectiveAccess === "available" ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-950"}`}
          >
            Buyer access {room.effectiveAccess}
          </span>
        </div>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="mt-5 rounded-xl bg-teal-50 p-4 text-sm font-semibold text-teal-900"
        >
          {message}
        </p>
      ) : null}
      {issuedLink ? (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-bold text-emerald-950">
            New secure buyer link
          </p>
          <p className="mt-1 text-xs leading-5 text-emerald-900">
            Copy it now. Only its hash is stored, so it cannot be recovered
            later.
          </p>
          <input
            aria-label="Secure buyer link"
            className="form-control mt-3 w-full font-mono text-xs"
            readOnly
            value={issuedLink}
            onFocus={(event) => event.currentTarget.select()}
          />
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void copyIssuedLink()}
          >
            Copy secure link
          </button>
        </div>
      ) : null}

      <div className="mt-7 grid gap-6">
        <fieldset className="grid gap-4 rounded-2xl border border-slate-200 p-4 sm:p-5">
          <legend className="px-2 text-base font-bold text-slate-950">
            Overview and approved commercial context
          </legend>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            Customer-facing overview
            <textarea
              className="min-h-28 rounded-xl border border-slate-300 p-4 text-sm font-normal outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
              maxLength={2000}
              value={draft.overview ?? ""}
              onChange={(event) =>
                setDraft({ ...draft, overview: event.target.value || null })
              }
            />
            <span className="text-xs font-normal text-slate-500">
              Seller-authored, plain text · {draft.overview?.length ?? 0}/2,000
            </span>
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            Approved Business Case revision
            <select
              className="form-control"
              value={draft.businessCaseVersionId ?? ""}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  businessCaseVersionId: event.target.value || null,
                })
              }
            >
              <option value="">Do not publish a Business Case</option>
              {workspace.businessCases.map((item) => (
                <option key={item.versionId} value={item.versionId}>
                  {item.title} · approved revision {item.version}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            Commercial summary approved for sharing
            <textarea
              className="min-h-24 rounded-xl border border-slate-300 p-4 text-sm font-normal outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
              maxLength={1500}
              value={draft.commercialSummary ?? ""}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  commercialSummary: event.target.value || null,
                })
              }
            />
            <span className="text-xs font-normal text-slate-500">
              Use only agreed scope, price or term. Never include margin,
              approval floors or internal economics.
            </span>
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800 sm:max-w-md">
            Next meeting or decision date
            <input
              type="datetime-local"
              className="form-control"
              value={toDateTimeLocal(draft.nextMeetingAt)}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  nextMeetingAt: event.target.value
                    ? new Date(event.target.value).toISOString()
                    : null,
                })
              }
            />
          </label>
        </fieldset>

        <StakeholderEditor draft={draft} setDraft={setDraft} />
        <MilestoneEditor draft={draft} setDraft={setDraft} />
        <ResourceEditor
          draft={draft}
          setDraft={setDraft}
          workspace={workspace}
        />
      </div>

      <div className="mt-7 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <p>
            <span className="font-bold text-slate-950">Published revision</span>
            <br />
            {room.publishedRevision ?? "None"}
          </p>
          <p>
            <span className="font-bold text-slate-950">Last published</span>
            <br />
            {formatDateTime(room.lastPublishedAt)}
          </p>
          <p>
            <span className="font-bold text-slate-950">Link expiry</span>
            <br />
            {formatDateTime(room.link.expiresAt)}
          </p>
        </div>
        {room.revisions.length > 0 ? (
          <details className="mt-4">
            <summary className="cursor-pointer text-sm font-bold text-slate-800">
              Publication history ({room.revisions.length})
            </summary>
            <ol className="mt-3 space-y-2 text-sm text-slate-700">
              {room.revisions.map((revision) => (
                <li key={revision.id}>
                  Revision {revision.revision} ·{" "}
                  {formatDateTime(revision.publishedAt)}
                </li>
              ))}
            </ol>
          </details>
        ) : null}
      </div>

      <div className="mt-6 grid gap-4 rounded-2xl border border-teal-200 bg-teal-50 p-5">
        <label className="flex items-start gap-3 text-sm font-semibold text-teal-950">
          <input
            type="checkbox"
            className="mt-1 size-4"
            checked={reviewed}
            onChange={(event) => setReviewed(event.target.checked)}
          />
          I have reviewed every field and selected resource as appropriate for
          this customer.
        </label>
        <label className="grid gap-2 text-sm font-semibold text-teal-950 sm:max-w-md">
          Optional secure-link expiry
          <input
            type="datetime-local"
            className="form-control"
            value={expiry}
            onChange={(event) => setExpiry(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => void saveDraft()}
          >
            {busy ? "Working…" : "Save draft"}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={busy || !reviewed || draftHasUnsavedChanges}
            onClick={() => void publish()}
          >
            {room.publishedRevision
              ? "Review and republish"
              : "Review and publish"}
          </button>
          {room.status === "published" ? (
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void lifecycle("pause")}
            >
              Pause access
            </button>
          ) : null}
          {room.status === "published" ? (
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void rotateLink()}
            >
              Rotate link
            </button>
          ) : null}
          {room.publishedRevision && room.status !== "revoked" ? (
            <button
              type="button"
              className="secondary-button border-rose-300 text-rose-800"
              disabled={busy}
              onClick={() => void lifecycle("revoke")}
            >
              Revoke
            </button>
          ) : null}
        </div>
        {draftHasUnsavedChanges ? (
          <p className="text-xs font-semibold text-amber-900">
            Save this draft before reviewing and publishing it.
          </p>
        ) : null}
        <p className="text-xs font-semibold text-teal-800">
          Publishing and link access use no Oryntela Credits.
        </p>
      </div>
    </section>
  );
}

function StakeholderEditor({
  draft,
  setDraft,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
}) {
  function update(id: string, patch: Partial<DealRoomStakeholderDraft>) {
    setDraft({
      ...draft,
      stakeholders: draft.stakeholders.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
    });
  }
  return (
    <fieldset className="rounded-2xl border border-slate-200 p-4 sm:p-5">
      <legend className="px-2 text-base font-bold text-slate-950">
        People
      </legend>
      <p className="mb-4 text-xs leading-5 text-slate-500">
        Only add names, roles and companies you intend the buyer to see. Contact
        details and internal relationship data are not supported.
      </p>
      <div className="grid gap-3">
        {draft.stakeholders.map((item) => (
          <div
            key={item.id}
            className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Name
              <input
                aria-label="Stakeholder name"
                className="form-control"
                maxLength={120}
                value={item.name}
                onChange={(event) =>
                  update(item.id, { name: event.target.value })
                }
              />
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Role
              <input
                aria-label="Stakeholder role"
                className="form-control"
                maxLength={120}
                value={item.role}
                onChange={(event) =>
                  update(item.id, { role: event.target.value })
                }
              />
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Company
              <input
                aria-label="Stakeholder company"
                className="form-control"
                maxLength={200}
                value={item.company}
                onChange={(event) =>
                  update(item.id, { company: event.target.value })
                }
              />
            </label>
            <div className="grid gap-2">
              <label className="grid gap-1 text-xs font-bold text-slate-700">
                Party
                <select
                  aria-label="Stakeholder party"
                  className="form-control"
                  value={item.party}
                  onChange={(event) =>
                    update(item.id, {
                      party: event.target.value as "seller" | "customer",
                    })
                  }
                >
                  <option value="customer">Customer</option>
                  <option value="seller">Our team</option>
                </select>
              </label>
              <button
                type="button"
                className="text-left text-xs font-bold text-rose-700 underline"
                onClick={() =>
                  setDraft({
                    ...draft,
                    stakeholders: draft.stakeholders.filter(
                      (candidate) => candidate.id !== item.id,
                    ),
                  })
                }
              >
                Remove person
              </button>
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="secondary-button mt-4"
        disabled={draft.stakeholders.length >= 12}
        onClick={() =>
          setDraft({
            ...draft,
            stakeholders: [
              ...draft.stakeholders,
              {
                id: newId(),
                name: "",
                role: "",
                company: "",
                party: "customer",
                sourceContactId: null,
              },
            ],
          })
        }
      >
        Add person
      </button>
    </fieldset>
  );
}

function MilestoneEditor({
  draft,
  setDraft,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
}) {
  function update(id: string, patch: Partial<DealRoomMilestoneDraft>) {
    setDraft({
      ...draft,
      milestones: draft.milestones.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
    });
  }
  return (
    <fieldset className="rounded-2xl border border-slate-200 p-4 sm:p-5">
      <legend className="px-2 text-base font-bold text-slate-950">
        Next steps and timeline
      </legend>
      <div className="grid gap-3">
        {draft.milestones.map((item) => (
          <div
            key={item.id}
            className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <label className="grid gap-1 text-xs font-bold text-slate-700 sm:col-span-2">
              Title
              <input
                aria-label="Milestone title"
                className="form-control"
                maxLength={160}
                value={item.title}
                onChange={(event) =>
                  update(item.id, { title: event.target.value })
                }
              />
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Owner
              <select
                aria-label="Milestone owner"
                className="form-control"
                value={item.ownerParty}
                onChange={(event) =>
                  update(item.id, {
                    ownerParty: event.target
                      .value as DealRoomMilestoneDraft["ownerParty"],
                  })
                }
              >
                <option value="our_team">Our team</option>
                <option value="customer">Customer</option>
                <option value="joint">Joint</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Status
              <select
                aria-label="Milestone status"
                className="form-control"
                value={item.status}
                onChange={(event) =>
                  update(item.id, {
                    status: event.target
                      .value as DealRoomMilestoneDraft["status"],
                  })
                }
              >
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="done">Done</option>
                <option value="blocked">Blocked</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Target date
              <input
                aria-label="Milestone target date"
                type="date"
                className="form-control"
                value={item.targetDate ?? ""}
                onChange={(event) =>
                  update(item.id, { targetDate: event.target.value || null })
                }
              />
            </label>
            <label className="grid gap-1 text-xs font-bold text-slate-700 sm:col-span-2 lg:col-span-3">
              Customer-facing note
              <input
                aria-label="Milestone note"
                className="form-control"
                maxLength={500}
                value={item.note ?? ""}
                onChange={(event) =>
                  update(item.id, { note: event.target.value || null })
                }
              />
            </label>
            <button
              type="button"
              className="text-left text-xs font-bold text-rose-700 underline"
              onClick={() =>
                setDraft({
                  ...draft,
                  milestones: draft.milestones.filter(
                    (candidate) => candidate.id !== item.id,
                  ),
                })
              }
            >
              Remove milestone
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="secondary-button mt-4"
        disabled={draft.milestones.length >= 20}
        onClick={() =>
          setDraft({
            ...draft,
            milestones: [
              ...draft.milestones,
              {
                id: newId(),
                title: "",
                ownerParty: "joint",
                targetDate: null,
                status: "not_started",
                note: null,
              },
            ],
          })
        }
      >
        Add milestone
      </button>
    </fieldset>
  );
}

function ResourceEditor({
  draft,
  setDraft,
  workspace,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
  workspace: DealRoomWorkspace;
}) {
  function update(id: string, patch: Partial<DealRoomResourceDraft>) {
    setDraft({
      ...draft,
      resources: draft.resources.map((item) =>
        item.id === id ? { ...item, ...patch } : item,
      ),
    });
  }
  function add(kind: DealRoomResourceDraft["kind"]) {
    setDraft({
      ...draft,
      resources: [
        ...draft.resources,
        {
          id: newId(),
          kind,
          title: "",
          externalUrl: kind === "external_link" ? "https://" : null,
          presentationVersionId:
            kind === "presentation"
              ? (workspace.presentations[0]?.versionId ?? null)
              : null,
        },
      ],
    });
  }
  return (
    <fieldset className="rounded-2xl border border-slate-200 p-4 sm:p-5">
      <legend className="px-2 text-base font-bold text-slate-950">
        Approved resources
      </legend>
      <p className="mb-4 text-xs leading-5 text-slate-500">
        Only credential-free HTTPS links and exact approved Create presentation
        revisions are supported. General file uploads are intentionally
        deferred.
      </p>
      <div className="grid gap-3">
        {draft.resources.map((item) => (
          <div
            key={item.id}
            className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2"
          >
            <label className="grid gap-1 text-xs font-bold text-slate-700">
              Display title
              <input
                aria-label="Resource title"
                className="form-control"
                maxLength={160}
                value={item.title}
                onChange={(event) =>
                  update(item.id, { title: event.target.value })
                }
              />
            </label>
            {item.kind === "external_link" ? (
              <label className="grid gap-1 text-xs font-bold text-slate-700">
                HTTPS URL
                <input
                  aria-label="Resource HTTPS URL"
                  type="url"
                  inputMode="url"
                  className="form-control"
                  value={item.externalUrl ?? ""}
                  onChange={(event) =>
                    update(item.id, { externalUrl: event.target.value })
                  }
                />
              </label>
            ) : (
              <label className="grid gap-1 text-xs font-bold text-slate-700">
                Approved presentation revision
                <select
                  aria-label="Approved presentation revision"
                  className="form-control"
                  value={item.presentationVersionId ?? ""}
                  onChange={(event) =>
                    update(item.id, {
                      presentationVersionId: event.target.value || null,
                    })
                  }
                >
                  <option value="">Select an approved presentation</option>
                  {workspace.presentations.map((presentation) => (
                    <option
                      key={presentation.versionId}
                      value={presentation.versionId}
                    >
                      {presentation.title} · revision {presentation.version}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              className="text-left text-xs font-bold text-rose-700 underline"
              onClick={() =>
                setDraft({
                  ...draft,
                  resources: draft.resources.filter(
                    (candidate) => candidate.id !== item.id,
                  ),
                })
              }
            >
              Remove resource
            </button>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          className="secondary-button"
          disabled={draft.resources.length >= 10}
          onClick={() => add("external_link")}
        >
          Add HTTPS link
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={
            draft.resources.length >= 10 || workspace.presentations.length === 0
          }
          onClick={() => add("presentation")}
        >
          Add approved presentation
        </button>
      </div>
    </fieldset>
  );
}
