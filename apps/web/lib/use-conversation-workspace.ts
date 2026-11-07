"use client";

import type { ConversationWorkspaceResponse } from "@revenueos/shared";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClientError, apiRequest } from "@/lib/api";

export type WorkspaceSaveState =
  "idle" | "saving" | "saved" | "failed" | "conflict";
export type WorkspaceGenerationActionState =
  "idle" | "retrying" | "applying" | "failed";

interface WorkspaceValues {
  liveNotes: string;
  enhancedNotes: string;
  followUpDraft: string;
  followUpReviewed: boolean;
}

export function useConversationWorkspace({
  interactionId,
  initialLiveNotes = "",
  initialEnhancedNotes = "",
  initialFollowUpDraft = "",
  refreshKey = 0,
}: {
  interactionId: string;
  initialLiveNotes?: string;
  initialEnhancedNotes?: string;
  initialFollowUpDraft?: string;
  refreshKey?: number;
}) {
  const [workspace, setWorkspace] =
    useState<ConversationWorkspaceResponse | null>(null);
  const defaults = useRef({
    liveNotes: initialLiveNotes,
    enhancedNotes: initialEnhancedNotes,
    followUpDraft: initialFollowUpDraft,
  });
  const [values, setValues] = useState<WorkspaceValues>({
    liveNotes: initialLiveNotes,
    enhancedNotes: initialEnhancedNotes,
    followUpDraft: initialFollowUpDraft,
    followUpReviewed: false,
  });
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<WorkspaceSaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [generationActionState, setGenerationActionState] =
    useState<WorkspaceGenerationActionState>("idle");
  const [generationError, setGenerationError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace`,
      );
      setWorkspace(response);
      setValues({
        liveNotes: response.exists
          ? (response.liveNotes ?? "")
          : defaults.current.liveNotes,
        enhancedNotes: response.exists
          ? (response.enhancedNotes ?? "")
          : defaults.current.enhancedNotes,
        followUpDraft: response.exists
          ? (response.followUpDraft ?? "")
          : defaults.current.followUpDraft,
        followUpReviewed: response.followUpReviewed,
      });
      setSaveState("idle");
      setGenerationActionState("idle");
      setGenerationError(null);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Your private conversation workspace could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [interactionId]);

  useEffect(() => {
    let active = true;
    window.queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
    };
  }, [load, refreshKey]);

  const save = useCallback(
    async (
      next: Partial<WorkspaceValues> = {},
      options: { importFromBrowser?: boolean } = {},
    ) => {
      if (workspace === null) return false;
      const merged = { ...values, ...next };
      setSaveState("saving");
      setError(null);
      try {
        const response = await apiRequest<ConversationWorkspaceResponse>(
          `/api/v1/interactions/${interactionId}/personal-workspace`,
          {
            method: "PUT",
            body: JSON.stringify({
              expectedLockVersion: workspace.lockVersion,
              liveNotes: merged.liveNotes,
              enhancedNotes: merged.enhancedNotes,
              followUpDraft: merged.followUpDraft,
              followUpReviewed: merged.followUpReviewed,
              generationFingerprint: workspace.generationFingerprint,
              importFromBrowser: options.importFromBrowser === true,
            }),
          },
        );
        setWorkspace(response);
        setValues(merged);
        setSaveState("saved");
        return true;
      } catch (reason: unknown) {
        const conflict =
          reason instanceof ApiClientError &&
          reason.code === "conversation_workspace_conflict";
        setSaveState(conflict ? "conflict" : "failed");
        setError(
          reason instanceof Error
            ? reason.message
            : "Your private conversation workspace could not be saved.",
        );
        return false;
      }
    },
    [interactionId, values, workspace],
  );

  const retryGeneration = useCallback(async () => {
    if (workspace === null || !workspace.generationRetryAvailable) return false;
    setGenerationActionState("retrying");
    setGenerationError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace/generation/retry`,
        { method: "POST" },
      );
      setWorkspace(response);
      setGenerationActionState("idle");
      return true;
    } catch (reason: unknown) {
      setGenerationActionState("failed");
      setGenerationError(
        reason instanceof Error
          ? reason.message
          : "Your private post-conversation draft could not be retried.",
      );
      return false;
    }
  }, [interactionId, workspace]);

  const applyGeneratedVersion = useCallback(async () => {
    if (
      workspace === null ||
      workspace.generationId === null ||
      !workspace.generationUpdateAvailable
    ) {
      return false;
    }
    setGenerationActionState("applying");
    setGenerationError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace/generation/apply`,
        {
          method: "POST",
          body: JSON.stringify({
            generationId: workspace.generationId,
            expectedLockVersion: workspace.lockVersion,
          }),
        },
      );
      setWorkspace(response);
      setValues({
        liveNotes: response.liveNotes ?? "",
        enhancedNotes: response.enhancedNotes ?? "",
        followUpDraft: response.followUpDraft ?? "",
        followUpReviewed: response.followUpReviewed,
      });
      setGenerationActionState("idle");
      return true;
    } catch (reason: unknown) {
      const conflict =
        reason instanceof ApiClientError &&
        reason.code === "conversation_workspace_conflict";
      setGenerationActionState("failed");
      setGenerationError(
        conflict
          ? "Your private draft changed in another session. Reload before choosing this generated version."
          : reason instanceof Error
            ? reason.message
            : "The generated private draft version could not be applied.",
      );
      return false;
    }
  }, [interactionId, workspace]);

  return {
    workspace,
    values,
    setValues,
    loading,
    saveState,
    error,
    generationActionState,
    generationError,
    save,
    retryGeneration,
    applyGeneratedVersion,
    reload: load,
  };
}
