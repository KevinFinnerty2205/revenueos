"use client";

import type {
  BusinessCase,
  Company,
  EntityPage,
  Opportunity,
  ValueModelList,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";

const currencies = ["AUD", "CAD", "EUR", "GBP", "NZD", "SGD", "USD"];

export function BusinessCaseNew() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [models, setModels] = useState<ValueModelList | null>(null);
  const [accountId, setAccountId] = useState(
    searchParams.get("accountId") ?? "",
  );
  const [opportunityId, setOpportunityId] = useState(
    searchParams.get("opportunityId") ?? "",
  );
  const [modelVersionId, setModelVersionId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Opportunity>>(
        "/api/v1/opportunities?pageSize=100",
        { signal: controller.signal },
      ),
      apiRequest<ValueModelList>("/api/v1/create/value-models", {
        signal: controller.signal,
      }),
    ])
      .then(([companyPage, opportunityPage, modelList]) => {
        setCompanies(companyPage.items);
        setOpportunities(opportunityPage.items);
        setModels(modelList);
        const firstApproved = modelList.items.find(
          (item) => item.latestVersion.state === "approved",
        );
        if (firstApproved) setModelVersionId(firstApproved.latestVersion.id);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Business Case options could not be loaded.",
        );
      });
    return () => controller.abort();
  }, []);

  const approvedModels =
    models?.items.filter((item) => item.latestVersion.state === "approved") ??
    [];
  const accountOpportunities = useMemo(
    () => opportunities.filter((item) => item.companyId === accountId),
    [accountId, opportunities],
  );
  const selectedModel = approvedModels.find(
    (item) => item.latestVersion.id === modelVersionId,
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSaving(true);
    setError(null);
    try {
      const created = await apiRequest<BusinessCase>(
        "/api/v1/create/business-cases",
        {
          method: "POST",
          body: JSON.stringify({
            accountId,
            opportunityId: opportunityId || null,
            modelVersionId,
            currency: data.get("currency"),
            title: String(data.get("title") ?? "").trim() || null,
            idempotencyKey: `web-business-case-${crypto.randomUUID()}`,
          }),
        },
      );
      router.push(`/create/business-cases/${created.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Business Case could not be created.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Create · Business Cases"
        title="Create a Business Case"
        description="Choose customer context and an approved Value Model. RevenueOS will ask for every required number before it calculates anything."
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> New Business Case
      </nav>
      {approvedModels.length === 0 && models ? (
        <section className="form-card" aria-labelledby="no-model-title">
          <h2 id="no-model-title" className="form-legend">
            No approved Value Models
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Ask an administrator to define and approve a bounded Value Model
            before creating a customer Business Case.
          </p>
          {models.canManage ? (
            <Link href="/create/value-models" className="secondary-button mt-5">
              Manage Value Models
            </Link>
          ) : null}
        </section>
      ) : (
        <form onSubmit={(event) => void submit(event)} className="space-y-6">
          <fieldset disabled={saving} className="form-card">
            <legend className="form-legend">Customer and model</legend>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="field-label">
                Account
                <select
                  required
                  value={accountId}
                  onChange={(event) => {
                    setAccountId(event.target.value);
                    setOpportunityId("");
                  }}
                  className="field-input mt-2"
                >
                  <option value="">Choose an Account</option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Opportunity (optional)
                <select
                  value={opportunityId}
                  disabled={!accountId}
                  onChange={(event) => setOpportunityId(event.target.value)}
                  className="field-input mt-2"
                >
                  <option value="">Account-level Business Case</option>
                  {accountOpportunities.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Approved Value Model
                <select
                  required
                  value={modelVersionId}
                  onChange={(event) => setModelVersionId(event.target.value)}
                  className="field-input mt-2"
                >
                  <option value="">Choose a model</option>
                  {approvedModels.map((item) => (
                    <option
                      key={item.latestVersion.id}
                      value={item.latestVersion.id}
                    >
                      {item.name} · version {item.latestVersion.version}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Case currency
                <select
                  name="currency"
                  defaultValue="AUD"
                  className="field-input mt-2"
                >
                  {currencies.map((currency) => (
                    <option key={currency}>{currency}</option>
                  ))}
                </select>
                <span className="mt-2 block text-xs font-normal text-slate-500">
                  One confirmed ISO currency. RevenueOS performs no FX
                  conversion.
                </span>
              </label>
              <label className="field-label sm:col-span-2">
                Title (optional)
                <input
                  name="title"
                  maxLength={240}
                  className="field-input mt-2"
                  placeholder="Defaults to the Account and model name"
                />
              </label>
            </div>
          </fieldset>
          {selectedModel ? (
            <section
              className="rounded-2xl border border-slate-200 bg-white p-5"
              aria-labelledby="model-summary-title"
            >
              <h2
                id="model-summary-title"
                className="font-semibold text-slate-950"
              >
                {selectedModel.name}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {selectedModel.description}
              </p>
              <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {selectedModel.latestVersion.definition.inputs.length} inputs ·{" "}
                {selectedModel.latestVersion.definition.outputs.length}{" "}
                deterministic outputs ·{" "}
                {selectedModel.latestVersion.formulaEngineVersion}
              </p>
            </section>
          ) : null}
          {error ? (
            <p
              role="alert"
              className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
            >
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={saving || !accountId || !modelVersionId}
              className="primary-button"
            >
              {saving ? "Creating…" : "Review inputs"}
            </button>
            <Link href="/create" className="secondary-button">
              Cancel
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
