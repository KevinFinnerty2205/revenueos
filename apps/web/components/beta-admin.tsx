"use client";

import { apiBlob, apiRequest } from "@/lib/api";
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
    completedAt: string | null;
    expiresAt: string | null;
    downloadAvailable: boolean;
    failureCode: string | null;
  }>;
}

interface MemberStatusUpdateResponse {
  member: AdminOverview["members"][number];
  sessionRevocation: {
    outcome: "succeeded" | "failed" | "unknown" | "not_required";
    revokedSessionCount: number;
  };
}

const retentionLabels: Record<AdminOverview["retention"]["policy"], string> = {
  days_30: "30 days",
  days_90: "90 days",
  days_180: "180 days",
  manual: "Retain until manually deleted",
};

const featureFlagLabels: Record<string, string> = {
  credits: "Credits",
  prospectExternalProvider: "External Prospect provider",
  openaiProvider: "External OpenAI processing",
  revenueBrain: "Revenue Brain",
  opportunityWorkspace: "Opportunity Workspace",
  aiCompanion: "AI Companion",
  aiDebrief: "AI Debrief",
  voiceJournal: "Voice Journal",
  visualEvidence: "Visual evidence",
  presentationMode: "Presentation mode",
  recordingCapture: "Recording capture",
  transcription: "Transcription",
  autoGenerateIntelligenceAfterTranscription:
    "Automatic intelligence after transcription",
  onlineMeetingCapture: "Online meeting capture",
  onlineMeetingImport: "Online meeting import",
  onlineMeetingNativeIntegration: "Native online meeting integration",
  onlineMeetingAutoIngest: "Automatic online meeting ingest",
  documentEvidence: "Document evidence",
  emailEvidence: "Email evidence",
  salesMethodology: "Sales methodology",
  askRevenueOS: "Ask Oryntela",
  liveInteractionIntelligence: "Live interaction intelligence",
  liveInteractionExternalAi: "External AI for live interactions",
  actionLayer: "Action layer",
  actionManualCompletion: "Manual action completion",
  integrations: "Integrations foundation",
  actionExecution: "Explicit Action execution",
  mockConnectors: "Mock simulation connectors",
  hubspotCrm: "HubSpot CRM sync",
  salesforceCrm: "Salesforce CRM sync",
  microsoft365: "Microsoft 365 sales integration",
  googleWorkspace: "Google Workspace sales integration",
  nativeCrm: "Native CRM",
  nativePipeline: "Native pipeline",
  salesAnalytics: "Sales analytics",
  salesTargets: "Sales targets",
  salesForecasting: "Sales forecasting",
  managerIntelligence: "Manager intelligence",
  dataExport: "Organisation data export",
  organisationDeletion: "Organisation deletion",
  prospect: "Prospect",
  engage: "Engage",
  engageCampaigns: "Engage campaigns",
  engageEvents: "Engage events",
  create: "Create",
};

function featureFlagLabel(name: string): string {
  const known = featureFlagLabels[name];
  if (known) return known;
  const words = name
    .replaceAll("_", " ")
    .replace(/([a-z\d])([A-Z])/gu, "$1 $2")
    .trim();
  return words.length
    ? `${words.charAt(0).toUpperCase()}${words.slice(1)}`
    : "Capability";
}

