import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Interaction, MicrosoftCalendarEvent } from "@revenueos/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MicrosoftCalendarContext } from "@/components/microsoft-calendar-context";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
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
      return Promise.resolve(jsonResponse({ items: [linkedEvent], total: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MicrosoftCalendarContext interactions={[interaction]} />);
    expect(
      await screen.findByRole("link", { name: "Prepare →" }),
    ).toBeVisible();
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

  it("does not offer relationship linkage for private events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
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
          }),
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
