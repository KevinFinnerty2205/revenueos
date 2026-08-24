"use client";

import type {
  ConnectionListResponse,
  CRMEntityMapping,
  CRMSearchResponse,
  CRMSearchResult,
  OrganisationConnection,
} from "@revenueos/shared";
import { useState } from "react";
import { apiRequest } from "@/lib/api";

export function CRMRecordLink({ opportunityId }: { opportunityId: string }) {
  const [connection, setConnection] = useState<OrganisationConnection | null>(
    null,
  );
  const [mapping, setMapping] = useState<CRMEntityMapping | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CRMSearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadConnection() {
    setBusy(true);
    setError(null);
    try {
      const response = await apiRequest<ConnectionListResponse>(
        "/api/v1/integrations/connections",
      );
      const hubspot = response.items.find(
        (item) =>
          item.connectorKey === "hubspot" && item.connectionStatus === "active",
      );
      if (!hubspot) {
        throw new Error(
          "Ask an administrator to connect HubSpot before linking this opportunity.",
        );
      }
      setConnection(hubspot);
      const current = await apiRequest<CRMEntityMapping | null>(
        `/api/v1/integrations/connections/${hubspot.id}/crm/entities/opportunity/${opportunityId}`,
      );
      setMapping(current);
      setLoaded(true);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The HubSpot link could not be loaded.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function search() {
    if (!connection || query.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiRequest<CRMSearchResponse>(
        `/api/v1/integrations/connections/${connection.id}/crm/search?entityType=opportunity&query=${encodeURIComponent(query.trim())}`,
      );
      setResults(response.items);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "HubSpot deals could not be searched.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function link(result: CRMSearchResult) {
    if (!connection) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await apiRequest<CRMEntityMapping>(
        `/api/v1/integrations/crm/entities/opportunity/${opportunityId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            connectionId: connection.id,
            externalObjectType: "deal",
            externalObjectId: result.externalObjectId,
          }),
        },
      );
      setMapping(saved);
      setResults([]);
      setQuery("");
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The HubSpot deal could not be linked.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function unlink() {
    if (!connection) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest(
        `/api/v1/integrations/connections/${connection.id}/crm/entities/opportunity/${opportunityId}`,
        { method: "DELETE" },
      );
      setMapping(null);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The HubSpot deal link could not be removed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="crm-record-link-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        HubSpot context
      </p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="crm-record-link-title" className="form-legend">
            CRM record link
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Linking selects the exact HubSpot deal used for reviewed updates. It
            does not import or overwrite data.
          </p>
        </div>
        {mapping ? (
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
            Connected
          </span>
        ) : null}
      </div>
      {!loaded ? (
        <button
          type="button"
          className="secondary-button mt-4"
          disabled={busy}
          onClick={() => void loadConnection()}
        >
          {busy ? "Checking CRM link…" : "Connect to CRM record"}
        </button>
      ) : mapping ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3">
          <p className="text-sm text-slate-700">
            HubSpot deal ID: {mapping.externalObjectId}
          </p>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => void unlink()}
          >
            Remove link
          </button>
        </div>
      ) : (
        <>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <label
              className="sr-only"
              htmlFor={`hubspot-deal-search-${opportunityId}`}
            >
              Search HubSpot deals
            </label>
            <input
              id={`hubspot-deal-search-${opportunityId}`}
              className="text-input flex-1"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search HubSpot deals by name"
            />
            <button
              type="button"
              className="secondary-button"
              disabled={busy || query.trim().length < 2}
              onClick={() => void search()}
            >
              {busy ? "Searching…" : "Search"}
            </button>
          </div>
          {results.length ? (
            <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
              {results.map((result) => (
                <li
                  key={result.externalObjectId}
                  className="flex items-center justify-between gap-3 p-3"
                >
                  <div>
                    <p className="text-sm font-bold text-slate-900">
                      {result.displayName}
                    </p>
                    {result.secondaryLabel ? (
                      <p className="text-xs text-slate-500">
                        {result.secondaryLabel}
                      </p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => void link(result)}
                  >
                    Link
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
      {error ? (
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </section>
  );
}
