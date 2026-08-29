"use client";

import type {
  CRMCustomFieldValue,
  CRMEntityType,
  CRMRecord,
} from "@revenueos/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function CRMRecordPanel({
  entityType,
  entityId,
}: {
  entityType: CRMEntityType;
  entityId: string;
}) {
  const [record, setRecord] = useState<CRMRecord | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string | boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    const next = await apiRequest<CRMRecord>(
      `/api/v1/crm/records/${entityType}/${entityId}`,
    );
    setRecord(next);
    setDrafts(
      Object.fromEntries(
        next.customFields.map((field) => [
          field.definition.id,
          field.value ?? "",
        ]),
      ),
    );
  }, [entityId, entityType]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load().catch((reason: unknown) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "The CRM record could not be loaded.",
        ),
      );
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function saveField(field: CRMCustomFieldValue) {
    if (!record) return;
    setSaving(field.definition.id);
    setError(null);
    try {
      const draft = drafts[field.definition.id];
      const value =
        draft === ""
          ? null
          : field.definition.fieldType === "number"
            ? Number(draft)
            : draft;
      await apiRequest(
        `/api/v1/crm/records/${entityType}/${entityId}/custom-fields/${field.definition.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            value,
            expectedRecordUpdatedAt: record.recordUpdatedAt,
          }),
        },
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The custom field could not be saved.",
      );
    } finally {
      setSaving(null);
    }
  }

  async function changeArchiveState() {
    if (!record) return;
    const action = record.archivedAt ? "restore" : "archive";
    if (
      !window.confirm(
        `${record.archivedAt ? "Restore" : "Archive"} ${record.title}?`,
      )
    )
      return;
    setSaving(action);
    setError(null);
    try {
      await apiRequest(
        `/api/v1/crm/records/${entityType}/${entityId}/${action}`,
        { method: "POST" },
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The record lifecycle could not be changed.",
      );
    } finally {
      setSaving(null);
    }
  }

  if (error && !record)
    return (
      <section role="alert" className="form-card text-rose-900">
        {error}
      </section>
    );
  if (!record)
    return (
      <p role="status" className="form-card text-sm text-slate-600">
        Loading CRM record…
      </p>
    );

  const editHref =
    entityType === "account"
      ? `/companies/${entityId}/edit`
      : entityType === "contact"
        ? `/contacts/${entityId}/edit`
        : `/opportunities/${entityId}/edit`;

  return (
    <div className="space-y-6">
      <section
        className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        aria-labelledby="crm-record-title"
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
              {humanise(entityType)} record
            </p>
            <h1
              id="crm-record-title"
              className="mt-2 text-3xl font-semibold tracking-tight text-slate-950"
            >
              {record.title}
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              Owned by {record.ownerName} · {humanise(record.mode)} CRM mode
            </p>
            {record.archivedAt ? (
              <p className="mt-3 inline-flex rounded-full bg-amber-100 px-3 py-1 text-sm font-bold text-amber-900">
                Archived {formatDate(record.archivedAt)}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-3">
            {!record.archivedAt ? (
              <Link className="secondary-button" href={editHref}>
                Edit core fields
              </Link>
            ) : null}
            {record.crmEnabled && record.canManage ? (
              <button
                type="button"
                className="secondary-button"
                disabled={saving !== null}
                onClick={() => void changeArchiveState()}
              >
                {record.archivedAt ? "Restore" : "Archive"}
              </button>
            ) : null}
          </div>
        </div>
        {Object.entries(record.fieldAuthority).some(
          ([, authority]) => authority === "crm_authoritative",
        ) ? (
          <p className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
            Fields marked as CRM-controlled are read-only in RevenueOS.
            Review-before-sync fields remain editable and require the existing
            sync review flow.
          </p>
        ) : null}
        {error ? (
          <p
            role="alert"
            className="mt-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
          >
            {error}
          </p>
        ) : null}
        <dl className="mt-6 grid gap-3 border-t border-slate-200 pt-6 sm:grid-cols-2 lg:grid-cols-3">
          {record.coreFields.map((field) => (
            <div key={field.key} className="rounded-xl bg-slate-50 p-4">
              <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {field.label}
              </dt>
              <dd className="mt-1 break-words text-sm font-semibold text-slate-900">
                {field.value ?? "Not set"}
              </dd>
              {field.authority !== "revenueos_authoritative" ? (
                <p
                  className={`mt-2 text-xs font-bold ${
                    field.authority === "crm_authoritative"
                      ? "text-blue-700"
                      : "text-amber-700"
                  }`}
                >
                  {field.authority === "crm_authoritative"
                    ? "CRM controlled · read-only"
                    : "Review before sync"}
                </p>
              ) : null}
            </div>
          ))}
        </dl>
      </section>

      <details className="form-card group">
        <summary className="cursor-pointer list-none font-semibold text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2">
          <span className="flex items-center justify-between gap-4">
            <span>
              CRM details
              <span className="mt-1 block text-sm font-normal text-slate-600">
                Custom fields stay secondary to the relationship overview.
              </span>
            </span>
            <span aria-hidden="true" className="text-teal-700">
              <span className="group-open:hidden">Show</span>
              <span className="hidden group-open:inline">Hide</span>
            </span>
          </span>
        </summary>
        <div className="mt-6 border-t border-slate-200 pt-6">
          <h2 className="form-legend">Custom fields</h2>
          {!record.crmEnabled ? (
            <p className="mt-2 text-sm text-slate-600">
              CRM administration is not in this organisation’s plan. Existing
              custom-field data remains readable.
            </p>
          ) : null}
          {record.customFields.length ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              {record.customFields.map((field) => (
                <div
                  key={field.definition.id}
                  className="rounded-xl border border-slate-200 p-4"
                >
                  <label
                    className="text-sm font-bold text-slate-800"
                    htmlFor={`custom-${field.definition.id}`}
                  >
                    {field.definition.label}
                  </label>
                  <CustomFieldInput
                    field={field}
                    value={drafts[field.definition.id] ?? ""}
                    disabled={!field.editable || record.archivedAt !== null}
                    onChange={(value) =>
                      setDrafts((current) => ({
                        ...current,
                        [field.definition.id]: value,
                      }))
                    }
                  />
                  {field.editable ? (
                    <button
                      type="button"
                      className="mt-3 text-sm font-bold text-teal-700 hover:text-teal-900 disabled:opacity-50"
                      disabled={saving !== null || record.archivedAt !== null}
                      onClick={() => void saveField(field)}
                    >
                      {saving === field.definition.id
                        ? "Saving…"
                        : "Save field"}
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">
              No custom fields have been configured for this record type.
            </p>
          )}
        </div>
      </details>

      <section className="form-card" aria-labelledby="activity-title">
        <h2 id="activity-title" className="form-legend">
          Relationship activity
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          A recent, bounded view of existing Interactions, Outreach, Actions,
          Events and linked Opportunities.
        </p>
        {record.activity.length ? (
          <ol className="mt-5 divide-y divide-slate-100">
            {record.activity.map((item) => (
              <li key={item.id} className="py-4 first:pt-0">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-teal-700">
                      {item.sourceLabel}
                    </p>
                    {item.href ? (
                      <Link
                        href={item.href}
                        className="mt-1 block font-semibold text-slate-950 hover:text-teal-800"
                      >
                        {item.title}
                      </Link>
                    ) : (
                      <p className="mt-1 font-semibold text-slate-950">
                        {item.title}
                      </p>
                    )}
                    <p className="mt-1 text-sm text-slate-600">
                      {item.detail ?? "Recorded activity"}
                    </p>
                  </div>
                  <time
                    className="shrink-0 text-xs text-slate-500"
                    dateTime={item.occurredAt}
                  >
                    {formatDate(item.occurredAt)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No related activity yet.
          </p>
        )}
      </section>

      <details className="form-card group">
        <summary className="cursor-pointer list-none font-semibold text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2">
          <span className="flex items-center justify-between gap-4">
            <span>
              Record history
              <span className="mt-1 block text-sm font-normal text-slate-600">
                Review who changed CRM fields, when and from which source.
              </span>
            </span>
            <span aria-hidden="true" className="text-teal-700">
              <span className="group-open:hidden">Show</span>
              <span className="hidden group-open:inline">Hide</span>
            </span>
          </span>
        </summary>
        {record.history.length ? (
          <ol className="mt-5 space-y-3 border-t border-slate-200 pt-5">
            {record.history.map((change) => (
              <li
                key={change.id}
                className="rounded-xl bg-slate-50 p-4 text-sm"
              >
                <p className="font-semibold text-slate-900">
                  {historyLabel(change.fieldKey)}
                </p>
                <p className="mt-1 text-slate-600">
                  {historyValue(change.fieldKey, change.oldValue, record)} →{" "}
                  {historyValue(change.fieldKey, change.newValue, record)}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  {change.changedByName} · {humanise(change.source)} ·{" "}
                  {formatDate(change.changedAt)}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No recorded field changes yet.
          </p>
        )}
      </details>
    </div>
  );
}

function CustomFieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: CRMCustomFieldValue;
  value: string | boolean;
  disabled: boolean;
  onChange: (value: string | boolean) => void;
}) {
  const id = `custom-${field.definition.id}`;
  if (field.definition.fieldType === "boolean")
    return (
      <select
        id={id}
        className="form-input mt-2"
        value={String(value)}
        disabled={disabled}
        onChange={(event) =>
          onChange(
            event.target.value === "" ? "" : event.target.value === "true",
          )
        }
      >
        <option value="">Not set</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    );
  if (field.definition.fieldType === "single_select")
    return (
      <select
        id={id}
        className="form-input mt-2"
        value={String(value)}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Not set</option>
        {value !== "" && !field.definition.options.includes(String(value)) ? (
          <option value={String(value)} disabled>
            {String(value)} (retired)
          </option>
        ) : null}
        {field.definition.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  return (
    <input
      id={id}
      className="form-input mt-2"
      disabled={disabled}
      type={
        field.definition.fieldType === "number"
          ? "number"
          : field.definition.fieldType === "date"
            ? "date"
            : field.definition.fieldType === "url"
              ? "url"
              : "text"
      }
      value={String(value)}
      step={field.definition.fieldType === "number" ? "0.0001" : undefined}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function historyLabel(fieldKey: string): string {
  if (fieldKey === "owner_user_id") return "Owner";
  return humanise(fieldKey.replace("custom.", ""));
}

function historyValue(
  fieldKey: string,
  value: unknown,
  record: CRMRecord,
): string {
  if (fieldKey !== "owner_user_id") return displayValue(value);
  if (value === null || value === undefined || value === "")
    return "Unassigned";
  return String(value) === record.ownerUserId
    ? record.ownerName
    : "Previous organisation member";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
