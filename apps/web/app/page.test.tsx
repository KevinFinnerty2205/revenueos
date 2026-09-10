import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/(marketing)/page";

describe("marketing home page", () => {
  it("presents the end-to-end product and an honest pre-launch trial CTA", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /one sales system from prospect to handover/i,
      }),
    ).toBeVisible();
    expect(
      screen.getAllByRole("link", { name: "Request trial access" })[0],
    ).toHaveAttribute("href", "/contact#trial");
    expect(screen.getByText(/14 days · Complete-level modules/i)).toBeVisible();
    expect(screen.getAllByText(/no automatic charge/i)).toHaveLength(2);
    expect(
      screen.getByText(/production connections remain activation-dependent/i),
    ).toBeVisible();
  });
});
