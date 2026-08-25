"use client";

import type {
  ProspectPromotion,
  ProspectResearchBrief,
  ProspectResearchChange,
  ProspectResearchObservation,
  ProspectResearchSource,
  ProspectTrustState,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";

const trustLabels: Record<ProspectTrustState, string> = {
  verified: "Verified",
  provider_supplied: "From data provider",
  inferred: "RevenueOS inference",
  unknown: "Not established",
};

const trustDescriptions: Record<ProspectTrustState, string> = {
  verified: "Supported directly by an authoritative public source.",
  provider_supplied: "Supplied by an external business-data provider.",
  inferred: "A hypothesis based on sourced public information.",
  unknown: "RevenueOS could not verify this reliably.",
};

const overviewCategories = new Set([
  "company_profile",
  "industry",
  "location",
  "business_model",
  "product_service",
]);
const developmentCategories = new Set([
  "strategic_initiative",
  "expansion",
  "hiring",
  "leadership_change",
  "funding_financial",
  "regulatory",
  "partnership",
  "trigger",
]);

function formatDate(value: string | null | undefined): string {
  if (!value) return "Date not available";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

function humanise(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./u, (letter) => letter.toUpperCase());
}

export function ProspectTrustLabel({ state }: { state: ProspectTrustState }) {
  const styles: Record<ProspectTrustState, string> = {
    verified: "border-emerald-200 bg-emerald-50 text-emerald-900",
    provider_supplied: "border-sky-200 bg-sky-50 text-sky-900",
    inferred: "border-amber-200 bg-amber-50 text-amber-950",
    unknown: "border-slate-200 bg-slate-100 text-slate-700",
  };
  return (
    <span
      title={trustDescriptions[state]}
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold ${styles[state]}`}
    >
      {trustLabels[state]}
    </span>
  );
}

export function ProspectResearchBriefView({ targetId }: { targetId: string }) {
  const [brief, setBrief] = useState<ProspectResearchBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [promotionOpen, setPromotionOpen] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promotion, setPromotion] = useState<ProspectPromotion | null>(null);
  const confirmationHeading = useRef<HTMLHeadingElement>(null);
  const promotionDialog = useRef<HTMLDivElement>(null);
  const promotionTrigger = useRef<HTMLButtonElement>(null);

  const load = useCallback(async () => {
    try {
      setBrief(
        await apiRequest<ProspectResearchBrief>(
          `/api/v1/prospect/research/${targetId}`,
        ),
      );
      setError(null);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Company research could not be loaded.",
      );
    }
  }, [targetId]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectResearchBrief>(`/api/v1/prospect/research/${targetId}`, {
      signal: controller.signal,
    })
      .then((nextBrief) => {
        setBrief(nextBrief);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Company research could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, [targetId]);

  useEffect(() => {
    if (brief?.status !== "pending" && brief?.status !== "researching") return;
    const timer = window.setInterval(() => void load(), 1_500);
    return () => window.clearInterval(timer);
  }, [brief?.status, load]);

  useEffect(() => {
    if (!promotionOpen) return;
    const trigger = promotionTrigger.current;
    confirmationHeading.current?.focus();
    function manageDialogKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPromotionOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const controls = promotionDialog.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!controls || controls.length === 0) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      const active = document.activeElement;
      if (
        event.shiftKey &&
        (active === first || active === confirmationHeading.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", manageDialogKeyboard);
    return () => {
      window.removeEventListener("keydown", manageDialogKeyboard);
      trigger?.focus();
    };
  }, [promotionOpen]);

  const sourceById = useMemo(
    () => new Map(brief?.sources.map((source) => [source.id, source]) ?? []),
    [brief?.sources],
  );

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      setBrief(
        await apiRequest<ProspectResearchBrief>(
          `/api/v1/prospect/research/${targetId}/refresh`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotencyKey: `refresh:${crypto.randomUUID()}`,
            }),
          },
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Research could not be refreshed.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function confirmPromotion() {
    if (!brief) return;
    setPromoting(true);
    setError(null);
    try {
      const result = await apiRequest<ProspectPromotion>(
        `/api/v1/prospect/research/${targetId}/promote`,
        {
          method: "POST",
          body: JSON.stringify({
            confirmed: true,
            existingCompanyId: brief.existingCompanyMatch?.id ?? null,
          }),
        },
      );
      setPromotion(result);
      setBrief({
        ...brief,
        target: {
          ...brief.target,
          promotedCompanyId: result.companyId,
          promotedAt: new Date().toISOString(),
        },
      });
      setPromotionOpen(false);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The company could not be added to Sales.",
      );
      setPromotionOpen(false);
    } finally {
      setPromoting(false);
    }
  }

  if (error && !brief) {
    return (
      <section className="rounded-3xl border border-rose-200 bg-rose-50 p-7">
        <h1 className="text-2xl font-semibold text-rose-950">
          Research unavailable
        </h1>
        <p role="alert" className="mt-3 text-sm text-rose-900">
          {error}
        </p>
        <Link href="/find" className="secondary-button mt-5">
          Choose another company
        </Link>
      </section>
    );
  }

  if (!brief) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading company research…
      </p>
    );
  }

  const observations = brief.observations;
  const overview = observations.filter(
    (item) =>
      overviewCategories.has(item.category) && item.trustState !== "unknown",
  );
  const recent = observations
    .filter(
      (item) =>
        item.trustState !== "unknown" &&
        (Boolean(item.observedAt) || developmentCategories.has(item.category)),
    )
    .slice(0, 5);
  const hypotheses = observations.filter(
    (item) => item.trustState === "inferred",
  );
  const unknown = observations.filter((item) => item.trustState === "unknown");
  const usefulFacts = observations.filter(
    (item) =>
      item.relevance === "high" &&
      (item.trustState === "verified" ||
        item.trustState === "provider_supplied"),
  );
  const businessContext = observations.filter(
    (item) =>
      item.trustState !== "unknown" &&
      item.trustState !== "inferred" &&
      !overview.includes(item) &&
      !recent.includes(item),
  );
  const isProcessing =
    brief.status === "pending" || brief.status === "researching";
  const promotedCompanyId =
    promotion?.companyId ?? brief.target.promotedCompanyId;

  return (
    <article className="space-y-7">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <Link
          href="/find"
          className="text-sm font-bold text-teal-700 hover:text-teal-900"
        >
          ← Back to Find
        </Link>
        <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
              Account Research
            </p>
            <h1 className="mt-2 break-words text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              {brief.target.name}
            </h1>
            <p className="mt-2 break-all text-sm font-semibold text-teal-800">
              {brief.target.domain}
            </p>
            {brief.target.location ? (
              <p className="mt-1 text-sm text-slate-600">
                {brief.target.location}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {promotedCompanyId ? (
              <Link
                href={`/companies/${promotedCompanyId}`}
                className="primary-button"
              >
                Open account
              </Link>
            ) : !isProcessing && brief.status !== "failed" ? (
              <button
                ref={promotionTrigger}
                type="button"
                className="primary-button"
                onClick={() => setPromotionOpen(true)}
              >
                Add to Sales
              </button>
            ) : null}
            {!isProcessing && brief.status !== "failed" ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void refresh()}
                disabled={refreshing}
              >
                {refreshing ? "Refreshing…" : "Refresh research"}
              </button>
            ) : null}
          </div>
        </div>
        {brief.status === "failed" ? null : <ResearchStatus brief={brief} />}
        {brief.currentRun?.completedAt ? (
          <p className="mt-3 text-xs text-slate-500">
            Research updated {formatDate(brief.currentRun.completedAt)} ·{" "}
            {brief.sources.length} public
            {brief.sources.length === 1 ? " source" : " sources"}
          </p>
        ) : null}
        {promotion ? (
          <p
            role="status"
            className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-950"
          >
            Added to Sales. {promotion.message}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="mt-4 text-sm font-medium text-rose-700">
            {error}
          </p>
        ) : null}
      </header>

      {isProcessing ? (
        <section
          className="rounded-3xl border border-teal-100 bg-teal-50/70 p-7"
          aria-live="polite"
        >
          <h2 className="text-xl font-semibold text-teal-950">
            Researching company…
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-teal-900">
            RevenueOS is checking permitted public business sources. You can
            leave this page and come back.
          </p>
        </section>
      ) : brief.status === "failed" ? (
        <section className="rounded-3xl border border-rose-200 bg-rose-50 p-7">
          <h2 className="text-xl font-semibold text-rose-950">
            Couldn’t complete research
          </h2>
          <p className="mt-2 text-sm leading-6 text-rose-900">
            RevenueOS couldn’t find enough reliable public information about
            this company.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              className="primary-button"
              onClick={() => void refresh()}
            >
              Try again
            </button>
            <a
              href={brief.target.websiteUrl}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
              className="secondary-button"
            >
              Check company website ↗
            </a>
          </div>
        </section>
      ) : (
        <>
          <ResearchSection
            title="Overview"
            description="What does this company do?"
          >
            <ObservationList
              items={overview}
              sourceById={sourceById}
              empty="No concise profile was established."
            />
          </ResearchSection>

          <ResearchSection
            title="Why this may matter"
            description="Public facts and cautious hypotheses to explore—not customer-confirmed needs."
          >
            {usefulFacts.length > 0 ? (
              <ObservationGroup
                label="Public business context"
                items={usefulFacts}
                sourceById={sourceById}
              />
            ) : null}
            {hypotheses.length > 0 ? (
              <ObservationGroup
                label="Possible sales relevance"
                items={hypotheses}
                sourceById={sourceById}
              />
            ) : null}
            {usefulFacts.length === 0 && hypotheses.length === 0 ? (
              <p className="text-sm text-slate-600">
                No supported sales context was established.
              </p>
            ) : null}
          </ResearchSection>

          {recent.length > 0 ? (
            <ResearchSection
              title="Recent developments"
              description="Dated, source-backed public developments."
            >
              <div className="grid gap-3">
                {recent.map((item) => (
                  <DevelopmentCard
                    key={item.id}
                    item={item}
                    sourceById={sourceById}
                  />
                ))}
              </div>
            </ResearchSection>
          ) : null}

          {businessContext.length > 0 ? (
            <ResearchSection
              title="Business context"
              description="Additional useful public company context."
            >
              <ObservationList
                items={businessContext}
                sourceById={sourceById}
              />
            </ResearchSection>
          ) : null}

          {unknown.length > 0 ? (
            <ResearchSection
              title="Not established"
              description="Relevant facts RevenueOS did not guess."
            >
              <ObservationList items={unknown} sourceById={sourceById} />
            </ResearchSection>
          ) : null}

          {brief.changes.length > 0 ? (
            <Changes changes={brief.changes} />
          ) : null}

          <Sources sources={brief.sources} />

          <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <summary className="cursor-pointer font-semibold text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600">
              Research history
            </summary>
            <div className="mt-4 space-y-3">
              {brief.history.map((run, index) => (
                <div
                  key={run.id}
                  className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-3 text-sm"
                >
                  <span className="font-medium text-slate-800">
                    {index === 0 ? "Current research" : "Previous research"}
                  </span>
                  <span className="text-slate-500">
                    {formatDate(run.completedAt ?? run.createdAt)} ·{" "}
                    {run.observationCount} findings
                  </span>
                </div>
              ))}
            </div>
          </details>
        </>
      )}

      {promotionOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="promotion-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <div
            ref={promotionDialog}
            className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl sm:p-8"
          >
            <h2
              id="promotion-title"
              ref={confirmationHeading}
              tabIndex={-1}
              className="text-2xl font-semibold tracking-tight text-slate-950 outline-none"
            >
              {brief.existingCompanyMatch
                ? "This company is already in RevenueOS"
                : `Add ${brief.target.name} to Sales?`}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {brief.existingCompanyMatch
                ? `Attach this public research to ${brief.existingCompanyMatch.name}. No duplicate Account will be created.`
                : "This creates a RevenueOS Account using the reviewed company details. It will not create an Opportunity or Contact automatically."}
            </p>
            <dl className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm">
              <div>
                <dt className="font-semibold text-slate-500">Company</dt>
                <dd className="mt-1 text-slate-950">{brief.target.name}</dd>
              </div>
              <div className="mt-3">
                <dt className="font-semibold text-slate-500">
                  Official domain
                </dt>
                <dd className="mt-1 break-all text-slate-950">
                  {brief.target.domain}
                </dd>
              </div>
            </dl>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPromotionOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={promoting}
                onClick={() => void confirmPromotion()}
              >
                {promoting
                  ? "Saving…"
                  : brief.existingCompanyMatch
                    ? "Attach research"
                    : "Add account"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function ResearchStatus({ brief }: { brief: ProspectResearchBrief }) {
  const content = {
    pending: ["Researching company…", "bg-teal-50 text-teal-950"],
    researching: ["Researching company…", "bg-teal-50 text-teal-950"],
    ready: ["Research ready", "bg-emerald-50 text-emerald-950"],
    partial: ["Research incomplete", "bg-amber-50 text-amber-950"],
    failed: ["Couldn’t complete research", "bg-rose-50 text-rose-950"],
  }[brief.status];
  return (
    <div
      role="status"
      className={`mt-5 rounded-xl px-4 py-3 text-sm ${content[1]}`}
    >
      <span className="font-bold">{content[0]}</span>
      <span className="ml-2">{brief.statusMessage}</span>
    </div>
  );
}

function ResearchSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
      <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
      <p className="mt-1 text-sm text-slate-500">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ObservationGroup({
  label,
  items,
  sourceById,
}: {
  label: string;
  items: ProspectResearchObservation[];
  sourceById: Map<string, ProspectResearchSource>;
}) {
  return (
    <div className="mt-5 first:mt-0">
      <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-slate-500">
        {label}
      </h3>
      <ObservationList items={items} sourceById={sourceById} />
    </div>
  );
}

function ObservationList({
  items,
  sourceById,
  empty,
}: {
  items: ProspectResearchObservation[];
  sourceById: Map<string, ProspectResearchSource>;
  empty?: string;
}) {
  if (items.length === 0)
    return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="mt-3 space-y-4">
      {items.map((item) => (
        <li key={item.id} className="border-l-2 border-slate-200 pl-4">
          <div className="flex flex-wrap items-center gap-2">
            <ProspectTrustLabel state={item.trustState} />
            <span className="text-xs font-semibold text-slate-500">
              {humanise(item.category)}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-800">
            {item.statement}
          </p>
          <ObservationSources item={item} sourceById={sourceById} />
        </li>
      ))}
    </ul>
  );
}

function ObservationSources({
  item,
  sourceById,
}: {
  item: ProspectResearchObservation;
  sourceById: Map<string, ProspectResearchSource>;
}) {
  const sources = item.sourceIds
    .map((sourceId) => sourceById.get(sourceId))
    .filter((source): source is ProspectResearchSource => Boolean(source));
  if (sources.length === 0) return null;
  return (
    <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
      {sources.map((source) => (
        <a
          key={source.id}
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          referrerPolicy="no-referrer"
          className="font-bold text-teal-700 underline decoration-teal-200 underline-offset-2 hover:text-teal-900"
        >
          {source.publisher} ↗
        </a>
      ))}
    </p>
  );
}

function DevelopmentCard({
  item,
  sourceById,
}: {
  item: ProspectResearchObservation;
  sourceById: Map<string, ProspectResearchSource>;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
          {formatDate(item.observedAt)}
        </span>
        <ProspectTrustLabel state={item.trustState} />
      </div>
      <p className="mt-3 text-sm font-medium leading-6 text-slate-900">
        {item.statement}
      </p>
      <ObservationSources item={item} sourceById={sourceById} />
    </article>
  );
}

function Changes({ changes }: { changes: ProspectResearchChange[] }) {
  const grouped = {
    new: changes.filter((item) => item.changeType === "new"),
    changed: changes.filter((item) => item.changeType === "changed"),
    no_longer_supported: changes.filter(
      (item) => item.changeType === "no_longer_supported",
    ),
  };
  const labels = {
    new: "New",
    changed: "Changed",
    no_longer_supported: "No longer supported",
  };
  return (
    <ResearchSection
      title="What changed"
      description="A deterministic comparison with the previous successful research."
    >
      <div className="grid gap-5 sm:grid-cols-3">
        {(Object.keys(grouped) as Array<keyof typeof grouped>).map((key) =>
          grouped[key].length > 0 ? (
            <div key={key}>
              <h3 className="text-sm font-bold text-slate-900">
                {labels[key]}
              </h3>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
                {grouped[key].map((item) => (
                  <li key={`${key}-${item.observationKey}`}>
                    {item.statement}
                  </li>
                ))}
              </ul>
            </div>
          ) : null,
        )}
      </div>
    </ResearchSection>
  );
}

function Sources({ sources }: { sources: ProspectResearchSource[] }) {
  return (
    <ResearchSection
      title="Sources"
      description="Public source metadata only. RevenueOS does not mirror full webpages."
    >
      <ul className="divide-y divide-slate-100">
        {sources.map((source) => (
          <li
            key={source.id}
            className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-semibold text-slate-950">{source.title}</p>
              <p className="mt-1 text-xs text-slate-500">
                {source.publisher} · {humanise(source.authorityClass)} ·{" "}
                {formatDate(source.publishedAt)}
              </p>
            </div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
              className="text-sm font-bold text-teal-700 hover:text-teal-900"
            >
              Open source ↗
            </a>
          </li>
        ))}
      </ul>
    </ResearchSection>
  );
}
