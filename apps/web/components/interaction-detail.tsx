"use client";

import type { Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";

export function InteractionDetail({
  interactionId,
}: {
  interactionId: string;
}) {
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Interaction>(`/api/v1/interactions/${interactionId}`, {
      signal: controller.signal,
    })
      .then(setInteraction)
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The interaction could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [interactionId]);

  async function complete() {
    setCompleting(true);
    setError(null);
    try {
      setInteraction(
        await apiRequest<Interaction>(
          `/api/v1/interactions/${interactionId}/complete`,
          { method: "POST", body: "{}" },
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The interaction could not be completed.",
      );
    } finally {
      setCompleting(false);
    }
  }

  if (loading) {
    return <p role="status">Loading interaction…</p>;
  }
  if (!interaction) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900"
      >
        {error ?? "The interaction was not found."}
      </div>
    );
  }

  const canComplete =
    interaction.lifecycleStatus === "planned" ||
    interaction.lifecycleStatus === "in_progress";
  return (
    <section aria-labelledby="interaction-detail-title">
      <Link
        className="text-sm font-bold text-teal-800 hover:underline"
        href="/interactions"
      >
        Back to interactions
      </Link>
      <div className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wide">
          <span className="rounded-full bg-teal-50 px-3 py-1 text-teal-800">
            {humanise(interaction.interactionType)}
          </span>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
            {humanise(interaction.lifecycleStatus)}
          </span>
        </div>
        <h1
          id="interaction-detail-title"
          className="mt-5 text-4xl font-semibold text-slate-950"
        >
          {interaction.title}
        </h1>
        <dl className="mt-8 grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Scheduled
            </dt>
            <dd className="mt-1 text-slate-800">
              {formatInteractionDate(interaction.scheduledStartAt)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Completed
            </dt>
            <dd className="mt-1 text-slate-800">
              {formatInteractionDate(interaction.actualEndAt)}
            </dd>
          </div>
        </dl>
        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-900"
          >
            {error}
          </p>
        ) : null}
        <div className="mt-8 flex flex-wrap gap-3">
          {canComplete ? (
            <button
              type="button"
              className="primary-button"
              disabled={completing}
              onClick={complete}
            >
              {completing ? "Completing…" : "Complete interaction"}
            </button>
          ) : null}
          {interaction.meetingId ? (
            <Link
              className="secondary-button"
              href={`/meetings/${interaction.meetingId}`}
            >
              Open Meeting Intelligence
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}
