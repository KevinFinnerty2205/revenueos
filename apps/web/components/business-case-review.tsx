"use client";

import type {
  BusinessCase,
  BusinessCaseCalculationInput,
  BusinessCaseCalculationOutput,
  BusinessCaseInputOrigin,
  ValueModelInputDefinition,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const origins: Array<{ value: BusinessCaseInputOrigin; label: string }> = [
  {
    value: "organisation_assumption",
    label: "Approved organisation assumption",
  },
  { value: "salesperson_reported", label: "Reported by you" },
  { value: "user_entered", label: "Entered by you" },
  { value: "unknown", label: "Source unknown — review required" },
];

export function BusinessCaseReview({ caseId }: { caseId: string }) {
  const [businessCase, setBusinessCase] = useState<BusinessCase | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const loaded = await apiRequest<BusinessCase>(
        `/api/v1/create/business-cases/${caseId}`,
        { signal },
      );
      setBusinessCase(loaded);
    },
    [caseId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The Business Case could not be loaded.",
        );
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  const currentInputs = useMemo(
    () =>
      new Map(
        businessCase?.currentVersion?.inputs.map((item) => [item.key, item]) ??
          [],
      ),
    [businessCase],
  );

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!businessCase) return;
    const data = new FormData(event.currentTarget);
    const inputs = businessCase.modelDefinition.inputs.map((definition) => ({
      key: definition.key,
      value: String(data.get(`input-${definition.key}`) ?? ""),
      origin: data.get(`origin-${definition.key}`),
    }));
    const scenarios = (["conservative", "upside"] as const).flatMap((name) => {
      const overrides = businessCase.modelDefinition.inputs.flatMap(
        (definition) => {
          const value = String(
            data.get(`${name}-${definition.key}`) ?? "",
          ).trim();
          return value ? [{ key: definition.key, value }] : [];
        },
      );
      return overrides.length ? [{ name, overrides }] : [];
    });
    const sensitivityInput = String(data.get("sensitivityInput") ?? "");
    const sensitivityValues = String(data.get("sensitivityValues") ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await apiRequest<BusinessCase>(
        `/api/v1/create/business-cases/${caseId}/calculate`,
        {
          method: "POST",
          body: JSON.stringify({
            inputs,
            scenarios,
            sensitivity:
              sensitivityInput && sensitivityValues.length >= 2
                ? { inputKey: sensitivityInput, values: sensitivityValues }
                : null,
            idempotencyKey: `web-business-case-calculation-${crypto.randomUUID()}`,
          }),
        },
      );
      setBusinessCase(updated);
      setMessage(
        "Calculation saved as a new immutable version. Review every input, assumption and output.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Business Case could not be calculated.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function approve() {
    setSaving(true);
    setError(null);
    try {
      const updated = await apiRequest<BusinessCase>(
        `/api/v1/create/business-cases/${caseId}/approve`,
        {
          method: "POST",
          body: JSON.stringify({ confirmed: true }),
        },
      );
      setBusinessCase(updated);
      setMessage(
        "Business Case approved. This exact model, input, scenario and output version may now be used in Create.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Business Case could not be approved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function archive() {
    if (
      !window.confirm(
        "Archive this Business Case? Its immutable versions remain in audit and export history.",
      )
    )
      return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiRequest<BusinessCase>(
        `/api/v1/create/business-cases/${caseId}/archive`,
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      setBusinessCase(updated);
      setMessage(
        "Business Case archived. It can no longer be recalculated or used in a new presentation.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Business Case could not be archived.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !businessCase)
    return (
      <p role="alert" className="form-card text-rose-900">
        {error}
      </p>
    );
  if (!businessCase) return <p role="status">Loading Business Case…</p>;
  const version = businessCase.currentVersion;
  const base = version?.scenarios.find((scenario) => scenario.name === "base");
  const sensitivityEligible = businessCase.modelDefinition.inputs.filter(
    (item) => item.sensitivityEligible,
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`Create · Business Case · ${humanise(businessCase.state)}`}
        title={businessCase.title}
        description={`${businessCase.accountName}${businessCase.opportunityName ? ` · ${businessCase.opportunityName}` : ""} · ${businessCase.modelName} v${businessCase.modelVersion} · ${businessCase.currency}`}
        actions={
          businessCase.state !== "archived" ? (
            <div className="flex flex-wrap gap-3">
              {version?.reviewState === "approved" ? (
                <Link
                  href={`/create/presentations/new?accountId=${businessCase.accountId}${businessCase.opportunityId ? `&opportunityId=${businessCase.opportunityId}` : ""}&businessCaseVersionId=${version.id}`}
                  className="primary-button"
                >
                  Use in presentation
                </Link>
              ) : null}
              <button
                type="button"
                disabled={saving}
                onClick={() => void archive()}
                className="secondary-button"
              >
                Archive Business Case
              </button>
            </div>
          ) : undefined
        }
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> Business Case
      </nav>

      {businessCase.state === "needs_review" ? (
        <section
          className="rounded-2xl border border-amber-300 bg-amber-50 p-5"
          aria-labelledby="source-review-title"
        >
          <h2 id="source-review-title" className="font-semibold text-amber-950">
            Source review required
          </h2>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            A referenced source is stale or unavailable. The approved snapshot
            remains for audit, but it cannot enter a new customer presentation
            until recalculated and approved.
          </p>
        </section>
      ) : null}

      {base ? (
        <section aria-labelledby="results-title" className="space-y-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
              Under the base assumptions
            </p>
            <h2
              id="results-title"
              className="mt-1 text-2xl font-semibold text-slate-950"
            >
              Deterministic results
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              These are modelled estimates, not guaranteed outcomes. Negative
              results and unavailable payback remain visible.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {base.outputs
              .filter((output) => output.highlight)
              .map((output) => (
                <article
                  key={output.key}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <p className="text-sm font-semibold text-slate-600">
                    {output.label}
                  </p>
                  <p className="mt-3 text-2xl font-semibold text-slate-950">
                    {formatValue(
                      output.displayValue,
                      output.unit,
                      businessCase.currency,
                    )}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {output.description}
                  </p>
                </article>
              ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {base.outputs.map((output) => (
              <CalculationDisclosure
                key={output.key}
                output={output}
                inputs={version?.inputs ?? []}
                currency={businessCase.currency}
              />
            ))}
          </div>
          {businessCase.modelDefinition.customerDisclaimer ? (
            <p className="rounded-xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-600">
              {businessCase.modelDefinition.customerDisclaimer}
            </p>
          ) : null}
        </section>
      ) : null}

      {version ? (
        <section className="form-card" aria-labelledby="assumptions-title">
          <h2 id="assumptions-title" className="form-legend">
            Inputs and visible assumptions
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Every number keeps its origin. Entered-by-you values are not
            promoted to customer truth.
          </p>
          <dl className="mt-5 space-y-3 sm:hidden">
            {version.inputs.map((input) => (
              <div
                key={input.key}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <dt className="font-semibold text-slate-900">
                  {input.label}
                  {input.material ? (
                    <span className="ml-2 text-xs text-amber-800">
                      Material
                    </span>
                  ) : null}
                </dt>
                <dd className="mt-2 text-sm text-slate-900">
                  {formatValue(input.value, input.unit, businessCase.currency)}
                </dd>
                <dd className="mt-1 text-xs leading-5 text-slate-600">
                  {input.sourceLabel} · {humanise(input.freshness)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-5 hidden overflow-x-auto sm:block">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-3 pr-4">Input</th>
                  <th className="pb-3 pr-4">Value</th>
                  <th className="pb-3 pr-4">Origin</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {version.inputs.map((input) => (
                  <tr key={input.key} className="border-b border-slate-100">
                    <th className="py-3 pr-4 font-semibold text-slate-900">
                      {input.label}
                      {input.material ? (
                        <span className="ml-2 text-xs text-amber-800">
                          Material
                        </span>
                      ) : null}
                    </th>
                    <td className="py-3 pr-4">
                      {formatValue(
                        input.value,
                        input.unit,
                        businessCase.currency,
                      )}
                    </td>
                    <td className="py-3 pr-4">{input.sourceLabel}</td>
                    <td className="py-3">{humanise(input.freshness)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {version && version.scenarios.length > 1 ? (
        <section className="form-card" aria-labelledby="scenarios-title">
          <h2 id="scenarios-title" className="form-legend">
            Conservative, base and upside
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Each scenario uses the explicit overrides shown. There is no random
            simulation or hidden optimism.
          </p>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            {version.scenarios.map((scenario) => (
              <article
                key={scenario.name}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <h3 className="font-semibold text-slate-950">
                  {humanise(scenario.name)}
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  {scenario.overrides.length
                    ? scenario.overrides
                        .map((item) => `${humanise(item.key)} = ${item.value}`)
                        .join(" · ")
                    : "Approved base inputs"}
                </p>
                <dl className="mt-4 space-y-3">
                  {scenario.outputs
                    .filter((output) => output.highlight)
                    .map((output) => (
                      <div key={output.key}>
                        <dt className="text-xs text-slate-500">
                          {output.label}
                        </dt>
                        <dd className="font-semibold text-slate-900">
                          {formatValue(
                            output.displayValue,
                            output.unit,
                            businessCase.currency,
                          )}
                        </dd>
                      </div>
                    ))}
                </dl>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {version?.sensitivity ? (
        <section className="form-card" aria-labelledby="sensitivity-title">
          <h2 id="sensitivity-title" className="form-legend">
            One-variable sensitivity
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Changing {humanise(version.sensitivity.inputKey)} does not mutate
            the approved base.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {version.sensitivity.rows.map((row) => {
              const output = row.outputs.find((item) => item.highlight);
              return (
                <div
                  key={row.inputValue}
                  className="rounded-xl border border-slate-200 p-4"
                >
                  <p className="text-xs text-slate-500">
                    Input {row.inputValue}
                  </p>
                  <p className="mt-2 font-semibold text-slate-950">
                    {output
                      ? `${output.label}: ${formatValue(output.displayValue, output.unit, businessCase.currency)}`
                      : "Calculated"}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {businessCase.state !== "archived" ? (
        <details open={!version} className="form-card">
          <summary className="cursor-pointer text-lg font-semibold text-slate-950">
            {version ? "Create a revised calculation" : "Enter required inputs"}
          </summary>
          <form
            onSubmit={(event) => void calculate(event)}
            className="mt-5 space-y-6"
          >
            <div className="grid gap-4 lg:grid-cols-2">
              {businessCase.modelDefinition.inputs.map((definition) => (
                <InputEditor
                  key={definition.key}
                  definition={definition}
                  current={currentInputs.get(definition.key)}
                  currency={businessCase.currency}
                  disabled={saving}
                />
              ))}
            </div>
            {sensitivityEligible.length ? (
              <fieldset
                disabled={saving}
                className="rounded-2xl border border-slate-200 p-5"
              >
                <legend className="px-2 font-semibold text-slate-900">
                  Optional sensitivity table
                </legend>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <label className="field-label">
                    Input
                    <select
                      name="sensitivityInput"
                      className="field-input mt-2"
                    >
                      <option value="">No sensitivity table</option>
                      {sensitivityEligible.map((item) => (
                        <option key={item.key} value={item.key}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field-label">
                    Two to five explicit values
                    <input
                      name="sensitivityValues"
                      className="field-input mt-2"
                      placeholder="For example: 5, 10, 15"
                    />
                    <span className="mt-2 block text-xs font-normal text-slate-500">
                      Comma-separated; every value must remain within the
                      approved bounds.
                    </span>
                  </label>
                </div>
              </fieldset>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={saving}
                className="primary-button"
              >
                {saving
                  ? "Calculating…"
                  : version
                    ? "Calculate new version"
                    : "Calculate Business Case"}
              </button>
            </div>
          </form>
        </details>
      ) : null}

      {version?.reviewState === "pending" &&
      businessCase.state === "calculated" ? (
        <section
          className="rounded-3xl border border-teal-200 bg-teal-50 p-6 sm:p-8"
          aria-labelledby="approval-title"
        >
          <h2
            id="approval-title"
            className="text-xl font-semibold text-teal-950"
          >
            Approve this exact Business Case version
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-teal-900">
            Approval binds model v{businessCase.modelVersion},{" "}
            {businessCase.currency}, all shown inputs, assumptions, scenario
            overrides and deterministic outputs. Any edit creates a new version
            and invalidates approval.
          </p>
          <button
            type="button"
            disabled={saving}
            onClick={() => void approve()}
            className="primary-button mt-5"
          >
            {saving ? "Approving…" : "Approve Business Case"}
          </button>
        </section>
      ) : null}
      {message ? (
        <p
          role="status"
          className="rounded-xl bg-teal-50 p-4 text-sm text-teal-900"
        >
          {message}
        </p>
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

function InputEditor({
  definition,
  current,
  currency,
  disabled,
}: {
  definition: ValueModelInputDefinition;
  current?: BusinessCaseCalculationInput;
  currency: string;
  disabled: boolean;
}) {
  const defaultValue = current?.value ?? definition.defaultValue ?? "";
  const locked =
    definition.assumptionLocked ||
    definition.sourcePolicy === "approved_org_only";
  const defaultOrigin =
    current?.origin ?? definition.defaultOrigin ?? "user_entered";
  return (
    <fieldset
      disabled={disabled}
      className="rounded-2xl border border-slate-200 bg-white p-5"
    >
      <legend className="px-2 font-semibold text-slate-950">
        {definition.label}
        {definition.material ? (
          <span className="ml-2 text-xs font-semibold text-amber-800">
            Material assumption
          </span>
        ) : null}
      </legend>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        {definition.description}
      </p>
      <label className="field-label mt-4 block">
        Value ({unitLabel(definition.unit, currency)})
        <input
          name={`input-${definition.key}`}
          type="number"
          step={definition.decimalPrecision === 0 ? "1" : "any"}
          min={definition.minimum ?? undefined}
          max={definition.maximum ?? undefined}
          required={definition.required}
          readOnly={locked}
          defaultValue={defaultValue}
          className="field-input mt-2 read-only:bg-slate-100"
        />
      </label>
      <label className="field-label mt-4 block">
        Origin
        {locked ? (
          <>
            <input
              type="hidden"
              name={`origin-${definition.key}`}
              value={defaultOrigin}
            />
            <span className="mt-2 block rounded-xl bg-slate-100 p-3 text-sm font-normal text-slate-700">
              {definition.defaultSourceReference ?? humanise(defaultOrigin)}
            </span>
          </>
        ) : (
          <select
            name={`origin-${definition.key}`}
            defaultValue={defaultOrigin}
            className="field-input mt-2"
          >
            {origins
              .filter(
                (origin) =>
                  origin.value !== "organisation_assumption" ||
                  definition.defaultValue !== null,
              )
              .map((origin) => (
                <option key={origin.value} value={origin.value}>
                  {origin.label}
                </option>
              ))}
          </select>
        )}
      </label>
      <p className="mt-3 text-xs text-slate-500">
        Approved range: {definition.minimum ?? "unbounded"} to{" "}
        {definition.maximum ?? "unbounded"}.{" "}
        {locked
          ? "This approved assumption cannot be changed by a salesperson."
          : "Manual values remain seller-entered or salesperson-reported."}
      </p>
      {definition.sensitivityEligible ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="field-label text-xs">
            Conservative override
            <input
              name={`conservative-${definition.key}`}
              type="number"
              step="any"
              min={definition.minimum ?? undefined}
              max={definition.maximum ?? undefined}
              defaultValue={definition.scenarioPreset?.conservative ?? ""}
              className="field-input mt-2"
            />
          </label>
          <label className="field-label text-xs">
            Upside override
            <input
              name={`upside-${definition.key}`}
              type="number"
              step="any"
              min={definition.minimum ?? undefined}
              max={definition.maximum ?? undefined}
              defaultValue={definition.scenarioPreset?.upside ?? ""}
              className="field-input mt-2"
            />
          </label>
        </div>
      ) : null}
    </fieldset>
  );
}

function CalculationDisclosure({
  output,
  inputs,
  currency,
}: {
  output: BusinessCaseCalculationOutput;
  inputs: BusinessCaseCalculationInput[];
  currency: string;
}) {
  const dependencies = inputs.filter((input) =>
    output.inputDependencies.includes(input.key),
  );
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-5">
      <summary className="cursor-pointer font-semibold text-slate-950">
        Why this number? · {output.label}
      </summary>
      <p className="mt-4 rounded-xl bg-slate-50 p-3 font-mono text-sm text-slate-800">
        {output.formula}
      </p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {dependencies.map((input) => (
          <div key={input.key}>
            <dt className="text-xs font-semibold text-slate-500">
              {input.label}
            </dt>
            <dd className="text-sm text-slate-900">
              {formatValue(input.value, input.unit, currency)} ·{" "}
              {input.sourceLabel}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-sm font-semibold text-slate-950">
        Result: {formatValue(output.displayValue, output.unit, currency)}
      </p>
    </details>
  );
}

function formatValue(value: string | null, unit: string, currency: string) {
  if (value === null) return "Not achieved under these assumptions";
  if (unit.startsWith("currency"))
    return value.startsWith("-")
      ? `−${currency} ${value.slice(1)}`
      : `${currency} ${value}`;
  if (unit === "percentage") return `${value}%`;
  if (unit === "dimensionless" || unit === "count") return value;
  return `${value} ${humanise(unit)}`;
}

function unitLabel(unit: string, currency: string) {
  return unit.startsWith("currency")
    ? `${currency} ${humanise(unit.replace("currency", ""))}`.trim()
    : humanise(unit);
}
