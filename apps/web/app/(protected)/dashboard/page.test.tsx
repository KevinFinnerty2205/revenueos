import type {
  Company,
  DailyResponse,
  EntityPage,
  Interaction,
} from "@revenueos/shared";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(protected)/dashboard/page";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));

const mockedApiRequest = vi.mocked(apiRequest);

function dailyFixture(overrides: Partial<DailyResponse> = {}): DailyResponse {
  return {
    generatedAt: new Date().toISOString(),
    localDate: "2026-08-17",
    timezone: "Australia/Sydney",
    userDisplayName: "Alex Morgan",
    topPriority: null,
    nextInteraction: {
      id: "interaction-1",
      title: "Northstar discovery",
      companyId: "company-1",
      companyName: "Northstar Labs",
      opportunityId: null,
      opportunityName: null,
      participantNames: ["Jordan Lee"],
      interactionType: "online_meeting",
      lifecycleStatus: "planned",
      startsAt: "2026-08-17T00:00:00Z",
      preparationState: "not_prepared",
      context: "Prepare the objective and unresolved questions.",
      ctaLabel: "Prepare",
      href: "/conversations/interaction-1#preparation",
    },
    todayInteractions: [],
    totalTodayInteractions: 1,
    actions: {
      attentionCount: 1,
      overdueCount: 1,
      dueTodayCount: 0,
      pendingReviewCount: 1,
      approvedOpenCount: 0,
      truncated: false,
      items: [
        {
          id: "action-1",
          title: "Send the agreed security summary",
          opportunityId: "opportunity-1",
          interactionId: "interaction-2",
          opportunityName: "Synthetic evaluation",
          companyName: "Northstar Labs",
          priority: "high",
          reviewStatus: "proposed",
          timing: "overdue",
          dueAt: "2026-08-16T01:00:00Z",
          state: "needs_review",
          stateLabel: "Needs review",
          ctaLabel: "Review",
          href: "/conversations/interaction-2#follow-up",
        },
      ],
    },
    privateFollowUps: {
      attentionCount: 1,
      items: [
        {
          interactionId: "interaction-private-follow-up",
          interactionTitle: "Founder debrief follow-up",
          companyName: null,
          updatedAt: "2026-08-16T02:00:00Z",
          ctaLabel: "Review",
          href: "/conversations/interaction-private-follow-up?view=review#follow-up",
        },
      ],
      truncated: false,
    },
    dealAttention: { attentionCount: 0, items: [], truncated: false },
    pipeline: {
      state: "empty",
      openOpportunityCount: 0,
      unvaluedOpportunityCount: 0,
      currencyCount: 0,
      currencies: [],
      safeMessage: "No pipeline context is required for conversations.",
    },
    recommendations: [],
    availability: {
      interactions: true,
      actions: true,
      privateFollowUps: true,
      dealAttention: true,
      pipeline: true,
      recommendations: true,
      methodology: true,
      revenueBrain: true,
      targets: false,
      forecast: false,
    },
    hasOpportunities: false,
    caughtUp: false,
    ...overrides,
  };
}

const recent: Interaction = {
  id: "interaction-2",
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: null,
  contactId: null,
  meetingId: null,
  eventId: null,
  interactionType: "manual_interaction",
  lifecycleStatus: "completed",
  title: "Founder coffee notes",
  scheduledStartAt: null,
  scheduledEndAt: null,
  actualStartAt: "2026-08-16T00:00:00Z",
  actualEndAt: "2026-08-16T00:30:00Z",
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  meetingPlatform: null,
  meetingUrl: null,
  externalMeetingId: null,
  captureSource: null,
  ingestionState: null,
  durationSeconds: 1800,
  captureMethods: ["debrief"],
  intelligenceState: "ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "unavailable",
  briefGeneratedAt: null,
  createdAt: "2026-08-16T00:00:00Z",
  updatedAt: "2026-08-16T00:30:00Z",
};

const account: Company = {
  id: "company-1",
  organisationId: "organisation-1",
  name: "Northstar Labs",
  website: "https://northstar.example.test",
  industry: "Facilities",
  location: "Sydney",
  employeeCount: 120,
  status: "prospect",
  ownerUserId: "user-1",
  archivedAt: null,
  createdAt: "2026-08-15T00:00:00Z",
  updatedAt: "2026-08-15T00:00:00Z",
};

function mockHomeSources({
  accountItems = [account],
  accountUnavailable = false,
  day = dailyFixture(),
  dayUnavailable = false,
  historyItems = [recent],
  historyUnavailable = false,
}: {
  accountItems?: Company[];
  accountUnavailable?: boolean;
  day?: DailyResponse;
  dayUnavailable?: boolean;
  historyItems?: Interaction[];
  historyUnavailable?: boolean;
} = {}) {
  mockedApiRequest.mockImplementation((path) => {
    if (String(path).startsWith("/api/v1/daily")) {
      return dayUnavailable
        ? Promise.reject(new Error("internal daily provider detail"))
        : Promise.resolve(day);
    }
    if (String(path).startsWith("/api/v1/companies")) {
      return accountUnavailable
        ? Promise.reject(new Error("internal account provider detail"))
        : Promise.resolve({ items: accountItems } as EntityPage<Company>);
    }
    return historyUnavailable
      ? Promise.reject(new Error("internal history provider detail"))
      : Promise.resolve({ items: historyItems } as EntityPage<Interaction>);
  });
}

