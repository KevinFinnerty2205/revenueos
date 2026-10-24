"use client";

import type {
  DealRoomDraftContent,
  DealRoomMilestoneDraft,
  DealRoomMutation,
  DealRoomResourceDraft,
  DealRoomStakeholderDraft,
  DealRoomWorkspace,
} from "@revenueos/shared";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { onOpportunityChanged } from "@/lib/opportunity-events";

const opportunityStatuses: ReadonlySet<string> = new Set([
  "open",
  "won",
  "lost",
  "on_hold",
]);
const dealRoomStatuses: ReadonlySet<string> = new Set([
  "draft",
  "published",
  "paused",
  "revoked",
]);
const milestoneOwnerParties: ReadonlySet<string> = new Set([
  "our_team",
  "customer",
  "joint",
]);
const milestoneStatuses: ReadonlySet<string> = new Set([
  "not_started",
  "in_progress",
  "done",
  "blocked",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isStakeholder(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.role === "string" &&
    typeof value.company === "string" &&
    (value.party === "seller" || value.party === "customer") &&
    isNullableString(value.sourceContactId)
  );
}

function isMilestone(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.ownerParty === "string" &&
    milestoneOwnerParties.has(value.ownerParty) &&
    isNullableString(value.targetDate) &&
    typeof value.status === "string" &&
    milestoneStatuses.has(value.status) &&
    isNullableString(value.note)
  );
}

function isResource(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    (value.kind === "external_link" || value.kind === "presentation") &&
    typeof value.title === "string" &&
    isNullableString(value.externalUrl) &&
    isNullableString(value.presentationVersionId)
  );
}

function isDraft(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNullableString(value.overview) &&
    isNullableString(value.commercialSummary) &&
    isNullableString(value.businessCaseVersionId) &&
    Array.isArray(value.stakeholders) &&
    value.stakeholders.every(isStakeholder) &&
    Array.isArray(value.milestones) &&
    value.milestones.every(isMilestone) &&
    Array.isArray(value.resources) &&
    value.resources.every(isResource) &&
    isNullableString(value.nextMeetingAt)
  );
}

function isLink(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.active === "boolean" &&
    isNullableString(value.expiresAt) &&
    isNullableString(value.createdAt)
  );
}

function isRevision(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    isFiniteNumber(value.revision) &&
    typeof value.publishedAt === "string" &&
    typeof value.publishedByUserId === "string" &&
    typeof value.contentFingerprint === "string"
  );
}

function isRoom(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.opportunityId === "string" &&
    typeof value.status === "string" &&
    dealRoomStatuses.has(value.status) &&
    (value.effectiveAccess === "available" ||
      value.effectiveAccess === "unavailable") &&
    isFiniteNumber(value.draftVersion) &&
    isFiniteNumber(value.lockVersion) &&
    isDraft(value.draft) &&
    isNullableString(value.publishedRevisionId) &&
    (value.publishedRevision === null ||
      isFiniteNumber(value.publishedRevision)) &&
    isNullableString(value.lastPublishedAt) &&
    isLink(value.link) &&
    Array.isArray(value.revisions) &&
    value.revisions.every(isRevision) &&
    typeof value.createdAt === "string" &&
    typeof value.updatedAt === "string"
  );
}

function isBusinessCase(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.caseId === "string" &&
    typeof value.versionId === "string" &&
    typeof value.title === "string" &&
    isFiniteNumber(value.version) &&
    typeof value.approvedAt === "string"
  );
}

function isPresentation(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.presentationId === "string" &&
    typeof value.versionId === "string" &&
    typeof value.title === "string" &&
    isFiniteNumber(value.version) &&
    typeof value.approvedAt === "string"
  );
}

function isDealRoomWorkspace(value: unknown): value is DealRoomWorkspace {
  return (
    isRecord(value) &&
    typeof value.opportunityStatus === "string" &&
    opportunityStatuses.has(value.opportunityStatus) &&
    typeof value.canEdit === "boolean" &&
    typeof value.canManageAccess === "boolean" &&
    (value.room === null || isRoom(value.room)) &&
    Array.isArray(value.businessCases) &&
    value.businessCases.every(isBusinessCase) &&
    Array.isArray(value.presentations) &&
    value.presentations.every(isPresentation) &&
    value.entitlement === "create" &&
    value.creditsRequired === false
  );
}

