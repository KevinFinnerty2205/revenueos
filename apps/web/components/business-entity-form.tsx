"use client";

import type {
  Company,
  Contact,
  CRMEntityType,
  Opportunity,
  OpportunityListItem,
  Task,
  TenantEntityPage,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FormEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiClientError, apiRequest } from "@/lib/api";
import {
  type BusinessEntityName,
  type EntityOption,
  entityLabels,
  humanise,
} from "@/lib/business-entities";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import {
  decodeCRMMemberListResponse,
  decodeTenantPage,
  isCompanyResponse,
  isContactResponse,
  isOpportunityListItemResponse,
  isOpportunityResponse,
  isRecord,
  isTaskResponse,
} from "@/lib/private-response-identity";

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
  reference?: "companies" | "contacts" | "opportunities" | "members";
  min?: number;
  max?: number;
  step?: string;
  placeholder?: string;
  fullWidth?: boolean;
}

type ReferenceOptions = Partial<
  Record<NonNullable<FieldConfig["reference"]>, EntityOption[]>
>;

type CRMFieldAuthority =
  "revenueos_authoritative" | "crm_authoritative" | "review_before_sync";
type ReferenceRecord = Company | Contact | Opportunity | OpportunityListItem;
type BusinessEntityRecord = Company | Contact | Opportunity | Task;

