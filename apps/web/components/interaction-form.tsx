"use client";

import type {
  CallDirection,
  Company,
  Contact,
  EntityPage,
  Interaction,
  InteractionType,
  Opportunity,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { interactionTypes } from "@/lib/interactions";

export function InteractionForm() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [interactionType, setInteractionType] =
    useState<InteractionType>("manual_interaction");
  const [companyId, setCompanyId] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [contactId, setContactId] = useState("");
  const [callDirection, setCallDirection] = useState<CallDirection>("unknown");
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [scheduledEndAt, setScheduledEndAt] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Opportunity>>(
        "/api/v1/opportunities?pageSize=100",
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Contact>>("/api/v1/contacts?pageSize=100", {
        signal: controller.signal,
      }),
    ])
      .then(([companyPage, opportunityPage, contactPage]) => {
        setCompanies(companyPage.items);
        setOpportunities(opportunityPage.items);
        setContacts(contactPage.items);
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setLoadError(
          requestError instanceof Error
            ? requestError.message
            : "Interaction options could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const interaction = await apiRequest<Interaction>(
        "/api/v1/interactions",
        {
          method: "POST",
          body: JSON.stringify({
            title: title.trim(),
            interactionType,
            lifecycleStatus: "planned",
            companyId: companyId || null,
            opportunityId: opportunityId || null,
            contactId:
              interactionType === "phone_call" ? contactId || null : null,
            callDirection:
              interactionType === "phone_call" ? callDirection : null,
            scheduledStartAt: scheduledStartAt
              ? new Date(scheduledStartAt).toISOString()
              : null,
            scheduledEndAt: scheduledEndAt
              ? new Date(scheduledEndAt).toISOString()
              : null,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          }),
        },
      );
      router.push(`/interactions/${interaction.id}`);
    } catch (requestError: unknown) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be created.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby="interaction-form-title" className="form-card">
      <div className="max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          Customer activity
        </p>
        <h1
          id="interaction-form-title"
          className="mt-3 text-3xl font-semibold text-slate-950"
        >
          Create interaction
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Add a customer event without recording, transcription or AI
          processing. Meetings can continue to be created from the existing
          Meeting workflow.
        </p>
      </div>

      {loading ? (
        <p role="status" className="mt-6 text-sm text-slate-600">
          Loading interaction options…
        </p>
      ) : null}
      {!loading && loadError ? (
        <p
          role="alert"
          className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-900"
        >
          {loadError}
        </p>
      ) : null}
      {!loading && !loadError ? (
        <form onSubmit={submit} className="mt-8 grid gap-5">
          <label className="grid gap-2 text-sm font-bold text-slate-800">
            Title
            <input
              className="form-control"
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm font-bold text-slate-800">
            Interaction type
            <select
              className="form-control"
              value={interactionType}
              onChange={(event) =>
                setInteractionType(event.target.value as InteractionType)
              }
            >
              {interactionTypes.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Company
              <select
                className="form-control"
                value={companyId}
                onChange={(event) => {
                  const nextCompanyId = event.target.value;
                  setCompanyId(nextCompanyId);
                  if (
                    contactId &&
                    contacts.find((contact) => contact.id === contactId)
                      ?.companyId !== nextCompanyId
                  ) {
                    setContactId("");
                  }
                }}
              >
                <option value="">No company</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Opportunity
              <select
                className="form-control"
                value={opportunityId}
                onChange={(event) => setOpportunityId(event.target.value)}
              >
                <option value="">No opportunity</option>
                {opportunities.map((opportunity) => (
                  <option key={opportunity.id} value={opportunity.id}>
                    {opportunity.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {interactionType === "phone_call" ? (
            <fieldset className="grid gap-5 rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:grid-cols-2">
              <legend className="px-2 text-sm font-bold text-teal-950">
                Phone call
              </legend>
              <p className="sm:col-span-2 text-sm leading-6 text-teal-950">
                Use the phone system you already have. RevenueOS prepares and
                times the interaction; it does not intercept or record a normal
                cellular call.
              </p>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Call direction
                <select
                  className="form-control"
                  value={callDirection}
                  onChange={(event) =>
                    setCallDirection(event.target.value as CallDirection)
                  }
                >
                  <option value="unknown">Unknown</option>
                  <option value="outbound">Outbound</option>
                  <option value="inbound">Inbound</option>
                </select>
              </label>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Contact
                <select
                  className="form-control"
                  value={contactId}
                  onChange={(event) => setContactId(event.target.value)}
                >
                  <option value="">No contact</option>
                  {contacts
                    .filter(
                      (contact) =>
                        !companyId || contact.companyId === companyId,
                    )
                    .map((contact) => (
                      <option key={contact.id} value={contact.id}>
                        {contact.firstName} {contact.lastName}
                        {contact.jobTitle ? ` · ${contact.jobTitle}` : ""}
                      </option>
                    ))}
                </select>
              </label>
            </fieldset>
          ) : null}
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Scheduled start
              <input
                className="form-control"
                type="datetime-local"
                value={scheduledStartAt}
                onChange={(event) => setScheduledStartAt(event.target.value)}
              />
            </label>
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Scheduled end
              <input
                className="form-control"
                type="datetime-local"
                value={scheduledEndAt}
                onChange={(event) => setScheduledEndAt(event.target.value)}
              />
            </label>
          </div>
          {submitError ? (
            <p
              role="alert"
              className="rounded-xl bg-red-50 p-4 text-sm text-red-900"
            >
              {submitError}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              className="primary-button"
              disabled={submitting}
            >
              {submitting ? "Creating…" : "Create interaction"}
            </button>
            <Link className="secondary-button" href="/interactions">
              Cancel
            </Link>
          </div>
        </form>
      ) : null}
    </section>
  );
}
