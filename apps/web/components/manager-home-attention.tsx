"use client";

import type { ManagerDealAttentionList } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest, ApiClientError } from "@/lib/api";

export function ManagerHomeAttention({
  refreshKey = 0,
}: {
  refreshKey?: number;
}) {
  const [data, setData] = useState<ManagerDealAttentionList | null>(null);
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<ManagerDealAttentionList>(
      "/api/v1/manager/deal-attention?pageSize=5",
      {
        signal: controller.signal,
      },
    )
      .then((value) => {
        if (!isManagerAttention(value)) {
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
        ) {
          setAvailable(false);
          return;
        }
        setData(null);
      });
    return () => controller.abort();
  }, [refreshKey]);

  if (!available || data === null) return null;

  return (
    <section
      aria-labelledby="manager-home-attention-title"
      className="mb-6 rounded-3xl border border-amber-200 bg-amber-50 p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-800">
            Organisation deal review
          </p>
          <h2
            id="manager-home-attention-title"
            className="mt-2 text-xl font-semibold text-slate-950"
          >
            Deals needing attention
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {data.total === 0
              ? "Nothing currently matches the deal-attention conditions."
              : `${data.total} open ${data.total === 1 ? "deal matches" : "deals match"} explainable conditions.`}
          </p>
        </div>
        <Link className="secondary-button" href="/opportunities?view=attention">
          Open manager view
        </Link>
      </div>
      {data.items.length ? (
        <ul className="mt-4 grid gap-3 lg:grid-cols-2">
          {data.items.map((item) => (
            <li
              key={item.opportunityId}
              className="rounded-2xl border border-amber-200 bg-white p-4"
            >
              <Link
                className="font-semibold text-teal-900 hover:underline"
                href={item.href}
              >
                {item.opportunityName}
              </Link>
              <p className="mt-1 text-xs text-slate-500">
                {item.companyName ?? "No account"} · {item.ownerDisplayName} ·{" "}
                {item.stageName}
              </p>
              <p className="mt-2 text-sm font-medium text-amber-950">
                {item.reasons
                  .slice(0, 2)
                  .map((reason) => reason.label)
                  .join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function isManagerAttention(value: ManagerDealAttentionList): boolean {
  return (
    Array.isArray(value.items) &&
    Array.isArray(value.summaries) &&
    typeof value.total === "number"
  );
}