function assertDealRoomWorkspace(
  value: unknown,
): asserts value is DealRoomWorkspace {
  if (!isDealRoomWorkspace(value)) {
    throw new Error("The Deal Room service returned an invalid response.");
  }
}

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
  const [refreshKey, setRefreshKey] = useState(0);
  const workspaceRef = useRef(workspace);
  const draftRef = useRef(draft);
  const expiryRef = useRef(expiry);
  const refreshGenerationRef = useRef(0);
  const pendingStatusRef = useRef<
    DealRoomWorkspace["opportunityStatus"] | undefined
  >(undefined);
  const pendingDirtyRefreshRef = useRef<{
    generation: number;
    roomId: string;
    draft: DealRoomDraftContent;
    expiry: string;
  } | null>(null);

  useEffect(() => {
    workspaceRef.current = workspace;
  }, [workspace]);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    expiryRef.current = expiry;
  }, [expiry]);

  useEffect(() => {
    const controller = new AbortController();
    const generation = refreshKey;
    const dirtyRefresh =
      pendingDirtyRefreshRef.current?.generation === generation
        ? pendingDirtyRefreshRef.current
        : null;
    apiRequest<DealRoomWorkspace>(
      `/api/v1/opportunities/${opportunityId}/deal-room`,
      { signal: controller.signal },
    )
      .then((response) => {
        if (
          controller.signal.aborted ||
          generation !== refreshGenerationRef.current
        )
          return;
        assertDealRoomWorkspace(response);
        const preserveDirtyDraft =
          dirtyRefresh !== null && dirtyRefresh.roomId === response.room?.id;
        const nextDraft = preserveDirtyDraft
          ? dirtyRefresh.draft
          : (response.room?.draft ?? null);
        const nextExpiry = preserveDirtyDraft
          ? dirtyRefresh.expiry
          : toDateTimeLocal(response.room?.link.expiresAt ?? null);
        workspaceRef.current = response;
        draftRef.current = nextDraft;
        expiryRef.current = nextExpiry;
        pendingDirtyRefreshRef.current = null;
        pendingStatusRef.current = undefined;
        setWorkspace(response);
        setDraft(nextDraft);
        setExpiry(nextExpiry);
        setError(null);
        if (preserveDirtyDraft) {
          setMessage(
            response.canEdit
              ? "Opportunity status refreshed. Your unsaved Deal Room edits were preserved; save them before publishing."
              : "Opportunity status refreshed. Your unsaved Deal Room edits were preserved. This Opportunity is now read-only; reopen it before saving.",
          );
        }
      })
      .catch((reason: unknown) => {
        if (
          controller.signal.aborted ||
          generation !== refreshGenerationRef.current ||
          (reason instanceof DOMException && reason.name === "AbortError")
        )
          return;
        pendingDirtyRefreshRef.current = null;
        pendingStatusRef.current = undefined;
        setError(
          reason instanceof Error
            ? reason.message
            : "The Deal Room could not be loaded.",
        );
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          generation === refreshGenerationRef.current
        )
          setLoading(false);
      });
    return () => controller.abort();
  }, [opportunityId, refreshKey]);

  useEffect(
    () =>
      onOpportunityChanged(opportunityId, (change) => {
        const currentStatus =
          pendingStatusRef.current ?? workspaceRef.current?.opportunityStatus;
        if (change.status !== undefined && change.status === currentStatus)
          return;
        const room = workspaceRef.current?.room;
        const currentDraft = draftRef.current;
        const preserveDirtyDraft = Boolean(
          room &&
          currentDraft &&
          (JSON.stringify(currentDraft) !== JSON.stringify(room.draft) ||
            expiryRef.current !== toDateTimeLocal(room.link.expiresAt)),
        );
        const generation = refreshGenerationRef.current + 1;
        refreshGenerationRef.current = generation;
        pendingStatusRef.current = change.status;
        pendingDirtyRefreshRef.current =
          preserveDirtyDraft && room && currentDraft
            ? {
                generation,
                roomId: room.id,
                draft: currentDraft,
                expiry: expiryRef.current,
              }
            : null;
        setLoading(true);
        setMessage(null);
        setIssuedLink(null);
        setReviewed(false);
        setRefreshKey(generation);
      }),
    [opportunityId],
  );

  async function reload(): Promise<void> {
    setLoading(true);
    try {
      const response = await apiRequest<DealRoomWorkspace>(
        `/api/v1/opportunities/${opportunityId}/deal-room`,
      );
      assertDealRoomWorkspace(response);
      const nextDraft = response.room?.draft ?? null;
      const nextExpiry = toDateTimeLocal(response.room?.link.expiresAt ?? null);
      workspaceRef.current = response;
      draftRef.current = nextDraft;
      expiryRef.current = nextExpiry;
      setWorkspace(response);
      setDraft(nextDraft);
      setExpiry(nextExpiry);
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
    assertDealRoomWorkspace(result.workspace);
    const nextDraft = result.workspace.room?.draft ?? null;
    const nextExpiry = toDateTimeLocal(
      result.workspace.room?.link.expiresAt ?? null,
    );
    workspaceRef.current = result.workspace;
    draftRef.current = nextDraft;
    expiryRef.current = nextExpiry;
    setWorkspace(result.workspace);
    setDraft(nextDraft);
    setExpiry(nextExpiry);
    setReviewed(false);
    setMessage(success);
    setError(null);
    if (result.shareToken) setIssuedLink(shareUrl(result.shareToken));
  }

  async function createRoom(): Promise<void> {
    if (!workspace?.canEdit) return;
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
    if (!workspace?.canEdit || !workspace.room || !draft) return;
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
    if (!workspace?.canEdit || !workspace.room || !reviewed) return;
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
          ? "Published. Copy the new secure link now; Oryntela will not display it again."
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
    if (!workspace?.canManageAccess || !workspace.room) return;
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
    if (!workspace?.canEdit || !workspace.room) return;
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
        className="rounded-3xl border border-brand-secondary/25 bg-brand-secondary/10 p-6 shadow-sm sm:p-8"
      >
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
          Customer collaboration
        </p>
        <h2
          id="deal-room-title"
          className="mt-2 text-2xl font-semibold text-brand-primary"
        >
          Create a simple Deal Room
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-brand-primary">
          Share a reviewed, read-only snapshot of agreed context, milestones and
          approved resources. Internal deal intelligence is never copied
          automatically. Nothing is public yet.
        </p>
        {!workspace.canEdit ? (
          <p className="mt-4 rounded-xl bg-white/80 p-4 text-sm font-semibold text-slate-700">
            Editing is unavailable while this Opportunity is{" "}
            {workspace.opportunityStatus.replaceAll("_", " ")} or Create write
            access is unavailable.
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="mt-3 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          className="primary-button mt-5"
          disabled={busy || !workspace.canEdit}
          onClick={() => void createRoom()}
        >
          {busy ? "Creating…" : "Create Deal Room draft"}
        </button>
        <p className="mt-3 text-xs font-semibold text-brand-secondary">
          Included with Create · No Credits required
        </p>
      </section>
    );
  }

  const room = workspace.room;
  const readOnly = !workspace.canEdit;
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
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
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

      {readOnly ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-950"
        >
          The Deal Room is read-only while this Opportunity is{" "}
          {workspace.opportunityStatus.replaceAll("_", " ")} or Create write
          access is unavailable. Buyer access remains unavailable unless the
          Opportunity is active and open.
        </p>
      ) : null}

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
          className="mt-5 rounded-xl bg-brand-secondary/10 p-4 text-sm font-semibold text-brand-primary"
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
              className="min-h-28 rounded-xl border border-slate-300 p-4 text-sm font-normal outline-none focus:border-brand-secondary focus:ring-2 focus:ring-brand-secondary/20"
              maxLength={2000}
              value={draft.overview ?? ""}
              disabled={readOnly}
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
              disabled={readOnly}
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
              className="min-h-24 rounded-xl border border-slate-300 p-4 text-sm font-normal outline-none focus:border-brand-secondary focus:ring-2 focus:ring-brand-secondary/20"
              maxLength={1500}
              value={draft.commercialSummary ?? ""}
              disabled={readOnly}
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
              disabled={readOnly}
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

        <StakeholderEditor
          draft={draft}
          setDraft={setDraft}
          disabled={readOnly}
        />
        <MilestoneEditor
          draft={draft}
          setDraft={setDraft}
          disabled={readOnly}
        />
        <ResourceEditor
          draft={draft}
          setDraft={setDraft}
          workspace={workspace}
          disabled={readOnly}
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

      <div className="mt-6 grid gap-4 rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5">
        <label className="flex items-start gap-3 text-sm font-semibold text-brand-primary">
          <input
            type="checkbox"
            className="mt-1 size-4"
            checked={reviewed}
            disabled={readOnly}
            onChange={(event) => setReviewed(event.target.checked)}
          />
          I have reviewed every field and selected resource as appropriate for
          this customer.
        </label>
        <label className="grid gap-2 text-sm font-semibold text-brand-primary sm:max-w-md">
          Optional secure-link expiry
          <input
            type="datetime-local"
            className="form-control"
            value={expiry}
            disabled={readOnly}
            onChange={(event) => setExpiry(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            disabled={busy || readOnly}
            onClick={() => void saveDraft()}
          >
            {busy ? "Working…" : "Save draft"}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={busy || readOnly || !reviewed || draftHasUnsavedChanges}
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
              disabled={busy || !workspace.canManageAccess}
              onClick={() => void lifecycle("pause")}
            >
              Pause access
            </button>
          ) : null}
          {room.status === "published" ? (
            <button
              type="button"
              className="secondary-button"
              disabled={busy || readOnly}
              onClick={() => void rotateLink()}
            >
              Rotate link
            </button>
          ) : null}
          {room.publishedRevision && room.status !== "revoked" ? (
            <button
              type="button"
              className="secondary-button border-rose-300 text-rose-800"
              disabled={busy || !workspace.canManageAccess}
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
        <p className="text-xs font-semibold text-brand-secondary">
          Publishing and link access use no Oryntela Credits.
        </p>
      </div>
    </section>
  );
}

function StakeholderEditor({
  draft,
  setDraft,
  disabled,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
  disabled: boolean;
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
                disabled={disabled}
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
                disabled={disabled}
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
                disabled={disabled}
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
                  disabled={disabled}
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
                disabled={disabled}
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
        disabled={disabled || draft.stakeholders.length >= 12}
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
  disabled,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
  disabled: boolean;
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
                disabled={disabled}
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
                disabled={disabled}
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
                disabled={disabled}
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
                disabled={disabled}
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
                disabled={disabled}
                onChange={(event) =>
                  update(item.id, { note: event.target.value || null })
                }
              />
            </label>
            <button
              type="button"
              className="text-left text-xs font-bold text-rose-700 underline"
              disabled={disabled}
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
        disabled={disabled || draft.milestones.length >= 20}
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
  disabled,
}: {
  draft: DealRoomDraftContent;
  setDraft: (value: DealRoomDraftContent) => void;
  workspace: DealRoomWorkspace;
  disabled: boolean;
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
                disabled={disabled}
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
                  disabled={disabled}
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
                  disabled={disabled}
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
              disabled={disabled}
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
          disabled={disabled || draft.resources.length >= 10}
          onClick={() => add("external_link")}
        >
          Add HTTPS link
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={
            disabled ||
            draft.resources.length >= 10 ||
            workspace.presentations.length === 0
          }
          onClick={() => add("presentation")}
        >
          Add approved presentation
        </button>
      </div>
    </fieldset>
  );
}
