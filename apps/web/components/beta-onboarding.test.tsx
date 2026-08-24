import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BetaOnboarding } from "@/components/beta-onboarding";

function response(state: { currentStep: number; completed: boolean }) {
  return Promise.resolve(
    new Response(
      JSON.stringify({
        ...state,
        skipped: false,
        completedAt: state.completed ? "2026-08-24T01:00:00Z" : null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
}

describe("BetaOnboarding", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("starts with the customer outcome instead of implementation steps", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => response({ currentStep: 0, completed: false })),
    );
    render(<BetaOnboarding />);
    expect(
      await screen.findByRole("heading", {
        name: "Move your first customer conversation forward",
      }),
    ).toBeVisible();
    expect(screen.getByText(/prepare, capture what happened/i)).toBeVisible();
    expect(screen.getByText("Step 1 of 5")).toBeVisible();
    expect(
      screen.queryByText(/generate meeting intelligence/i),
    ).not.toBeInTheDocument();
  });

  it("returns a completed seller to Home", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => response({ currentStep: 4, completed: true })),
    );
    render(<BetaOnboarding />);
    expect(
      await screen.findByRole("link", { name: "Go to Home" }),
    ).toHaveAttribute("href", "/dashboard");
  });
});
