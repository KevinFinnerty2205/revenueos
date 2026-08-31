"use client";

import type {
  BusinessCaseList,
  CreateAvailability,
  CreatePresentationList,
  CreateTemplateList,
  CreateTemplateSummary,
  ValueModelList,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const PPTX_MIME =
  "application/vnd.openxmlformats-officedocument.presentationml.presentation";

async function filePayload(file: File): Promise<{
  contentBase64: string;
  checksumSha256: string;
}> {
  const content = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", content);
  const checksumSha256 = Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  const bytes = new Uint8Array(content);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8_192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8_192));
  }
  return { contentBase64: btoa(binary), checksumSha256 };
}

export function CreateStudio() {
  const [availability, setAvailability] = useState<CreateAvailability | null>(
    null,
  );
  const [templates, setTemplates] = useState<CreateTemplateList | null>(null);
  const [presentations, setPresentations] =
    useState<CreatePresentationList | null>(null);
  const [businessCases, setBusinessCases] = useState<BusinessCaseList | null>(
    null,
  );
  const [valueModels, setValueModels] = useState<ValueModelList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    const nextAvailability = await apiRequest<CreateAvailability>(
      "/api/v1/create/availability",
      { signal },
    );
    setAvailability(nextAvailability);
    if (!nextAvailability.enabled) return;
    const [
      nextTemplates,
      nextPresentations,
      nextBusinessCases,
      nextValueModels,
    ] = await Promise.all([
      apiRequest<CreateTemplateList>("/api/v1/create/templates", { signal }),
      apiRequest<CreatePresentationList>("/api/v1/create/presentations", {
        signal,
      }),
      apiRequest<BusinessCaseList>("/api/v1/create/business-cases", { signal }),
      apiRequest<ValueModelList>("/api/v1/create/value-models", { signal }),
    ]);
    setTemplates(nextTemplates);
    setPresentations(nextPresentations);
    setBusinessCases(nextBusinessCases);
    setValueModels(nextValueModels);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setError(null);
      void load(controller.signal).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Create could not be loaded.",
        );
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("template");
    const name = String(data.get("name") ?? "").trim();
    const authorityAttested = data.get("authority") === "on";
    if (!(file instanceof File) || file.size === 0 || !name) {
      setUploadMessage("Choose a named PPTX template.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      setUploadMessage("Create accepts PowerPoint .pptx templates only.");
      return;
    }
    if (!authorityAttested) {
      setUploadMessage(
        "Confirm your authority to upload and reuse this template.",
      );
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const payload = await filePayload(file);
      const created = await apiRequest<CreateTemplateSummary>(
        "/api/v1/create/templates",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            fileName: file.name,
            mimeType: PPTX_MIME,
            ...payload,
            authorityAttested: true,
            attestationVersion: 1,
          }),
        },
      );
      form.reset();
      setUploadMessage(
        `${created.name} is processing. Review every slide before approval.`,
      );
      await load();
    } catch (reason) {
      setUploadMessage(
        reason instanceof Error
          ? reason.message
          : "The template could not be uploaded.",
      );
    } finally {
      setUploading(false);
    }
  }

  if (error) {
    return (
      <CreateError
        message={error}
        onRetry={() => setRetryKey((value) => value + 1)}
      />
    );
  }
  if (!availability) {
    return <p role="status">Loading Create…</p>;
  }
  if (!availability.enabled) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="RevenueOS Create"
          title="Sales Content Studio"
          description="Build reviewed, traceable customer presentations from approved company content."
        />
        <section
          className="form-card"
          aria-labelledby="create-unavailable-title"
        >
          <h2 id="create-unavailable-title" className="form-legend">
            {availability.message}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            An organisation administrator can manage the Create add-on in
            Settings. Your existing Accounts, Opportunities and Evidence are
            unchanged.
          </p>
          <Link href="/settings" className="secondary-button mt-5">
            View workspace settings
          </Link>
        </section>
      </div>
    );
  }

  const approvedTemplates =
    templates?.items.filter(
      (item) => item.latestVersion.approvalState === "approved",
    ) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="RevenueOS Create"
        title="Sales Content Studio"
        description="Plan first, generate from approved sources, review every claim, then download an editable PowerPoint."
        actions={
          <div className="flex flex-wrap gap-3">
            <Link href="/create/business-cases/new" className="primary-button">
              New Business Case
            </Link>
            <Link
              href="/create/presentations/new"
              className="secondary-button"
              aria-disabled={approvedTemplates.length === 0}
            >
              New presentation
            </Link>
          </div>
        }
      />

      <section aria-labelledby="business-cases-title" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
              Transparent value modelling
            </p>
            <h2
              id="business-cases-title"
              className="mt-1 text-2xl font-semibold text-slate-950"
            >
              Business Cases
            </h2>
          </div>
          {valueModels?.canManage ? (
            <Link href="/create/value-models" className="secondary-button">
              Manage Value Models
            </Link>
          ) : null}
        </div>
        {valueModels &&
        !valueModels.items.some(
          (item) => item.latestVersion.state === "approved",
        ) ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
            <h3 className="font-semibold text-amber-950">
              No approved Value Models available
            </h3>
            <p className="mt-2 text-sm leading-6 text-amber-900">
              An administrator must define and approve the typed inputs, bounded
              formulas and visible assumptions first.
            </p>
          </div>
        ) : businessCases?.items.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {businessCases.items.map((item) => {
              const base = item.currentVersion?.scenarios.find(
                (scenario) => scenario.name === "base",
              );
              const headline = base?.outputs.find((output) => output.highlight);
              return (
                <Link
                  key={item.id}
                  href={`/create/business-cases/${item.id}`}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-semibold text-slate-950">
                        {item.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {item.accountName}
                        {item.opportunityName
                          ? ` · ${item.opportunityName}`
                          : ""}
                      </p>
                    </div>
                    <StateBadge state={item.state} />
                  </div>
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {item.modelName} · model v{item.modelVersion}
                  </p>
                  {headline ? (
                    <p className="mt-2 text-sm text-slate-800">
                      Base case · {headline.label}:{" "}
                      {formatBusinessOutput(
                        headline.displayValue,
                        headline.unit,
                        item.currency,
                      )}
                    </p>
                  ) : null}
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <h3 className="font-semibold text-slate-950">
              Build a credible customer business case
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Use explicit inputs and your organisation’s approved deterministic
              model—never invented benchmarks.
            </p>
            <Link
              href="/create/business-cases/new"
              className="primary-button mt-5"
            >
              Create Business Case
            </Link>
          </div>
        )}
      </section>

      {approvedTemplates.length === 0 ? (
        <section className="rounded-3xl border border-teal-200 bg-teal-50 p-6 sm:p-8">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            First use
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-teal-950">
            Approve a company presentation template first
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-teal-900">
            An administrator uploads a company-approved PPTX, reviews each
            slide, classifies reuse and edit rules, and approves an immutable
            template version. Create will not generate without that approval.
          </p>
        </section>
      ) : null}

      <section aria-labelledby="presentations-title" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
              Studio
            </p>
            <h2
              id="presentations-title"
              className="mt-1 text-2xl font-semibold text-slate-950"
            >
              Presentations
            </h2>
          </div>
          <p className="text-sm text-slate-500">
            {presentations?.items.length ?? 0} in this organisation
          </p>
        </div>
        {presentations?.items.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {presentations.items.map((item) => (
              <Link
                key={item.id}
                href={`/create/presentations/${item.id}`}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-slate-950">
                      {item.title}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {item.accountName}
                      {item.opportunityName ? ` · ${item.opportunityName}` : ""}
                    </p>
                  </div>
                  <StateBadge state={item.state} />
                </div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {humanise(item.objective)} · {item.templateName} v
                  {item.templateVersion}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <h3 className="font-semibold text-slate-950">
              No presentations yet
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Start with an Account, objective, audience and approved template.
            </p>
          </div>
        )}
      </section>

      <section aria-labelledby="templates-title" className="space-y-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Controlled source content
          </p>
          <h2
            id="templates-title"
            className="mt-1 text-2xl font-semibold text-slate-950"
          >
            Presentation templates
          </h2>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {templates?.items.map((item) => (
            <Link
              key={item.id}
              href={`/create/templates/${item.id}`}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-slate-950">{item.name}</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Version {item.latestVersion.version} ·{" "}
                    {item.latestVersion.slideCount} slides
                  </p>
                </div>
                <StateBadge
                  state={
                    item.latestVersion.approvalState === "approved"
                      ? "approved"
                      : item.latestVersion.processingState
                  }
                />
              </div>
              {item.latestVersion.warningCodes.length ? (
                <p className="mt-3 text-xs text-amber-800">
                  Review:{" "}
                  {item.latestVersion.warningCodes.map(humanise).join(", ")}
                </p>
              ) : null}
            </Link>
          ))}
        </div>
      </section>

      {availability.canUploadTemplates ? (
        <form onSubmit={(event) => void upload(event)} className="form-card">
          <fieldset disabled={uploading}>
            <legend className="form-legend">
              Upload an approved company PPTX
            </legend>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              PPTX only, up to 50 MB and 100 slides. Macros, embedded objects,
              external relationships and unsafe media are rejected. Notes and
              comments never enter approved content.
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="field-label">
                Template name
                <input
                  name="name"
                  required
                  maxLength={200}
                  className="field-input mt-2"
                />
              </label>
              <label className="field-label">
                PowerPoint template
                <input
                  name="template"
                  type="file"
                  required
                  accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                  className="field-input mt-2"
                />
              </label>
            </div>
            <label className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-700">
              <input
                name="authority"
                type="checkbox"
                required
                className="mt-1 h-4 w-4"
              />
              <span>
                I confirm that I am authorised to upload this company content
                and approve it for customer-facing reuse in RevenueOS.
              </span>
            </label>
            <button type="submit" className="primary-button mt-5">
              {uploading ? "Checking and uploading…" : "Upload for review"}
            </button>
            {uploadMessage ? (
              <p role="status" className="mt-4 text-sm text-slate-700">
                {uploadMessage}
              </p>
            ) : null}
          </fieldset>
        </form>
      ) : null}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  return (
    <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
      {humanise(state)}
    </span>
  );
}

function CreateError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <section className="form-card" aria-labelledby="create-error-title">
      <h1 id="create-error-title" className="form-legend">
        Create is unavailable
      </h1>
      <p role="alert" className="mt-2 text-sm text-slate-700">
        {message}
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <button type="button" className="secondary-button" onClick={onRetry}>
          Try again
        </button>
        <Link href="/dashboard" className="secondary-button">
          Return Home
        </Link>
      </div>
    </section>
  );
}

function formatBusinessOutput(
  value: string | null,
  unit: string,
  currency: string,
) {
  if (value === null) return "Not achieved under these assumptions";
  if (unit === "currency" || unit === "currency_per_year")
    return `${currency} ${value}`;
  if (unit === "percentage") return `${value}%`;
  return `${value} ${humanise(unit)}`;
}
