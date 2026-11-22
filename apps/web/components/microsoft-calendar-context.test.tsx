import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { Interaction, MicrosoftCalendarEvent } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MicrosoftCalendarContext } from "@/components/microsoft-calendar-context";

const organisationId = "organisation-1";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

function calendarList(
  items: MicrosoftCalendarEvent[],
  responseOrganisationId = organisationId,
) {
  return {
    organisationId: responseOrganisationId,
    items,
    total: items.length,
  };
}

const interaction: Interaction = {
  id: "interaction-1",
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: null,
  contactId: "contact-1",
  meetingId: null,
  interactionType: "online_meeting",
  lifecycleStatus: "planned",
  title: "Customer discovery",
  scheduledStartAt: "2026-09-10T00:00:00Z",
  scheduledEndAt: "2026-09-10T01:00:00Z",
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  durationSeconds: null,
  captureMethods: [],
  intelligenceState: "not_ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "not_generated",
  briefGeneratedAt: null,
  createdAt: "2026-09-01T00:00:00Z",
  updatedAt: "2026-09-01T00:00:00Z",
};

const linkedEvent: MicrosoftCalendarEvent = {
  id: "calendar-event-1",
  organisationId,
  title: "Customer discovery",
  startAt: "2026-09-10T00:00:00Z",
  endAt: "2026-09-10T01:00:00Z",
  providerTimezone: "UTC",
  attendeeEmails: ["buyer@example.test"],
  location: "Microsoft Teams",
  onlineMeetingUrl: "https://teams.microsoft.com/l/meetup-join/synthetic",
  sensitivity: "normal",
  state: "active",
  matchState: "matched",
  contactId: "contact-1",
  companyId: "company-1",
  opportunityId: null,
  interactionId: "interaction-1",
  lastSyncedAt: "2026-09-01T00:00:00Z",
};

