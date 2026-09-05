import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BillingSuccess } from "@/components/billing-success";

afterEach(() => vi.unstubAllGlobals());

it("never treats the success URL as entitlement authority", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          confirmed: false,
          status: "not_configured",
          message:
            "Payment confirmation is pending. No entitlement change has been made.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValue(
      new Response(
        JSON.stringify({
          confirmed: true,
          status: "active",
          message:
            "Payment is confirmed and the organisation subscription is active.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  vi.stubGlobal("fetch", fetch);
  render(<BillingSuccess />);

  expect(await screen.findByText("Payment confirmation pending")).toBeVisible();
  expect(
    screen.getByText(/Visiting this page never grants plan access/i),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Check status again" }));
  expect(await screen.findByText("Payment confirmed")).toBeVisible();
});
