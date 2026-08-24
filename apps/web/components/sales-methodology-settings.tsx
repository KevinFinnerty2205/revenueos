"use client";

import type {
  MethodologyCatalogueResponse,
  MethodologyDefinitionSummary,
  MethodologyFieldDefinition,
  MethodologySelection,
  MethodologySelectionResponse,
  OpportunityStage,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const FACT_OPTIONS = [
  "quantified_business_impact",
  "economic_buyer",
  "champion",
  "decision_criteria",
  "decision_process",
  "paper_process",
  "business_pain",
  "competition",
  "budget",
  "authority",
  "need",
  "timing",
  "situation",
  "pain",
  "impact",
  "critical_event",
  "decision",
] as const;

const CATEGORY_OPTIONS = [
  "buying_signal",
  "stakeholder",
  "decision",
  "risk",
  "open_question",
  "budget",
  "timeline",
  "procurement",
  "commercial_intent",
  "competitor",
  "objection",
  "implementation",
  "customer_request",
  "technical_requirement",
  "security_legal",
  "other",
] as const;

const STAGE_OPTIONS: OpportunityStage[] = [
  "qualification",
  "discovery",
  "evaluation",
  "proposal",
  "negotiation",
  "procurement",
  "closed_won",
  "closed_lost",
  "other",
];

interface FieldDraft {
  key: string;
  keyEdited: boolean;
  displayName: string;
  explanation: string;
  required: boolean;
  evidenceExpectation: string;
  canonicalFact: (typeof FACT_OPTIONS)[number];
  evidenceCategory: (typeof CATEGORY_OPTIONS)[number];
  freshnessDays: string;
  suggestedQuestion: string;
  stageExpectation: OpportunityStage | "";
}

const EMPTY_FIELD: FieldDraft = {
  key: "",
  keyEdited: false,
  displayName: "",
  explanation: "",
  required: true,
  evidenceExpectation: "",
  canonicalFact: "need",
  evidenceCategory: "buying_signal",
  freshnessDays: "90",
  suggestedQuestion: "",
  stageExpectation: "",
};

export function SalesMethodologySettings() {
  const [catalogue, setCatalogue] =
    useState<MethodologyCatalogueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [fields, setFields] = useState<FieldDraft[]>([{ ...EMPTY_FIELD }]);
  const [editing, setEditing] = useState<MethodologyDefinitionSummary | null>(
    null,
  );

  const load = useCallback(async () => {
    try {
      setCatalogue(
        await apiRequest<MethodologyCatalogueResponse>("/api/v1/methodologies"),
      );
      setError(null);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Sales Methodology settings could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<MethodologyCatalogueResponse>("/api/v1/methodologies", {
      signal: controller.signal,
    })
      .then((response) => {
        setCatalogue(response);
        setError(null);
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Sales Methodology settings could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function select(
    selection: MethodologySelection,
    customDefinitionId: string | null = null,
  ) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await apiRequest<MethodologySelectionResponse>(
        "/api/v1/methodologies/current",
        {
          method: "PATCH",
          body: JSON.stringify({ selection, customDefinitionId }),
        },
      );
      setMessage(
        selection === "none"
          ? "Sales Methodology is now optional and unselected. Existing review history is preserved."
          : "Organisation methodology updated. Existing evidence and review history are preserved.",
      );
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The selection could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveCustom() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        name,
        description,
        fields: fields.map(toFieldDefinition),
        ...(editing ? { expectedVersion: editing.version } : {}),
      };
      const saved = await apiRequest<MethodologyDefinitionSummary>(
        editing
          ? `/api/v1/methodologies/custom/${editing.id}`
          : "/api/v1/methodologies/custom",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) },
      );
      setMessage(
        editing
          ? `Saved ${saved.name} as immutable definition version ${saved.version}.`
          : `Created ${saved.name}. Select it when your organisation is ready.`,
      );
      resetBuilder();
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The custom methodology could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function archive(definition: MethodologyDefinitionSummary) {
    if (!definition.id) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/methodologies/custom/${definition.id}`, {
        method: "DELETE",
      });
      setMessage(
        `${definition.name} was archived. Historical methodology views remain available.`,
      );
      if (editing?.id === definition.id) resetBuilder();
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The methodology could not be archived.",
      );
    } finally {
      setBusy(false);
    }
  }

  function startEditing(definition: MethodologyDefinitionSummary) {
    setEditing(definition);
    setName(definition.name);
    setDescription(definition.description);
    setFields(definition.fields.map(fromFieldDefinition));
  }

  function resetBuilder() {
    setEditing(null);
    setName("");
    setDescription("");
    setFields([{ ...EMPTY_FIELD }]);
  }

  if (loading)
    return (
      <div role="status" className="form-card">
        Loading Sales Methodology settings…
      </div>
    );
  if (!catalogue)
    return (
      <div
        role="alert"
        className="form-card border-rose-200 bg-rose-50 text-sm text-rose-900"
      >
        {error ?? "Sales Methodology settings are unavailable."}
      </div>
    );

  return (
    <section
      aria-labelledby="sales-methodology-settings-title"
      className="form-card"
    >
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
          Admin control
        </p>
        <h2 id="sales-methodology-settings-title" className="form-legend mt-2">
          Sales Methodology
        </h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
          Choose one organisation default or none. Methodologies structure
          evidence; they do not score opportunities, block stages, or execute
          rules.
        </p>
      </div>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm font-semibold text-teal-800">
          {message}
        </p>
      ) : null}

      <fieldset className="mt-6">
        <legend className="text-base font-bold text-slate-950">
          Organisation default
        </legend>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <MethodologyChoice
            name="None"
            description="RevenueOS works normally without a selected methodology."
            selected={catalogue.current.selection === "none"}
            busy={busy}
            onSelect={() => void select("none")}
          />
          {catalogue.standards.map((definition) => (
            <MethodologyChoice
              key={definition.key}
              name={definition.name}
              description={definition.description}
              selected={catalogue.current.selection === definition.key}
              busy={busy}
              details={definition}
              onSelect={() =>
                void select(definition.key as MethodologySelection)
              }
            />
          ))}
          {catalogue.custom
            .filter((item) => item.status === "active")
            .map((definition) => (
              <MethodologyChoice
                key={definition.id}
                name={definition.name}
                description={`${definition.description} · custom v${definition.version}`}
                selected={
                  catalogue.current.customDefinitionId === definition.id
                }
                busy={busy}
                details={definition}
                onSelect={() => void select("custom", definition.id)}
              />
            ))}
        </div>
      </fieldset>

      <div className="mt-8 border-t border-slate-200 pt-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-slate-950">
              Custom methodology builder
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Guided fields only. This builder captures descriptive fields and
              discovery questions; it does not automate deal rules.
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
            {catalogue.custom.length} of {catalogue.customMethodologyLimit}{" "}
            definitions
          </span>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-bold text-slate-800">
            Name
            <input
              className="form-control mt-2"
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="text-sm font-bold text-slate-800">
            Purpose
            <textarea
              className="form-control mt-2 min-h-24"
              maxLength={500}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        </div>
        <ol className="mt-6 space-y-5">
          {fields.map((field, index) => (
            <li
              key={index}
              className="rounded-2xl border border-slate-200 p-4 sm:p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <h4 className="font-bold text-slate-950">Field {index + 1}</h4>
                {fields.length > 1 ? (
                  <button
                    type="button"
                    className="text-sm font-bold text-rose-800"
                    onClick={() =>
                      setFields((values) =>
                        values.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              <FieldEditor
                field={field}
                index={index}
                onChange={(next) =>
                  setFields((values) =>
                    values.map((value, itemIndex) =>
                      itemIndex === index ? next : value,
                    ),
                  )
                }
              />
            </li>
          ))}
        </ol>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            disabled={fields.length >= catalogue.fieldLimit}
            onClick={() =>
              setFields((values) => [...values, { ...EMPTY_FIELD }])
            }
          >
            Add field
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={
              busy ||
              !name.trim() ||
              !description.trim() ||
              fields.some(
                (field) =>
                  !field.displayName.trim() ||
                  !field.explanation.trim() ||
                  !field.evidenceExpectation.trim() ||
                  !field.suggestedQuestion.trim(),
              )
            }
            onClick={() => void saveCustom()}
          >
            {busy
              ? "Saving…"
              : editing
                ? `Save version ${editing.version + 1}`
                : "Create methodology"}
          </button>
          {editing ? (
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={resetBuilder}
            >
              Cancel edit
            </button>
          ) : null}
        </div>
      </div>

      {catalogue.custom.length ? (
        <div className="mt-8 border-t border-slate-200 pt-7">
          <h3 className="text-lg font-bold text-slate-950">
            Custom definitions
          </h3>
          <ul className="mt-4 space-y-3">
            {catalogue.custom.map((definition) => (
              <li
                key={definition.id}
                className="flex flex-col gap-3 rounded-2xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-bold text-slate-950">
                    {definition.name} · v{definition.version}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {definition.fieldCount} fields ·{" "}
                    {humanise(definition.status)}
                  </p>
                </div>
                {definition.status === "active" ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={busy}
                      onClick={() => startEditing(definition)}
                    >
                      Edit as new version
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={busy}
                      onClick={() => void archive(definition)}
                    >
                      Archive · keeps history
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function MethodologyChoice({
  name,
  description,
  selected,
  busy,
  details,
  onSelect,
}: {
  name: string;
  description: string;
  selected: boolean;
  busy: boolean;
  details?: MethodologyDefinitionSummary;
  onSelect: () => void;
}) {
  return (
    <div
      className={`rounded-2xl border p-4 ${selected ? "border-teal-500 bg-teal-50" : "border-slate-200"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-bold text-slate-950">{name}</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        </div>
        {selected ? (
          <span className="rounded-full bg-teal-700 px-2 py-1 text-xs font-bold text-white">
            Selected
          </span>
        ) : null}
      </div>
      {details ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-bold text-teal-800">
            Inspect {details.fieldCount} fields
          </summary>
          <ol className="mt-2 space-y-1 text-sm text-slate-700">
            {details.fields.map((field) => (
              <li key={field.key}>
                {field.order}. {field.displayName}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
      <button
        type="button"
        className="secondary-button mt-4"
        disabled={busy || selected}
        onClick={onSelect}
      >
        {selected ? "Current default" : "Select"}
      </button>
    </div>
  );
}

function FieldEditor({
  field,
  index,
  onChange,
}: {
  field: FieldDraft;
  index: number;
  onChange: (value: FieldDraft) => void;
}) {
  const update = <Key extends keyof FieldDraft>(
    key: Key,
    value: FieldDraft[Key],
  ) => onChange({ ...field, [key]: value });
  return (
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-bold text-slate-800">
        Display name
        <input
          className="form-control mt-2"
          maxLength={80}
          value={field.displayName}
          onChange={(event) => {
            const displayName = event.target.value;
            onChange({
              ...field,
              displayName,
              key: field.keyEdited
                ? field.key
                : keyFromName(displayName, index),
            });
          }}
        />
      </label>
      <label className="text-sm font-bold text-slate-800">
        Stable key
        <input
          className="form-control mt-2"
          maxLength={64}
          pattern="[a-z][a-z0-9_]*"
          value={field.key}
          onChange={(event) =>
            onChange({
              ...field,
              key: event.target.value
                .toLowerCase()
                .replace(/[^a-z0-9_]/gu, "_"),
              keyEdited: true,
            })
          }
        />
      </label>
      <label className="text-sm font-bold text-slate-800 sm:col-span-2">
        What this field means
        <textarea
          className="form-control mt-2 min-h-20"
          maxLength={500}
          value={field.explanation}
          onChange={(event) => update("explanation", event.target.value)}
        />
      </label>
      <label className="text-sm font-bold text-slate-800">
        Expected evidence
        <input
          className="form-control mt-2"
          maxLength={160}
          value={field.evidenceExpectation}
          onChange={(event) =>
            update("evidenceExpectation", event.target.value)
          }
        />
      </label>
      <label className="text-sm font-bold text-slate-800">
        Suggested discovery question
        <input
          className="form-control mt-2"
          maxLength={300}
          value={field.suggestedQuestion}
          onChange={(event) => update("suggestedQuestion", event.target.value)}
        />
      </label>
      <label className="text-sm font-bold text-slate-800">
        Customer fact
        <select
          className="form-control mt-2"
          value={field.canonicalFact}
          onChange={(event) =>
            update(
              "canonicalFact",
              event.target.value as FieldDraft["canonicalFact"],
            )
          }
        >
          {FACT_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-bold text-slate-800">
        Evidence category
        <select
          className="form-control mt-2"
          value={field.evidenceCategory}
          onChange={(event) =>
            update(
              "evidenceCategory",
              event.target.value as FieldDraft["evidenceCategory"],
            )
          }
        >
          {CATEGORY_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-bold text-slate-800">
        Freshness window (days)
        <input
          type="number"
          className="form-control mt-2"
          min={7}
          max={730}
          value={field.freshnessDays}
          onChange={(event) => update("freshnessDays", event.target.value)}
        />
      </label>
      <label className="text-sm font-bold text-slate-800">
        Expected by stage
        <select
          className="form-control mt-2"
          value={field.stageExpectation}
          onChange={(event) =>
            update(
              "stageExpectation",
              event.target.value as FieldDraft["stageExpectation"],
            )
          }
        >
          <option value="">No stage guidance</option>
          {STAGE_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {humanise(value)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-3 text-sm font-bold text-slate-800">
        <input
          type="checkbox"
          checked={field.required}
          onChange={(event) => update("required", event.target.checked)}
        />
        Core field
      </label>
    </div>
  );
}

function toFieldDefinition(
  field: FieldDraft,
  index: number,
): MethodologyFieldDefinition {
  return {
    key: field.key || keyFromName(field.displayName, index),
    displayName: field.displayName,
    explanation: field.explanation,
    order: index + 1,
    required: field.required,
    evidenceExpectations: [field.evidenceExpectation],
    canonicalFacts: [field.canonicalFact],
    evidenceCategories: [field.evidenceCategory],
    freshnessDays: field.freshnessDays ? Number(field.freshnessDays) : null,
    suggestedQuestions: [
      field.suggestedQuestion.endsWith("?")
        ? field.suggestedQuestion
        : `${field.suggestedQuestion}?`,
    ],
    stageExpectation: field.stageExpectation || null,
  };
}

function fromFieldDefinition(field: MethodologyFieldDefinition): FieldDraft {
  return {
    key: field.key,
    keyEdited: true,
    displayName: field.displayName,
    explanation: field.explanation,
    required: field.required,
    evidenceExpectation: field.evidenceExpectations[0] ?? "",
    canonicalFact: (field.canonicalFacts[0] ??
      "need") as FieldDraft["canonicalFact"],
    evidenceCategory: (field.evidenceCategories[0] ??
      "buying_signal") as FieldDraft["evidenceCategory"],
    freshnessDays: field.freshnessDays ? String(field.freshnessDays) : "",
    suggestedQuestion: field.suggestedQuestions[0] ?? "",
    stageExpectation: field.stageExpectation ?? "",
  };
}

function keyFromName(name: string, index: number): string {
  const key = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "");
  return /^[a-z]/u.test(key) ? key.slice(0, 64) : `field_${index + 1}`;
}
