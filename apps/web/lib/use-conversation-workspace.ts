"use client";

import type { ConversationWorkspaceResponse } from "@revenueos/shared";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClientError, apiRequest } from "@/lib/api";

export type WorkspaceSaveState =
  "idle" | "saving" | "saved" | "failed" | "conflict";

interface WorkspaceValues {
  enhancedNotes: string;
  followUpDraft: string;
  followUpReviewed: boolean;
}

export function useConversationWorkspace({
  interactionId,
  initialEnhancedNotes = "",
  initialFollowUpDraft = "",
}: {
  interactionId: string;
  initialEnhancedNotes?: string;
  initialFollowUpDraft?: string;
}) {
  const [workspace, setWorkspace] =
    useState<ConversationWorkspaceResponse | null>(null);
  const defaults = useRef({
    enhancedNotes: initialEnhancedNotes,
    followUpDraft: initialFollowUpDraft,
  });
  const [values, setValues] = useState<WorkspaceValues>({
    enhancedNotes: initialEnhancedNotes,
    followUpDraft: initialFollowUpDraft,
    followUpReviewed: false,
  });
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<WorkspaceSaveState>("idle");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace`,
      );
      setWorkspace(response);
      setValues({
        enhancedNotes: response.exists
          ? (response.enhancedNotes ?? "")
          : defaults.current.enhancedNotes,
        followUpDraft: response.exists
          ? (response.followUpDraft ?? "")
          : defaults.current.followUpDraft,
        followUpReviewed: response.followUpReviewed,
      });
      setSaveState("idle");
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
  }, [load]);

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

  return {
    workspace,
    values,
    setValues,
    loading,
    saveState,
    error,
    save,
    reload: load,
  };
}
