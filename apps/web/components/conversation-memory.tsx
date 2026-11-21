"use client";

import type {
  ConversationFrameworkCoverage,
  ConversationInitiativeHistory,
  ConversationMemoryResponse,
  ConversationThreadSummary,
  InteractionLifecycleStatus,
  InteractionType,
  MethodologyProjectionItem,
} from "@revenueos/shared";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  formatInteractionDate,
  interactionStatuses,
  interactionTypes,
} from "@/lib/interactions";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T/.test(value) &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isInteractionType(value: unknown): value is InteractionType {
  return interactionTypes.some((interactionType) => interactionType === value);
}

function isInteractionStatus(
  value: unknown,
): value is InteractionLifecycleStatus {
  return interactionStatuses.some(
    (interactionStatus) => interactionStatus === value,
  );
}

function isConversationThreadSummary(
  value: unknown,
): value is ConversationThreadSummary {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    (value.status === "active" || value.status === "archived") &&
    typeof value.interactionCount === "number"
  );
}

function isCoverage(value: unknown): value is ConversationFrameworkCoverage {
  if (!isRecord(value) || !isRecord(value.stateCounts)) return false;
  const counts = value.stateCounts;
  const validCounts = [
    counts.confirmed,
    counts.partiallySupported,
    counts.unknown,
    counts.conflicting,
    counts.stale,
  ].every((count) => typeof count === "number");
  const validItems =
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.fieldKey === "string" &&
        typeof item.displayName === "string" &&
        typeof item.state === "string" &&
        Array.isArray(item.sources) &&
        item.sources.every(
          (source) => isRecord(source) && typeof source.sourceId === "string",
        ) &&
        Array.isArray(item.conflicts) &&
        item.conflicts.every(
          (source) => isRecord(source) && typeof source.sourceId === "string",
        ),
    );
  const validSources =
    Array.isArray(value.sourceConversations) &&
    value.sourceConversations.every(
      (source) =>
        isRecord(source) &&
        typeof source.sourceId === "string" &&
        typeof source.interactionId === "string" &&
        typeof source.interactionTitle === "string" &&
        isDateTime(source.occurredAt),
    );
  return validCounts && validItems && validSources;
}

function isInitiativeHistory(
  value: unknown,
): value is ConversationInitiativeHistory {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    typeof value.total !== "number" ||
    !Number.isInteger(value.total) ||
    value.total < 0 ||
    typeof value.truncated !== "boolean"
  ) {
    return false;
  }
  const total = value.total;
  const validItems =
    value.items.length <= 20 &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.interactionId === "string" &&
        typeof item.title === "string" &&
        isInteractionType(item.interactionType) &&
        isInteractionStatus(item.lifecycleStatus) &&
        isDateTime(item.occurredAt),
    );
  return (
    validItems &&
    total >= value.items.length &&
    value.truncated === total > value.items.length
  );
}

function isConversationMemoryResponse(
  value: unknown,
  expectedInteractionId: string,
): value is ConversationMemoryResponse {
  if (!isRecord(value) || !isRecord(value.assignment)) return false;
  const assignment = value.assignment;
  const validThread =
    assignment.thread === null ||
    isConversationThreadSummary(assignment.thread);
  const validSuggestions =
    Array.isArray(value.suggestions) &&
    value.suggestions.every(
      (suggestion) =>
        isRecord(suggestion) &&
        isConversationThreadSummary(suggestion.thread) &&
        Array.isArray(suggestion.reasons) &&
        suggestion.reasons.every((reason) => typeof reason === "string"),
    );
  const validDefinition =
    value.definition === null ||
    (isRecord(value.definition) && typeof value.definition.name === "string");
  const validCurrentCoverage =
    value.currentConversation === null || isCoverage(value.currentConversation);
  const validThreadCoverage =
    value.confirmedThread === null || isCoverage(value.confirmedThread);
  const validInitiativeHistory = isInitiativeHistory(
    value.confirmedInitiativeHistory,
  );
  return (
    (value.state === "not_configured" || value.state === "current") &&
    typeof value.safeMessage === "string" &&
    validDefinition &&
    assignment.interactionId === expectedInteractionId &&
    typeof assignment.lockVersion === "number" &&
    validThread &&
    validSuggestions &&
    validCurrentCoverage &&
    validThreadCoverage &&
    validInitiativeHistory &&
    typeof value.generatedAt === "string"
  );
}

