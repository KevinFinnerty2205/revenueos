"use client";

import type { ConversationWorkspaceResponse } from "@revenueos/shared";
import {
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiClientError, apiRequest } from "@/lib/api";

export type WorkspaceSaveState =
  "idle" | "saving" | "saved" | "failed" | "conflict";
export type WorkspaceGenerationActionState =
  "idle" | "retrying" | "applying" | "failed";

export interface WorkspaceValues {
  liveNotes: string;
  enhancedNotes: string;
  followUpDraft: string;
  followUpReviewed: boolean;
}

export type WorkspaceDirtyFields = Record<keyof WorkspaceValues, boolean>;

const generationMetadataKeys = [
  "generationState",
  "generationId",
  "generationTranscriptVersion",
  "generationPersonalNotesState",
  "generationFailureCode",
  "generationRetryAvailable",
  "generationUpdateAvailable",
  "generationCompletedAt",
] as const satisfies ReadonlyArray<keyof ConversationWorkspaceResponse>;

function responseValues(
  response: ConversationWorkspaceResponse,
  defaults: Pick<
    WorkspaceValues,
    "liveNotes" | "enhancedNotes" | "followUpDraft"
  >,
): WorkspaceValues {
  return {
    liveNotes: response.liveNotes ?? defaults.liveNotes,
    enhancedNotes: response.enhancedNotes ?? defaults.enhancedNotes,
    followUpDraft: response.followUpDraft ?? defaults.followUpDraft,
    followUpReviewed: response.followUpReviewed,
  };
}

function dirtyFields(
  values: WorkspaceValues,
  baseline: WorkspaceValues,
): WorkspaceDirtyFields {
  return {
    liveNotes: values.liveNotes !== baseline.liveNotes,
    enhancedNotes: values.enhancedNotes !== baseline.enhancedNotes,
    followUpDraft: values.followUpDraft !== baseline.followUpDraft,
    followUpReviewed: values.followUpReviewed !== baseline.followUpReviewed,
  };
}

function mergeGenerationMetadata(
  current: ConversationWorkspaceResponse,
  response: ConversationWorkspaceResponse,
): ConversationWorkspaceResponse {
  const merged = { ...current };
  for (const key of generationMetadataKeys) {
    Object.assign(merged, { [key]: response[key] });
  }
  return merged;
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
  const [values, setValuesState] = useState<WorkspaceValues>({
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
  const [baseline, setBaseline] = useState<WorkspaceValues>({
    liveNotes: initialLiveNotes,
    enhancedNotes: initialEnhancedNotes,
    followUpDraft: initialFollowUpDraft,
    followUpReviewed: false,
  });
  const valuesRevision = useRef(0);
  const setValues = useCallback((update: SetStateAction<WorkspaceValues>) => {
    valuesRevision.current += 1;
    setValuesState(update);
  }, []);

  const fieldsDirty = useMemo(
    () => dirtyFields(values, baseline),
    [baseline, values],
  );
  const isDirty = Object.values(fieldsDirty).some(Boolean);

  const hydrate = useCallback((response: ConversationWorkspaceResponse) => {
    const next = responseValues(response, defaults.current);
    setBaseline(next);
    setWorkspace(response);
    setValuesState(next);
    setSaveState("idle");
    setGenerationActionState("idle");
    setGenerationError(null);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace`,
      );
      hydrate(response);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Your private conversation workspace could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [hydrate, interactionId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<ConversationWorkspaceResponse>(
        `/api/v1/interactions/${interactionId}/personal-workspace`,
      );
      if (!isDirty || workspace === null) {
        hydrate(response);
      } else {
        setWorkspace((current) =>
          current === null
            ? response
            : mergeGenerationMetadata(current, response),
        );
        setGenerationActionState("idle");
        setGenerationError(null);
      }
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Your private conversation workspace could not be refreshed.",
      );
    } finally {
      setLoading(false);
    }
  }, [hydrate, interactionId, isDirty, workspace]);

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
      const requestStartValues = values;
      const requestStartRevision = valuesRevision.current;
      const merged = { ...requestStartValues, ...next };
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
        const savedValues: WorkspaceValues = {
          liveNotes: response.liveNotes ?? merged.liveNotes,
          enhancedNotes: response.enhancedNotes ?? merged.enhancedNotes,
          followUpDraft: response.followUpDraft ?? merged.followUpDraft,
          followUpReviewed: response.followUpReviewed,
        };
        setWorkspace(response);
        setBaseline(savedValues);
        setValuesState((current) =>
          valuesRevision.current === requestStartRevision
            ? savedValues
            : current,
        );
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
      setWorkspace((current) =>
        current === null
          ? response
          : mergeGenerationMetadata(current, response),
      );
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
    const requestStartValues = values;
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
      const appliedValues: WorkspaceValues = {
        liveNotes: response.liveNotes ?? requestStartValues.liveNotes,
        enhancedNotes:
          response.enhancedNotes ?? requestStartValues.enhancedNotes,
        followUpDraft:
          response.followUpDraft ?? requestStartValues.followUpDraft,
        followUpReviewed: response.followUpReviewed,
      };
      setBaseline(appliedValues);
      setValuesState((current) => ({
        // Applying a generated version only owns enhanced notes and follow-up.
        // Rough notes stay local even if they changed before or during the request.
        liveNotes: current.liveNotes,
        enhancedNotes:
          current.enhancedNotes === requestStartValues.enhancedNotes
            ? appliedValues.enhancedNotes
            : current.enhancedNotes,
        followUpDraft:
          current.followUpDraft === requestStartValues.followUpDraft
            ? appliedValues.followUpDraft
            : current.followUpDraft,
        followUpReviewed:
          current.followUpReviewed === requestStartValues.followUpReviewed
            ? appliedValues.followUpReviewed
            : current.followUpReviewed,
      }));
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
  }, [interactionId, values, workspace]);

  return {
    workspace,
    values,
    setValues,
    loading,
    saveState,
    error,
    generationActionState,
    generationError,
    dirtyFields: fieldsDirty,
    isDirty,
    save,
    retryGeneration,
    applyGeneratedVersion,
    refresh,
    reload: load,
  };
}

export type ConversationWorkspaceController = ReturnType<
  typeof useConversationWorkspace
>;
