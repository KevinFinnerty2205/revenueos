import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractionList } from "@/components/interaction-list";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const interactionPage = {
  items: [
    {
      id: "interaction-1",
      organisationId: "organisation-1",
      companyId: "company-1",
      opportunityId: null,
      meetingId: "meeting-1",
      interactionType: "online_meeting",
      lifecycleStatus: "planned",
      title: "Acme discovery",
      scheduledStartAt: "2026-08-01T00:00:00Z",
      scheduledEndAt: null,
      actualStartAt: null,
      actualEndAt: null,
      timezone: "Australia/Sydney",
      creationOrigin: "meeting_compatibility",
      createdByUserId: "user-1",
      briefState: "completed",
      briefGeneratedAt: "2026-07-26T00:00:00Z",
      createdAt: "2026-07-26T00:00:00Z",
      updatedAt: "2026-07-26T00:00:00Z",
    },
  ],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

const companyPage = {
  items: [{ id: "company-1", name: "Acme Australia" }],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

const contactPage = {
  items: [
    {
      id: "contact-1",
      companyId: "company-1",
      firstName: "Jordan",
      lastName: "Lee",
    },
  ],
  page: 1,
  pageSize: 100,
  total: 1,
  pages: 1,
};

describe("InteractionList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an account-first directory with deterministic account navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          jsonResponse(
            String(input).includes("/interactions")
              ? interactionPage
              : companyPage,
          ),
        ),
      ),
    );

    render(<InteractionList />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading conversations",
    );
    expect(
      await screen.findByRole("heading", { name: "Account conversations" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Acme Australia" }),
    ).toBeVisible();
    expect(
      screen.getAllByRole("link", { name: "Acme Australia" })[0],
    ).toHaveAttribute("href", "/companies/company-1#conversations");
    expect(
      screen.getByRole("link", { name: "Acme discovery" }),
    ).toHaveAttribute("href", "/conversations/interaction-1");
    expect(
      screen.getByRole("link", { name: "View conversations and notes" }),
    ).toHaveAttribute("href", "/companies/company-1#conversations");
    expect(
      screen.queryByText(/prompt|provider|worker/i),
    ).not.toBeInTheDocument();
  });

  it("applies accessible filters and presents a useful empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/interactions")
            ? { ...interactionPage, items: [], total: 0, pages: 0 }
            : companyPage,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Search conversations"), {
      target: { value: "Acme discovery" },
    });
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "online_meeting" },
    });
    fireEvent.change(screen.getByLabelText("Filter by status"), {
      target: { value: "planned" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => {
          const url = String(input);
          return (
            url.includes("search=Acme+discovery") &&
            url.includes("interactionType=online_meeting") &&
            url.includes("status=planned")
          );
        }),
      ).toBe(true),
    );
  });

  it("hydrates accounts outside the first company page and appends filtered result pages", async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    };
    const firstFilteredPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "phone-101",
          companyId: "company-101",
          meetingId: null,
          interactionType: "phone_call",
          title: "First paged call",
        },
      ],
      total: 2,
      pages: 2,
    };
    const secondFilteredPage = {
      ...firstFilteredPage,
      items: [
        {
          ...firstFilteredPage.items[0],
          id: "phone-102",
          companyId: "company-102",
          title: "Second paged call",
        },
      ],
      page: 2,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/interactions")) {
        if (!path.includes("interactionType=phone_call")) {
          return Promise.resolve(jsonResponse(emptyPage));
        }
        return Promise.resolve(
          jsonResponse(
            path.includes("page=2") ? secondFilteredPage : firstFilteredPage,
          ),
        );
      }
      if (path.includes("/companies/company-101")) {
        return Promise.resolve(
          jsonResponse({ id: "company-101", name: "Outside Page One" }),
        );
      }
      if (path.includes("/companies/company-102")) {
        return Promise.resolve(
          jsonResponse({ id: "company-102", name: "Outside Page Two" }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "phone_call" },
    });

    expect(
      await screen.findByRole("heading", { name: "Outside Page One" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/v1/companies/company-101"),
      ),
    ).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Load more conversations" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Outside Page Two" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Outside Page One" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) => {
        const path = String(input);
        return (
          path.includes("/api/v1/interactions?") &&
          path.includes("page=2") &&
          path.includes("interactionType=phone_call")
        );
      }),
    ).toBe(true);
  });

  it("shows a safe error and supports retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            code: "persistence_unavailable",
            message: "Interactions are temporarily unavailable.",
            requestId: "request-1",
          },
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage))
      .mockResolvedValueOnce(jsonResponse(contactPage))
      .mockResolvedValueOnce(
        jsonResponse({ ...interactionPage, items: [], total: 0, pages: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(companyPage))
      .mockResolvedValueOnce(jsonResponse(contactPage));
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interactions are temporarily unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No conversations found" }),
    ).toBeVisible();
  });

  it("shows phone direction, contact, duration, capture and intelligence readiness", async () => {
    const phonePage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "overdue",
          title: "Overdue discovery",
          scheduledStartAt: "2025-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "phone-1",
          title: "Commercial call",
          companyId: null,
          meetingId: null,
          contactId: "contact-1",
          interactionType: "phone_call",
          lifecycleStatus: "completed",
          callDirection: "outbound",
          callOutcome: "connected",
          durationSeconds: 185,
          captureMethods: ["debrief", "recording"],
          intelligenceState: "ready",
          recordingAvailable: true,
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(phonePage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByRole("heading", { name: "Commercial call" }),
    ).toBeVisible();
    expect(screen.getByText("Outbound")).toBeVisible();
    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("· 3m 5s")).toBeVisible();
    expect(screen.getByText("· Connected")).toBeVisible();
    expect(
      screen.getByText(
        "Capture: Debrief · Recording · Intelligence ready · Recording available",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open notes and follow-up" }),
    ).toHaveAttribute("href", "/conversations/phone-1#debrief");
    expect(
      screen.getByRole("heading", {
        name: "General and unassigned conversations",
      }),
    ).toBeVisible();
  });

  it("groups several conversations beneath one account instead of repeating it", async () => {
    const groupedPage = {
      ...interactionPage,
      items: [
        interactionPage.items[0],
        {
          ...interactionPage.items[0],
          id: "interaction-2",
          title: "Acme follow-up",
          briefState: "not_generated",
        },
      ],
      total: 2,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(groupedPage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(
      await screen.findByText("2 conversations · 1 prepared"),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Acme Australia 2 conversations",
      }),
    ).toHaveAttribute("href", "/companies/company-1#conversations");
    expect(
      screen.getByRole("link", { name: "Acme Australia" }),
    ).toHaveAttribute("href", "/companies/company-1#conversations");
    expect(
      screen.queryByRole("heading", { name: "Acme follow-up" }),
    ).not.toBeInTheDocument();
  });

  it("highlights the nearest future conversation rather than the farthest", async () => {
    const groupedPage = {
      ...interactionPage,
      items: [
        {
          ...interactionPage.items[0],
          id: "overdue-meeting",
          title: "Overdue discovery",
          scheduledStartAt: "2025-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "far-future",
          title: "Annual review",
          scheduledStartAt: "2031-08-01T00:00:00Z",
        },
        {
          ...interactionPage.items[0],
          id: "next-meeting",
          title: "Next discovery",
          scheduledStartAt: "2030-08-01T00:00:00Z",
        },
      ],
      total: 3,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path.includes("/interactions")) {
          return Promise.resolve(jsonResponse(groupedPage));
        }
        if (path.includes("/contacts")) {
          return Promise.resolve(jsonResponse(contactPage));
        }
        return Promise.resolve(jsonResponse(companyPage));
      }),
    );

    render(<InteractionList />);
    expect(await screen.findByText("Next conversation")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Next discovery" }),
    ).toHaveAttribute("href", "/conversations/next-meeting");
    expect(
      screen.queryByRole("link", { name: "Annual review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Overdue discovery" }),
    ).not.toBeInTheDocument();
  });
});
