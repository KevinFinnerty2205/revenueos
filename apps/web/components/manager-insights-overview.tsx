"use client";

import type { ManagerSummary } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest, ApiClientError } from "@/lib/api";

export function ManagerInsightsOverview() {
  const [data, setData] = useState<ManagerSummary | null>(null);
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const today = localDate();
    const query = new URLSearchParams({ periodAnchor: today, currency: "AUD" });
    apiRequest<ManagerSummary>(`/api/v1/manager/summary?${query.toString()}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!isManagerSummary(value)) {
          setAvailable(false);
          return;
        }
        setData(value);
        setAvailable(true);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError")
          return;
        if (
          caught instanceof ApiClientError &&
          (caught.status === 403 || caught.status === 404)
        )
          setAvailable(false);
      });
    return () => controller.abort();
  }, []);

  if (!available || data === null) return null;
  const target =
    data.organisationTargets.length === 1
      ? (data.organisationTargets[0]?.targetValue ?? null)
      : null;
  return (
    <section
      aria-labelledby="manager-insights-title"
      className="rounded-3xl border border-amber-200 bg-amber-50 p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-800">
            Organisation sales overview
          </p>
          <h2
            id="manager-insights-title"
            className="mt-2 text-xl font-semibold text-slate-950"
          >
            {data.periodLabel} · {data.currency}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Five separate references—there is no blended final forecast.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            className="secondary-button"
            href="/opportunities?view=attention"
          >
            Review deals
          </Link>
          <Link className="secondary-button" href="/insights?tab=forecast">
            Open forecast
          </Link>
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Position
          label="Actual won"
          value={money(data.actual.amount, data.currency)}
          detail="Canonical sales metric"
        />
        <Position
          label="Organisation target"
          value={
            data.organisationTargets.length === 1
              ? money(target, data.currency)
              : data.organisationTargets.length
                ? `${data.organisationTargets.length} matching targets`
                : "Not set"
          }
          detail="Organisation scope only"
        />
        <Position
          label="Seller Likely"
          value={money(data.sellerForecast.likely.amount, data.currency)}
          detail="Commit + Likely"
        />
        <Position
          label="Manager Likely"
          value={money(data.managerForecast.likely.amount, data.currency)}
          detail="Independent review"
        />
        <Position
          label="RevenueOS baseline"
          value={money(
            data.revenueosBaseline.expectedContribution,
            data.currency,
          )}
          detail="Historical stage outcomes"
        />
      </div>
      <p className="mt-4 text-sm text-amber-950">
        <strong>{data.dealsNeedingAttention}</strong> open{" "}
        {data.dealsNeedingAttention === 1 ? "deal matches" : "deals match"}{" "}
        current attention conditions.
      </p>
    </section>
  );
}

function isManagerSummary(value: ManagerSummary): boolean {
  return (
    Array.isArray(value.organisationTargets) &&
    value.sellerForecast !== undefined &&
    value.managerForecast !== undefined
  );
}

function Position({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-amber-200 bg-white p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </article>
  );
}

function money(value: string | null, currency: string) {
  if (value === null) return "Unavailable";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
