import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BetaFeatureGate } from "@/components/beta-feature-gate";

afterEach(() => vi.restoreAllMocks());

describe("BetaFeatureGate", () => {
  it("hides disabled private-beta workspace content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          featureFlags: { opportunityWorkspace: false, revenueBrain: true },
        }),
        { status: 200 },
      ),
    );

    render(
      <BetaFeatureGate feature="opportunityWorkspace">
        <p>Sensitive workspace content</p>
      </BetaFeatureGate>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "This section is not enabled",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sensitive workspace content")).toBeNull();
  });

  it("renders content only after the server capability is enabled", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          featureFlags: { opportunityWorkspace: true, revenueBrain: true },
        }),
        { status: 200 },
      ),
    );

    render(
      <BetaFeatureGate feature="revenueBrain">
        <p>Revenue Brain content</p>
      </BetaFeatureGate>,
    );

    await waitFor(() =>
      expect(screen.getByText("Revenue Brain content")).toBeInTheDocument(),
    );
  });
});
