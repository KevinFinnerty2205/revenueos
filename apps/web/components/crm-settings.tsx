"use client";

import type {
  CRMAvailability,
  CRMCustomFieldDefinition,
  CRMCustomFieldType,
  CRMEntityType,
} from "@revenueos/shared";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const fieldTypes: CRMCustomFieldType[] = [
  "short_text",
  "number",
  "date",
  "boolean",
  "single_select",
  "url",
];

export function CRMSettings() {
  const [availability, setAvailability] = useState<CRMAvailability | null>(
    null,
  );
  const [definitions, setDefinitions] = useState<CRMCustomFieldDefinition[]>(
    [],
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [entityType, setEntityType] = useState<CRMEntityType>("account");
  const [fieldType, setFieldType] = useState<CRMCustomFieldType>("short_text");
  const [fieldKey, setFieldKey] = useState("");
  const [label, setLabel] = useState("");
  const [options, setOptions] = useState("");

  const load = useCallback(async () => {
    const [nextAvailability, nextDefinitions] = await Promise.all([
      apiRequest<CRMAvailability>("/api/v1/crm/availability"),
      apiRequest<CRMCustomFieldDefinition[]>("/api/v1/crm/custom-fields"),
    ]);
    setAvailability(nextAvailability);
    setDefinitions(nextDefinitions);
  }, []);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void load()
        .then(() => {
          if (active) setMessage(null);
        })
        .catch(() => {
          if (active) setMessage("CRM settings could not be loaded.");
        });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  async function selectMode(mode: "native" | "external") {
    if (!confirmed) return;
    setSaving(true);
    setMessage(null);
    try {
      setAvailability(
        await apiRequest<CRMAvailability>("/api/v1/crm/settings", {
          method: "PUT",
          body: JSON.stringify({ mode, confirmed: true }),
        }),
      );
      setConfirmed(false);
      setMessage(
        mode === "native"
          ? "RevenueOS is now the native CRM system of record."
          : "HubSpot remains the external CRM system of record.",
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "CRM mode could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function createField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      await apiRequest<CRMCustomFieldDefinition>("/api/v1/crm/custom-fields", {
        method: "POST",
        body: JSON.stringify({
          entityType,
          fieldKey,
          label,
          fieldType,
          options:
            fieldType === "single_select"
              ? options
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean)
              : [],
          displayOrder: definitions.filter(
            (item) => item.entityType === entityType,
          ).length,
        }),
      });
      setFieldKey("");
      setLabel("");
      setOptions("");
      await load();
      setMessage("Custom field created.");
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The custom field could not be created.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function archiveField(definitionId: string) {
    setSaving(true);
    setMessage(null);
    try {
      await apiRequest(`/api/v1/crm/custom-fields/${definitionId}/archive`, {
        method: "POST",
      });
      await load();
      setMessage("Custom field archived. Existing history is preserved.");
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The custom field could not be archived.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="crm-settings-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Native CRM
      </p>
      <div className="mt-2 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="crm-settings-title" className="form-legend">
            CRM foundation
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Accounts, Contacts and Opportunities are always canonical RevenueOS
            records. This add-on unlocks system-of-record controls and
            organisation custom fields.
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-700">
            {availability?.message ?? "Loading CRM settings…"}
          </p>
        </div>
        {availability ? (
          <span className="inline-flex min-h-11 shrink-0 items-center rounded-full border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700">
            {availability.enabled
              ? "Included in plan"
              : availability.state === "read_only"
                ? "View only"
                : "Not included"}
          </span>
        ) : null}
      </div>

      {availability?.enabled ? (
        <div className="mt-6 space-y-6 border-t border-slate-200 pt-6">
          <fieldset>
            <legend className="font-semibold text-slate-950">
              System of record
            </legend>
            <p className="mt-1 text-sm text-slate-600">
              Current mode: <strong>{humanise(availability.mode)}</strong>
              {availability.externalConnected
                ? " · HubSpot connected"
                : " · No external CRM connected"}
            </p>
            <label className="mt-4 flex items-start gap-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                className="mt-1 h-4 w-4 accent-teal-700"
              />
              I understand that changing the system of record affects which
              mapped fields can be edited.
            </label>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                className="secondary-button"
                disabled={saving || !confirmed}
                onClick={() => void selectMode("native")}
              >
                Use RevenueOS as our CRM
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={
                  saving || !confirmed || !availability.externalConnected
                }
                onClick={() => void selectMode("external")}
              >
                Use HubSpot
              </button>
            </div>
          </fieldset>

          <div>
            <h3 className="font-semibold text-slate-950">Custom fields</h3>
            <p className="mt-1 text-sm text-slate-600">
              Up to 25 fields per record type. Field types cannot be changed
              after creation.
            </p>
            {definitions.length ? (
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {definitions.map((definition) => (
                  <li
                    key={definition.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3 text-sm"
                  >
                    <span>
                      <strong>{definition.label}</strong>
                      <br />
                      <span className="text-slate-500">
                        {humanise(definition.entityType)} ·{" "}
                        {humanise(definition.fieldType)}
                      </span>
                    </span>
                    <button
                      type="button"
                      className="text-sm font-bold text-rose-700 hover:text-rose-900"
                      disabled={saving}
                      onClick={() => void archiveField(definition.id)}
                    >
                      Archive
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-slate-500">
                No custom fields yet.
              </p>
            )}
          </div>

          <form
            onSubmit={(event) => void createField(event)}
            className="grid gap-4 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2"
          >
            <h3 className="font-semibold text-slate-950 sm:col-span-2">
              Create a custom field
            </h3>
            <label className="text-sm font-semibold text-slate-700">
              Record type
              <select
                className="form-input mt-2"
                value={entityType}
                onChange={(event) =>
                  setEntityType(event.target.value as CRMEntityType)
                }
              >
                <option value="account">Account</option>
                <option value="contact">Contact</option>
                <option value="opportunity">Opportunity</option>
              </select>
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Field type
              <select
                className="form-input mt-2"
                value={fieldType}
                onChange={(event) =>
                  setFieldType(event.target.value as CRMCustomFieldType)
                }
              >
                {fieldTypes.map((type) => (
                  <option key={type} value={type}>
                    {humanise(type)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Label
              <input
                required
                maxLength={100}
                className="form-input mt-2"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Field key
              <input
                required
                pattern="[a-z][a-z0-9_]*"
                maxLength={64}
                className="form-input mt-2"
                placeholder="renewal_date"
                value={fieldKey}
                onChange={(event) => setFieldKey(event.target.value)}
              />
            </label>
            {fieldType === "single_select" ? (
              <label className="text-sm font-semibold text-slate-700 sm:col-span-2">
                Options, separated by commas
                <input
                  required
                  className="form-input mt-2"
                  placeholder="Tier 1, Tier 2, Tier 3"
                  value={options}
                  onChange={(event) => setOptions(event.target.value)}
                />
              </label>
            ) : null}
            <button
              type="submit"
              className="primary-button sm:col-span-2 sm:justify-self-start"
              disabled={saving}
            >
              Create field
            </button>
          </form>
        </div>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {message}
        </p>
      ) : null}
    </section>
  );
}
