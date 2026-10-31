"use client";

import type { Contact, EntityPage } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function AccountPeoplePanel({ companyId }: { companyId: string }) {
  const [result, setResult] = useState<{
    companyId: string;
    people: Contact[];
  } | null>(null);
  const [failure, setFailure] = useState<{
    companyId: string;
    message: string;
  } | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const people = result?.companyId === companyId ? result.people : null;
  const error = failure?.companyId === companyId ? failure.message : null;

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({
      companyId,
      page: "1",
      pageSize: "100",
      sortBy: "last_name",
      sortOrder: "asc",
    });
    apiRequest<EntityPage<Contact>>(`/api/v1/contacts?${query.toString()}`, {
      signal: controller.signal,
    })
      .then((response) => {
        setResult({ companyId, people: response.items });
        setFailure(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setFailure({
          companyId,
          message:
            reason instanceof Error
              ? reason.message
              : "The people linked to this account could not be loaded.",
        });
      });
    return () => controller.abort();
  }, [companyId, retryKey]);

  return (
    <section
      aria-labelledby="account-people-title"
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-secondary">
            People
          </p>
          <h2
            id="account-people-title"
            className="mt-1 text-xl font-semibold text-slate-950"
          >
            People at this account
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Review the people linked to this account.
          </p>
        </div>
        <Link
          className="secondary-button"
          href={`/contacts/new?companyId=${encodeURIComponent(companyId)}`}
        >
          Add person
        </Link>
      </div>

      {people === null && error === null ? (
        <p role="status" className="mt-5 text-sm text-slate-600">
          Loading linked people…
        </p>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950"
        >
          <p>{error}</p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => {
              setResult(null);
              setFailure(null);
              setRetryKey((current) => current + 1);
            }}
          >
            Try again
          </button>
        </div>
      ) : null}

      {people?.length === 0 ? (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          No people are linked to this account yet.
        </p>
      ) : null}

      {people && people.length > 0 ? (
        <ul className="mt-5 divide-y divide-slate-200">
          {people.map((person) => {
            const name = `${person.firstName} ${person.lastName}`.trim();
            return (
              <li key={person.id} className="py-4 first:pt-0 last:pb-0">
                <Link
                  href={`/contacts/${person.id}`}
                  className="font-semibold text-brand-primary underline decoration-brand-secondary/40 underline-offset-4 hover:text-brand-secondary"
                >
                  {name}
                </Link>
                <p className="mt-1 text-sm text-slate-600">
                  {person.jobTitle ?? "Role not recorded"}
                  {person.email ? ` · ${person.email}` : ""}
                </p>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
