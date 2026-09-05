import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommercialPlanSettings } from "@/components/commercial-plan-settings";

function commercial(
  status:
    "trial_active" | "active" | "grace" | "expired" | "inactive" | "suspended",
) {
  return {
    plan: { code: "complete", displayName: "Complete", version: 1 },
    status,
    billingInterval: status === "trial_active" ? null : "annual",
    trial: {
      lengthDays: 14,
      startedAt: "2032-04-05T06:30:00Z",
      endsAt: "2032-04-19T06:30:00Z",
      graceEndsAt: "2032-05-19T06:30:00Z",
      daysRemaining: status === "trial_active" ? 8 : 0,
      automaticCharge: false,
      paymentMethodRequired: false,
    },
    includedUserLimit: 15,
    activeUserCount: 16,
    seatsAvailable: 0,
    seatLimitStatus: "requires_resolution",
    modules: [
      {
        code: "core",
        displayName: "Core",
        accessLevel: status === "expired" ? "none" : "write",
        commerciallyIncluded: status !== "expired",
        operationalStatus: "available",
      },
      {
        code: "prospect",
        displayName: "Prospect",
        accessLevel: status === "grace" ? "read" : "write",
        commerciallyIncluded: true,
        operationalStatus: "mock_only",
      },
      {
        code: "engage",
        displayName: "Engage",
        accessLevel: "none",
        commerciallyIncluded: false,
        operationalStatus: "unavailable",
      },
    ],
    effectiveAt: "2032-04-05T06:30:00Z",
    stateVersion: 2,
    canCreateNewWork: status === "trial_active" || status === "active",
    readAccessEndsAt: status === "grace" ? "2032-05-19T06:30:00Z" : null,
    message:
      status === "grace"
        ? "Your trial has ended. No payment was taken. Your workspace remains available for viewing and export during the grace period."
        : status === "trial_active"
          ? "Your 14-day trial is active."
          : `Commercial status: ${status}.`,
  };
}

describe("CommercialPlanSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows an honest trial with no-card and provider distinction", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(commercial("trial_active")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<CommercialPlanSettings />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByText("Complete")).toBeVisible();
    expect(screen.getByText(/8 days remaining/i)).toBeVisible();
    expect(screen.getByText(/no card is required/i)).toBeVisible();
    expect(screen.getByText(/test provider is available/i)).toBeVisible();
    expect(screen.getByText(/more active users/i)).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.getByText("Not included")).toBeVisible();
  });

  it.each(["active", "expired", "inactive", "suspended"] as const)(
    "renders the %s commercial state",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(() =>
          Promise.resolve(
            new Response(JSON.stringify(commercial(status)), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
          ),
        ),
      );
      render(<CommercialPlanSettings />);
      expect(
        await screen.findByText(
          status === "active"
            ? "Active"
            : status[0].toUpperCase() + status.slice(1),
        ),
      ).toBeVisible();
    },
  );

  it("makes grace and its exact viewing deadline explicit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(commercial("grace")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<CommercialPlanSettings />);
    expect(await screen.findByText("Viewing and export grace")).toBeVisible();
    expect(screen.getByText(/No payment was taken/i)).toBeVisible();
    expect(screen.getByText(/19 May 2032/i)).toBeVisible();
    expect(screen.getByText("View only")).toBeVisible();
  });

  it("explains an empty module projection instead of rendering a blank list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ ...commercial("active"), modules: [] }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        ),
      ),
    );
    render(<CommercialPlanSettings />);
    expect(
      await screen.findByText(
        "Module information is not available yet. Contact support before relying on this plan.",
      ),
    ).toHaveAttribute("role", "status");
  });

  it("shows a recoverable error state", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "unavailable",
            message: "Plan service unavailable.",
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValue(
        new Response(JSON.stringify(commercial("active")), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetch);
    render(<CommercialPlanSettings />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Plan service unavailable",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Complete")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Billing & plan" }),
    ).toHaveFocus();
  });
});
