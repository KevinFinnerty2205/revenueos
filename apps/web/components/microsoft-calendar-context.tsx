"use client";

import type {
  Interaction,
  MicrosoftCalendarEvent,
  MicrosoftCalendarEventListResponse,
} from "@revenueos/shared";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function MicrosoftCalendarContext({
  interactions,
}: {
  interactions: Interaction[];
}) {
  const [events, setEvents] = useState<MicrosoftCalendarEvent[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<MicrosoftCalendarEventListResponse>(
      "/api/v1/integrations/microsoft/calendar/events?limit=4",
      { signal: controller.signal },
    )
      .then((result) => setEvents(result.items))
      .catch(() => setEvents([]));
    return () => controller.abort();
  }, []);

  async function linkEvent(event: MicrosoftCalendarEvent) {
    const interactionId = selected[event.id];
    if (!interactionId) return;
    setBusy(event.id);
    setError(null);
    try {
      const updated = await apiRequest<MicrosoftCalendarEvent>(
        `/api/v1/integrations/microsoft/calendar/events/${event.id}/interaction`,
        {
          method: "PUT",
          body: JSON.stringify({ interactionId }),
        },
      );
      setEvents((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
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
      className="mb-7 rounded-2xl border border-teal-200 bg-teal-50/60 p-5"
      aria-labelledby="microsoft-calendar-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Microsoft Calendar
      </p>
      <h2 id="microsoft-calendar-title" className="mt-2 text-xl font-semibold">
        Upcoming meetings
      </h2>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {events.map((event) => (
          <article
            key={event.id}
            className="rounded-xl border border-teal-100 bg-white p-4"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-teal-800">
              {new Date(event.startAt).toLocaleString("en-AU", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
            <h3 className="mt-2 font-bold text-slate-950">{event.title}</h3>
            <p className="mt-1 text-sm text-slate-600">
              {event.location ?? "Location not supplied"}
              {event.matchState === "review_required"
                ? " · Relationship needs review"
                : ""}
            </p>
            {event.interactionId ? (
              <Link
                className="mt-3 inline-flex text-sm font-bold text-teal-800 hover:underline"
                href={`/interactions/${event.interactionId}#preparation`}
              >
                Prepare →
              </Link>
            ) : interactions.length ? (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <label className="sr-only" htmlFor={`interaction-${event.id}`}>
                  Link {event.title} to an interaction
                </label>
                <select
                  id={`interaction-${event.id}`}
                  className="form-control min-w-0 flex-1"
                  value={selected[event.id] ?? ""}
                  onChange={(change) =>
                    setSelected((current) => ({
                      ...current,
                      [event.id]: change.target.value,
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
                  disabled={!selected[event.id] || busy === event.id}
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
