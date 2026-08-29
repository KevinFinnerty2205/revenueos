"use client";

import type {
  ValueModel,
  ValueModelDefinition,
  ValueModelInputDefinition,
  ValueModelList,
  ValueModelOutputDefinition,
  ValueUnit,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const units: ValueUnit[] = [
  "count",
  "currency",
  "currency_per_year",
  "currency_per_hour",
  "percentage",
  "hours",
  "hours_per_year",
  "minutes",
  "days",
  "months",
  "years",
  "dimensionless",
];

function newInput(order: number): ValueModelInputDefinition {
  return {
    key: `input_${order}`,
    label: `Input ${order}`,
    description: "Explain what this explicit input measures.",
    valueType: "decimal",
    unit: "dimensionless",
    required: true,
    minimum: "0",
    maximum: "1000000",
    decimalPrecision: 2,
    defaultValue: null,
    defaultOrigin: null,
    defaultSourceReference: null,
    reviewExpiresOn: null,
    maxSourceAgeDays: null,
    assumptionLocked: false,
    sourcePolicy: "reviewed_manual",
    customerFacing: true,
    material: false,
    sensitivityEligible: false,
    scenarioPreset: null,
    displayOrder: order,
  };
}

function newOutput(
  order: number,
  inputKey: string,
): ValueModelOutputDefinition {
  return {
    key: `output_${order}`,
    label: `Output ${order}`,
    description: "Explain what this deterministic result means.",
    formula: inputKey,
    unit: "dimensionless",
    displayPrecision: 2,
    customerFacing: true,
    highlight: order === 1,
    scenarioSensitive: true,
    displayOrder: order,
  };
}

export function ValueModelAdmin() {
  const [models, setModels] = useState<ValueModelList | null>(null);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [inputs, setInputs] = useState<ValueModelInputDefinition[]>([
    newInput(1),
  ]);
  const [outputs, setOutputs] = useState<ValueModelOutputDefinition[]>([
    newOutput(1, "input_1"),
  ]);
  const [disclaimer, setDisclaimer] = useState(
    "Based on the inputs and assumptions shown; not a guarantee of future results.",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setModels(
      await apiRequest<ValueModelList>("/api/v1/create/value-models", {
        signal,
      }),
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Value Models could not be loaded.",
        );
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  function edit(model: ValueModel) {
    setEditingModelId(model.id);
    setName(model.name);
    setDescription(model.description);
    setInputs(model.latestVersion.definition.inputs);
    setOutputs(model.latestVersion.definition.outputs);
    setDisclaimer(model.latestVersion.definition.customerDisclaimer ?? "");
    setMessage(
      `Editing creates version ${model.latestVersion.version + 1}; approved version ${model.latestVersion.version} remains immutable.`,
    );
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  function reset() {
    setEditingModelId(null);
    setName("");
    setDescription("");
    setInputs([newInput(1)]);
    setOutputs([newOutput(1, "input_1")]);
    setDisclaimer(
      "Based on the inputs and assumptions shown; not a guarantee of future results.",
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const definition: ValueModelDefinition = {
      inputs: inputs.map((item, index) => ({
        ...item,
        displayOrder: index + 1,
      })),
      outputs: outputs.map((item, index) => ({
        ...item,
        displayOrder: index + 1,
      })),
      customerDisclaimer: disclaimer.trim() || null,
    };
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const path = editingModelId
        ? `/api/v1/create/value-models/${editingModelId}/versions`
        : "/api/v1/create/value-models";
      await apiRequest<ValueModel>(path, {
        method: "POST",
        body: JSON.stringify({
          ...(editingModelId ? { name, description } : { name, description }),
          definition,
          idempotencyKey: `web-value-model-${crypto.randomUUID()}`,
        }),
      });
      setMessage(
        editingModelId
          ? "New draft model version created. Validate and approve it before use."
          : "Draft Value Model created. Validate and approve it before use.",
      );
      reset();
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Value Model could not be validated.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function approve(model: ValueModel) {
    setSaving(true);
    setError(null);
    try {
      await apiRequest<ValueModel>(
        `/api/v1/create/value-models/${model.id}/versions/${model.latestVersion.id}/approve`,
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      setMessage(
        `${model.name} version ${model.latestVersion.version} approved and immutable.`,
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Value Model could not be approved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function archive(model: ValueModel) {
    if (
      !window.confirm(
        `Archive ${model.name}? Existing approved snapshots remain auditable.`,
      )
    )
      return;
    setSaving(true);
    setError(null);
    try {
      await apiRequest<ValueModel>(
        `/api/v1/create/value-models/${model.id}/archive`,
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      setMessage(
        `${model.name} archived. It is no longer available for new Business Cases.`,
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Value Model could not be archived.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!models && !error) return <p role="status">Loading Value Models…</p>;
  if (models && !models.canManage)
    return (
      <section className="form-card">
        <h1 className="form-legend">Administrator access required</h1>
        <p className="mt-2 text-sm text-slate-600">
          Members can use approved Value Models but cannot change formula
          definitions.
        </p>
        <Link href="/create" className="secondary-button mt-5">
          Back to Create
        </Link>
      </section>
    );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Create · Administration"
        title="Value Models"
        description="Define typed inputs and small, bounded formulas. Approved versions are immutable and normal members cannot edit them."
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> Value Models
      </nav>
      <section aria-labelledby="models-title" className="space-y-4">
        <h2 id="models-title" className="text-2xl font-semibold text-slate-950">
          Organisation models
        </h2>
        {models?.items.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {models.items.map((model) => (
              <article
                key={model.id}
                className="rounded-2xl border border-slate-200 bg-white p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-slate-950">
                      {model.name}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {model.description}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                    {humanise(model.latestVersion.state)} · v
                    {model.latestVersion.version}
                  </span>
                </div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {model.latestVersion.definition.inputs.length} inputs ·{" "}
                  {model.latestVersion.definition.outputs.length} outputs ·{" "}
                  {model.latestVersion.formulaEngineVersion}
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {model.latestVersion.state === "draft" ? (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void approve(model)}
                      className="primary-button"
                    >
                      Approve version
                    </button>
                  ) : null}
                  {model.state === "active" ? (
                    <button
                      type="button"
                      onClick={() => edit(model)}
                      className="secondary-button"
                    >
                      Create new version
                    </button>
                  ) : null}
                  {model.state !== "archived" ? (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void archive(model)}
                      className="secondary-button"
                    >
                      Archive model
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <h3 className="font-semibold text-slate-950">
              No Value Models yet
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Start small. Define only the inputs and outputs your organisation
              can credibly approve.
            </p>
          </div>
        )}
      </section>

      <form onSubmit={(event) => void submit(event)} className="space-y-6">
        <fieldset disabled={saving} className="form-card">
          <legend className="form-legend">
            {editingModelId
              ? "Create a new model version"
              : "Create a Value Model"}
          </legend>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="field-label">
              Model name
              <input
                required
                maxLength={200}
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="field-input mt-2"
              />
            </label>
            <label className="field-label">
              What this model measures
              <input
                required
                maxLength={800}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="field-input mt-2"
              />
            </label>
          </div>
        </fieldset>

        <section className="form-card" aria-labelledby="input-builder-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="input-builder-title" className="form-legend">
                Typed inputs
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Every default is a visible assumption. Bounds and origin policy
                are enforced server-side.
              </p>
            </div>
            <button
              type="button"
              disabled={inputs.length >= 30}
              onClick={() =>
                setInputs((items) => [...items, newInput(items.length + 1)])
              }
              className="secondary-button"
            >
              Add input
            </button>
          </div>
          <div className="mt-5 space-y-4">
            {inputs.map((input, index) => (
              <InputDefinitionEditor
                key={`${index}-${input.key}`}
                input={input}
                index={index}
                onChange={(next) =>
                  setInputs((items) =>
                    items.map((item, itemIndex) =>
                      itemIndex === index ? next : item,
                    ),
                  )
                }
                onRemove={() =>
                  setInputs((items) =>
                    items.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
              />
            ))}
          </div>
        </section>

        <section className="form-card" aria-labelledby="output-builder-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="output-builder-title" className="form-legend">
                Deterministic outputs
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Allowed syntax: identifiers, decimal literals, + − × ÷,
                parentheses, min, max, safe_divide, positive_divide and
                payback_months. No code execution.
              </p>
            </div>
            <button
              type="button"
              disabled={outputs.length >= 30}
              onClick={() =>
                setOutputs((items) => [
                  ...items,
                  newOutput(items.length + 1, inputs[0]?.key ?? "input_1"),
                ])
              }
              className="secondary-button"
            >
              Add output
            </button>
          </div>
          <div className="mt-5 space-y-4">
            {outputs.map((output, index) => (
              <OutputDefinitionEditor
                key={`${index}-${output.key}`}
                output={output}
                index={index}
                onChange={(next) =>
                  setOutputs((items) =>
                    items.map((item, itemIndex) =>
                      itemIndex === index ? next : item,
                    ),
                  )
                }
                onRemove={() =>
                  setOutputs((items) =>
                    items.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
              />
            ))}
          </div>
        </section>

        <label className="form-card field-label block">
          Approved customer disclaimer
          <textarea
            maxLength={500}
            rows={3}
            value={disclaimer}
            onChange={(event) => setDisclaimer(event.target.value)}
            className="field-input mt-2"
          />
        </label>
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
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={
              saving ||
              !name ||
              !description ||
              !inputs.length ||
              !outputs.length
            }
            className="primary-button"
          >
            {saving
              ? "Validating…"
              : editingModelId
                ? "Create draft version"
                : "Validate and save draft"}
          </button>
          {editingModelId ? (
            <button type="button" onClick={reset} className="secondary-button">
              Cancel version edit
            </button>
          ) : null}
        </div>
      </form>
    </div>
  );
}

function InputDefinitionEditor({
  input,
  index,
  onChange,
  onRemove,
}: {
  input: ValueModelInputDefinition;
  index: number;
  onChange: (input: ValueModelInputDefinition) => void;
  onRemove: () => void;
}) {
  function patch(values: Partial<ValueModelInputDefinition>) {
    onChange({ ...input, ...values });
  }
  return (
    <fieldset className="rounded-2xl border border-slate-200 p-5">
      <legend className="px-2 font-semibold text-slate-900">
        Input {index + 1}
      </legend>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="field-label">
          Key
          <input
            required
            pattern="[a-z][a-z0-9_]*"
            value={input.key}
            onChange={(event) => patch({ key: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Label
          <input
            required
            value={input.label}
            onChange={(event) => patch({ label: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Type
          <select
            value={input.valueType}
            onChange={(event) => {
              const valueType = event.target
                .value as ValueModelInputDefinition["valueType"];
              const defaults: Record<
                ValueModelInputDefinition["valueType"],
                { unit: ValueUnit; decimalPrecision: number }
              > = {
                integer: { unit: "dimensionless", decimalPrecision: 0 },
                decimal: { unit: "dimensionless", decimalPrecision: 2 },
                currency: { unit: "currency", decimalPrecision: 2 },
                percentage: { unit: "percentage", decimalPrecision: 2 },
                hours: { unit: "hours", decimalPrecision: 2 },
                days: { unit: "days", decimalPrecision: 2 },
                minutes: { unit: "minutes", decimalPrecision: 2 },
                count: { unit: "count", decimalPrecision: 0 },
              };
              patch({ valueType, ...defaults[valueType] });
            }}
            className="field-input mt-2"
          >
            {[
              "integer",
              "decimal",
              "currency",
              "percentage",
              "hours",
              "days",
              "minutes",
              "count",
            ].map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Unit
          <select
            value={input.unit}
            onChange={(event) =>
              patch({ unit: event.target.value as ValueUnit })
            }
            className="field-input mt-2"
          >
            {units.map((unit) => (
              <option key={unit}>{unit}</option>
            ))}
          </select>
        </label>
        <label className="field-label sm:col-span-2">
          Description
          <input
            required
            value={input.description}
            onChange={(event) => patch({ description: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Minimum
          <input
            type="number"
            step="any"
            value={input.minimum ?? ""}
            onChange={(event) => patch({ minimum: event.target.value || null })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Maximum
          <input
            type="number"
            step="any"
            value={input.maximum ?? ""}
            onChange={(event) => patch({ maximum: event.target.value || null })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Approved default (optional)
          <input
            type="number"
            step="any"
            value={input.defaultValue ?? ""}
            onChange={(event) =>
              patch({
                defaultValue: event.target.value || null,
                defaultOrigin: event.target.value
                  ? "organisation_assumption"
                  : null,
                defaultSourceReference: event.target.value
                  ? (input.defaultSourceReference ??
                    "Approved organisation assumption")
                  : null,
              })
            }
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Source policy
          <select
            value={input.sourcePolicy}
            onChange={(event) =>
              patch({
                sourcePolicy: event.target
                  .value as ValueModelInputDefinition["sourcePolicy"],
              })
            }
            className="field-input mt-2"
          >
            {[
              "reviewed_manual",
              "customer_or_manual",
              "approved_org_only",
              "public_or_manual",
            ].map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-5 text-sm text-slate-700">
        <label>
          <input
            type="checkbox"
            checked={input.material}
            onChange={(event) => patch({ material: event.target.checked })}
            className="mr-2"
          />
          Material assumption
        </label>
        <label>
          <input
            type="checkbox"
            checked={input.sensitivityEligible}
            onChange={(event) =>
              patch({
                sensitivityEligible: event.target.checked,
                scenarioPreset: null,
              })
            }
            className="mr-2"
          />
          Scenario/sensitivity eligible
        </label>
        <label>
          <input
            type="checkbox"
            checked={input.assumptionLocked}
            disabled={!input.defaultValue}
            onChange={(event) =>
              patch({ assumptionLocked: event.target.checked })
            }
            className="mr-2"
          />
          Lock approved default
        </label>
      </div>
      {input.defaultValue ? (
        <label className="field-label mt-4 block">
          Visible assumption source
          <input
            required
            value={input.defaultSourceReference ?? ""}
            onChange={(event) =>
              patch({ defaultSourceReference: event.target.value })
            }
            className="field-input mt-2"
          />
        </label>
      ) : null}
      {index > 0 ? (
        <button
          type="button"
          onClick={onRemove}
          className="mt-4 text-sm font-semibold text-rose-800 hover:underline"
        >
          Remove input
        </button>
      ) : null}
    </fieldset>
  );
}

function OutputDefinitionEditor({
  output,
  index,
  onChange,
  onRemove,
}: {
  output: ValueModelOutputDefinition;
  index: number;
  onChange: (output: ValueModelOutputDefinition) => void;
  onRemove: () => void;
}) {
  function patch(values: Partial<ValueModelOutputDefinition>) {
    onChange({ ...output, ...values });
  }
  return (
    <fieldset className="rounded-2xl border border-slate-200 p-5">
      <legend className="px-2 font-semibold text-slate-900">
        Output {index + 1}
      </legend>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="field-label">
          Key
          <input
            required
            pattern="[a-z][a-z0-9_]*"
            value={output.key}
            onChange={(event) => patch({ key: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Label
          <input
            required
            value={output.label}
            onChange={(event) => patch({ label: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label">
          Output unit
          <select
            value={output.unit}
            onChange={(event) =>
              patch({ unit: event.target.value as ValueUnit })
            }
            className="field-input mt-2"
          >
            {units.map((unit) => (
              <option key={unit}>{unit}</option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Display precision
          <input
            type="number"
            min="0"
            max="6"
            value={output.displayPrecision}
            onChange={(event) =>
              patch({ displayPrecision: Number(event.target.value) })
            }
            className="field-input mt-2"
          />
        </label>
        <label className="field-label sm:col-span-2 lg:col-span-4">
          Description
          <input
            required
            value={output.description}
            onChange={(event) => patch({ description: event.target.value })}
            className="field-input mt-2"
          />
        </label>
        <label className="field-label sm:col-span-2 lg:col-span-4">
          Bounded formula
          <input
            required
            maxLength={500}
            value={output.formula}
            onChange={(event) => patch({ formula: event.target.value })}
            className="field-input mt-2 font-mono"
          />
          <span className="mt-2 block text-xs font-normal text-slate-500">
            {output.label} = {output.formula || "…"}
          </span>
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-5 text-sm text-slate-700">
        <label>
          <input
            type="checkbox"
            checked={output.highlight}
            onChange={(event) => patch({ highlight: event.target.checked })}
            className="mr-2"
          />
          Highlight result
        </label>
        <label>
          <input
            type="checkbox"
            checked={output.customerFacing}
            onChange={(event) =>
              patch({ customerFacing: event.target.checked })
            }
            className="mr-2"
          />
          Customer-facing
        </label>
      </div>
      {index > 0 ? (
        <button
          type="button"
          onClick={onRemove}
          className="mt-4 text-sm font-semibold text-rose-800 hover:underline"
        >
          Remove output
        </button>
      ) : null}
    </fieldset>
  );
}
