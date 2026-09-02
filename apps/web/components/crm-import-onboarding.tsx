"use client";

import type {
  CRMAvailability,
  CRMCustomFieldDefinition,
  CRMEntityType,
  CRMImportPreview,
  CRMMember,
  SalesPipeline,
} from "@revenueos/shared";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiBlob, apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

type ColumnMapping = Record<string, string | null>;
type ValueMapping = Record<string, string>;

const coreTargets: Record<CRMEntityType, { value: string; label: string }[]> = {
  account: [
    { value: "name", label: "Name (required)" },
    { value: "website", label: "Website" },
    { value: "industry", label: "Industry" },
    { value: "location", label: "Location" },
    { value: "employee_count", label: "Employee count" },
    { value: "status", label: "Status" },
    { value: "owner", label: "Owner name" },
  ],
  contact: [
    { value: "first_name", label: "First name (required)" },
    { value: "last_name", label: "Last name (required)" },
    { value: "email", label: "Business email" },
    { value: "phone", label: "Phone" },
    { value: "job_title", label: "Job title" },
    { value: "linkedin_url", label: "LinkedIn URL" },
    { value: "account_domain", label: "Account domain" },
    { value: "account_name", label: "Account name" },
    { value: "status", label: "Status" },
    { value: "owner", label: "Owner name" },
    { value: "do_not_contact", label: "Do not contact" },
  ],
  opportunity: [
    { value: "name", label: "Name (required)" },
    { value: "account_domain", label: "Account domain" },
    { value: "account_name", label: "Account name" },
    { value: "stage", label: "Open stage (required)" },
    { value: "estimated_value", label: "Estimated value" },
    { value: "currency", label: "Currency" },
    { value: "expected_close_date", label: "Expected close date" },
    { value: "description", label: "Description" },
    { value: "owner", label: "Owner name" },
  ],
};