function mockHome(day: DailyResponse = dailyFixture()) {
  mockHomeSources({ day });
}

describe("conversation-first Home", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
  });

  it("prioritises the next conversation, follow-up and searchable memory", async () => {
    mockHome();
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: /good .*alex/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Northstar discovery" }),
    ).toBeVisible();
    expect(screen.getByText("Northstar Labs · Jordan Lee")).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/i,
      }),
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
    );
    expect(
      document.querySelector(
        'img[src="/demo/account-logos/northstar-facilities.svg"]',
      ),
    ).toBeInTheDocument();
    expect(mockedApiRequest).toHaveBeenCalledWith(
      "/api/v1/companies?page=1&pageSize=8&sortBy=name&sortOrder=asc",
      expect.any(Object),
    );
    expect(screen.getByRole("link", { name: "Prepare now" })).toHaveAttribute(
      "href",
      "/conversations/interaction-1#preparation",
    );
    expect(
      screen.getByRole("heading", { name: "Follow-ups needing attention" }),
    ).toBeVisible();
    const followUps = screen.getByRole("list", {
      name: "Follow-ups needing attention",
    });
    const followUpRows = within(followUps).getAllByRole("listitem");
    expect(followUpRows[0]).toHaveTextContent("Founder debrief follow-up");
    expect(followUpRows[1]).toHaveTextContent(
      "Send the agreed security summary",
    );
    expect(
      within(followUps).getByRole("link", { name: "Review private draft" }),
    ).toHaveAttribute(
      "href",
      "/conversations/interaction-private-follow-up?view=review#follow-up",
    );
    expect(
      within(followUps).getByRole("link", { name: "Review" }),
    ).toHaveAttribute("href", "/conversations/interaction-2#follow-up");
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/ }),
    ).toHaveAttribute("href", "/conversations/interaction-2");
    expect(
      screen.queryByRole("heading", { name: /pipeline/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /forecast/i }),
    ).not.toBeInTheDocument();
  });

  it("announces a restrained loading state", () => {
    mockedApiRequest.mockReturnValue(new Promise(() => undefined));
    render(<DashboardPage />);
    expect(screen.getByLabelText("Loading conversation home")).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("does not claim an empty queue when private follow-ups are unavailable", async () => {
    mockHome(
      dailyFixture({
        privateFollowUps: {
          attentionCount: 0,
          items: [],
          truncated: false,
        },
        availability: {
          ...dailyFixture().availability,
          privateFollowUps: false,
        },
      }),
    );
    render(<DashboardPage />);

    expect(
      await screen.findByText(
        "Private follow-up drafts are temporarily unavailable. Shared follow-ups are still shown when available.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Send the agreed security summary")).toBeVisible();
    expect(
      screen.queryByText("No follow-ups need attention right now."),
    ).not.toBeInTheDocument();
  });

  it("starts with knowledge or a conversation instead of CRM setup", async () => {
    mockHome(
      dailyFixture({
        nextInteraction: null,
        todayInteractions: [],
        totalTodayInteractions: 0,
        actions: {
          attentionCount: 0,
          overdueCount: 0,
          dueTodayCount: 0,
          pendingReviewCount: 0,
          approvedOpenCount: 0,
          items: [],
          truncated: false,
        },
        privateFollowUps: {
          attentionCount: 0,
          items: [],
          truncated: false,
        },
      }),
    );
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Nothing is scheduled yet." }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Add conversation" }),
    ).toHaveAttribute("href", "/conversations/new");
    expect(
      screen.getByRole("link", { name: "Set up company knowledge" }),
    ).toHaveAttribute("href", "/knowledge");
    expect(screen.queryByText(/add an opportunity/i)).not.toBeInTheDocument();
    expect(
      screen.getByText("No follow-ups need attention right now."),
    ).toBeVisible();
  });

  it("keeps conversation history and accounts usable when Daily is unavailable", async () => {
    mockHomeSources({ dayUnavailable: true });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Today's schedule and follow-ups are temporarily unavailable/u,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toHaveAttribute("href", "/conversations/interaction-2");
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toHaveAttribute(
      "href",
      "/conversations/accounts/company-1#conversations",
    );
    expect(
      screen.getByRole("link", { name: "Add conversation" }),
    ).toHaveAttribute("href", "/conversations/new");
    expect(
      screen.getAllByRole("link", { name: "Search or ask" })[0],
    ).toHaveAttribute("href", "/assistant");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Upcoming conversations" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "Follow-ups needing attention",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("No other conversations are scheduled today."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("No follow-ups need attention right now."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("internal daily provider detail"),
    ).not.toBeInTheDocument();
  });

  it("keeps recent conversations when account links and Daily are unavailable", async () => {
    mockHomeSources({ accountUnavailable: true, dayUnavailable: true });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Account conversation links are temporarily unavailable.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText(
        "Recent conversation history is temporarily unavailable.",
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps account memory when recent history and Daily are unavailable", async () => {
    mockHomeSources({ dayUnavailable: true, historyUnavailable: true });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Recent conversation history is temporarily unavailable.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Recent conversations" }),
    ).not.toBeInTheDocument();
  });

  it("shows truthful empty secondary sources instead of a fatal Daily error", async () => {
    mockHomeSources({
      accountItems: [],
      dayUnavailable: true,
      historyItems: [],
    });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Accounts" })).toBeVisible();
    expect(
      screen.getByText(
        "Accounts will appear here when a conversation is linked to one.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Recent conversations" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Completed conversations will become your searchable relationship history.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows usable history without waiting for a pending account source", async () => {
    let resolveAccounts: (value: EntityPage<Company>) => void = () => undefined;
    const pendingAccounts = new Promise<EntityPage<Company>>((resolve) => {
      resolveAccounts = resolve;
    });
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        return Promise.reject(new Error("internal daily provider detail"));
      }
      if (String(path).startsWith("/api/v1/companies")) {
        return pendingAccounts;
      }
      return Promise.resolve({ items: [recent] } as EntityPage<Interaction>);
    });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Conversation workspace" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      screen.getByText("Account conversation links are still loading."),
    ).toBeVisible();
    expect(
      screen.queryByText(
        "Account conversation links are temporarily unavailable.",
      ),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try Daily again" }));
    expect(
      screen.getByRole("button", { name: "Trying again…" }),
    ).toBeDisabled();
    expect(
      await screen.findByRole("button", { name: "Try Daily again" }),
    ).toBeEnabled();
    expect(
      screen.getByText("Account conversation links are still loading."),
    ).toBeVisible();

    await act(async () => {
      resolveAccounts({ items: [account] } as EntityPage<Company>);
    });
    expect(
      await screen.findByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();
  });

  it("shows a successful Daily view without waiting for optional sources", async () => {
    let resolveAccounts: (value: EntityPage<Company>) => void = () => undefined;
    let resolveHistory: (value: EntityPage<Interaction>) => void = () =>
      undefined;
    const pendingAccounts = new Promise<EntityPage<Company>>((resolve) => {
      resolveAccounts = resolve;
    });
    const pendingHistory = new Promise<EntityPage<Interaction>>((resolve) => {
      resolveHistory = resolve;
    });
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        return Promise.resolve(dailyFixture());
      }
      if (String(path).startsWith("/api/v1/companies")) {
        return pendingAccounts;
      }
      return pendingHistory;
    });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: /good .*alex/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Northstar discovery" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Recent conversations" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Recent conversation history is still loading."),
    ).toBeVisible();
    expect(
      screen.getByText("Account conversation links are still loading."),
    ).toBeVisible();

    await act(async () => {
      resolveAccounts({ items: [account] } as EntityPage<Company>);
      resolveHistory({ items: [recent] } as EntityPage<Interaction>);
    });
    expect(
      await screen.findByRole("heading", { name: "Recent conversations" }),
    ).toBeVisible();
  });

  it("uses the fatal retry state only when every Home source is unavailable", async () => {
    mockHomeSources({
      accountUnavailable: true,
      dayUnavailable: true,
      historyUnavailable: true,
    });
    render(<DashboardPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Oryntela couldn’t load your conversations.",
    );
    expect(alert).toHaveTextContent(
      "Your conversation workspace is temporarily unavailable. Please try again.",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
    expect(alert).not.toHaveTextContent("internal daily provider detail");
    expect(alert).not.toHaveTextContent("internal history provider detail");
    expect(alert).not.toHaveTextContent("internal account provider detail");
  });

  it("keeps the reduced Home visible while retrying and restores Daily on success", async () => {
    let dailyAttempt = 0;
    let resolveRecoveredDaily: (value: DailyResponse) => void = () => undefined;
    const recoveredDaily = new Promise<DailyResponse>((resolve) => {
      resolveRecoveredDaily = resolve;
    });
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        dailyAttempt += 1;
        return dailyAttempt === 1
          ? Promise.reject(new Error("internal daily provider detail"))
          : recoveredDaily;
      }
      if (String(path).startsWith("/api/v1/companies")) {
        return Promise.resolve({ items: [account] } as EntityPage<Company>);
      }
      return Promise.resolve({ items: [recent] } as EntityPage<Interaction>);
    });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try Daily again" }));
    expect(
      screen.getByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Trying again…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    await act(async () => {
      resolveRecoveredDaily(dailyFixture());
    });
    expect(
      await screen.findByRole("heading", { name: /good .*alex/i }),
    ).toBeVisible();
    expect(
      screen.queryByText(
        /Today's schedule and follow-ups are temporarily unavailable/u,
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps full Daily useful without a false recent-history empty state", async () => {
    mockHomeSources({ historyUnavailable: true });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: /good .*alex/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Northstar discovery" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Recent conversation history is temporarily unavailable. Your next conversation is still shown.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Recent conversations" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("internal history provider detail"),
    ).not.toBeInTheDocument();
  });
});
