import type { CreditsProjection } from "@revenueos/shared";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreditsSettings } from "@/components/credits-settings";

function projection(): CreditsProjection {
  return {
    unitName: "Oryntela Credit",
    balance: {
      available: 120,
      purchasedAvailable: 100,
      promotionalAvailable: 20,
      reserved: 10,
      purchasedReserved: 0,
      promotionalReserved: 10,
      totalHeld: 130,
    },
    recentActivity: [
      {
        id: "00000000-0000-4000-8000-000000000001",
        eventType: "promotional_grant",
        creditType: "promotional",
        availableChange: 20,
        reservedChange: 0,
        actionCode: null,
        operationId: null,
        reason: "Synthetic authorised grant.",
        createdAt: "2032-04-01T00:00:00Z",
      },
      {
        id: "00000000-0000-4000-8000-000000000002",
        eventType: "reservation",
        creditType: "promotional",
        availableChange: -10,
        reservedChange: 10,
        actionCode: "PROSPECT_COMPANY_RESEARCH",
        operationId: "00000000-0000-4000-8000-000000000003",
        reason: "Synthetic reservation.",
        createdAt: "2032-04-02T00:00:00Z",
      },
    ],
    testPacks: [
      {
        id: "00000000-0000-4000-8000-000000000004",
        packCode: "TEST_100",
        displayName: "100 test Credits",
        version: 1,
        creditQuantity: 100,
        amountMinorUnits: 2000,
        currency: "AUD",
        testOnly: true,
        purchaseAvailable: false,
        pricingNote: "TEST ONLY / NOT CUSTOMER PRICING",
      },
    ],
    lowBalance: false,
    autoTopUp: false,
    productionPricesAvailable: false,
    message:
      "Credits cover meaningful metered external services. Ordinary Oryntela software use is not metered.",
  };
}

describe("CreditsSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows a responsive, customer-safe balance and immutable activity view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(projection()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    const { container } = render(<CreditsSettings />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByText("120")).toBeVisible();
    expect(screen.getByText("100")).toBeVisible();
    expect(screen.getByText("20")).toBeVisible();
    expect(screen.getByText(/10 Credits are reserved/i)).toBeVisible();
    expect(screen.getByText("Promotional grant")).toBeVisible();
    expect(screen.getByText("+20 Credits")).toBeVisible();
    expect(screen.getByText("-10 Credits")).toBeVisible();
    expect(screen.getByText(/ordinary Oryntela software use/i)).toBeVisible();
    expect(screen.queryByText(/provider cost/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Purchase unavailable" }),
    ).toBeDisabled();
    expect(screen.getByText("TEST ONLY / NOT CUSTOMER PRICING")).toBeVisible();
    expect(
      container.querySelector("section.min-w-0.overflow-hidden"),
    ).not.toBeNull();
  });

  it("supports empty and retryable error states", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "credits_unavailable",
            message: "Credit information is unavailable.",
            requestId: "request-credits",
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            ...projection(),
            balance: {
              available: 0,
              purchasedAvailable: 0,
              promotionalAvailable: 0,
              reserved: 0,
              purchasedReserved: 0,
              promotionalReserved: 0,
              totalHeld: 0,
            },
            recentActivity: [],
            testPacks: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetch);
    render(<CreditsSettings />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Credit information is unavailable",
    );
    screen.getByRole("button", { name: "Try again" }).click();
    expect(await screen.findByText("No Credit activity yet.")).toBeVisible();
    expect(screen.getByText(/Automatic top-up is off/i)).toBeVisible();
  });
});