export function CRMImportOnboarding() {
  const [availability, setAvailability] = useState<CRMAvailability | null>(
    null,
  );
  const [members, setMembers] = useState<CRMMember[]>([]);
  const [definitions, setDefinitions] = useState<CRMCustomFieldDefinition[]>(
    [],
  );
  const [pipelines, setPipelines] = useState<SalesPipeline[]>([]);
  const [entityType, setEntityType] = useState<CRMEntityType>("account");
  const [fileName, setFileName] = useState("");
  const [contentBase64, setContentBase64] = useState("");
  const [csvRows, setCsvRows] = useState<string[][]>([]);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [defaultOwner, setDefaultOwner] = useState("");
  const [ownerMapping, setOwnerMapping] = useState<ValueMapping>({});
  const [pipelineId, setPipelineId] = useState("");
  const [stageMapping, setStageMapping] = useState<ValueMapping>({});
  const [preview, setPreview] = useState<CRMImportPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [nextAvailability, nextMembers, nextDefinitions, nextPipelines] =
      await Promise.all([
        apiRequest<CRMAvailability>("/api/v1/crm/availability"),
        apiRequest<CRMMember[]>("/api/v1/crm/members"),
        apiRequest<CRMCustomFieldDefinition[]>("/api/v1/crm/custom-fields"),
        apiRequest<SalesPipeline[]>("/api/v1/pipelines"),
      ]);
    setAvailability(nextAvailability);
    setMembers(nextMembers.filter((member) => member.active));
    setDefinitions(nextDefinitions.filter((definition) => definition.active));
    setPipelines(nextPipelines.filter((pipeline) => pipeline.active));
    setDefaultOwner(
      (current) =>
        current || nextMembers.find((member) => member.active)?.userId || "",
    );
    setPipelineId(
      (current) =>
        current ||
        nextPipelines.find((pipeline) => pipeline.isDefault)?.id ||
        "",
    );
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load().catch((reason: unknown) =>
        setMessage(
          reason instanceof Error
            ? reason.message
            : "CRM import settings could not be loaded.",
        ),
      );
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const headers = csvRows[0] ?? [];
  const ownerValues = useMemo(
    () => mappedValues(csvRows, mapping, "owner"),
    [csvRows, mapping],
  );
  const stageValues = useMemo(
    () => mappedValues(csvRows, mapping, "stage"),
    [csvRows, mapping],
  );
  const selectedPipeline =
    pipelines.find((pipeline) => pipeline.id === pipelineId) ?? null;
  const availableTargets = [
    ...coreTargets[entityType],
    ...definitions
      .filter((definition) => definition.entityType === entityType)
      .map((definition) => ({
        value: `custom:${definition.id}`,
        label: definition.label,
      })),
  ];

  function resetPreview() {
    setPreview(null);
    setConfirmed(false);
  }

  function changeEntity(next: CRMEntityType) {
    setEntityType(next);
    setMapping(Object.fromEntries(headers.map((header) => [header, null])));
    setOwnerMapping({});
    setStageMapping({});
    resetPreview();
  }

  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    resetPreview();
    setMessage(null);
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setMessage("Choose a CSV file no larger than 5 MB.");
      event.target.value = "";
      return;
    }
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const text = new TextDecoder("utf-8", { fatal: true })
        .decode(bytes)
        .replace(/^\uFEFF/u, "");
      const rows = parseCsv(text);
      if (rows.length < 2 || rows[0].length === 0)
        throw new Error("The CSV needs headers and at least one row.");
      const nextHeaders = rows[0].map((header) => header.trim());
      if (nextHeaders.some((header) => !header))
        throw new Error("Every CSV column needs a header.");
      setFileName(file.name);
      setContentBase64(bytesToBase64(bytes));
      setCsvRows([nextHeaders, ...rows.slice(1)]);
      setMapping(
        Object.fromEntries(nextHeaders.map((header) => [header, null])),
      );
      setOwnerMapping({});
      setStageMapping({});
      setMessage(
        "CSV loaded in this browser. Map or explicitly ignore every column before previewing.",
      );
    } catch (reason) {
      setFileName("");
      setContentBase64("");
      setCsvRows([]);
      setMapping({});
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The CSV could not be read as UTF-8.",
      );
    }
  }

  function requestBody() {
    return {
      entityType,
      fileName,
      contentBase64,
      columnMapping: mapping,
      defaultOwnerUserId: defaultOwner,
      ownerValueMapping: ownerMapping,
      pipelineId: entityType === "opportunity" ? pipelineId : null,
      stageValueMapping: entityType === "opportunity" ? stageMapping : {},
    };
  }

  function mappingComplete(): boolean {
    const targets = Object.values(mapping).filter(
      (value): value is string => value !== null,
    );
    const requiredTargets =
      entityType === "account"
        ? ["name"]
        : entityType === "contact"
          ? ["first_name", "last_name"]
          : ["name", "stage"];
    if (
      !fileName ||
      !defaultOwner ||
      targets.length === 0 ||
      new Set(targets).size !== targets.length ||
      requiredTargets.some((target) => !targets.includes(target)) ||
      ((entityType === "contact" || entityType === "opportunity") &&
        !targets.some((target) =>
          ["account_domain", "account_name"].includes(target),
        ))
    )
      return false;
    if (ownerValues.some((value) => !ownerMapping[value])) return false;
    if (entityType === "opportunity") {
      if (
        !pipelineId ||
        !targets.includes("stage") ||
        stageValues.some((value) => !stageMapping[value])
      )
        return false;
    }
    return true;
  }

  async function previewImport() {
    setWorking(true);
    setMessage(null);
    try {
      const next = await apiRequest<CRMImportPreview>(
        "/api/v1/crm/imports/preview",
        {
          method: "POST",
          body: JSON.stringify(requestBody()),
        },
      );
      setPreview(next);
      setConfirmed(false);
      setMessage("Preview complete. RevenueOS has not changed CRM records.");
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The CSV could not be previewed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function confirmImport() {
    if (!preview || !confirmed) return;
    setWorking(true);
    setMessage(null);
    try {
      const result = await apiRequest<CRMImportPreview>(
        "/api/v1/crm/imports/confirm",
        {
          method: "POST",
          body: JSON.stringify({ ...requestBody(), batchId: preview.batchId }),
        },
      );
      setPreview(result);
      setConfirmed(false);
      setContentBase64("");
      setCsvRows([]);
      setMessage(
        `${result.importedRowCount} ${humanise(entityType)} record${result.importedRowCount === 1 ? "" : "s"} imported.`,
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The CRM import could not be confirmed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function downloadTemplate() {
    setWorking(true);
    setMessage(null);
    try {
      const blob = await apiBlob(
        `/api/v1/crm/imports/template?entityType=${entityType}`,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `revenueos-${entityType}-import-template.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The CSV template could not be downloaded.",
      );
    } finally {
      setWorking(false);
    }
  }

  if (
    !availability?.canManage ||
    !availability.enabled ||
    availability.mode !== "native"
  )
    return null;

  const counts = preview ? dispositionCounts(preview) : null;
  return (
    <section className="form-card" aria-labelledby="crm-import-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Supervised onboarding
      </p>
      <h2 id="crm-import-title" className="form-legend mt-2">
        Import CRM data
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Import Accounts, Contacts or open Opportunities from a UTF-8 CSV.
        Preview is read-only; RevenueOS never infers permission to contact and
        does not retain the raw CSV.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-700">
          Record type
          <select
            className="form-input mt-2"
            value={entityType}
            onChange={(event) =>
              changeEntity(event.target.value as CRMEntityType)
            }
            disabled={working}
          >
            <option value="account">Accounts</option>
            <option value="contact">Contacts</option>
            <option value="opportunity">Open Opportunities</option>
          </select>
        </label>
        <div className="flex items-end">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void downloadTemplate()}
            disabled={working}
          >
            Download CSV template
          </button>
        </div>
        <label className="text-sm font-semibold text-slate-700 sm:col-span-2">
          UTF-8 CSV · maximum 5 MB and 5,000 rows
          <input
            className="form-input mt-2"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => void chooseFile(event)}
            disabled={working}
          />
        </label>
      </div>

      {headers.length ? (
        <div className="mt-6 border-t border-slate-200 pt-6">
          <h3 className="font-semibold text-slate-950">Column mapping</h3>
          <p className="mt-1 text-sm text-slate-600">
            Each column must be mapped once or explicitly ignored.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {headers.map((header) => (
              <label
                key={header}
                className="text-sm font-semibold text-slate-700"
              >
                {header}
                <select
                  className="form-input mt-2"
                  value={mapping[header] ?? ""}
                  onChange={(event) => {
                    setMapping((current) => ({
                      ...current,
                      [header]: event.target.value || null,
                    }));
                    resetPreview();
                  }}
                >
                  <option value="">Ignore this column</option>
                  {availableTargets.map((target) => (
                    <option key={target.value} value={target.value}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>

          <label className="mt-4 block text-sm font-semibold text-slate-700">
            Default owner
            <select
              className="form-input mt-2"
              value={defaultOwner}
              onChange={(event) => {
                setDefaultOwner(event.target.value);
                resetPreview();
              }}
            >
              {members.map((member) => (
                <option key={member.userId} value={member.userId}>
                  {member.displayName}
                </option>
              ))}
            </select>
          </label>

          {ownerValues.length ? (
            <MappingSelectors
              title="Owner values"
              values={ownerValues}
              mapping={ownerMapping}
              options={members.map((member) => ({
                value: member.userId,
                label: member.displayName,
              }))}
              onChange={(value, target) => {
                setOwnerMapping((current) => ({ ...current, [value]: target }));
                resetPreview();
              }}
            />
          ) : null}

          {entityType === "opportunity" ? (
            <div className="mt-5 rounded-2xl border border-slate-200 p-4">
              <label className="text-sm font-semibold text-slate-700">
                Destination pipeline
                <select
                  className="form-input mt-2"
                  value={pipelineId}
                  onChange={(event) => {
                    setPipelineId(event.target.value);
                    setStageMapping({});
                    resetPreview();
                  }}
                >
                  {pipelines.map((pipeline) => (
                    <option key={pipeline.id} value={pipeline.id}>
                      {pipeline.name}
                    </option>
                  ))}
                </select>
              </label>
              {stageValues.length ? (
                <MappingSelectors
                  title="Open stage values"
                  values={stageValues}
                  mapping={stageMapping}
                  options={(selectedPipeline?.stages ?? [])
                    .filter(
                      (stage) => stage.active && stage.stageType === "open",
                    )
                    .map((stage) => ({ value: stage.id, label: stage.name }))}
                  onChange={(value, target) => {
                    setStageMapping((current) => ({
                      ...current,
                      [value]: target,
                    }));
                    resetPreview();
                  }}
                />
              ) : null}
            </div>
          ) : null}

          <button
            type="button"
            className="primary-button mt-5"
            disabled={working || !mappingComplete()}
            onClick={() => void previewImport()}
          >
            {working ? "Checking…" : "Preview import"}
          </button>
        </div>
      ) : null}

      {preview ? (
        <div className="mt-6 rounded-2xl border border-teal-200 bg-teal-50 p-5">
          <h3 className="font-semibold text-teal-950">Import preview</h3>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
            <Metric label="Rows checked" value={preview.rowCount} />
            <Metric
              label={
                preview.state === "confirmed"
                  ? "Imported records"
                  : "New records"
              }
              value={
                preview.state === "confirmed"
                  ? preview.importedRowCount
                  : (counts?.new ?? 0)
              }
            />
            <Metric
              label="Existing matches"
              value={counts?.matches_existing ?? 0}
            />
            <Metric
              label="Possible duplicates"
              value={counts?.possible_duplicate ?? 0}
            />
            <Metric label="Invalid rows" value={counts?.invalid ?? 0} />
            <Metric
              label={preview.state === "confirmed" ? "Imported" : "Will import"}
              value={
                preview.state === "confirmed"
                  ? preview.importedRowCount
                  : preview.actionableRowCount
              }
            />
          </dl>
          <p className="mt-4 text-sm text-teal-950">
            Possible duplicates and invalid rows are skipped. Permission to
            contact is never inferred.
          </p>
          {preview.state === "previewed" ? (
            <>
              <label className="mt-4 flex items-start gap-3 text-sm font-semibold text-teal-950">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-teal-700"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                Import only the {preview.actionableRowCount} rows marked new. I
                have reviewed the skipped matches and duplicates.
              </label>
              <button
                type="button"
                className="primary-button mt-4"
                disabled={working || !confirmed}
                onClick={() => void confirmImport()}
              >
                {working
                  ? "Importing…"
                  : `Import ${preview.actionableRowCount} new records`}
              </button>
            </>
          ) : (
            <p className="mt-4 font-semibold text-teal-950">
              Import confirmed · {preview.importedRowCount} records created.
            </p>
          )}
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

function MappingSelectors({
  title,
  values,
  mapping,
  options,
  onChange,
}: {
  title: string;
  values: string[];
  mapping: ValueMapping;
  options: { value: string; label: string }[];
  onChange: (value: string, target: string) => void;
}) {
  return (
    <fieldset className="mt-5">
      <legend className="text-sm font-semibold text-slate-800">{title}</legend>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {values.map((value) => (
          <label key={value} className="text-sm text-slate-700">
            {value}
            <select
              className="form-input mt-2"
              value={mapping[value] ?? ""}
              onChange={(event) => onChange(value, event.target.value)}
            >
              <option value="">Choose a mapping</option>
              {options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="font-semibold text-teal-800">{label}</dt>
      <dd className="mt-1 text-xl font-bold text-teal-950">{value}</dd>
    </div>
  );
}

function mappedValues(
  rows: string[][],
  mapping: ColumnMapping,
  target: string,
): string[] {
  const headerIndex =
    rows[0]?.findIndex((header) => mapping[header] === target) ?? -1;
  if (headerIndex < 0) return [];
  return [
    ...new Set(
      rows
        .slice(1)
        .map((row) => row[headerIndex]?.trim() ?? "")
        .filter(Boolean),
    ),
  ].sort();
}

function dispositionCounts(preview: CRMImportPreview): Record<string, number> {
  return preview.rows.reduce<Record<string, number>>((counts, row) => {
    counts[row.disposition] = (counts[row.disposition] ?? 0) + 1;
    return counts;
  }, {});
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 32_768;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }
  return window.btoa(binary);
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') quoted = false;
      else cell += character;
    } else if (character === '"' && cell === "") quoted = true;
    else if (character === ",") {
      row.push(cell);
      cell = "";
    } else if (character === "\n" || character === "\r") {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else cell += character;
  }
  if (quoted) throw new Error("The CSV contains an unclosed quoted field.");
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  return rows;
}
