"use client";

import type {
  CreateDownloadGrant,
  CreateGeneratedSlide,
  CreatePresentation,
  CreatePresentationPlanItem,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiBlob, apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function CreatePresentationReview({
  presentationId,
}: {
  presentationId: string;
}) {
  const [presentation, setPresentation] = useState<CreatePresentation | null>(
    null,
  );
  const [plan, setPlan] = useState<CreatePresentationPlanItem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const next = await apiRequest<CreatePresentation>(
      `/api/v1/create/presentations/${presentationId}`,
    );
    setPresentation(next);
    setPlan(next.plan);
    setError(null);
    return next;
  }, [presentationId]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const next = await load();
        if (active && next.state === "generating") {
          timer = setTimeout(() => void refresh(), 2_000);
        }
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "The presentation could not be loaded.",
          );
        }
      }
    };
    void refresh();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  function move(index: number, direction: -1 | 1) {
    const included = plan.filter((item) => item.included);
    const selected = included[index];
    const target = included[index + direction];
    if (!selected || !target) return;
    setPlan((current) =>
      current.map((item) => {
        if (item.id === selected.id) return { ...item, order: target.order };
        if (item.id === target.id) return { ...item, order: selected.order };
        return item;
      }),
    );
  }

  async function savePlan(): Promise<boolean> {
    setBusy("plan");
    setError(null);
    try {
      const next = await apiRequest<CreatePresentation>(
        `/api/v1/create/presentations/${presentationId}/plan`,
        {
          method: "PUT",
          body: JSON.stringify({
            items: plan.map((item) => ({
              id: item.id,
              included: item.included,
              order: item.order,
            })),
            addSlideIds: [],
          }),
        },
      );
      setPresentation(next);
      setPlan(next.plan);
      return true;
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The plan could not be saved.",
      );
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function generate() {
    setBusy("generate");
    setError(null);
    try {
      if (!(await savePlan())) return;
      const next = await apiRequest<CreatePresentation>(
        `/api/v1/create/presentations/${presentationId}/generate`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: `web-generate-${crypto.randomUUID()}`,
          }),
        },
      );
      setPresentation(next);
      window.setTimeout(() => void load(), 2_000);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The presentation could not be generated.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function decide(claimId: string, action: "keep" | "remove") {
    setBusy(claimId);
    setError(null);
    try {
      const next = await apiRequest<CreatePresentation>(
        `/api/v1/create/presentations/${presentationId}/review`,
        {
          method: "POST",
          body: JSON.stringify({ decisions: [{ claimId, action }] }),
        },
      );
      setPresentation(next);
      if (next.state === "generating")
        window.setTimeout(() => void load(), 2_000);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The claim review could not be saved.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    setBusy("approve");
    setError(null);
    try {
      const next = await apiRequest<CreatePresentation>(
        `/api/v1/create/presentations/${presentationId}/approve`,
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      setPresentation(next);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The presentation could not be approved.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    if (!presentation) return;
    setBusy("download");
    setError(null);
    try {
      const grant = await apiRequest<CreateDownloadGrant>(
        `/api/v1/create/presentations/${presentationId}/download-grant`,
        { method: "POST" },
      );
      const blob = await apiBlob(grant.downloadUrl, {
        method: "POST",
        body: JSON.stringify({ grantToken: grant.grantToken }),
        headers: { "Content-Type": "application/json" },
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = grant.fileName;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The PowerPoint could not be downloaded.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (!presentation) {
    return error ? (
      <p role="alert" className="rounded-xl bg-rose-50 p-4 text-rose-900">
        {error}
      </p>
    ) : (
      <p role="status">Loading presentation…</p>
    );
  }
  const current = presentation.currentVersion;
  const pendingClaims =
    current?.claims.filter((claim) => claim.reviewState === "pending") ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Create · Presentation"
        title={presentation.title}
        description={`${presentation.accountName}${presentation.opportunityName ? ` · ${presentation.opportunityName}` : ""} · ${humanise(presentation.objective)}`}
        actions={<StateBadge state={presentation.state} />}
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> Presentation
      </nav>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:grid-cols-3">
        <Detail label="Template">
          {presentation.templateName} v{presentation.templateVersion}
        </Detail>
        <Detail label="Audience">
          {presentation.audience
            .map(
              (item) => item.name ?? item.role ?? humanise(item.audienceType),
            )
            .join(", ")}
        </Detail>
        <Detail label="Focus">
          {presentation.focusInstruction ?? "No additional focus"}
        </Detail>
      </section>

      {presentation.state === "draft_plan" ? (
        <PlanReview
          plan={plan}
          busy={busy !== null}
          onToggle={(id) =>
            setPlan((currentPlan) =>
              currentPlan.map((item) =>
                item.id === id && !item.required
                  ? { ...item, included: !item.included }
                  : item,
              ),
            )
          }
          onMove={move}
          onSave={() => void savePlan()}
          onGenerate={() => void generate()}
        />
      ) : presentation.state === "generating" ? (
        <section className="form-card">
          <h2 className="form-legend">Rendering the PowerPoint</h2>
          <p role="status" className="mt-2 text-sm leading-6 text-slate-600">
            RevenueOS is composing approved slides against the immutable source
            snapshot. This page will refresh automatically.
          </p>
        </section>
      ) : presentation.state === "failed" ? (
        <section className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
          <h2 className="font-semibold text-rose-950">
            Generation failed safely
          </h2>
          <p className="mt-2 text-sm text-rose-900">
            {current?.safeFailureCode ??
              "The presentation could not be rendered."}
          </p>
        </section>
      ) : current ? (
        <>
          <section aria-labelledby="slide-review-title" className="space-y-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
                Bounded text review
              </p>
              <h2
                id="slide-review-title"
                className="mt-1 text-2xl font-semibold text-slate-950"
              >
                Review the generated slides
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Review the structure and customer-facing content below. The
                downloaded PowerPoint is the final file. Fonts, spacing and
                layout may vary slightly by device and PowerPoint version. You
                can edit text only where the template permits it.
              </p>
            </div>
            <div className="space-y-4">
              {current.slides.map((slide) => (
                <GeneratedSlideCard
                  key={`${slide.planItemId}-${current.generatedAt}`}
                  slide={slide}
                  presentationId={presentationId}
                  immutable={presentation.state === "ready"}
                  onUpdated={(next) => {
                    setPresentation(next);
                    window.setTimeout(() => void load(), 2_000);
                  }}
                  onError={setError}
                />
              ))}
            </div>
          </section>

          <section className="form-card" aria-labelledby="claim-manifest-title">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
                  Traceability
                </p>
                <h2 id="claim-manifest-title" className="form-legend mt-1">
                  Claim and source manifest
                </h2>
              </div>
              <span className="text-sm font-semibold text-slate-600">
                {pendingClaims.length} require review
              </span>
            </div>
            <div className="mt-5 space-y-3">
              {current.claims
                .filter((claim) => claim.reviewState !== "removed")
                .map((claim) => (
                  <article
                    key={claim.id}
                    className="rounded-xl border border-slate-200 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="max-w-3xl">
                        <p className="text-sm font-semibold text-slate-950">
                          {claim.claim}
                        </p>
                        <p className="mt-2 text-xs leading-5 text-slate-600">
                          {humanise(claim.origin)} ·{" "}
                          {humanise(claim.supportState)} ·{" "}
                          {claim.sourceLabels.join(", ")}
                        </p>
                      </div>
                      <StateBadge state={claim.reviewState} />
                    </div>
                    {claim.reviewState === "pending" ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() => void decide(claim.id, "keep")}
                          className="secondary-button"
                        >
                          Keep with review
                        </button>
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() => void decide(claim.id, "remove")}
                          className="secondary-button"
                        >
                          Remove claim
                        </button>
                      </div>
                    ) : null}
                  </article>
                ))}
            </div>
          </section>

          <section className="rounded-3xl border border-teal-200 bg-teal-50 p-6 sm:p-8">
            <h2 className="text-2xl font-semibold text-teal-950">
              Human approval before download
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-teal-900">
              Approval confirms the current immutable version, its required
              slides, source manifest and any claims you explicitly kept.
              RevenueOS does not send the deck or upload it to an external
              presentation service.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {presentation.state === "ready" && current.downloadAvailable ? (
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void download()}
                  className="primary-button"
                >
                  {busy === "download"
                    ? "Preparing download…"
                    : "Download PowerPoint"}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy !== null || pendingClaims.length > 0}
                  onClick={() => void approve()}
                  className="primary-button"
                >
                  {busy === "approve" ? "Approving…" : "Approve presentation"}
                </button>
              )}
            </div>
          </section>
        </>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PlanReview({
  plan,
  busy,
  onToggle,
  onMove,
  onSave,
  onGenerate,
}: {
  plan: CreatePresentationPlanItem[];
  busy: boolean;
  onToggle: (id: string) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onSave: () => void;
  onGenerate: () => void;
}) {
  const included = [...plan.filter((item) => item.included)].sort(
    (left, right) => left.order - right.order,
  );
  return (
    <section className="form-card" aria-labelledby="plan-review-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Plan first
      </p>
      <h2 id="plan-review-title" className="form-legend mt-1">
        Review the deterministic slide plan
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Required template slides cannot be removed. Generation is limited to 30
        slides and uses only this reviewed plan.
      </p>
      <ol className="mt-5 space-y-3">
        {included.map((item, index) => (
          <li
            key={item.id}
            className="flex flex-col gap-4 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {index + 1} · {humanise(item.category)}
                {item.required ? " · required" : ""}
              </p>
              <h3 className="mt-1 font-semibold text-slate-950">
                {item.title}
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                {item.sourceClasses.map(humanise).join(" · ")}
                {item.exactTextRequired ? " · Exact approved text" : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={index === 0 || busy}
                onClick={() => onMove(index, -1)}
                className="secondary-button"
              >
                Move up
              </button>
              <button
                type="button"
                disabled={index === included.length - 1 || busy}
                onClick={() => onMove(index, 1)}
                className="secondary-button"
              >
                Move down
              </button>
              {!item.required ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onToggle(item.id)}
                  className="secondary-button"
                >
                  Remove
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      {plan.some((item) => !item.included) ? (
        <div className="mt-5 border-t border-slate-200 pt-5">
          <h3 className="text-sm font-semibold text-slate-950">
            Removed slides
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {plan
              .filter((item) => !item.included)
              .map((item) => (
                <button
                  key={item.id}
                  type="button"
                  disabled={busy}
                  onClick={() => onToggle(item.id)}
                  className="secondary-button"
                >
                  Restore {item.title}
                </button>
              ))}
          </div>
        </div>
      ) : null}
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={onSave}
          className="secondary-button"
        >
          Save plan
        </button>
        <button
          type="button"
          disabled={busy || included.length === 0}
          onClick={onGenerate}
          className="primary-button"
        >
          {busy ? "Working…" : "Generate from this plan"}
        </button>
      </div>
    </section>
  );
}

function GeneratedSlideCard({
  slide,
  presentationId,
  immutable,
  onUpdated,
  onError,
}: {
  slide: CreateGeneratedSlide;
  presentationId: string;
  immutable: boolean;
  onUpdated: (presentation: CreatePresentation) => void;
  onError: (message: string) => void;
}) {
  const editable =
    !immutable && !["locked", "reuse_as_is"].includes(slide.modificationPolicy);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(slide.title);
  const [body, setBody] = useState(slide.bodyBlocks.join("\n\n"));
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const next = await apiRequest<CreatePresentation>(
        `/api/v1/create/presentations/${presentationId}/slides/${slide.planItemId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title,
            bodyBlocks: body
              .split(/\n\s*\n/u)
              .map((value) => value.trim())
              .filter(Boolean),
          }),
        },
      );
      setEditing(false);
      onUpdated(next);
    } catch (reason) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The slide edit could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Slide {slide.order} · {humanise(slide.modificationPolicy)}
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {slide.title}
          </h3>
        </div>
        <StateBadge state={slide.reviewState} />
      </div>
      {editing ? (
        <div className="mt-4 space-y-4">
          <label className="field-label block">
            Slide title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={240}
              className="field-input mt-2"
            />
          </label>
          <label className="field-label block">
            Body blocks (separate blocks with a blank line)
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={6}
              className="field-input mt-2"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void save()}
              className="primary-button"
            >
              {saving ? "Saving and re-rendering…" : "Save text edit"}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => setEditing(false)}
              className="secondary-button"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-4 space-y-2 text-sm leading-6 text-slate-700">
            {slide.bodyBlocks.map((block, index) => (
              <p
                key={`${slide.planItemId}-${index}`}
                className="whitespace-pre-wrap"
              >
                {block}
              </p>
            ))}
          </div>
          {editable ? (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="secondary-button mt-4"
            >
              Edit permitted text
            </button>
          ) : null}
        </>
      )}
    </article>
  );
}

function Detail({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-sm text-slate-900">{children}</p>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  return (
    <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
      {humanise(state)}
    </span>
  );
}
