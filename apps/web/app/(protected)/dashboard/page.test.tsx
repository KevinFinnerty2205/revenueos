import type { DailyResponse } from "@revenueos/shared";
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
    topPriority: {
      kind: "interaction",
      reasonCode: "interaction_needs_preparation",
      title: "Qantas technical review",
      context: "Economic Buyer is still unknown.",
      reason:
        "This customer interaction starts within four hours and has no completed brief.",
      ctaLabel: "Prepare for meeting",
      href: "/interactions/interaction-1#preparation",
      sourceId: "interaction-1",
      startsAt: "2026-08-17T00:00:00Z",
      dueAt: null,
    },
    nextInteraction: {
      id: "interaction-1",
      title: "Qantas technical review",
      companyId: "company-1",
      companyName: "Qantas",
      opportunityId: "opportunity-1",
      opportunityName: "Network modernisation",
      interactionType: "workshop",
      lifecycleStatus: "planned",
      startsAt: "2026-08-17T00:00:00Z",
      preparationState: "not_prepared",
      context: "Economic Buyer is still unknown.",
      ctaLabel: "Prepare for meeting",
      href: "/interactions/interaction-1#preparation",
    },
    todayInteractions: [
      {
        id: "interaction-1",
        title: "Qantas technical review",
        companyId: "company-1",
        companyName: "Qantas",
        opportunityId: "opportunity-1",
        opportunityName: "Network modernisation",
        interactionType: "workshop",
        lifecycleStatus: "planned",
        startsAt: "2026-08-17T00:00:00Z",
        preparationState: "not_prepared",
        context: "Economic Buyer is still unknown.",
        ctaLabel: "Prepare for meeting",
        href: "/interactions/interaction-1#preparation",
      },
    ],
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
          title: "Send security documentation",
          opportunityId: "opportunity-1",
          opportunityName: "Network modernisation",
          companyName: "Qantas",
          priority: "high",
          reviewStatus: "proposed",
          timing: "overdue",
          dueAt: "2026-08-16T01:00:00Z",
          state: "needs_review",
          stateLabel: "Needs review",
          ctaLabel: "Review",
          href: "/opportunities/opportunity-1#recommended-actions",
        },
      ],
    },
    dealAttention: {
      attentionCount: 1,
      truncated: false,
      items: [
        {
          opportunityId: "opportunity-1",
          opportunityName: "Network modernisation",
          companyName: "Qantas",
          estimatedValue: "420000.00",
          currency: "AUD",
          expectedCloseDate: "2026-08-25",
          priority: "urgent",
          reasons: [
            {
              code: "upcoming_close_with_blocker",
              text: "The expected close date is approaching with an unresolved gap.",
            },
            {
              code: "methodology_gap",
              text: "Economic Buyer is still unknown.",
            },
          ],
          href: "/opportunities/opportunity-1",
        },
      ],
    },
    pipeline: {
      state: "single_currency",
      openOpportunityCount: 1,
      unvaluedOpportunityCount: 0,
      currencyCount: 1,
      safeMessage: "Open pipeline and opportunities closing this month.",
      currencies: [
        {
          currency: "AUD",
          openValue: "420000.00",
          closingThisMonthValue: "420000.00",
          openOpportunityCount: 1,
          closingThisMonthCount: 1,
        },
      ],
    },
    recommendations: [
      {
        sourceId: "nba-1",
        opportunityId: "opportunity-1",
        opportunityName: "Network modernisation",
        recommendation: "Confirm access to the economic buyer.",
        priority: "high",
        reason: "Existing Next Best Action from final validated intelligence.",
        ctaLabel: "Review",
        href: "/opportunities/opportunity-1#latest-next-best-action",
      },
    ],
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
    hasOpportunities: true,
    caughtUp: false,
    ...overrides,
  };
}

describe("RevenueOS Daily Home", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
  });

  it("makes one next action obvious and keeps source workflows available", async () => {
    mockedApiRequest.mockResolvedValue(dailyFixture());

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: /good .*alex/i }),
    ).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Top priority")).toBeVisible();
    expect(
      screen.getAllByRole("link", { name: /prepare/i })[0],
    ).toHaveAttribute("href", "/interactions/interaction-1#preparation");
    expect(
      screen.getAllByRole("heading", { name: "Today’s interactions" }),
    ).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Actions" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Deals needing attention" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Open pipeline" }),
    ).toBeVisible();
    expect(screen.getByText("AUD 420,000.00")).toBeVisible();
    expect(
      screen.queryByText("Approved — not complete"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/deal health/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /forecast/i })).toBeNull();
  });

  it("announces a restrained loading state", () => {
    mockedApiRequest.mockReturnValue(new Promise(() => undefined));

    render(<DashboardPage />);

    expect(
      screen.getByRole("heading", { name: "Loading your day…" }),
    ).toBeVisible();
    expect(
      screen
        .getByRole("heading", { name: "Loading your day…" })
        .closest("section"),
    ).toHaveAttribute("aria-busy", "true");
  });

  it("teaches a new user one first step without empty analytics", async () => {
    mockedApiRequest.mockResolvedValue(
      dailyFixture({
        topPriority: null,
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
        dealAttention: { attentionCount: 0, items: [], truncated: false },
        recommendations: [],
        pipeline: {
          state: "empty",
          openOpportunityCount: 0,
          unvaluedOpportunityCount: 0,
          currencyCount: 0,
          currencies: [],
          safeMessage:
            "Open pipeline will appear here when you add an opportunity.",
        },
        hasOpportunities: false,
        caughtUp: true,
      }),
    );

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", {
        name: /let’s get your first deal into revenueos/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Add an opportunity" }),
    ).toHaveAttribute("href", "/opportunities/new");
    expect(screen.queryByRole("heading", { name: "Open pipeline" })).toBeNull();
  });

  it("calmly handles an existing user with no interactions or Actions", async () => {
    const fixture = dailyFixture();
    mockedApiRequest.mockResolvedValue({
      ...fixture,
      topPriority: null,
      nextInteraction: null,
      todayInteractions: [],
      totalTodayInteractions: 0,
      actions: {
        ...fixture.actions,
        attentionCount: 0,
        overdueCount: 0,
        dueTodayCount: 0,
        pendingReviewCount: 0,
        approvedOpenCount: 0,
        items: [],
      },
      dealAttention: { attentionCount: 0, items: [], truncated: false },
      recommendations: [],
      caughtUp: true,
    });

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "You’re caught up." }),
    ).toBeVisible();
    expect(
      screen.getAllByText("No customer interactions scheduled today."),
    ).toHaveLength(2);
    expect(
      screen.getByText("No current Actions need your attention."),
    ).toBeVisible();
  });

  it("degrades one unavailable section without failing Home", async () => {
    const fixture = dailyFixture();
    mockedApiRequest.mockResolvedValue({
      ...fixture,
      actions: { ...fixture.actions, items: [] },
      availability: { ...fixture.availability, actions: false },
    });

    render(<DashboardPage />);

    expect(
      await screen.findByText("Actions temporarily unavailable."),
    ).toBeVisible();
    expect(screen.getAllByText("Qantas technical review")).toHaveLength(2);
    expect(screen.getByText("AUD 420,000.00")).toBeVisible();
  });

  it("offers recovery and normal navigation after a total failure", async () => {
    mockedApiRequest.mockRejectedValue(new Error("safe failure"));

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", {
        name: "RevenueOS couldn’t load your day.",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open interactions" }),
    ).toHaveAttribute("href", "/interactions");
  });
});
