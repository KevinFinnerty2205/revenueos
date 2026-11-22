"use client";

import type { Interaction } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BetaFeatureGate } from "@/components/beta-feature-gate";
import { ConversationMemory } from "@/components/conversation-memory";
import { FaceToFaceCompanion } from "@/components/face-to-face-companion";
import { InteractionDetail } from "@/components/interaction-detail";
import { PreInteractionBrief } from "@/components/pre-interaction-brief";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { apiRequest } from "@/lib/api";
import { decodeInteractionResponse } from "@/lib/interaction-response-identity";
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
const conversationUpdateFailure =
  "Notes & capture returned an unexpected conversation update. Your verified conversation and private notes are unchanged.";

export function ConversationWorkspace({
  interactionId,
  initialView,
}: {
  interactionId: string;
  initialView?: ConversationView;
}) {
  const verifiedOrganisation = useVerifiedOrganisation();
  if (verifiedOrganisation.status === "loading") {
    return <p role="status">Verifying your secure workspace…</p>;
  }
  if (verifiedOrganisation.status !== "available") {
    return (
      <section role="alert" className="form-card">
        <p>
          Your identity could not be verified. This conversation is temporarily
          unavailable.
        </p>
        <button
          type="button"
          className="secondary-button mt-3"
          onClick={verifiedOrganisation.reload}
        >
          Try again
        </button>
      </section>
    );
  }
  return (
    <ConversationWorkspaceSession
      key={`${interactionId}:${verifiedOrganisation.organisationId}:${verifiedOrganisation.userId}:${verifiedOrganisation.identityKey}`}
      interactionId={interactionId}
      initialView={initialView}
      organisationId={verifiedOrganisation.organisationId}
    />
  );
}

function ConversationWorkspaceSession({
  interactionId,
  initialView,
  organisationId,
}: {
  interactionId: string;
  initialView?: ConversationView;
  organisationId: string;
}) {
  const [loadState, setLoadState] = useState<ConversationLoadState>({
    status: "loading",
  });
  const [view, setView] = useState<ConversationView>(initialView ?? "prepare");
  const [opened, setOpened] = useState<Set<ConversationView>>(new Set());
  const [briefRefreshKey, setBriefRefreshKey] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [interactionWarning, setInteractionWarning] = useState<string | null>(
    null,
  );
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

    void apiRequest<unknown>(
      `/api/v1/interactions/${encodeURIComponent(interactionId)}`,
      {
        signal: controller.signal,
      },
    )
      .then((loaded) => {
        if (!requestIsCurrent()) return;
        const decoded = decodeInteractionResponse(loaded, {
          interactionId,
          organisationId,
        });
        if (decoded === null) {
          setLoadState({
            status: "failed",
            message: conversationLoadFailure,
          });
          return;
        }
        setInteractionWarning(null);
        setLoadState({ status: "available", interaction: decoded });
        const hash = window.location.hash;
        const selected =
          initialView ??
          (hash === "#preparation"
            ? "prepare"
            : ["#debrief", "#enhanced-notes", "#follow-up"].includes(hash)
              ? "review"
              : decoded.lifecycleStatus === "completed"
                ? "review"
                : decoded.lifecycleStatus === "in_progress" ||
                    decoded.interactionType === "manual_interaction"
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
  }, [initialView, interactionId, organisationId, retryKey]);

  function select(next: ConversationView) {
    setView(next);
    setOpened((current) => new Set([...current, next]));
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  }

  function updateInteraction(next: unknown) {
    if (loadState.status !== "available") return;
    const decoded = decodeInteractionResponse(next, {
      interactionId,
      organisationId,
      baseline: loadState.interaction,
    });
    if (decoded === null) {
      setInteractionWarning(conversationUpdateFailure);
      return;
    }
    setInteractionWarning(null);
    setLoadState({ status: "available", interaction: decoded });
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

      {interactionWarning ? (
        <p
          role="alert"
          className="rounded-xl bg-red-50 p-4 text-sm text-red-900"
        >
          {interactionWarning}
        </p>
      ) : null}

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
            organisationId={interaction.organisationId}
            companyId={interaction.companyId}
          />
        </div>
      ) : null}
    </section>
  );
}
