"use client";

import type { EngageAvailability, OutreachPolicy } from "@revenueos/shared";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface PolicyDraft {
  outboundEnabled: boolean;
  providerSuppliedEmailAllowed: boolean;
  cooldownHours: number;
  maxDailySendsUser: number;
  maxDailySendsOrg: number;
  requireOptOutMechanism: boolean;
  offeringName: string;
  valueProposition: string;
  approvedCta: string;
}

function draftFrom(policy: OutreachPolicy): PolicyDraft {
  return {
    outboundEnabled: policy.outboundEnabled,
    providerSuppliedEmailAllowed: policy.providerSuppliedEmailAllowed,
    cooldownHours: policy.cooldownHours,
    maxDailySendsUser: policy.maxDailySendsUser,
    maxDailySendsOrg: policy.maxDailySendsOrg,
    requireOptOutMechanism: policy.requireOptOutMechanism,
    offeringName: policy.offeringName ?? "",
    valueProposition: policy.valueProposition ?? "",
    approvedCta: policy.approvedCta ?? "",
  };
}

export function EngageSettings() {
  const [availability, setAvailability] = useState<EngageAvailability | null>(
    null,
  );
  const [policy, setPolicy] = useState<OutreachPolicy | null>(null);
  const [draft, setDraft] = useState<PolicyDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiRequest<EngageAvailability>("/api/v1/engage/availability"),
      apiRequest<OutreachPolicy>("/api/v1/engage/policy"),
    ])
      .then(([nextAvailability, nextPolicy]) => {
        setAvailability(nextAvailability);
        setPolicy(nextPolicy);
        setDraft(draftFrom(nextPolicy));
      })
      .catch(() => setMessage("Engage settings could not be loaded."));
  }, []);

  async function toggleEntitlement() {
    if (!availability) return;
    setBusy("entitlement");
    setMessage(null);
    try {
      const next = await apiRequest<EngageAvailability>(
        "/api/v1/engage/admin/entitlement",
        {
          method: "PATCH",
          body: JSON.stringify({ enabled: !availability.enabled }),
        },
      );
      setAvailability(next);
      setMessage(
        next.enabled
          ? "Engage is enabled for this organisation."
          : "Engage is disabled. Existing outreach history remains available to authorised maintenance workflows.",
      );
    } catch (reason: unknown) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The Engage entitlement could not be saved.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function savePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setBusy("policy");
    setMessage(null);
    try {
      const next = await apiRequest<OutreachPolicy>("/api/v1/engage/policy", {
        method: "PUT",
        body: JSON.stringify(draft),
      });
      setPolicy(next);
      setDraft(draftFrom(next));
      setMessage("Engage policy and approved seller context saved.");
    } catch (reason: unknown) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The Engage policy could not be saved.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="form-card" aria-labelledby="engage-settings-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Modules
      </p>
      <div className="mt-2 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="engage-settings-title" className="form-legend">
            RevenueOS Engage
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Configure source-backed one-to-one outreach, conservative send
            limits and business-address trust policy. Permission remains a
            separate organisation responsibility.
          </p>
        </div>
        {availability ? (
          <button
            type="button"
            role="switch"
            aria-checked={availability.enabled}
            disabled={
              busy !== null || availability.state === "temporarily_unavailable"
            }
            onClick={() => void toggleEntitlement()}
            className={`inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 ${
              availability.enabled
                ? "border-teal-700 bg-teal-700 text-white"
                : "border-slate-300 bg-white text-slate-700"
            }`}
          >
            {busy === "entitlement"
              ? "Saving…"
              : availability.enabled
                ? "Enabled"
                : "Disabled"}
          </button>
        ) : (
          <span className="text-sm text-slate-500">Loading…</span>
        )}
      </div>

      {draft ? (
        <form
          onSubmit={savePolicy}
          className="mt-7 border-t border-slate-200 pt-7"
        >
          <fieldset disabled={busy !== null} className="space-y-6">
            <legend className="text-base font-bold text-slate-950">
              Approved outreach context and controls
            </legend>
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField
                id="engage-offering"
                label="Approved offering"
                value={draft.offeringName}
                maxLength={120}
                onChange={(value) =>
                  setDraft({ ...draft, offeringName: value })
                }
              />
              <TextField
                id="engage-cta"
                label="Approved call to action"
                value={draft.approvedCta}
                maxLength={300}
                onChange={(value) => setDraft({ ...draft, approvedCta: value })}
              />
            </div>
            <div>
              <label
                htmlFor="engage-value"
                className="text-sm font-bold text-slate-800"
              >
                Approved value proposition
              </label>
              <textarea
                id="engage-value"
                required
                rows={4}
                maxLength={1000}
                value={draft.valueProposition}
                onChange={(event) =>
                  setDraft({ ...draft, valueProposition: event.target.value })
                }
                className="form-control mt-2 w-full resize-y py-3 leading-6"
              />
            </div>
            <div className="grid gap-5 sm:grid-cols-3">
              <NumberField
                id="engage-cooldown"
                label="Contact cooldown (hours)"
                value={draft.cooldownHours}
                min={0}
                max={720}
                onChange={(value) =>
                  setDraft({ ...draft, cooldownHours: value })
                }
              />
              <NumberField
                id="engage-user-limit"
                label="Daily limit per sender"
                value={draft.maxDailySendsUser}
                min={1}
                max={500}
                onChange={(value) =>
                  setDraft({ ...draft, maxDailySendsUser: value })
                }
              />
              <NumberField
                id="engage-org-limit"
                label="Daily organisation limit"
                value={draft.maxDailySendsOrg}
                min={1}
                max={2000}
                onChange={(value) =>
                  setDraft({ ...draft, maxDailySendsOrg: value })
                }
              />
            </div>
            <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
              <Checkbox
                label="Allow provider-supplied business email"
                checked={draft.providerSuppliedEmailAllowed}
                onChange={(checked) =>
                  setDraft({ ...draft, providerSuppliedEmailAllowed: checked })
                }
              />
              <Checkbox
                label="Enable outbound execution"
                checked={draft.outboundEnabled}
                onChange={(checked) =>
                  setDraft({ ...draft, outboundEnabled: checked })
                }
              />
              <Checkbox
                label="Require opt-out mechanism"
                checked={draft.requireOptOutMechanism}
                onChange={(checked) =>
                  setDraft({ ...draft, requireOptOutMechanism: checked })
                }
              />
            </div>
          </fieldset>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button
              type="submit"
              className="primary-button"
              disabled={busy !== null}
            >
              {busy === "policy" ? "Saving policy…" : "Save Engage policy"}
            </button>
            <p className="text-xs leading-5 text-slate-500">
              Production Gmail and Microsoft mailbox adapters are not enabled.
              Local/test email execution is clearly labelled simulation only.
            </p>
          </div>
          {policy ? (
            <p className="mt-4 text-xs text-slate-500">
              {policy.complianceNotice}
            </p>
          ) : null}
        </form>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {message}
        </p>
      ) : null}
    </section>
  );
}

function TextField({
  id,
  label,
  value,
  maxLength,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  maxLength: number;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-bold text-slate-800">
        {label}
      </label>
      <input
        id={id}
        required
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="form-control mt-2 w-full"
      />
    </div>
  );
}

function NumberField({
  id,
  label,
  value,
  min,
  max,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-bold text-slate-800">
        {label}
      </label>
      <input
        id={id}
        type="number"
        required
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="form-control mt-2 w-full"
      />
    </div>
  );
}

function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-slate-800">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-5 rounded border-slate-300 text-teal-700 focus:ring-teal-600"
      />
      {label}
    </label>
  );
}
