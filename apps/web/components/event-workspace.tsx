"use client";

import type {
  EventAttendee,
  EventAttendeeList,
  EventImportPreview,
  EventPlanState,
  SalesEvent,
  SalesEventGoal,
  SalesEventList,
  SalesEventType,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ChangeEvent,
  type FormEvent,
  cloneElement,
  useCallback,
  useEffect,
  useState,
} from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const importFields = [
  "first_name",
  "last_name",
  "company_name",
  "job_title",
  "business_email",
  "country_or_location",
  "profile_url",
  "company_domain",
  "registration_category",
] as const;

type EventTab = "overview" | "people" | "activity" | "follow_up";

function message(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

function eventDate(event: SalesEvent): string {
  const start = new Date(event.startAt);
  const end = new Date(event.endAt);
  const formatter = new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: event.timezone,
  });
  return `${formatter.format(start)} – ${formatter.format(end)}`;
}

function localInputValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function zonedInputToIso(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/u.exec(value);
  if (!match) throw new Error("Choose a valid Event date and time.");
  const expected = match.slice(1).map(Number);
  const targetAsUtc = Date.UTC(
    expected[0],
    expected[1] - 1,
    expected[2],
    expected[3],
    expected[4],
  );
  const formatter = new Intl.DateTimeFormat("en-AU", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  let instant = targetAsUtc;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const values = Object.fromEntries(
      formatter
        .formatToParts(new Date(instant))
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, Number(part.value)]),
    );
    const renderedAsUtc = Date.UTC(
      values.year,
      values.month - 1,
      values.day,
      values.hour,
      values.minute,
    );
    instant += targetAsUtc - renderedAsUtc;
  }
  const rendered = formatter
    .formatToParts(new Date(instant))
    .filter((part) => part.type !== "literal")
    .reduce<Record<string, number>>((parts, part) => {
      parts[part.type] = Number(part.value);
      return parts;
    }, {});
  if (
    rendered.year !== expected[0] ||
    rendered.month !== expected[1] ||
    rendered.day !== expected[2] ||
    rendered.hour !== expected[3] ||
    rendered.minute !== expected[4]
  ) {
    throw new Error("That local time does not exist in the selected timezone.");
  }
  return new Date(instant).toISOString();
}

function base64FromBuffer(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 16_384) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 16_384));
  }
  return window.btoa(binary);
}

function Status({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex rounded-full bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-900">
      {children}
    </span>
  );
}

