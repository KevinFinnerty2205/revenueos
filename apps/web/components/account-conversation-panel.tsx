"use client";

import type { Contact, Interaction, TenantEntityPage } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { InteractionCard } from "@/components/interaction-card";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { apiRequest, ApiClientError } from "@/lib/api";
import {
  decodeTenantPage,
  isContactResponse,
  isInteractionResponse,
} from "@/lib/private-response-identity";

export function AccountConversationPanel({ companyId }: { companyId: string }) {
  const verifiedOrganisation = useVerifiedOrganisation();
  const organisationId = verifiedOrganisation.organisationId;
  const requestKey = `${organisationId ?? "unverified"}:${companyId}`;
  const [loadedRequestKey, setLoadedRequestKey] = useState(requestKey);
  const [result, setResult] = useState<TenantEntityPage<Interaction> | null>(
    null,
  );
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingMoreRequestKey, setLoadingMoreRequestKey] = useState<
    string | null
  >(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const activeRequestKey = useRef(requestKey);
  const loadMoreController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!organisationId) return;
    const requestOrganisationId = organisationId;
    activeRequestKey.current = requestKey;
    loadMoreController.current?.abort();
    const controller = new AbortController();
    const encodedCompanyId = encodeURIComponent(companyId);
    async function loadAccountConversations() {
      let interactionPage: TenantEntityPage<Interaction>;
      try {
        const payload = await apiRequest<unknown>(
          accountInteractionPath(companyId),
          { signal: controller.signal },
        );
        const decoded = decodeTenantPage(
          payload,
          requestOrganisationId,
          isInteractionResponse,
          { expectedPage: 1 },
        );
        if (!decoded) {
          throw new Error(
            "Account conversations could not be loaded. Please try again.",
          );
        }
        interactionPage = decoded;
      } catch (reason: unknown) {
        if (
          controller.signal.aborted ||
          (reason instanceof DOMException && reason.name === "AbortError")
        )
          return;
        setLoadedRequestKey(requestKey);
        setResult(null);
        setContacts([]);
        setLoadMoreError(null);
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "Account conversations could not be loaded. Please try again.",
        );
        return;
      }

      if (controller.signal.aborted) return;
      if (
        !interactionsBelongToAccount(
          interactionPage.items,
          companyId,
          requestOrganisationId,
        )
      ) {
        setLoadedRequestKey(requestKey);
        setResult(null);
        setContacts([]);
        setLoadMoreError(null);
        setError(
          "Account conversations could not be loaded. Please try again.",
        );
        return;
      }
      setLoadedRequestKey(requestKey);
      setContacts([]);
      setResult(interactionPage);
      setError(null);
      setLoadMoreError(null);

      let listedContacts: Contact[] = [];
      try {
        const payload = await apiRequest<unknown>(
          "/api/v1/contacts?pageSize=100&companyId=" + encodedCompanyId,
          { signal: controller.signal },
        );
        const contactPage = decodeTenantPage(
          payload,
          requestOrganisationId,
          isContactResponse,
          { expectedPage: 1 },
        );
        if (!contactPage) throw new Error("invalid_account_contact_page");
        if (
          contactPage.items.some(
            (contact) =>
              !isAvailableAccountContact(
                contact,
                companyId,
                requestOrganisationId,
              ),
          )
        ) {
          throw new Error("invalid_account_contact_page");
        }
        listedContacts = contactPage.items;
      } catch {
        if (controller.signal.aborted) return;
      }

      const hydratedContacts = await hydrateLinkedContacts(
        interactionPage.items,
        listedContacts,
        companyId,
        requestOrganisationId,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setContacts((current) =>
        mergeAccountContacts(
          current,
          hydratedContacts,
          companyId,
          requestOrganisationId,
        ),
      );
    }

    void loadAccountConversations();
    return () => {
      controller.abort();
      loadMoreController.current?.abort();
    };
  }, [companyId, organisationId, requestKey, retryKey]);

  const accountIsCurrent = loadedRequestKey === requestKey;
  const currentResult = accountIsCurrent ? result : null;
  const currentContacts = accountIsCurrent ? contacts : [];
  const currentError = accountIsCurrent ? error : null;
  const currentLoadMoreError = accountIsCurrent ? loadMoreError : null;
  const loadingMore = loadingMoreRequestKey === requestKey;
  const interactions = currentResult?.items ?? null;

  const contactNames = useMemo(
    () =>
      new Map(
        (accountIsCurrent ? contacts : []).map((contact) => [
          contact.id,
          contact.firstName + " " + contact.lastName,
        ]),
      ),
    [accountIsCurrent, contacts],
  );

  async function loadMore() {
    if (
      !currentResult ||
      currentResult.page >= currentResult.pages ||
      loadingMore
    )
      return;
    if (!organisationId) return;
    const requestOrganisationId = organisationId;
    const requestedCompanyId = companyId;
    const requestedKey = requestKey;
    const controller = new AbortController();
    loadMoreController.current?.abort();
    loadMoreController.current = controller;
    setLoadingMoreRequestKey(requestedKey);
    setLoadMoreError(null);
    const finish = () => {
      if (loadMoreController.current !== controller) return;
      loadMoreController.current = null;
      setLoadingMoreRequestKey((current) =>
        current === requestedKey ? null : current,
      );
    };
    let nextPage: TenantEntityPage<Interaction>;
    try {
      const payload = await apiRequest<unknown>(
        accountInteractionPath(companyId, currentResult.page + 1),
        { signal: controller.signal },
      );
      const decoded = decodeTenantPage(
        payload,
        requestOrganisationId,
        isInteractionResponse,
        { expectedPage: currentResult.page + 1 },
      );
      if (!decoded) {
        throw new Error(
          "More account conversations could not be loaded. Please try again.",
        );
      }
      nextPage = decoded;
    } catch (reason: unknown) {
      if (
        !controller.signal.aborted &&
        activeRequestKey.current === requestedKey
      ) {
        setLoadMoreError(
          reason instanceof ApiClientError
            ? reason.message
            : "More account conversations could not be loaded. Please try again.",
        );
      }
      finish();
      return;
    }

    if (
      controller.signal.aborted ||
      activeRequestKey.current !== requestedKey
    ) {
      finish();
      return;
    }
    if (
      !interactionsBelongToAccount(
        nextPage.items,
        requestedCompanyId,
        requestOrganisationId,
      )
    ) {
      setLoadMoreError(
        "More account conversations could not be loaded. Please try again.",
      );
      finish();
      return;
    }
    setResult((current) =>
      current
        ? {
            ...nextPage,
            items: mergeById(current.items, nextPage.items),
          }
        : nextPage,
    );

    try {
      const hydratedContacts = await hydrateLinkedContacts(
        nextPage.items,
        currentContacts,
        companyId,
        requestOrganisationId,
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        activeRequestKey.current !== requestedKey
      )
        return;
      setContacts((current) =>
        mergeAccountContacts(
          current,
          hydratedContacts,
          companyId,
          requestOrganisationId,
        ),
      );
    } catch {
      // Contact names are optional enrichment; the conversation page is kept.
    } finally {
      finish();
    }
  }

  if (verifiedOrganisation.status === "unavailable") {
    return (
      <section className="form-card" role="alert">
        Account conversations are unavailable until the active organisation is
        verified. Reload the page to try again.
      </section>
    );
  }

  return (
    <section
      id="conversations"
      aria-labelledby="account-conversations-title"
      className="scroll-mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-secondary">
            Relationship memory
          </p>
          <h2
            id="account-conversations-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            Conversations and notes
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Meetings, calls, private notes and preparation linked to this
            account.
          </p>
        </div>
        <Link
          className="primary-button shrink-0"
          href={"/conversations/new?companyId=" + encodeURIComponent(companyId)}
        >
          Add conversation
        </Link>
      </div>

      {interactions === null && !currentError ? (
        <p role="status" className="mt-6 text-sm text-slate-600">
          Loading account conversations…
        </p>
      ) : null}
      {currentError ? (
        <div
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-5"
        >
          <p className="text-sm text-red-900">{currentError}</p>
          <button
            type="button"
            className="secondary-button mt-4"
            onClick={() => {
              setResult(null);
              setError(null);
              setLoadMoreError(null);
              setLoadingMoreRequestKey(null);
              setRetryKey((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      {interactions?.length === 0 ? (
        <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <h3 className="font-semibold text-slate-950">
            No account conversations yet
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Add the first meeting, call or note to start this account history.
          </p>
        </div>
      ) : null}
      {interactions && interactions.length > 0 ? (
        <div className="mt-6 space-y-4">
          <div className="grid gap-4 xl:grid-cols-2">
            {interactions.map((interaction) => (
              <InteractionCard
                key={interaction.id}
                interaction={interaction}
                contactName={
                  interaction.contactId
                    ? (contactNames.get(interaction.contactId) ??
                      "Linked contact")
                    : null
                }
              />
            ))}
          </div>
          {currentResult && currentResult.page < currentResult.pages ? (
            <button
              type="button"
              className="secondary-button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
            >
              {loadingMore ? "Loading more…" : "Load more conversations"}
            </button>
          ) : null}
          {currentLoadMoreError ? (
            <p
              role="alert"
              className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
            >
              {currentLoadMoreError}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function accountInteractionPath(companyId: string, page = 1): string {
  const parameters = new URLSearchParams({
    page: String(page),
    pageSize: "100",
    sortBy: "start_at",
    sortOrder: "desc",
    companyId,
  });
  return "/api/v1/interactions?" + parameters.toString();
}

async function hydrateLinkedContacts(
  interactions: Interaction[],
  contacts: Contact[],
  companyId: string,
  organisationId: string,
  signal?: AbortSignal,
): Promise<Contact[]> {
  const accountContacts = contacts.filter((contact) =>
    isAvailableAccountContact(contact, companyId, organisationId),
  );
  const knownIds = new Set(accountContacts.map((contact) => contact.id));
  const missingIds = [
    ...new Set(
      interactions
        .map((interaction) => interaction.contactId)
        .filter((value): value is string => Boolean(value)),
    ),
  ].filter((contactId) => !knownIds.has(contactId));
  const linkedContactResults = await Promise.allSettled(
    missingIds.map((contactId) =>
      apiRequest<unknown>(
        "/api/v1/contacts/" + encodeURIComponent(contactId),
        signal ? { signal } : undefined,
      ).then((value) => ({ contactId, value })),
    ),
  );
  const mismatched = linkedContactResults.some(
    (result) =>
      result.status === "fulfilled" &&
      (!isContactResponse(result.value.value, organisationId) ||
        result.value.value.id !== result.value.contactId ||
        !isAvailableAccountContact(
          result.value.value,
          companyId,
          organisationId,
        )),
  );
  if (mismatched) return accountContacts;
  const linkedContacts = linkedContactResults.flatMap((result) =>
    result.status === "fulfilled" &&
    isContactResponse(result.value.value, organisationId) &&
    result.value.value.id === result.value.contactId &&
    isAvailableAccountContact(result.value.value, companyId, organisationId)
      ? [result.value.value]
      : [],
  );
  return mergeById(accountContacts, linkedContacts);
}

function mergeAccountContacts(
  current: Contact[],
  additions: Contact[],
  companyId: string,
  organisationId: string,
): Contact[] {
  return mergeById(
    current.filter((contact) =>
      isAvailableAccountContact(contact, companyId, organisationId),
    ),
    additions.filter((contact) =>
      isAvailableAccountContact(contact, companyId, organisationId),
    ),
  );
}

function isAvailableAccountContact(
  contact: Contact,
  companyId: string,
  organisationId: string,
): boolean {
  return (
    contact.organisationId === organisationId &&
    contact.companyId === companyId &&
    contact.archivedAt === null
  );
}

function interactionsBelongToAccount(
  interactions: Interaction[],
  companyId: string,
  organisationId: string,
): boolean {
  return interactions.every(
    (interaction) =>
      interaction.organisationId === organisationId &&
      interaction.companyId === companyId,
  );
}

function mergeById<T extends { id: string }>(
  current: T[],
  additions: T[],
): T[] {
  const merged = new Map(current.map((item) => [item.id, item]));
  for (const item of additions) merged.set(item.id, item);
  return [...merged.values()];
}
