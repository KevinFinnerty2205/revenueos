"use client";

import type { CreateAvailability } from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function CreateModuleSettings() {
  const [availability, setAvailability] = useState<CreateAvailability | null>(
    null,
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<CreateAvailability>("/api/v1/create/availability")
      .then(setAvailability)
      .catch(() => setMessage("Create settings could not be loaded."));
  }, []);

  async function update(enabled: boolean) {
    setSaving(true);
    setMessage(null);
    try {
      const next = await apiRequest<CreateAvailability>(
        "/api/v1/create/admin/entitlement",
        { method: "PATCH", body: JSON.stringify({ enabled }) },
      );
      setAvailability(next);
      setMessage(
        enabled
          ? "Create is enabled for this organisation."
          : "Create is disabled. Existing Accounts and Opportunities are unchanged.",
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "Create settings could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="create-module-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Add-on module
      </p>
      <div className="mt-2 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="create-module-title" className="form-legend">
            RevenueOS Create
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Build reviewed PowerPoint presentations from approved company
            templates and traceable, customer-safe context. Create does not send
            presentations externally.
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
    </section>
  );
}
