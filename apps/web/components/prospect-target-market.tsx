"use client";

import type {
  ProspectBusinessCharacteristic,
  ProspectCandidateFeedback,
  ProspectDiscovery,
  ProspectDiscoveryCandidate,
  ProspectDiscoveryCapabilities,
  ProspectEmployeeBand,
  ProspectOrganisationType,
  ProspectResearchBrief,
  ProspectTargetMarket,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";

const employeeBandLabels: Record<ProspectEmployeeBand, string> = {
  "50_199": "50–199 employees",
  "200_499": "200–499 employees",
  "500_999": "500–999 employees",
  "1000_4999": "1,000–4,999 employees",
  "5000_plus": "5,000+ employees",
};

const organisationTypeLabels: Record<ProspectOrganisationType, string> = {
  private_company: "Private company",
  public_company: "Public company",
  government: "Government",
  education: "Education",
  healthcare: "Healthcare",
  not_for_profit: "Not for profit",
};

const characteristicLabels: Record<ProspectBusinessCharacteristic, string> = {
  multi_site: "Multi-site",
  international: "International",
  expanding: "Expanding",
  regulated: "Regulated",
  b2b: "B2B",
};

const priorityLabels = {
  high: "High priority",
  worth_researching: "Worth researching",
  needs_more_information: "Needs more information",
  excluded: "Excluded",
} as const;

const relationshipLabels = {
  new_prospect: "New prospect",
  existing_account_no_active_opportunity:
    "Already in Sales · no active opportunity",
  active_opportunity: "Active opportunity",
} as const;

interface BuilderState {
  name: string;
  description: string;
  industries: string[];
  countries: string[];
  regions: string[];
  minimumEmployeeBand: ProspectEmployeeBand | "";
  organisationTypes: ProspectOrganisationType[];
  preferredBusinessCharacteristics: ProspectBusinessCharacteristic[];
  excludedIndustries: string[];
  excludeExistingAccounts: boolean;
  researchObjective: string;
  status: "draft" | "active";
}

const emptyBuilder: BuilderState = {
  name: "",
  description: "",
  industries: [],
  countries: ["AU"],
  regions: [],
  minimumEmployeeBand: "",
  organisationTypes: [],
  preferredBusinessCharacteristics: [],
  excludedIndustries: [],
  excludeExistingAccounts: false,
  researchObjective: "",
  status: "active",
};

export function ProspectTargetMarketBuilder({
  marketId,
}: {
  marketId?: string;
}) {
  const router = useRouter();
  const [capabilities, setCapabilities] =
    useState<ProspectDiscoveryCapabilities | null>(null);
  const [state, setState] = useState<BuilderState>(emptyBuilder);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const requests: [
      Promise<ProspectDiscoveryCapabilities>,
      Promise<ProspectTargetMarket | null>,
    ] = [
      apiRequest<ProspectDiscoveryCapabilities>(
        "/api/v1/prospect/discovery/capabilities",
        { signal: controller.signal },
      ),
      marketId
        ? apiRequest<ProspectTargetMarket>(
            `/api/v1/prospect/target-markets/${marketId}`,
            { signal: controller.signal },
          )
        : Promise.resolve(null),
    ];
    Promise.all(requests)
      .then(([nextCapabilities, market]) => {
        setCapabilities(nextCapabilities);
        if (market) {
          const definition = market.definition;
          setState({
            name: market.name,
            description: definition.description ?? "",
            industries: definition.industries,
            countries: definition.countries,
            regions: definition.regions,
            minimumEmployeeBand: definition.minimumEmployeeBand ?? "",
            organisationTypes: definition.organisationTypes,
            preferredBusinessCharacteristics:
              definition.preferredBusinessCharacteristics,
            excludedIndustries: definition.excludedIndustries,
            excludeExistingAccounts: definition.excludeExistingAccounts,
            researchObjective: definition.researchObjective ?? "",
            status: market.status === "draft" ? "draft" : "active",
          });
        }
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Target-market setup could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [marketId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const market = await apiRequest<ProspectTargetMarket>(
        marketId
          ? `/api/v1/prospect/target-markets/${marketId}`
          : "/api/v1/prospect/target-markets",
        {
          method: marketId ? "PATCH" : "POST",
          body: JSON.stringify({
            ...state,
            description: state.description.trim() || null,
            minimumEmployeeBand: state.minimumEmployeeBand || null,
            researchObjective: state.researchObjective.trim() || null,
          }),
        },
      );
      router.push(`/find/target-markets/${market.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The target market could not be saved.",
      );
      setSaving(false);
    }
  }

  if (loading) {
    return <p role="status">Loading target-market setup…</p>;
  }

  if (!capabilities) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-800"
      >
        {error ?? "Target-market setup is unavailable."}
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="RevenueOS Prospect"
        title={marketId ? "Edit target market" : "New target market"}
        description="Describe the organisations you want to sell to in four simple steps."
      />
      <form onSubmit={submit} className="space-y-5">
        <BuilderStep
          step="1"
          title="Who do you want to sell to?"
          description="Name this shared market and choose supported industries."
        >
          <label
            className="block text-sm font-semibold text-slate-800"
            htmlFor="market-name"
          >
            Target market name
          </label>
          <input
            id="market-name"
            required
            maxLength={120}
            value={state.name}
            onChange={(event) =>
              setState((current) => ({ ...current, name: event.target.value }))
            }
            placeholder="Australian Multi-Site Enterprises"
            className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 px-4 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
          />
          <label
            className="mt-5 block text-sm font-semibold text-slate-800"
            htmlFor="market-description"
          >
            Short description{" "}
            <span className="font-normal text-slate-500">(optional)</span>
          </label>
          <textarea
            id="market-description"
            maxLength={400}
            rows={2}
            value={state.description}
            onChange={(event) =>
              setState((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
          />
          <CheckboxGroup
            legend="Industries"
            values={capabilities.industries}
            selected={state.industries}
            label={(value) => value}
            onChange={(industries) =>
              setState((current) => ({ ...current, industries }))
            }
          />
          <details className="mt-5 rounded-xl border border-slate-200 p-4">
            <summary className="cursor-pointer font-semibold text-slate-800">
              More filters
            </summary>
            <CheckboxGroup
              legend="Organisation types"
              values={capabilities.organisationTypes}
              selected={state.organisationTypes}
              label={(value) => organisationTypeLabels[value]}
              onChange={(organisationTypes) =>
                setState((current) => ({ ...current, organisationTypes }))
              }
            />
          </details>
        </BuilderStep>

        <BuilderStep
          step="2"
          title="Where are they?"
          description="Choose a supported country and, if useful, Australian regions."
        >
          <CheckboxGroup
            legend="Countries"
            values={capabilities.countries}
            selected={state.countries}
            label={(value) => (value === "AU" ? "Australia" : "New Zealand")}
            onChange={(countries) =>
              setState((current) => ({
                ...current,
                countries,
                regions: countries.includes("AU") ? current.regions : [],
              }))
            }
          />
          {state.countries.includes("AU") ? (
            <CheckboxGroup
              legend="States and territories (optional)"
              values={capabilities.regions}
              selected={state.regions}
              label={(value) => value}
              onChange={(regions) =>
                setState((current) => ({ ...current, regions }))
              }
            />
          ) : null}
        </BuilderStep>

        <BuilderStep
          step="3"
          title="What characteristics matter?"
          description="Required size affects eligibility. Preferred characteristics influence review order only."
        >
          <label
            className="block text-sm font-semibold text-slate-800"
            htmlFor="employee-band"
          >
            Minimum company size{" "}
            <span className="font-normal text-slate-500">(optional)</span>
          </label>
          <select
            id="employee-band"
            value={state.minimumEmployeeBand}
            onChange={(event) =>
              setState((current) => ({
                ...current,
                minimumEmployeeBand: event.target.value as
                  ProspectEmployeeBand | "",
              }))
            }
            className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100 sm:max-w-md"
          >
            <option value="">Any supported size</option>
            {capabilities.employeeBands.map((band) => (
              <option key={band} value={band}>
                {employeeBandLabels[band]}
              </option>
            ))}
          </select>
          <CheckboxGroup
            legend="Preferred business characteristics"
            values={capabilities.businessCharacteristics}
            selected={state.preferredBusinessCharacteristics}
            label={(value) => characteristicLabels[value]}
            onChange={(preferredBusinessCharacteristics) =>
              setState((current) => ({
                ...current,
                preferredBusinessCharacteristics,
              }))
            }
          />
          <label
            className="mt-5 block text-sm font-semibold text-slate-800"
            htmlFor="research-objective"
          >
            What are you selling?{" "}
            <span className="font-normal text-slate-500">(optional)</span>
          </label>
          <input
            id="research-objective"
            maxLength={300}
            value={state.researchObjective}
            onChange={(event) =>
              setState((current) => ({
                ...current,
                researchObjective: event.target.value,
              }))
            }
            placeholder="Enterprise access-control systems"
            className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 px-4 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
          />
          <p className="mt-2 text-xs leading-5 text-slate-500">
            This is bounded context for your team. It is not sent as an
            open-ended provider instruction.
          </p>
        </BuilderStep>

        <BuilderStep
          step="4"
          title="What should RevenueOS exclude?"
          description="Hard exclusions are applied only when the data is known."
        >
          <CheckboxGroup
            legend="Excluded industries"
            values={capabilities.industries.filter(
              (industry) => !state.industries.includes(industry),
            )}
            selected={state.excludedIndustries}
            label={(value) => value}
            onChange={(excludedIndustries) =>
              setState((current) => ({ ...current, excludedIndustries }))
            }
          />
          <label className="mt-5 flex min-h-11 items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-800">
            <input
              type="checkbox"
              checked={state.excludeExistingAccounts}
              onChange={(event) =>
                setState((current) => ({
                  ...current,
                  excludeExistingAccounts: event.target.checked,
                }))
              }
              className="h-5 w-5 accent-teal-700"
            />
            Exclude companies already in RevenueOS Sales
          </label>
        </BuilderStep>

        {error ? (
          <p
            role="alert"
            className="rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-800"
          >
            {error}
          </p>
        ) : null}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Link
            href={marketId ? `/find/target-markets/${marketId}` : "/find"}
            className="secondary-button"
          >
            Cancel
          </Link>
          <button type="submit" className="primary-button" disabled={saving}>
            {saving
              ? "Saving…"
              : marketId
                ? "Save changes"
                : "Create target market"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function ProspectTargetMarketDetail({ marketId }: { marketId: string }) {
  const router = useRouter();
  const [market, setMarket] = useState<ProspectTargetMarket | null>(null);
  const [discovery, setDiscovery] = useState<ProspectDiscovery | null>(null);
  const [filter, setFilter] = useState<
    "all" | "high" | "saved" | "existing" | "excluded"
  >("all");
  const [loading, setLoading] = useState(true);
  const [finding, setFinding] = useState(false);
  const [researching, setResearching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ProspectTargetMarket>(
      `/api/v1/prospect/target-markets/${marketId}`,
      {
        signal: controller.signal,
      },
    )
      .then(async (nextMarket) => {
        setMarket(nextMarket);
        if (nextMarket.latestRun) {
          setDiscovery(
            await apiRequest<ProspectDiscovery>(
              `/api/v1/prospect/discovery/${nextMarket.latestRun.id}`,
              { signal: controller.signal },
            ),
          );
        }
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(
            reason instanceof Error
              ? reason.message
              : "The target market could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [marketId]);

  const visibleCandidates = useMemo(() => {
    if (!discovery) return [];
    return discovery.candidates.filter((candidate) => {
      if (filter === "high")
        return candidate.priority === "high" && !candidate.excludedByUser;
      if (filter === "saved") return candidate.saved;
      if (filter === "existing")
        return candidate.relationshipState !== "new_prospect";
      if (filter === "excluded")
        return candidate.priority === "excluded" || candidate.excludedByUser;
      return candidate.priority !== "excluded" && !candidate.excludedByUser;
    });
  }, [discovery, filter]);

  async function findAccounts(refresh: boolean) {
    setFinding(true);
    setError(null);
    try {
      const result = await apiRequest<ProspectDiscovery>(
        `/api/v1/prospect/target-markets/${marketId}/discover`,
        {
          method: "POST",
          body: JSON.stringify({
            refresh,
            idempotencyKey: `target-market:${crypto.randomUUID()}`,
          }),
        },
      );
      setDiscovery(result);
      setMarket(result.targetMarket);
      setFilter("all");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Accounts could not be found.",
      );
    } finally {
      setFinding(false);
    }
  }

  async function openRun(runId: string) {
    setLoading(true);
    setError(null);
    try {
      setDiscovery(
        await apiRequest<ProspectDiscovery>(
          `/api/v1/prospect/discovery/${runId}`,
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The previous search could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function research(candidate: ProspectDiscoveryCandidate) {
    if (
      candidate.researchStatus !== "not_started" &&
      candidate.researchStatus !== "failed"
    ) {
      router.push(`/find/${candidate.prospectTargetId}`);
      return;
    }
    setResearching(candidate.id);
    setError(null);
    try {
      const brief = await apiRequest<ProspectResearchBrief>(
        "/api/v1/prospect/research",
        {
          method: "POST",
          body: JSON.stringify({
            candidateId: candidate.providerCandidateId,
            idempotencyKey: `target-market-research:${crypto.randomUUID()}`,
          }),
        },
      );
      router.push(`/find/${brief.target.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Company research could not be started.",
      );
      setResearching(null);
    }
  }

  async function changeFeedback(
    candidate: ProspectDiscoveryCandidate,
    action: "save" | "exclude" | "restore",
  ) {
    setError(null);
    try {
      const feedback = await apiRequest<ProspectCandidateFeedback>(
        `/api/v1/prospect/candidates/${candidate.id}/${action}`,
        {
          method: "POST",
          body:
            action === "exclude"
              ? JSON.stringify({ reason: "not_relevant" })
              : undefined,
        },
      );
      setDiscovery((current) =>
        current
          ? {
              ...current,
              candidates: current.candidates.map((item) =>
                item.prospectTargetId === feedback.prospectTargetId
                  ? {
                      ...item,
                      saved: feedback.saved,
                      excludedByUser: feedback.excludedByUser,
                      exclusionReason: feedback.exclusionReason,
                    }
                  : item,
              ),
            }
          : current,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The target preference could not be saved.",
      );
    }
  }

  async function archive() {
    if (
      !window.confirm(
        "Archive this target market? Historical account searches will remain available.",
      )
    ) {
      return;
    }
    try {
      setMarket(
        await apiRequest<ProspectTargetMarket>(
          `/api/v1/prospect/target-markets/${marketId}/archive`,
          { method: "POST" },
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The target market could not be archived.",
      );
    }
  }

  if (loading && !market) return <p role="status">Loading target market…</p>;
  if (!market) {
    return (
      <p role="alert">{error ?? "The target market could not be found."}</p>
    );
  }
  const definition = discovery?.targetMarket.definition ?? market.definition;

  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader
          eyebrow="Target market"
          title={market.name}
          description={
            definition.description ??
            "A shared, explainable account-discovery definition."
          }
        />
        <div className="flex flex-wrap gap-2">
          {market.canManage && market.status !== "archived" ? (
            <>
              <Link
                href={`/find/target-markets/${market.id}/edit`}
                className="secondary-button"
              >
                Edit
              </Link>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void archive()}
              >
                Archive
              </button>
            </>
          ) : null}
        </div>
      </div>

      <section
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        aria-labelledby="criteria-title"
      >
        <h2
          id="criteria-title"
          className="text-lg font-semibold text-slate-950"
        >
          Who and where
        </h2>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <DefinitionItem
            label="Industries"
            value={definition.industries.join(", ") || "Any supported industry"}
          />
          <DefinitionItem
            label="Countries"
            value={definition.countries
              .map((country) =>
                country === "AU" ? "Australia" : "New Zealand",
              )
              .join(", ")}
          />
          <DefinitionItem
            label="Minimum size"
            value={
              definition.minimumEmployeeBand
                ? employeeBandLabels[definition.minimumEmployeeBand]
                : "Any supported size"
            }
          />
          <DefinitionItem
            label="Preferred"
            value={
              definition.preferredBusinessCharacteristics
                .map((item) => characteristicLabels[item])
                .join(", ") || "None"
            }
          />
        </dl>
        {definition.excludedIndustries.length ||
        definition.excludeExistingAccounts ? (
          <p className="mt-4 text-sm text-slate-600">
            <strong className="text-slate-800">Excluding:</strong>{" "}
            {[
              ...definition.excludedIndustries,
              definition.excludeExistingAccounts
                ? "Existing RevenueOS Accounts"
                : null,
            ]
              .filter(Boolean)
              .join(", ")}
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-teal-100 bg-teal-50/50 p-5 sm:flex sm:items-center sm:justify-between sm:gap-5">
        <div>
          <h2 className="font-semibold text-slate-950">
            {market.status === "archived"
              ? "This target market is archived"
              : discovery
                ? "Latest account search"
                : "Ready to find accounts"}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {discovery
              ? `${discovery.run.candidateCount} bounded candidates found ${new Date(discovery.run.requestedAt).toLocaleDateString("en-AU")}.`
              : "RevenueOS applies supported criteria and preserves the reasons for this point-in-time search."}
          </p>
        </div>
        {market.status === "active" ? (
          <button
            type="button"
            className="primary-button mt-4 shrink-0 sm:mt-0"
            disabled={finding}
            onClick={() => void findAccounts(Boolean(discovery))}
          >
            {finding
              ? "Finding accounts…"
              : discovery
                ? "Find accounts again"
                : "Find accounts"}
          </button>
        ) : null}
      </section>

      {finding ? (
        <p
          role="status"
          aria-live="polite"
          className="text-sm font-semibold text-teal-800"
        >
          Finding accounts…
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-800"
        >
          {error}
        </p>
      ) : null}

      {discovery ? (
        <>
          <section aria-labelledby="account-results-title">
            <div className="flex flex-col gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
                  Accounts you may want to research
                </p>
                <h2
                  id="account-results-title"
                  className="mt-2 text-2xl font-semibold text-slate-950"
                >
                  {discovery.summary.totalCandidates} discovered accounts
                </h2>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <SummaryStat
                  label="High priority"
                  value={discovery.summary.highPriority}
                />
                <SummaryStat
                  label="New prospects"
                  value={discovery.summary.newProspects}
                />
                <SummaryStat
                  label="Existing Accounts"
                  value={discovery.summary.existingAccounts}
                />
                <SummaryStat
                  label="Active opportunities"
                  value={discovery.summary.activeOpportunities}
                />
              </div>
              <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                <strong>High priority</strong> means a strong fit with your
                targeting criteria. It does not mean the company intends to buy.
              </p>
              <div
                className="flex flex-wrap gap-2"
                aria-label="Filter discovered accounts"
              >
                {(
                  [
                    ["all", "Matches"],
                    ["high", "High priority"],
                    ["saved", "Saved"],
                    ["existing", "Existing"],
                    ["excluded", "Excluded / unknown"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                    className={`min-h-11 rounded-full border px-4 text-sm font-semibold ${filter === value ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300 bg-white text-slate-700"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {visibleCandidates.length === 0 ? (
              <p className="mt-4 rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-600">
                No accounts match this view.
              </p>
            ) : (
              <div className="mt-4 grid gap-4">
                {visibleCandidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.id}
                    candidate={candidate}
                    researching={researching === candidate.id}
                    onResearch={() => void research(candidate)}
                    onSave={() =>
                      void changeFeedback(
                        candidate,
                        candidate.saved ? "restore" : "save",
                      )
                    }
                    onExclude={() =>
                      void changeFeedback(
                        candidate,
                        candidate.excludedByUser ? "restore" : "exclude",
                      )
                    }
                  />
                ))}
              </div>
            )}
          </section>

          {market.recentRuns.length > 1 ? (
            <section aria-labelledby="history-title">
              <h2
                id="history-title"
                className="text-lg font-semibold text-slate-950"
              >
                Previous account searches
              </h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {market.recentRuns.map((run) => (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => void openRun(run.id)}
                    aria-pressed={discovery.run.id === run.id}
                    className="min-h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700"
                  >
                    {new Date(run.requestedAt).toLocaleDateString("en-AU")} ·
                    version {run.targetMarketVersion}
                  </button>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function BuilderStep({
  step,
  title,
  description,
  children,
}: {
  step: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <legend className="sr-only">
        Step {step}: {title}
      </legend>
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Step {step}
      </p>
      <h2 className="mt-2 text-xl font-semibold text-slate-950">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
      <div className="mt-5">{children}</div>
    </fieldset>
  );
}

function CheckboxGroup<TValue extends string>({
  legend,
  values,
  selected,
  label,
  onChange,
}: {
  legend: string;
  values: readonly TValue[];
  selected: TValue[];
  label: (value: TValue) => string;
  onChange: (values: TValue[]) => void;
}) {
  return (
    <fieldset className="mt-5">
      <legend className="text-sm font-semibold text-slate-800">{legend}</legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {values.map((value) => (
          <label
            key={value}
            className="flex min-h-11 items-center gap-3 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
          >
            <input
              type="checkbox"
              checked={selected.includes(value)}
              onChange={(event) =>
                onChange(
                  event.target.checked
                    ? [...selected, value]
                    : selected.filter((item) => item !== value),
                )
              }
              className="h-5 w-5 accent-teal-700"
            />
            {label(value)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function DefinitionItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-900">{value}</dd>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <span className="block text-2xl font-semibold text-slate-950">
        {value}
      </span>
      <span className="mt-1 block text-xs font-semibold text-slate-600">
        {label}
      </span>
    </div>
  );
}

function CandidateCard({
  candidate,
  researching,
  onResearch,
  onSave,
  onExclude,
}: {
  candidate: ProspectDiscoveryCandidate;
  researching: boolean;
  onResearch: () => void;
  onSave: () => void;
  onExclude: () => void;
}) {
  const excluded =
    candidate.priority === "excluded" || candidate.excludedByUser;
  return (
    <article
      className={`rounded-2xl border bg-white p-5 shadow-sm ${excluded ? "border-slate-200 opacity-80" : "border-slate-200"}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-950">
              {candidate.companyName}
            </h3>
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold ${candidate.priority === "high" ? "bg-teal-100 text-teal-900" : candidate.priority === "excluded" ? "bg-slate-200 text-slate-800" : "bg-amber-100 text-amber-900"}`}
            >
              {priorityLabels[candidate.priority]}
            </span>
          </div>
          <p className="mt-1 break-all text-sm font-medium text-teal-800">
            {candidate.domain}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {[
              candidate.location,
              candidate.industry,
              candidate.employeeBand
                ? employeeBandLabels[candidate.employeeBand]
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-700">
            {relationshipLabels[candidate.relationshipState]}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {candidate.relationshipState === "active_opportunity" &&
          candidate.activeOpportunityId ? (
            <Link
              href={`/opportunities/${candidate.activeOpportunityId}`}
              className="secondary-button"
            >
              Open opportunity
            </Link>
          ) : candidate.relationshipState ===
              "existing_account_no_active_opportunity" &&
            candidate.matchedCompanyId ? (
            <Link
              href={`/companies/${candidate.matchedCompanyId}`}
              className="secondary-button"
            >
              Open Account
            </Link>
          ) : null}
          {!excluded ? (
            <button
              type="button"
              className="primary-button"
              disabled={researching}
              onClick={onResearch}
            >
              {researching
                ? "Starting research…"
                : candidate.researchStatus === "not_started" ||
                    candidate.researchStatus === "failed"
                  ? "Research"
                  : "Open research"}
            </button>
          ) : null}
        </div>
      </div>
      <details
        className="mt-4 rounded-xl border border-slate-200 p-4"
        open={
          candidate.priority === "high" || candidate.priority === "excluded"
        }
      >
        <summary className="cursor-pointer font-semibold text-slate-800">
          Why this account appears
        </summary>
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {candidate.reasons.map((reason) => (
            <li key={reason.reasonCode} className="flex gap-2">
              <span aria-hidden="true">
                {reason.state === "matched"
                  ? "✓"
                  : reason.state === "missing"
                    ? "?"
                    : reason.state === "excluded"
                      ? "×"
                      : "•"}
              </span>
              <span>
                {reason.text}{" "}
                <span className="text-xs text-slate-500">
                  ({reason.dataOrigin.replaceAll("_", " ")})
                </span>
                {reason.sourceReference ? (
                  <>
                    {" "}
                    ·{" "}
                    <a
                      href={reason.sourceReference}
                      target="_blank"
                      rel="noopener noreferrer"
                      referrerPolicy="no-referrer"
                      className="font-semibold text-teal-800 underline"
                    >
                      Source
                    </a>
                  </>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </details>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="secondary-button" onClick={onSave}>
          {candidate.saved ? "Remove saved" : "Save target"}
        </button>
        <button type="button" className="secondary-button" onClick={onExclude}>
          {candidate.excludedByUser ? "Undo exclusion" : "Not relevant"}
        </button>
      </div>
    </article>
  );
}
