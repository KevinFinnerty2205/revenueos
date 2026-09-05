import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BillingSubscriptionSettings } from "@/components/billing-subscription-settings";
import type { BillingProjection } from "@revenueos/shared";

const options = [
  ["core", "Core", "monthly", "200.00", 5, "AUD $200 billed monthly."],
  [
    "core",
    "Core",
    "annual",
    "2000.00",
    5,
    "AUD $2,000 billed annually as an annual prepayment.",
  ],
  ["growth", "Growth", "monthly", "350.00", 10, "AUD $350 billed monthly."],
  [
    "growth",
    "Growth",
    "annual",
    "3500.00",
    10,
    "AUD $3,500 billed annually as an annual prepayment.",
  ],
  ["complete", "Complete", "monthly", "500.00", 15, "AUD $500 billed monthly."],
  [
    "complete",
    "Complete",
    "annual",
    "5000.00",
    15,
    "AUD $5,000 billed annually as an annual prepayment.",
  ],
].map(
  ([
    planCode,
    displayName,
    billingInterval,
    amount,
    includedUserLimit,
    paymentStatement,
  ]) => ({
    planCode,
    displayName,
    billingInterval,
    amount,
    currency: "AUD",
    includedUserLimit,
    selfServiceAvailable: true,
    paymentStatement,
  }),
);

function projection(
  subscription: BillingProjection["subscription"] = null,
): BillingProjection {
  return {
    configured: subscription !== null,
    provider: "deterministic",
    mode: "test",
    legalEntityName: "Management Services Australia Pty. Ltd.",
    legalEntityAbn: "15 113 119 556",
    subscription,
    invoices: [],
    checkoutOptions: [
      ...options,
      {
        planCode: "enterprise",
        displayName: "Enterprise",
        billingInterval: null,
        amount: null,
        currency: "AUD",
        includedUserLimit: null,
        selfServiceAvailable: false,
        paymentStatement: "Contact us for a manual commercial process.",
      },
    ] as BillingProjection["checkoutOptions"],
    portalAvailable: subscription !== null,
    message:
      subscription === null
        ? "Billing is not configured or is manually managed. No provider subscription is being represented."
        : "Payment needs attention. Existing data has not been deleted; use hosted billing management to resolve it.",
  };
}

describe("BillingSubscriptionSettings", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("shows honest no-card state and prepares server-priced hosted checkout", async () => {
    const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (
        url.endsWith("/api/v1/billing") &&
        (init?.method ?? "GET") === "GET"
      ) {
        return Promise.resolve(
          new Response(JSON.stringify(projection()), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            operationId: "00000000-0000-4000-8000-000000000099",
            checkoutUrl: "https://checkout.stripe.test/pay/session",
            status: "redirect_ready",
            planCode: "core",
            billingInterval: "annual",
            amount: "2000.00",
            currency: "AUD",
            paymentStatement:
              "AUD $2,000 billed annually as an annual prepayment.",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetch);
    render(<BillingSubscriptionSettings />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByText(/Billing not configured/i)).toBeVisible();
    expect(screen.getByText(/trial remains no-card/i)).toBeVisible();
    expect(screen.getByText(/Management Services Australia/i)).toBeVisible();
    expect(screen.getByText(/test mode only/i)).toBeVisible();
    expect(screen.queryByText(/Enterprise ·/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: /Core · annual/i }));
    expect(screen.getByText("Review before continuing")).toBeVisible();
    expect(
      screen.getAllByText(/AUD \$2,000 billed annually/i).length,
    ).toBeGreaterThan(0);
    fireEvent.click(
      screen.getByRole("button", { name: "Prepare secure checkout" }),
    );
    expect(
      await screen.findByRole("link", { name: "Continue to hosted billing" }),
    ).toHaveAttribute("href", "https://checkout.stripe.test/pay/session");
    const posted = JSON.parse(
      String(fetch.mock.calls.at(-1)?.[1]?.body),
    ) as Record<string, unknown>;
    expect(posted).toMatchObject({
      planCode: "core",
      billingInterval: "annual",
    });
    expect(posted).not.toHaveProperty("amount");
    expect(posted).not.toHaveProperty("currency");
  });

  it("shows payment attention, cancellation timing and reconciled invoices", async () => {
    const current = projection({
      id: "00000000-0000-4000-8000-000000000080",
      planCode: "growth",
      planName: "Growth",
      billingInterval: "annual",
      amount: "3500.00",
      currency: "AUD",
      status: "past_due",
      currentPeriodStart: "2032-04-01T00:00:00Z",
      currentPeriodEnd: "2033-04-01T00:00:00Z",
      cancelAtPeriodEnd: true,
      pendingPlanCode: "complete",
      pendingBillingInterval: "annual",
      paymentNeedsAttention: true,
    });
    current.invoices = [
      {
        id: "00000000-0000-4000-8000-000000000081",
        invoiceDate: "2032-04-01T00:00:00Z",
        amountDue: "3500.00",
        amountPaid: "0.00",
        taxAmount: null,
        currency: "AUD",
        status: "open",
        hostedInvoiceUrl: "https://invoice.stripe.test/i/example",
        receiptUrl: null,
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(current), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<BillingSubscriptionSettings />);

    expect(await screen.findByText("Growth")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Payment needs attention",
    );
    expect(
      screen.getByText(/Access continues until 1 April 2033/i),
    ).toBeVisible();
    expect(
      screen.getByText(/Plan change scheduled for next renewal/i),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Keep subscription" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("radio", { name: /Core · monthly/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("link", { name: "View provider invoice" }),
    ).toBeVisible();
  });

  it("uses a fresh hosted checkout after a subscription has ended", async () => {
    const ended = projection({
      id: "00000000-0000-4000-8000-000000000082",
      planCode: "core",
      planName: "Core",
      billingInterval: "monthly",
      amount: "200.00",
      currency: "AUD",
      status: "cancelled",
      currentPeriodStart: "2032-04-01T00:00:00Z",
      currentPeriodEnd: "2032-05-01T00:00:00Z",
      cancelAtPeriodEnd: false,
      pendingPlanCode: null,
      pendingBillingInterval: null,
      paymentNeedsAttention: false,
    });
    const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET") {
        return Promise.resolve(
          new Response(JSON.stringify(ended), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            operationId: "00000000-0000-4000-8000-000000000083",
            checkoutUrl: "https://checkout.stripe.test/pay/reactivation",
            status: "redirect_ready",
            planCode: "growth",
            billingInterval: "monthly",
            amount: "350.00",
            currency: "AUD",
            paymentStatement: "AUD $350 billed monthly.",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetch);
    render(<BillingSubscriptionSettings />);

    expect(await screen.findByText("cancelled")).toBeVisible();
    expect(screen.getByText("Choose a paid plan")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Cancel at period end" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Growth · monthly/i }));
    fireEvent.click(
      screen.getByRole("button", { name: "Prepare secure checkout" }),
    );
    expect(
      await screen.findByRole("link", { name: "Continue to hosted billing" }),
    ).toBeVisible();
    expect(String(fetch.mock.calls.at(-1)?.[0])).toContain(
      "/api/v1/billing/checkout",
    );
  });

  it("shows a safe load error and keyboard-operable retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.reject(new Error("Billing information could not be loaded.")),
      ),
    );
    render(<BillingSubscriptionSettings />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "RevenueOS could not reach the service.",
    );
    const retry = screen.getByRole("button", { name: "Try again" });
    retry.focus();
    expect(retry).toHaveFocus();
    fireEvent.click(retry);
  });
});
