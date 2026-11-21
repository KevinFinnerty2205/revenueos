"use client";

import type { Company, Contact } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AccountAvatar } from "@/components/account-avatar";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { apiRequest, ApiClientError } from "@/lib/api";
import {
  decodeTenantPage,
  isCompanyResponse,
  isContactResponse,
} from "@/lib/private-response-identity";

type CompanyState =
  | { requestKey: string; status: "loading" }
  | { requestKey: string; status: "available"; company: Company }
  | { requestKey: string; status: "failed"; message: string };

type ParticipantState =
  | { requestKey: string; status: "loading" }
  | { requestKey: string; status: "available"; participants: Contact[] }
  | { requestKey: string; status: "unavailable" };

export function AccountRelationshipHeader({
  companyId,
}: {
  companyId: string;
}) {
  const verifiedOrganisation = useVerifiedOrganisation();
  const organisationId = verifiedOrganisation.organisationId;
  const requestKey = `${organisationId ?? "unverified"}:${companyId}`;
  const [companyState, setCompanyState] = useState<CompanyState>({
    requestKey,
    status: "loading",
  });
  const [participantState, setParticipantState] = useState<ParticipantState>({
    requestKey,
    status: "loading",
  });
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!organisationId) return;
    const controller = new AbortController();
    const encodedCompanyId = encodeURIComponent(companyId);
    const contactQuery = new URLSearchParams({
      companyId,
      page: "1",
      pageSize: "100",
      sortBy: "last_name",
      sortOrder: "asc",
    });

    void apiRequest<unknown>(`/api/v1/companies/${encodedCompanyId}`, {
      signal: controller.signal,
    })
      .then((payload) => {
        if (controller.signal.aborted) return;
        if (
          !isCompanyResponse(payload, organisationId) ||
          payload.id !== companyId ||
          payload.archivedAt !== null
        ) {
          setCompanyState({
            requestKey,
            status: "failed",
            message: "This account could not be loaded.",
          });
          return;
        }
        setCompanyState({ requestKey, status: "available", company: payload });
      })
      .catch((reason: unknown) => {
        if (
          controller.signal.aborted ||
          (reason instanceof DOMException && reason.name === "AbortError")
        ) {
          return;
        }
        setCompanyState({
          requestKey,
          status: "failed",
          message:
            reason instanceof ApiClientError
              ? reason.message
              : "This account could not be loaded.",
        });
      });

    void apiRequest<unknown>(`/api/v1/contacts?${contactQuery.toString()}`, {
      signal: controller.signal,
    })
      .then((payload) => {
        if (controller.signal.aborted) return;
        const participants = decodeTenantPage(
          payload,
          organisationId,
          isContactResponse,
          { expectedPage: 1 },
        );
        if (
          !participants ||
          participants.items.some(
            (participant) =>
              participant.companyId !== companyId ||
              participant.archivedAt !== null,
          )
        ) {
          setParticipantState({ requestKey, status: "unavailable" });
          return;
        }
        setParticipantState({
          requestKey,
          status: "available",
          participants: participants.items,
        });
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setParticipantState({ requestKey, status: "unavailable" });
      });

    return () => controller.abort();
  }, [companyId, organisationId, requestKey, retryKey]);

  const visibleCompanyState =
    companyState.requestKey === requestKey
      ? companyState
      : ({ requestKey, status: "loading" } satisfies CompanyState);
  const visibleParticipantState =
    participantState.requestKey === requestKey
      ? participantState
      : ({ requestKey, status: "loading" } satisfies ParticipantState);

  if (verifiedOrganisation.status === "unavailable") {
    return (
      <section
        className="rounded-3xl border border-rose-200 bg-rose-50 p-6 sm:p-8"
        role="alert"
      >
        <h1 className="text-2xl font-semibold text-rose-950">
          Oryntela couldn’t verify this workspace.
        </h1>
        <p className="mt-3 text-sm text-rose-900">
          This account cannot be shown until the active organisation is
          verified. Reload the page to try again.
        </p>
      </section>
    );
  }

  if (visibleCompanyState.status === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label="Loading account relationship"
        className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <p role="status" className="text-sm text-slate-600">
          Loading relationship memory…
        </p>
      </section>
    );
  }

  if (visibleCompanyState.status === "failed") {
    return (
      <section
        className="rounded-3xl border border-rose-200 bg-rose-50 p-6 sm:p-8"
        role="alert"
      >
        <h1 className="text-2xl font-semibold text-rose-950">
          Oryntela couldn’t load this account.
        </h1>
        <p className="mt-3 text-sm text-rose-900">
          {visibleCompanyState.message}
        </p>
        <button
          type="button"
          className="secondary-button mt-5"
          onClick={() => {
            setCompanyState({ requestKey, status: "loading" });
            setParticipantState({ requestKey, status: "loading" });
            setRetryKey((value) => value + 1);
          }}
        >
          Try again
        </button>
      </section>
    );
  }

  const { company } = visibleCompanyState;
  const context = [
    company.industry,
    company.location,
    websiteHost(company.website),
  ]
    .filter((value): value is string => Boolean(value))
    .join(" · ");

  return (
    <section className="overflow-hidden rounded-3xl border border-brand-primary/10 bg-white shadow-sm">
      <div className="bg-brand-primary px-6 py-7 text-white sm:px-8 sm:py-9">
        <Link
          className="text-sm font-bold text-slate-200 underline-offset-4 hover:text-white hover:underline focus:outline-none focus:ring-2 focus:ring-brand-accent"
          href="/conversations"
        >
          ← All conversations
        </Link>
        <div className="mt-6 flex items-start gap-4">
          <AccountAvatar
            accountId={company.id}
            name={company.name}
            website={company.website}
          />
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
              Relationship memory
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              {company.name}
            </h1>
            {context ? (
              <p className="mt-2 text-sm leading-6 text-slate-200">{context}</p>
            ) : null}
          </div>
        </div>
        <p className="mt-6 max-w-3xl text-sm leading-6 text-slate-200">
          Conversations, participants and notes stay together here so the next
          conversation starts with the right context.
        </p>
      </div>

      <div className="px-6 py-6 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-secondary">
              Participants
            </p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">
              People in this relationship
            </h2>
          </div>
          {visibleParticipantState.status === "available" ? (
            <p className="text-sm font-semibold text-slate-500">
              {visibleParticipantState.participants.length}{" "}
              {visibleParticipantState.participants.length === 1
                ? "person"
                : "people"}
            </p>
          ) : null}
        </div>

        {visibleParticipantState.status === "loading" ? (
          <p className="mt-5 text-sm text-slate-600" role="status">
            Loading people linked to this account…
          </p>
        ) : null}
        {visibleParticipantState.status === "unavailable" ? (
          <p
            className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950"
            role="status"
          >
            People linked to this account are temporarily unavailable.
          </p>
        ) : null}
        {visibleParticipantState.status === "available" &&
        visibleParticipantState.participants.length ? (
          <ul className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleParticipantState.participants.map((participant) => (
              <li
                key={participant.id}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
              >
                <p className="font-semibold text-slate-950">
                  {participantName(participant)}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {participant.jobTitle ?? "Role not recorded"}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
        {visibleParticipantState.status === "available" &&
        visibleParticipantState.participants.length === 0 ? (
          <p className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            Participants linked to future conversations will appear here.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function participantName(participant: Contact): string {
  return `${participant.firstName} ${participant.lastName}`.trim();
}

function websiteHost(website: string | null): string | null {
  if (!website) return null;
  try {
    return new URL(
      website.startsWith("http://") || website.startsWith("https://")
        ? website
        : `https://${website}`,
    ).hostname.replace(/^www\./u, "");
  } catch {
    return null;
  }
}