export function BetaAdmin({ currentUserId }: { currentUserId: string }) {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [deletionConfirmation, setDeletionConfirmation] = useState("");
  const [busyMember, setBusyMember] = useState<string | null>(null);
  const [busyExport, setBusyExport] = useState<string | null>(null);

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
      const result = await apiRequest<MemberStatusUpdateResponse>(
        `/api/v1/beta/admin/members/${userId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: membershipStatus }),
        },
      );
      setStatus(
        membershipStatus === "disabled"
          ? result.sessionRevocation.outcome === "succeeded" ||
            result.sessionRevocation.outcome === "not_required"
            ? "The member has been disabled. Protected access is denied and their relevant active authentication sessions were revoked."
            : "The member has been disabled and protected access is denied. Authentication-session revocation requires operator reconciliation."
          : "The member has been re-enabled. Previously revoked sessions remain unusable; they must authenticate again.",
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

  async function downloadExport(requestId: string) {
    setError(null);
    setStatus(null);
    setBusyExport(requestId);
    try {
      const blob = await apiBlob(
        `/api/v1/beta/admin/exports/${requestId}/download`,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `oryntela-export-${requestId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus("The temporary organisation export was downloaded.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The temporary export could not be downloaded.",
      );
      await load();
    } finally {
      setBusyExport(null);
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
        <details className="mt-2 text-xs text-slate-500">
          <summary className="w-fit cursor-pointer font-semibold focus:outline-none focus:ring-2 focus:ring-brand-focus">
            Technical organisation identifier
          </summary>
          <p className="mt-2 break-all">{overview.organisation.id}</p>
        </details>
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
                {member.user.id === currentUserId ? (
                  <span className="text-xs font-semibold text-slate-500">
                    Current user
                  </span>
                ) : (
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
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <details className="form-card group">
        <summary className="cursor-pointer list-none focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2">
          <span className="flex items-center justify-between gap-4">
            <span>
              <span className="block text-xl font-semibold text-slate-950">
                Technical diagnostics
              </span>
              <span className="mt-1 block text-sm font-normal text-slate-600">
                Server capability flags for troubleshooting. Most administrators
                do not need these details.
              </span>
            </span>
            <span
              aria-hidden="true"
              className="text-sm font-bold text-brand-secondary"
            >
              <span className="group-open:hidden">Show</span>
              <span className="hidden group-open:inline">Hide</span>
            </span>
          </span>
        </summary>
        <dl className="mt-5 grid gap-3 border-t border-slate-200 pt-5 sm:grid-cols-2">
          {Object.entries(overview.featureFlags).map(([name, enabled]) => (
            <div key={name} className="rounded-2xl bg-slate-50 p-4">
              <dt className="text-sm font-semibold">
                {featureFlagLabel(name)}
              </dt>
              <dd className="mt-1 text-sm text-slate-600">
                {enabled ? "Enabled" : "Disabled"}
              </dd>
            </div>
          ))}
        </dl>
      </details>

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
          {overview.dataRequests.map((request) => {
            const expiry = request.expiresAt
              ? new Date(request.expiresAt).toLocaleString("en-AU")
              : null;
            return (
              <li
                key={request.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3"
              >
                <span>
                  {request.requestType.replaceAll("_", " ")} · {request.status}{" "}
                  · {new Date(request.requestedAt).toLocaleString("en-AU")}
                  {request.downloadAvailable && expiry
                    ? ` · available until ${expiry}`
                    : request.status === "completed" && expiry
                      ? ` · download expired ${expiry}`
                      : request.status === "failed"
                        ? ` · ${request.failureCode?.replaceAll("_", " ") ?? "generation failed"}`
                        : ""}
                </span>
                {request.requestType === "export" &&
                request.downloadAvailable ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busyExport === request.id}
                    onClick={() => void downloadExport(request.id)}
                  >
                    {busyExport === request.id
                      ? "Downloading…"
                      : "Download export"}
                  </button>
                ) : null}
              </li>
            );
          })}
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

      <details className="form-card group">
        <summary className="cursor-pointer list-none focus:outline-none focus:ring-2 focus:ring-brand-focus focus:ring-offset-2">
          <span className="flex items-center justify-between gap-4">
            <span>
              <span className="block text-xl font-semibold text-slate-950">
                Recent system events
              </span>
              <span className="mt-1 block text-sm font-normal text-slate-600">
                Content-free administration history for troubleshooting.
              </span>
            </span>
            <span
              aria-hidden="true"
              className="text-sm font-bold text-brand-secondary"
            >
              <span className="group-open:hidden">Show</span>
              <span className="hidden group-open:inline">Hide</span>
            </span>
          </span>
        </summary>
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
      </details>

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
