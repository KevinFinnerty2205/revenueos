import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LandingPage from "@/app/page";

describe("landing page", () => {
  it("describes RevenueOS without claiming planned features are live", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /the ai sales teammate that remembers every customer interaction/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/conversation recording, ai processing/i),
    ).toBeVisible();
    expect(screen.getByText("Not connected")).toBeVisible();
  });
});
