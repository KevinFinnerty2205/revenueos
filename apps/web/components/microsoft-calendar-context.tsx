"use client";

import type { Interaction, ProviderCalendarEvent } from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import {
  decodeProviderCalendarEventListResponse,
  isProviderCalendarEventResponse,
} from "@/lib/private-response-identity";

interface CalendarItem extends ProviderCalendarEvent {
  provider: "microsoft" | "google";
  providerName: "Microsoft 365" | "Google Workspace";
}

function eventKey(event: CalendarItem): string {
  return `${event.provider}:${event.id}`;
}

interface EventMutationState {
  operation: number;
  pending: boolean;
  error: string | null;
}

export function ProviderCalendarContext({
  interactions,
  organisationId,
}: {
  interactions: Interaction[];
  organisationId: string;
}) {
  return (
    <ProviderCalendarContextSession
      key={organisationId}
      interactions={interactions}
      organisationId={organisationId}
    />
  );
}

function ProviderCalendarContextSession({
  interactions,
  organisationId,
}: {
  interactions: Interaction[];
  organisationId: string;
}) {
  const [events, setEvents] = useState<CalendarItem[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [mutations, setMutations] = useState<
    Record<string, EventMutationState>
  >({});
  const activeOperations = useRef<Record<string, number>>({});
  const operationSequence = useRef(0);
  const interactionIds = useMemo(
    () => new Set(interactions.map((interaction) => interaction.id)),
    [interactions],
  );

  useEffect(() => {
    let active = true;
    window.queueMicrotask(() => {
      if (!active) return;
      setSelected((current) => {
        const entries = Object.entries(current);
        if (
          entries.every(([, interactionId]) =>
            interactionIds.has(interactionId),
          )
        ) {
          return current;
        }
        return Object.fromEntries(
          entries.filter(([, interactionId]) =>
            interactionIds.has(interactionId),
          ),
        );
      });
    });
    return () => {
      active = false;
    };
  }, [interactionIds]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      apiRequest<unknown>(
        "/api/v1/integrations/microsoft/calendar/events?limit=4",
        { signal: controller.signal },
      ).then((result) => {
        const decoded = decodeProviderCalendarEventListResponse(
          result,
          organisationId,
        );
        if (decoded === null) {
          throw new Error("Microsoft calendar events are unavailable.");
        }
        return decoded.items.map((item) => ({
          ...item,
          provider: "microsoft" as const,
          providerName: "Microsoft 365" as const,
        }));
      }),
      apiRequest<unknown>(
        "/api/v1/integrations/google/calendar/events?limit=4",
        { signal: controller.signal },
      ).then((result) => {
        const decoded = decodeProviderCalendarEventListResponse(
          result,
          organisationId,
        );
        if (decoded === null) {
          throw new Error("Google calendar events are unavailable.");
        }
        return decoded.items.map((item) => ({
          ...item,
          provider: "google" as const,
          providerName: "Google Workspace" as const,
        }));
      }),
    ])
      .then((results) => {
        const availableEvents: CalendarItem[] = [];
        for (const result of results) {
          if (result.status === "fulfilled") {
            availableEvents.push(...result.value);
          }
        }
        setEvents(availableEvents);
      })
      .catch(() => setEvents([]));
    return () => controller.abort();
  }, [organisationId]);

  async function linkEvent(event: CalendarItem) {
    const key = eventKey(event);
    const interactionId = selected[key];
    if (!interactionId || !interactionIds.has(interactionId)) {
      if (interactionId) {
        setSelected((current) => {
          if (!(key in current)) return current;
          const next = { ...current };
          delete next[key];
          return next;
        });
      }
      return;
    }
    await updateInteraction(event, interactionId);
  }

  async function unlinkEvent(event: CalendarItem) {
    await updateInteraction(event, null);
  }

  async function updateInteraction(
    event: CalendarItem,
    interactionId: string | null,
  ) {
    const key = eventKey(event);
    if (activeOperations.current[key] !== undefined) return;

    const operation = operationSequence.current + 1;
    operationSequence.current = operation;
    activeOperations.current[key] = operation;
    setMutations((current) => ({
      ...current,
      [key]: { operation, pending: true, error: null },
    }));
    try {
      const response = await apiRequest<unknown>(
        `/api/v1/integrations/${event.provider}/calendar/events/${encodeURIComponent(event.id)}/interaction`,
        {
          method: "PUT",
          body: JSON.stringify({ interactionId }),
        },
      );
      if (activeOperations.current[key] !== operation) return;
      if (
        !isProviderCalendarEventResponse(response, organisationId) ||
        response.id !== event.id ||
        response.interactionId !== interactionId
      ) {
        throw new Error("The calendar event could not be updated. Try again.");
      }
      const updated = response;
      setEvents((current) =>
        current.map((item) =>
          item.provider === event.provider && item.id === event.id
            ? { ...item, ...updated }
            : item,
        ),
      );
    } catch (reason: unknown) {
      if (activeOperations.current[key] !== operation) return;
      const message =
        reason instanceof Error
          ? reason.message
          : "The calendar event could not be linked.";
      setMutations((current) => {
        if (current[key]?.operation !== operation) return current;
        return {
          ...current,
          [key]: { operation, pending: true, error: message },
        };
      });
    } finally {
      if (activeOperations.current[key] !== operation) return;
      delete activeOperations.current[key];
      setMutations((current) => {
        if (current[key]?.operation !== operation) return current;
        return {
          ...current,
          [key]: { ...current[key], pending: false },
        };
      });
    }
  }

  if (!events.length) return null;

  return (
    <section
      className="mb-7 rounded-2xl border border-brand-secondary/25 bg-brand-secondary/10 p-5"
      aria-labelledby="provider-calendar-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        Work calendar
      </p>
      <h2 id="provider-calendar-title" className="mt-2 text-xl font-semibold">
        Upcoming meetings
      </h2>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {events.map((event) => {
          const key = eventKey(event);
          const mutation = mutations[key];
          const selectedInteractionId = interactionIds.has(selected[key] ?? "")
            ? selected[key]
            : "";
          return (
            <article
              key={key}
              className="rounded-xl border border-brand-secondary/15 bg-white p-4"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
                {new Date(event.startAt).toLocaleString("en-AU", {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {event.providerName}
              </p>
              <h3 className="mt-2 font-bold text-slate-950">{event.title}</h3>
              <p className="mt-1 text-sm text-slate-600">
                {event.location ?? "Location not supplied"}
                {event.matchState === "review_required"
                  ? " · Relationship needs review"
                  : ""}
              </p>
              {event.interactionId ? (
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <Link
                    className="inline-flex text-sm font-bold text-brand-secondary hover:underline"
                    href={`/conversations/${encodeURIComponent(event.interactionId)}?view=prepare`}
                  >
                    Prepare →
                  </Link>
                  <button
                    type="button"
                    className="text-sm font-bold text-slate-600 underline-offset-4 hover:underline"
                    disabled={mutation?.pending}
                    onClick={() => void unlinkEvent(event)}
                  >
                    {mutation?.pending ? "Unlinking…" : "Unlink"}
                  </button>
                </div>
              ) : event.matchState === "private" ? (
                <p className="mt-3 text-sm text-slate-600">
                  Private events cannot be linked to an interaction.
                </p>
              ) : interactions.length ? (
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <label
                    className="sr-only"
                    htmlFor={`interaction-${event.provider}-${event.id}`}
                  >
                    Link {event.title} to an interaction
                  </label>
                  <select
                    id={`interaction-${event.provider}-${event.id}`}
                    className="form-control min-w-0 flex-1"
                    value={selectedInteractionId}
                    disabled={mutation?.pending}
                    onChange={(change) =>
                      setSelected((current) => ({
                        ...current,
                        [key]: change.target.value,
                      }))
                    }
                  >
                    <option value="">Link an interaction…</option>
                    {interactions.map((interaction) => (
                      <option key={interaction.id} value={interaction.id}>
                        {interaction.title}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!selectedInteractionId || mutation?.pending}
                    onClick={() => void linkEvent(event)}
                  >
                    {mutation?.pending ? "Linking…" : "Link"}
                  </button>
                </div>
              ) : null}
              {mutation?.error ? (
                <p role="alert" className="mt-3 text-sm text-rose-800">
                  {mutation.error}
                </p>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export const MicrosoftCalendarContext = ProviderCalendarContext;
