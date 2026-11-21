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

type ManualRelationshipSource = "opportunity" | "contact";

interface ManualCompanyVerificationRequest {
  source: ManualRelationshipSource;
  sequence: number;
  relationshipId: string;
  companyId: string;
  contextIdentity: string;
  controller: AbortController;
}

interface ManualRelationshipFeedback {
  source: ManualRelationshipSource;
  message: string;
}

interface RelationshipContextInput {
  companyId: string;
  opportunityId: string;
  contactId: string;
  interactionType: InteractionType;
  companies: Company[];
  opportunities: Opportunity[];
  contacts: Contact[];
}

const linkedCompanyWarning =
  "The linked company could not be verified as active. Choose another company or continue without one.";
const linkedOpportunityWarning =
  "The linked opportunity could not be verified as active for this account. Continue without it or choose another opportunity when available.";
const linkedContactWarning =
  "The linked person could not be verified as active for this account. Choose another person or continue without one.";
const selectedOpportunityCompanyWarning =
  "The selected opportunity’s company could not be verified as active. Choose another opportunity or continue without one.";
const selectedContactCompanyWarning =
  "The selected person’s company could not be verified as active. Choose another person or continue without one.";

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

function isActiveRecord(record: { archivedAt: string | null }): boolean {
  return record.archivedAt === null;
}

function exactActiveRecord<T extends { id: string; archivedAt: string | null }>(
  record: T,
  requestedId: string,
): T | null {
  return record.id === requestedId && isActiveRecord(record) ? record : null;
}

function activeRecordById<T extends { id: string; archivedAt: string | null }>(
  items: T[],
  id: string,
): T | null {
  const record = items.find((item) => item.id === id);
  return record && isActiveRecord(record) ? record : null;
}

function mergeActiveRecords<
  T extends { id: string; archivedAt: string | null },
>(items: T[], additions: T[]): T[] {
  return additions
    .filter(isActiveRecord)
    .reduce(
      (merged, item) => appendUnique(merged, item),
      items.filter(isActiveRecord),
    );
}