describe("MicrosoftCalendarContext", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explicitly unlinks an event and returns it to the linkable state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({ ...linkedEvent, interactionId: null }),
        );
      }
      if (String(input).includes("/integrations/google/")) {
        return Promise.resolve(jsonResponse(calendarList([])));
      }
      return Promise.resolve(jsonResponse(calendarList([linkedEvent])));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    expect(
      await screen.findByRole("link", { name: "Prepare →" }),
    ).toHaveAttribute("href", "/conversations/interaction-1?view=prepare");
    fireEvent.click(screen.getByRole("button", { name: "Unlink" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Unlink" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByLabelText("Link Customer discovery to an interaction"),
    ).toBeVisible();
    const update = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PUT",
    );
    expect(update).toBeDefined();
    expect(JSON.parse(String(update?.[1]?.body))).toEqual({
      interactionId: null,
    });
  });

  it("keeps each event locked until its own link request settles", async () => {
    const first = {
      ...linkedEvent,
      id: "calendar-event-1",
      title: "First discovery",
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const second = {
      ...linkedEvent,
      id: "calendar-event-2",
      title: "Second discovery",
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const firstUpdate = deferred<Response>();
    const secondUpdate = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PUT") {
        return url.includes(first.id)
          ? firstUpdate.promise
          : secondUpdate.promise;
      }
      if (url.includes("/integrations/google/")) {
        return Promise.resolve(jsonResponse(calendarList([])));
      }
      return Promise.resolve(jsonResponse(calendarList([first, second])));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const firstArticle = (await screen.findByText(first.title)).closest(
      "article",
    );
    const secondArticle = screen.getByText(second.title).closest("article");
    expect(firstArticle).not.toBeNull();
    expect(secondArticle).not.toBeNull();
    if (!firstArticle || !secondArticle) return;

    const firstSelect = within(firstArticle).getByLabelText(
      `Link ${first.title} to an interaction`,
    );
    const secondSelect = within(secondArticle).getByLabelText(
      `Link ${second.title} to an interaction`,
    );
    fireEvent.change(firstSelect, { target: { value: interaction.id } });
    fireEvent.change(secondSelect, { target: { value: interaction.id } });

    fireEvent.click(within(firstArticle).getByRole("button", { name: "Link" }));
    expect(firstSelect).toBeDisabled();
    expect(
      within(firstArticle).getByRole("button", { name: "Linking…" }),
    ).toBeDisabled();
    expect(secondSelect).toBeEnabled();
    expect(
      within(secondArticle).getByRole("button", { name: "Link" }),
    ).toBeEnabled();

    fireEvent.click(
      within(firstArticle).getByRole("button", { name: "Linking…" }),
    );
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT"),
    ).toHaveLength(1);

    fireEvent.click(
      within(secondArticle).getByRole("button", { name: "Link" }),
    );
    expect(secondSelect).toBeDisabled();
    expect(
      within(secondArticle).getByRole("button", { name: "Linking…" }),
    ).toBeDisabled();

    firstUpdate.resolve(
      jsonResponse({
        ...first,
        interactionId: interaction.id,
        matchState: "matched",
      }),
    );
    expect(
      await within(firstArticle).findByRole("link", { name: "Prepare →" }),
    ).toHaveAttribute("href", `/conversations/${interaction.id}?view=prepare`);
    expect(secondSelect).toBeDisabled();
    expect(
      within(secondArticle).getByRole("button", { name: "Linking…" }),
    ).toBeDisabled();

    secondUpdate.resolve(
      jsonResponse({
        ...second,
        interactionId: interaction.id,
        matchState: "matched",
      }),
    );
    expect(
      await within(secondArticle).findByRole("link", { name: "Prepare →" }),
    ).toBeVisible();
  });

  it("rejects a mismatched response without affecting another pending event", async () => {
    const first = {
      ...linkedEvent,
      id: "calendar-event-1",
      title: "First discovery",
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const second = {
      ...linkedEvent,
      id: "calendar-event-2",
      title: "Second discovery",
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const firstUpdate = deferred<Response>();
    const secondUpdate = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "PUT") {
          return url.includes(first.id)
            ? firstUpdate.promise
            : secondUpdate.promise;
        }
        if (url.includes("/integrations/google/")) {
          return Promise.resolve(jsonResponse(calendarList([])));
        }
        return Promise.resolve(jsonResponse(calendarList([first, second])));
      }),
    );

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const firstArticle = (await screen.findByText(first.title)).closest(
      "article",
    );
    const secondArticle = screen.getByText(second.title).closest("article");
    expect(firstArticle).not.toBeNull();
    expect(secondArticle).not.toBeNull();
    if (!firstArticle || !secondArticle) return;

    for (const [article, title] of [
      [firstArticle, first.title],
      [secondArticle, second.title],
    ] as const) {
      fireEvent.change(
        within(article).getByLabelText(`Link ${title} to an interaction`),
        { target: { value: interaction.id } },
      );
      fireEvent.click(within(article).getByRole("button", { name: "Link" }));
    }

    firstUpdate.resolve(
      jsonResponse({
        ...second,
        interactionId: interaction.id,
        matchState: "matched",
      }),
    );
    expect(await within(firstArticle).findByRole("alert")).toHaveTextContent(
      "The calendar event could not be updated. Try again.",
    );
    expect(within(secondArticle).queryByRole("alert")).not.toBeInTheDocument();
    expect(
      within(secondArticle).getByRole("button", { name: "Linking…" }),
    ).toBeDisabled();

    secondUpdate.resolve(
      jsonResponse({
        ...second,
        interactionId: interaction.id,
        matchState: "matched",
      }),
    );
    expect(
      await within(secondArticle).findByRole("link", { name: "Prepare →" }),
    ).toBeVisible();
    expect(within(firstArticle).getByRole("alert")).toBeVisible();
  });

  it("rejects a link response that echoes another interaction", async () => {
    const unlinkedEvent = {
      ...linkedEvent,
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({
            ...unlinkedEvent,
            matchState: "matched",
            interactionId: "interaction-foreign",
          }),
        );
      }
      if (String(input).includes("/integrations/google/")) {
        return Promise.resolve(jsonResponse(calendarList([])));
      }
      return Promise.resolve(jsonResponse(calendarList([unlinkedEvent])));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const select = await screen.findByLabelText(
      "Link Customer discovery to an interaction",
    );
    fireEvent.change(select, { target: { value: interaction.id } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The calendar event could not be updated. Try again.",
    );
    expect(
      screen.queryByRole("link", { name: "Prepare →" }),
    ).not.toBeInTheDocument();
    expect(select).toBeVisible();
  });

  it("rejects an unlink response that remains linked", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({
            ...linkedEvent,
            interactionId: "interaction-foreign",
          }),
        );
      }
      if (String(input).includes("/integrations/google/")) {
        return Promise.resolve(jsonResponse(calendarList([])));
      }
      return Promise.resolve(jsonResponse(calendarList([linkedEvent])));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const prepare = await screen.findByRole("link", { name: "Prepare →" });
    fireEvent.click(screen.getByRole("button", { name: "Unlink" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The calendar event could not be updated. Try again.",
    );
    expect(prepare).toHaveAttribute(
      "href",
      "/conversations/interaction-1?view=prepare",
    );
    expect(screen.getByRole("button", { name: "Unlink" })).toBeEnabled();
  });

  it("atomically rejects a calendar list containing another organisation", async () => {
    const foreignEvent = {
      ...linkedEvent,
      id: "calendar-event-foreign",
      organisationId: "organisation-other",
      title: "Foreign private meeting title",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/integrations/google/")
            ? calendarList([])
            : calendarList([linkedEvent, foreignEvent]),
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(linkedEvent.title)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Foreign private meeting title"),
    ).not.toBeInTheDocument();
  });

  it("rejects a link response owned by another organisation", async () => {
    const unlinkedEvent = {
      ...linkedEvent,
      matchState: "unmatched" as const,
      interactionId: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PUT") {
          return Promise.resolve(
            jsonResponse({
              ...unlinkedEvent,
              organisationId: "organisation-other",
              matchState: "matched",
              interactionId: interaction.id,
            }),
          );
        }
        return Promise.resolve(
          jsonResponse(
            String(input).includes("/integrations/google/")
              ? calendarList([])
              : calendarList([unlinkedEvent]),
          ),
        );
      }),
    );

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const select = await screen.findByLabelText(
      "Link Customer discovery to an interaction",
    );
    fireEvent.change(select, { target: { value: interaction.id } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The calendar event could not be updated. Try again.",
    );
    expect(select).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Prepare →" }),
    ).not.toBeInTheDocument();
  });

  it("rejects an unlink response owned by another organisation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PUT") {
          return Promise.resolve(
            jsonResponse({
              ...linkedEvent,
              organisationId: "organisation-other",
              interactionId: null,
            }),
          );
        }
        return Promise.resolve(
          jsonResponse(
            String(input).includes("/integrations/google/")
              ? calendarList([])
              : calendarList([linkedEvent]),
          ),
        );
      }),
    );

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const prepare = await screen.findByRole("link", { name: "Prepare →" });
    fireEvent.click(screen.getByRole("button", { name: "Unlink" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The calendar event could not be updated. Try again.",
    );
    expect(prepare).toBeVisible();
    expect(screen.getByRole("button", { name: "Unlink" })).toBeEnabled();
  });

  it("clears a selection that is no longer in the interaction options", async () => {
    const unlinkedEvent = {
      ...linkedEvent,
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/integrations/google/")
            ? calendarList([])
            : calendarList([unlinkedEvent]),
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    const select = await screen.findByLabelText(
      "Link Customer discovery to an interaction",
    );
    fireEvent.change(select, { target: { value: interaction.id } });
    expect(select).toHaveValue(interaction.id);
    expect(screen.getByRole("button", { name: "Link" })).toBeEnabled();

    rerender(
      <MicrosoftCalendarContext
        interactions={[
          {
            ...interaction,
            id: "interaction-2",
            title: "Replacement interaction",
          },
        ]}
        organisationId={organisationId}
      />,
    );

    await waitFor(() =>
      expect(
        screen.getByLabelText("Link Customer discovery to an interaction"),
      ).toHaveValue(""),
    );
    const linkButton = screen.getByRole("button", { name: "Link" });
    expect(linkButton).toBeDisabled();
    fireEvent.click(linkButton);
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(false);

    rerender(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    await waitFor(() => expect(select).toHaveValue(""));
  });

  it("keeps an event mutation locked when the visible interaction set changes", async () => {
    const unlinkedEvent = {
      ...linkedEvent,
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const update = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") return update.promise;
      return Promise.resolve(
        jsonResponse(
          String(input).includes("/integrations/google/")
            ? calendarList([])
            : calendarList([unlinkedEvent]),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    fireEvent.change(
      await screen.findByLabelText("Link Customer discovery to an interaction"),
      { target: { value: interaction.id } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Link" }));
    expect(screen.getByRole("button", { name: "Linking…" })).toBeDisabled();

    rerender(
      <MicrosoftCalendarContext
        interactions={[
          interaction,
          {
            ...interaction,
            id: "interaction-2",
            title: "Newly loaded interaction",
          },
        ]}
        organisationId={organisationId}
      />,
    );

    const pendingButton = await screen.findByRole("button", {
      name: "Linking…",
    });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT"),
    ).toHaveLength(1);

    update.resolve(
      jsonResponse({
        ...unlinkedEvent,
        matchState: "matched",
        interactionId: interaction.id,
      }),
    );
    expect(
      await screen.findByRole("link", { name: "Prepare →" }),
    ).toHaveAttribute("href", `/conversations/${interaction.id}?view=prepare`);
  });

  it("encodes event and interaction route segments", async () => {
    const encodedInteraction = {
      ...interaction,
      id: "interaction/with?#characters",
    };
    const unlinkedEvent = {
      ...linkedEvent,
      id: "calendar/event?#characters",
      matchState: "unmatched" as const,
      interactionId: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({
            ...unlinkedEvent,
            matchState: "matched",
            interactionId: encodedInteraction.id,
          }),
        );
      }
      if (String(input).includes("/integrations/google/")) {
        return Promise.resolve(jsonResponse(calendarList([])));
      }
      return Promise.resolve(jsonResponse(calendarList([unlinkedEvent])));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MicrosoftCalendarContext
        interactions={[encodedInteraction]}
        organisationId={organisationId}
      />,
    );
    fireEvent.change(
      await screen.findByLabelText("Link Customer discovery to an interaction"),
      { target: { value: encodedInteraction.id } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    expect(
      await screen.findByRole("link", { name: "Prepare →" }),
    ).toHaveAttribute(
      "href",
      "/conversations/interaction%2Fwith%3F%23characters?view=prepare",
    );
    const update = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PUT",
    );
    expect(String(update?.[0])).toContain(
      "/events/calendar%2Fevent%3F%23characters/interaction",
    );
  });

  it("does not offer relationship linkage for private events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/integrations/google/")
              ? calendarList([])
              : calendarList([
                  {
                    ...linkedEvent,
                    id: "private-event-1",
                    title: "Private event",
                    matchState: "private",
                    interactionId: null,
                  },
                ]),
          ),
        ),
      ),
    );

    render(
      <MicrosoftCalendarContext
        interactions={[interaction]}
        organisationId={organisationId}
      />,
    );
    expect(
      await screen.findByText(
        "Private events cannot be linked to an interaction.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Link" }),
    ).not.toBeInTheDocument();
  });
});
