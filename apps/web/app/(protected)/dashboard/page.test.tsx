import type { DailyResponse, EntityPage, Interaction } from "@revenueos/shared";
import { render, screen } from "@testing-library/react";
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

function mockHome(day: DailyResponse = dailyFixture()) {
  mockedApiRequest.mockImplementation((path) => {
    if (String(path).startsWith("/api/v1/daily")) return Promise.resolve(day);
    return Promise.resolve({ items: [recent] } as EntityPage<Interaction>);
  });
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
    expect(screen.getByRole("link", { name: "Prepare now" })).toHaveAttribute(
      "href",
      "/conversations/interaction-1#preparation",
    );
    expect(
      screen.getByRole("heading", { name: "Follow-ups needing attention" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      "/conversations/interaction-2#follow-up",
    );
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
  });
});
