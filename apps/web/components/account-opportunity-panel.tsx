"use client";

import type { EntityPage, OpportunityListItem } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const PAGE_SIZE = 20;

export function AccountOpportunityPanel({ companyId }: { companyId: string }) {
  const [result, setResult] = useState<{
    companyId: string;
    opportunities: OpportunityListItem[];
    total: number;
  } | null>(null);
  const [failure, setFailure] = useState<{
    companyId: string;
    message: string;
  } | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const opportunities =
    result?.companyId === companyId ? result.opportunities : null;
  const error = failure?.companyId === companyId ? failure.message : null;

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({
      companyId,
      status: "open",
      page: "1",
      pageSize: String(PAGE_SIZE),
      sortBy: "updated_at",
      sortOrder: "desc",
    });
    apiRequest<EntityPage<OpportunityListItem>>(
      `/api/v1/opportunities?${query.toString()}`,
      { signal: controller.signal },
    )
      .then((response) => {
        setResult({
          companyId,
          opportunities: response.items,
          total: response.total,
        });
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
              : "The open Opportunities linked to this Account could not be loaded.",
        });
      });
    return () => controller.abort();
  }, [companyId, retryKey]);

  return (
    <section
      aria-labelledby="account-opportunities-title"
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-secondary">
            Opportunity workflow
          </p>
          <h2
            id="account-opportunities-title"
            className="mt-1 text-xl font-semibold text-slate-950"
          >
            Open Opportunities
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Continue the active sales work linked to this Account.
          </p>
        </div>
        <Link
          className="secondary-button"
          href={`/opportunities/new?companyId=${encodeURIComponent(companyId)}`}
        >
          Add Opportunity
        </Link>
      </div>

      {opportunities === null && error === null ? (
        <p role="status" className="mt-5 text-sm text-slate-600">
          Loading open Opportunities…
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

      {opportunities?.length === 0 ? (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          No open Opportunities are linked to this Account yet.
        </p>
      ) : null}

      {opportunities && opportunities.length > 0 ? (
        <>
          <ul className="mt-5 divide-y divide-slate-200">
            {opportunities.map((opportunity) => (
              <li key={opportunity.id} className="py-4 first:pt-0 last:pb-0">
                <Link
                  href={`/opportunities/${opportunity.id}`}
                  className="font-semibold text-brand-primary underline decoration-brand-secondary/40 underline-offset-4 hover:text-brand-secondary"
                >
                  {opportunity.name}
                </Link>
                <p className="mt-1 text-sm text-slate-600">
                  {humanise(opportunity.stage)} · {opportunity.ownerName}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {formatValue(
                    opportunity.estimatedValue,
                    opportunity.currency,
                  )}
                  {" · "}Expected close{" "}
                  {formatDate(opportunity.expectedCloseDate)}
                </p>
              </li>
            ))}
          </ul>
          {result && result.total > opportunities.length ? (
            <p className="mt-5 border-t border-slate-200 pt-4 text-sm text-slate-600">
              Showing {opportunities.length} of {result.total} open
              Opportunities.{" "}
              <Link
                href="/opportunities"
                className="font-semibold text-brand-primary underline underline-offset-4"
              >
                View the full Pipeline
              </Link>
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function formatValue(value: string | null, currency: string | null) {
  if (!value || !currency) return "Value not set";
  const currencyCode = currency.toUpperCase();
  const amount = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: currencyCode,
    currencyDisplay: "narrowSymbol",
    maximumFractionDigits: 0,
  }).format(Number(value));
  return `${currencyCode} ${amount}`;
}

function formatDate(value: string | null) {
  if (!value) return "not set";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}