function reconcileRelationshipContext({
  companyId,
  opportunityId,
  contactId,
  interactionType,
  companies,
  opportunities,
  contacts,
}: RelationshipContextInput): LinkedInteractionContext {
  const requestedCompany = activeRecordById(companies, companyId);
  const requestedOpportunity = activeRecordById(opportunities, opportunityId);
  const requestedContact =
    interactionType === "phone_call"
      ? activeRecordById(contacts, contactId)
      : null;
  const relationshipCompanyId =
    requestedCompany?.id ??
    requestedContact?.companyId ??
    requestedOpportunity?.companyId ??
    "";
  const relationshipCompany = activeRecordById(
    companies,
    relationshipCompanyId,
  );
  const verifiedCompanyId = relationshipCompany?.id ?? "";
  const verifiedOpportunityId =
    requestedOpportunity &&
    (requestedOpportunity.companyId === null ||
      (verifiedCompanyId !== "" &&
        requestedOpportunity.companyId === verifiedCompanyId))
      ? requestedOpportunity.id
      : "";
  const verifiedContactId =
    requestedContact &&
    verifiedCompanyId !== "" &&
    requestedContact.companyId === verifiedCompanyId
      ? requestedContact.id
      : "";

  return {
    companyId: verifiedCompanyId,
    opportunityId: verifiedOpportunityId,
    contactId: verifiedContactId,
    interactionType,
  };
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
  let items = page.items.filter(isActiveRecord);
  if (linkedId && !items.some((company) => company.id === linkedId)) {
    try {
      const exact = exactActiveRecord(
        await apiRequest<Company>(
          `/api/v1/companies/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
        linkedId,
      );
      items = appendUnique(items, exact);
      exactWarning = exact === null;
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
  let items = page.items.filter(isActiveRecord);
  if (linkedId && !items.some((contact) => contact.id === linkedId)) {
    try {
      const exact = exactActiveRecord(
        await apiRequest<Contact>(
          `/api/v1/contacts/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
        linkedId,
      );
      items = appendUnique(items, exact);
      exactWarning = exact === null;
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
  let items = page.items.filter(isActiveRecord);
  if (linkedId && !items.some((opportunity) => opportunity.id === linkedId)) {
    try {
      const exact = exactActiveRecord(
        await apiRequest<Opportunity>(
          `/api/v1/opportunities/${encodeURIComponent(linkedId)}`,
          { signal },
        ),
        linkedId,
      );
      items = appendUnique(items, exact);
      exactWarning = exact === null;
    } catch (reason: unknown) {
      if (signal.aborted || isAbortError(reason)) throw reason;
      exactWarning = true;
    }
  }
  return { items, exactWarning };
}

async function loadLinkedOpportunity(
  linkedId: string,
  signal: AbortSignal,
): Promise<LoadedOptions<Opportunity>> {
  if (!linkedId) return { items: [], exactWarning: false };
  try {
    const exact = exactActiveRecord(
      await apiRequest<Opportunity>(
        `/api/v1/opportunities/${encodeURIComponent(linkedId)}`,
        { signal },
      ),
      linkedId,
    );
    return {
      items: exact ? [exact] : [],
      exactWarning: exact === null,
    };
  } catch (reason: unknown) {
    if (signal.aborted || isAbortError(reason)) throw reason;
    return { items: [], exactWarning: true };
  }
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
    useState<OptionLoadState>(
      conversationOnly && !initialOpportunityId ? "ready" : "loading",
    );
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
  const [manualCompanyVerification, setManualCompanyVerification] =
    useState<ManualCompanyVerificationRequest | null>(null);
  const [manualRelationshipFeedback, setManualRelationshipFeedback] =
    useState<ManualRelationshipFeedback | null>(null);
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
  const manualVerificationSequenceRef = useRef(0);
  const manualCompanyVerificationRef =
    useRef<ManualCompanyVerificationRequest | null>(null);
  const activeLinkedContextIdentityRef = useRef(linkedContextIdentity);
  const companiesRef = useRef(companies);
  const opportunitiesRef = useRef(opportunities);
  const contactsRef = useRef(contacts);
  const manuallyVerifiedCompaniesRef = useRef<Company[]>([]);

  useLayoutEffect(() => {
    activeLinkedContextIdentityRef.current = linkedContextIdentity;
  }, [linkedContextIdentity]);

  useLayoutEffect(() => {
    companiesRef.current = companies;
    opportunitiesRef.current = opportunities;
    contactsRef.current = contacts;
  }, [companies, contacts, opportunities]);

  useEffect(() => {
    const controller = new AbortController();
    const requestContextIdentity = linkedContextIdentity;
    manualCompanyVerificationRef.current?.controller.abort();
    manualCompanyVerificationRef.current = null;
    manuallyVerifiedCompaniesRef.current = [];
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
      setOpportunityOptionsState(
        conversationOnly && !initialOpportunityId ? "ready" : "loading",
      );
      setCompanyOptionsWarning(null);
      setContactOptionsWarning(null);
      setOpportunityOptionsWarning(null);
      setManualCompanyVerification(null);
      setManualRelationshipFeedback(null);
    });

    const companyOptionsRequest = loadCompanyOptions(
      initialCompanyId,
      controller.signal,
    );
    const contactOptionsRequest = loadContactOptions(
      initialContactId,
      controller.signal,
    );
    const opportunityOptionsRequest: Promise<LoadedOptions<Opportunity>> =
      conversationOnly
        ? loadLinkedOpportunity(initialOpportunityId, controller.signal)
        : loadOpportunityOptions(initialOpportunityId, controller.signal);

    const requestIsActive = (): boolean =>
      !controller.signal.aborted &&
      activeLinkedContextIdentityRef.current === requestContextIdentity;

    void companyOptionsRequest.then(
      (loaded) => {
        if (!requestIsActive()) return;
        const nextCompanies = mergeActiveRecords(
          loaded.items,
          manuallyVerifiedCompaniesRef.current,
        );
        companiesRef.current = nextCompanies;
        setCompanies(nextCompanies);
        setCompanyOptionsState("ready");
        setCompanyOptionsWarning(
          loaded.exactWarning ? linkedCompanyWarning : null,
        );
      },
      (reason: unknown) => {
        if (!requestIsActive() || isAbortError(reason)) return;
        const verifiedCompanies = manuallyVerifiedCompaniesRef.current;
        companiesRef.current = verifiedCompanies;
        setCompanies(verifiedCompanies);
        setCompanyOptionsState(
          verifiedCompanies.length > 0 ? "ready" : "unavailable",
        );
        setCompanyOptionsWarning(
          "Company options are temporarily unavailable. You can still add this conversation without company context.",
        );
      },
    );
    void opportunityOptionsRequest.then(
      (loaded) => {
        if (!requestIsActive()) return;
        opportunitiesRef.current = loaded.items;
        setOpportunities(loaded.items);
        setOpportunityOptionsState("ready");
        setOpportunityOptionsWarning(
          loaded.exactWarning ? linkedOpportunityWarning : null,
        );
      },
      (reason: unknown) => {
        if (!requestIsActive() || isAbortError(reason)) return;
        opportunitiesRef.current = [];
        setOpportunities([]);
        setOpportunityOptionsState("unavailable");
        setOpportunityOptionsWarning(
          "Opportunity options are temporarily unavailable. You can still add this conversation without an opportunity.",
        );
      },
    );
    void contactOptionsRequest.then(
      (loaded) => {
        if (!requestIsActive()) return;
        contactsRef.current = loaded.items;
        setContacts(loaded.items);
        setContactOptionsState("ready");
        setContactOptionsWarning(
          loaded.exactWarning ? linkedContactWarning : null,
        );
      },
      (reason: unknown) => {
        if (!requestIsActive() || isAbortError(reason)) return;
        contactsRef.current = [];
        setContacts([]);
        setContactOptionsState("unavailable");
        setContactOptionsWarning(
          "People options are temporarily unavailable. You can still add this conversation without a person.",
        );
      },
    );

    void Promise.allSettled([
      companyOptionsRequest,
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
        companyResult.status === "fulfilled"
          ? mergeActiveRecords(
              companyResult.value.items,
              manuallyVerifiedCompaniesRef.current,
            )
          : manuallyVerifiedCompaniesRef.current;
      const nextOpportunities =
        opportunityResult.status === "fulfilled"
          ? opportunityResult.value.items
          : [];
      const nextContacts =
        contactResult.status === "fulfilled" ? contactResult.value.items : [];
      const selectedContact = activeRecordById(nextContacts, initialContactId);
      const selectedOpportunity = activeRecordById(
        nextOpportunities,
        initialOpportunityId,
      );
      const selectedCompany = activeRecordById(nextCompanies, initialCompanyId);
      const linkedCompanyCandidate =
        selectedCompany?.id ||
        (initialInteractionType === "phone_call"
          ? selectedContact?.companyId
          : "") ||
        selectedOpportunity?.companyId ||
        "";
      let companyExactWarning =
        companyResult.status === "fulfilled" &&
        companyResult.value.exactWarning;
      if (
        companyResult.status === "fulfilled" &&
        linkedCompanyCandidate &&
        !nextCompanies.some((company) => company.id === linkedCompanyCandidate)
      ) {
        try {
          const exact = exactActiveRecord(
            await apiRequest<Company>(
              `/api/v1/companies/${encodeURIComponent(linkedCompanyCandidate)}`,
              { signal: controller.signal },
            ),
            linkedCompanyCandidate,
          );
          nextCompanies = appendUnique(nextCompanies, exact);
          companyExactWarning ||= exact === null;
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

      if (companyResult.status === "fulfilled") {
        companiesRef.current = nextCompanies;
        setCompanies(nextCompanies);
        setCompanyOptionsWarning(
          companyExactWarning ? linkedCompanyWarning : null,
        );
      }

      const linkedContext = reconcileRelationshipContext({
        companyId: linkedCompanyCandidate,
        opportunityId: initialOpportunityId,
        contactId: initialContactId,
        interactionType: initialInteractionType,
        companies: nextCompanies,
        opportunities: nextOpportunities,
        contacts: nextContacts,
      });
      if (
        opportunityResult.status === "fulfilled" &&
        initialOpportunityId &&
        !linkedContext.opportunityId
      ) {
        setOpportunityOptionsWarning(linkedOpportunityWarning);
      }
      if (
        contactResult.status === "fulfilled" &&
        initialContactId &&
        !linkedContext.contactId
      ) {
        setContactOptionsWarning(linkedContactWarning);
      }
      if (!contextDirtyRef.current) {
        setCompanyId(linkedContext.companyId);
        setOpportunityId(linkedContext.opportunityId);
        setContactId(linkedContext.contactId);
        setInteractionType(linkedContext.interactionType);
        contextDirtyRef.current = false;
        setPendingLinkedContext(null);
      } else if (linkedContextLoadedRef.current) {
        setPendingLinkedContext(linkedContext);
      }
      linkedContextLoadedRef.current = true;
      setLoading(false);
    });
    return () => {
      controller.abort();
      const manualRequest = manualCompanyVerificationRef.current;
      if (manualRequest?.contextIdentity === requestContextIdentity) {
        manualRequest.controller.abort();
        manualCompanyVerificationRef.current = null;
      }
    };
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
      } else if (request.source === "opportunity") {
        setOpportunityOptionsState("loading");
      } else {
        setContactOptionsState("loading");
      }
    });

    void (async () => {
      const adoptVerifiedContext = (
        nextCompanies: Company[],
        nextOpportunities: Opportunity[],
        nextContacts: Contact[],
      ): LinkedInteractionContext => {
        const linkedContext = reconcileRelationshipContext({
          companyId: initialCompanyId,
          opportunityId: initialOpportunityId,
          contactId: initialContactId,
          interactionType: initialInteractionType,
          companies: nextCompanies,
          opportunities: nextOpportunities,
          contacts: nextContacts,
        });
        if (!contextDirtyRef.current) {
          setCompanyId(linkedContext.companyId);
          setOpportunityId(linkedContext.opportunityId);
          setContactId(linkedContext.contactId);
          setInteractionType(linkedContext.interactionType);
        }
        return linkedContext;
      };

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
          const nextCompanies = mergeActiveRecords(
            loaded.items,
            manuallyVerifiedCompaniesRef.current,
          );
          companiesRef.current = nextCompanies;
          setCompanies(nextCompanies);
          setCompanyOptionsState("ready");
          const linkedContext = adoptVerifiedContext(
            nextCompanies,
            opportunitiesRef.current,
            contactsRef.current,
          );
          setCompanyOptionsWarning(
            loaded.exactWarning ||
              (initialCompanyId !== "" && !linkedContext.companyId)
              ? linkedCompanyWarning
              : null,
          );
          setOptionRetryRequest(null);
          return;
        }
        if (request.source === "opportunity") {
          const loaded = conversationOnly
            ? await loadLinkedOpportunity(request.linkedId, controller.signal)
            : await loadOpportunityOptions(request.linkedId, controller.signal);
          if (
            controller.signal.aborted ||
            activeLinkedContextIdentityRef.current !== request.contextIdentity
          ) {
            return;
          }
          opportunitiesRef.current = loaded.items;
          setOpportunities(loaded.items);
          setOpportunityOptionsState("ready");
          const linkedContext = adoptVerifiedContext(
            companiesRef.current,
            loaded.items,
            contactsRef.current,
          );
          setOpportunityOptionsWarning(
            loaded.exactWarning ||
              (initialOpportunityId !== "" && !linkedContext.opportunityId)
              ? linkedOpportunityWarning
              : null,
          );
          setOptionRetryRequest(null);
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
        contactsRef.current = loaded.items;
        setContacts(loaded.items);
        setContactOptionsState("ready");
        const linkedContext = adoptVerifiedContext(
          companiesRef.current,
          opportunitiesRef.current,
          loaded.items,
        );
        setContactOptionsWarning(
          loaded.exactWarning ||
            (initialContactId !== "" && !linkedContext.contactId)
            ? linkedContactWarning
            : null,
        );
        setOptionRetryRequest(null);
      } catch (reason: unknown) {
        if (
          controller.signal.aborted ||
          activeLinkedContextIdentityRef.current !== request.contextIdentity ||
          isAbortError(reason)
        ) {
          return;
        }
        if (request.source === "company") {
          const verifiedCompanies = manuallyVerifiedCompaniesRef.current;
          companiesRef.current = verifiedCompanies;
          setCompanies(verifiedCompanies);
          setCompanyOptionsState(
            verifiedCompanies.length > 0 ? "ready" : "unavailable",
          );
          setCompanyOptionsWarning(
            "Company options are temporarily unavailable. You can still add this conversation without company context.",
          );
        } else if (request.source === "opportunity") {
          opportunitiesRef.current = [];
          setOpportunities([]);
          setOpportunityOptionsState("unavailable");
          setOpportunityOptionsWarning(
            "Opportunity options are temporarily unavailable. You can still add this conversation without an opportunity.",
          );
        } else {
          contactsRef.current = [];
          setContacts([]);
          setContactOptionsState("unavailable");
          setContactOptionsWarning(
            "People options are temporarily unavailable. You can still add this conversation without a person.",
          );
        }
        setOptionRetryRequest(null);
      }
    })();
    return () => controller.abort();
  }, [
    conversationOnly,
    initialCompanyId,
    initialContactId,
    initialInteractionType,
    initialOpportunityId,
    linkedContextIdentity,
    optionRetryRequest,
  ]);

  function requestOptionRetry(source: OptionRetryRequest["source"]): void {
    const linkedCompanyId =
      initialCompanyId ||
      contactsRef.current.find((contact) => contact.id === initialContactId)
        ?.companyId ||
      opportunitiesRef.current.find(
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

  function clearManualCompanyVerification(clearSelection: boolean): void {
    const request = manualCompanyVerificationRef.current;
    if (request === null) return;
    request.controller.abort();
    manualCompanyVerificationRef.current = null;
    setManualCompanyVerification(null);
    if (!clearSelection) return;
    if (request.source === "opportunity") {
      setOpportunityId((current) =>
        current === request.relationshipId ? "" : current,
      );
    } else {
      setContactId((current) =>
        current === request.relationshipId ? "" : current,
      );
    }
  }

  function rejectManualRelationship(
    source: ManualRelationshipSource,
    relationshipId: string,
  ): void {
    if (source === "opportunity") {
      setOpportunityId((current) =>
        current === relationshipId ? "" : current,
      );
      setManualRelationshipFeedback({
        source,
        message: selectedOpportunityCompanyWarning,
      });
    } else {
      setContactId((current) => (current === relationshipId ? "" : current));
      setManualRelationshipFeedback({
        source,
        message: selectedContactCompanyWarning,
      });
    }
  }

  function verifyManualRelationshipCompany(
    source: ManualRelationshipSource,
    relationshipId: string,
    relatedCompanyId: string,
  ): void {
    const controller = new AbortController();
    const request: ManualCompanyVerificationRequest = {
      source,
      sequence: ++manualVerificationSequenceRef.current,
      relationshipId,
      companyId: relatedCompanyId,
      contextIdentity: linkedContextIdentity,
      controller,
    };
    manualCompanyVerificationRef.current = request;
    setManualCompanyVerification(request);
    setManualRelationshipFeedback(null);

    const requestIsActive = (): boolean =>
      !controller.signal.aborted &&
      manualCompanyVerificationRef.current === request &&
      activeLinkedContextIdentityRef.current === request.contextIdentity;
    const finish = (): void => {
      if (!requestIsActive()) return;
      manualCompanyVerificationRef.current = null;
      setManualCompanyVerification(null);
    };
    const adoptVerifiedCompany = (verifiedCompany: Company): void => {
      manuallyVerifiedCompaniesRef.current = appendUnique(
        manuallyVerifiedCompaniesRef.current,
        verifiedCompany,
      );
      const nextCompanies = mergeActiveRecords(companiesRef.current, [
        verifiedCompany,
      ]);
      companiesRef.current = nextCompanies;
      setCompanies(nextCompanies);
      setCompanyOptionsState("ready");
      setCompanyId(verifiedCompany.id);
      setManualRelationshipFeedback(null);
      finish();
    };
    const rejectUnlessAlreadyVerified = (): void => {
      const currentlyVerified = activeRecordById(
        companiesRef.current,
        relatedCompanyId,
      );
      if (currentlyVerified !== null) {
        adoptVerifiedCompany(currentlyVerified);
        return;
      }
      rejectManualRelationship(source, relationshipId);
      finish();
    };

    void apiRequest<Company>(
      `/api/v1/companies/${encodeURIComponent(relatedCompanyId)}`,
      { signal: controller.signal },
    ).then(
      (record) => {
        if (!requestIsActive()) return;
        const verifiedCompany = exactActiveRecord(record, relatedCompanyId);
        if (verifiedCompany === null) {
          rejectUnlessAlreadyVerified();
          return;
        }
        adoptVerifiedCompany(verifiedCompany);
      },
      (reason: unknown) => {
        if (!requestIsActive() || isAbortError(reason)) return;
        rejectUnlessAlreadyVerified();
      },
    );
  }

  function selectManualOpportunity(nextOpportunityId: string): void {
    clearManualCompanyVerification(true);
    setManualRelationshipFeedback(null);
    setOpportunityId(nextOpportunityId);
    if (!nextOpportunityId) return;
    const nextOpportunity = activeRecordById(
      opportunitiesRef.current,
      nextOpportunityId,
    );
    if (nextOpportunity === null) {
      rejectManualRelationship("opportunity", nextOpportunityId);
      return;
    }
    if (nextOpportunity.companyId === null) return;
    if (companyId && companyId !== nextOpportunity.companyId) {
      rejectManualRelationship("opportunity", nextOpportunityId);
      return;
    }
    const verifiedCompany = activeRecordById(
      companiesRef.current,
      nextOpportunity.companyId,
    );
    if (verifiedCompany !== null) {
      setCompanyId(verifiedCompany.id);
      return;
    }
    verifyManualRelationshipCompany(
      "opportunity",
      nextOpportunity.id,
      nextOpportunity.companyId,
    );
  }

  function selectManualContact(nextContactId: string): void {
    clearManualCompanyVerification(true);
    setManualRelationshipFeedback(null);
    setContactId(nextContactId);
    if (!nextContactId) return;
    const nextContact = activeRecordById(contactsRef.current, nextContactId);
    if (
      nextContact === null ||
      (companyId && companyId !== nextContact.companyId)
    ) {
      rejectManualRelationship("contact", nextContactId);
      return;
    }
    const verifiedCompany = activeRecordById(
      companiesRef.current,
      nextContact.companyId,
    );
    if (verifiedCompany !== null) {
      setCompanyId(verifiedCompany.id);
      return;
    }
    verifyManualRelationshipCompany(
      "contact",
      nextContact.id,
      nextContact.companyId,
    );
  }

  function markContextDirty(): void {
    contextDirtyRef.current = true;
  }

  function applyLinkedContext(context: LinkedInteractionContext): void {
    clearManualCompanyVerification(true);
    setManualRelationshipFeedback(null);
    setCompanyId(context.companyId);
    setOpportunityId(context.opportunityId);
    setContactId(context.contactId);
    setInteractionType(context.interactionType);
    contextDirtyRef.current = false;
    setPendingLinkedContext(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (manualCompanyVerificationRef.current !== null) return;
    setSubmitError(null);
    setSubmitting(true);
    const submittedContext = reconcileRelationshipContext({
      companyId,
      opportunityId,
      contactId,
      interactionType,
      companies: companyOptionsState === "ready" ? companies : [],
      opportunities: opportunityOptionsState === "ready" ? opportunities : [],
      contacts: contactOptionsState === "ready" ? contacts : [],
    });
    try {
      const interaction = await apiRequest<Interaction>(
        "/api/v1/interactions",
        {
          method: "POST",
          body: JSON.stringify({
            title: title.trim(),
            interactionType,
            lifecycleStatus: "planned",
            companyId: submittedContext.companyId || null,
            opportunityId: submittedContext.opportunityId || null,
            contactId:
              interactionType === "phone_call"
                ? submittedContext.contactId || null
                : null,
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
                const nextInteractionType = event.target
                  .value as InteractionType;
                if (
                  nextInteractionType !== "phone_call" &&
                  manualCompanyVerificationRef.current?.source === "contact"
                ) {
                  clearManualCompanyVerification(true);
                }
                if (nextInteractionType !== "phone_call") {
                  setManualRelationshipFeedback((current) =>
                    current?.source === "contact" ? null : current,
                  );
                }
                setInteractionType(nextInteractionType);
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
                    clearManualCompanyVerification(true);
                    setManualRelationshipFeedback(null);
                    const nextCompanyId = event.target.value;
                    setCompanyId(nextCompanyId);
                    const selectedOpportunity = activeRecordById(
                      opportunities,
                      opportunityId,
                    );
                    if (
                      opportunityId &&
                      (conversationOnly ||
                        (selectedOpportunity?.companyId !== null &&
                          selectedOpportunity?.companyId !== nextCompanyId))
                    ) {
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
                      selectManualOpportunity(event.target.value);
                    }}
                  >
                    <option value="">
                      {opportunityOptionsState === "loading"
                        ? "Loading opportunities…"
                        : opportunityOptionsState === "unavailable"
                          ? "Opportunity options unavailable"
                          : "No opportunity"}
                    </option>
                    {opportunities
                      .filter(
                        (opportunity) =>
                          !companyId ||
                          opportunity.companyId === null ||
                          opportunity.companyId === companyId,
                      )
                      .map((opportunity) => (
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
                <ManualRelationshipStatus
                  source="opportunity"
                  verification={manualCompanyVerification}
                  feedback={manualRelationshipFeedback}
                />
              </div>
            ) : null}
          </div>
          {conversationOnly && opportunityOptionsWarning ? (
            <OptionAvailability
              message={opportunityOptionsWarning}
              retryLabel="Retry linked opportunity"
              loading={opportunityOptionsState === "loading"}
              onRetry={() => requestOptionRetry("opportunity")}
            />
          ) : null}
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
                      selectManualContact(event.target.value);
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
                <ManualRelationshipStatus
                  source="contact"
                  verification={manualCompanyVerification}
                  feedback={manualRelationshipFeedback}
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
              disabled={submitting || manualCompanyVerification !== null}
            >
              {manualCompanyVerification
                ? "Verifying relationship…"
                : submitting
                  ? "Creating…"
                  : "Add conversation"}
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

function ManualRelationshipStatus({
  source,
  verification,
  feedback,
}: {
  source: ManualRelationshipSource;
  verification: ManualCompanyVerificationRequest | null;
  feedback: ManualRelationshipFeedback | null;
}) {
  const verifying = verification?.source === source;
  const message = feedback?.source === source ? feedback.message : null;
  if (!verifying && message === null) return null;
  return (
    <p
      role="status"
      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-normal leading-6 text-amber-950"
    >
      {verifying
        ? source === "opportunity"
          ? "Verifying the selected opportunity’s company…"
          : "Verifying the selected person’s company…"
        : message}
    </p>
  );
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
