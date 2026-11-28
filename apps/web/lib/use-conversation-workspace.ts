"use client";

import type { ConversationWorkspaceResponse } from "@revenueos/shared";
import {
  type SetStateAction,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useVerifiedOrganisation } from "@/components/verified-organisation-context";
import { ApiClientError, apiRequest } from "@/lib/api";
import {
  decodeConversationWorkspaceResponse,
  decodeConversationWorkspaceSaveResponse,
} from "@/lib/conversation-workspace-response";

export type WorkspaceSaveState =
  "idle" | "saving" | "saved" | "failed" | "conflict";
export type WorkspaceGenerationActionState =
  "idle" | "retrying" | "applying" | "failed" | "refresh_required";
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

const SAFE_WORKSPACE_IDENTITY_ERROR =
  "Your private conversation workspace response could not be verified. Your local changes are still safe.";
const SAFE_WORKSPACE_SAVE_ERROR =
  "Your private workspace save could not be verified. Your local changes are still safe.";

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

interface WorkspaceSession {
  interactionId: string;
  organisationId: string;
  ownerUserId: string;
  epoch: symbol;
}

interface WorkspaceOperationToken extends WorkspaceSession {
  token: number;
}

interface WorkspaceReadRequest extends WorkspaceSession {
  sequence: number;
  controller: AbortController;
}

interface CommittedWorkspaceState {
  owner: WorkspaceSession | null;
  workspace: ConversationWorkspaceResponse | null;
  values: WorkspaceValues;
  baseline: WorkspaceValues;
  saveState: WorkspaceSaveState;
  generationActionState: WorkspaceGenerationActionState;
  conflictRecovery: WorkspaceConflictRecovery;
}

interface InitialDefaultsBinding {
  owner: {
    interactionId: string;
    organisationId: string;
    ownerUserId: string;
  } | null;
  invalidated: boolean;
}

function sameWorkspaceSession(
  left: WorkspaceSession,
  right: WorkspaceSession,
): boolean {
  return (
    left.interactionId === right.interactionId &&
    left.organisationId === right.organisationId &&
    left.ownerUserId === right.ownerUserId &&
    left.epoch === right.epoch
  );
}

