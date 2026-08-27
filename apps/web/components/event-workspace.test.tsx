import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  EventDetailWorkspace,
  EventListWorkspace,
} from "@/components/event-workspace";

const navigation = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function event(overrides: Record<string, unknown> = {}) {
  return {
    id: "event-1",
    name: "Security Expo Australia",
    eventType: "trade_show",
    startAt: "2026-08-27T00:00:00Z",
    endAt: "2026-08-28T07:00:00Z",
    timezone: "Australia/Sydney",
    locationName: "ICC Sydney",
    city: "Sydney",
    country: "Australia",
    eventUrl: "https://events.example.test/security",
    organiser: "Synthetic Events",
    description: "Synthetic security industry event.",
    goalType: "meet_new_prospects",
    goalDetail: null,
    sourceType: "manual",
    state: "active",
    ownerUserId: "user-1",
    readOnly: false,
    prospectEnrichmentAvailable: true,
    summary: {
      attendeesImported: 1,
      priorityPeople: 1,
      planned: 0,
      met: 0,
      followUp: 0,
      addedToSales: 1,
      interactionsCaptured: 0,
      activeOpportunityContacts: 1,
    },
    campaigns: [],
    createdAt: "2026-08-26T00:00:00Z",
    updatedAt: "2026-08-26T00:00:00Z",
    ...overrides,
  };
}

function attendee(overrides: Record<string, unknown> = {}) {
  return {
    id: "attendee-jane",
    eventId: "event-1",
    firstName: "Jane",
    lastName: "Smith",
    displayName: "Jane Smith",
    companyName: "Northstar Systems",
    jobTitle: "Chief Information Officer",
    businessEmail: "jane@northstar.example",
    emailTrustState: "provider_supplied",
    permissionStatus: "not_assessed",
    countryOrLocation: "Australia",
    profileUrl: "https://profiles.example.test/jane",
    companyDomain: "northstar.example",
    registrationCategory: "Delegate",
    matchState: "matched_contact",
    priorityState: "priority_to_meet",
    priorityReasons: ["Active Opportunity relationship."],
    contactId: "contact-jane",
    companyId: "company-northstar",
    prospectPersonId: null,
    activeOpportunityId: "opportunity-northstar",
    planState: "not_planned",
    meetingArranged: false,
    plannedByTeammateCount: 0,
    encounterId: null,
    interactionId: null,
    sellerNote: null,
    canResearch: true,
    createdAt: "2026-08-26T00:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  navigation.push.mockReset();
});

describe("Events workspace", () => {
  it("shows a restrained first-use path", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({
        items: [],
        total: 0,
        canCreate: true,
        readOnly: false,
        maxActiveEvents: 50,
      }),
    );

    render(<EventListWorkspace />);

    expect(
      await screen.findByRole("heading", {
        name: "Get more from the events you attend",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create Event" })).toHaveAttribute(
      "href",
      "/events/new",
    );
  });

  it("keeps quick notes seller-reported when marking an attendee met", async () => {
    let encounterBody: Record<string, unknown> | null = null;
    let currentAttendee = attendee();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = new URL(String(input)).pathname;
      const method = init?.method ?? "GET";
      if (path === "/api/v1/engage/events/event-1") {
        return jsonResponse(event());
      }
      if (
        path === "/api/v1/engage/events/event-1/attendees" &&
        method === "GET"
      ) {
        return jsonResponse({
          items: [currentAttendee],
          total: 1,
          page: 1,
          pageSize: 100,
        });
      }
      if (path.endsWith("/encounter") && method === "POST") {
        encounterBody = JSON.parse(String(init?.body)) as Record<
          string,
          unknown
        >;
        currentAttendee = attendee({
          encounterId: "encounter-1",
          sellerNote: encounterBody.sellerNote,
          planState: "met",
        });
        return jsonResponse(currentAttendee);
      }
      return jsonResponse({}, 404);
    });

    render(<EventDetailWorkspace eventId="event-1" />);
    await screen.findByRole("heading", { name: "Security Expo Australia" });
    fireEvent.click(screen.getByRole("tab", { name: "People" }));
    fireEvent.change(screen.getByLabelText(/Quick seller note/u), {
      target: { value: "Discussed a technical workshop next week." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Mark met" }));

    await waitFor(() =>
      expect(encounterBody).toEqual({
        state: "met",
        sellerNote: "Discussed a technical workshop next week.",
        createInteraction: false,
      }),
    );
    expect(
      await screen.findByText(/no Evidence or Interaction was created/u),
    ).toBeInTheDocument();
  });

  it("starts the existing Companion from a canonical Contact", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = new URL(String(input)).pathname;
      const method = init?.method ?? "GET";
      if (path === "/api/v1/engage/events/event-1")
        return jsonResponse(event());
      if (path === "/api/v1/engage/events/event-1/attendees")
        return jsonResponse({
          items: [attendee()],
          total: 1,
          page: 1,
          pageSize: 100,
        });
      if (path.endsWith("/encounter") && method === "POST") {
        return jsonResponse(
          attendee({
            encounterId: "encounter-1",
            interactionId: "interaction-event-1",
          }),
        );
      }
      return jsonResponse({}, 404);
    });

    render(<EventDetailWorkspace eventId="event-1" />);
    await screen.findByRole("heading", { name: "Security Expo Australia" });
    fireEvent.click(screen.getByRole("tab", { name: "People" }));
    fireEvent.click(screen.getByRole("button", { name: "Start Companion" }));

    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith(
        "/interactions/interaction-event-1/companion",
      ),
    );
  });
});
