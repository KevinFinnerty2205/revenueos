"use client";

import type { Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { ConversationMemory } from "@/components/conversation-memory";
import { FaceToFaceCompanion } from "@/components/face-to-face-companion";
import { InteractionDetail } from "@/components/interaction-detail";
import { PreInteractionBrief } from "@/components/pre-interaction-brief";
import { apiRequest } from "@/lib/api";
import { formatInteractionDate } from "@/lib/interactions";

export type ConversationView = "prepare" | "capture" | "review" | "history";

const views: { id: ConversationView; label: string }[] = [
  { id: "prepare", label: "Preparation" },
  { id: "capture", label: "Notes & capture" },
  { id: "review", label: "Review & follow-up" },
  { id: "history", label: "Relationship history" },
];

export function ConversationWorkspace({
  interactionId,
  initialView,
}: {
  interactionId: string;
  initialView?: ConversationView;
}) {
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [view, setView] = useState<ConversationView>(initialView ?? "prepare");
  const [opened, setOpened] = useState<Set<ConversationView>>(new Set());
  const [briefRefreshKey, setBriefRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<Interaction>(`/api/v1/interactions/${interactionId}`, {
      signal: controller.signal,
    })
      .then((loaded) => {
        if (controller.signal.aborted) return;
        setInteraction(loaded);
        setError(null);
        const hash = window.location.hash;
        const selected =
          initialView ??
          (hash === "#preparation"
            ? "prepare"
            : ["#debrief", "#enhanced-notes"].includes(hash)
              ? "review"
              : loaded.lifecycleStatus === "completed"
                ? "review"
                : loaded.lifecycleStatus === "in_progress" ||
                    loaded.interactionType === "manual_interaction"
                  ? "capture"
                  : "prepare");
        setView(selected);
        setOpened(new Set([selected]));
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "This conversation could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [initialView, interactionId, retryKey]);

  function select(next: ConversationView) {
    setView(next);
    setOpened((current) => new Set([...current, next]));
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  }

  if (!interaction || interaction.id !== interactionId) {
    return error ? (
      <div role="alert" className="form-card">
        <p>{error}</p>
        <button
          type="button"
          className="secondary-button mt-3"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </div>
    ) : (
      <p role="status">Loading conversation…</p>
    );
  }

  return (
    <section aria-labelledby="conversation-title" className="space-y-6">
      <header>
        <Link
          className="text-sm font-bold text-brand-secondary hover:underline"
          href={
            interaction.companyId
              ? `/conversations/accounts/${interaction.companyId}`
              : "/conversations"
          }
        >
          Back to conversations
        </Link>
        <h1
          id="conversation-title"
          className="mt-4 text-3xl font-semibold tracking-tight text-brand-primary"
        >
          {interaction.title}
        </h1>
        <p className="mt-2 text-sm text-brand-muted">
          {formatInteractionDate(
            interaction.actualStartAt ?? interaction.scheduledStartAt,
          )}
        </p>
        {interaction.interactionType === "online_meeting" &&
        interaction.meetingUrl ? (
          <a
            className="secondary-button mt-4 inline-flex"
            href={interaction.meetingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open meeting
          </a>
        ) : null}
      </header>

      <nav
        aria-label="Conversation sections"
        className="flex flex-wrap gap-2 border-b border-brand-primary/10 pb-3"
      >
        {views.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={view === item.id}
            onClick={() => select(item.id)}
            className={view === item.id ? "primary-button" : "secondary-button"}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {/* Visited panels stay mounted so capture and unsaved private notes survive section changes. */}
      {opened.has("prepare") ? (
        <div hidden={view !== "prepare"}>
          <BetaFeatureGate feature="aiCompanion">
            <PreInteractionBrief
              interactionId={interaction.id}
              interactionType={interaction.interactionType}
              onBriefChange={() => setBriefRefreshKey((value) => value + 1)}
            />
          </BetaFeatureGate>
          <button
            type="button"
            className="primary-button mt-5"
            onClick={() => select("capture")}
          >
            Open notes & capture
          </button>
        </div>
      ) : null}

      {opened.has("capture") ? (
        <div hidden={view !== "capture"}>
          <FaceToFaceCompanion
            interactionId={interaction.id}
            initialInteraction={interaction}
            embedded
            onInteractionChange={setInteraction}
            onOpenPreparation={() => select("prepare")}
            onOpenReview={() => select("review")}
            briefRefreshKey={briefRefreshKey}
          />
        </div>
      ) : null}

      {opened.has("review") ? (
        <div hidden={view !== "review"}>
          <InteractionDetail
            key={interaction.lifecycleStatus}
            interactionId={interaction.id}
            reviewOnly
            onOpenCapture={() => select("capture")}
          />
        </div>
      ) : null}

      {opened.has("history") ? (
        <div hidden={view !== "history"}>
          <ConversationMemory
            interactionId={interaction.id}
            companyId={interaction.companyId}
          />
        </div>
      ) : null}
    </section>
  );
}