export function ConversationMemory({
  interactionId,
  companyId,
}: {
  interactionId: string;
  companyId: string | null;
}) {
  return (
    <ConversationMemorySession
      key={`${interactionId}:${companyId ?? ""}`}
      interactionId={interactionId}
      companyId={companyId}
    />
  );
}

function ConversationMemorySession({
  interactionId,
  companyId,
}: {
  interactionId: string;
  companyId: string | null;
}) {
  const [memory, setMemory] = useState<ConversationMemoryResponse | null>(null);
  const [threads, setThreads] = useState<ConversationThreadSummary[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [newThreadName, setNewThreadName] = useState("");
  const [loading, setLoading] = useState(true);
  const [threadDirectoryState, setThreadDirectoryState] = useState<
    "loading" | "available" | "unavailable"
  >("loading");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionActiveRef = useRef(true);
  const memoryRequestId = useRef(0);
  const threadDirectoryRequestId = useRef(0);
  const mutationRequestId = useRef(0);

  useLayoutEffect(() => {
    sessionActiveRef.current = true;
    return () => {
      sessionActiveRef.current = false;
      memoryRequestId.current += 1;
      threadDirectoryRequestId.current += 1;
      mutationRequestId.current += 1;
    };
  }, []);

  const loadThreadDirectory = useCallback(async (signal?: AbortSignal) => {
    const requestId = threadDirectoryRequestId.current + 1;
    threadDirectoryRequestId.current = requestId;
    if (!sessionActiveRef.current) return;
    setThreadDirectoryState("loading");
    try {
      const payload = await apiRequest<unknown>(
        "/api/v1/conversation-threads",
        { signal },
      );
      if (
        !Array.isArray(payload) ||
        !payload.every(isConversationThreadSummary)
      ) {
        throw new Error("Unexpected initiative directory response.");
      }
      if (
        signal?.aborted ||
        !sessionActiveRef.current ||
        threadDirectoryRequestId.current !== requestId
      )
        return;
      setThreads(payload);
      setThreadDirectoryState("available");
    } catch (requestError: unknown) {
      if (
        requestError instanceof DOMException &&
        requestError.name === "AbortError"
      ) {
        return;
      }
      if (
        signal?.aborted ||
        !sessionActiveRef.current ||
        threadDirectoryRequestId.current !== requestId
      )
        return;
      setThreads([]);
      setThreadDirectoryState("unavailable");
    }
  }, []);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const requestId = memoryRequestId.current + 1;
      memoryRequestId.current = requestId;
      if (!sessionActiveRef.current) return;
      setLoading(true);
      setError(null);
      void loadThreadDirectory(signal);
      try {
        const memoryPayload = await apiRequest<unknown>(
          `/api/v1/interactions/${interactionId}/conversation-memory`,
          { signal },
        );
        if (
          signal?.aborted ||
          !sessionActiveRef.current ||
          memoryRequestId.current !== requestId
        ) {
          return;
        }
        if (!isConversationMemoryResponse(memoryPayload, interactionId)) {
          setMemory(null);
          throw new Error(
            "Conversation memory returned an unexpected response. Reload this section to try again.",
          );
        }
        const nextMemory = memoryPayload;
        setMemory(nextMemory);
        setSelectedThreadId(nextMemory.assignment.thread?.id ?? "");
      } catch (requestError: unknown) {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        if (
          signal?.aborted ||
          !sessionActiveRef.current ||
          memoryRequestId.current !== requestId
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Conversation memory could not be loaded.",
        );
      } finally {
        if (
          !signal?.aborted &&
          sessionActiveRef.current &&
          memoryRequestId.current === requestId
        ) {
          setLoading(false);
        }
      }
    },
    [interactionId, loadThreadDirectory],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function assign(threadId: string | null) {
    if (!memory) return;
    const requestId = mutationRequestId.current + 1;
    mutationRequestId.current = requestId;
    setSaving(true);
    setError(null);
    try {
      await apiRequest(
        `/api/v1/interactions/${interactionId}/thread-assignment`,
        {
          method: "PUT",
          body: JSON.stringify({
            threadId,
            expectedLockVersion: memory.assignment.lockVersion,
          }),
        },
      );
      if (
        !sessionActiveRef.current ||
        mutationRequestId.current !== requestId
      ) {
        return;
      }
      await load();
    } catch (requestError: unknown) {
      if (
        !sessionActiveRef.current ||
        mutationRequestId.current !== requestId
      ) {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The initiative assignment could not be saved.",
      );
    } finally {
      if (sessionActiveRef.current && mutationRequestId.current === requestId) {
        setSaving(false);
      }
    }
  }

  async function createThread() {
    const name = newThreadName.trim();
    if (!name || !memory) return;
    const expectedAssignmentLockVersion = memory.assignment.lockVersion;
    const requestId = mutationRequestId.current + 1;
    mutationRequestId.current = requestId;
    setSaving(true);
    setError(null);
    try {
      await apiRequest<ConversationThreadSummary>(
        "/api/v1/conversation-threads",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            companyId,
            initialInteractionId: interactionId,
            expectedAssignmentLockVersion,
          }),
        },
      );
      if (
        !sessionActiveRef.current ||
        mutationRequestId.current !== requestId
      ) {
        return;
      }
      setNewThreadName("");
      await load();
    } catch (requestError: unknown) {
      if (
        !sessionActiveRef.current ||
        mutationRequestId.current !== requestId
      ) {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The initiative could not be created.",
      );
    } finally {
      if (sessionActiveRef.current && mutationRequestId.current === requestId) {
        setSaving(false);
      }
    }
  }

  return (
    <section
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
      aria-labelledby="conversation-memory-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
            Conversation memory
          </p>
          <h2
            id="conversation-memory-title"
            className="mt-1 text-xl font-semibold text-slate-950"
          >
            Initiative and framework coverage
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Related conversations are combined only after someone confirms the
            same initiative. A shared company or participant can suggest a
            match, but never assigns it automatically.
          </p>
        </div>
        {memory?.assignment.thread ? (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-900">
            Confirmed · {memory.assignment.thread.name}
          </span>
        ) : (
          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-950">
            Not grouped
          </span>
        )}
      </div>

      {loading ? (
        <p className="mt-5 text-sm" role="status">
          Loading conversation memory…
        </p>
      ) : null}
      {error ? (
        <div
          className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-900"
          role="alert"
        >
          <p>{error}</p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void load()}
          >
            Reload memory
          </button>
        </div>
      ) : null}

      {memory ? (
        <>
          <div className="mt-5 rounded-2xl bg-slate-50 p-4">
            <p className="text-sm font-bold text-slate-900">
              Confirmed initiative
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              {memory.safeMessage}
            </p>
            {threadDirectoryState === "loading" ? (
              <p className="mt-4 text-sm text-slate-600" role="status">
                Loading initiative choices…
              </p>
            ) : null}
            {threadDirectoryState === "unavailable" ? (
              <div
                className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
                role="status"
              >
                <p>
                  Initiative choices are temporarily unavailable. Conversation
                  memory remains available.
                </p>
                <button
                  type="button"
                  className="secondary-button mt-3"
                  onClick={() => void loadThreadDirectory()}
                >
                  Retry initiative choices
                </button>
              </div>
            ) : null}
            {threadDirectoryState === "available" ? (
              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                <label className="text-sm font-semibold text-slate-800">
                  Choose an existing initiative
                  <select
                    className="form-control mt-2"
                    value={selectedThreadId}
                    disabled={saving}
                    onChange={(event) =>
                      setSelectedThreadId(event.target.value)
                    }
                  >
                    <option value="">Not grouped</option>
                    {threads
                      .filter((thread) => thread.status === "active")
                      .map((thread) => (
                        <option key={thread.id} value={thread.id}>
                          {thread.name} · {thread.interactionCount} conversation
                          {thread.interactionCount === 1 ? "" : "s"}
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="secondary-button self-end"
                  disabled={
                    saving ||
                    selectedThreadId === (memory.assignment.thread?.id ?? "")
                  }
                  onClick={() => void assign(selectedThreadId || null)}
                >
                  {saving ? "Saving…" : "Confirm grouping"}
                </button>
              </div>
            ) : null}
            {memory.suggestions.length ? (
              <div className="mt-4">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Suggestions requiring confirmation
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {memory.suggestions.map((suggestion) => (
                    <button
                      type="button"
                      className="rounded-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:border-brand-secondary"
                      key={suggestion.thread.id}
                      disabled={saving}
                      onClick={() => void assign(suggestion.thread.id)}
                    >
                      {suggestion.thread.name} · {suggestion.reasons.join(", ")}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="mt-5 border-t border-slate-200 pt-4">
              <label className="text-sm font-semibold text-slate-800">
                Start a separate initiative
                <input
                  className="form-control mt-2"
                  value={newThreadName}
                  maxLength={200}
                  placeholder="For example, APAC renewal programme"
                  disabled={saving}
                  onChange={(event) => setNewThreadName(event.target.value)}
                />
              </label>
              <button
                type="button"
                className="secondary-button mt-3"
                disabled={
                  saving ||
                  !newThreadName.trim() ||
                  memory.assignment.thread !== null
                }
                onClick={() => void createThread()}
              >
                Create and confirm initiative
              </button>
              {memory.assignment.thread ? (
                <p className="mt-2 text-xs text-slate-500">
                  Remove or change the current grouping before creating a new
                  initiative for this conversation.
                </p>
              ) : null}
            </div>
          </div>

          <InitiativeHistoryPanel
            history={memory.confirmedInitiativeHistory}
            confirmed={memory.assignment.thread !== null}
          />

          {memory.definition && memory.currentConversation ? (
            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              <CoveragePanel
                title="This conversation"
                description="Only validated evidence from this conversation."
                definitionName={memory.definition.name}
                coverage={memory.currentConversation}
              />
              {memory.confirmedThread && memory.assignment.thread ? (
                <CoveragePanel
                  title={`Cumulative · ${memory.assignment.thread.name}`}
                  description="Only completed conversations in the confirmed initiative, up to this conversation date."
                  definitionName={memory.definition.name}
                  coverage={memory.confirmedThread}
                />
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 p-5">
                  <h3 className="font-semibold text-slate-950">
                    Cumulative initiative
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    Confirm an initiative to compare this conversation with its
                    authorised history. Oryntela will not use a company-wide
                    fallback.
                  </p>
                </div>
              )}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function InitiativeHistoryPanel({
  history,
  confirmed,
}: {
  history: ConversationInitiativeHistory;
  confirmed: boolean;
}) {
  return (
    <section
      className="mt-6 rounded-2xl border border-slate-200 p-5"
      aria-labelledby="initiative-conversation-history-title"
    >
      <h3
        id="initiative-conversation-history-title"
        className="font-semibold text-slate-950"
      >
        Earlier conversations in this initiative
      </h3>
      <p className="mt-1 text-sm leading-6 text-slate-600">
        Conversation membership is user-confirmed context. It does not mean the
        conversation was validated as framework evidence.
      </p>
      {!confirmed ? (
        <p className="mt-4 text-sm leading-6 text-slate-600">
          Confirm an initiative to see its earlier conversations. Oryntela will
          not use company-wide history.
        </p>
      ) : history.items.length ? (
        <>
          <ol
            className="mt-4 space-y-3"
            aria-label="Earlier conversations in this initiative"
          >
            {history.items.map((item) => (
              <li
                key={item.interactionId}
                className="min-w-0 rounded-xl bg-slate-50 p-4"
              >
                <Link
                  href={`/conversations/${item.interactionId}`}
                  className="break-words text-sm font-bold text-brand-primary underline decoration-brand-primary/30 underline-offset-4 hover:decoration-brand-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-focus"
                >
                  {item.title}
                </Link>
                <p className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-xs text-slate-600">
                  <span>{humanise(item.interactionType)}</span>
                  <span aria-hidden="true">·</span>
                  <span>{humanise(item.lifecycleStatus)}</span>
                  <span aria-hidden="true">·</span>
                  <time dateTime={item.occurredAt}>
                    {formatInteractionDate(item.occurredAt)}
                  </time>
                </p>
              </li>
            ))}
          </ol>
          {history.truncated ? (
            <p className="mt-4 text-xs leading-5 text-slate-500">
              Showing the {history.items.length} most recent of {history.total}{" "}
              earlier conversations.
            </p>
          ) : null}
        </>
      ) : (
        <p className="mt-4 text-sm leading-6 text-slate-600">
          No earlier conversations are available in this confirmed initiative
          yet.
        </p>
      )}
    </section>
  );
}

function CoveragePanel({
  title,
  description,
  definitionName,
  coverage,
}: {
  title: string;
  description: string;
  definitionName: string;
  coverage: ConversationFrameworkCoverage;
}) {
  const supported =
    coverage.stateCounts.confirmed + coverage.stateCounts.partiallySupported;
  return (
    <section className="rounded-2xl border border-slate-200 p-5">
      <h3 className="font-semibold text-slate-950">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
      <p className="mt-3 text-sm text-slate-700">
        <strong>{definitionName}:</strong> {supported} supported ·{" "}
        {coverage.stateCounts.conflicting} conflicting ·{" "}
        {coverage.stateCounts.stale} stale
      </p>
      <div className="mt-4 space-y-3">
        {coverage.items.map((item) => (
          <CoverageItem key={item.fieldKey} item={item} coverage={coverage} />
        ))}
      </div>
    </section>
  );
}

function CoverageItem({
  item,
  coverage,
}: {
  item: MethodologyProjectionItem;
  coverage: ConversationFrameworkCoverage;
}) {
  const sourceIds = new Set(
    [...item.sources, ...item.conflicts].map((source) => source.sourceId),
  );
  const conversations = coverage.sourceConversations.filter((source) =>
    sourceIds.has(source.sourceId),
  );
  return (
    <details className="rounded-xl bg-slate-50 p-4">
      <summary className="cursor-pointer list-none focus:outline-none focus:ring-2 focus:ring-brand-focus">
        <span className="flex items-center justify-between gap-3">
          <span className="text-sm font-bold text-slate-900">
            {item.displayName}
          </span>
          <span className="rounded-full bg-white px-2 py-1 text-xs font-bold text-slate-700">
            {humanise(item.state)}
          </span>
        </span>
      </summary>
      <p className="mt-3 text-sm leading-6 text-slate-700">
        {item.conclusion ??
          "Not discussed or not yet supported by validated evidence."}
      </p>
      {conversations.length ? (
        <ul className="mt-3 space-y-2 text-xs text-slate-600">
          {conversations.map((source) => (
            <li key={source.sourceId}>
              <strong>{source.interactionTitle}</strong> ·{" "}
              {new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
                new Date(source.occurredAt),
              )}
            </li>
          ))}
        </ul>
      ) : null}
      {item.suggestedQuestion ? (
        <p className="mt-3 text-sm text-brand-primary">
          <strong>Suggested question:</strong> {item.suggestedQuestion}
        </p>
      ) : null}
    </details>
  );
}
