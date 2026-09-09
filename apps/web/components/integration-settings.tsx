"use client";

import type {
  ConnectionListResponse,
  ConnectorDefinition,
  ConnectorKey,
  CRMConflictList,
  CRMConnectionStatus,
  CRMFieldConfiguration,
  CRMFieldMapping,
  CRMMember,
  CRMOwnerMappingList,
  CRMStageConfiguration,
  IntegrationCatalogResponse,
  ProviderSyncResponse,
  ProviderSyncStatus,
  OAuthStartResponse,
  OrganisationConnection,
} from "@revenueos/shared";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const OPPORTUNITY_FIELDS = [
  "name",
  "stage",
  "expected_close_date",
  "estimated_value",
  "currency",
  "description",
] as const;
const ACCOUNT_FIELDS = ["name", "domain", "industry"] as const;
const CONTACT_FIELDS = [
  "first_name",
  "last_name",
  "email",
  "phone",
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
  const [mailboxConsent, setMailboxConsent] = useState<ConnectorKey | null>(
    null,
  );
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<
    Record<string, ProviderSyncStatus>
  >({});
  const mailboxTriggerRef = useRef<HTMLButtonElement>(null);
  const disconnectTriggerRef = useRef<HTMLButtonElement>(null);
  const mailboxDialogTitleRef = useRef<HTMLParagraphElement>(null);
  const disconnectDialogTitleRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!mailboxConsent) return;
    window.requestAnimationFrame(() => mailboxDialogTitleRef.current?.focus());
  }, [mailboxConsent]);

  useEffect(() => {
    if (!disconnecting) return;
    window.requestAnimationFrame(() =>
      disconnectDialogTitleRef.current?.focus(),
    );
  }, [disconnecting]);

  function closeMailboxConsent() {
    setMailboxConsent(null);
    window.requestAnimationFrame(() => mailboxTriggerRef.current?.focus());
  }

  function openMailboxConsent(
    connectorKey: ConnectorKey,
    trigger?: HTMLButtonElement,
  ) {
    mailboxTriggerRef.current =
      trigger ??
      (document.activeElement instanceof HTMLButtonElement
        ? document.activeElement
        : null);
    setMailboxConsent(connectorKey);
  }

  function closeDisconnectConfirmation() {
    setDisconnecting(null);
    window.requestAnimationFrame(() => disconnectTriggerRef.current?.focus());
  }

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

  useEffect(() => {
    const mailboxConnections = connections.filter(
      (item) =>
        (item.connectorKey === "microsoft_365" ||
          item.connectorKey === "google_workspace") &&
        item.connectionStatus !== "revoked",
    );
    if (!mailboxConnections.length) return;
    const controller = new AbortController();
    Promise.all(
      mailboxConnections.map(async (connection) => {
        const provider =
          connection.connectorKey === "google_workspace"
            ? "google"
            : "microsoft";
        return apiRequest<ProviderSyncStatus>(
          `/api/v1/integrations/${provider}/connections/${connection.id}/sync-status`,
          { signal: controller.signal },
        );
      }),
    )
      .then((items) =>
        setSyncStatus(
          Object.fromEntries(items.map((item) => [item.connectionId, item])),
        ),
      )
      .catch(() => setSyncStatus({}));
    return () => controller.abort();
  }, [connections]);

  async function connect(
    definition: ConnectorDefinition,
    mailboxConsentConfirmed = false,
    trigger?: HTMLButtonElement,
  ) {
    if (
      (definition.connectorKey === "microsoft_365" ||
        definition.connectorKey === "google_workspace") &&
      !mailboxConsentConfirmed
    ) {
      openMailboxConsent(definition.connectorKey, trigger);
      setError(null);
      setMessage(null);
      return;
    }
    setBusy(definition.connectorKey);
    setError(null);
    setMessage(null);
    try {
      if (
        definition.connectorKey === "hubspot" ||
        definition.connectorKey === "salesforce" ||
        definition.connectorKey === "microsoft_365" ||
        definition.connectorKey === "google_workspace"
      ) {
        const provider =
          definition.connectorKey === "google_workspace"
            ? "google"
            : definition.connectorKey === "microsoft_365"
              ? "microsoft"
              : definition.connectorKey;
        const result = await apiRequest<OAuthStartResponse>(
          `/api/v1/integrations/${provider}/oauth/start`,
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
      setDisconnecting(null);
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
          : connection.connectorKey === "microsoft_365" ||
              connection.connectorKey === "google_workspace"
            ? `${connection.displayName} mailbox and calendar authorisation were verified.`
            : `${connection.displayName} authorisation and account identity were verified.`,
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
          : connection.connectorKey === "microsoft_365" ||
              connection.connectorKey === "google_workspace"
            ? `${connection.displayName} disconnected. Future email sending and calendar synchronisation have stopped; bounded historical Oryntela records remain under retention policy.`
            : `${connection.displayName} disconnected. Provider revocation was attempted, local credentials were deleted, and pending work was cancelled.`,
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

  async function syncMailbox(connection: OrganisationConnection) {
    setBusy(connection.connectorKey);
    setError(null);
    setMessage(null);
    try {
      const provider =
        connection.connectorKey === "google_workspace" ? "google" : "microsoft";
      const result = await apiRequest<ProviderSyncResponse>(
        `/api/v1/integrations/${provider}/connections/${connection.id}/sync`,
        { method: "POST" },
      );
      setSyncStatus((current) => ({
        ...current,
        [connection.id]: {
          connectionId: connection.id,
          lastSuccessfulSyncAt: result.syncedAt,
          lastErrorCategory: result.resources.some(
            (resource) => resource.state === "degraded",
          )
            ? `${provider}_sync_degraded`
            : null,
          state: result.resources.some(
            (resource) => resource.state === "degraded",
          )
            ? "degraded"
            : "healthy",
        },
      }));
      setMessage(
        result.resources.some((resource) => resource.state === "degraded")
          ? `${connection.displayName} synchronisation is delayed. Existing Oryntela records remain available.`
          : `${connection.displayName} email and calendar changes were synchronised.`,
      );
      await load();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : `${connection.displayName} could not be synchronised.`,
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="form-card" aria-labelledby="integrations-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        Reviewed execution boundary
      </p>
      <h2 id="integrations-title" className="mt-2 text-xl font-semibold">
        Integrations
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Connect the work systems you choose. Oryntela sends customer email only
        after the required review and approval, keeps mailbox access bounded to
        Oryntela-managed conversations, and never sends a raw transcript.
      </p>

      {catalog.length ? (
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          {catalog.map((definition) => {
            const matchingConnections = connections.filter(
              (item) => item.connectorKey === definition.connectorKey,
            );
            const connection =
              matchingConnections.find(
                (item) => item.connectionStatus !== "revoked",
              ) ?? matchingConnections.at(-1);
            const active = connection?.connectionStatus === "active";
            const needsAuth =
              connection?.connectionStatus === "reauthorisation_required";
            const mailbox =
              definition.connectorKey === "microsoft_365" ||
              definition.connectorKey === "google_workspace";
            const currentSyncStatus = connection
              ? (syncStatus[connection.id] ?? null)
              : null;
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
                      className={`mt-1 text-xs font-bold uppercase tracking-wide ${definition.simulationOnly ? "text-amber-800" : "text-brand-secondary"}`}
                    >
                      {definition.simulationOnly
                        ? "Simulation — no external action"
                        : "Live — explicit review required"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                    {!definition.available
                      ? "Setup required"
                      : active
                        ? "Connected"
                        : needsAuth
                          ? "Reconnect required"
                          : "Not connected"}
                  </span>
                </div>
                {mailbox ? (
                  <p className="mt-3 text-sm leading-6 text-slate-600">
                    Connect your {definition.displayName} work account to use
                    email and calendar with Oryntela.
                  </p>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">
                    Capabilities:{" "}
                    {definition.supportedCapabilities.map(humanise).join(", ")}
                  </p>
                )}
                {connection &&
                (connection.connectorKey === "microsoft_365" ||
                  connection.connectorKey === "google_workspace") &&
                connection.externalAccountEmail ? (
                  <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
                    <p>
                      Connected as:{" "}
                      <strong className="break-all">
                        {connection.externalAccountEmail}
                      </strong>
                    </p>
                    <p className="mt-2">
                      Email: {needsAuth ? "Reconnect required" : "Connected"}
                    </p>
                    <p>
                      Replies: {needsAuth ? "Reconnect required" : "Connected"}
                    </p>
                    <p>
                      Calendar: {needsAuth ? "Reconnect required" : "Connected"}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      Last sync:{" "}
                      {currentSyncStatus?.lastSuccessfulSyncAt
                        ? new Date(
                            currentSyncStatus.lastSuccessfulSyncAt,
                          ).toLocaleString("en-AU")
                        : "Not yet synchronised"}
                      {currentSyncStatus?.state === "degraded"
                        ? " · Delayed"
                        : ""}
                    </p>
                  </div>
                ) : connection?.externalAccountName ? (
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
                      {mailbox ? (
                        <>
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={busy === definition.connectorKey}
                            onClick={() => void syncMailbox(connection)}
                          >
                            Sync now
                          </button>
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={busy === definition.connectorKey}
                            onClick={(event) =>
                              openMailboxConsent(
                                definition.connectorKey,
                                event.currentTarget,
                              )
                            }
                          >
                            Reconnect
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={busy === definition.connectorKey}
                          onClick={() => void testConnection(connection)}
                        >
                          Test connection
                        </button>
                      )}
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busy === definition.connectorKey}
                        onClick={(event) => {
                          disconnectTriggerRef.current = event.currentTarget;
                          setDisconnecting(connection.id);
                        }}
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
                      onClick={(event) =>
                        void connect(definition, false, event.currentTarget)
                      }
                    >
                      {!definition.available
                        ? "Setup required"
                        : needsAuth
                          ? "Reconnect"
                          : definition.simulationOnly
                            ? "Connect simulation"
                            : mailbox
                              ? `Connect ${definition.displayName}`
                              : `Connect ${definition.displayName}`}
                    </button>
                  )}
                </div>
                {mailbox && mailboxConsent === definition.connectorKey ? (
                  <div
                    className="mt-4 rounded-xl border border-brand-secondary/25 bg-brand-secondary/10 p-4"
                    role="dialog"
                    aria-labelledby={`${definition.connectorKey}-permissions-title`}
                  >
                    <p
                      ref={mailboxDialogTitleRef}
                      id={`${definition.connectorKey}-permissions-title`}
                      tabIndex={-1}
                      className="font-bold text-slate-950"
                    >
                      Before you continue
                    </p>
                    <dl className="mt-3 space-y-3 text-sm text-slate-700">
                      <div>
                        <dt className="font-bold">Email</dt>
                        <dd>
                          Send emails you have reviewed and approved through
                          your connected work mailbox.
                        </dd>
                      </div>
                      <div>
                        <dt className="font-bold">Replies</dt>
                        <dd>
                          {definition.connectorKey === "microsoft_365"
                            ? "Microsoft grants mail read access because its narrower metadata permission cannot provide reply content."
                            : "Google grants restricted Gmail read-only access because Gmail does not offer a narrower scope that can provide strongly correlated reply content."}{" "}
                          Oryntela scans a bounded window of Inbox and Sent
                          message metadata to identify emails tied to Oryntela
                          sends, then reads the subject and body only for one
                          strongly matched reply. Unrelated mail content is not
                          read or stored.
                        </dd>
                      </div>
                      <div>
                        <dt className="font-bold">Calendar</dt>
                        <dd>
                          Read event details from your primary work calendar so
                          Oryntela can help you prepare for customer meetings.
                          Event bodies and attachments are not requested.
                        </dd>
                      </div>
                    </dl>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="primary-button"
                        disabled={busy === definition.connectorKey}
                        onClick={() => {
                          setMailboxConsent(null);
                          void connect(definition, true);
                        }}
                      >
                        Continue to {definition.displayName}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={closeMailboxConsent}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
                {connection && disconnecting === connection.id ? (
                  <div
                    className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4"
                    role="dialog"
                    aria-labelledby={`disconnect-${connection.id}-title`}
                  >
                    <p
                      ref={disconnectDialogTitleRef}
                      id={`disconnect-${connection.id}-title`}
                      tabIndex={-1}
                      className="font-bold text-slate-950"
                    >
                      Disconnect {definition.displayName}?
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {mailbox
                        ? `Disconnecting ${definition.displayName} will stop future Oryntela email sending and calendar synchronisation for this account. Historical Oryntela records will remain according to retention policy.`
                        : "Disconnecting will cancel pending provider work and invalidate existing previews."}
                    </p>
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        className="primary-button"
                        disabled={busy === definition.connectorKey}
                        onClick={() => void revoke(connection)}
                      >
                        Confirm disconnect
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={closeDisconnectConfirmation}
                      >
                        Keep connected
                      </button>
                    </div>
                  </div>
                ) : null}
                {active &&
                connection &&
                (connection.connectorKey === "hubspot" ||
                  connection.connectorKey === "salesforce") ? (
                  <CRMMappingSettings
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

function CRMMappingSettings({
  connection,
  onError,
  onMessage,
}: {
  connection: OrganisationConnection;
  onError: (value: string | null) => void;
  onMessage: (value: string | null) => void;
}) {
  const providerName = connection.displayName;
  const [account, setAccount] = useState<CRMFieldConfiguration | null>(null);
  const [opportunity, setOpportunity] = useState<CRMFieldConfiguration | null>(
    null,
  );
  const [contact, setContact] = useState<CRMFieldConfiguration | null>(null);
  const [stages, setStages] = useState<CRMStageConfiguration | null>(null);
  const [status, setStatus] = useState<CRMConnectionStatus | null>(null);
  const [owners, setOwners] = useState<CRMOwnerMappingList | null>(null);
  const [members, setMembers] = useState<CRMMember[]>([]);
  const [conflicts, setConflicts] = useState<CRMConflictList | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadMappings() {
    setLoading(true);
    onError(null);
    try {
      const [
        accountResult,
        opportunityResult,
        contactResult,
        stageResult,
        statusResult,
        ownerResult,
        memberResult,
        conflictResult,
      ] = await Promise.all([
        apiRequest<CRMFieldConfiguration>(
          `/api/v1/integrations/connections/${connection.id}/crm/fields/company`,
        ),
        apiRequest<CRMFieldConfiguration>(
          `/api/v1/integrations/connections/${connection.id}/crm/fields/opportunity`,
        ),
        apiRequest<CRMFieldConfiguration>(
          `/api/v1/integrations/connections/${connection.id}/crm/fields/contact`,
        ),
        apiRequest<CRMStageConfiguration>(
          `/api/v1/integrations/connections/${connection.id}/crm/stages`,
        ),
        apiRequest<CRMConnectionStatus>(
          `/api/v1/integrations/connections/${connection.id}/crm/status`,
        ),
        apiRequest<CRMOwnerMappingList>(
          `/api/v1/integrations/connections/${connection.id}/crm/owners`,
        ),
        apiRequest<CRMMember[]>("/api/v1/crm/members"),
        apiRequest<CRMConflictList>(
          `/api/v1/integrations/connections/${connection.id}/crm/conflicts`,
        ),
      ]);
      setAccount(accountResult);
      setOpportunity(opportunityResult);
      setContact(contactResult);
      setStages(stageResult);
      setStatus(statusResult);
      setOwners(ownerResult);
      setMembers(memberResult);
      setConflicts(conflictResult);
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : `${providerName} mapping settings could not be loaded.`,
      );
    } finally {
      setLoading(false);
    }
  }

  async function saveField(
    entityType: "company" | "opportunity" | "contact",
    revenueosField: string,
    propertyName: string,
    authority:
      "review_before_sync" | "crm_authoritative" | "revenueos_authoritative",
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
      onMessage(`${providerName} field authority and mapping saved.`);
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
      onMessage(`${providerName} stage mapping saved.`);
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The stage mapping could not be saved.",
      );
    }
  }

  async function enqueueSync(mode: "incremental" | "reconcile") {
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/sync`,
        {
          method: "POST",
          body: JSON.stringify({
            mode,
            idempotencyKey: crypto.randomUUID(),
          }),
        },
      );
      await loadMappings();
      onMessage(`${providerName} synchronisation was queued.`);
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : `${providerName} synchronisation could not be queued.`,
      );
    }
  }

  async function setOwner(externalOwnerId: string, userId: string) {
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/owners`,
        {
          method: "PUT",
          body: JSON.stringify({
            externalOwnerId,
            userId: userId || null,
          }),
        },
      );
      await loadMappings();
      onMessage(`${providerName} owner mapping saved. Writeback remains off.`);
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The owner mapping could not be saved.",
      );
    }
  }

  async function reviewMappings() {
    if (!status) return;
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/mappings/review`,
        {
          method: "POST",
          body: JSON.stringify({
            mappingVersion: status.mappingVersion,
            confirmed: true,
          }),
        },
      );
      await loadMappings();
      onMessage("Mappings approved. CRM writeback is still off.");
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The mapping review could not be saved.",
      );
    }
  }

  async function setWriteback(enabled: boolean) {
    if (!status) return;
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/writeback`,
        {
          method: "PUT",
          body: JSON.stringify({
            mappingVersion: status.mappingVersion,
            enabled,
            confirmed: true,
          }),
        },
      );
      await loadMappings();
      onMessage(
        enabled
          ? "Reviewed CRM writeback enabled. Every write still requires a preview and confirmation."
          : "CRM writeback disabled immediately.",
      );
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "CRM writeback could not be changed.",
      );
    }
  }

  async function setConnectorEnabled(enabled: boolean) {
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/enabled`,
        {
          method: "PUT",
          body: JSON.stringify({ enabled, confirmed: true }),
        },
      );
      await loadMappings();
      onMessage(
        enabled
          ? `${providerName} sync enabled in read-only mapping mode.`
          : `${providerName} sync and writeback stopped immediately.`,
      );
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The CRM connector kill switch could not be changed.",
      );
    }
  }

  async function resolveConflict(
    conflictId: string,
    resolution: "provider" | "oryntela",
  ) {
    onError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/crm/conflicts/${conflictId}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({
            resolution,
            confirmed: true,
          }),
        },
      );
      await loadMappings();
      onMessage(
        resolution === "provider"
          ? "The reviewed provider value was applied to Oryntela."
          : "The current Oryntela value was kept.",
      );
    } catch (reason: unknown) {
      onError(
        reason instanceof Error
          ? reason.message
          : "The CRM conflict could not be resolved.",
      );
    }
  }

  return (
    <details className="mt-4 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer text-sm font-bold text-slate-800">
        CRM sync, ownership and mappings
      </summary>
      {!account ||
      !opportunity ||
      !contact ||
      !stages ||
      !status ||
      !owners ||
      !conflicts ? (
        <button
          type="button"
          className="secondary-button mt-3"
          disabled={loading}
          onClick={() => void loadMappings()}
        >
          {loading
            ? `Loading ${providerName} configuration…`
            : `Load ${providerName} configuration`}
        </button>
      ) : (
        <div className="mt-4 space-y-5">
          <section
            className="rounded-xl border border-slate-200 bg-slate-50 p-3"
            aria-labelledby={`crm-state-${connection.id}`}
          >
            <h4
              id={`crm-state-${connection.id}`}
              className="text-sm font-bold text-slate-950"
            >
              Connector state
            </h4>
            <dl className="mt-2 grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
              <div>
                <dt className="font-bold">Lifecycle</dt>
                <dd>{humanise(status.lifecycle)}</dd>
              </div>
              <div>
                <dt className="font-bold">Health</dt>
                <dd>{humanise(status.healthStatus)}</dd>
              </div>
              <div>
                <dt className="font-bold">Last successful sync</dt>
                <dd>
                  {status.lastSuccessfulSyncAt
                    ? new Date(status.lastSuccessfulSyncAt).toLocaleString(
                        "en-AU",
                      )
                    : "Not yet completed"}
                </dd>
              </div>
              <div>
                <dt className="font-bold">Records</dt>
                <dd>
                  {status.recordsApplied} applied of {status.recordsSeen} seen
                </dd>
              </div>
            </dl>
            <p className="mt-3 text-xs leading-5 text-slate-600">
              Initial and incremental sync are read-only. Writeback is off by
              default and every enabled write still requires a fresh preview and
              explicit confirmation.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="secondary-button"
                disabled={
                  !status.connectorEnabled ||
                  Boolean(
                    status.latestJob &&
                    ["queued", "running", "paused"].includes(
                      status.latestJob.status,
                    ),
                  )
                }
                onClick={() => void enqueueSync("incremental")}
              >
                Sync now
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  void setConnectorEnabled(!status.connectorEnabled)
                }
              >
                {status.connectorEnabled
                  ? "Stop all CRM sync"
                  : "Enable read-only sync"}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={!status.connectorEnabled}
                onClick={() => void reviewMappings()}
              >
                Approve current mappings
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={!status.connectorEnabled}
                onClick={() => void setWriteback(!status.writebackEnabled)}
              >
                {status.writebackEnabled
                  ? "Turn writeback off"
                  : "Enable reviewed writeback"}
              </button>
            </div>
          </section>
          <p className="text-xs leading-5 text-slate-600">
            Mapping is explicit. “Review before update” requires a fresh CRM
            read and final confirmation. “CRM is source of truth” blocks
            Oryntela writes for that field.
          </p>
          <FieldMappingGroup
            title="Account fields"
            entityType="company"
            fields={ACCOUNT_FIELDS}
            configuration={account}
            onSave={saveField}
          />
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
          <fieldset>
            <legend className="text-sm font-bold text-slate-900">
              CRM owners
            </legend>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              Every active CRM owner must map to an active Oryntela member
              before mappings can be approved.
            </p>
            <div className="mt-2 grid gap-2">
              {owners.items.length ? (
                owners.items.map((owner) => (
                  <label
                    key={owner.id}
                    className="grid gap-1 text-xs font-bold text-slate-700"
                  >
                    {owner.externalOwnerName ??
                      owner.externalOwnerEmail ??
                      owner.externalOwnerId}
                    <select
                      className="text-input"
                      value={owner.userId ?? ""}
                      disabled={owner.state === "inactive"}
                      onChange={(event) =>
                        void setOwner(owner.externalOwnerId, event.target.value)
                      }
                    >
                      <option value="">Not mapped</option>
                      {members
                        .filter((member) => member.active)
                        .map((member) => (
                          <option key={member.userId} value={member.userId}>
                            {member.displayName}
                          </option>
                        ))}
                    </select>
                  </label>
                ))
              ) : (
                <p className="text-xs text-slate-600">
                  Owners appear after the first account sync page.
                </p>
              )}
            </div>
          </fieldset>
          <section aria-labelledby={`crm-conflicts-${connection.id}`}>
            <h4
              id={`crm-conflicts-${connection.id}`}
              className="text-sm font-bold text-slate-900"
            >
              Conflicts (
              {conflicts.items.filter((item) => item.status === "open").length})
            </h4>
            {conflicts.items.some((item) => item.status === "open") ? (
              <ul className="mt-2 grid gap-2">
                {conflicts.items
                  .filter((item) => item.status === "open")
                  .map((conflict) => (
                    <li
                      key={conflict.id}
                      className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-slate-700"
                    >
                      <p className="font-bold text-slate-900">
                        {humanise(conflict.objectType)} ·{" "}
                        {humanise(conflict.fieldKey)}
                      </p>
                      <p className="mt-1 break-words">
                        Oryntela: {String(conflict.oryntelaValue ?? "Empty")} ·{" "}
                        {providerName}:{" "}
                        {String(conflict.providerValue ?? "Empty")}
                      </p>
                      <p className="mt-1 text-slate-600">
                        Authority: {humanise(conflict.authority)} · observed{" "}
                        {new Date(conflict.observedAt).toLocaleString()}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {conflict.allowedResolutions.includes("provider") ? (
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void resolveConflict(conflict.id, "provider")
                            }
                          >
                            Use reviewed {providerName} value
                          </button>
                        ) : null}
                        {conflict.allowedResolutions.includes("oryntela") ? (
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void resolveConflict(conflict.id, "oryntela")
                            }
                          >
                            Keep Oryntela value
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-slate-600">No open conflicts.</p>
            )}
          </section>
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
  entityType: "company" | "opportunity" | "contact";
  fields: readonly string[];
  configuration: CRMFieldConfiguration;
  onSave: (
    entityType: "company" | "opportunity" | "contact",
    revenueosField: string,
    propertyName: string,
    authority:
      "review_before_sync" | "crm_authoritative" | "revenueos_authoritative",
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
                      : current?.authority === "revenueos_authoritative"
                        ? "revenueos_authoritative"
                        : "review_before_sync"
                  }
                  onChange={(event) => {
                    if (current)
                      void onSave(
                        entityType,
                        field,
                        current.externalPropertyName,
                        event.target.value as
                          | "review_before_sync"
                          | "crm_authoritative"
                          | "revenueos_authoritative",
                      );
                  }}
                >
                  <option value="review_before_sync">
                    Review before update
                  </option>
                  <option value="crm_authoritative">
                    CRM is source of truth
                  </option>
                  <option value="revenueos_authoritative">
                    Oryntela is source of truth
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
