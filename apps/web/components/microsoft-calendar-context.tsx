"use client";

import type {
  Interaction,
  ProviderCalendarEvent,
  ProviderCalendarEventListResponse,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface CalendarItem extends ProviderCalendarEvent {
  provider: "microsoft" | "google";
  providerName: "Microsoft 365" | "Google Workspace";
}

function eventKey(event: CalendarItem): string {
  return `${event.provider}:${event.id}`;
}

export function ProviderCalendarContext({
  interactions,
}: {
  interactions: Interaction[];
}) {
  const [events, setEvents] = useState<CalendarItem[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      apiRequest<ProviderCalendarEventListResponse>(
        "/api/v1/integrations/microsoft/calendar/events?limit=4",
        { signal: controller.signal },
      ).then((result) =>
        result.items.map((item) => ({
          ...item,
          provider: "microsoft" as const,
          providerName: "Microsoft 365" as const,
        })),
      ),
      apiRequest<ProviderCalendarEventListResponse>(
        "/api/v1/integrations/google/calendar/events?limit=4",
        { signal: controller.signal },
      ).then((result) =>
        result.items.map((item) => ({
          ...item,
          provider: "google" as const,
          providerName: "Google Workspace" as const,
        })),
      ),
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
  }, []);

  async function linkEvent(event: CalendarItem) {
    const interactionId = selected[eventKey(event)];
    if (!interactionId) return;
    await updateInteraction(event, interactionId);
  }

  async function unlinkEvent(event: CalendarItem) {
    await updateInteraction(event, null);
  }

  async function updateInteraction(
    event: CalendarItem,
    interactionId: string | null,
  ) {
    setBusy(eventKey(event));
    setError(null);
    try {
      const updated = await apiRequest<ProviderCalendarEvent>(
        `/api/v1/integrations/${event.provider}/calendar/events/${event.id}/interaction`,
        {
          method: "PUT",
          body: JSON.stringify({ interactionId }),
        },
      );
      setEvents((current) =>
        current.map((item) =>
          item.provider === event.provider && item.id === updated.id
            ? { ...item, ...updated }
            : item,
        ),
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The calendar event could not be linked.",
      );
    } finally {
      setBusy(null);
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
        {events.map((event) => (
          <article
            key={eventKey(event)}
            className="rounded-xl border border-brand-secondary/15 bg-white p-4"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-brand-secondary">
              {new Date(event.startAt).toLocaleString("en-AU", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
            <p className="mt-1 text-xs text-slate-500">{event.providerName}</p>
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
                  href={`/interactions/${event.interactionId}#preparation`}
                >
                  Prepare →
                </Link>
                <button
                  type="button"
                  className="text-sm font-bold text-slate-600 underline-offset-4 hover:underline"
                  disabled={busy === eventKey(event)}
                  onClick={() => void unlinkEvent(event)}
                >
                  Unlink
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
                  value={selected[eventKey(event)] ?? ""}
                  onChange={(change) =>
                    setSelected((current) => ({
                      ...current,
                      [eventKey(event)]: change.target.value,
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
                  disabled={
                    !selected[eventKey(event)] || busy === eventKey(event)
                  }
                  onClick={() => void linkEvent(event)}
                >
                  Link
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {error ? (
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </section>
  );
}

export const MicrosoftCalendarContext = ProviderCalendarContext;
