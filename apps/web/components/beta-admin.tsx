"use client";

import { apiRequest } from "@/lib/api";
import { IntegrationSettings } from "@/components/integration-settings";
import { useEffect, useState } from "react";

interface AdminOverview {
  organisation: { id: string; name: string; slug: string };
  members: Array<{
    user: { id: string; displayName: string; email: string };
    role: "admin" | "member";
    status: "active" | "disabled";
    joinedAt: string;
  }>;
  retention: {
    policy: "days_30" | "days_90" | "days_180" | "manual";
    defaultApplied: boolean;
  };
  noticeVersion: number;
  acknowledgementCount: number;
  activeMemberCount: number;
  featureFlags: Record<string, boolean>;
  usage: {
    date: string;
    generations: number;
    generationLimit: number;
    providerRequests: number;
    providerRequestLimit: number;
    estimatedCostAvailable: false;
  };
  recentEvents: Array<{
    id: string;
    eventType: string;
    subjectId: string | null;
    createdAt: string;
  }>;
  dataRequests: Array<{
    id: string;
    requestType: "export" | "organisation_deletion";
    status: string;
    requestedAt: string;
    downloadAvailable: boolean;
  }>;
}

const retentionLabels: Record<AdminOverview["retention"]["policy"], string> = {
  days_30: "30 days",
  days_90: "90 days",
  days_180: "180 days",
  manual: "Retain until manually deleted",
};

const featureFlagLabels: Record<string, string> = {
  openaiProvider: "External OpenAI processing",
  revenueBrain: "Revenue Brain",
  opportunityWorkspace: "Opportunity Workspace",
  integrations: "Integrations foundation",
  actionExecution: "Explicit Action execution",
  mockConnectors: "Mock simulation connectors",
  hubspotCrm: "HubSpot CRM sync",
  dataExport: "Organisation data export",
  organisationDeletion: "Organisation deletion",
};

