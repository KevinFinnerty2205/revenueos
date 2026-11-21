"use client";

import type {
  CallDirection,
  Company,
  Contact,
  EntityPage,
  Interaction,
  InteractionType,
  OnlineMeetingPlatform,
  Opportunity,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FormEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { interactionTypes } from "@/lib/interactions";

interface LinkedInteractionContext {
  companyId: string;
  opportunityId: string;
  contactId: string;
  interactionType: InteractionType;
}

type OptionLoadState = "loading" | "ready" | "unavailable";

interface LoadedOptions<T> {
  items: T[];
  exactWarning: boolean;
}

interface OptionRetryRequest {
  source: "company" | "opportunity" | "contact";
  sequence: number;
  linkedId: string;
  contextIdentity: string;
}

function isAbortError(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === "AbortError";
}

function appendUnique<T extends { id: string }>(
  items: T[],
  item: T | null,
): T[] {
  return item && !items.some((candidate) => candidate.id === item.id)
    ? [...items, item]
    : items;
}

async function loadCompanyOptions(
  linkedId: string,
  signal: AbortSignal,
): Promise<LoadedOptions<Company>> {
  const page = await apiRequest<EntityPage<Company>>(
    "/api/v1/companies?pageSize=100",
    { signal },
  );
  let exactWarning = false;
  let items = page.items;
  if (linkedId && !items.some((company) => company.id === linkedId)) {
    try {
      items = appendUnique(
        items,
        await apiRequest<Company>(
          `/api/v1/companies/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
      );
    } catch (reason: unknown) {
      if (signal.aborted || isAbortError(reason)) throw reason;
      exactWarning = true;
    }
  }
  return { items, exactWarning };
}

async function loadContactOptions(
  linkedId: string,
  signal: AbortSignal,
): Promise<LoadedOptions<Contact>> {
  const page = await apiRequest<EntityPage<Contact>>(
    "/api/v1/contacts?pageSize=100",
    { signal },
  );
  let exactWarning = false;
  let items = page.items;
  if (linkedId && !items.some((contact) => contact.id === linkedId)) {
    try {
      items = appendUnique(
        items,
        await apiRequest<Contact>(
          `/api/v1/contacts/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
      );
    } catch (reason: unknown) {
      if (signal.aborted || isAbortError(reason)) throw reason;
      exactWarning = true;
    }
  }
  return { items, exactWarning };
}

async function loadOpportunityOptions(
  linkedId: string,
  signal: AbortSignal,
): Promise<LoadedOptions<Opportunity>> {
  const page = await apiRequest<EntityPage<Opportunity>>(
    "/api/v1/opportunities?pageSize=100",
    { signal },
  );
  let exactWarning = false;
  let items = page.items;
  if (linkedId && !items.some((opportunity) => opportunity.id === linkedId)) {
    try {
      items = appendUnique(
        items,
        await apiRequest<Opportunity>(
          `/api/v1/opportunities/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
      );
    } catch (reason: unknown) {
      if (signal.aborted || isAbortError(reason)) throw reason;
      exactWarning = true;
    }
  }
  return { items, exactWarning };
}

export function InteractionForm({
  conversationOnly = false,
  initialCompanyId = "",
  initialOpportunityId = "",
  initialContactId = "",
  initialInteractionType = "manual_interaction",
}: {
  conversationOnly?: boolean;
  initialCompanyId?: string;
  initialOpportunityId?: string;
  initialContactId?: string;
  initialInteractionType?: InteractionType;
}) {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [companyOptionsState, setCompanyOptionsState] =
    useState<OptionLoadState>("loading");
  const [opportunityOptionsState, setOpportunityOptionsState] =
    useState<OptionLoadState>(conversationOnly ? "ready" : "loading");
  const [contactOptionsState, setContactOptionsState] =
    useState<OptionLoadState>("loading");
  const [companyOptionsWarning, setCompanyOptionsWarning] = useState<
    string | null
  >(null);
  const [opportunityOptionsWarning, setOpportunityOptionsWarning] = useState<
    string | null
  >(null);
  const [contactOptionsWarning, setContactOptionsWarning] = useState<
    string | null
  >(null);
  const [optionRetryRequest, setOptionRetryRequest] =
    useState<OptionRetryRequest | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [interactionType, setInteractionType] = useState<InteractionType>(
    initialInteractionType,
  );
  const [companyId, setCompanyId] = useState(initialCompanyId);
  const [opportunityId, setOpportunityId] = useState(initialOpportunityId);
  const [contactId, setContactId] = useState(initialContactId);
  const [callDirection, setCallDirection] = useState<CallDirection>("unknown");
  const [meetingPlatform, setMeetingPlatform] =
    useState<OnlineMeetingPlatform>("microsoft_teams");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [scheduledEndAt, setScheduledEndAt] = useState("");
  const [pendingLinkedContext, setPendingLinkedContext] =
    useState<LinkedInteractionContext | null>(null);
  const linkedContextIdentity = JSON.stringify([
    conversationOnly,
    initialCompanyId,
    initialOpportunityId,
    initialContactId,
    initialInteractionType,
  ]);
  const contextDirtyRef = useRef(false);
  const linkedContextLoadedRef = useRef(false);
  const optionRetrySequenceRef = useRef(0);
  const activeLinkedContextIdentityRef = useRef(linkedContextIdentity);

  useLayoutEffect(() => {
    activeLinkedContextIdentityRef.current = linkedContextIdentity;
  }, [linkedContextIdentity]);

  useEffect(() => {
    const controller = new AbortController();
    const requestContextIdentity = linkedContextIdentity;
    window.queueMicrotask(() => {
      if (
        controller.signal.aborted ||
        activeLinkedContextIdentityRef.current !== requestContextIdentity
      ) {
        return;
      }
      setLoading(true);
      setCompanyOptionsState("loading");
      setContactOptionsState("loading");
      setOpportunityOptionsState(conversationOnly ? "ready" : "loading");
      setCompanyOptionsWarning(null);
      setContactOptionsWarning(null);
      setOpportunityOptionsWarning(null);
    });

    const companyPageRequest = apiRequest<EntityPage<Company>>(
      "/api/v1/companies?pageSize=100",
      { signal: controller.signal },
    );
    const contactOptionsRequest = loadContactOptions(
      initialContactId,
      controller.signal,
    );
    const opportunityOptionsRequest: Promise<LoadedOptions<Opportunity>> =
      conversationOnly
        ? Promise.resolve({ items: [], exactWarning: false })
        : loadOpportunityOptions(initialOpportunityId, controller.signal);

    void Promise.allSettled([
      companyPageRequest,
      opportunityOptionsRequest,
      contactOptionsRequest,
    ]).then(async ([companyResult, opportunityResult, contactResult]) => {
      if (
        controller.signal.aborted ||
        activeLinkedContextIdentityRef.current !== requestContextIdentity
      ) {
        return;
      }

      let nextCompanies =
        companyResult.status === "fulfilled" ? companyResult.value.items : [];
      const nextOpportunities =
        opportunityResult.status === "fulfilled"
          ? opportunityResult.value.items
          : [];
      const nextContacts =
        contactResult.status === "fulfilled" ? contactResult.value.items : [];
      const selectedContact = nextContacts.find(
        (contact) => contact.id === initialContactId,
      );
      const selectedOpportunity = nextOpportunities.find(
        (opportunity) => opportunity.id === initialOpportunityId,
      );
      const linkedCompanyCandidate =
        initialCompanyId ||
        selectedContact?.companyId ||
        selectedOpportunity?.companyId ||
        "";
      let companyExactWarning = false;
      if (
        companyResult.status === "fulfilled" &&
        linkedCompanyCandidate &&
        !nextCompanies.some((company) => company.id === linkedCompanyCandidate)
      ) {
        try {
          nextCompanies = appendUnique(
            nextCompanies,
            await apiRequest<Company>(
              `/api/v1/companies/${encodeURIComponent(linkedCompanyCandidate)}`,
              { signal: controller.signal },
            ),
          );
        } catch (reason: unknown) {
          if (
            controller.signal.aborted ||
            activeLinkedContextIdentityRef.current !== requestContextIdentity ||
            isAbortError(reason)
          ) {
            return;
          }
          companyExactWarning = true;
        }
      }
      if (
        controller.signal.aborted ||
        activeLinkedContextIdentityRef.current !== requestContextIdentity
      ) {
        return;
      }

      setCompanies(nextCompanies);
      setOpportunities(nextOpportunities);
      setContacts(nextContacts);
      setCompanyOptionsState(
        companyResult.status === "fulfilled" ? "ready" : "unavailable",
      );
      setOpportunityOptionsState(
        opportunityResult.status === "fulfilled" ? "ready" : "unavailable",
      );
      setContactOptionsState(
        contactResult.status === "fulfilled" ? "ready" : "unavailable",
      );
      setCompanyOptionsWarning(
        companyResult.status === "rejected"
          ? "Company options are temporarily unavailable. You can still add this conversation without company context."
          : companyExactWarning
            ? "The linked company could not be loaded. Choose another company or continue without one."
            : null,
      );
      setOpportunityOptionsWarning(
        opportunityResult.status === "rejected"
          ? "Opportunity options are temporarily unavailable. You can still add this conversation without an opportunity."
          : opportunityResult.value.exactWarning
            ? "The linked opportunity could not be loaded. Choose another opportunity or continue without one."
            : null,
      );
      setContactOptionsWarning(
        contactResult.status === "rejected"
          ? "People options are temporarily unavailable. You can still add this conversation without a person."
          : contactResult.value.exactWarning
            ? "The linked person could not be loaded. Choose another person or continue without one."
            : null,
      );

      const linkedCompanyId = nextCompanies.some(
        (company) => company.id === linkedCompanyCandidate,
      )
        ? linkedCompanyCandidate
        : "";
      const linkedOpportunityId = conversationOnly
        ? initialOpportunityId
        : nextOpportunities.some(
              (opportunity) => opportunity.id === initialOpportunityId,
            )
          ? initialOpportunityId
          : "";
      const linkedContactId = nextContacts.some(
        (contact) => contact.id === initialContactId,
      )
        ? initialContactId
        : "";
      const linkedContext: LinkedInteractionContext = {
        companyId: linkedCompanyId,
        opportunityId: linkedOpportunityId,
        contactId: linkedContactId,
        interactionType: initialInteractionType,
      };
      if (!linkedContextLoadedRef.current || !contextDirtyRef.current) {
        setCompanyId(linkedContext.companyId);
        setOpportunityId(linkedContext.opportunityId);
        setContactId(linkedContext.contactId);
        setInteractionType(linkedContext.interactionType);
        contextDirtyRef.current = false;
        setPendingLinkedContext(null);
      } else {
        setPendingLinkedContext(linkedContext);
      }
      linkedContextLoadedRef.current = true;
      setLoading(false);
    });
    return () => controller.abort();
  }, [
    conversationOnly,
    initialCompanyId,
    initialContactId,
    initialInteractionType,
    initialOpportunityId,
    linkedContextIdentity,
  ]);

  useEffect(() => {
    if (optionRetryRequest === null) return;
    const request = optionRetryRequest;
    if (request.contextIdentity !== linkedContextIdentity) return;
    const controller = new AbortController();
    window.queueMicrotask(() => {
      if (
        controller.signal.aborted ||
        activeLinkedContextIdentityRef.current !== request.contextIdentity
      ) {
        return;
      }
      if (request.source === "company") {
        setCompanyOptionsState("loading");
        setCompanyOptionsWarning(null);
      } else if (request.source === "opportunity") {
        setOpportunityOptionsState("loading");
        setOpportunityOptionsWarning(null);
      } else {
        setContactOptionsState("loading");
        setContactOptionsWarning(null);
      }
    });

    void (async () => {
      try {
        if (request.source === "company") {
          const loaded = await loadCompanyOptions(
            request.linkedId,
            controller.signal,
          );
          if (
            controller.signal.aborted ||
            activeLinkedContextIdentityRef.current !== request.contextIdentity
          ) {
            return;
          }
          setCompanies(loaded.items);
          setCompanyOptionsState("ready");
          setCompanyOptionsWarning(
            loaded.exactWarning
              ? "The linked company could not be loaded. Choose another company or continue without one."
              : null,
          );
          if (
            !contextDirtyRef.current &&
            loaded.items.some((company) => company.id === request.linkedId)
          ) {
            setCompanyId(request.linkedId);
          }
          return;
        }
        if (request.source === "opportunity") {
          const loaded = await loadOpportunityOptions(
            request.linkedId,
            controller.signal,
          );
          if (
            controller.signal.aborted ||
            activeLinkedContextIdentityRef.current !== request.contextIdentity
          ) {
            return;
          }
          setOpportunities(loaded.items);
          setOpportunityOptionsState("ready");
          setOpportunityOptionsWarning(
            loaded.exactWarning
              ? "The linked opportunity could not be loaded. Choose another opportunity or continue without one."
              : null,
          );
          if (
            !contextDirtyRef.current &&
            loaded.items.some(
              (opportunity) => opportunity.id === request.linkedId,
            )
          ) {
            setOpportunityId(request.linkedId);
          }
          return;
        }

        const loaded = await loadContactOptions(
          request.linkedId,
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          activeLinkedContextIdentityRef.current !== request.contextIdentity
        ) {
          return;
        }
        setContacts(loaded.items);
        setContactOptionsState("ready");
        setContactOptionsWarning(
          loaded.exactWarning
            ? "The linked person could not be loaded. Choose another person or continue without one."
            : null,
        );
        if (
          !contextDirtyRef.current &&
          loaded.items.some((contact) => contact.id === request.linkedId)
        ) {
          setContactId(request.linkedId);
        }
      } catch (reason: unknown) {
        if (
          controller.signal.aborted ||
          activeLinkedContextIdentityRef.current !== request.contextIdentity ||
          isAbortError(reason)
        ) {
          return;
        }
        if (request.source === "company") {
          setCompanies([]);
          setCompanyOptionsState("unavailable");
          setCompanyOptionsWarning(
            "Company options are temporarily unavailable. You can still add this conversation without company context.",
          );
        } else if (request.source === "opportunity") {
          setOpportunities([]);
          setOpportunityOptionsState("unavailable");
          setOpportunityOptionsWarning(
            "Opportunity options are temporarily unavailable. You can still add this conversation without an opportunity.",
          );
        } else {
          setContacts([]);
          setContactOptionsState("unavailable");
          setContactOptionsWarning(
            "People options are temporarily unavailable. You can still add this conversation without a person.",
          );
        }
      }
    })();
    return () => controller.abort();
  }, [linkedContextIdentity, optionRetryRequest]);

  function requestOptionRetry(source: OptionRetryRequest["source"]): void {
    const linkedCompanyId =
      initialCompanyId ||
      contacts.find((contact) => contact.id === initialContactId)?.companyId ||
      opportunities.find(
        (opportunity) => opportunity.id === initialOpportunityId,
      )?.companyId ||
      "";
    setOptionRetryRequest({
      source,
      sequence: ++optionRetrySequenceRef.current,
      contextIdentity: linkedContextIdentity,
      linkedId:
        source === "company"
          ? linkedCompanyId
          : source === "opportunity"
            ? initialOpportunityId
            : initialContactId,
    });
  }

  function markContextDirty(): void {
    contextDirtyRef.current = true;
  }

  function applyLinkedContext(context: LinkedInteractionContext): void {
    setCompanyId(context.companyId);
    setOpportunityId(context.opportunityId);
    setContactId(context.contactId);
    setInteractionType(context.interactionType);
    contextDirtyRef.current = false;
    setPendingLinkedContext(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    const submittedCompanyId =
      companyOptionsState === "ready" &&
      companies.some((company) => company.id === companyId)
        ? companyId
        : null;
    const submittedOpportunityId = conversationOnly
      ? opportunityId || null
      : opportunityOptionsState === "ready" &&
          opportunities.some((opportunity) => opportunity.id === opportunityId)
        ? opportunityId
        : null;
    const submittedContactId =
      contactOptionsState === "ready" &&
      contacts.some((contact) => contact.id === contactId)
        ? contactId
        : null;
    try {
      const interaction = await apiRequest<Interaction>(
        "/api/v1/interactions",
        {
          method: "POST",
          body: JSON.stringify({
            title: title.trim(),
            interactionType,
            lifecycleStatus: "planned",
            companyId: submittedCompanyId,
            opportunityId: submittedOpportunityId,
            contactId:
              interactionType === "phone_call" ? submittedContactId : null,
            callDirection:
              interactionType === "phone_call" ? callDirection : null,
            meetingPlatform:
              interactionType === "online_meeting" ? meetingPlatform : null,
            meetingUrl:
              interactionType === "online_meeting"
                ? meetingUrl.trim() || null
                : null,
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
      router.push(`/conversations/${interaction.id}`);
    } catch (requestError: unknown) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The conversation could not be created.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby="interaction-form-title" className="form-card">
      <div className="max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
          Conversation memory
        </p>
        <h1
          id="interaction-form-title"
          className="mt-3 text-3xl font-semibold text-slate-950"
        >
          Add conversation
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Add a meeting, call or in-person note. Give it a title to get started;
          you can add company context and a time when useful.
        </p>
      </div>

      <>
        {loading ? (
          <p role="status" className="mt-6 text-sm text-slate-600">
            Loading optional relationship context…
          </p>
        ) : null}
        <form onSubmit={submit} className="mt-8 grid gap-5">
          {pendingLinkedContext ? (
            <aside
              role="status"
              className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
            >
              <p>
                The linked relationship context changed. Your current selections
                were kept because you had already edited them.
              </p>
              <button
                type="button"
                className="secondary-button mt-3"
                onClick={() => applyLinkedContext(pendingLinkedContext)}
              >
                Use linked context
              </button>
            </aside>
          ) : null}
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
            Conversation type
            <select
              className="form-control"
              value={interactionType}
              onChange={(event) => {
                markContextDirty();
                setInteractionType(event.target.value as InteractionType);
              }}
            >
              {(conversationOnly
                ? [
                    ...new Set<InteractionType>([
                      "online_meeting",
                      "face_to_face_meeting",
                      "phone_call",
                      "conference_interaction",
                      "manual_interaction",
                      initialInteractionType,
                    ]),
                  ]
                : interactionTypes
              ).map((value) => (
                <option key={value} value={value}>
                  {conversationOnly
                    ? ((
                        {
                          online_meeting: "Online meeting",
                          face_to_face_meeting: "In-person meeting",
                          phone_call: "Phone call",
                          conference_interaction: "Event notes",
                          manual_interaction: "Note",
                        } as Partial<Record<InteractionType, string>>
                      )[value] ?? humanise(value))
                    : humanise(value)}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Company
                <select
                  className="form-control"
                  disabled={companyOptionsState !== "ready"}
                  value={companyOptionsState === "ready" ? companyId : ""}
                  onChange={(event) => {
                    markContextDirty();
                    const nextCompanyId = event.target.value;
                    setCompanyId(nextCompanyId);
                    if (conversationOnly && opportunityId) {
                      setOpportunityId("");
                    }
                    if (
                      contactId &&
                      contacts.find((contact) => contact.id === contactId)
                        ?.companyId !== nextCompanyId
                    ) {
                      setContactId("");
                    }
                  }}
                >
                  <option value="">
                    {companyOptionsState === "loading"
                      ? "Loading companies…"
                      : companyOptionsState === "unavailable"
                        ? "Company options unavailable"
                        : "No company"}
                  </option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </label>
              <OptionAvailability
                message={companyOptionsWarning}
                retryLabel="Retry companies"
                loading={companyOptionsState === "loading"}
                onRetry={() => requestOptionRetry("company")}
              />
            </div>
            {!conversationOnly ? (
              <div>
                <label className="grid gap-2 text-sm font-bold text-slate-800">
                  Opportunity
                  <select
                    className="form-control"
                    disabled={opportunityOptionsState !== "ready"}
                    value={
                      opportunityOptionsState === "ready" ? opportunityId : ""
                    }
                    onChange={(event) => {
                      markContextDirty();
                      setOpportunityId(event.target.value);
                    }}
                  >
                    <option value="">
                      {opportunityOptionsState === "loading"
                        ? "Loading opportunities…"
                        : opportunityOptionsState === "unavailable"
                          ? "Opportunity options unavailable"
                          : "No opportunity"}
                    </option>
                    {opportunities.map((opportunity) => (
                      <option key={opportunity.id} value={opportunity.id}>
                        {opportunity.name}
                      </option>
                    ))}
                  </select>
                </label>
                <OptionAvailability
                  message={opportunityOptionsWarning}
                  retryLabel="Retry opportunities"
                  loading={opportunityOptionsState === "loading"}
                  onRetry={() => requestOptionRetry("opportunity")}
                />
              </div>
            ) : null}
          </div>
          {interactionType === "phone_call" ? (
            <fieldset className="grid gap-5 rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5 sm:grid-cols-2">
              <legend className="px-2 text-sm font-bold text-brand-primary">
                Phone call
              </legend>
              <p className="sm:col-span-2 text-sm leading-6 text-brand-primary">
                Use the phone system you already have. Oryntela prepares and
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
              <div>
                <label className="grid gap-2 text-sm font-bold text-slate-800">
                  Person
                  <select
                    className="form-control"
                    disabled={contactOptionsState !== "ready"}
                    value={contactOptionsState === "ready" ? contactId : ""}
                    onChange={(event) => {
                      markContextDirty();
                      setContactId(event.target.value);
                    }}
                  >
                    <option value="">
                      {contactOptionsState === "loading"
                        ? "Loading people…"
                        : contactOptionsState === "unavailable"
                          ? "People options unavailable"
                          : "No contact"}
                    </option>
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
                <OptionAvailability
                  message={contactOptionsWarning}
                  retryLabel="Retry people"
                  loading={contactOptionsState === "loading"}
                  onRetry={() => requestOptionRetry("contact")}
                />
              </div>
            </fieldset>
          ) : null}
          {interactionType === "online_meeting" ? (
            <fieldset className="grid gap-5 rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5 sm:grid-cols-2">
              <legend className="px-2 text-sm font-bold text-brand-primary">
                Online meeting
              </legend>
              <p className="sm:col-span-2 text-sm leading-6 text-brand-primary">
                Use your normal meeting app. Oryntela stores a safe link for you
                to open and offers authorised import or debrief choices
                afterwards. It does not join, record system audio or run a bot.
              </p>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Meeting platform
                <select
                  className="form-control"
                  value={meetingPlatform}
                  onChange={(event) => {
                    const nextPlatform = event.target
                      .value as OnlineMeetingPlatform;
                    setMeetingPlatform(nextPlatform);
                    if (nextPlatform === "other") setMeetingUrl("");
                  }}
                >
                  <option value="microsoft_teams">Microsoft Teams</option>
                  <option value="zoom">Zoom</option>
                  <option value="google_meet">Google Meet</option>
                  <option value="other">Other or not known</option>
                </select>
              </label>
              <label className="grid gap-2 text-sm font-bold text-slate-800">
                Meeting link (optional)
                <input
                  className="form-control"
                  type="url"
                  inputMode="url"
                  maxLength={1000}
                  placeholder="https://…"
                  value={meetingUrl}
                  disabled={meetingPlatform === "other"}
                  onChange={(event) => setMeetingUrl(event.target.value)}
                />
              </label>
              <p className="sm:col-span-2 text-xs leading-5 text-slate-600">
                Query parameters and fragments are removed before storage.
                Choose a supported platform before adding a link; for other
                platforms, create the interaction without one.
              </p>
            </fieldset>
          ) : null}
          <OptionalSchedule collapsed={conversationOnly}>
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
          </OptionalSchedule>
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
              {submitting ? "Creating…" : "Add conversation"}
            </button>
            <Link className="secondary-button" href="/conversations">
              Cancel
            </Link>
          </div>
        </form>
      </>
    </section>
  );
}

function OptionAvailability({
  message,
  retryLabel,
  loading,
  onRetry,
}: {
  message: string | null;
  retryLabel: string;
  loading: boolean;
  onRetry: () => void;
}) {
  return message ? (
    <div
      role="status"
      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-normal leading-6 text-amber-950"
    >
      <p>{message}</p>
      <button
        type="button"
        className="secondary-button mt-3"
        disabled={loading}
        onClick={onRetry}
      >
        {loading ? "Retrying…" : retryLabel}
      </button>
    </div>
  ) : null;
}

function OptionalSchedule({
  collapsed,
  children,
}: {
  collapsed: boolean;
  children: ReactNode;
}) {
  return collapsed ? (
    <details className="rounded-xl border border-brand-primary/10 p-4">
      <summary className="cursor-pointer text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-focus">
        Add a scheduled time (optional)
      </summary>
      <div className="mt-4">{children}</div>
    </details>
  ) : (
    children
  );
}
