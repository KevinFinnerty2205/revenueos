"use client";

import type { Contact, EntityPage, Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { InteractionCard } from "@/components/interaction-card";
import { apiRequest } from "@/lib/api";

export function AccountConversationPanel({ companyId }: { companyId: string }) {
  const [loadedCompanyId, setLoadedCompanyId] = useState(companyId);
  const [result, setResult] = useState<EntityPage<Interaction> | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingMoreCompanyId, setLoadingMoreCompanyId] = useState<
    string | null
  >(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const activeCompanyId = useRef(companyId);
  const loadMoreController = useRef<AbortController | null>(null);

  useEffect(() => {
    activeCompanyId.current = companyId;
    loadMoreController.current?.abort();
    const controller = new AbortController();
    const encodedCompanyId = encodeURIComponent(companyId);
    async function loadAccountConversations() {
      let interactionPage: EntityPage<Interaction>;
      try {
        interactionPage = await apiRequest<EntityPage<Interaction>>(
          accountInteractionPath(companyId),
          { signal: controller.signal },
        );
      } catch (reason: unknown) {
        if (
          controller.signal.aborted ||
          (reason instanceof DOMException && reason.name === "AbortError")
        )
          return;
        setLoadedCompanyId(companyId);
        setResult(null);
        setContacts([]);
        setLoadMoreError(null);
        setError(
          reason instanceof Error
            ? reason.message
            : "Account conversations could not be loaded.",
        );
        return;
      }

      if (controller.signal.aborted) return;
      setLoadedCompanyId(companyId);
      setContacts([]);
      setResult(interactionPage);
      setError(null);
      setLoadMoreError(null);

      let listedContacts: Contact[] = [];
      try {
        const contactPage = await apiRequest<EntityPage<Contact>>(
          "/api/v1/contacts?pageSize=100&companyId=" + encodedCompanyId,
          { signal: controller.signal },
        );
        listedContacts = contactPage.items;
      } catch {
        if (controller.signal.aborted) return;
      }

      const hydratedContacts = await hydrateLinkedContacts(
        interactionPage.items,
        listedContacts,
        companyId,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setContacts((current) =>
        mergeAccountContacts(current, hydratedContacts, companyId),
      );
    }

    void loadAccountConversations();
    return () => {
      controller.abort();
      loadMoreController.current?.abort();
    };
  }, [companyId, retryKey]);

  const accountIsCurrent = loadedCompanyId === companyId;
  const currentResult = accountIsCurrent ? result : null;
  const currentContacts = accountIsCurrent ? contacts : [];
  const currentError = accountIsCurrent ? error : null;
  const currentLoadMoreError = accountIsCurrent ? loadMoreError : null;
  const loadingMore = loadingMoreCompanyId === companyId;
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
    const requestedCompanyId = companyId;
    const controller = new AbortController();
    loadMoreController.current?.abort();
    loadMoreController.current = controller;
    setLoadingMoreCompanyId(requestedCompanyId);
    setLoadMoreError(null);
    const finish = () => {
      if (loadMoreController.current !== controller) return;
      loadMoreController.current = null;
      setLoadingMoreCompanyId((current) =>
        current === requestedCompanyId ? null : current,
      );
    };
    let nextPage: EntityPage<Interaction>;
    try {
      nextPage = await apiRequest<EntityPage<Interaction>>(
        accountInteractionPath(companyId, currentResult.page + 1),
        { signal: controller.signal },
      );
    } catch (reason: unknown) {
      if (
        !controller.signal.aborted &&
        activeCompanyId.current === requestedCompanyId
      ) {
        setLoadMoreError(
          reason instanceof Error
            ? reason.message
            : "More account conversations could not be loaded.",
        );
      }
      finish();
      return;
    }

    if (
      controller.signal.aborted ||
      activeCompanyId.current !== requestedCompanyId
    ) {
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
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        activeCompanyId.current !== requestedCompanyId
      )
        return;
      setContacts((current) =>
        mergeAccountContacts(current, hydratedContacts, companyId),
      );
    } catch {
      // Contact names are optional enrichment; the conversation page is kept.
    } finally {
      finish();
    }
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
              setLoadingMoreCompanyId(null);
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
  signal?: AbortSignal,
): Promise<Contact[]> {
  const accountContacts = contacts.filter((contact) =>
    isAvailableAccountContact(contact, companyId),
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
      apiRequest<Contact>(
        "/api/v1/contacts/" + encodeURIComponent(contactId),
        signal ? { signal } : undefined,
      ),
    ),
  );
  const linkedContacts = linkedContactResults.flatMap((result) =>
    result.status === "fulfilled" &&
    isAvailableAccountContact(result.value, companyId)
      ? [result.value]
      : [],
  );
  return mergeById(accountContacts, linkedContacts);
}

function mergeAccountContacts(
  current: Contact[],
  additions: Contact[],
  companyId: string,
): Contact[] {
  return mergeById(
    current.filter((contact) => isAvailableAccountContact(contact, companyId)),
    additions.filter((contact) =>
      isAvailableAccountContact(contact, companyId),
    ),
  );
}

function isAvailableAccountContact(
  contact: Contact,
  companyId: string,
): boolean {
  return contact.companyId === companyId && contact.archivedAt === null;
}

function mergeById<T extends { id: string }>(
  current: T[],
  additions: T[],
): T[] {
  const merged = new Map(current.map((item) => [item.id, item]));
  for (const item of additions) merged.set(item.id, item);
  return [...merged.values()];
}
