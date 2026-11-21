"use client";

import type { Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
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

type ConversationLoadState =
  | { status: "loading" }
  | { status: "available"; interaction: Interaction }
  | { status: "failed"; message: string };

const conversationLoadFailure = "This conversation could not be loaded.";

export function ConversationWorkspace({
  interactionId,
  initialView,
}: {
  interactionId: string;
  initialView?: ConversationView;
}) {
  return (
    <ConversationWorkspaceSession
      key={interactionId}
      interactionId={interactionId}
      initialView={initialView}
    />
  );
}

function ConversationWorkspaceSession({
  interactionId,
  initialView,
}: {
  interactionId: string;
  initialView?: ConversationView;
}) {
  const [loadState, setLoadState] = useState<ConversationLoadState>({
    status: "loading",
  });
  const [view, setView] = useState<ConversationView>(initialView ?? "prepare");
  const [opened, setOpened] = useState<Set<ConversationView>>(new Set());
  const [briefRefreshKey, setBriefRefreshKey] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const active = useRef(true);
  const requestSequence = useRef(0);

  useLayoutEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      requestSequence.current += 1;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const request = requestSequence.current + 1;
    requestSequence.current = request;
    const requestIsCurrent = () =>
      active.current &&
      requestSequence.current === request &&
      !controller.signal.aborted;

    void apiRequest<Interaction>(`/api/v1/interactions/${interactionId}`, {
      signal: controller.signal,
    })
      .then((loaded) => {
        if (!requestIsCurrent()) return;
        if (loaded.id !== interactionId) {
          setLoadState({
            status: "failed",
            message: conversationLoadFailure,
          });
          return;
        }
        setLoadState({ status: "available", interaction: loaded });
        const hash = window.location.hash;
        const selected =
          initialView ??
          (hash === "#preparation"
            ? "prepare"
            : ["#debrief", "#enhanced-notes", "#follow-up"].includes(hash)
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
        if (!requestIsCurrent()) return;
        setLoadState({
          status: "failed",
          message:
            reason instanceof Error ? reason.message : conversationLoadFailure,
        });
      });
    return () => {
      controller.abort();
      if (requestSequence.current === request) {
        requestSequence.current += 1;
      }
    };
  }, [initialView, interactionId, retryKey]);

  function select(next: ConversationView) {
    setView(next);
    setOpened((current) => new Set([...current, next]));
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  }

  function updateInteraction(next: Interaction) {
    if (next.id !== interactionId) {
      setLoadState({ status: "failed", message: conversationLoadFailure });
      return;
    }
    setLoadState({ status: "available", interaction: next });
  }

  if (loadState.status !== "available") {
    return loadState.status === "failed" ? (
      <div role="alert" className="form-card">
        <p>{loadState.message}</p>
        <button
          type="button"
          className="secondary-button mt-3"
          onClick={() => {
            setLoadState({ status: "loading" });
            setRetryKey((value) => value + 1);
          }}
        >
          Try again
        </button>
      </div>
    ) : (
      <p role="status">Loading conversation…</p>
    );
  }

  const { interaction } = loadState;

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
            onInteractionChange={updateInteraction}
            onOpenPreparation={() => select("prepare")}
            onOpenReview={() => select("review")}
            briefRefreshKey={briefRefreshKey}
          />
        </div>
      ) : null}

      {opened.has("review") ? (
        <div hidden={view !== "review"}>
          <InteractionDetail
            key={`${interaction.id}:${interaction.lifecycleStatus}`}
            interactionId={interaction.id}
            initialInteraction={interaction}
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
