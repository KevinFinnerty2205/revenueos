"use client";

import type {
  ConnectionListResponse,
  ConnectorDefinition,
  ConnectorKey,
  CRMFieldConfiguration,
  CRMFieldMapping,
  CRMStageConfiguration,
  IntegrationCatalogResponse,
  OAuthStartResponse,
  OrganisationConnection,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const OPPORTUNITY_FIELDS = [
  "stage",
  "status",
  "expected_close_date",
  "estimated_value",
  "next_step",
  "description",
] as const;
const CONTACT_FIELDS = [
  "first_name",
  "last_name",
  "email",
  "job_title",
] as const;
const REVENUEOS_STAGES = [
  "qualification",
  "discovery",
  "evaluation",
  "proposal",
  "negotiation",
  "procurement",
  "closed_won",
  "closed_lost",
  "other",
] as const;

export function IntegrationSettings() {
  const [catalog, setCatalog] = useState<ConnectorDefinition[]>([]);
  const [connections, setConnections] = useState<OrganisationConnection[]>([]);
  const [busy, setBusy] = useState<ConnectorKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(signal?: AbortSignal) {
    const [definitions, connectionList] = await Promise.all([
      apiRequest<IntegrationCatalogResponse>("/api/v1/integrations", {
        signal,
      }),
      apiRequest<ConnectionListResponse>("/api/v1/integrations/connections", {
        signal,
      }),
    ]);
    setCatalog(definitions.connectors);
    setConnections(connectionList.items);
  }

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<IntegrationCatalogResponse>("/api/v1/integrations", {
        signal: controller.signal,
      }),
      apiRequest<ConnectionListResponse>("/api/v1/integrations/connections", {
        signal: controller.signal,
      }),
    ])
      .then(([definitions, connectionList]) => {
        setCatalog(definitions.connectors);
        setConnections(connectionList.items);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Integrations could not be loaded.",
        );
      });
    return () => controller.abort();
  }, []);

  async function connect(definition: ConnectorDefinition) {
    setBusy(definition.connectorKey);
    setError(null);
    setMessage(null);
    try {
      if (definition.connectorKey === "hubspot") {
        const result = await apiRequest<OAuthStartResponse>(
          "/api/v1/integrations/hubspot/oauth/start",
          { method: "POST" },
        );
        window.location.assign(result.authorisationUrl);
        return;
      }
      await apiRequest<OrganisationConnection>(
        "/api/v1/integrations/connections",
        {
          method: "POST",
          body: JSON.stringify({ connectorKey: definition.connectorKey }),
        },
      );
      await load();
      setMessage(
        "Simulation connector enabled. It cannot contact an external system.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The connector could not be enabled.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function testConnection(connection: OrganisationConnection) {
    setBusy(connection.connectorKey);
    setError(null);
    setMessage(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/test`,
        { method: "POST" },
      );
      await load();
      setMessage(
        connection.simulationOnly
          ? "Simulation connection verified. No external request was made."
          : "HubSpot authorisation and account identity were verified.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The connection could not be tested.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function revoke(connection: OrganisationConnection) {
    setBusy(connection.connectorKey);
    setError(null);
    setMessage(null);
    try {
      await apiRequest(`/api/v1/integrations/connections/${connection.id}`, {
        method: "DELETE",
      });
      await load();
      setMessage(
        connection.simulationOnly
          ? "Simulation connector disconnected. Pending previews and queued simulations were invalidated."
          : "HubSpot disconnected. Provider revocation was attempted, local credentials were deleted, and pending work was cancelled.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The connection could not be disconnected.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="form-card" aria-labelledby="integrations-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Reviewed execution boundary
      </p>
      <h2 id="integrations-title" className="mt-2 text-xl font-semibold">
        Integrations
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        HubSpot can apply only the field update or interaction summary that a
        user reviews and confirms. RevenueOS never sends a raw transcript and
        does not run autonomous CRM writes. Development mock connectors remain
        clearly labelled simulations.
      </p>

      {catalog.length ? (
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          {catalog.map((definition) => {
            const connection = connections.find(
              (item) => item.connectorKey === definition.connectorKey,
            );
            const active = connection?.connectionStatus === "active";
            const needsAuth =
              connection?.connectionStatus === "reauthorisation_required";
            return (
              <li
                key={definition.connectorKey}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-slate-950">
                      {definition.displayName}
                    </h3>
                    <p
                      className={`mt-1 text-xs font-bold uppercase tracking-wide ${definition.simulationOnly ? "text-amber-800" : "text-teal-800"}`}
                    >
                      {definition.simulationOnly
                        ? "Simulation — no external action"
                        : "Live — explicit review required"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                    {active
                      ? "Connected"
                      : needsAuth
                        ? "Reconnect required"
                        : "Not connected"}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-600">
                  Capabilities:{" "}
                  {definition.supportedCapabilities.map(humanise).join(", ")}
                </p>
                {connection?.externalAccountName ? (
                  <p className="mt-2 text-sm text-slate-600">
                    Account: {connection.externalAccountName} (
                    {connection.externalAccountId})
                  </p>
                ) : null}
                {connection?.lastVerifiedAt ? (
                  <p className="mt-2 text-xs text-slate-500">
                    Last verified{" "}
                    {new Date(connection.lastVerifiedAt).toLocaleString(
                      "en-AU",
                    )}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  {active && connection ? (
                    <>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy === definition.connectorKey}
                        onClick={() => void testConnection(connection)}
                      >
                        Test connection
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy === definition.connectorKey}
                        onClick={() => void revoke(connection)}
                      >
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="primary-button"
                      disabled={
                        !definition.available ||
                        busy === definition.connectorKey
                      }
                      onClick={() => void connect(definition)}
                    >
                      {needsAuth
                        ? "Reconnect"
                        : definition.simulationOnly
                          ? "Connect simulation"
                          : "Connect HubSpot"}
                    </button>
                  )}
                </div>
                {active && connection?.connectorKey === "hubspot" ? (
                  <HubSpotMappingSettings
                    connection={connection}
                    onError={setError}
                    onMessage={setMessage}
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : error ? null : (
        <p role="status" className="mt-4 text-sm text-slate-600">
          Loading integrations…
        </p>
      )}
      {message ? (
        <p role="status" className="mt-4 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function HubSpotMappingSettings({
  connection,
  onError,
  onMessage,
}: {
  connection: OrganisationConnection;
  onError: (value: string | null) => void;
  onMessage: (value: string | null) => void;
}) {
  const [opportunity, setOpportunity] = useState<CRMFieldConfiguration | null>(
    null,
  );
  const [contact, setContact] = useState<CRMFieldConfiguration | null>(null);
  const [stages, setStages] = useState<CRMStageConfiguration | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadMappings() {
    setLoading(true);
    onError(null);
    try {
      const [opportunityResult, contactResult, stageResult] = await Promise.all(
        [
          apiRequest<CRMFieldConfiguration>(
            `/api/v1/integrations/connections/${connection.id}/crm/fields/opportunity`,
          ),
          apiRequest<CRMFieldConfiguration>(
            `/api/v1/integrations/connections/${connection.id}/crm/fields/contact`,
          ),
          apiRequest<CRMStageConfiguration>(
            `/api/v1/integrations/connections/${connection.id}/crm/stages`,
          ),
        ],
      );
      setOpportunity(opportunityResult);
      setContact(contactResult);
      setStages(stageResult);
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "HubSpot mapping settings could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function saveField(
    entityType: "opportunity" | "contact",
    revenueosField: string,
    propertyName: string,
    authority: "review_before_sync" | "crm_authoritative",
  ) {
    onError(null);
    try {
      await apiRequest<CRMFieldMapping>(
        `/api/v1/integrations/connections/${connection.id}/crm/fields`,
        {
          method: "PUT",
          body: JSON.stringify({
            entityType,
            revenueosField,
            externalPropertyName: propertyName,
            authority,
          }),
        },
      );
      await loadMappings();
      onMessage("HubSpot field authority and mapping saved.");
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The field mapping could not be saved.",
      );
    }
  }

  async function saveStage(revenueosStage: string, value: string) {
    const [externalPipelineId, externalStageId] = value.split("::");
    if (!externalPipelineId || !externalStageId) return;
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/stages`,
        {
          method: "PUT",
          body: JSON.stringify({
            revenueosStage,
            externalPipelineId,
            externalStageId,
          }),
        },
      );
      await loadMappings();
      onMessage("HubSpot stage mapping saved.");
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The stage mapping could not be saved.",
      );
    }
  }

  return (
    <details className="mt-4 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer text-sm font-bold text-slate-800">
        Advanced mapping settings
      </summary>
      {!opportunity || !contact || !stages ? (
        <button
          type="button"
          className="secondary-button mt-3"
          disabled={loading}
          onClick={() => void loadMappings()}
        >
          {loading
            ? "Loading HubSpot fields…"
            : "Load HubSpot fields and stages"}
        </button>
      ) : (
        <div className="mt-4 space-y-5">
          <p className="text-xs leading-5 text-slate-600">
            Mapping is explicit. “Review before update” requires a fresh CRM
            read and final confirmation. “CRM is source of truth” blocks
            RevenueOS writes for that field.
          </p>
          <FieldMappingGroup
            title="Opportunity fields"
            entityType="opportunity"
            fields={OPPORTUNITY_FIELDS}
            configuration={opportunity}
            onSave={saveField}
          />
          <FieldMappingGroup
            title="Contact fields"
            entityType="contact"
            fields={CONTACT_FIELDS}
            configuration={contact}
            onSave={saveField}
          />
          <fieldset>
            <legend className="text-sm font-bold text-slate-900">
              Deal stages
            </legend>
            <div className="mt-2 grid gap-2">
              {REVENUEOS_STAGES.map((stage) => {
                const current = stages.mappings.find(
                  (item) => item.revenueosStage === stage,
                );
                return (
                  <label
                    key={stage}
                    className="grid gap-1 text-xs font-bold text-slate-700"
                  >
                    {humanise(stage)}
                    <select
                      className="text-input"
                      value={
                        current
                          ? `${current.externalPipelineId}::${current.externalStageId}`
                          : ""
                      }
                      onChange={(event) =>
                        void saveStage(stage, event.target.value)
                      }
                    >
                      <option value="">Not mapped</option>
                      {stages.availableStages.map((item) => (
                        <option
                          key={`${item.pipelineId}:${item.stageId}`}
                          value={`${item.pipelineId}::${item.stageId}`}
                        >
                          {item.pipelineLabel} — {item.stageLabel}
                        </option>
                      ))}
                    </select>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </div>
      )}
    </details>
  );
}

function FieldMappingGroup({
  title,
  entityType,
  fields,
  configuration,
  onSave,
}: {
  title: string;
  entityType: "opportunity" | "contact";
  fields: readonly string[];
  configuration: CRMFieldConfiguration;
  onSave: (
    entityType: "opportunity" | "contact",
    revenueosField: string,
    propertyName: string,
    authority: "review_before_sync" | "crm_authoritative",
  ) => Promise<void>;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-bold text-slate-900">{title}</legend>
      <div className="mt-2 grid gap-3">
        {fields.map((field) => {
          const current = configuration.mappings.find(
            (item) => item.revenueosField === field,
          );
          return (
            <div key={field} className="grid gap-2 sm:grid-cols-2">
              <label className="grid gap-1 text-xs font-bold text-slate-700">
                {humanise(field)}
                <select
                  className="text-input"
                  value={current?.externalPropertyName ?? ""}
                  onChange={(event) => {
                    if (event.target.value)
                      void onSave(
                        entityType,
                        field,
                        event.target.value,
                        "review_before_sync",
                      );
                  }}
                >
                  <option value="">Not mapped</option>
                  {configuration.properties
                    .filter((item) => !item.readOnly)
                    .map((item) => (
                      <option
                        key={item.externalPropertyName}
                        value={item.externalPropertyName}
                      >
                        {item.label} ({item.propertyType})
                      </option>
                    ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-bold text-slate-700">
                Field authority
                <select
                  className="text-input"
                  disabled={!current}
                  value={
                    current?.authority === "crm_authoritative"
                      ? "crm_authoritative"
                      : "review_before_sync"
                  }
                  onChange={(event) => {
                    if (current)
                      void onSave(
                        entityType,
                        field,
                        current.externalPropertyName,
                        event.target.value as
                          "review_before_sync" | "crm_authoritative",
                      );
                  }}
                >
                  <option value="review_before_sync">
                    Review before update
                  </option>
                  <option value="crm_authoritative">
                    CRM is source of truth
                  </option>
                </select>
              </label>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
