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
export type WorkspaceConflictRecoveryState =
  "idle" | "loading" | "ready" | "saving" | "failed";

export interface WorkspaceValues {
  liveNotes: string;
  enhancedNotes: string;
  followUpDraft: string;
  followUpReviewed: boolean;
}

export type WorkspaceDirtyFields = Record<keyof WorkspaceValues, boolean>;

export interface WorkspaceConflictRecovery {
  state: WorkspaceConflictRecoveryState;
  latestWorkspace: ConversationWorkspaceResponse | null;
  latestValues: WorkspaceValues | null;
  submittedValues: WorkspaceValues | null;
  localValuesAtSubmission: WorkspaceValues | null;
  submittedFields: WorkspaceDirtyFields;
  importFromBrowser: boolean;
  error: string | null;
}

interface WorkspaceConflictSubmission {
  values: WorkspaceValues;
  localValues: WorkspaceValues;
  fields: WorkspaceDirtyFields;
  importFromBrowser: boolean;
}

const EMPTY_DIRTY_FIELDS: WorkspaceDirtyFields = {
  liveNotes: false,
  enhancedNotes: false,
  followUpDraft: false,
  followUpReviewed: false,
};

const EMPTY_CONFLICT_RECOVERY: WorkspaceConflictRecovery = {
  state: "idle",
  latestWorkspace: null,
  latestValues: null,
  submittedValues: null,
  localValuesAtSubmission: null,
  submittedFields: EMPTY_DIRTY_FIELDS,
  importFromBrowser: false,
  error: null,
};

const AUTHORITATIVE_EMPTY_VALUES = {
  liveNotes: "",
  enhancedNotes: "",
  followUpDraft: "",
} as const;

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

function applyReviewedValues(
  latest: WorkspaceValues,
  reviewed: Partial<WorkspaceValues>,
): WorkspaceValues {
  const resolved = { ...latest };
  if (reviewed.liveNotes !== undefined) {
    resolved.liveNotes = reviewed.liveNotes;
  }
  if (reviewed.enhancedNotes !== undefined) {
    resolved.enhancedNotes = reviewed.enhancedNotes;
  }
  if (reviewed.followUpDraft !== undefined) {
    resolved.followUpDraft = reviewed.followUpDraft;
    resolved.followUpReviewed = reviewed.followUpReviewed ?? false;
  } else if (reviewed.followUpReviewed !== undefined) {
    resolved.followUpReviewed = reviewed.followUpReviewed;
  }
  return resolved;
}

function submittedFields(
  submitted: WorkspaceValues,
  baseline: WorkspaceValues,
  explicit: Partial<WorkspaceValues>,
): WorkspaceDirtyFields {
  const fields = dirtyFields(submitted, baseline);
  const followUpReviewSubmitted = Object.hasOwn(explicit, "followUpReviewed");
  return {
    liveNotes: fields.liveNotes || Object.hasOwn(explicit, "liveNotes"),
    enhancedNotes:
      fields.enhancedNotes || Object.hasOwn(explicit, "enhancedNotes"),
    followUpDraft:
      fields.followUpDraft ||
      Object.hasOwn(explicit, "followUpDraft") ||
      followUpReviewSubmitted,
    followUpReviewed: fields.followUpReviewed || followUpReviewSubmitted,
  };
}

function submittedValuesPatch(
  submission: WorkspaceConflictSubmission,
): Partial<WorkspaceValues> {
  return {
    ...(submission.fields.liveNotes
      ? { liveNotes: submission.values.liveNotes }
      : {}),
    ...(submission.fields.enhancedNotes
      ? { enhancedNotes: submission.values.enhancedNotes }
      : {}),
    ...(submission.fields.followUpDraft
      ? { followUpDraft: submission.values.followUpDraft }
      : {}),
    ...(submission.fields.followUpReviewed
      ? { followUpReviewed: submission.values.followUpReviewed }
      : {}),
  };
}

