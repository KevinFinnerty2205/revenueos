"use client";

import type {
  ContactProspectResearchLink,
  ProspectBuyingRoleHypothesis,
  ProspectPersonDiscovery,
  ProspectPersonPromotion,
  ProspectPersonResearchBrief,
  ProspectResearchObservation,
  ProspectResearchSource,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiClientError, apiRequest } from "@/lib/api";
import { ProspectCreditAction } from "@/components/prospect-credit-action";
import { ProspectTrustLabel } from "@/components/prospect-research-brief";

function humanise(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./u, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Date not available";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export function ProspectPeopleSection({ targetId }: { targetId: string }) {
  const [discovery, setDiscovery] = useState<ProspectPersonDiscovery | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectPersonDiscovery>(
      `/api/v1/prospect/research/${targetId}/people`,
      { signal: controller.signal },
    )
      .then((nextDiscovery) => {
        setDiscovery(nextDiscovery);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Relevant people could not be loaded.",
          );
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [targetId]);

  async function discover() {
    setDiscovering(true);
    setError(null);
    try {
      setDiscovery(
        await apiRequest<ProspectPersonDiscovery>(
          `/api/v1/prospect/research/${targetId}/people/discover`,
          { method: "POST" },
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "RevenueOS could not find reliable professional people.",
      );
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">
            People worth understanding
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            Public professional context for likely relevant functions. These
            people are not Contacts until you explicitly add them to Sales.
          </p>
        </div>
        <button
          type="button"
          className="secondary-button shrink-0"
          disabled={discovering}
          onClick={() => void discover()}
        >
          {discovering
            ? "Finding people…"
            : discovery?.people.length
              ? "Refresh people"
              : "Find relevant people"}
        </button>
      </div>

      {loading ? (
        <p role="status" className="mt-5 text-sm text-slate-600">
          Loading relevant people…
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-5 text-sm font-medium text-rose-700">
          {error}
        </p>
      ) : null}

      {discovery && discovery.people.length === 0 && !loading ? (
        <div className="mt-5 rounded-2xl bg-slate-50 p-5">
          <p className="text-sm font-semibold text-slate-900">
            No people have been researched yet.
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            RevenueOS can look for a small, company-scoped set of public
            professional profiles. It does not scrape social networks or guess
            private details.
          </p>
        </div>
      ) : null}

      {discovery?.people.length ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {discovery.people.map((person) => (
            <article
              key={person.id}
              className="rounded-2xl border border-slate-200 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">
                    {person.displayName}
                  </h3>
                  <p className="mt-1 text-sm font-medium text-slate-700">
                    {person.currentRole}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {humanise(person.relevantFunction)} ·{" "}
                    {person.currentCompany}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-700">
                  {person.employmentState === "no_longer_current"
                    ? "Role may have changed"
                    : humanise(person.researchStatus)}
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-600">
                {person.whyMayMatter}
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <span className="text-xs text-slate-500">
                  {person.providerAttribution}
                </span>
                <Link
                  href={`/find/${targetId}/people/${person.id}`}
                  className="text-sm font-bold text-teal-700 hover:text-teal-900"
                >
                  {person.researchStatus === "not_started"
                    ? "Research person"
                    : "View professional research"}
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {discovery?.gaps.length ? (
        <div className="mt-5 rounded-2xl border border-dashed border-amber-300 bg-amber-50 p-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-900">
            Coverage gaps
          </p>
          <ul className="mt-2 space-y-1 text-sm text-amber-950">
            {discovery.gaps.map((gap) => (
              <li key={gap.role}>{gap.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {discovery?.functions.length ? (
        <details className="mt-5 rounded-2xl border border-slate-200 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-600">
            Functions RevenueOS considers
          </summary>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {discovery.functions.map((item) => (
              <div key={item.functionKey}>
                <p className="text-sm font-semibold text-slate-900">
                  {item.label}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {item.whyItMayMatter}
                </p>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

const profileCategories = new Set([
  "current_role",
  "current_company",
  "career_history",
  "responsibility",
  "expertise",
  "professional_interest",
]);
const activityCategories = new Set([
  "professional_activity",
  "public_statement",
  "authored_content",
  "conference_activity",
  "company_initiative",
]);
const contextCategories = new Set([
  "why_person_matters",
  "conversation_context",
]);

export function ProspectPersonResearchView({ personId }: { personId: string }) {
  const router = useRouter();
  const [brief, setBrief] = useState<ProspectPersonResearchBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [promotionOpen, setPromotionOpen] = useState(false);
  const [promotion, setPromotion] = useState<ProspectPersonPromotion | null>(
    null,
  );
  const [companyPromotionRequired, setCompanyPromotionRequired] =
    useState(false);
  const dialogHeading = useRef<HTMLHeadingElement>(null);
  const promotionDialog = useRef<HTMLDivElement>(null);
  const promotionTrigger = useRef<HTMLButtonElement>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setBrief(
          await apiRequest<ProspectPersonResearchBrief>(
            `/api/v1/prospect/people/${personId}`,
            { signal },
          ),
        );
        setError(null);
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Professional research could not be loaded.",
          );
        }
      }
    },
    [personId],
  );

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectPersonResearchBrief>(
      `/api/v1/prospect/people/${personId}`,
      { signal: controller.signal },
    )
      .then((nextBrief) => {
        setBrief(nextBrief);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Professional research could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, [personId]);

  useEffect(() => {
    if (brief?.status !== "pending" && brief?.status !== "researching") return;
    const timer = window.setInterval(() => void load(), 1_500);
    return () => window.clearInterval(timer);
  }, [brief?.status, load]);

  useEffect(() => {
    if (!promotionOpen) return;
    const trigger = promotionTrigger.current;
    dialogHeading.current?.focus();
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
        (active === first || active === dialogHeading.current)
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

  async function queueResearch(
    refresh: boolean,
    creditQuoteId: string | null,
    idempotencyKey: string,
  ): Promise<boolean> {
    setWorking(true);
    setError(null);
    setCompanyPromotionRequired(false);
    try {
      setBrief(
        await apiRequest<ProspectPersonResearchBrief>(
          `/api/v1/prospect/people/${personId}/${refresh ? "refresh" : "research"}`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotencyKey,
              creditQuoteId,
            }),
          },
        ),
      );
      return true;
    } catch (reason) {
      const needsCompany =
        reason instanceof ApiClientError &&
        reason.code === "company_not_in_sales";
      setCompanyPromotionRequired(needsCompany);
      setError(
        reason instanceof Error
          ? reason.message
          : "Professional research could not be started.",
      );
      return false;
    } finally {
      setWorking(false);
    }
  }

  async function reviewRole(
    hypothesis: ProspectBuyingRoleHypothesis,
    reviewState: "relevant" | "not_relevant",
  ) {
    if (!brief) return;
    setWorking(true);
    setError(null);
    try {
      const updated = await apiRequest<ProspectBuyingRoleHypothesis>(
        `/api/v1/prospect/people/${personId}/buying-roles/${hypothesis.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ role: hypothesis.role, reviewState }),
        },
      );
      setBrief({
        ...brief,
        buyingRoles: brief.buyingRoles.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      });
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "The review was not saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function promote(
    duplicateAction?: "attach_research" | "create_separate",
    existingContactId?: string,
  ) {
    setWorking(true);
    setError(null);
    setCompanyPromotionRequired(false);
    try {
      const result = await apiRequest<ProspectPersonPromotion>(
        `/api/v1/prospect/people/${personId}/promote`,
        {
          method: "POST",
          body: JSON.stringify({
            confirmed: true,
            duplicateAction: duplicateAction ?? null,
            existingContactId: existingContactId ?? null,
          }),
        },
      );
      setPromotion(result);
      setBrief((current) =>
        current
          ? {
              ...current,
              person: {
                ...current.person,
                promotedContactId: result.contactId,
                promotedAt: new Date().toISOString(),
              },
            }
          : current,
      );
      setPromotionOpen(false);
    } catch (reason) {
      const needsCompany =
        reason instanceof ApiClientError &&
        reason.code === "company_not_in_sales";
      setCompanyPromotionRequired(needsCompany);
      setError(
        reason instanceof Error
          ? reason.message
          : "This person could not be added to Sales.",
      );
      if (!(
        reason instanceof ApiClientError &&
        reason.code === "existing_contact_match"
      )) {
        setPromotionOpen(false);
      }
    } finally {
      setWorking(false);
    }
  }

  async function deleteResearch() {
    if (!brief) return;
    if (
      !window.confirm(
        "Delete this public professional research? Any promoted Contact will be preserved.",
      )
    )
      return;
    setWorking(true);
    try {
      await apiRequest<void>(`/api/v1/prospect/people/${personId}`, {
        method: "DELETE",
      });
      router.push(`/find/${brief.person.companyTargetId}`);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Research was not deleted.",
      );
      setWorking(false);
    }
  }

  if (error && !brief) {
    return (
      <section className="rounded-3xl border border-rose-200 bg-rose-50 p-7">
        <h1 className="text-2xl font-semibold text-rose-950">
          Professional research unavailable
        </h1>
        <p role="alert" className="mt-3 text-sm text-rose-900">
          {error}
        </p>
      </section>
    );
  }
  if (!brief) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading professional research…
      </p>
    );
  }

  const profile = brief.observations.filter((item) =>
    profileCategories.has(item.category),
  );
  const activity = brief.observations.filter((item) =>
    activityCategories.has(item.category),
  );
  const context = brief.observations.filter((item) =>
    contextCategories.has(item.category),
  );
  const processing =
    brief.status === "pending" || brief.status === "researching";
  const hasResearch = Boolean(brief.currentRun);
  const outcomeRequiresResolution = brief.status === "unknown";
  const canPromote =
    hasResearch &&
    !processing &&
    brief.status !== "unknown" &&
    brief.status !== "no_result";
  const contactId = promotion?.contactId ?? brief.person.promotedContactId;

  return (
    <article className="space-y-7">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <Link
          href={`/find/${brief.person.companyTargetId}`}
          className="text-sm font-bold text-teal-700 hover:text-teal-900"
        >
          ← Back to company research
        </Link>
        <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
              Public professional research
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              {brief.person.displayName}
            </h1>
            <p className="mt-2 text-sm font-semibold text-slate-700">
              {brief.person.currentRole} · {brief.person.currentCompany}
            </p>
            {brief.person.publicProfessionalLocation ? (
              <p className="mt-1 text-sm text-slate-500">
                {brief.person.publicProfessionalLocation}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {!hasResearch && !outcomeRequiresResolution ? (
              <ProspectCreditAction
                actionCode="PROSPECT_PERSON_RESEARCH"
                className="primary-button"
                disabled={working}
                label={
                  brief.status === "no_result" || brief.status === "failed"
                    ? "Try again"
                    : "Research person"
                }
                busyLabel="Starting…"
                onAuthorised={(creditQuoteId, idempotencyKey) =>
                  queueResearch(false, creditQuoteId, idempotencyKey)
                }
              />
            ) : hasResearch && !processing && !outcomeRequiresResolution ? (
              <ProspectCreditAction
                actionCode="PROSPECT_PERSON_RESEARCH"
                className="secondary-button"
                disabled={working}
                label="Refresh research"
                busyLabel="Starting…"
                onAuthorised={(creditQuoteId, idempotencyKey) =>
                  queueResearch(true, creditQuoteId, idempotencyKey)
                }
              />
            ) : null}
            {canPromote && !contactId ? (
              <button
                ref={promotionTrigger}
                type="button"
                className="primary-button"
                disabled={working}
                onClick={() => setPromotionOpen(true)}
              >
                Add to Sales as Contact
              </button>
            ) : null}
            {contactId ? (
              <Link href={`/contacts/${contactId}`} className="primary-button">
                Open Contact
              </Link>
            ) : null}
          </div>
        </div>
        <div
          role="status"
          className={`mt-5 rounded-xl px-4 py-3 text-sm ${
            brief.status === "ready"
              ? "bg-emerald-50 text-emerald-950"
              : brief.status === "failed"
                ? "bg-rose-50 text-rose-950"
                : "bg-amber-50 text-amber-950"
          }`}
        >
          <span className="font-bold">
            {brief.person.employmentState === "no_longer_current"
              ? "Role may have changed"
              : processing
                ? "Researching person…"
                : humanise(brief.status)}
          </span>{" "}
          {brief.statusMessage}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {brief.person.providerAttribution}. No personal photos, private-life
          details or personality profiling are used.
        </p>
        {promotion ? (
          <p
            role="status"
            className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-950"
          >
            {promotion.message}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="mt-4 text-sm font-medium text-rose-700">
            {error}
          </p>
        ) : null}
        {companyPromotionRequired ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            <p className="font-semibold">
              Save the Account first, then continue with this Contact.
            </p>
            <Link
              className="primary-button mt-3"
              href={`/find/${brief.person.companyTargetId}?returnToPerson=${personId}`}
            >
              Save Company first
            </Link>
          </div>
        ) : null}
      </header>

      {processing ? (
        <section
          className="rounded-3xl border border-teal-100 bg-teal-50 p-7"
          aria-live="polite"
        >
          <h2 className="text-xl font-semibold text-teal-950">
            Researching public professional context…
          </h2>
          <p className="mt-2 text-sm leading-6 text-teal-900">
            RevenueOS is checking permitted business sources. It will not create
            a Contact, outreach or customer evidence.
          </p>
        </section>
      ) : brief.status === "unknown" ? (
        <section
          className="rounded-3xl border border-amber-200 bg-amber-50 p-7"
          aria-live="polite"
        >
          <h2 className="text-xl font-semibold text-amber-950">
            Reconciling provider outcome
          </h2>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            The provider outcome is uncertain. Reserved Credits remain held and
            RevenueOS will not retry or charge again until the operation is
            reconciled.
          </p>
        </section>
      ) : brief.status === "no_result" ? (
        <section className="rounded-3xl border border-slate-200 bg-slate-50 p-7">
          <h2 className="text-xl font-semibold text-slate-950">
            No reliable professional result
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            No supported professional facts were returned, so no Contact,
            buying-role claim or customer Evidence was created.
          </p>
        </section>
      ) : brief.status === "failed" ? (
        <section className="rounded-3xl border border-rose-200 bg-rose-50 p-7">
          <h2 className="text-xl font-semibold text-rose-950">
            Couldn’t complete professional research
          </h2>
          <p className="mt-2 text-sm leading-6 text-rose-900">
            RevenueOS could not establish reliable public professional context.
            No Contact or outreach was created.
          </p>
        </section>
      ) : hasResearch ? (
        <>
          <PersonSection
            title="Why this person may matter"
            description="A cautious, source-backed starting point—not a statement of buying authority."
          >
            <PersonObservationList
              items={context}
              sourceById={sourceById}
              empty="No reliable, source-backed relevance context was established."
            />
          </PersonSection>

          <PersonSection
            title="Professional profile"
            description="Public role, responsibilities and professional experience."
          >
            <PersonObservationList
              items={profile}
              sourceById={sourceById}
              empty="No reliable professional profile details were established."
            />
          </PersonSection>

          <PersonSection
            title="Possible buying-committee role"
            description="System hypotheses that require seller validation. They do not change Stakeholder Intelligence."
          >
            {brief.buyingRoles.length ? (
              <div className="grid gap-4 lg:grid-cols-2">
                {brief.buyingRoles.map((hypothesis) => (
                  <article
                    key={hypothesis.id}
                    className="rounded-2xl border border-amber-200 bg-amber-50 p-5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-[0.12em] text-amber-950">
                        Hypothesis — {humanise(hypothesis.reviewState)}
                      </span>
                      <ProspectTrustLabel state={hypothesis.trustState} />
                    </div>
                    <h3 className="mt-3 font-semibold text-slate-950">
                      {humanise(hypothesis.role)}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {hypothesis.rationale}
                    </p>
                    <SourceLinks
                      sourceIds={hypothesis.sourceIds}
                      sourceById={sourceById}
                    />
                    <div
                      className="mt-4 flex flex-wrap gap-2"
                      aria-label={`Review ${humanise(hypothesis.role)}`}
                    >
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={
                          working || hypothesis.reviewState === "relevant"
                        }
                        onClick={() => void reviewRole(hypothesis, "relevant")}
                      >
                        Mark relevant
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={
                          working || hypothesis.reviewState === "not_relevant"
                        }
                        onClick={() =>
                          void reviewRole(hypothesis, "not_relevant")
                        }
                      >
                        Not relevant
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-600">
                No supported buying-role hypothesis was established.
              </p>
            )}
          </PersonSection>

          <PersonSection
            title="Professional activity"
            description="Public statements, authored content and professional activity only."
          >
            <PersonObservationList
              items={activity}
              sourceById={sourceById}
              empty="No relevant recent professional activity was established."
            />
          </PersonSection>

          <PersonSection
            title="Known business contact details"
            description="Availability is not permission to contact. Permission and outreach compliance have not been assessed."
          >
            {brief.contactPoints.length ? (
              <ul className="grid gap-4 lg:grid-cols-2">
                {brief.contactPoints.map((point) => {
                  const source = sourceById.get(point.sourceId);
                  return (
                    <li
                      key={point.id}
                      className="rounded-2xl border border-slate-200 p-5"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                          {humanise(point.pointType)}
                        </span>
                        <ProspectTrustLabel state={point.trustState} />
                      </div>
                      <p className="mt-3 break-all text-sm font-semibold text-slate-950">
                        {point.value}
                      </p>
                      <p className="mt-2 text-xs leading-5 text-amber-800">
                        Permission not assessed ·{" "}
                        {humanise(point.verificationMethod)}
                        {point.expiresAt
                          ? ` · Expires ${formatDate(point.expiresAt)}`
                          : ""}
                      </p>
                      {source ? <SafeSourceLink source={source} /> : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-600">
                No reliable business contact details were established. RevenueOS
                did not guess an email address.
              </p>
            )}
          </PersonSection>

          {brief.changes.length ? (
            <PersonSection
              title="What changed"
              description="Compared with the previous successful research version."
            >
              <ul className="space-y-3 text-sm text-slate-700">
                {brief.changes.map((change) => (
                  <li key={`${change.changeType}-${change.observationKey}`}>
                    <span className="font-bold">
                      {humanise(change.changeType)}:
                    </span>{" "}
                    {change.statement}
                  </li>
                ))}
              </ul>
            </PersonSection>
          ) : null}

          <PersonSources sources={brief.sources} />
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
                  <span>
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
          <div className="flex justify-end">
            <button
              type="button"
              className="text-sm font-bold text-rose-700 hover:text-rose-900"
              disabled={working}
              onClick={() => void deleteResearch()}
            >
              Delete professional research
            </button>
          </div>
        </>
      ) : (
        <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">
            Research has not started
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Start a bounded review of permitted public professional sources. No
            Contact or outreach will be created.
          </p>
        </section>
      )}

      {promotionOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="person-promotion-title"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <div
            ref={promotionDialog}
            className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl sm:p-8"
          >
            <h2
              id="person-promotion-title"
              ref={dialogHeading}
              tabIndex={-1}
              className="text-2xl font-semibold text-slate-950 outline-none"
            >
              Add {brief.person.displayName} to Sales?
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              This explicitly creates or links a canonical Contact. It will not
              create an Opportunity, stakeholder role, Methodology answer,
              Revenue Brain fact or outreach.
            </p>
            {brief.existingContactMatches.length ? (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm font-bold text-amber-950">
                  Possible existing Contact
                </p>
                <div className="mt-3 space-y-3">
                  {brief.existingContactMatches.map((match) => (
                    <div
                      key={match.id}
                      className="flex flex-wrap items-center justify-between gap-3"
                    >
                      <div>
                        <p className="text-sm font-semibold text-slate-950">
                          {match.displayName}
                        </p>
                        <p className="text-xs text-slate-600">
                          {match.email ?? "Email not established"} ·{" "}
                          {humanise(match.matchStrength)} match
                        </p>
                      </div>
                      <button
                        type="button"
                        className="primary-button"
                        disabled={working}
                        onClick={() =>
                          void promote("attach_research", match.id)
                        }
                      >
                        Attach research
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
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
                className={
                  brief.existingContactMatches.length
                    ? "secondary-button"
                    : "primary-button"
                }
                disabled={working}
                onClick={() =>
                  void promote(
                    brief.existingContactMatches.length
                      ? "create_separate"
                      : undefined,
                  )
                }
              >
                {working
                  ? "Saving…"
                  : brief.existingContactMatches.length
                    ? "Create separate Contact"
                    : "Add Contact"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function PersonSection({
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

function PersonObservationList({
  items,
  sourceById,
  empty,
}: {
  items: ProspectResearchObservation[];
  sourceById: Map<string, ProspectResearchSource>;
  empty?: string;
}) {
  if (!items.length)
    return <p className="mt-3 text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="mt-4 space-y-4">
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
          <SourceLinks sourceIds={item.sourceIds} sourceById={sourceById} />
        </li>
      ))}
    </ul>
  );
}

function SourceLinks({
  sourceIds,
  sourceById,
}: {
  sourceIds: string[];
  sourceById: Map<string, ProspectResearchSource>;
}) {
  const sources = sourceIds
    .map((id) => sourceById.get(id))
    .filter((source): source is ProspectResearchSource => Boolean(source));
  if (!sources.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-3">
      {sources.map((source) => (
        <SafeSourceLink key={source.id} source={source} />
      ))}
    </div>
  );
}

function SafeSourceLink({ source }: { source: ProspectResearchSource }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      referrerPolicy="no-referrer"
      className="text-xs font-bold text-teal-700 underline decoration-teal-200 underline-offset-2 hover:text-teal-900"
    >
      {source.publisher} ↗
    </a>
  );
}

function PersonSources({ sources }: { sources: ProspectResearchSource[] }) {
  return (
    <PersonSection
      title="Sources"
      description="Public source metadata only. RevenueOS does not mirror full profiles or webpages."
    >
      <ul className="divide-y divide-slate-100">
        {sources.map((source) => (
          <li
            key={source.id}
            className="flex flex-col gap-2 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-semibold text-slate-950">{source.title}</p>
              <p className="mt-1 text-xs text-slate-500">
                {source.publisher} · {humanise(source.authorityClass)} ·{" "}
                {formatDate(source.publishedAt)}
              </p>
            </div>
            <SafeSourceLink source={source} />
          </li>
        ))}
      </ul>
    </PersonSection>
  );
}

export function ContactPublicProfessionalResearch({
  contactId,
}: {
  contactId: string;
}) {
  const [link, setLink] = useState<ContactProspectResearchLink | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ContactProspectResearchLink>(
      `/api/v1/prospect/contacts/${contactId}/research-link`,
      { signal: controller.signal },
    )
      .then(setLink)
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.status === 404) return;
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            "The public professional research link could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, [contactId]);

  if (!link && !error) return null;
  if (error)
    return (
      <p role="alert" className="mt-5 text-sm text-rose-700">
        {error}
      </p>
    );
  return (
    <aside className="mt-6 rounded-2xl border border-teal-200 bg-teal-50 p-5">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-800">
        Separate research context
      </p>
      <h2 className="mt-2 text-lg font-semibold text-teal-950">
        {link?.label}
      </h2>
      <p className="mt-2 text-sm leading-6 text-teal-900">
        Public professional research remains separate from customer evidence,
        Stakeholder Intelligence and Revenue Brain facts.
      </p>
      <Link
        href={`/find/${link?.companyTargetId}/people/${link?.prospectPersonId}`}
        className="secondary-button mt-4"
      >
        View public research
      </Link>
    </aside>
  );
}