function workspacePath(session: WorkspaceSession): string {
  return `/api/v1/interactions/${encodeURIComponent(session.interactionId)}/personal-workspace`;
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
  const verifiedIdentity = useVerifiedOrganisation();
  const identityAvailable = verifiedIdentity.status === "available";
  const organisationId = identityAvailable
    ? verifiedIdentity.organisationId
    : "";
  const ownerUserId = identityAvailable ? verifiedIdentity.userId : "";
  const renderSession = useMemo<WorkspaceSession>(
    () => ({
      interactionId,
      organisationId,
      ownerUserId,
      epoch: Symbol(`${interactionId}:${organisationId}:${ownerUserId}`),
    }),
    [interactionId, organisationId, ownerUserId],
  );
  const activeSession = useRef<WorkspaceSession>(renderSession);
  const [initialDefaults] = useState(() => ({
    interactionId,
    identityKey: verifiedIdentity.identityKey,
    values: {
      liveNotes: initialLiveNotes,
      enhancedNotes: initialEnhancedNotes,
      followUpDraft: initialFollowUpDraft,
    },
  }));
  const [initialDefaultsBinding, setInitialDefaultsBinding] =
    useState<InitialDefaultsBinding>({ owner: null, invalidated: false });
  let resolvedInitialDefaultsBinding = initialDefaultsBinding;
  if (!initialDefaultsBinding.invalidated) {
    if (
      interactionId !== initialDefaults.interactionId ||
      verifiedIdentity.identityKey !== initialDefaults.identityKey
    ) {
      resolvedInitialDefaultsBinding = {
        ...initialDefaultsBinding,
        invalidated: true,
      };
    } else if (identityAvailable) {
      const candidate = { interactionId, organisationId, ownerUserId };
      if (initialDefaultsBinding.owner === null) {
        resolvedInitialDefaultsBinding = {
          owner: candidate,
          invalidated: false,
        };
      } else if (
        initialDefaultsBinding.owner.interactionId !==
          candidate.interactionId ||
        initialDefaultsBinding.owner.organisationId !==
          candidate.organisationId ||
        initialDefaultsBinding.owner.ownerUserId !== candidate.ownerUserId
      ) {
        resolvedInitialDefaultsBinding = {
          ...initialDefaultsBinding,
          invalidated: true,
        };
      }
    }
  }
  if (resolvedInitialDefaultsBinding !== initialDefaultsBinding) {
    setInitialDefaultsBinding(resolvedInitialDefaultsBinding);
  }
  const sessionDefaults =
    resolvedInitialDefaultsBinding.invalidated ||
    interactionId !== initialDefaults.interactionId
      ? AUTHORITATIVE_EMPTY_VALUES
      : initialDefaults.values;
  const defaultsOwner = resolvedInitialDefaultsBinding.owner;
  const defaultsBelongToCurrentVerifiedIdentity =
    identityAvailable &&
    !resolvedInitialDefaultsBinding.invalidated &&
    defaultsOwner !== null &&
    defaultsOwner.interactionId === interactionId &&
    defaultsOwner.organisationId === organisationId &&
    defaultsOwner.ownerUserId === ownerUserId;
  const defaults = useRef({
    ...initialDefaults.values,
  });
  useLayoutEffect(() => {
    activeSession.current = renderSession;
    defaults.current = {
      liveNotes: sessionDefaults.liveNotes,
      enhancedNotes: sessionDefaults.enhancedNotes,
      followUpDraft: sessionDefaults.followUpDraft,
    };
  }, [
    renderSession,
    sessionDefaults.enhancedNotes,
    sessionDefaults.followUpDraft,
    sessionDefaults.liveNotes,
  ]);
  const [workspace, setWorkspace] =
    useState<ConversationWorkspaceResponse | null>(null);
  const [stateOwnerSession, setStateOwnerSession] =
    useState<WorkspaceSession | null>(null);
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
  const activeRead = useRef<WorkspaceReadRequest | null>(null);
  const activeConflictRead = useRef<WorkspaceReadRequest | null>(null);
  const readSequence = useRef(0);
  const conflictReadSequence = useRef(0);
  const operationSequence = useRef(0);
  const activeSaveToken = useRef<WorkspaceOperationToken | null>(null);
  const activeGenerationToken = useRef<WorkspaceOperationToken | null>(null);
  const loadedSession = useRef<WorkspaceSession | null>(null);
  const appliedRefreshKey = useRef(refreshKey);
  const committedState = useRef<CommittedWorkspaceState>({
    owner: null,
    workspace,
    values,
    baseline,
    saveState,
    generationActionState,
    conflictRecovery,
  });

  useLayoutEffect(() => {
    // Publish one keyed snapshot only after all state from this commit exists.
    // Mutations never combine a new owner with values from an older commit.
    committedState.current = {
      owner: stateOwnerSession,
      workspace,
      values,
      baseline,
      saveState,
      generationActionState,
      conflictRecovery,
    };
  }, [
    baseline,
    conflictRecovery,
    generationActionState,
    saveState,
    stateOwnerSession,
    values,
    workspace,
  ]);

  const sessionIsCurrent = useCallback((candidate: WorkspaceSession) => {
    return sameWorkspaceSession(activeSession.current, candidate);
  }, []);

  const verifiedSessionIsCurrent = useCallback(
    (candidate: WorkspaceSession) =>
      identityAvailable &&
      candidate.organisationId === organisationId &&
      candidate.ownerUserId === ownerUserId &&
      sessionIsCurrent(candidate),
    [identityAvailable, organisationId, ownerUserId, sessionIsCurrent],
  );

  const ownerIsCurrent = useCallback((candidate: WorkspaceSession) => {
    const owner = committedState.current.owner;
    return (
      sameWorkspaceSession(activeSession.current, candidate) &&
      owner !== null &&
      sameWorkspaceSession(owner, candidate)
    );
  }, []);

  const setValues = useCallback(
    (update: SetStateAction<WorkspaceValues>) => {
      const target = renderSession;
      if (!ownerIsCurrent(target)) return;
      valuesRevision.current += 1;
      setValuesState((current) => {
        if (!ownerIsCurrent(target)) return current;
        return typeof update === "function" ? update(current) : update;
      });
    },
    [ownerIsCurrent, renderSession],
  );

  const nextOperationToken = useCallback(
    (target: WorkspaceSession): WorkspaceOperationToken => ({
      ...target,
      token: ++operationSequence.current,
    }),
    [],
  );

  const operationIsCurrent = useCallback(
    (token: WorkspaceOperationToken) => sessionIsCurrent(token),
    [sessionIsCurrent],
  );

  const beginRead = useCallback((target: WorkspaceSession) => {
    activeRead.current?.controller.abort();
    const request: WorkspaceReadRequest = {
      ...target,
      sequence: ++readSequence.current,
      controller: new AbortController(),
    };
    activeRead.current = request;
    return request;
  }, []);

  const readIsCurrent = useCallback(
    (request: WorkspaceReadRequest) =>
      activeRead.current === request &&
      !request.controller.signal.aborted &&
      sessionIsCurrent(request),
    [sessionIsCurrent],
  );

  const finishRead = useCallback(
    (request: WorkspaceReadRequest) => {
      if (!readIsCurrent(request)) return;
      activeRead.current = null;
      setLoading(false);
    },
    [readIsCurrent],
  );

  const invalidateActiveRead = useCallback(
    (target: WorkspaceSession) => {
      if (!sessionIsCurrent(target)) return;
      activeRead.current?.controller.abort();
      activeRead.current = null;
      readSequence.current += 1;
      setLoading(false);
    },
    [sessionIsCurrent],
  );

  const hydrate = useCallback(
    (
      target: WorkspaceSession,
      response: ConversationWorkspaceResponse,
      fallback: Pick<
        WorkspaceValues,
        "liveNotes" | "enhancedNotes" | "followUpDraft"
      >,
    ) => {
      if (!sessionIsCurrent(target)) return false;
      const next = responseValues(response, fallback);
      setStateOwnerSession(target);
      setBaseline(next);
      setWorkspace(response);
      setValuesState(next);
      setSaveState("idle");
      setError(null);
      setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
      setGenerationActionState("idle");
      setGenerationError(null);
      return true;
    },
    [sessionIsCurrent],
  );

  const loadForSession = useCallback(
    async (target: WorkspaceSession) => {
      if (!verifiedSessionIsCurrent(target)) return false;
      const fallback = {
        liveNotes: defaults.current.liveNotes,
        enhancedNotes: defaults.current.enhancedNotes,
        followUpDraft: defaults.current.followUpDraft,
      };
      activeConflictRead.current?.controller.abort();
      activeConflictRead.current = null;
      conflictReadSequence.current += 1;
      const hasVerifiedWorkspace =
        ownerIsCurrent(target) && committedState.current.workspace !== null;
      if (!hasVerifiedWorkspace) {
        setStateOwnerSession(target);
        valuesRevision.current = 0;
        setWorkspace(null);
        setValuesState({ ...fallback, followUpReviewed: false });
        setBaseline({ ...fallback, followUpReviewed: false });
        setSaveState("idle");
        setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
        setGenerationActionState("idle");
        setGenerationError(null);
      }
      setError(null);
      setLoading(true);
      const request = beginRead(target);
      try {
        const payload = await apiRequest<unknown>(workspacePath(target), {
          signal: request.controller.signal,
        });
        if (!readIsCurrent(request)) return false;
        const response = decodeConversationWorkspaceResponse(payload, target);
        if (response === null) {
          setError(SAFE_WORKSPACE_IDENTITY_ERROR);
          return false;
        }
        return hydrate(target, response, fallback);
      } catch (reason: unknown) {
        if (!readIsCurrent(request)) return false;
        setError(
          reason instanceof Error
            ? reason.message
            : "Your private conversation workspace could not be loaded.",
        );
        return false;
      } finally {
        finishRead(request);
      }
    },
    [
      beginRead,
      finishRead,
      hydrate,
      ownerIsCurrent,
      readIsCurrent,
      verifiedSessionIsCurrent,
    ],
  );

  const refreshForSession = useCallback(
    async (target: WorkspaceSession, recoverGeneratedVersion = false) => {
      const requestStartState = committedState.current;
      if (
        !verifiedSessionIsCurrent(target) ||
        !ownerIsCurrent(target) ||
        requestStartState.workspace === null
      ) {
        return loadForSession(target);
      }
      const saveAtStart = activeSaveToken.current;
      const generationAtStart = activeGenerationToken.current;
      const overlapsMutation =
        (saveAtStart !== null && sameWorkspaceSession(saveAtStart, target)) ||
        (generationAtStart !== null &&
          sameWorkspaceSession(generationAtStart, target));
      const requestStartRevision = valuesRevision.current;
      setLoading(true);
      setError(null);
      const request = beginRead(target);
      try {
        const payload = await apiRequest<unknown>(workspacePath(target), {
          signal: request.controller.signal,
        });
        if (!readIsCurrent(request) || !ownerIsCurrent(target)) return false;
        const response = decodeConversationWorkspaceResponse(payload, target);
        if (response === null) {
          setError(SAFE_WORKSPACE_IDENTITY_ERROR);
          return false;
        }
        if (overlapsMutation) return false;
        const latestState = committedState.current;
        if (
          latestState.owner === null ||
          !sameWorkspaceSession(latestState.owner, target)
        ) {
          return false;
        }
        const editedFields = dirtyFields(
          latestState.values,
          latestState.baseline,
        );
        const hasLocalEdits = Object.values(editedFields).some(Boolean);
        const conflictActive =
          latestState.saveState === "conflict" ||
          latestState.conflictRecovery.state !== "idle";
        const preserveLocalValues =
          hasLocalEdits ||
          valuesRevision.current !== requestStartRevision ||
          latestState.saveState === "saving" ||
          conflictActive;
        if (!preserveLocalValues) {
          return hydrate(target, response, {
            liveNotes: defaults.current.liveNotes,
            enhancedNotes: defaults.current.enhancedNotes,
            followUpDraft: defaults.current.followUpDraft,
          });
        }
        if (
          recoverGeneratedVersion &&
          !conflictActive &&
          latestState.saveState !== "saving"
        ) {
          setSaveState("conflict");
          setConflictRecovery({
            state: "ready",
            latestWorkspace: response,
            latestValues: responseValues(response, AUTHORITATIVE_EMPTY_VALUES),
            submittedValues: latestState.values,
            localValuesAtSubmission: latestState.values,
            submittedFields: editedFields,
            importFromBrowser: false,
            error: null,
          });
          setGenerationActionState("idle");
          setGenerationError(null);
          return true;
        }
        setWorkspace((current) =>
          current === null
            ? response
            : mergeGenerationMetadata(current, response),
        );
        if (latestState.generationActionState !== "refresh_required") {
          setGenerationActionState("idle");
          setGenerationError(null);
        }
        return true;
      } catch (reason: unknown) {
        if (!readIsCurrent(request)) return false;
        setError(
          reason instanceof Error
            ? reason.message
            : "Your private conversation workspace could not be refreshed.",
        );
        return false;
      } finally {
        finishRead(request);
      }
    },
    [
      beginRead,
      finishRead,
      hydrate,
      loadForSession,
      ownerIsCurrent,
      readIsCurrent,
      verifiedSessionIsCurrent,
    ],
  );

  const load = useCallback(async () => {
    if (verifiedIdentity.status !== "available") {
      verifiedIdentity.reload();
      return;
    }
    if (!verifiedSessionIsCurrent(renderSession)) return;
    await loadForSession(renderSession);
  }, [
    loadForSession,
    renderSession,
    verifiedIdentity,
    verifiedSessionIsCurrent,
  ]);

  const refresh = useCallback(async () => {
    if (!verifiedSessionIsCurrent(renderSession)) return;
    await refreshForSession(
      renderSession,
      committedState.current.generationActionState === "refresh_required",
    );
  }, [refreshForSession, renderSession, verifiedSessionIsCurrent]);

  const fetchLatestConflict = useCallback(
    async (
      submission: WorkspaceConflictSubmission,
      target: WorkspaceSession,
    ) => {
      if (!verifiedSessionIsCurrent(target) || !ownerIsCurrent(target)) {
        return false;
      }
      const previousRecovery = committedState.current.conflictRecovery;
      activeConflictRead.current?.controller.abort();
      const request: WorkspaceReadRequest = {
        ...target,
        sequence: ++conflictReadSequence.current,
        controller: new AbortController(),
      };
      activeConflictRead.current = request;
      const loadingRecovery: WorkspaceConflictRecovery = {
        state: "loading",
        latestWorkspace: null,
        latestValues: null,
        submittedValues: submission.values,
        localValuesAtSubmission: submission.localValues,
        submittedFields: submission.fields,
        importFromBrowser: submission.importFromBrowser,
        error: null,
      };
      setConflictRecovery(loadingRecovery);
      try {
        const payload = await apiRequest<unknown>(workspacePath(target), {
          signal: request.controller.signal,
        });
        if (
          activeConflictRead.current !== request ||
          request.controller.signal.aborted ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
        const latestWorkspace = decodeConversationWorkspaceResponse(
          payload,
          target,
        );
        if (latestWorkspace === null) {
          setConflictRecovery(
            previousRecovery.state === "ready"
              ? previousRecovery
              : {
                  ...loadingRecovery,
                  state: "failed",
                  error: SAFE_WORKSPACE_IDENTITY_ERROR,
                },
          );
          setError(SAFE_WORKSPACE_IDENTITY_ERROR);
          return false;
        }
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
        if (
          activeConflictRead.current !== request ||
          request.controller.signal.aborted ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
        if (
          previousRecovery.state === "ready" &&
          previousRecovery.error !== null
        ) {
          setConflictRecovery(previousRecovery);
          return false;
        }
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
      } finally {
        if (activeConflictRead.current === request) {
          activeConflictRead.current = null;
        }
      }
    },
    [ownerIsCurrent, verifiedSessionIsCurrent],
  );

  const loadLatestConflict = useCallback(async () => {
    const target = renderSession;
    const snapshot = committedState.current;
    const recovery = snapshot.conflictRecovery;
    if (
      !verifiedSessionIsCurrent(target) ||
      !ownerIsCurrent(target) ||
      snapshot.owner === null ||
      !sameWorkspaceSession(snapshot.owner, target) ||
      snapshot.saveState !== "conflict" ||
      recovery.submittedValues === null
    ) {
      return false;
    }
    return fetchLatestConflict(
      {
        values: recovery.submittedValues,
        localValues:
          recovery.localValuesAtSubmission ?? recovery.submittedValues,
        fields: recovery.submittedFields,
        importFromBrowser: recovery.importFromBrowser,
      },
      target,
    );
  }, [
    fetchLatestConflict,
    ownerIsCurrent,
    renderSession,
    verifiedSessionIsCurrent,
  ]);

  useEffect(() => {
    if (!identityAvailable) return;
    const interactionChanged =
      loadedSession.current === null ||
      !sameWorkspaceSession(loadedSession.current, renderSession);
    const refreshRequested = appliedRefreshKey.current !== refreshKey;
    if (!interactionChanged && !refreshRequested) return;

    const target = renderSession;
    let active = true;
    window.queueMicrotask(() => {
      if (!active || !sessionIsCurrent(target)) return;
      loadedSession.current = target;
      appliedRefreshKey.current = refreshKey;
      void (interactionChanged
        ? loadForSession(target)
        : refreshForSession(target));
    });
    return () => {
      active = false;
      if (
        activeRead.current &&
        sameWorkspaceSession(activeRead.current, target)
      ) {
        activeRead.current.controller.abort();
        activeRead.current = null;
      }
      if (
        activeConflictRead.current &&
        sameWorkspaceSession(activeConflictRead.current, target)
      ) {
        activeConflictRead.current.controller.abort();
        activeConflictRead.current = null;
      }
    };
  }, [
    identityAvailable,
    interactionId,
    loadForSession,
    refreshForSession,
    refreshKey,
    renderSession,
    sessionIsCurrent,
  ]);

  const save = useCallback(
    async (
      next: Partial<WorkspaceValues> = {},
      options: { importFromBrowser?: boolean } = {},
    ) => {
      const target = renderSession;
      const snapshot = committedState.current;
      if (
        !verifiedSessionIsCurrent(target) ||
        !ownerIsCurrent(target) ||
        snapshot.owner === null ||
        !sameWorkspaceSession(snapshot.owner, target) ||
        snapshot.workspace === null ||
        (activeSaveToken.current !== null &&
          sameWorkspaceSession(activeSaveToken.current, target)) ||
        snapshot.saveState === "saving" ||
        snapshot.saveState === "conflict" ||
        snapshot.conflictRecovery.state !== "idle"
      ) {
        return false;
      }
      const requestStartValues = snapshot.values;
      const requestStartRevision = valuesRevision.current;
      const merged = { ...requestStartValues, ...next };
      const submitted = {
        ...merged,
        expectedLockVersion: snapshot.workspace.lockVersion,
        generationFingerprint: snapshot.workspace.generationFingerprint,
        importFromBrowser: options.importFromBrowser === true,
      };
      const conflictSubmission: WorkspaceConflictSubmission = {
        values: merged,
        localValues: requestStartValues,
        fields: submittedFields(merged, snapshot.baseline, next),
        importFromBrowser: submitted.importFromBrowser,
      };
      const token = nextOperationToken(target);
      activeSaveToken.current = token;
      invalidateActiveRead(target);
      setSaveState("saving");
      setError(null);
      try {
        const payload = await apiRequest<unknown>(workspacePath(target), {
          method: "PUT",
          body: JSON.stringify(submitted),
        });
        if (
          activeSaveToken.current !== token ||
          !operationIsCurrent(token) ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
        const response = decodeConversationWorkspaceSaveResponse(
          payload,
          target,
          submitted,
        );
        if (response === null) {
          setSaveState("failed");
          setError(SAFE_WORKSPACE_SAVE_ERROR);
          return false;
        }
        setWorkspace(response);
        setBaseline(merged);
        setValuesState((current) =>
          valuesRevision.current === requestStartRevision ? merged : current,
        );
        setSaveState("saved");
        setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
        return true;
      } catch (reason: unknown) {
        if (
          activeSaveToken.current !== token ||
          !operationIsCurrent(token) ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
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
          await fetchLatestConflict(conflictSubmission, target);
        }
        return false;
      } finally {
        if (activeSaveToken.current === token) {
          activeSaveToken.current = null;
        }
      }
    },
    [
      fetchLatestConflict,
      invalidateActiveRead,
      nextOperationToken,
      operationIsCurrent,
      ownerIsCurrent,
      renderSession,
      verifiedSessionIsCurrent,
    ],
  );

  const useLatestConflict = useCallback(() => {
    const target = renderSession;
    const snapshot = committedState.current;
    const recovery = snapshot.conflictRecovery;
    if (
      !verifiedSessionIsCurrent(target) ||
      !ownerIsCurrent(target) ||
      snapshot.owner === null ||
      !sameWorkspaceSession(snapshot.owner, target) ||
      recovery.state !== "ready" ||
      recovery.error !== null ||
      recovery.latestWorkspace === null ||
      recovery.latestValues === null
    ) {
      return false;
    }
    valuesRevision.current += 1;
    setWorkspace(recovery.latestWorkspace);
    setBaseline(recovery.latestValues);
    setValuesState({ ...recovery.latestValues });
    setSaveState("idle");
    setError(null);
    setGenerationActionState("idle");
    setGenerationError(null);
    setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
    return true;
  }, [ownerIsCurrent, renderSession, verifiedSessionIsCurrent]);

  const saveReviewedConflict = useCallback(
    async (reviewed: Partial<WorkspaceValues> = {}) => {
      const target = renderSession;
      const snapshot = committedState.current;
      const recovery = snapshot.conflictRecovery;
      const latestWorkspace = recovery.latestWorkspace;
      const latestValues = recovery.latestValues;
      const submittedValues = recovery.submittedValues;
      const localValuesAtSubmission = recovery.localValuesAtSubmission;
      if (
        !verifiedSessionIsCurrent(target) ||
        !ownerIsCurrent(target) ||
        snapshot.owner === null ||
        !sameWorkspaceSession(snapshot.owner, target) ||
        (activeSaveToken.current !== null &&
          sameWorkspaceSession(activeSaveToken.current, target)) ||
        snapshot.saveState !== "conflict" ||
        recovery.state !== "ready" ||
        recovery.error !== null ||
        latestWorkspace === null ||
        latestValues === null ||
        submittedValues === null ||
        localValuesAtSubmission === null
      ) {
        return false;
      }
      const requestStartValues = snapshot.values;
      const reviewedValues = {
        ...submittedValuesPatch({
          values: submittedValues,
          localValues: localValuesAtSubmission,
          fields: recovery.submittedFields,
          importFromBrowser: recovery.importFromBrowser,
        }),
        ...reviewed,
      };
      const resolved = applyReviewedValues(latestValues, reviewedValues);
      const submitted = {
        ...resolved,
        expectedLockVersion: latestWorkspace.lockVersion,
        generationFingerprint: latestWorkspace.generationFingerprint,
        importFromBrowser: recovery.importFromBrowser,
      };
      const conflictSubmission: WorkspaceConflictSubmission = {
        values: resolved,
        localValues: requestStartValues,
        fields: submittedFields(resolved, latestValues, reviewedValues),
        importFromBrowser: submitted.importFromBrowser,
      };
      const token = nextOperationToken(target);
      activeSaveToken.current = token;
      invalidateActiveRead(target);
      setSaveState("saving");
      setError(null);
      const pendingRecovery: WorkspaceConflictRecovery = {
        state: "saving",
        latestWorkspace,
        latestValues,
        submittedValues: conflictSubmission.values,
        localValuesAtSubmission: conflictSubmission.localValues,
        submittedFields: conflictSubmission.fields,
        importFromBrowser: conflictSubmission.importFromBrowser,
        error: null,
      };
      setConflictRecovery(pendingRecovery);
      try {
        const payload = await apiRequest<unknown>(workspacePath(target), {
          method: "PUT",
          body: JSON.stringify(submitted),
        });
        if (
          activeSaveToken.current !== token ||
          !operationIsCurrent(token) ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
        const response = decodeConversationWorkspaceSaveResponse(
          payload,
          target,
          submitted,
        );
        if (response === null) {
          setSaveState("conflict");
          setConflictRecovery({
            ...pendingRecovery,
            state: "ready",
            error: SAFE_WORKSPACE_SAVE_ERROR,
          });
          setError(SAFE_WORKSPACE_SAVE_ERROR);
          return false;
        }
        setWorkspace(response);
        setBaseline(resolved);
        setValuesState((current) =>
          mergeSavedValuesPreservingEdits(
            current,
            requestStartValues,
            localValuesAtSubmission,
            resolved,
          ),
        );
        setSaveState("saved");
        setConflictRecovery(EMPTY_CONFLICT_RECOVERY);
        return true;
      } catch (reason: unknown) {
        if (
          activeSaveToken.current !== token ||
          !operationIsCurrent(token) ||
          !ownerIsCurrent(target)
        ) {
          return false;
        }
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
          await fetchLatestConflict(conflictSubmission, target);
        } else {
          setConflictRecovery({
            ...pendingRecovery,
            state: "failed",
            error:
              reason instanceof Error
                ? reason.message
                : "Your reviewed conflict resolution could not be saved.",
          });
        }
        return false;
      } finally {
        if (activeSaveToken.current === token) {
          activeSaveToken.current = null;
        }
      }
    },
    [
      fetchLatestConflict,
      invalidateActiveRead,
      nextOperationToken,
      operationIsCurrent,
      ownerIsCurrent,
      renderSession,
      verifiedSessionIsCurrent,
    ],
  );

  const retryGeneration = useCallback(async () => {
    const target = renderSession;
    const snapshot = committedState.current;
    if (
      !verifiedSessionIsCurrent(target) ||
      !ownerIsCurrent(target) ||
      snapshot.owner === null ||
      !sameWorkspaceSession(snapshot.owner, target) ||
      snapshot.workspace === null ||
      !snapshot.workspace.generationRetryAvailable ||
      (activeGenerationToken.current !== null &&
        sameWorkspaceSession(activeGenerationToken.current, target))
    )
      return false;
    const token = nextOperationToken(target);
    activeGenerationToken.current = token;
    invalidateActiveRead(target);
    setGenerationActionState("retrying");
    setGenerationError(null);
    try {
      const payload = await apiRequest<unknown>(
        `${workspacePath(target)}/generation/retry`,
        { method: "POST" },
      );
      if (
        activeGenerationToken.current !== token ||
        !operationIsCurrent(token) ||
        !ownerIsCurrent(target)
      ) {
        return false;
      }
      const response = decodeConversationWorkspaceResponse(payload, target);
      if (response === null) {
        setGenerationActionState("failed");
        setGenerationError(SAFE_WORKSPACE_IDENTITY_ERROR);
        return false;
      }
      setWorkspace((current) =>
        current === null
          ? response
          : mergeGenerationMetadata(current, response),
      );
      setGenerationActionState("idle");
      return true;
    } catch (reason: unknown) {
      if (
        activeGenerationToken.current !== token ||
        !operationIsCurrent(token) ||
        !ownerIsCurrent(target)
      ) {
        return false;
      }
      setGenerationActionState("failed");
      setGenerationError(
        reason instanceof Error
          ? reason.message
          : "Your private post-conversation draft could not be retried.",
      );
      return false;
    } finally {
      if (activeGenerationToken.current === token) {
        activeGenerationToken.current = null;
      }
    }
  }, [
    invalidateActiveRead,
    nextOperationToken,
    operationIsCurrent,
    ownerIsCurrent,
    renderSession,
    verifiedSessionIsCurrent,
  ]);

  const applyGeneratedVersion = useCallback(async () => {
    const target = renderSession;
    const snapshot = committedState.current;
    const workspaceAtStart = snapshot.workspace;
    if (
      !verifiedSessionIsCurrent(target) ||
      !ownerIsCurrent(target) ||
      snapshot.owner === null ||
      !sameWorkspaceSession(snapshot.owner, target) ||
      workspaceAtStart === null ||
      workspaceAtStart.generationId === null ||
      !workspaceAtStart.generationUpdateAvailable ||
      snapshot.generationActionState === "refresh_required" ||
      snapshot.saveState === "conflict" ||
      snapshot.conflictRecovery.state !== "idle" ||
      (activeSaveToken.current !== null &&
        sameWorkspaceSession(activeSaveToken.current, target)) ||
      (activeGenerationToken.current !== null &&
        sameWorkspaceSession(activeGenerationToken.current, target))
    ) {
      return false;
    }
    const token = nextOperationToken(target);
    activeGenerationToken.current = token;
    invalidateActiveRead(target);
    setGenerationActionState("applying");
    setGenerationError(null);
    const requestStartValues = snapshot.values;
    try {
      const payload = await apiRequest<unknown>(
        `${workspacePath(target)}/generation/apply`,
        {
          method: "POST",
          body: JSON.stringify({
            generationId: workspaceAtStart.generationId,
            expectedLockVersion: workspaceAtStart.lockVersion,
          }),
        },
      );
      if (
        activeGenerationToken.current !== token ||
        !operationIsCurrent(token) ||
        !ownerIsCurrent(target)
      ) {
        return false;
      }
      const response = decodeConversationWorkspaceResponse(payload, target);
      if (
        response === null ||
        !response.exists ||
        response.generationId !== workspaceAtStart.generationId ||
        response.generationTranscriptVersion !==
          workspaceAtStart.generationTranscriptVersion ||
        response.generationState !== "ready" ||
        response.generationUpdateAvailable ||
        (response.lockVersion !== workspaceAtStart.lockVersion &&
          response.lockVersion !== workspaceAtStart.lockVersion + 1)
      ) {
        setGenerationActionState("refresh_required");
        setGenerationError(SAFE_WORKSPACE_IDENTITY_ERROR);
        return false;
      }
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
      if (
        activeGenerationToken.current !== token ||
        !operationIsCurrent(token) ||
        !ownerIsCurrent(target)
      ) {
        return false;
      }
      const code = reason instanceof ApiClientError ? reason.code : null;
      if (code === "conversation_workspace_conflict") {
        setGenerationActionState("refresh_required");
        setGenerationError(
          "Your private draft changed in another session. Load the latest saved draft before choosing a generated version.",
        );
      } else if (code === "conversation_draft_generation_not_ready") {
        setGenerationActionState("refresh_required");
        setGenerationError(
          "This generated version is no longer ready. Load the latest saved draft to check which version is available.",
        );
      } else {
        setGenerationActionState("failed");
        setGenerationError(
          reason instanceof Error
            ? reason.message
            : "The generated private draft version could not be applied.",
        );
      }
      return false;
    } finally {
      if (activeGenerationToken.current === token) {
        activeGenerationToken.current = null;
      }
    }
  }, [
    invalidateActiveRead,
    nextOperationToken,
    operationIsCurrent,
    ownerIsCurrent,
    renderSession,
    verifiedSessionIsCurrent,
  ]);

  const stateBelongsToCurrentInteraction =
    stateOwnerSession !== null &&
    sameWorkspaceSession(stateOwnerSession, renderSession);
  const safeValueDefaults = defaultsBelongToCurrentVerifiedIdentity
    ? sessionDefaults
    : AUTHORITATIVE_EMPTY_VALUES;
  const safeValues: WorkspaceValues = {
    liveNotes: safeValueDefaults.liveNotes,
    enhancedNotes: safeValueDefaults.enhancedNotes,
    followUpDraft: safeValueDefaults.followUpDraft,
    followUpReviewed: false,
  };
  const visibleValues = stateBelongsToCurrentInteraction ? values : safeValues;
  const visibleBaseline = stateBelongsToCurrentInteraction
    ? baseline
    : safeValues;
  const visibleDirtyFields = dirtyFields(visibleValues, visibleBaseline);

  return {
    workspace: stateBelongsToCurrentInteraction ? workspace : null,
    values: visibleValues,
    setValues,
    loading:
      verifiedIdentity.status === "loading"
        ? true
        : identityAvailable && stateBelongsToCurrentInteraction
          ? loading
          : identityAvailable,
    saveState: stateBelongsToCurrentInteraction ? saveState : "idle",
    error:
      verifiedIdentity.status === "unavailable"
        ? SAFE_WORKSPACE_IDENTITY_ERROR
        : stateBelongsToCurrentInteraction
          ? error
          : null,
    generationActionState: stateBelongsToCurrentInteraction
      ? generationActionState
      : "idle",
    generationError: stateBelongsToCurrentInteraction ? generationError : null,
    conflictRecovery: stateBelongsToCurrentInteraction
      ? conflictRecovery
      : EMPTY_CONFLICT_RECOVERY,
    dirtyFields: visibleDirtyFields,
    isDirty: Object.values(visibleDirtyFields).some(Boolean),
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
