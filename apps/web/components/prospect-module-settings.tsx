"use client";

import type {
  ProspectAvailability,
  ProspectProviderReadiness,
} from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function ProspectModuleSettings() {
  const [availability, setAvailability] = useState<ProspectAvailability | null>(
    null,
  );
  const [saving, setSaving] = useState(false);
  const [provider, setProvider] = useState<ProspectProviderReadiness | null>(
    null,
  );
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiRequest<ProspectAvailability>("/api/v1/prospect/availability"),
      apiRequest<ProspectProviderReadiness>(
        "/api/v1/prospect/admin/provider-readiness",
      ),
    ])
      .then(([nextAvailability, nextProvider]) => {
        setAvailability(nextAvailability);
        setProvider(nextProvider);
      })
      .catch(() => setMessage("Prospect settings could not be loaded."));
  }, []);

  async function update(enabled: boolean) {
    setSaving(true);
    setMessage(null);
    try {
      const next = await apiRequest<ProspectAvailability>(
        "/api/v1/prospect/admin/entitlement",
        { method: "PATCH", body: JSON.stringify({ enabled }) },
      );
      setAvailability(next);
      setMessage(
        enabled
          ? "Prospect is enabled for this organisation."
          : "Prospect is disabled. Existing Accounts remain available.",
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "Prospect settings could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="prospect-module-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Modules
      </p>
      <div className="mt-2 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="prospect-module-title" className="form-legend">
            RevenueOS Prospect
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Let active sales members find companies and create sourced public
            account research. Public research stays separate from customer
            Evidence.
          </p>
        </div>
        {availability?.canManage ? (
          <button
            type="button"
            role="switch"
            aria-checked={availability.enabled}
            disabled={
              saving || availability.state === "temporarily_unavailable"
            }
            onClick={() => void update(!availability.enabled)}
            className={`inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 ${
              availability.enabled
                ? "border-teal-700 bg-teal-700 text-white"
                : "border-slate-300 bg-white text-slate-700"
            }`}
          >
            {saving ? "Saving…" : availability.enabled ? "Enabled" : "Disabled"}
          </button>
        ) : availability ? (
          <span className="text-sm font-semibold text-slate-500">
            Managed by an administrator
          </span>
        ) : (
          <span className="text-sm text-slate-500">Loading…</span>
        )}
      </div>
      {message ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {message}
        </p>
      ) : null}
      {provider ? (
        <div
          className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4"
          role="region"
          aria-labelledby="prospect-provider-status"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3
                id="prospect-provider-status"
                className="text-sm font-bold text-slate-900"
              >
                Live research readiness
              </h3>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {provider.message}
              </p>
            </div>
            <span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-bold text-slate-700">
              {provider.adapterState === "READY" ? "Ready" : "Not active"}
            </span>
          </div>
          {provider.blockers.length > 0 ? (
            <details className="mt-3 text-sm text-slate-700">
              <summary className="min-h-11 cursor-pointer py-3 font-semibold focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2">
                Review activation requirements
              </summary>
              <ul className="list-disc space-y-2 pl-5">
                {provider.blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            </details>
          ) : null}
          <p className="mt-3 text-xs leading-5 text-slate-500">
            No production Credit prices, Credit packs, automatic top-up, phone
            reveal or recent-post collection are active.
          </p>
        </div>
      ) : null}
    </section>
  );
}