export function EventListWorkspace() {
  const [result, setResult] = useState<SalesEventList | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      const parameters = new URLSearchParams();
      if (search.trim()) parameters.set("search", search.trim());
      const suffix = parameters.size ? `?${parameters.toString()}` : "";
      apiRequest<SalesEventList>(`/api/v1/engage/events${suffix}`, {
        signal: controller.signal,
      })
        .then((value) => {
          setResult(value);
          setError(null);
        })
        .catch((reason: unknown) => {
          if (reason instanceof DOMException && reason.name === "AbortError")
            return;
          setError(message(reason, "Events could not be loaded."));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [search]);

  return (
    <section aria-labelledby="events-title">
      <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Engage · Sell
          </p>
          <h1
            id="events-title"
            className="mt-3 text-4xl font-semibold tracking-tight"
          >
            Events
          </h1>
          <p className="mt-2 max-w-2xl text-slate-600">
            Plan who to meet, capture what happened and follow up truthfully.
            Events do not imply outreach permission.
          </p>
        </div>
        {result?.canCreate ? (
          <Link className="primary-button" href="/events/new">
            Create Event
          </Link>
        ) : null}
      </header>

      {result?.readOnly ? (
        <p
          role="status"
          className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          Historical Event data is read-only because Engage is not enabled for
          this organisation.
        </p>
      ) : null}
      <label className="mb-6 block max-w-md text-sm font-semibold text-slate-800">
        Search Events
        <input
          className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-200"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Name, city or venue"
        />
      </label>
      {error ? (
        <p
          role="alert"
          className="rounded-2xl bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
      {loading && !result ? (
        <div
          aria-label="Loading Events"
          className="h-48 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none"
        />
      ) : null}
      {!loading && result?.items.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-9 text-center">
          <h2 className="text-xl font-semibold">
            Get more from the events you attend
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Plan who to meet, capture conversations and follow up while the
            context is fresh. Start by creating a business Event.
          </p>
        </div>
      ) : null}
      <div className="grid gap-4">
        {result?.items.map((event) => (
          <Link
            key={event.id}
            href={`/events/${event.id}`}
            className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-semibold">{event.name}</h2>
                  <Status>{humanise(event.state)}</Status>
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  {eventDate(event)}
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  {[event.locationName, event.city, event.country]
                    .filter(Boolean)
                    .join(" · ") || "Location not set"}
                </p>
              </div>
              <dl className="grid grid-cols-3 gap-5 text-center">
                <div>
                  <dt className="text-xs text-slate-500">People</dt>
                  <dd className="mt-1 text-lg font-bold">
                    {event.summary.attendeesImported}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Planned</dt>
                  <dd className="mt-1 text-lg font-bold">
                    {event.summary.planned}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Met</dt>
                  <dd className="mt-1 text-lg font-bold">
                    {event.summary.met}
                  </dd>
                </div>
              </dl>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function EventBuilder() {
  const router = useRouter();
  const now = new Date();
  const defaultEnd = new Date(now.getTime() + 2 * 60 * 60 * 1000);
  const [name, setName] = useState("");
  const [eventType, setEventType] = useState<SalesEventType>("conference");
  const [startAt, setStartAt] = useState(localInputValue(now));
  const [endAt, setEndAt] = useState(localInputValue(defaultEnd));
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "Australia/Sydney",
  );
  const [locationName, setLocationName] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("Australia");
  const [eventUrl, setEventUrl] = useState("");
  const [organiser, setOrganiser] = useState("");
  const [goalType, setGoalType] =
    useState<SalesEventGoal>("meet_new_prospects");
  const [goalDetail, setGoalDetail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await apiRequest<SalesEvent>("/api/v1/engage/events", {
        method: "POST",
        body: JSON.stringify({
          name,
          eventType,
          startAt: zonedInputToIso(startAt, timezone),
          endAt: zonedInputToIso(endAt, timezone),
          timezone,
          locationName: locationName || null,
          city: city || null,
          country: country || null,
          eventUrl: eventUrl || null,
          organiser: organiser || null,
          goalType,
          goalDetail: goalType === "other" ? goalDetail : null,
          state: "upcoming",
        }),
      });
      router.push(`/events/${created.id}`);
    } catch (reason: unknown) {
      setError(message(reason, "The Event could not be created."));
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="new-event-title">
      <Link href="/events" className="text-sm font-bold text-teal-800">
        ← Events
      </Link>
      <p className="mt-6 text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
        Create Event
      </p>
      <h1
        id="new-event-title"
        className="mt-3 text-4xl font-semibold tracking-tight"
      >
        Set up the Event workspace
      </h1>
      <p className="mt-2 text-slate-600">
        Use event-local time and only business context you are authorised to
        handle.
      </p>
      <form
        onSubmit={submit}
        className="mt-7 grid gap-5 rounded-3xl border border-slate-200 bg-white p-6 sm:grid-cols-2"
      >
        <Field label="Event name">
          <input
            required
            maxLength={160}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <Field label="Event type">
          <select
            value={eventType}
            onChange={(event) =>
              setEventType(event.target.value as SalesEventType)
            }
          >
            {[
              "conference",
              "trade_show",
              "networking_event",
              "customer_event",
              "partner_event",
              "industry_event",
              "executive_roundtable",
              "internal_hosted_event",
              "other_business_event",
            ].map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Starts">
          <input
            required
            type="datetime-local"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
          />
        </Field>
        <Field label="Ends">
          <input
            required
            type="datetime-local"
            value={endAt}
            onChange={(event) => setEndAt(event.target.value)}
          />
        </Field>
        <Field label="Timezone">
          <input
            required
            maxLength={64}
            value={timezone}
            onChange={(event) => setTimezone(event.target.value)}
          />
        </Field>
        <Field label="Venue">
          <input
            maxLength={200}
            value={locationName}
            onChange={(event) => setLocationName(event.target.value)}
          />
        </Field>
        <Field label="City">
          <input
            maxLength={120}
            value={city}
            onChange={(event) => setCity(event.target.value)}
          />
        </Field>
        <Field label="Country">
          <input
            maxLength={100}
            value={country}
            onChange={(event) => setCountry(event.target.value)}
          />
        </Field>
        <Field label="Event website (HTTPS)">
          <input
            type="url"
            maxLength={1000}
            value={eventUrl}
            onChange={(event) => setEventUrl(event.target.value)}
          />
        </Field>
        <Field label="Organiser">
          <input
            maxLength={160}
            value={organiser}
            onChange={(event) => setOrganiser(event.target.value)}
          />
        </Field>
        <Field label="Goal">
          <select
            value={goalType}
            onChange={(event) =>
              setGoalType(event.target.value as SalesEventGoal)
            }
          >
            {[
              "meet_new_prospects",
              "progress_active_opportunities",
              "meet_strategic_accounts",
              "reconnect_existing_contacts",
              "find_partners",
              "other",
            ].map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </Field>
        {goalType === "other" ? (
          <Field label="Goal detail">
            <input
              required
              maxLength={300}
              value={goalDetail}
              onChange={(event) => setGoalDetail(event.target.value)}
            />
          </Field>
        ) : null}
        {error ? (
          <p
            role="alert"
            className="sm:col-span-2 rounded-2xl bg-red-50 p-4 text-sm text-red-900"
          >
            {error}
          </p>
        ) : null}
        <div className="sm:col-span-2 flex justify-end">
          <button className="primary-button" disabled={busy} type="submit">
            {busy ? "Creating…" : "Create Event"}
          </button>
        </div>
      </form>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactElement<{ className?: string }>;
}) {
  return (
    <label className="text-sm font-semibold text-slate-800">
      {label}
      {cloneElement(children, {
        className:
          "mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-200",
      })}
    </label>
  );
}

export function EventDetailWorkspace({ eventId }: { eventId: string }) {
  const router = useRouter();
  const [event, setEvent] = useState<SalesEvent | null>(null);
  const [attendees, setAttendees] = useState<EventAttendee[]>([]);
  const [tab, setTab] = useState<EventTab>("overview");
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [planState, setPlanState] = useState("");
  const [relationship, setRelationship] = useState("");
  const [page, setPage] = useState(1);
  const [attendeeTotal, setAttendeeTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const parameters = new URLSearchParams({
        page: String(page),
        pageSize: "100",
      });
      if (search.trim()) parameters.set("search", search.trim());
      if (priority) parameters.set("priority", priority);
      if (planState) parameters.set("planState", planState);
      const [eventValue, people] = await Promise.all([
        apiRequest<SalesEvent>(`/api/v1/engage/events/${eventId}`),
        apiRequest<EventAttendeeList>(
          `/api/v1/engage/events/${eventId}/attendees?${parameters.toString()}`,
        ),
      ]);
      setEvent(eventValue);
      setAttendees(people.items);
      setAttendeeTotal(people.total);
      setError(null);
    } catch (reason: unknown) {
      setError(message(reason, "The Event workspace could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [eventId, page, planState, priority, search]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function deleteEvent() {
    if (
      !window.confirm(
        "Delete the Event workspace? Promoted Contacts, captured Interactions and Campaigns are preserved.",
      )
    )
      return;
    try {
      await apiRequest(`/api/v1/engage/events/${eventId}`, {
        method: "DELETE",
        body: JSON.stringify({ confirmed: true }),
      });
      router.push("/events");
    } catch (reason: unknown) {
      setError(message(reason, "The Event could not be deleted."));
    }
  }

  if (loading && !event)
    return (
      <div
        aria-label="Loading Event"
        className="h-72 animate-pulse rounded-3xl bg-slate-200 motion-reduce:animate-none"
      />
    );
  if (!event)
    return (
      <section className="rounded-2xl bg-red-50 p-4 text-red-900">
        <p role="alert">{error ?? "The Event was not found."}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void load()}
          >
            Try again
          </button>
          <Link href="/events" className="secondary-button">
            Return to Events
          </Link>
        </div>
      </section>
    );
  const campaignContacts = selectedContacts;
  const visibleAttendees = attendees.filter((item) => {
    if (relationship === "existing") return Boolean(item.contactId);
    if (relationship === "new") return !item.contactId;
    return true;
  });

  return (
    <section aria-labelledby="event-title">
      <Link href="/events" className="text-sm font-bold text-teal-800">
        ← Events
      </Link>
      <header className="mt-5 rounded-[2rem] bg-slate-950 p-6 text-white sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Status>{humanise(event.state)}</Status>
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                {humanise(event.eventType)}
              </span>
            </div>
            <h1
              id="event-title"
              className="mt-3 text-3xl font-semibold sm:text-4xl"
            >
              {event.name}
            </h1>
            <p className="mt-2 text-sm text-slate-300">{eventDate(event)}</p>
            <p className="mt-1 text-sm text-slate-400">
              {[event.locationName, event.city, event.country]
                .filter(Boolean)
                .join(" · ") || "Location not set"}
            </p>
          </div>
          {!event.readOnly ? (
            <button
              type="button"
              onClick={() => void deleteEvent()}
              className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-bold hover:border-red-300 hover:text-red-200 focus:outline-none focus:ring-2 focus:ring-white"
            >
              Delete
            </button>
          ) : null}
        </div>
        <dl className="mt-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            ["People", event.summary.attendeesImported],
            ["Priority", event.summary.priorityPeople],
            ["Planned", event.summary.planned],
            ["Met", event.summary.met],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl bg-white/10 p-4">
              <dt className="text-xs text-slate-300">{label}</dt>
              <dd className="mt-1 text-2xl font-bold">{value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <div
        className="mt-6 grid grid-cols-4 gap-1 rounded-xl bg-slate-100 p-1 sm:flex sm:gap-2 sm:bg-transparent sm:p-0 sm:pb-2"
        role="tablist"
        aria-label="Event workspace"
      >
        {(["overview", "people", "activity", "follow_up"] as const).map(
          (value) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              type="button"
              onClick={() => setTab(value)}
              className={`min-h-11 min-w-0 rounded-xl px-1 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-teal-600 sm:px-4 sm:text-sm ${tab === value ? "bg-teal-700 text-white" : "bg-white text-slate-700"}`}
            >
              {humanise(value)}
            </button>
          ),
        )}
      </div>
      {error ? (
        <div className="mt-4 rounded-2xl bg-red-50 p-4 text-sm text-red-900">
          <p role="alert">{error}</p>
          <button
            type="button"
            className="secondary-button mt-4"
            onClick={() => void load()}
          >
            Try again
          </button>
        </div>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="mt-4 rounded-2xl bg-teal-50 p-4 text-sm text-teal-950"
        >
          {notice}
        </p>
      ) : null}

      {tab === "overview" ? (
        <EventOverview
          event={event}
          attendees={attendees}
          onImported={load}
          setError={setError}
        />
      ) : null}
      {tab === "people" ? (
        <div className="mt-6">
          <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm font-semibold">
              Search people
              <input
                className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5"
                value={search}
                onChange={(value) => {
                  setPage(1);
                  setSearch(value.target.value);
                }}
              />
            </label>
            <label className="text-sm font-semibold">
              Priority
              <select
                className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5"
                value={priority}
                onChange={(value) => {
                  setPage(1);
                  setPriority(value.target.value);
                }}
              >
                <option value="">All</option>
                <option value="priority_to_meet">Priority to meet</option>
                <option value="worth_meeting">Worth meeting</option>
                <option value="needs_more_information">
                  Needs more information
                </option>
                <option value="context_only">Context only</option>
              </select>
            </label>
            <label className="text-sm font-semibold">
              Plan status
              <select
                className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5"
                value={planState}
                onChange={(value) => {
                  setPage(1);
                  setPlanState(value.target.value);
                }}
              >
                <option value="">All</option>
                <option value="planned">Planned</option>
                <option value="met">Met</option>
                <option value="follow_up">Follow up</option>
              </select>
            </label>
            <label className="text-sm font-semibold">
              Relationship
              <select
                className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5"
                value={relationship}
                onChange={(value) => setRelationship(value.target.value)}
              >
                <option value="">All</option>
                <option value="existing">Existing Contact</option>
                <option value="new">New attendee</option>
              </select>
            </label>
          </div>
          <div className="grid gap-4">
            {visibleAttendees.map((attendee) => (
              <AttendeeCard
                key={attendee.id}
                event={event}
                attendee={attendee}
                selected={Boolean(
                  attendee.contactId &&
                  selectedContacts.includes(attendee.contactId),
                )}
                onSelect={(contactId, checked) =>
                  setSelectedContacts((current) =>
                    checked
                      ? [...new Set([...current, contactId])]
                      : current.filter((id) => id !== contactId),
                  )
                }
                onChanged={load}
                setError={setError}
                setNotice={setNotice}
              />
            ))}
          </div>
          {attendeeTotal > 100 ? (
            <nav
              className="mt-6 flex items-center justify-between"
              aria-label="Event attendees"
            >
              <button
                type="button"
                className="secondary-button"
                disabled={page === 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </button>
              <span className="text-sm font-semibold">
                Page {page} of {Math.ceil(attendeeTotal / 100)}
              </span>
              <button
                type="button"
                className="secondary-button"
                disabled={page * 100 >= attendeeTotal}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </button>
            </nav>
          ) : null}
        </div>
      ) : null}
      {tab === "activity" ? (
        <ActivityPanel event={event} attendees={attendees} />
      ) : null}
      {tab === "follow_up" ? (
        <div className="mt-6 space-y-5">
          <div className="rounded-3xl border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-semibold">Campaign handoff</h2>
            <p className="mt-2 text-sm text-slate-600">
              Only promoted canonical Contacts can enter a Campaign. Existing
              Engage suppression and contactability checks still apply.
            </p>
            <p className="mt-3 text-sm font-semibold">
              {campaignContacts.length} Contact
              {campaignContacts.length === 1 ? "" : "s"} selected
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              {campaignContacts.length ? (
                <Link
                  className="primary-button"
                  href={`/campaigns/new?eventId=${event.id}&eventStage=post_event&contactIds=${campaignContacts.join(",")}`}
                >
                  Create post-Event Campaign
                </Link>
              ) : null}
              {campaignContacts.length ? (
                <Link
                  className="secondary-button"
                  href={`/campaigns/new?eventId=${event.id}&eventStage=pre_event&contactIds=${campaignContacts.join(",")}`}
                >
                  Create pre-Event Campaign
                </Link>
              ) : null}
            </div>
          </div>
          <ActivityPanel
            event={event}
            attendees={attendees.filter(
              (item) => item.planState === "follow_up" || item.encounterId,
            )}
          />
        </div>
      ) : null}
    </section>
  );
}

function EventOverview({
  event,
  attendees,
  onImported,
  setError,
}: {
  event: SalesEvent;
  attendees: EventAttendee[];
  onImported: () => Promise<void>;
  setError: (value: string | null) => void;
}) {
  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <div className="rounded-3xl border border-slate-200 bg-white p-6">
        <h2 className="text-xl font-semibold">Event brief</h2>
        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="font-bold text-slate-500">Goal</dt>
            <dd className="mt-1">
              {event.goalType ? humanise(event.goalType) : "Not set"}
              {event.goalDetail ? ` · ${event.goalDetail}` : ""}
            </dd>
          </div>
          <div>
            <dt className="font-bold text-slate-500">Organiser</dt>
            <dd className="mt-1">{event.organiser ?? "Not set"}</dd>
          </div>
          <div>
            <dt className="font-bold text-slate-500">Description</dt>
            <dd className="mt-1">
              {event.description ?? "No description supplied."}
            </dd>
          </div>
        </dl>
        {event.eventUrl ? (
          <a
            className="secondary-button mt-5"
            href={event.eventUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open Event website
          </a>
        ) : null}
        {!event.readOnly ? (
          <EventEditor
            key={event.updatedAt}
            event={event}
            onSaved={onImported}
            setError={setError}
          />
        ) : null}
      </div>
      {!event.readOnly ? (
        <ImportPanel
          eventId={event.id}
          attendeeCount={attendees.length}
          onImported={onImported}
          setError={setError}
        />
      ) : null}
    </div>
  );
}

function EventEditor({
  event,
  onSaved,
  setError,
}: {
  event: SalesEvent;
  onSaved: () => Promise<void>;
  setError: (value: string | null) => void;
}) {
  const [name, setName] = useState(event.name);
  const [locationName, setLocationName] = useState(event.locationName ?? "");
  const [organiser, setOrganiser] = useState(event.organiser ?? "");
  const [description, setDescription] = useState(event.description ?? "");
  const [goalType, setGoalType] = useState<SalesEventGoal | "">(
    event.goalType ?? "",
  );
  const [goalDetail, setGoalDetail] = useState(event.goalDetail ?? "");
  const [busy, setBusy] = useState(false);

  async function save(change: FormEvent<HTMLFormElement>) {
    change.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiRequest(`/api/v1/engage/events/${event.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name,
          locationName: locationName || null,
          organiser: organiser || null,
          description: description || null,
          goalType: goalType || null,
          goalDetail: goalType === "other" ? goalDetail : null,
        }),
      });
      await onSaved();
    } catch (reason: unknown) {
      setError(message(reason, "The Event details could not be updated."));
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    setBusy(true);
    setError(null);
    try {
      await apiRequest(`/api/v1/engage/events/${event.id}`, {
        method: "PATCH",
        body: JSON.stringify({ state: "archived" }),
      });
      await onSaved();
    } catch (reason: unknown) {
      setError(message(reason, "The Event could not be archived."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="mt-6 border-t border-slate-200 pt-5">
      <summary className="cursor-pointer text-sm font-bold text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600">
        Edit Event details
      </summary>
      <form onSubmit={save} className="mt-4 grid gap-4">
        <Field label="Event name">
          <input
            required
            maxLength={160}
            value={name}
            onChange={(change) => setName(change.target.value)}
          />
        </Field>
        <Field label="Venue">
          <input
            maxLength={200}
            value={locationName}
            onChange={(change) => setLocationName(change.target.value)}
          />
        </Field>
        <Field label="Organiser">
          <input
            maxLength={160}
            value={organiser}
            onChange={(change) => setOrganiser(change.target.value)}
          />
        </Field>
        <Field label="Goal">
          <select
            value={goalType}
            onChange={(change) =>
              setGoalType(change.target.value as SalesEventGoal | "")
            }
          >
            <option value="">Not set</option>
            {[
              "meet_new_prospects",
              "progress_active_opportunities",
              "meet_strategic_accounts",
              "reconnect_existing_contacts",
              "find_partners",
              "other",
            ].map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </Field>
        {goalType === "other" ? (
          <Field label="Goal detail">
            <input
              required
              maxLength={300}
              value={goalDetail}
              onChange={(change) => setGoalDetail(change.target.value)}
            />
          </Field>
        ) : null}
        <Field label="Description">
          <textarea
            maxLength={1000}
            value={description}
            onChange={(change) => setDescription(change.target.value)}
          />
        </Field>
        <div className="flex flex-wrap gap-3">
          <button type="submit" className="primary-button" disabled={busy}>
            Save changes
          </button>
          {event.state !== "archived" ? (
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void archive()}
            >
              Archive Event
            </button>
          ) : null}
        </div>
      </form>
    </details>
  );
}

function ImportPanel({
  eventId,
  attendeeCount,
  onImported,
  setError,
}: {
  eventId: string;
  attendeeCount: number;
  onImported: () => Promise<void>;
  setError: (value: string | null) => void;
}) {
  const [fileName, setFileName] = useState("");
  const [contentBase64, setContentBase64] = useState("");
  const [preview, setPreview] = useState<EventImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [attested, setAttested] = useState(false);
  const [busy, setBusy] = useState(false);

  async function previewFile(
    name: string,
    content: string,
    columnMapping: Record<string, string | null>,
  ) {
    setBusy(true);
    setError(null);
    try {
      const value = await apiRequest<EventImportPreview>(
        `/api/v1/engage/events/${eventId}/attendee-imports/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            fileName: name,
            contentBase64: content,
            columnMapping,
          }),
        },
      );
      setPreview(value);
      setMapping(
        Object.fromEntries(
          [...value.recognised, ...value.ignored].map((item) => [
            item.sourceColumn,
            item.mappedField,
          ]),
        ),
      );
    } catch (reason: unknown) {
      setError(message(reason, "The attendee list could not be previewed."));
    } finally {
      setBusy(false);
    }
  }

  async function chooseFile(change: ChangeEvent<HTMLInputElement>) {
    const file = change.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("Attendee CSV files may be at most 5 MB.");
      return;
    }
    const encoded = base64FromBuffer(await file.arrayBuffer());
    setFileName(file.name);
    setContentBase64(encoded);
    await previewFile(file.name, encoded, {});
  }

  async function confirmImport() {
    if (!preview || !attested) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest(
        `/api/v1/engage/events/${eventId}/attendee-imports/${preview.id}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            confirmed: true,
            authorityAttested: true,
            attestationVersion: 1,
          }),
        },
      );
      setPreview(null);
      setContentBase64("");
      setFileName("");
      setAttested(false);
      await onImported();
    } catch (reason: unknown) {
      setError(message(reason, "The attendee list could not be imported."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Attendee list</h2>
      <p className="mt-2 text-sm text-slate-600">
        {attendeeCount} imported · CSV only · 5 MB and 500 rows maximum. Raw
        files are not retained.
      </p>
      <label className="secondary-button mt-5 cursor-pointer">
        Choose CSV
        <input
          className="sr-only"
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => void chooseFile(event)}
        />
      </label>
      {busy ? (
        <p role="status" className="mt-3 text-sm">
          Reviewing list…
        </p>
      ) : null}
      {preview ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl bg-slate-50 p-4 text-sm">
            <p className="font-bold">
              Review {preview.validRowCount} valid of {preview.rowCount} rows
            </p>
            <p className="mt-1 text-slate-600">
              Preview expires{" "}
              {new Intl.DateTimeFormat("en-AU", {
                dateStyle: "medium",
                timeStyle: "short",
              }).format(new Date(preview.expiresAt))}
              .
            </p>
          </div>
          <div>
            <h3 className="font-semibold">Column mapping</h3>
            <div className="mt-2 grid gap-2">
              {Object.entries(mapping).map(([source, target]) => (
                <label
                  key={source}
                  className="grid grid-cols-[1fr_1fr] items-center gap-3 text-sm"
                >
                  <span className="truncate" title={source}>
                    {source}
                  </span>
                  <select
                    className="rounded-lg border border-slate-300 px-2 py-1.5"
                    value={target ?? ""}
                    onChange={(event) =>
                      setMapping((current) => ({
                        ...current,
                        [source]: event.target.value || null,
                      }))
                    }
                  >
                    <option value="">Ignore</option>
                    {importFields.map((field) => (
                      <option key={field} value={field}>
                        {humanise(field)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <button
              type="button"
              className="mt-3 text-sm font-bold text-teal-800 underline"
              onClick={() => void previewFile(fileName, contentBase64, mapping)}
            >
              Apply mapping and review again
            </button>
          </div>
          {preview.issues.length ? (
            <div>
              <h3 className="font-semibold">Import checks</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {preview.issues.map((issue) => (
                  <li key={issue.code}>
                    {issue.count} · {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <label className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            <input
              className="mt-1 size-4"
              type="checkbox"
              checked={attested}
              onChange={(event) => setAttested(event.target.checked)}
            />
            <span>
              <strong>Authority confirmation</strong>
              <br />
              {preview.authorityStatement}
              <br />
              <span className="mt-2 block text-xs">
                {preview.permissionNotice}
              </span>
            </span>
          </label>
          <button
            className="primary-button w-full sm:w-auto"
            type="button"
            disabled={!attested || busy}
            onClick={() => void confirmImport()}
          >
            Confirm authorised import
          </button>
        </div>
      ) : null}
    </div>
  );
}

function AttendeeCard({
  event,
  attendee,
  selected,
  onSelect,
  onChanged,
  setError,
  setNotice,
}: {
  event: SalesEvent;
  attendee: EventAttendee;
  selected: boolean;
  onSelect: (contactId: string, checked: boolean) => void;
  onChanged: () => Promise<void>;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [sellerNote, setSellerNote] = useState(attendee.sellerNote ?? "");
  async function mutate(path: string, body: object, method = "POST") {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiRequest(path, { method, body: JSON.stringify(body) });
      await onChanged();
    } catch (reason: unknown) {
      setError(message(reason, "The attendee could not be updated."));
    } finally {
      setBusy(false);
    }
  }
  async function plan(planState: EventPlanState) {
    await mutate(
      `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/plan`,
      { planState, meetingArranged: attendee.meetingArranged },
    );
  }
  async function met() {
    await mutate(
      `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/encounter`,
      {
        state: "met",
        sellerNote: sellerNote.trim() || null,
        createInteraction: false,
      },
    );
    setNotice(
      "Marked met. The note remains seller-reported; no Evidence or Interaction was created.",
    );
  }
  async function followUpLater() {
    await mutate(
      `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/encounter`,
      {
        state: "follow_up",
        sellerNote: sellerNote.trim() || null,
        createInteraction: false,
      },
    );
    setNotice("Added to the Event follow-up queue. No message was sent.");
  }
  async function startCapture() {
    if (!attendee.contactId) {
      setError(
        "Add this attendee to Sales before starting full conversation capture.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await apiRequest<EventAttendee>(
        `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/encounter`,
        {
          method: "POST",
          body: JSON.stringify({
            state: "met",
            sellerNote: sellerNote.trim() || null,
            createInteraction: true,
            interactionLifecycle: "planned",
          }),
        },
      );
      if (!updated.interactionId) {
        throw new Error("The companion Interaction was not created.");
      }
      router.push(`/interactions/${updated.interactionId}/companion`);
    } catch (reason: unknown) {
      setError(message(reason, "Conversation capture could not be started."));
      setBusy(false);
    }
  }
  async function promote() {
    await mutate(
      `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/promote`,
      {
        confirmed: true,
        companyId: attendee.companyId,
        createCompany: !attendee.companyId,
      },
      "POST",
    );
    setNotice("Attendee added to Sales with Event-list provenance.");
  }
  async function outreach(stage: "pre_event" | "post_event") {
    await mutate(
      `/api/v1/engage/events/${event.id}/attendees/${attendee.id}/outreach`,
      { stage },
    );
    setNotice("A review-required Event outreach draft was created.");
  }
  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{attendee.displayName}</h2>
            <Status>{humanise(attendee.priorityState)}</Status>
            {attendee.activeOpportunityId ? (
              <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-900">
                Active Opportunity
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-slate-700">
            {[attendee.jobTitle, attendee.companyName]
              .filter(Boolean)
              .join(" · ") || "Professional context incomplete"}
          </p>
          <p className="mt-2 text-xs font-semibold text-slate-500">
            {humanise(attendee.matchState)} · Email{" "}
            {humanise(attendee.emailTrustState)} · Permission not assessed
          </p>
          <ul className="mt-3 space-y-1 text-sm text-slate-600">
            {attendee.priorityReasons.map((reason) => (
              <li key={reason}>• {reason}</li>
            ))}
          </ul>
        </div>
        {attendee.contactId ? (
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={selected}
              onChange={(change) =>
                onSelect(attendee.contactId!, change.target.checked)
              }
            />{" "}
            Campaign
          </label>
        ) : null}
      </div>
      <label className="mt-4 block text-sm font-semibold text-slate-800">
        Quick seller note (optional)
        <textarea
          className="mt-2 min-h-20 w-full rounded-xl border border-slate-300 px-3 py-2.5 font-normal focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-200"
          maxLength={1000}
          value={sellerNote}
          disabled={busy || event.readOnly}
          onChange={(change) => setSellerNote(change.target.value)}
          placeholder="What happened or what needs follow-up?"
        />
        <span className="mt-1 block text-xs font-normal text-slate-500">
          Seller-reported context only. This does not become customer Evidence.
        </span>
      </label>
      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || event.readOnly}
          onClick={() =>
            void plan(
              attendee.planState === "planned" ? "not_planned" : "planned",
            )
          }
          className="secondary-button"
        >
          {attendee.planState === "planned" ? "Unplan" : "Plan to meet"}
        </button>
        <button
          type="button"
          disabled={busy || event.readOnly}
          onClick={() => void met()}
          className="min-h-12 rounded-xl bg-teal-700 px-5 py-3 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
        >
          Mark met
        </button>
        <button
          type="button"
          disabled={busy || event.readOnly}
          onClick={() => void followUpLater()}
          className="secondary-button"
        >
          Follow up later
        </button>
        {attendee.contactId ? (
          <button
            type="button"
            disabled={busy || event.readOnly}
            onClick={() => void startCapture()}
            className="secondary-button"
          >
            Start Companion
          </button>
        ) : null}
        {!attendee.contactId && (attendee.companyId || attendee.companyName) ? (
          <button
            type="button"
            disabled={busy || event.readOnly}
            onClick={() => void promote()}
            className="secondary-button"
          >
            Add to Sales
          </button>
        ) : null}
        {attendee.contactId ? (
          <button
            type="button"
            disabled={busy || event.readOnly}
            onClick={() =>
              void outreach(attendee.encounterId ? "post_event" : "pre_event")
            }
            className="secondary-button"
          >
            Draft {attendee.encounterId ? "follow-up" : "meeting request"}
          </button>
        ) : null}
        {attendee.canResearch && attendee.companyDomain ? (
          <Link
            className="secondary-button"
            href={`/find?query=${encodeURIComponent(attendee.companyDomain)}`}
          >
            Research
          </Link>
        ) : null}
        {attendee.profileUrl ? (
          <a
            className="secondary-button"
            href={attendee.profileUrl}
            target="_blank"
            rel="noreferrer"
          >
            Profile
          </a>
        ) : null}
      </div>
      {attendee.sellerNote ? (
        <p className="mt-4 rounded-2xl bg-slate-50 p-3 text-sm">
          <strong>Seller note:</strong> {attendee.sellerNote}
        </p>
      ) : null}
      {attendee.plannedByTeammateCount ? (
        <p className="mt-3 text-xs font-semibold text-slate-500">
          {attendee.plannedByTeammateCount} teammate
          {attendee.plannedByTeammateCount === 1 ? "" : "s"} also planned
          activity.
        </p>
      ) : null}
    </article>
  );
}

function ActivityPanel({
  event,
  attendees,
}: {
  event: SalesEvent;
  attendees: EventAttendee[];
}) {
  const active = attendees.filter(
    (item) => item.encounterId || item.planState !== "not_planned",
  );
  return (
    <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Event activity</h2>
      {active.length ? (
        <ul className="mt-4 divide-y divide-slate-100">
          {active.map((item) => (
            <li key={item.id} className="py-3 text-sm">
              <span className="font-semibold">{item.displayName}</span> ·{" "}
              {item.encounterId
                ? "Seller reported met"
                : humanise(item.planState)}
              {item.interactionId ? " · Interaction captured" : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-600">
          No planning or seller-reported encounters yet.
        </p>
      )}
      <p className="mt-4 text-xs text-slate-500">
        Marking met records seller-reported Event activity only. Evidence and
        Revenue Brain updates require a separate Interaction capture and normal
        review.
      </p>
      {event.campaigns.length ? (
        <div className="mt-5">
          <h3 className="font-semibold">Linked Campaigns</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {event.campaigns.map((campaign) => (
              <li key={campaign.campaignId}>
                <Link
                  className="font-bold text-teal-800"
                  href={`/campaigns/${campaign.campaignId}`}
                >
                  {campaign.name}
                </Link>{" "}
                · {humanise(campaign.stage)} · {humanise(campaign.state)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
