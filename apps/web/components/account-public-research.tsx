"use client";

import type { ProspectAccountResearchLink } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiClientError, apiRequest } from "@/lib/api";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export function AccountPublicResearch({ companyId }: { companyId: string }) {
  const [state, setState] = useState<ResearchState>({
    companyId,
    status: "loading",
  });
  const requestSequence = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    apiRequest<ProspectAccountResearchLink>(
      `/api/v1/prospect/accounts/${encodeURIComponent(companyId)}/research-link`,
      { signal: controller.signal },
    )
      .then((research) => {
        if (
          controller.signal.aborted ||
          requestSequence.current !== requestId
        ) {
          return;
        }
        if (research.companyId !== companyId) {
          setState({ companyId, status: "unavailable" });
          return;
        }
        setState({ companyId, status: "available", research });
      })
      .catch((reason: unknown) => {
        if (
          controller.signal.aborted ||
          requestSequence.current !== requestId ||
          (reason instanceof DOMException && reason.name === "AbortError")
        ) {
          return;
        }
        if (
          reason instanceof ApiClientError &&
          (reason.status === 403 || reason.status === 404)
        ) {
          setState({ companyId, status: "unavailable" });
          return;
        }
        setState({ companyId, status: "unavailable" });
      });
    return () => {
      controller.abort();
      if (requestSequence.current === requestId) {
        requestSequence.current += 1;
      }
    };
  }, [companyId]);

  const visibleState: ResearchState =
    state.companyId === companyId ? state : { companyId, status: "loading" };

  if (visibleState.status !== "available") return null;

  const { research } = visibleState;

  return (
    <section
      aria-labelledby="account-public-research-title"
      className="mb-7 flex flex-col gap-4 rounded-2xl border border-sky-200 bg-sky-50/70 p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.15em] text-sky-800">
          Separate from customer evidence
        </p>
        <h2
          id="account-public-research-title"
          className="mt-1 text-lg font-semibold text-slate-950"
        >
          Public research
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Updated {formatDate(research.updatedAt)} ·{" "}
          {research.status === "partial"
            ? "Research incomplete"
            : "Research ready"}
        </p>
      </div>
      <Link
        href={`/find/${encodeURIComponent(research.targetId)}`}
        className="secondary-button shrink-0"
      >
        View research
      </Link>
    </section>
  );
}

type ResearchState =
  | { companyId: string; status: "loading" | "unavailable" }
  | {
      companyId: string;
      status: "available";
      research: ProspectAccountResearchLink;
    };
