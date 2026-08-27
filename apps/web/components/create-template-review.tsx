"use client";

import type {
  CreateModificationPolicy,
  CreateSlideCategory,
  CreateTemplateSlide,
  CreateTemplateSummary,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const categories: CreateSlideCategory[] = [
  "title",
  "agenda",
  "company_overview",
  "problem",
  "solution",
  "product",
  "capability",
  "architecture",
  "case_study",
  "proof_point",
  "process",
  "pricing_placeholder",
  "next_steps",
  "appendix",
  "unknown",
];

export function CreateTemplateReview({ templateId }: { templateId: string }) {
  const [template, setTemplate] = useState<CreateTemplateSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);

  const load = useCallback(async () => {
    const next = await apiRequest<CreateTemplateSummary>(
      `/api/v1/create/templates/${templateId}`,
    );
    setTemplate(next);
    setError(null);
    return next;
  }, [templateId]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const next = await load();
        if (active && next.latestVersion.processingState === "processing") {
          timer = setTimeout(() => void refresh(), 2_000);
        }
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "The template could not be loaded.",
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

  async function approve() {
    if (!template) return;
    setApproving(true);
    setError(null);
    try {
      const next = await apiRequest<CreateTemplateSummary>(
        `/api/v1/create/templates/${template.id}/versions/${template.latestVersion.id}/approve`,
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      setTemplate(next);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The template could not be approved.",
      );
    } finally {
      setApproving(false);
    }
  }

  if (error && !template) {
    return (
      <p role="alert" className="rounded-xl bg-rose-50 p-4 text-rose-900">
        {error}
      </p>
    );
  }
  if (!template) return <p role="status">Loading template review…</p>;
  const version = template.latestVersion;
  const pendingCount = version.slides.filter(
    (slide) => slide.reuseState === "pending",
  ).length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Create · Template control"
        title={template.name}
        description={`Version ${version.version} · ${version.slideCount} slides · ${humanise(version.processingState)}`}
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> Template review
      </nav>

      {version.processingState === "processing" ? (
        <section className="form-card">
          <h2 className="form-legend">Secure processing is running</h2>
          <p role="status" className="mt-2 text-sm leading-6 text-slate-600">
            RevenueOS is checking the PPTX package and extracting a bounded
            slide structure. No slide content is approved automatically.
          </p>
        </section>
      ) : version.processingState === "failed" ? (
        <section className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
          <h2 className="font-semibold text-rose-950">
            Template processing failed
          </h2>
          <p className="mt-2 text-sm text-rose-900">
            Safe failure code:{" "}
            {version.safeFailureCode ?? "pptx_processing_failed"}
          </p>
        </section>
      ) : (
        <>
          {version.warningCodes.length ? (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
              <h2 className="font-semibold text-amber-950">
                Review processing warnings
              </h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">
                {version.warningCodes.map((warning) => (
                  <li key={warning}>{humanise(warning)}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section aria-labelledby="slide-review-title" className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
                  Human approval boundary
                </p>
                <h2
                  id="slide-review-title"
                  className="mt-1 text-2xl font-semibold text-slate-950"
                >
                  Review every slide
                </h2>
              </div>
              <p className="text-sm text-slate-600">
                {pendingCount} pending · {version.approvedSlideCount} approved
              </p>
            </div>
            <div className="space-y-4">
              {version.slides.map((slide) => (
                <SlideReview
                  key={`${slide.id}-${slide.updatedAt}`}
                  slide={slide}
                  immutable={version.approvalState === "approved"}
                  onSaved={setTemplate}
                />
              ))}
            </div>
          </section>

          <section
            className="form-card"
            aria-labelledby="approve-template-title"
          >
            <h2 id="approve-template-title" className="form-legend">
              Approve immutable template version
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Approval creates the controlled content library for this version.
              Required and exact-text slides remain locked. Upload a new PPTX
              version for later source changes.
            </p>
            {version.approvalState === "approved" ? (
              <p role="status" className="mt-4 font-semibold text-teal-800">
                Approved for customer-facing presentation generation.
              </p>
            ) : (
              <button
                type="button"
                disabled={
                  approving ||
                  pendingCount > 0 ||
                  version.approvedSlideCount === 0
                }
                onClick={() => void approve()}
                className="primary-button mt-5"
              >
                {approving ? "Approving…" : "Approve template version"}
              </button>
            )}
            {error ? (
              <p role="alert" className="mt-4 text-sm text-rose-800">
                {error}
              </p>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}

function SlideReview({
  slide,
  immutable,
  onSaved,
}: {
  slide: CreateTemplateSlide;
  immutable: boolean;
  onSaved: (template: CreateTemplateSummary) => void;
}) {
  const [reuseState, setReuseState] = useState(slide.reuseState);
  const [category, setCategory] = useState(slide.category);
  const [policy, setPolicy] = useState<CreateModificationPolicy>(
    slide.modificationPolicy,
  );
  const [customerSafe, setCustomerSafe] = useState(slide.customerSafe);
  const [required, setRequired] = useState(slide.required);
  const [exact, setExact] = useState(slide.exactTextRequired);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const next = await apiRequest<CreateTemplateSummary>(
        `/api/v1/create/template-slides/${slide.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            category,
            reuseState,
            modificationPolicy: exact ? "locked" : policy,
            customerSafe: reuseState === "approved" ? true : customerSafe,
            required,
            exactTextRequired: exact,
            approvedDescription:
              reuseState === "approved"
                ? "Approved for customer-facing reuse."
                : null,
            placeholderMappings: {},
          }),
        },
      );
      onSaved(next);
      setMessage("Slide review saved.");
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The slide review could not be saved.",
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
            Slide {slide.slideNumber}
            {slide.hidden ? " · hidden in source" : ""}
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {slide.title}
          </h3>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
          {humanise(reuseState)}
        </span>
      </div>
      <div className="mt-4 rounded-xl bg-slate-50 p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          Extracted text · visual styling remains in the PPTX
        </p>
        <div className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
          {slide.textBlocks.length ? (
            slide.textBlocks.map((block) => (
              <p key={block.shapeId} className="whitespace-pre-wrap">
                {block.text}
              </p>
            ))
          ) : (
            <p>No reusable text was detected.</p>
          )}
        </div>
      </div>
      {!immutable ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="field-label">
            Reuse decision
            <select
              value={reuseState}
              onChange={(event) => {
                const next = event.target.value as typeof reuseState;
                setReuseState(next);
                if (next !== "approved") {
                  setRequired(false);
                  setExact(false);
                }
              }}
              className="field-input mt-2"
            >
              <option value="pending">Pending review</option>
              <option value="approved">Approve for reuse</option>
              <option value="excluded">Exclude</option>
            </select>
          </label>
          <label className="field-label">
            Category
            <select
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as CreateSlideCategory)
              }
              className="field-input mt-2"
            >
              {categories.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Modification policy
            <select
              value={exact ? "locked" : policy}
              disabled={exact}
              onChange={(event) =>
                setPolicy(event.target.value as CreateModificationPolicy)
              }
              className="field-input mt-2"
            >
              <option value="text_placeholders_only">
                Text placeholders only
              </option>
              <option value="editable_text">Bounded text edit</option>
              <option value="reuse_as_is">Reuse as is</option>
              <option value="locked">Locked</option>
            </select>
          </label>
          <label className="flex items-center gap-3 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={reuseState === "approved" ? true : customerSafe}
              disabled={reuseState === "approved"}
              onChange={(event) => setCustomerSafe(event.target.checked)}
            />
            Customer-safe
          </label>
          <label className="flex items-center gap-3 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={required}
              disabled={reuseState !== "approved"}
              onChange={(event) => setRequired(event.target.checked)}
            />
            Required in every deck
          </label>
          <label className="flex items-center gap-3 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={exact}
              disabled={reuseState !== "approved"}
              onChange={(event) => {
                setExact(event.target.checked);
                if (event.target.checked) setPolicy("locked");
              }}
            />
            Exact text required
          </label>
          <div className="sm:col-span-2 lg:col-span-3">
            <button
              type="button"
              disabled={saving}
              onClick={() => void save()}
              className="secondary-button"
            >
              {saving ? "Saving…" : "Save slide review"}
            </button>
            {message ? (
              <span role="status" className="ml-3 text-sm text-slate-600">
                {message}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
