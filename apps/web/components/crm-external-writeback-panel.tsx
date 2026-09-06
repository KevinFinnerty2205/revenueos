"use client";

import type {
  ConnectionListResponse,
  CRMConnectionStatus,
  CRMEntityType,
  CRMWritebackPreview,
  CRMWritebackResult,
  OrganisationConnection,
} from "@revenueos/shared";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function CRMExternalWritebackPanel({
  entityType,
  entityId,
}: {
  entityType: CRMEntityType;
  entityId: string;
}) {
  const [connection, setConnection] = useState<OrganisationConnection | null>(
    null,
  );
  const [status, setStatus] = useState<CRMConnectionStatus | null>(null);
  const [preview, setPreview] = useState<CRMWritebackPreview | null>(null);
  const [result, setResult] = useState<CRMWritebackResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const idempotencyKey = useRef<string | null>(null);
  const writebackEntityType = entityType === "account" ? "company" : entityType;

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ConnectionListResponse>("/api/v1/integrations/connections", {
      signal: controller.signal,
    })
      .then(async (connections) => {
        const active = connections.items.find(
          (item) =>
            (item.connectorKey === "hubspot" ||
              item.connectorKey === "salesforce") &&
            item.connectionStatus === "active",
        );
        if (!active) return;
        setConnection(active);
        const nextStatus = await apiRequest<CRMConnectionStatus>(
          `/api/v1/integrations/connections/${active.id}/crm/status`,
          { signal: controller.signal },
        );
        setStatus(nextStatus);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "CRM writeback availability could not be checked.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function createPreview() {
    if (!connection) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const next = await apiRequest<CRMWritebackPreview>(
        `/api/v1/integrations/connections/${connection.id}/crm/writeback/preview`,
        {
          method: "POST",
          body: JSON.stringify({ entityType: writebackEntityType, entityId }),
        },
      );
      idempotencyKey.current = `crm-writeback-${globalThis.crypto.randomUUID()}`;
      setPreview(next);
      setConfirmed(false);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The CRM writeback preview could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmWriteback() {
    if (!connection || !preview || !confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<CRMWritebackResult>(
        `/api/v1/integrations/connections/${connection.id}/crm/writeback/confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            previewId: preview.id,
            previewFingerprint: preview.previewFingerprint,
            idempotencyKey:
              idempotencyKey.current ??
              `crm-writeback-${globalThis.crypto.randomUUID()}`,
            confirmed: true,
          }),
        },
      );
      setResult(next);
      setPreview(null);
      setConfirmed(false);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The reviewed CRM writeback could not be confirmed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function reconcile() {
    if (!connection || !result || result.status !== "unknown") return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<CRMWritebackResult>(
        `/api/v1/integrations/connections/${connection.id}/crm/writeback/receipts/${result.receiptId}/reconcile`,
        { method: "POST" },
      );
      setResult(next);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The CRM writeback outcome could not be reconciled.",
      );
    } finally {
      setBusy(false);
    }
  }

  const providerName = connection?.displayName ?? "CRM";
  const ready =
    status?.connectorEnabled === true &&
    status.writebackEnabled === true &&
    status.lifecycle === "ready";

  return (
    <section className="form-card" aria-labelledby="external-writeback-title">
      <h2 id="external-writeback-title" className="form-legend">
        Reviewed CRM update
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Preview the exact mapped fields before sending this record to the
        connected CRM. Nothing is written until you confirm.
      </p>
      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {loading ? (
        <p role="status" className="mt-4 text-sm text-slate-600">
          Checking CRM update availability…
        </p>
      ) : !connection ? (
        <p role="status" className="mt-4 text-sm text-slate-600">
          No active HubSpot or Salesforce connection is available.
        </p>
      ) : !ready ? (
        <p role="status" className="mt-4 text-sm text-amber-800">
          {providerName} writeback is unavailable. An organisation admin must
          complete the initial sync, approve mappings and explicitly enable
          writeback in Integration settings.
        </p>
      ) : (
        <>
          {!preview && !result ? (
            <button
              type="button"
              className="secondary-button mt-4"
              disabled={busy}
              onClick={() => void createPreview()}
            >
              {busy ? "Preparing preview…" : `Preview ${providerName} update`}
            </button>
          ) : null}
          {preview ? (
            <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5">
              <h3 className="font-semibold text-amber-950">
                Exact fields to {preview.operation}
              </h3>
              <dl className="mt-4 space-y-3">
                {Object.entries(preview.changes).map(([field, value]) => (
                  <div
                    key={field}
                    className="grid gap-1 rounded-xl bg-white p-3 sm:grid-cols-[12rem_1fr]"
                  >
                    <dt className="text-sm font-bold text-slate-700">
                      {humanise(field)}
                    </dt>
                    <dd className="break-words text-sm text-slate-900">
                      {displayValue(value)}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="mt-4 text-xs text-amber-900">
                Preview expires {formatDate(preview.expiresAt)}. RevenueOS will
                reject it if the CRM record or mapping changes first.
              </p>
              <label className="mt-4 flex items-start gap-3 text-sm font-semibold text-amber-950">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-teal-700"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                I reviewed every listed field and authorise this one CRM update.
              </label>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="primary-button"
                  disabled={busy || !confirmed}
                  onClick={() => void confirmWriteback()}
                >
                  {busy ? "Updating…" : `Update ${providerName}`}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={busy}
                  onClick={() => {
                    setPreview(null);
                    setConfirmed(false);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
          {result ? (
            <div
              role="status"
              className={`mt-5 rounded-xl p-4 text-sm ${
                result.status === "unknown"
                  ? "border border-amber-200 bg-amber-50 text-amber-950"
                  : "border border-emerald-200 bg-emerald-50 text-emerald-950"
              }`}
            >
              <p>{result.safeMessage}</p>
              {result.status === "unknown" ? (
                <>
                  <p className="mt-2 font-semibold">
                    RevenueOS did not retry the update.
                  </p>
                  <button
                    type="button"
                    className="secondary-button mt-3"
                    disabled={busy}
                    onClick={() => void reconcile()}
                  >
                    {busy
                      ? "Reconciling…"
                      : `Reconcile ${providerName} outcome`}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="secondary-button mt-3"
                  disabled={busy}
                  onClick={() => {
                    setResult(null);
                    idempotencyKey.current = null;
                  }}
                >
                  Preview another update
                </button>
              )}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
