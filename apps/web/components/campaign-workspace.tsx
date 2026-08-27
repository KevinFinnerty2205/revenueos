"use client";

import type {
  ActionExecution,
  ActionExecutionOptionListResponse,
  Campaign,
  CampaignApprovalMode,
  CampaignEnrollment,
  CampaignEnrollmentListResponse,
  CampaignListResponse,
  CampaignOutcome,
  CampaignStepObjective,
  Contact,
  EngageAvailability,
  EntityPage,
  ExecutionPreview,
  OutreachMessage,
  OutreachPolicy,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

interface StepDraft {
  key: string;
  delayDays: number;
  objective: CampaignStepObjective;
}

const objectiveOptions: Array<{ value: CampaignStepObjective; label: string }> =
  [
    { value: "introduction", label: "Introduction" },
    { value: "follow_up", label: "Follow-up" },
    {
      value: "share_relevant_information",
      label: "Share relevant information",
    },
    { value: "different_angle", label: "Different relevant angle" },
    { value: "meeting_request", label: "Meeting request" },
    { value: "final_follow_up", label: "Final respectful follow-up" },
  ];

const defaultSteps: StepDraft[] = [
  { key: "step-1", delayDays: 0, objective: "introduction" },
  { key: "step-2", delayDays: 4, objective: "follow_up" },
  { key: "step-3", delayDays: 5, objective: "different_angle" },
  { key: "step-4", delayDays: 7, objective: "final_follow_up" },
];

function contentStrategy(objective: CampaignStepObjective): string {
  if (objective === "introduction" || objective === "meeting_request")
    return "source_backed_value";
  if (objective === "follow_up") return "truthful_follow_up";
  if (objective === "final_follow_up") return "respectful_close";
  return "source_backed_new_angle";
}

function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

function dateTime(value: string | null): string {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function timeLabel(minutes: number): string {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function StatePill({ state }: { state: string }) {
  const attention = [
    "blocked",
    "needs_attention",
    "unknown_delivery_state",
  ].includes(state);
  const positive = ["active", "sent", "completed", "simulated"].includes(state);
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${
        attention
          ? "bg-amber-100 text-amber-900"
          : positive
            ? "bg-teal-100 text-teal-900"
            : "bg-slate-100 text-slate-700"
      }`}
    >
      {humanise(state)}
    </span>
  );
}

function Notice({
  error,
  notice,
}: {
  error: string | null;
  notice?: string | null;
}) {
  return (
    <>
      {error ? (
        <p
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="rounded-2xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-950"
        >
          {notice}
        </p>
      ) : null}
    </>
  );
}

export function CampaignListWorkspace() {
  const [result, setResult] = useState<CampaignListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<CampaignListResponse>("/api/v1/engage/campaigns", {
      signal: controller.signal,
    })
      .then(setResult)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(errorMessage(reason, "Campaigns could not be loaded."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  return (
    <section aria-labelledby="campaigns-title">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Engage · Sell
          </p>
          <h1
            id="campaigns-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Campaigns
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Run small, explicit sequences for canonical Contacts. Every message
            remains source-backed and every recipient keeps an inspectable
            status.
          </p>
        </div>
        {result?.canCreate !== false ? (
          <Link href="/campaigns/new" className="primary-button">
            Create campaign
          </Link>
        ) : null}
      </header>

      <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <strong>Private-beta sending:</strong> campaign execution uses the
        sender-bound mock mailbox in this release. No production mailbox
        provider is enabled.
      </div>
      <Notice error={error} />
      {loading ? (
        <p role="status" className="text-sm text-slate-600">
          Loading campaigns…
        </p>
      ) : null}
      {!loading && result?.items.length === 0 ? (
        <div className="form-card text-center">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            First campaign
          </p>
          <h2 className="mt-3 text-2xl font-semibold">
            Start with a small, exact audience
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-600">
            Choose up to 50 existing Contacts, review every eligibility
            decision, and use one to four ordered steps. CSV upload and
            automatic audience expansion are not supported.
          </p>
          <Link href="/campaigns/new" className="primary-button mt-6">
            Create campaign
          </Link>
        </div>
      ) : null}
      {result?.items.length ? (
        <div className="space-y-3">
          {result.items.map((campaign) => (
            <Link
              key={campaign.id}
              href={`/campaigns/${campaign.id}`}
              className="block rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-slate-950">
                      {campaign.name}
                    </h2>
                    <StatePill state={campaign.state} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">
                    {campaign.purpose}
                  </p>
                  <p className="mt-3 text-xs font-semibold text-slate-500">
                    {campaign.approvalMode === "review_each_send"
                      ? "Review every send"
                      : "Approved campaign auto-send"}
                  </p>
                </div>
                <dl className="grid grid-cols-3 gap-5 text-center sm:text-right">
                  <div>
                    <dt className="text-xs text-slate-500">Audience</dt>
                    <dd className="mt-1 font-bold">{campaign.audienceCount}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Eligible</dt>
                    <dd className="mt-1 font-bold text-teal-800">
                      {campaign.eligibleCount}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Blocked</dt>
                    <dd className="mt-1 font-bold text-amber-800">
                      {campaign.blockedCount}
                    </dd>
                  </div>
                </dl>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function CampaignBuilder() {
  const router = useRouter();
  const [eventContext, setEventContext] = useState<{
    eventId: string;
    eventStage: "pre_event" | "post_event";
  } | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [policy, setPolicy] = useState<OutreachPolicy | null>(null);
  const [name, setName] = useState("Australian Multi-Site CIO Outreach");
  const [purpose, setPurpose] = useState(
    "Book respectful introductory meetings",
  );
  const [approvalMode, setApprovalMode] =
    useState<CampaignApprovalMode>("review_each_send");
  const [selected, setSelected] = useState<string[]>([]);
  const [steps, setSteps] = useState<StepDraft[]>(defaultSteps);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const parameters = new URLSearchParams(window.location.search);
      const eventId = parameters.get("eventId");
      const eventStage = parameters.get("eventStage");
      const contactIds = (parameters.get("contactIds") ?? "")
        .split(",")
        .filter(Boolean);
      if (
        eventId &&
        (eventStage === "pre_event" || eventStage === "post_event")
      ) {
        setEventContext({ eventId, eventStage });
        setSelected([...new Set(contactIds)]);
        setName(
          eventStage === "pre_event"
            ? "Event meeting requests"
            : "Event follow-up",
        );
        setPurpose(
          eventStage === "pre_event"
            ? "Arrange relevant meetings before the Event"
            : "Follow up truthfully after the Event",
        );
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<EntityPage<Contact>>("/api/v1/contacts?page=1&pageSize=50", {
        signal: controller.signal,
      }),
      apiRequest<OutreachPolicy>("/api/v1/engage/policy", {
        signal: controller.signal,
      }),
    ])
      .then(([contactPage, currentPolicy]) => {
        setContacts(contactPage.items);
        setPolicy(currentPolicy);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(errorMessage(reason, "Campaign setup could not be loaded."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const cumulativeDays = useMemo(() => {
    return steps.map((_, index) =>
      steps
        .slice(0, index + 1)
        .reduce((total, step) => total + step.delayDays, 0),
    );
  }, [steps]);
  const visibleContacts = eventContext
    ? contacts.filter((contact) => selected.includes(contact.id))
    : contacts;

  function updateStep(index: number, update: Partial<StepDraft>) {
    setSteps((current) =>
      current.map((step, stepIndex) =>
        stepIndex === index ? { ...step, ...update } : step,
      ),
    );
  }

  function removeStep(index: number) {
    setSteps((current) =>
      current.filter((_, stepIndex) => stepIndex !== index),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!selected.length) {
      setError("Select at least one canonical Contact.");
      return;
    }
    if (!policy?.configured || !policy.outboundEnabled) {
      setError(
        "An administrator must configure and enable the Engage sending policy first.",
      );
      return;
    }
    setBusy(true);
    try {
      const campaign = await apiRequest<Campaign>("/api/v1/engage/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name,
          purpose,
          approvalMode,
          sourceType: eventContext ? "event_attendees" : "manual_contacts",
          eventId: eventContext?.eventId ?? null,
          eventStage: eventContext?.eventStage ?? null,
          senderTimezone: "Australia/Sydney",
          sendDays: [1, 2, 3, 4, 5],
          sendWindowStartMinutes: 510,
          sendWindowEndMinutes: 1020,
          stopOnActiveOpportunity: true,
          contactIds: selected,
          steps: steps.map((step) => ({
            delayDays: step.delayDays,
            objective: step.objective,
            contentStrategy: contentStrategy(step.objective),
            enabled: true,
          })),
        }),
      });
      router.push(`/campaigns/${campaign.id}`);
    } catch (reason: unknown) {
      setError(
        errorMessage(reason, "The campaign draft could not be created."),
      );
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="campaign-builder-title">
      <Link
        href="/campaigns"
        className="text-sm font-bold text-teal-800 hover:text-teal-950"
      >
        ← Campaigns
      </Link>
      <div className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          Create campaign
        </p>
        <h1
          id="campaign-builder-title"
          className="mt-3 text-4xl font-semibold tracking-tight text-slate-950"
        >
          A clear sequence, not an automation maze
        </h1>
        <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
          Choose existing Contacts and one to four ordered steps. RevenueOS
          evaluates every recipient before launch and again before every send.
        </p>
        {eventContext ? (
          <p className="mt-4 rounded-2xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-950">
            Event audience · {humanise(eventContext.eventStage)}. Only canonical
            Contacts linked to the Event are accepted, and normal Engage policy
            checks still apply.
          </p>
        ) : null}
      </div>
      <Notice error={error} />
      {loading ? (
        <p role="status" className="mt-6 text-sm text-slate-600">
          Loading approved context and Contacts…
        </p>
      ) : null}
      {!loading ? (
        <form onSubmit={submit} className="mt-7 space-y-6">
          <fieldset className="form-card">
            <legend className="form-legend">1. Campaign</legend>
            <div className="mt-5 grid gap-5">
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Name
                <input
                  className="form-control"
                  value={name}
                  maxLength={160}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </label>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Purpose
                <textarea
                  className="min-h-24 rounded-xl border border-slate-300 p-4 text-sm outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
                  value={purpose}
                  maxLength={300}
                  onChange={(event) => setPurpose(event.target.value)}
                  required
                />
              </label>
              <div className="rounded-2xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                  Approved offering
                </p>
                <p className="mt-2 font-semibold text-slate-950">
                  {policy?.offeringName ?? "Not configured"}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {policy?.valueProposition ??
                    "Configure approved seller context in Engage settings."}
                </p>
              </div>
            </div>
          </fieldset>

          <fieldset className="form-card">
            <legend className="form-legend">2. Audience</legend>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Select up to 50 canonical Contacts. Email addresses cannot be
              pasted or uploaded here.
            </p>
            <div className="mt-5 max-h-80 space-y-2 overflow-y-auto rounded-2xl border border-slate-200 p-2">
              {visibleContacts.length ? (
                visibleContacts.map((contact) => {
                  const checked = selected.includes(contact.id);
                  return (
                    <label
                      key={contact.id}
                      className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl p-3 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!checked && selected.length >= 50}
                        onChange={() =>
                          setSelected((current) =>
                            checked
                              ? current.filter((id) => id !== contact.id)
                              : [...current, contact.id],
                          )
                        }
                        className="size-4 accent-teal-700"
                      />
                      <span className="min-w-0">
                        <span className="block font-semibold text-slate-950">
                          {contact.firstName} {contact.lastName}
                        </span>
                        <span className="block truncate text-sm text-slate-500">
                          {contact.jobTitle ?? "Role not recorded"} ·{" "}
                          {contact.email ?? "No business email"}
                        </span>
                      </span>
                    </label>
                  );
                })
              ) : (
                <p className="p-4 text-sm text-slate-600">
                  Create or promote a Contact before building a campaign.
                </p>
              )}
            </div>
            <p className="mt-3 text-sm font-bold text-teal-800">
              {selected.length} of 50 Contacts selected
            </p>
          </fieldset>

          <fieldset className="form-card">
            <legend className="form-legend">3. Sequence</legend>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Ordered follow-ups are scheduled only after the prior step
              succeeds. There is no branching or overdue backlog burst.
            </p>
            <ol className="mt-5 space-y-3">
              {steps.map((step, index) => (
                <li
                  key={step.key}
                  className="grid gap-3 rounded-2xl border border-slate-200 p-4 sm:grid-cols-[5rem_minmax(0,1fr)_8rem_auto] sm:items-end"
                >
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                      Step {index + 1}
                    </p>
                    <p className="mt-1 font-semibold">
                      Day {cumulativeDays[index]}
                    </p>
                  </div>
                  <label className="grid gap-1 text-xs font-bold text-slate-600">
                    Objective
                    <select
                      className="form-control"
                      value={step.objective}
                      onChange={(event) =>
                        updateStep(index, {
                          objective: event.target
                            .value as CampaignStepObjective,
                        })
                      }
                    >
                      {objectiveOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-xs font-bold text-slate-600">
                    {index === 0 ? "Starts" : "Wait days"}
                    <input
                      className="form-control"
                      type="number"
                      min={index === 0 ? 0 : 1}
                      max={30}
                      disabled={index === 0}
                      value={step.delayDays}
                      onChange={(event) =>
                        updateStep(index, {
                          delayDays: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                  {steps.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => removeStep(index)}
                      className="secondary-button"
                    >
                      Remove
                    </button>
                  ) : null}
                </li>
              ))}
            </ol>
            {steps.length < 4 ? (
              <button
                type="button"
                className="secondary-button mt-4"
                onClick={() =>
                  setSteps((current) => [
                    ...current,
                    {
                      key: `step-${crypto.randomUUID()}`,
                      delayDays: 4,
                      objective: "follow_up",
                    },
                  ])
                }
              >
                Add step
              </button>
            ) : null}
          </fieldset>

          <fieldset className="form-card">
            <legend className="form-legend">4. Approval and safeguards</legend>
            <div className="mt-5 grid gap-3">
              <label
                className={`rounded-2xl border p-4 ${approvalMode === "review_each_send" ? "border-teal-500 bg-teal-50" : "border-slate-200"}`}
              >
                <span className="flex gap-3">
                  <input
                    type="radio"
                    name="approval-mode"
                    value="review_each_send"
                    checked={approvalMode === "review_each_send"}
                    onChange={() => setApprovalMode("review_each_send")}
                    className="accent-teal-700"
                  />
                  <span>
                    <strong className="block">Review each send</strong>
                    <span className="mt-1 block text-sm leading-6 text-slate-600">
                      A personalised draft waits for the sender to inspect,
                      approve and confirm the exact send preview.
                    </span>
                  </span>
                </span>
              </label>
              <label
                className={`rounded-2xl border p-4 ${approvalMode === "approved_campaign_auto_send" ? "border-amber-500 bg-amber-50" : "border-slate-200"}`}
              >
                <span className="flex gap-3">
                  <input
                    type="radio"
                    name="approval-mode"
                    value="approved_campaign_auto_send"
                    checked={approvalMode === "approved_campaign_auto_send"}
                    disabled={!policy?.campaignAutoSendAllowed}
                    onChange={() =>
                      setApprovalMode("approved_campaign_auto_send")
                    }
                    className="accent-amber-700"
                  />
                  <span>
                    <strong className="block">
                      Approved campaign auto-send
                    </strong>
                    <span className="mt-1 block text-sm leading-6 text-slate-600">
                      Future source-backed drafts may be submitted automatically
                      only under explicit organisation policy and a second
                      launch confirmation. Every send is still revalidated.
                    </span>
                    {!policy?.campaignAutoSendAllowed ? (
                      <span className="mt-2 block text-xs font-bold text-amber-900">
                        Not enabled by your organisation administrator.
                      </span>
                    ) : null}
                  </span>
                </span>
              </label>
            </div>
            <ul className="mt-5 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
              <li>✓ Weekdays, 08:30–17:00 Australia/Sydney</li>
              <li>✓ Stop when an active Opportunity exists</li>
              <li>✓ Suppression and Contact changes checked before send</li>
              <li>✓ Global cooldown and daily quotas apply</li>
            </ul>
          </fieldset>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Link href="/campaigns" className="secondary-button">
              Cancel
            </Link>
            <button
              type="submit"
              className="primary-button"
              disabled={busy || !selected.length || !steps.length}
            >
              {busy ? "Reviewing audience…" : "Review audience"}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

export function CampaignShortcut() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<EngageAvailability>("/api/v1/engage/availability", {
      signal: controller.signal,
    })
      .then((availability) => setEnabled(availability.enabled))
      .catch(() => setEnabled(false));
    return () => controller.abort();
  }, []);
  if (!enabled) return null;
  return (
    <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-teal-200 bg-teal-50 p-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-teal-950">
        <strong>Planning bounded outreach?</strong> Build a Campaign from
        existing Contacts and review eligibility before launch.
      </p>
      <Link href="/campaigns" className="secondary-button shrink-0">
        Open Campaigns
      </Link>
    </div>
  );
}

export function CampaignDetail({ campaignId }: { campaignId: string }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [enrollments, setEnrollments] = useState<CampaignEnrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [autoConfirmed, setAutoConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const detail = await apiRequest<Campaign>(
      `/api/v1/engage/campaigns/${campaignId}`,
    );
    setCampaign(detail);
    if (
      ["active", "paused", "completed", "stopped", "needs_attention"].includes(
        detail.state,
      )
    ) {
      const recipients = await apiRequest<CampaignEnrollmentListResponse>(
        `/api/v1/engage/campaigns/${campaignId}/enrollments`,
      );
      setEnrollments(recipients.items);
    } else {
      setEnrollments([]);
    }
  }, [campaignId]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Campaign>(`/api/v1/engage/campaigns/${campaignId}`, {
      signal: controller.signal,
    })
      .then(async (detail) => {
        setCampaign(detail);
        if (
          [
            "active",
            "paused",
            "completed",
            "stopped",
            "needs_attention",
          ].includes(detail.state)
        ) {
          const recipients = await apiRequest<CampaignEnrollmentListResponse>(
            `/api/v1/engage/campaigns/${campaignId}/enrollments`,
            { signal: controller.signal },
          );
          setEnrollments(recipients.items);
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(errorMessage(reason, "The campaign could not be loaded."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [campaignId]);

  async function transition(action: "launch" | "pause" | "resume" | "stop") {
    if (!campaign) return;
    setBusy(action);
    setError(null);
    setNotice(null);
    try {
      const body =
        action === "launch"
          ? {
              expectedVersion: campaign.version,
              confirmed: true,
              autoSendConfirmed: autoConfirmed,
            }
          : { confirmed: true };
      const updated = await apiRequest<Campaign>(
        `/api/v1/engage/campaigns/${campaign.id}/${action}`,
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      );
      setCampaign(updated);
      setNotice(
        action === "launch"
          ? "Campaign launched. Recipient work will be prepared inside the configured send window."
          : `Campaign ${action === "resume" ? "resumed" : `${action}d`}.`,
      );
      await load();
    } catch (reason: unknown) {
      setError(errorMessage(reason, `The campaign could not be ${action}ed.`));
    } finally {
      setBusy(null);
    }
  }

  if (loading)
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading campaign…
      </p>
    );
  if (!campaign) return <Notice error={error ?? "Campaign not found."} />;

  const cumulative = campaign.steps.reduce<number[]>((days, step) => {
    days.push((days.at(-1) ?? 0) + step.delayDays);
    return days;
  }, []);

  return (
    <section aria-labelledby="campaign-title">
      <Link
        href="/campaigns"
        className="text-sm font-bold text-teal-800 hover:text-teal-950"
      >
        ← Campaigns
      </Link>
      <header className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1
              id="campaign-title"
              className="text-4xl font-semibold tracking-tight text-slate-950"
            >
              {campaign.name}
            </h1>
            <StatePill state={campaign.state} />
          </div>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            {campaign.purpose}
          </p>
          <p className="mt-3 text-sm font-semibold text-slate-500">
            {campaign.approvalMode === "review_each_send"
              ? "Every message requires sender review"
              : "Approved campaign auto-send"}{" "}
            ·{" "}
            {campaign.simulationOnly ? "Mock email only" : "Production mailbox"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {campaign.state === "active" ? (
            <button
              className="secondary-button"
              disabled={busy !== null}
              onClick={() => transition("pause")}
            >
              Pause
            </button>
          ) : null}
          {campaign.state === "paused" ? (
            <button
              className="primary-button"
              disabled={busy !== null}
              onClick={() => transition("resume")}
            >
              Resume
            </button>
          ) : null}
          {["active", "paused", "needs_attention"].includes(campaign.state) ? (
            <button
              className="secondary-button border-red-300 text-red-800"
              disabled={busy !== null}
              onClick={() => transition("stop")}
            >
              Stop campaign
            </button>
          ) : null}
        </div>
      </header>
      <div className="mt-5 space-y-3">
        <Notice error={error} notice={notice} />
      </div>
      {campaign.needsAttentionReason ? (
        <p className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>Needs attention:</strong>{" "}
          {humanise(campaign.needsAttentionReason)}
        </p>
      ) : null}

      <div className="mt-7 grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-5">
          <section className="form-card" aria-labelledby="sequence-title">
            <div className="flex items-center justify-between">
              <h2 id="sequence-title" className="text-xl font-semibold">
                Sequence
              </h2>
              <span className="text-xs font-bold text-slate-500">
                {campaign.steps.length} of 4 steps
              </span>
            </div>
            <ol className="mt-5 space-y-3">
              {campaign.steps.map((step, index) => (
                <li
                  key={step.id}
                  className="flex items-center gap-4 rounded-2xl bg-slate-50 p-4"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-slate-950 text-sm font-bold text-white">
                    {index + 1}
                  </span>
                  <div>
                    <p className="font-semibold">{humanise(step.objective)}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Day {cumulative[index]}
                      {index
                        ? ` · waits ${step.delayDays} day${step.delayDays === 1 ? "" : "s"} after successful prior send`
                        : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section
            className="form-card min-w-0"
            aria-labelledby="audience-title"
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="audience-title" className="text-xl font-semibold">
                  Audience review
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Exact launch snapshot from canonical Contacts.
                </p>
              </div>
              <p className="text-sm font-bold">
                <span className="text-teal-800">
                  {campaign.eligibleCount} eligible
                </span>{" "}
                ·{" "}
                <span className="text-amber-800">
                  {campaign.blockedCount} blocked
                </span>
              </p>
            </div>
            <div className="mt-5 space-y-3 md:hidden">
              {campaign.audience.map((item) => (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-200 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold">{item.recipientName}</h3>
                      <p className="break-all text-sm text-slate-500">
                        {item.recipientEmail ?? "No business email"}
                      </p>
                    </div>
                    <StatePill state={item.eligible ? "eligible" : "blocked"} />
                  </div>
                  <dl className="mt-4 space-y-3 text-sm">
                    <div>
                      <dt className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">
                        Address trust
                      </dt>
                      <dd className="mt-1">{humanise(item.recipientTrust)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">
                        Eligibility reason
                      </dt>
                      <dd className="mt-1 leading-6 text-slate-600">
                        {item.eligibilityReason}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
            <div className="mt-5 hidden overflow-x-auto md:block">
              <table className="w-full table-fixed text-left text-sm">
                <colgroup>
                  <col className="w-[34%]" />
                  <col className="w-[18%]" />
                  <col className="w-[18%]" />
                  <col className="w-[30%]" />
                </colgroup>
                <thead className="border-b border-slate-200 text-xs uppercase tracking-[0.1em] text-slate-500">
                  <tr>
                    <th className="pb-3 pr-4">Contact</th>
                    <th className="pb-3 pr-4">Trust</th>
                    <th className="pb-3 pr-4">Decision</th>
                    <th className="pb-3">Why</th>
                  </tr>
                </thead>
                <tbody>
                  {campaign.audience.map((item) => (
                    <tr
                      key={item.id}
                      className="border-b border-slate-100 align-top"
                    >
                      <td className="py-4 pr-4 font-semibold">
                        {item.recipientName}
                        <span className="block break-all font-normal text-slate-500">
                          {item.recipientEmail ?? "No business email"}
                        </span>
                      </td>
                      <td className="break-words py-4 pr-4">
                        {humanise(item.recipientTrust)}
                      </td>
                      <td className="py-4 pr-4">
                        <StatePill
                          state={item.eligible ? "eligible" : "blocked"}
                        />
                      </td>
                      <td className="py-4 text-slate-600">
                        {item.eligibilityReason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {enrollments.length ? (
            <section className="form-card" aria-labelledby="recipients-title">
              <h2 id="recipients-title" className="text-xl font-semibold">
                Recipients
              </h2>
              <div className="mt-5 space-y-2">
                {enrollments.map((item) => (
                  <Link
                    key={item.id}
                    href={`/campaigns/${campaign.id}/enrollments/${item.id}`}
                    className="flex min-h-16 items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4 hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600"
                  >
                    <div>
                      <p className="font-semibold">{item.recipientName}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Step {item.currentStepOrder} ·{" "}
                        {dateTime(item.nextScheduledAt)}
                      </p>
                    </div>
                    <StatePill state={item.state} />
                  </Link>
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          <section className="rounded-3xl bg-slate-950 p-6 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-300">
              Operational status
            </p>
            <dl className="mt-5 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-slate-400">Recipients</dt>
                <dd className="mt-1 text-2xl font-semibold">
                  {campaign.metrics.recipients || campaign.eligibleCount}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Messages sent</dt>
                <dd className="mt-1 text-2xl font-semibold">
                  {campaign.metrics.messagesSent}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Ready to review</dt>
                <dd className="mt-1 text-2xl font-semibold">
                  {campaign.metrics.messagesReadyForReview}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Needs attention</dt>
                <dd className="mt-1 text-2xl font-semibold">
                  {campaign.metrics.needsAttention}
                </dd>
              </div>
            </dl>
            <p className="mt-5 border-t border-slate-700 pt-4 text-xs leading-5 text-slate-400">
              No open or click tracking. Replies and meetings shown here are
              seller-reported.
            </p>
          </section>
          <section className="rounded-3xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold">Sending controls</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div>
                <dt className="text-slate-500">Window</dt>
                <dd className="font-semibold">
                  {timeLabel(campaign.sendWindowStartMinutes)}–
                  {timeLabel(campaign.sendWindowEndMinutes)}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Timezone</dt>
                <dd className="font-semibold">{campaign.senderTimezone}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Active Opportunity</dt>
                <dd className="font-semibold">
                  {campaign.stopOnActiveOpportunity
                    ? "Stops recipient"
                    : "Not enabled"}
                </dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>

      {campaign.canLaunch ? (
        <section
          className="mt-6 rounded-3xl border-2 border-teal-700 bg-white p-6 sm:p-8"
          aria-labelledby="launch-title"
        >
          <h2 id="launch-title" className="text-2xl font-semibold">
            Launch review
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Launch freezes the exact sequence, audience decisions, approval mode
            and organisation policy version. Blocked Contacts will not be
            enrolled.
          </p>
          {campaign.approvalMode === "approved_campaign_auto_send" ? (
            <p className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm font-semibold text-amber-950">
              Future personalised steps may be submitted automatically after
              current-policy, suppression, quota, source and recipient checks.
              This is not blanket approval and stops on uncertainty.
            </p>
          ) : null}
          <div className="mt-5 space-y-3">
            <label className="flex gap-3 text-sm font-semibold">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                className="mt-0.5 size-4 accent-teal-700"
              />
              I reviewed the exact audience and ordered sequence and want to
              launch this campaign.
            </label>
            {campaign.approvalMode === "approved_campaign_auto_send" ? (
              <label className="flex gap-3 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={autoConfirmed}
                  onChange={(event) => setAutoConfirmed(event.target.checked)}
                  className="mt-0.5 size-4 accent-amber-700"
                />
                I explicitly authorise future validated steps in this campaign
                to use bounded auto-send.
              </label>
            ) : null}
          </div>
          <button
            className="primary-button mt-6"
            disabled={
              !confirmed ||
              (campaign.approvalMode === "approved_campaign_auto_send" &&
                !autoConfirmed) ||
              busy !== null
            }
            onClick={() => transition("launch")}
          >
            {busy === "launch"
              ? "Launching…"
              : `Launch to ${campaign.eligibleCount} eligible Contact${campaign.eligibleCount === 1 ? "" : "s"}`}
          </button>
        </section>
      ) : null}
    </section>
  );
}

function OutreachReview({
  outreach,
  onChanged,
}: {
  outreach: OutreachMessage;
  onChanged: () => Promise<void>;
}) {
  const [current, setCurrent] = useState(outreach);
  const [preview, setPreview] = useState<ExecutionPreview | null>(null);
  const [execution, setExecution] = useState<ActionExecution | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function approve() {
    setBusy("approve");
    setError(null);
    try {
      const approved = await apiRequest<OutreachMessage>(
        `/api/v1/engage/outreach/${current.id}/approve`,
        {
          method: "POST",
          body: JSON.stringify({ expectedVersion: current.currentVersion }),
        },
      );
      setCurrent(approved);
      setNotice("Exact message approved. Nothing has been sent yet.");
    } catch (reason: unknown) {
      setError(errorMessage(reason, "The message could not be approved."));
    } finally {
      setBusy(null);
    }
  }

  async function preparePreview() {
    setBusy("preview");
    setError(null);
    try {
      const options = await apiRequest<ActionExecutionOptionListResponse>(
        `/api/v1/actions/${current.actionId}/execution-options`,
      );
      const option = options.items[0];
      if (!option) throw new Error("No sender-bound mailbox is available.");
      setPreview(
        await apiRequest<ExecutionPreview>(
          `/api/v1/engage/outreach/${current.id}/execution-preview`,
          {
            method: "POST",
            body: JSON.stringify({ connectionId: option.connectionId }),
          },
        ),
      );
    } catch (reason: unknown) {
      setError(
        errorMessage(reason, "The exact send preview could not be prepared."),
      );
    } finally {
      setBusy(null);
    }
  }

  async function send() {
    if (!preview) return;
    setBusy("send");
    setError(null);
    try {
      const result = await apiRequest<ActionExecution>(
        `/api/v1/engage/outreach/${current.id}/send`,
        {
          method: "POST",
          body: JSON.stringify({
            previewId: preview.id,
            connectionId: preview.connectionId,
            confirmed: true,
          }),
        },
      );
      setExecution(result);
      setNotice(result.safeMessage);
      await onChanged();
    } catch (reason: unknown) {
      setError(
        errorMessage(reason, "The reviewed message could not be submitted."),
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="form-card" aria-labelledby="message-review-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Ready for review
          </p>
          <h2 id="message-review-title" className="mt-2 text-xl font-semibold">
            Exact personalised message
          </h2>
        </div>
        <StatePill state={execution?.executionStatus ?? current.state} />
      </div>
      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <p className="text-xs text-slate-500">
          To: {current.version.recipientName} &lt;
          {current.version.recipientEmail}&gt;
        </p>
        <p className="mt-3 font-semibold">{current.version.subject}</p>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
          {current.version.body}
        </p>
      </div>
      <div className="mt-5">
        <h3 className="text-sm font-bold">Why this message?</h3>
        <ul className="mt-2 space-y-2">
          {current.version.sources.map((source) => (
            <li
              key={source.id}
              className="rounded-xl bg-teal-50 p-3 text-sm text-teal-950"
            >
              <strong>{source.label}</strong>
              <span className="mt-1 block text-xs text-teal-800">
                {humanise(source.trustState)} source
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-5 space-y-3">
        <Notice error={error} notice={notice} />
      </div>
      {preview ? (
        <div className="mt-5 rounded-2xl border-2 border-slate-950 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
            Exact send preview ·{" "}
            {preview.simulationOnly ? "Simulation only" : "Production"}
          </p>
          {preview.content.kind === "email" ? (
            <>
              <p className="mt-3 text-sm">
                From: {preview.content.senderName} &lt;
                {preview.content.senderEmail}&gt;
              </p>
              <p className="mt-1 text-sm">
                To: {preview.content.recipientName} &lt;
                {preview.content.recipient}&gt;
              </p>
              <p className="mt-3 font-semibold">{preview.content.subject}</p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
                {preview.content.body}
              </p>
            </>
          ) : null}
          <button
            className="primary-button mt-5"
            disabled={busy !== null || execution !== null}
            onClick={send}
          >
            {busy === "send" ? "Submitting…" : preview.confirmationLabel}
          </button>
        </div>
      ) : null}
      {!preview ? (
        <div className="mt-5 flex flex-wrap gap-3">
          {current.state === "draft" ? (
            <button
              className="primary-button"
              disabled={busy !== null}
              onClick={approve}
            >
              {busy === "approve" ? "Approving…" : "Approve exact message"}
            </button>
          ) : (
            <button
              className="primary-button"
              disabled={busy !== null}
              onClick={preparePreview}
            >
              {busy === "preview" ? "Preparing…" : "Review exact send preview"}
            </button>
          )}
        </div>
      ) : null}
    </section>
  );
}

export function CampaignEnrollmentDetail({
  campaignId,
  enrollmentId,
}: {
  campaignId: string;
  enrollmentId: string;
}) {
  const [enrollment, setEnrollment] = useState<CampaignEnrollment | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setEnrollment(
      await apiRequest<CampaignEnrollment>(
        `/api/v1/engage/enrollments/${enrollmentId}`,
      ),
    );
  }, [enrollmentId]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<CampaignEnrollment>(
      `/api/v1/engage/enrollments/${enrollmentId}`,
      {
        signal: controller.signal,
      },
    )
      .then(setEnrollment)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(errorMessage(reason, "The recipient could not be loaded."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [enrollmentId]);

  async function mutate(path: "stop" | "outcome", outcome?: CampaignOutcome) {
    setBusy(path);
    setError(null);
    try {
      const updated = await apiRequest<CampaignEnrollment>(
        `/api/v1/engage/enrollments/${enrollmentId}/${path}`,
        {
          method: "POST",
          body: JSON.stringify(
            path === "stop" ? { confirmed: true } : { outcome },
          ),
        },
      );
      setEnrollment(updated);
    } catch (reason: unknown) {
      setError(errorMessage(reason, "The recipient could not be updated."));
    } finally {
      setBusy(null);
    }
  }

  if (loading)
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading recipient…
      </p>
    );
  if (!enrollment) return <Notice error={error ?? "Recipient not found."} />;
  const terminal = ["stopped", "completed", "blocked"].includes(
    enrollment.state,
  );

  return (
    <section aria-labelledby="recipient-title">
      <Link
        href={`/campaigns/${campaignId}`}
        className="text-sm font-bold text-teal-800 hover:text-teal-950"
      >
        ← Campaign
      </Link>
      <header className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Campaign recipient
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1
              id="recipient-title"
              className="text-4xl font-semibold tracking-tight"
            >
              {enrollment.recipientName}
            </h1>
            <StatePill state={enrollment.state} />
          </div>
          <p className="mt-2 text-sm text-slate-600">
            {enrollment.recipientEmail} · {humanise(enrollment.recipientTrust)}
          </p>
        </div>
        {!terminal ? (
          <button
            className="secondary-button border-red-300 text-red-800"
            disabled={busy !== null}
            onClick={() => mutate("stop")}
          >
            Stop this recipient
          </button>
        ) : null}
      </header>
      <div className="mt-5">
        <Notice error={error} />
      </div>
      {enrollment.stopReason ? (
        <p className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>Stopped or blocked:</strong> {humanise(enrollment.stopReason)}
        </p>
      ) : null}
      <div className="mt-7 grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-5">
          {enrollment.currentOutreach ? (
            <OutreachReview
              key={`${enrollment.currentOutreach.id}-${enrollment.currentOutreach.currentVersion}`}
              outreach={enrollment.currentOutreach}
              onChanged={load}
            />
          ) : (
            <div className="form-card">
              <h2 className="text-xl font-semibold">Message preparation</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {enrollment.state === "active"
                  ? `Step ${enrollment.currentStepOrder} is scheduled for ${dateTime(enrollment.nextScheduledAt)}. A source-backed draft is prepared inside the campaign preparation window.`
                  : "No message is waiting for review."}
              </p>
            </div>
          )}
          <section className="form-card" aria-labelledby="timeline-title">
            <h2 id="timeline-title" className="text-xl font-semibold">
              Sequence timeline
            </h2>
            <ol className="mt-5 space-y-4">
              {enrollment.steps.map((step) => (
                <li key={step.id} className="flex gap-4">
                  <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold">
                    {step.stepOrder}
                  </span>
                  <div className="min-w-0 flex-1 border-b border-slate-100 pb-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold">
                        {humanise(step.objective)}
                      </p>
                      <StatePill state={step.state} />
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {step.sentAt
                        ? `Sent ${dateTime(step.sentAt)}`
                        : `Scheduled ${dateTime(step.scheduledAt)}`}
                    </p>
                    {step.safeStatusCode ? (
                      <p className="mt-2 text-xs font-semibold text-amber-800">
                        {humanise(step.safeStatusCode)}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
        <aside className="space-y-5">
          <section className="rounded-3xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold">Seller-reported outcome</h2>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              RevenueOS does not read the mailbox or infer replies in this
              release. Reporting an outcome stops future steps and does not
              create customer Evidence.
            </p>
            {enrollment.outcome ? (
              <p className="mt-4 text-sm font-semibold">
                Seller reported · {humanise(enrollment.outcome)}
              </p>
            ) : !terminal ? (
              <div className="mt-4 grid gap-2">
                <button
                  className="secondary-button"
                  disabled={busy !== null}
                  onClick={() => mutate("outcome", "replied")}
                >
                  Report replied
                </button>
                <button
                  className="secondary-button"
                  disabled={busy !== null}
                  onClick={() => mutate("outcome", "meeting_booked")}
                >
                  Report meeting booked
                </button>
                <button
                  className="secondary-button"
                  disabled={busy !== null}
                  onClick={() => mutate("outcome", "not_interested")}
                >
                  Report not interested
                </button>
              </div>
            ) : null}
          </section>
          <section className="rounded-3xl bg-slate-950 p-6 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-300">
              Next work
            </p>
            <p className="mt-3 text-lg font-semibold">
              {dateTime(enrollment.nextScheduledAt)}
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              Schedule advances only after confirmed success. Pauses and outages
              do not release a burst of overdue sends.
            </p>
          </section>
        </aside>
      </div>
    </section>
  );
}
