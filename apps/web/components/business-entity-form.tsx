"use client";

import type {
  Company,
  Contact,
  EntityPage,
  Opportunity,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import {
  type BusinessEntityName,
  type EntityOption,
  entityLabels,
  humanise,
} from "@/lib/business-entities";

type FieldKind =
  | "text"
  | "email"
  | "url"
  | "tel"
  | "number"
  | "date"
  | "datetime-local"
  | "textarea"
  | "select"
  | "reference";

interface FieldConfig {
  name: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  options?: string[];
  reference?: "companies" | "contacts" | "opportunities";
  min?: number;
  max?: number;
  step?: string;
  placeholder?: string;
  fullWidth?: boolean;
}

type ReferenceOptions = Partial<
  Record<NonNullable<FieldConfig["reference"]>, EntityOption[]>
>;

const fields: Record<BusinessEntityName, FieldConfig[]> = {
  companies: [
    { name: "name", label: "Company name", kind: "text", required: true },
    {
      name: "website",
      label: "Website",
      kind: "url",
      placeholder: "https://example.com",
    },
    { name: "industry", label: "Industry", kind: "text" },
    {
      name: "employeeCount",
      label: "Employee count",
      kind: "number",
      min: 0,
      step: "1",
    },
    {
      name: "status",
      label: "Status",
      kind: "select",
      required: true,
      options: ["prospect", "active", "inactive"],
    },
  ],
  contacts: [
    {
      name: "companyId",
      label: "Company",
      kind: "reference",
      reference: "companies",
      required: true,
      fullWidth: true,
    },
    { name: "firstName", label: "First name", kind: "text", required: true },
    { name: "lastName", label: "Last name", kind: "text", required: true },
    { name: "email", label: "Email", kind: "email", required: true },
    { name: "phone", label: "Phone", kind: "tel" },
    { name: "jobTitle", label: "Job title", kind: "text" },
    {
      name: "linkedinUrl",
      label: "LinkedIn URL",
      kind: "url",
      placeholder: "https://www.linkedin.com/in/name",
    },
  ],
  opportunities: [
    {
      name: "companyId",
      label: "Company",
      kind: "reference",
      reference: "companies",
      fullWidth: true,
    },
    {
      name: "name",
      label: "Opportunity name",
      kind: "text",
      required: true,
      fullWidth: true,
    },
    {
      name: "stage",
      label: "Stage",
      kind: "select",
      required: true,
      options: [
        "qualification",
        "discovery",
        "evaluation",
        "proposal",
        "negotiation",
        "procurement",
        "closed_won",
        "closed_lost",
        "other",
      ],
    },
    {
      name: "status",
      label: "Status",
      kind: "select",
      required: true,
      options: ["open", "won", "lost", "on_hold"],
    },
    {
      name: "estimatedValue",
      label: "Estimated value",
      kind: "number",
      min: 0,
      step: "0.01",
    },
    {
      name: "currency",
      label: "Currency",
      kind: "select",
      options: ["AUD", "USD", "NZD", "GBP", "EUR"],
    },
    {
      name: "expectedCloseDate",
      label: "Expected close date",
      kind: "date",
    },
    {
      name: "description",
      label: "Description",
      kind: "textarea",
      fullWidth: true,
    },
  ],
  tasks: [
    {
      name: "title",
      label: "Task title",
      kind: "text",
      required: true,
      fullWidth: true,
    },
    {
      name: "description",
      label: "Description",
      kind: "textarea",
      fullWidth: true,
    },
    {
      name: "companyId",
      label: "Company",
      kind: "reference",
      reference: "companies",
    },
    {
      name: "contactId",
      label: "Contact",
      kind: "reference",
      reference: "contacts",
    },
    {
      name: "opportunityId",
      label: "Opportunity",
      kind: "reference",
      reference: "opportunities",
    },
    {
      name: "status",
      label: "Status",
      kind: "select",
      required: true,
      options: ["open", "in_progress", "completed", "cancelled"],
    },
    {
      name: "priority",
      label: "Priority",
      kind: "select",
      required: true,
      options: ["low", "medium", "high", "urgent"],
    },
    { name: "dueAt", label: "Due date and time", kind: "datetime-local" },
  ],
};

const createDefaults: Record<BusinessEntityName, Record<string, string>> = {
  companies: { status: "prospect" },
  contacts: {},
  opportunities: {
    stage: "discovery",
    status: "open",
  },
  tasks: { status: "open", priority: "medium" },
};

export function BusinessEntityForm({
  entity,
  entityId,
}: {
  entity: BusinessEntityName;
  entityId?: string;
}) {
  const router = useRouter();
  const labels = entityLabels[entity];
  const isEditing = Boolean(entityId);
  const formFields = useMemo(() => fields[entity], [entity]);
  const [values, setValues] = useState<Record<string, string>>(
    createDefaults[entity],
  );
  const [referenceOptions, setReferenceOptions] = useState<ReferenceOptions>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string | null>(
    null,
  );

  const loadForm = useCallback(
    async (signal: AbortSignal) => {
      const referenceNames = [
        ...new Set(
          formFields
            .map((field) => field.reference)
            .filter(
              (reference): reference is NonNullable<FieldConfig["reference"]> =>
                Boolean(reference),
            ),
        ),
      ];
      const optionEntries = await Promise.all(
        referenceNames.map(async (reference) => {
          const page = await apiRequest<
            EntityPage<Company | Contact | Opportunity>
          >(`/api/v1/${reference}?pageSize=100`, { signal });
          return [
            reference,
            page.items.map((item) => optionFor(reference, item)),
          ] as const;
        }),
      );
      let loadedValues = createDefaults[entity];
      let loadedUpdatedAt: string | null = null;
      if (entityId) {
        const record = await apiRequest<Record<string, unknown>>(
          `/api/v1/${entity}/${entityId}`,
          { signal },
        );
        loadedValues = valuesForForm(record, formFields);
        if (
          entity === "opportunities" &&
          typeof record.updatedAt === "string"
        ) {
          loadedUpdatedAt = record.updatedAt;
        }
      }
      return {
        options: Object.fromEntries(optionEntries) as ReferenceOptions,
        values: loadedValues,
        updatedAt: loadedUpdatedAt,
      };
    },
    [entity, entityId, formFields],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadForm(controller.signal)
      .then((loaded) => {
        setReferenceOptions(loaded.options);
        setValues(loaded.values);
        setExpectedUpdatedAt(loaded.updatedAt);
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setLoadError(
          requestError instanceof Error
            ? requestError.message
            : "The form could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [loadForm, retryKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const payload = payloadFor(formFields, values);
      if (entity === "opportunities" && entityId && expectedUpdatedAt) {
        payload.expectedUpdatedAt = expectedUpdatedAt;
      }
      const saved = await apiRequest<{ id?: string }>(
        `/api/v1/${entity}${entityId ? `/${entityId}` : ""}`,
        {
          method: entityId ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
      router.push(
        entity === "opportunities" && (entityId || saved.id)
          ? `/opportunities/${entityId ?? saved.id}`
          : `/${entity}`,
      );
    } catch (requestError: unknown) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The record could not be saved.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby={`${entity}-form-title`}>
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          {isEditing ? "Edit record" : "New record"}
        </p>
        <h1
          id={`${entity}-form-title`}
          className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
        >
          {isEditing ? `Edit ${labels.singular}` : `Create ${labels.singular}`}
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
          Required fields are marked. All data is saved to the active
          organisation only.
        </p>
      </header>

      {loading ? (
        <div
          role="status"
          className="rounded-2xl border border-slate-200 bg-white p-8"
        >
          Loading form…
        </div>
      ) : null}
      {!loading && loadError ? (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-6"
        >
          <h2 className="font-bold text-rose-950">Form could not be loaded</h2>
          <p className="mt-2 text-sm text-rose-800">{loadError}</p>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              setLoadError(null);
              setRetryKey((key) => key + 1);
            }}
            className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
          >
            Retry
          </button>
        </div>
      ) : null}
      {!loading && !loadError ? (
        <form
          onSubmit={submit}
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        >
          {submitError ? (
            <div
              id="form-error"
              role="alert"
              className="mb-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
            >
              {submitError}
            </div>
          ) : null}
          <div className="grid gap-6 sm:grid-cols-2">
            {formFields.map((field) => (
              <FormField
                key={field.name}
                field={field}
                value={values[field.name] ?? ""}
                options={
                  field.reference
                    ? (referenceOptions[field.reference] ?? [])
                    : []
                }
                onChange={(value) =>
                  setValues((current) => ({
                    ...current,
                    [field.name]: value,
                  }))
                }
              />
            ))}
          </div>
          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:justify-end">
            <Link
              href={`/${entity}`}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-300 px-5 text-sm font-bold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting}
              aria-describedby={submitError ? "form-error" : undefined}
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-teal-700 px-5 text-sm font-bold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-60"
            >
              {submitting
                ? "Saving…"
                : isEditing
                  ? `Save ${labels.singular}`
                  : `Create ${labels.singular}`}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

function FormField({
  field,
  value,
  options,
  onChange,
}: {
  field: FieldConfig;
  value: string;
  options: EntityOption[];
  onChange: (value: string) => void;
}) {
  const id = `field-${field.name}`;
  const className =
    "mt-2 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm text-slate-950 outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-100";

  return (
    <div className={field.fullWidth ? "sm:col-span-2" : undefined}>
      <label htmlFor={id} className="text-sm font-bold text-slate-800">
        {field.label}
        {field.required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {field.kind === "textarea" ? (
        <textarea
          id={id}
          name={field.name}
          value={value}
          required={field.required}
          onChange={(event) => onChange(event.target.value)}
          rows={5}
          className={`${className} py-3`}
        />
      ) : field.kind === "select" || field.kind === "reference" ? (
        <select
          id={id}
          name={field.name}
          value={value}
          required={field.required}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        >
          <option value="">
            {field.required ? `Select ${field.label.toLowerCase()}` : "None"}
          </option>
          {(field.kind === "select"
            ? (field.options ?? []).map((option) => ({
                value: option,
                label: humanise(option),
              }))
            : options
          ).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          name={field.name}
          type={field.kind}
          value={value}
          required={field.required}
          min={field.min}
          max={field.max}
          step={field.step}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        />
      )}
    </div>
  );
}

function optionFor(
  reference: NonNullable<FieldConfig["reference"]>,
  record: Company | Contact | Opportunity,
): EntityOption {
  if (reference === "companies") {
    const company = record as Company;
    return { value: company.id, label: company.name };
  }
  if (reference === "contacts") {
    const contact = record as Contact;
    return {
      value: contact.id,
      label: `${contact.firstName} ${contact.lastName}`,
    };
  }
  const opportunity = record as Opportunity;
  return { value: opportunity.id, label: opportunity.name };
}

function valuesForForm(
  record: Record<string, unknown>,
  formFields: FieldConfig[],
): Record<string, string> {
  return Object.fromEntries(
    formFields.map((field) => {
      const value = record[field.name];
      if (value === null || value === undefined) {
        return [field.name, ""];
      }
      if (field.kind === "datetime-local" && typeof value === "string") {
        const date = new Date(value);
        const local = new Date(
          date.getTime() - date.getTimezoneOffset() * 60_000,
        );
        return [field.name, local.toISOString().slice(0, 16)];
      }
      return [field.name, String(value)];
    }),
  );
}

function payloadFor(
  formFields: FieldConfig[],
  values: Record<string, string>,
): Record<string, string | number | null> {
  return Object.fromEntries(
    formFields.map((field) => {
      const value = values[field.name]?.trim() ?? "";
      if (!value && !field.required) {
        return [field.name, null];
      }
      if (field.kind === "number") {
        return [field.name, Number(value)];
      }
      if (field.kind === "datetime-local") {
        return [field.name, value ? new Date(value).toISOString() : null];
      }
      return [field.name, value];
    }),
  );
}
