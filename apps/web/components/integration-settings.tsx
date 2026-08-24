"use client";

import type {
  ConnectionListResponse,
  ConnectorDefinition,
  ConnectorKey,
  IntegrationCatalogResponse,
  OrganisationConnection,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function IntegrationSettings() {
  const [catalog, setCatalog] = useState<ConnectorDefinition[]>([]);
  const [connections, setConnections] = useState<OrganisationConnection[]>([]);
  const [busy, setBusy] = useState<ConnectorKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [definitions, connectionList] = await Promise.all([
      apiRequest<IntegrationCatalogResponse>("/api/v1/integrations"),
      apiRequest<ConnectionListResponse>("/api/v1/integrations/connections"),
    ]);
    setCatalog(definitions.connectors);
    setConnections(connectionList.items);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<IntegrationCatalogResponse>("/api/v1/integrations"),
      apiRequest<ConnectionListResponse>("/api/v1/integrations/connections"),
    ])
      .then(([definitions, connectionList]) => {
        if (!active) return;
        setCatalog(definitions.connectors);
        setConnections(connectionList.items);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Simulation connectors could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function connect(connectorKey: ConnectorKey) {
    setBusy(connectorKey);
    setError(null);
    setMessage(null);
    try {
      await apiRequest<OrganisationConnection>(
        "/api/v1/integrations/connections",
        {
          method: "POST",
          body: JSON.stringify({ connectorKey }),
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
          : "The simulation connector could not be enabled.",
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
        "Simulation connection verified. No external request was made.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The simulation connection could not be tested.",
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
        "Simulation connector revoked. Pending previews and queued simulations were invalidated.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The simulation connector could not be revoked.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="form-card" aria-labelledby="integrations-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Development / Beta Simulation
      </p>
      <h2 id="integrations-title" className="mt-2 text-xl font-semibold">
        Integrations
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        These deterministic mock connectors exercise review, confirmation and
        audit controls only. They never contact an email, calendar, CRM or task
        service.
      </p>

      {catalog.length ? (
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          {catalog.map((definition) => {
            const connection = connections.find(
              (item) => item.connectorKey === definition.connectorKey,
            );
            const active = connection?.connectionStatus === "active";
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
                    <p className="mt-1 text-xs font-bold uppercase tracking-wide text-amber-800">
                      Simulation — no external action
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
                    {active ? "Connected" : "Not connected"}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-600">
                  Capabilities:{" "}
                  {definition.supportedCapabilities.map(humanise).join(", ")}
                </p>
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
                        Test simulation
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
                      onClick={() => void connect(definition.connectorKey)}
                    >
                      Connect simulation
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : error ? null : (
        <p role="status" className="mt-4 text-sm text-slate-600">
          Loading simulation connectors…
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
