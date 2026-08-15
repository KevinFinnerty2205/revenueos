import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LandingPage from "@/app/page";

describe("landing page", () => {
  it("describes the reviewed private-beta workflow without claiming recording or connected actions", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /the ai sales teammate that remembers every customer interaction/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /recording is consent-gated and never starts implicitly/i,
      ),
    ).toBeVisible();
    expect(screen.getByText("Review required")).toBeVisible();
    expect(screen.getByText(/private reviewed visual evidence/i)).toBeVisible();
  });
});