export function BetaAdmin() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [deletionConfirmation, setDeletionConfirmation] = useState("");
  const [busyMember, setBusyMember] = useState<string | null>(null);

  async function load() {
    try {
      setOverview(await apiRequest<AdminOverview>("/api/v1/beta/admin"));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Beta administration could not be loaded.",
      );
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<AdminOverview>("/api/v1/beta/admin", {
      signal: controller.signal,
    })
      .then(setOverview)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Beta administration could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, []);

  async function saveRetention(policy: AdminOverview["retention"]["policy"]) {
    setError(null);
    setStatus(null);
    try {
      await apiRequest("/api/v1/beta/admin/retention", {
        method: "PATCH",
        body: JSON.stringify({ policy }),
      });
      setStatus(
        "Retention policy saved. The next maintenance run applies it to eligible current and historical data.",
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Retention could not be saved.",
      );
    }
  }

  async function requestExport() {
    setError(null);
    setStatus(null);
    try {
      await apiRequest("/api/v1/beta/admin/exports", { method: "POST" });
      setStatus(
        "Export queued. An operator will generate the temporary JSON file.",
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The export could not be queued.",
      );
    }
  }

  async function updateMember(
    userId: string,
    membershipStatus: "active" | "disabled",
  ) {
    setError(null);
    setStatus(null);
    setBusyMember(userId);
    try {
      await apiRequest(`/api/v1/beta/admin/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: membershipStatus }),
      });
      setStatus(
        membershipStatus === "disabled"
          ? "The member has been disabled. Their next authenticated request will be rejected."
          : "The member has been re-enabled.",
      );
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The member status could not be changed.",
      );
    } finally {
      setBusyMember(null);
    }
  }

  async function requestDeletion() {
    if (!overview) return;
    setError(null);
    setStatus(null);
    try {
      await apiRequest("/api/v1/beta/admin/organisation-deletion", {
        method: "POST",
        body: JSON.stringify({ confirmation: deletionConfirmation }),
      });
      setStatus(
        "Organisation deletion queued for operator review. No data has been deleted yet.",
      );
      setDeletionConfirmation("");
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The deletion request could not be queued.",
      );
    }
  }

  if (error && !overview)
    return (
      <p role="alert" className="rounded-2xl bg-rose-50 p-4 text-rose-900">
        {error}
      </p>
    );
  if (!overview)
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading private beta administration…
      </p>
    );

  const deletionPhrase = `DELETE ${overview.organisation.slug}`;
  return (
    <div className="space-y-6">
      <section
        className="form-card"
        aria-labelledby="organisation-settings-title"
      >
        <h2 id="organisation-settings-title" className="text-2xl font-semibold">
          {overview.organisation.name}
        </h2>
        <p className="mt-2 break-all text-xs text-slate-500">
          Organisation ID: {overview.organisation.id}
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Metric
            label="Active members"
            value={String(overview.activeMemberCount)}
          />
          <Metric
            label={`Notice v${overview.noticeVersion}`}
            value={`${overview.acknowledgementCount} acknowledged`}
          />
          <Metric
            label="Today’s generations"
            value={`${overview.usage.generations} / ${overview.usage.generationLimit}`}
          />
        </div>
        <p className="mt-3 text-xs text-slate-500">
          External AI requests: {overview.usage.providerRequests} /{" "}
          {overview.usage.providerRequestLimit}. Cost is unavailable; no pricing
          claim is made.
        </p>
      </section>

      <section className="form-card" aria-labelledby="retention-title">
        <h2 id="retention-title" className="text-xl font-semibold">
          Retention
        </h2>
        <label
          htmlFor="retention-policy"
          className="mt-4 block text-sm font-bold text-slate-800"
        >
          Transcript and intelligence retention policy
        </label>
        <select
          id="retention-policy"
          className="form-control mt-2 w-full"
          value={overview.retention.policy}
          onChange={(event) =>
            void saveRetention(
              event.target.value as AdminOverview["retention"]["policy"],
            )
          }
        >
          {Object.entries(retentionLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="mt-3 text-xs text-slate-500">
          The private-beta default is 90 days. “Manual” must be selected
          explicitly.
        </p>
      </section>

      <section className="form-card" aria-labelledby="members-title">
        <h2 id="members-title" className="text-xl font-semibold">
          Members
        </h2>
        <ul className="mt-4 divide-y divide-slate-200">
          {overview.members.map((member) => (
            <li
              key={member.user.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div>
                <p className="font-semibold">{member.user.displayName}</p>
                <p className="text-sm text-slate-500">{member.user.email}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">
                  {member.role} · {member.status}
                </span>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={busyMember === member.user.id}
                  aria-label={`${member.status === "active" ? "Disable" : "Enable"} ${member.user.displayName}`}
                  onClick={() =>
                    void updateMember(
                      member.user.id,
                      member.status === "active" ? "disabled" : "active",
                    )
                  }
                >
                  {busyMember === member.user.id
                    ? "Saving…"
                    : member.status === "active"
                      ? "Disable"
                      : "Enable"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="form-card" aria-labelledby="flags-title">
        <h2 id="flags-title" className="text-xl font-semibold">
          Server feature flags
        </h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          {Object.entries(overview.featureFlags).map(([name, enabled]) => (
            <div key={name} className="rounded-2xl bg-slate-50 p-4">
              <dt className="text-sm font-semibold">
                {featureFlagLabels[name] ?? "Unrecognised capability"}
              </dt>
              <dd className="mt-1 text-sm text-slate-600">
                {enabled ? "Enabled" : "Disabled"}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="form-card" aria-labelledby="data-requests-title">
        <h2 id="data-requests-title" className="text-xl font-semibold">
          Data requests
        </h2>
        {overview.featureFlags.dataExport ? (
          <button
            className="secondary-button mt-4"
            type="button"
            onClick={() => void requestExport()}
          >
            Request organisation export
          </button>
        ) : (
          <p className="mt-3 text-sm text-slate-600">
            Organisation export is not enabled.
          </p>
        )}
        <ul className="mt-4 space-y-2 text-sm text-slate-600">
          {overview.dataRequests.map((request) => (
            <li key={request.id}>
              {request.requestType.replaceAll("_", " ")} · {request.status} ·{" "}
              {new Date(request.requestedAt).toLocaleString("en-AU")}
            </li>
          ))}
        </ul>
      </section>

      {overview.featureFlags.integrations ? <IntegrationSettings /> : null}

      {overview.featureFlags.organisationDeletion ? (
        <section
          className="rounded-3xl border border-rose-200 bg-white p-6"
          aria-labelledby="deletion-title"
        >
          <h2
            id="deletion-title"
            className="text-xl font-semibold text-rose-950"
          >
            Organisation deletion
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            This queues a reviewed maintenance operation. Type{" "}
            <strong>{deletionPhrase}</strong> exactly. Deletion from the
            identity service remains a separate operator step.
          </p>
          <label
            htmlFor="deletion-confirmation"
            className="mt-4 block text-sm font-bold"
          >
            Confirmation phrase
          </label>
          <input
            id="deletion-confirmation"
            className="form-control mt-2 w-full"
            value={deletionConfirmation}
            onChange={(event) => setDeletionConfirmation(event.target.value)}
          />
          <button
            className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-rose-700 px-5 py-3 text-sm font-bold text-white disabled:opacity-50"
            type="button"
            disabled={deletionConfirmation !== deletionPhrase}
            onClick={() => void requestDeletion()}
          >
            Queue organisation deletion
          </button>
        </section>
      ) : null}

      <section className="form-card" aria-labelledby="events-title">
        <h2 id="events-title" className="text-xl font-semibold">
          Recent safe system events
        </h2>
        <ul className="mt-4 space-y-2 text-sm text-slate-600">
          {overview.recentEvents.length ? (
            overview.recentEvents.map((event) => (
              <li key={event.id}>
                {event.eventType.replaceAll("_", " ")} ·{" "}
                {new Date(event.createdAt).toLocaleString("en-AU")}
              </li>
            ))
          ) : (
            <li>No recent beta events.</li>
          )}
        </ul>
      </section>

      {status ? (
        <p
          role="status"
          aria-live="polite"
          className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-950"
        >
          {status}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          aria-live="assertive"
          className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}
