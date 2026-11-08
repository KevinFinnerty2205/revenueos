"use client";

import type {
  ConversationFrameworkCoverage,
  ConversationMemoryResponse,
  ConversationThreadSummary,
  MethodologyProjectionItem,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
        typeof source.interactionTitle === "string" &&
        typeof source.occurredAt === "string",
    );
  return validCounts && validItems && validSources;
}

function isConversationMemoryResponse(
  value: unknown,
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
  return (
    (value.state === "not_configured" || value.state === "current") &&
    typeof value.safeMessage === "string" &&
    validDefinition &&
    typeof assignment.interactionId === "string" &&
    typeof assignment.lockVersion === "number" &&
    validThread &&
    validSuggestions &&
    validCurrentCoverage &&
    validThreadCoverage &&
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
  const [memory, setMemory] = useState<ConversationMemoryResponse | null>(null);
  const [threads, setThreads] = useState<ConversationThreadSummary[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [newThreadName, setNewThreadName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [memoryPayload, threadsPayload] = await Promise.all([
          apiRequest<unknown>(
            `/api/v1/interactions/${interactionId}/conversation-memory`,
            { signal },
          ),
          apiRequest<unknown>("/api/v1/conversation-threads", { signal }),
        ]);
        if (
          !isConversationMemoryResponse(memoryPayload) ||
          !Array.isArray(threadsPayload) ||
          !threadsPayload.every(isConversationThreadSummary)
        ) {
          setMemory(null);
          setThreads([]);
          throw new Error(
            "Conversation memory returned an unexpected response. Reload this section to try again.",
          );
        }
        const nextMemory = memoryPayload;
        const nextThreads = threadsPayload;
        setMemory(nextMemory);
        setThreads(nextThreads);
        setSelectedThreadId(nextMemory.assignment.thread?.id ?? "");
      } catch (requestError: unknown) {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Conversation memory could not be loaded.",
        );
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [interactionId],
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
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The initiative assignment could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function createThread() {
    const name = newThreadName.trim();
    if (!name || !memory) return;
    const expectedAssignmentLockVersion = memory.assignment.lockVersion;
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
      setNewThreadName("");
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The initiative could not be created.",
      );
    } finally {
      setSaving(false);
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
            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <label className="text-sm font-semibold text-slate-800">
                Choose an existing initiative
                <select
                  className="form-control mt-2"
                  value={selectedThreadId}
                  disabled={saving}
                  onChange={(event) => setSelectedThreadId(event.target.value)}
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
