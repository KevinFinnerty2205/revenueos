"use client";

import type { Contact, EntityPage, Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { InteractionCard } from "@/components/interaction-card";
import { apiRequest } from "@/lib/api";

export function AccountConversationPanel({ companyId }: { companyId: string }) {
  const [result, setResult] = useState<EntityPage<Interaction> | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const encodedCompanyId = encodeURIComponent(companyId);
    Promise.all([
      apiRequest<EntityPage<Interaction>>(accountInteractionPath(companyId), {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Contact>>(
        "/api/v1/contacts?pageSize=100&companyId=" + encodedCompanyId,
        { signal: controller.signal },
      ),
    ])
      .then(async ([interactionPage, contactPage]) => {
        const hydratedContacts = await hydrateLinkedContacts(
          interactionPage.items,
          contactPage.items,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setResult(interactionPage);
        setContacts(hydratedContacts);
        setError(null);
        setLoadMoreError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Account conversations could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [companyId, retryKey]);

  const interactions = result?.items ?? null;

  const contactNames = useMemo(
    () =>
      new Map(
        contacts.map((contact) => [
          contact.id,
          contact.firstName + " " + contact.lastName,
        ]),
      ),
    [contacts],
  );

  async function loadMore() {
    if (!result || result.page >= result.pages || loadingMore) return;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const nextPage = await apiRequest<EntityPage<Interaction>>(
        accountInteractionPath(companyId, result.page + 1),
      );
      const hydratedContacts = await hydrateLinkedContacts(
        nextPage.items,
        contacts,
      );
      setContacts(hydratedContacts);
      setResult((current) =>
        current
          ? {
              ...nextPage,
              items: mergeById(current.items, nextPage.items),
            }
          : nextPage,
      );
    } catch (reason: unknown) {
      setLoadMoreError(
        reason instanceof Error
          ? reason.message
          : "More account conversations could not be loaded.",
      );
    } finally {
      setLoadingMore(false);
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

      {interactions === null && !error ? (
        <p role="status" className="mt-6 text-sm text-slate-600">
          Loading account conversations…
        </p>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-5"
        >
          <p className="text-sm text-red-900">{error}</p>
          <button
            type="button"
            className="secondary-button mt-4"
            onClick={() => {
              setResult(null);
              setError(null);
              setLoadMoreError(null);
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
          {result && result.page < result.pages ? (
            <button
              type="button"
              className="secondary-button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
            >
              {loadingMore ? "Loading more…" : "Load more conversations"}
            </button>
          ) : null}
          {loadMoreError ? (
            <p
              role="alert"
              className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
            >
              {loadMoreError}
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
  signal?: AbortSignal,
): Promise<Contact[]> {
  const knownIds = new Set(contacts.map((contact) => contact.id));
  const missingIds = [
    ...new Set(
      interactions
        .map((interaction) => interaction.contactId)
        .filter((value): value is string => Boolean(value)),
    ),
  ].filter((contactId) => !knownIds.has(contactId));
  const linkedContacts = await Promise.all(
    missingIds.map((contactId) =>
      apiRequest<Contact>(
        "/api/v1/contacts/" + encodeURIComponent(contactId),
        signal ? { signal } : undefined,
      ),
    ),
  );
  return mergeById(contacts, linkedContacts);
}

function mergeById<T extends { id: string }>(
  current: T[],
  additions: T[],
): T[] {
  const merged = new Map(current.map((item) => [item.id, item]));
  for (const item of additions) merged.set(item.id, item);
  return [...merged.values()];
}
