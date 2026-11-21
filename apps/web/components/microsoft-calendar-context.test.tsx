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
        return Promise.resolve(jsonResponse({ items: [], total: 0 }));
      }
      return Promise.resolve(jsonResponse({ items: [linkedEvent], total: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MicrosoftCalendarContext interactions={[interaction]} />);
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
        return Promise.resolve(jsonResponse({ items: [], total: 0 }));
      }
      return Promise.resolve(
        jsonResponse({ items: [first, second], total: 2 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MicrosoftCalendarContext interactions={[interaction]} />);
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
          return Promise.resolve(jsonResponse({ items: [], total: 0 }));
        }
        return Promise.resolve(
          jsonResponse({ items: [first, second], total: 2 }),
        );
      }),
    );

    render(<MicrosoftCalendarContext interactions={[interaction]} />);
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

  it("does not offer relationship linkage for private events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/integrations/google/")
              ? { items: [], total: 0 }
              : {
                  items: [
                    {
                      ...linkedEvent,
                      id: "private-event-1",
                      title: "Private event",
                      matchState: "private",
                      interactionId: null,
                    },
                  ],
                  total: 1,
                },
          ),
        ),
      ),
    );

    render(<MicrosoftCalendarContext interactions={[interaction]} />);
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