const fields: Record<BusinessEntityName, FieldConfig[]> = {
  companies: [
    { name: "name", label: "Account name", kind: "text", required: true },
    {
      name: "website",
      label: "Website",
      kind: "url",
      placeholder: "https://example.com",
    },
    { name: "industry", label: "Industry", kind: "text" },
    { name: "location", label: "Location", kind: "text" },
    {
      name: "employeeCount",
      label: "Employee count",
      kind: "number",
      min: 0,
      step: "1",
    },
    {
      name: "ownerUserId",
      label: "Owner",
      kind: "reference",
      reference: "members",
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
      label: "Account",
      kind: "reference",
      reference: "companies",
      required: true,
      fullWidth: true,
    },
    { name: "firstName", label: "First name", kind: "text", required: true },
    { name: "lastName", label: "Last name", kind: "text", required: true },
    { name: "email", label: "Business email", kind: "email" },
    { name: "phone", label: "Phone", kind: "tel" },
    { name: "jobTitle", label: "Job title", kind: "text" },
    {
      name: "linkedinUrl",
      label: "LinkedIn URL",
      kind: "url",
      placeholder: "https://www.linkedin.com/in/name",
    },
    {
      name: "status",
      label: "Employment status",
      kind: "select",
      required: true,
      options: ["active", "left_company"],
    },
    {
      name: "ownerUserId",
      label: "Owner",
      kind: "reference",
      reference: "members",
    },
  ],
  opportunities: [
    {
      name: "companyId",
      label: "Account",
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
    {
      name: "ownerUserId",
      label: "Owner",
      kind: "reference",
      reference: "members",
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
      label: "Person",
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
      name: "assignedUserId",
      label: "Assignee",
      kind: "reference",
      reference: "members",
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
  contacts: { status: "active" },
  opportunities: {},
  tasks: { status: "open", priority: "medium" },
};

export function BusinessEntityForm({
  entity,
  entityId,
  initialCompanyId,
}: BusinessEntityFormProps) {
  const organisation = useVerifiedOrganisation();
  if (organisation.status === "loading") {
    return (
      <section className="form-card" aria-busy="true">
        <p role="status" className="text-sm text-slate-600">
          Verifying your secure workspace…
        </p>
      </section>
    );
  }
  if (organisation.status !== "available") {
    return (
      <section className="form-card border-rose-200 bg-rose-50" role="alert">
        <p className="text-sm text-rose-900">
          Your organisation could not be verified. This form is temporarily
          unavailable.
        </p>
      </section>
    );
  }
  return (
    <BusinessEntityFormSession
      key={`${organisation.organisationId}:${entity}:${entityId ?? "new"}:${initialCompanyId ?? ""}`}
      organisationId={organisation.organisationId}
      entity={entity}
      entityId={entityId}
      initialCompanyId={initialCompanyId}
    />
  );
}

interface BusinessEntityFormProps {
  entity: BusinessEntityName;
  entityId?: string;
  initialCompanyId?: string;
}

function BusinessEntityFormSession({
  organisationId,
  entity,
  entityId,
  initialCompanyId,
}: BusinessEntityFormProps & { organisationId: string }) {
  const router = useRouter();
  const sessionActive = useRef(true);
  const labels = entityLabels[entity];
  const isEditing = Boolean(entityId);
  const formFields = useMemo(() => fields[entity], [entity]);
  const memberReferenceField = useMemo(
    () => formFields.find((field) => field.reference === "members"),
    [formFields],
  );
  const [values, setValues] = useState<Record<string, string>>(
    initialCompanyId
      ? { ...createDefaults[entity], companyId: initialCompanyId }
      : createDefaults[entity],
  );
  const [referenceOptions, setReferenceOptions] = useState<ReferenceOptions>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [duplicateLink, setDuplicateLink] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string | null>(
    null,
  );
  const [initialMemberReference, setInitialMemberReference] = useState<
    { fieldName: string; value: string } | undefined
  >(undefined);
  const [readOnlyFields, setReadOnlyFields] = useState<ReadonlySet<string>>(
    new Set(),
  );

  useLayoutEffect(() => {
    sessionActive.current = true;
    return () => {
      sessionActive.current = false;
    };
  }, []);

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
          if (reference === "members") {
            const response = await apiRequest<unknown>("/api/v1/crm/members", {
              signal,
            });
            const members = decodeCRMMemberListResponse(
              response,
              organisationId,
            );
            if (!members) {
              throw new Error(
                "The member list could not be verified. Try loading the form again.",
              );
            }
            return [
              reference,
              members.map((member) => ({
                value: member.userId,
                label: `${member.displayName}${
                  !member.active
                    ? " (inactive)"
                    : member.canAssign
                      ? ""
                      : " (not assignable)"
                }`,
                disabled: !member.active || !member.canAssign,
              })),
            ] as const;
          }
          const response = await apiRequest<unknown>(
            `/api/v1/${reference}?pageSize=100`,
            { signal },
          );
          const page = decodeReferencePage(reference, response, organisationId);
          if (!page) {
            throw new Error(
              "A relationship list could not be verified. Try loading the form again.",
            );
          }
          return [
            reference,
            page.items
              .filter(isAvailableReferenceRecord)
              .map((item) => optionFor(reference, item)),
          ] as const;
        }),
      );
      let loadedValues = initialCompanyId
        ? { ...createDefaults[entity], companyId: initialCompanyId }
        : createDefaults[entity];
      let loadedUpdatedAt: string | null = null;
      let loadedReadOnlyFields: ReadonlySet<string> = new Set();
      if (entityId) {
        const [recordResponse, crmRecordResponse] = await Promise.all([
          apiRequest<unknown>(
            `/api/v1/${entity}/${encodeURIComponent(entityId)}`,
            { signal },
          ),
          entity === "tasks"
            ? Promise.resolve(null)
            : apiRequest<unknown>(
                `/api/v1/crm/records/${crmEntityType(entity)}/${encodeURIComponent(entityId)}`,
                { signal },
              ),
        ]);
        const record = decodeBusinessEntityResponse(
          entity,
          recordResponse,
          organisationId,
        );
        if (
          !record ||
          record.id !== entityId ||
          !isActiveBusinessEntity(entity, record)
        ) {
          throw new Error(
            "The requested record could not be verified. Try loading it again.",
          );
        }
        loadedValues = valuesForForm(
          record as unknown as Record<string, unknown>,
          formFields,
        );
        if (entity !== "tasks") {
          loadedUpdatedAt = record.updatedAt;
          const fieldAuthority = decodeCRMFieldAuthority(
            crmRecordResponse,
            organisationId,
            crmEntityType(entity),
            entityId,
          );
          if (!fieldAuthority) {
            throw new Error(
              "The record authority could not be verified. Try loading it again.",
            );
          }
          loadedReadOnlyFields = new Set(
            Object.entries(fieldAuthority)
              .filter(([, authority]) => authority === "crm_authoritative")
              .map(([field]) => camelCaseField(field)),
          );
        }
      }
      const loadedOptions = Object.fromEntries(
        optionEntries,
      ) as ReferenceOptions;
      const exactOptionEntries = await Promise.all(
        formFields.map(async (field) => {
          const reference = field.reference;
          const selectedId = loadedValues[field.name];
          if (
            !reference ||
            reference === "members" ||
            !selectedId ||
            loadedOptions[reference]?.some(
              (option) => option.value === selectedId,
            )
          ) {
            return null;
          }
          const response = await apiRequest<unknown>(
            `/api/v1/${reference}/${encodeURIComponent(selectedId)}`,
            { signal },
          );
          const record = decodeExactReferenceRecord(
            reference,
            response,
            organisationId,
          );
          if (
            !record ||
            record.id !== selectedId ||
            !isAvailableReferenceRecord(record)
          ) {
            throw new Error(
              "A linked record could not be verified. Try loading the form again.",
            );
          }
          return [reference, optionFor(reference, record)] as const;
        }),
      );
      for (const entry of exactOptionEntries) {
        if (!entry) continue;
        const [reference, option] = entry;
        const current = loadedOptions[reference] ?? [];
        if (!current.some((candidate) => candidate.value === option.value)) {
          loadedOptions[reference] = [...current, option];
        }
      }
      return {
        options: loadedOptions,
        values: loadedValues,
        updatedAt: loadedUpdatedAt,
        readOnlyFields: loadedReadOnlyFields,
      };
    },
    [entity, entityId, formFields, initialCompanyId, organisationId],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadForm(controller.signal)
      .then((loaded) => {
        setReferenceOptions(loaded.options);
        setValues(loaded.values);
        setExpectedUpdatedAt(loaded.updatedAt);
        setReadOnlyFields(loaded.readOnlyFields);
        setInitialMemberReference(
          entityId && memberReferenceField
            ? {
                fieldName: memberReferenceField.name,
                value: loaded.values[memberReferenceField.name] ?? "",
              }
            : undefined,
        );
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
  }, [entityId, loadForm, memberReferenceField, retryKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setDuplicateLink(null);
    setSubmitting(true);
    try {
      const payloadFields = formFields.filter(
        (field) =>
          !readOnlyFields.has(field.name) &&
          !(
            entityId &&
            field.reference === "members" &&
            initialMemberReference?.fieldName === field.name &&
            values[field.name] === initialMemberReference.value
          ),
      );
      const payload = payloadFor(payloadFields, values);
      if (entity !== "tasks" && entityId && expectedUpdatedAt) {
        payload.expectedUpdatedAt = expectedUpdatedAt;
      }
      const response = await apiRequest<unknown>(
        `/api/v1/${entity}${entityId ? `/${encodeURIComponent(entityId)}` : ""}`,
        {
          method: entityId ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
      if (!sessionActive.current) return;
      const saved = decodeBusinessEntityResponse(
        entity,
        response,
        organisationId,
      );
      if (
        !saved ||
        (entityId !== undefined && saved.id !== entityId) ||
        !isActiveBusinessEntity(entity, saved)
      ) {
        throw new Error(
          "The saved record could not be verified. Try saving it again.",
        );
      }
      router.push(
        entity === "opportunities"
          ? `/opportunities/${encodeURIComponent(saved.id)}`
          : `/${entity}`,
      );
    } catch (requestError: unknown) {
      if (!sessionActive.current) return;
      if (
        requestError instanceof ApiClientError &&
        requestError.details?.entityId
      ) {
        const duplicateEntity = requestError.details.entityType;
        setDuplicateLink(
          duplicateEntity === "account"
            ? `/companies/${encodeURIComponent(requestError.details.entityId)}`
            : `/contacts/${encodeURIComponent(requestError.details.entityId)}`,
        );
      }
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The record could not be saved.",
      );
    } finally {
      if (sessionActive.current) setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby={`${entity}-form-title`}>
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
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
              {duplicateLink ? (
                <Link href={duplicateLink} className="ml-2 font-bold underline">
                  Open existing record
                </Link>
              ) : null}
            </div>
          ) : null}
          <div className="grid gap-6 sm:grid-cols-2">
            {formFields.map((field) => (
              <FormField
                key={field.name}
                field={field}
                required={field.required}
                disabled={readOnlyFields.has(field.name)}
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
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-brand-primary px-5 text-sm font-bold text-white hover:bg-brand-secondary disabled:cursor-wait disabled:opacity-60"
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
  required,
  disabled,
  value,
  options,
  onChange,
}: {
  field: FieldConfig;
  required?: boolean;
  disabled?: boolean;
  value: string;
  options: EntityOption[];
  onChange: (value: string) => void;
}) {
  const id = `field-${field.name}`;
  const isRequired = required ?? field.required;
  const className =
    "mt-2 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm text-slate-950 outline-none transition focus:border-brand-secondary focus:ring-2 focus:ring-brand-secondary/20";

  return (
    <div className={field.fullWidth ? "sm:col-span-2" : undefined}>
      <label htmlFor={id} className="text-sm font-bold text-slate-800">
        {field.label}
        {isRequired ? <span aria-hidden="true"> *</span> : null}
      </label>
      {field.kind === "textarea" ? (
        <textarea
          id={id}
          name={field.name}
          value={value}
          required={isRequired}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          rows={5}
          className={`${className} py-3`}
        />
      ) : field.kind === "select" || field.kind === "reference" ? (
        <select
          id={id}
          name={field.name}
          value={value}
          required={isRequired}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        >
          <option value="">
            {isRequired ? `Select ${field.label.toLowerCase()}` : "None"}
          </option>
          {(field.kind === "select"
            ? (field.options ?? []).map((option) => ({
                value: option,
                label: humanise(option),
              }))
            : options.filter(
                (option) => !option.disabled || option.value === value,
              )
          ).map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={"disabled" in option && option.disabled === true}
            >
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
          required={isRequired}
          disabled={disabled}
          min={field.min}
          max={field.max}
          step={field.step}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        />
      )}
      {disabled ? (
        <p className="mt-2 text-xs font-semibold text-blue-700">
          CRM controlled · read-only in Oryntela
        </p>
      ) : null}
    </div>
  );
}

function optionFor(
  reference: Exclude<NonNullable<FieldConfig["reference"]>, "members">,
  record: ReferenceRecord,
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

function isAvailableReferenceRecord(record: ReferenceRecord): boolean {
  return record.archivedAt === null;
}

function decodeReferencePage(
  reference: Exclude<NonNullable<FieldConfig["reference"]>, "members">,
  value: unknown,
  organisationId: string,
): TenantEntityPage<ReferenceRecord> | null {
  if (reference === "companies") {
    return decodeTenantPage(value, organisationId, isCompanyResponse, {
      expectedPage: 1,
    });
  }
  if (reference === "contacts") {
    return decodeTenantPage(value, organisationId, isContactResponse, {
      expectedPage: 1,
    });
  }
  return decodeTenantPage(
    value,
    organisationId,
    isOpportunityListItemResponse,
    { expectedPage: 1 },
  );
}

function decodeExactReferenceRecord(
  reference: Exclude<NonNullable<FieldConfig["reference"]>, "members">,
  value: unknown,
  organisationId: string,
): Company | Contact | Opportunity | null {
  if (reference === "companies") {
    return isCompanyResponse(value, organisationId) ? value : null;
  }
  if (reference === "contacts") {
    return isContactResponse(value, organisationId) ? value : null;
  }
  return isOpportunityResponse(value, organisationId) ? value : null;
}

function decodeBusinessEntityResponse(
  entity: BusinessEntityName,
  value: unknown,
  organisationId: string,
): BusinessEntityRecord | null {
  if (entity === "companies") {
    return isCompanyResponse(value, organisationId) ? value : null;
  }
  if (entity === "contacts") {
    return isContactResponse(value, organisationId) ? value : null;
  }
  if (entity === "opportunities") {
    return isOpportunityResponse(value, organisationId) ? value : null;
  }
  return isTaskResponse(value, organisationId) ? value : null;
}

function isActiveBusinessEntity(
  entity: BusinessEntityName,
  record: BusinessEntityRecord,
): boolean {
  return (
    entity === "tasks" || ("archivedAt" in record && record.archivedAt === null)
  );
}

const crmFieldAuthorities = new Set<CRMFieldAuthority>([
  "revenueos_authoritative",
  "crm_authoritative",
  "review_before_sync",
]);

function decodeCRMFieldAuthority(
  value: unknown,
  organisationId: string,
  expectedEntityType: CRMEntityType,
  expectedEntityId: string,
): Record<string, CRMFieldAuthority> | null {
  if (
    !isRecord(value) ||
    value.organisationId !== organisationId ||
    value.entityType !== expectedEntityType ||
    value.entityId !== expectedEntityId ||
    value.archivedAt !== null ||
    !isRecord(value.fieldAuthority) ||
    Array.isArray(value.fieldAuthority)
  ) {
    return null;
  }
  const entries = Object.entries(value.fieldAuthority);
  if (
    !entries.every(
      ([field, authority]) =>
        field.trim().length > 0 &&
        typeof authority === "string" &&
        crmFieldAuthorities.has(authority as CRMFieldAuthority),
    )
  ) {
    return null;
  }
  return Object.fromEntries(entries) as Record<string, CRMFieldAuthority>;
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
  optionalFields: ReadonlySet<string> = new Set(),
): Record<string, string | number | null> {
  return Object.fromEntries(
    formFields.map((field) => {
      const value = values[field.name]?.trim() ?? "";
      if (!value && (!field.required || optionalFields.has(field.name))) {
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

function crmEntityType(
  entity: Exclude<BusinessEntityName, "tasks">,
): "account" | "contact" | "opportunity" {
  if (entity === "companies") return "account";
  if (entity === "contacts") return "contact";
  return "opportunity";
}

function camelCaseField(value: string): string {
  return value.replace(/_([a-z])/g, (_, letter: string) =>
    letter.toUpperCase(),
  );
}
