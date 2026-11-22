import type {
  Company,
  DailyResponse,
  Interaction,
  TenantEntityPage,
} from "@revenueos/shared";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(protected)/dashboard/page";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
const organisationId = "organisation-1";
const verifiedOrganisation = vi.hoisted(() => ({
  state: {
    status: "available" as "available" | "loading" | "unavailable",
    organisationId: "organisation-1" as string | null,
  },
}));
vi.mock("@/components/verified-organisation-context", () => ({
  useVerifiedOrganisation: () => verifiedOrganisation.state,
}));

const mockedApiRequest = vi.mocked(apiRequest);

function tenantPage<T>(
  items: T[],
  pageOrganisationId = organisationId,
): TenantEntityPage<T> {
  return {
    organisationId: pageOrganisationId,
    items,
    page: 1,
    pageSize: Math.max(items.length, 1),
    total: items.length,
    pages: items.length === 0 ? 0 : 1,
  };
}

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
        : Promise.resolve(tenantPage(accountItems));
    }
    return historyUnavailable
      ? Promise.reject(new Error("internal history provider detail"))
      : Promise.resolve(tenantPage(historyItems));
  });
}

function mockHome(day: DailyResponse = dailyFixture()) {
  mockHomeSources({ day });
}

describe("conversation-first Home", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
    verifiedOrganisation.state = {
      status: "available",
      organisationId,
    };
  });

  it("waits for verified organisation context before loading private sources", () => {
    verifiedOrganisation.state = {
      status: "loading",
      organisationId: null,
    };

    render(<DashboardPage />);

    expect(screen.getByLabelText("Loading conversation home")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(mockedApiRequest).not.toHaveBeenCalled();
  });

  it("fails closed when organisation context is unavailable", () => {
    verifiedOrganisation.state = {
      status: "unavailable",
      organisationId: null,
    };

    render(<DashboardPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Oryntela couldn’t verify your organisation.",
    );
    expect(mockedApiRequest).not.toHaveBeenCalled();
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
    let resolveAccounts: (value: TenantEntityPage<Company>) => void = () =>
      undefined;
    const pendingAccounts = new Promise<TenantEntityPage<Company>>(
      (resolve) => {
        resolveAccounts = resolve;
      },
    );
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        return Promise.reject(new Error("internal daily provider detail"));
      }
      if (String(path).startsWith("/api/v1/companies")) {
        return pendingAccounts;
      }
      return Promise.resolve(tenantPage([recent]));
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
      resolveAccounts(tenantPage([account]));
    });
    expect(
      await screen.findByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();
  });

  it("shows a successful Daily view without waiting for optional sources", async () => {
    let resolveAccounts: (value: TenantEntityPage<Company>) => void = () =>
      undefined;
    let resolveHistory: (value: TenantEntityPage<Interaction>) => void = () =>
      undefined;
    const pendingAccounts = new Promise<TenantEntityPage<Company>>(
      (resolve) => {
        resolveAccounts = resolve;
      },
    );
    const pendingHistory = new Promise<TenantEntityPage<Interaction>>(
      (resolve) => {
        resolveHistory = resolve;
      },
    );
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
      resolveAccounts(tenantPage([account]));
      resolveHistory(tenantPage([recent]));
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

  it("retries unavailable secondary sources from the fatal Home state", async () => {
    let dailyRequests = 0;
    let accountRequests = 0;
    let historyRequests = 0;
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        dailyRequests += 1;
        return Promise.reject(new Error("Daily remains unavailable"));
      }
      if (String(path).startsWith("/api/v1/companies")) {
        accountRequests += 1;
        return accountRequests === 1
          ? Promise.reject(new Error("initial account failure"))
          : Promise.resolve(tenantPage([account]));
      }
      historyRequests += 1;
      return Promise.reject(new Error("history remains unavailable"));
    });
    render(<DashboardPage />);

    expect(await screen.findByRole("alert")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();
    expect(dailyRequests).toBe(2);
    expect(accountRequests).toBe(2);
    expect(historyRequests).toBe(2);
  });

  it("retries only Daily and preserves confirmed relationship memory when retry fails", async () => {
    let dailyAttempt = 0;
    let accountRequests = 0;
    let historyRequests = 0;
    let rejectRetriedDaily: (reason: unknown) => void = () => undefined;
    const retriedDaily = new Promise<DailyResponse>((_resolve, reject) => {
      rejectRetriedDaily = reject;
    });
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        dailyAttempt += 1;
        return dailyAttempt === 1
          ? Promise.reject(new Error("initial Daily failure"))
          : retriedDaily;
      }
      if (String(path).startsWith("/api/v1/companies")) {
        accountRequests += 1;
        return accountRequests === 1
          ? Promise.resolve(tenantPage([account]))
          : Promise.reject(new Error("accounts must not be retried"));
      }
      historyRequests += 1;
      return historyRequests === 1
        ? Promise.resolve(tenantPage([recent]))
        : Promise.reject(new Error("history must not be retried"));
    });
    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Conversation workspace" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Try Daily again" }));
    expect(
      screen.getByRole("button", { name: "Trying again…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();

    await act(async () => {
      rejectRetriedDaily(new Error("retried Daily failure"));
      await retriedDaily.catch(() => undefined);
    });

    expect(
      await screen.findByRole("button", { name: "Try Daily again" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("link", { name: /Founder coffee notes/u }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /Northstar Labs.*conversation memory/u,
      }),
    ).toBeVisible();
    expect(dailyAttempt).toBe(2);
    expect(accountRequests).toBe(1);
    expect(historyRequests).toBe(1);
  });

  it("keeps the reduced Home visible while retrying and restores Daily on success", async () => {
    let dailyAttempt = 0;
    let accountRequests = 0;
    let historyRequests = 0;
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
        accountRequests += 1;
        return accountRequests === 1
          ? Promise.resolve(tenantPage([account]))
          : Promise.reject(new Error("accounts must not be retried"));
      }
      historyRequests += 1;
      return historyRequests === 1
        ? Promise.resolve(tenantPage([recent]))
        : Promise.reject(new Error("history must not be retried"));
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
    expect(dailyAttempt).toBe(2);
    expect(accountRequests).toBe(1);
    expect(historyRequests).toBe(1);
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

  it.each([
    { invalidSource: "accounts" as const },
    { invalidSource: "history" as const },
  ])(
    "rejects a wrong-organisation $invalidSource page without discarding the independent source",
    async ({ invalidSource }) => {
      mockedApiRequest.mockImplementation((path) => {
        if (String(path).startsWith("/api/v1/daily")) {
          return Promise.reject(new Error("Daily is unavailable"));
        }
        if (String(path).startsWith("/api/v1/companies")) {
          return Promise.resolve(
            tenantPage(
              [account],
              invalidSource === "accounts"
                ? "organisation-other"
                : organisationId,
            ),
          );
        }
        return Promise.resolve(
          tenantPage(
            [recent],
            invalidSource === "history" ? "organisation-other" : organisationId,
          ),
        );
      });

      render(<DashboardPage />);

      if (invalidSource === "accounts") {
        expect(
          await screen.findByRole("link", { name: /Founder coffee notes/u }),
        ).toBeVisible();
        expect(
          screen.getByText(
            "Account conversation links are temporarily unavailable.",
          ),
        ).toBeVisible();
      } else {
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
      }
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
  );

  it("encodes response-derived conversation and account route segments", async () => {
    const unsafeInteractionId = "interaction/unsafe?view=bad#fragment";
    const unsafeCompanyId = "company/unsafe?tab=bad#fragment";
    mockHomeSources({
      accountItems: [
        { ...account, id: unsafeCompanyId, name: "Encoded account" },
      ],
      dayUnavailable: true,
      historyItems: [
        { ...recent, id: unsafeInteractionId, title: "Encoded conversation" },
      ],
    });

    render(<DashboardPage />);

    expect(
      await screen.findByRole("link", { name: /Encoded conversation/u }),
    ).toHaveAttribute(
      "href",
      `/conversations/${encodeURIComponent(unsafeInteractionId)}`,
    );
    expect(
      screen.getByRole("link", {
        name: /Encoded account.*conversation memory/u,
      }),
    ).toHaveAttribute(
      "href",
      `/conversations/accounts/${encodeURIComponent(unsafeCompanyId)}#conversations`,
    );
  });

  it("starts a fresh private-source session when the verified organisation changes", async () => {
    let historyReads = 0;
    let accountReads = 0;
    let dailyReads = 0;
    let resolveOldHistory: (
      value: TenantEntityPage<Interaction>,
    ) => void = () => undefined;
    let resolveOldAccounts: (value: TenantEntityPage<Company>) => void = () =>
      undefined;
    let resolveOldDaily: (value: DailyResponse) => void = () => undefined;
    const oldHistory = new Promise<TenantEntityPage<Interaction>>((resolve) => {
      resolveOldHistory = resolve;
    });
    const oldAccounts = new Promise<TenantEntityPage<Company>>((resolve) => {
      resolveOldAccounts = resolve;
    });
    const oldDaily = new Promise<DailyResponse>((resolve) => {
      resolveOldDaily = resolve;
    });
    const nextOrganisationId = "organisation-2";
    const nextRecent = {
      ...recent,
      id: "interaction-org-2",
      organisationId: nextOrganisationId,
      title: "New organisation conversation",
    };
    const nextAccount = {
      ...account,
      id: "company-org-2",
      organisationId: nextOrganisationId,
      name: "New organisation account",
    };
    mockedApiRequest.mockImplementation((path) => {
      if (String(path).startsWith("/api/v1/daily")) {
        dailyReads += 1;
        return dailyReads === 1
          ? oldDaily
          : Promise.reject(new Error("Daily is unavailable"));
      }
      if (String(path).startsWith("/api/v1/companies")) {
        accountReads += 1;
        return accountReads === 1
          ? oldAccounts
          : Promise.resolve(tenantPage([nextAccount], nextOrganisationId));
      }
      historyReads += 1;
      return historyReads === 1
        ? oldHistory
        : Promise.resolve(tenantPage([nextRecent], nextOrganisationId));
    });

    const { rerender } = render(<DashboardPage />);
    verifiedOrganisation.state = {
      status: "available",
      organisationId: nextOrganisationId,
    };
    rerender(<DashboardPage />);

    expect(
      await screen.findByRole("link", {
        name: /New organisation conversation/u,
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /New organisation account.*conversation memory/u,
      }),
    ).toBeVisible();

    await act(async () => {
      resolveOldHistory(tenantPage([recent]));
      resolveOldAccounts(tenantPage([account]));
      resolveOldDaily(dailyFixture());
      await Promise.all([oldHistory, oldAccounts, oldDaily]);
    });

    expect(screen.queryByText("Founder coffee notes")).not.toBeInTheDocument();
    expect(screen.queryByText("Northstar Labs")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /New organisation conversation/u }),
    ).toBeVisible();
  });
});