function mergeSavedValuesPreservingEdits(
  current: WorkspaceValues,
  requestStart: WorkspaceValues,
  localValuesAtSubmission: WorkspaceValues,
  saved: WorkspaceValues,
): WorkspaceValues {
  const liveNotesChanged =
    requestStart.liveNotes !== localValuesAtSubmission.liveNotes ||
    current.liveNotes !== requestStart.liveNotes;
  const enhancedNotesChanged =
    requestStart.enhancedNotes !== localValuesAtSubmission.enhancedNotes ||
    current.enhancedNotes !== requestStart.enhancedNotes;
  const followUpDraftChanged =
    requestStart.followUpDraft !== localValuesAtSubmission.followUpDraft ||
    current.followUpDraft !== requestStart.followUpDraft;
  const followUpReviewedChanged =
    requestStart.followUpReviewed !==
      localValuesAtSubmission.followUpReviewed ||
    current.followUpReviewed !== requestStart.followUpReviewed;
  return {
    liveNotes: liveNotesChanged ? current.liveNotes : saved.liveNotes,
    enhancedNotes: enhancedNotesChanged
      ? current.enhancedNotes
      : saved.enhancedNotes,
    followUpDraft: followUpDraftChanged
      ? current.followUpDraft
      : saved.followUpDraft,
    followUpReviewed:
      followUpDraftChanged || followUpReviewedChanged
        ? current.followUpReviewed
        : saved.followUpReviewed,
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
  const [conflictRecovery, setConflictRecovery] =
    useState<WorkspaceConflictRecovery>(EMPTY_CONFLICT_RECOVERY);
  const valuesRevision = useRef(0);
  const saveRequestInFlight = useRef(false);
  const loadedInteractionId = useRef<string | null>(null);
  const appliedRefreshKey = useRef(refreshKey);
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
    setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
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
      const preserveLocalValues =
        isDirty ||
        saveState === "saving" ||
        saveState === "conflict" ||
        conflictRecovery.state !== "idle";
      if (workspace === null || !preserveLocalValues) {
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
  }, [
    conflictRecovery.state,
    hydrate,
    interactionId,
    isDirty,
    saveState,
    workspace,
  ]);

  const fetchLatestConflict = useCallback(
    async (submission: WorkspaceConflictSubmission) => {
      setConflictRecovery({
        state: "loading",
        latestWorkspace: null,
        latestValues: null,
        submittedValues: submission.values,
        localValuesAtSubmission: submission.localValues,
        submittedFields: submission.fields,
        importFromBrowser: submission.importFromBrowser,
        error: null,
      });
      try {
        const latestWorkspace = await apiRequest<ConversationWorkspaceResponse>(
          `/api/v1/interactions/${interactionId}/personal-workspace`,
        );
        const latestValues = responseValues(
          latestWorkspace,
          AUTHORITATIVE_EMPTY_VALUES,
        );
        setConflictRecovery({
          state: "ready",
          latestWorkspace,
          latestValues,
          submittedValues: submission.values,
          localValuesAtSubmission: submission.localValues,
          submittedFields: submission.fields,
          importFromBrowser: submission.importFromBrowser,
          error: null,
        });
        return true;
      } catch (reason: unknown) {
        setConflictRecovery({
          state: "failed",
          latestWorkspace: null,
          latestValues: null,
          submittedValues: submission.values,
          localValuesAtSubmission: submission.localValues,
          submittedFields: submission.fields,
          importFromBrowser: submission.importFromBrowser,
          error:
            reason instanceof Error
              ? reason.message
              : "The latest saved workspace could not be loaded. Your local text is still visible.",
        });
        return false;
      }
    },
    [interactionId],
  );

  const loadLatestConflict = useCallback(async () => {
    if (saveState !== "conflict" || conflictRecovery.submittedValues === null) {
      return false;
    }
    return fetchLatestConflict({
      values: conflictRecovery.submittedValues,
      localValues:
        conflictRecovery.localValuesAtSubmission ??
        conflictRecovery.submittedValues,
      fields: conflictRecovery.submittedFields,
      importFromBrowser: conflictRecovery.importFromBrowser,
    });
  }, [conflictRecovery, fetchLatestConflict, saveState]);

  useEffect(() => {
    const interactionChanged = loadedInteractionId.current !== interactionId;
    const refreshRequested = appliedRefreshKey.current !== refreshKey;
    if (!interactionChanged && !refreshRequested) return;

    let active = true;
    window.queueMicrotask(() => {
      if (!active) return;
      loadedInteractionId.current = interactionId;
      appliedRefreshKey.current = refreshKey;
      void (interactionChanged ? load() : refresh());
    });
    return () => {
      active = false;
    };
  }, [interactionId, load, refresh, refreshKey]);

  const save = useCallback(
    async (
      next: Partial<WorkspaceValues> = {},
      options: { importFromBrowser?: boolean } = {},
    ) => {
      if (
        workspace === null ||
        saveRequestInFlight.current ||
        saveState === "saving" ||
        saveState === "conflict" ||
        conflictRecovery.state !== "idle"
      ) {
        return false;
      }
      const requestStartValues = values;
      const requestStartRevision = valuesRevision.current;
      const merged = { ...requestStartValues, ...next };
      const conflictSubmission: WorkspaceConflictSubmission = {
        values: merged,
        localValues: requestStartValues,
        fields: submittedFields(merged, baseline, next),
        importFromBrowser: options.importFromBrowser === true,
      };
      saveRequestInFlight.current = true;
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
        setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
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
        if (conflict) {
          await fetchLatestConflict(conflictSubmission);
        }
        return false;
      } finally {
        saveRequestInFlight.current = false;
      }
    },
    [
      baseline,
      conflictRecovery.state,
      fetchLatestConflict,
      interactionId,
      saveState,
      values,
      workspace,
    ],
  );

  const useLatestConflict = useCallback(() => {
    if (
      conflictRecovery.state !== "ready" ||
      conflictRecovery.latestWorkspace === null ||
      conflictRecovery.latestValues === null
    ) {
      return false;
    }
    valuesRevision.current += 1;
    setWorkspace(conflictRecovery.latestWorkspace);
    setBaseline(conflictRecovery.latestValues);
    setValuesState({ ...conflictRecovery.latestValues });
    setSaveState("idle");
    setError(null);
    setGenerationActionState("idle");
    setGenerationError(null);
    setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
    return true;
  }, [conflictRecovery]);

  const saveReviewedConflict = useCallback(
    async (reviewed: Partial<WorkspaceValues> = {}) => {
      const latestWorkspace = conflictRecovery.latestWorkspace;
      const latestValues = conflictRecovery.latestValues;
      const submittedValues = conflictRecovery.submittedValues;
      const localValuesAtSubmission = conflictRecovery.localValuesAtSubmission;
      if (
        saveRequestInFlight.current ||
        saveState !== "conflict" ||
        conflictRecovery.state !== "ready" ||
        latestWorkspace === null ||
        latestValues === null ||
        submittedValues === null ||
        localValuesAtSubmission === null
      ) {
        return false;
      }
      const requestStartValues = values;
      const reviewedValues = {
        ...submittedValuesPatch({
          values: submittedValues,
          localValues: localValuesAtSubmission,
          fields: conflictRecovery.submittedFields,
          importFromBrowser: conflictRecovery.importFromBrowser,
        }),
        ...reviewed,
      };
      const resolved = applyReviewedValues(latestValues, reviewedValues);
      const conflictSubmission: WorkspaceConflictSubmission = {
        values: resolved,
        localValues: requestStartValues,
        fields: submittedFields(resolved, latestValues, reviewedValues),
        importFromBrowser: conflictRecovery.importFromBrowser,
      };
      saveRequestInFlight.current = true;
      setSaveState("saving");
      setError(null);
      setConflictRecovery({
        state: "saving",
        latestWorkspace,
        latestValues,
        submittedValues: conflictSubmission.values,
        localValuesAtSubmission: conflictSubmission.localValues,
        submittedFields: conflictSubmission.fields,
        importFromBrowser: conflictSubmission.importFromBrowser,
        error: null,
      });
      try {
        const response = await apiRequest<ConversationWorkspaceResponse>(
          `/api/v1/interactions/${interactionId}/personal-workspace`,
          {
            method: "PUT",
            body: JSON.stringify({
              expectedLockVersion: latestWorkspace.lockVersion,
              liveNotes: resolved.liveNotes,
              enhancedNotes: resolved.enhancedNotes,
              followUpDraft: resolved.followUpDraft,
              followUpReviewed: resolved.followUpReviewed,
              generationFingerprint: latestWorkspace.generationFingerprint,
              importFromBrowser: conflictRecovery.importFromBrowser,
            }),
          },
        );
        const savedValues: WorkspaceValues = {
          liveNotes: response.liveNotes ?? resolved.liveNotes,
          enhancedNotes: response.enhancedNotes ?? resolved.enhancedNotes,
          followUpDraft: response.followUpDraft ?? resolved.followUpDraft,
          followUpReviewed: response.followUpReviewed,
        };
        setWorkspace(response);
        setBaseline(savedValues);
        setValuesState((current) =>
          mergeSavedValuesPreservingEdits(
            current,
            requestStartValues,
            localValuesAtSubmission,
            savedValues,
          ),
        );
        setSaveState("saved");
        setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
        return true;
      } catch (reason: unknown) {
        const conflict =
          reason instanceof ApiClientError &&
          reason.code === "conversation_workspace_conflict";
        setSaveState("conflict");
        setError(
          reason instanceof Error
            ? reason.message
            : "Your reviewed conflict resolution could not be saved.",
        );
        if (conflict) {
          await fetchLatestConflict(conflictSubmission);
        } else {
          setConflictRecovery({
            state: "failed",
            latestWorkspace,
            latestValues,
            submittedValues: conflictSubmission.values,
            localValuesAtSubmission: conflictSubmission.localValues,
            submittedFields: conflictSubmission.fields,
            importFromBrowser: conflictSubmission.importFromBrowser,
            error:
              reason instanceof Error
                ? reason.message
                : "Your reviewed conflict resolution could not be saved.",
          });
        }
        return false;
      } finally {
        saveRequestInFlight.current = false;
      }
    },
    [conflictRecovery, fetchLatestConflict, interactionId, saveState, values],
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
    conflictRecovery,
    dirtyFields: fieldsDirty,
    isDirty,
    save,
    loadLatestConflict,
    useLatestConflict,
    saveReviewedConflict,
    retryGeneration,
    applyGeneratedVersion,
    refresh,
    reload: load,
  };
}

export type ConversationWorkspaceController = ReturnType<
  typeof useConversationWorkspace
>;
