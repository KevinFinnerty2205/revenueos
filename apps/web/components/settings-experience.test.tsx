import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsExperience } from "@/components/settings-experience";

vi.mock("@/components/beta-admin", () => ({
  BetaAdmin: () => <section>Administrator controls</section>,
}));
vi.mock("@/components/sales-methodology-settings", () => ({
  SalesMethodologySettings: () => <section>Methodology controls</section>,
}));

function me(role: "admin" | "member") {
  return {
    user: {
      id: "user-1",
      externalAuthId: "user_dev_001",
      displayName: "Alex Morgan",
      email: "alex@example.test",
    },
    organisation: {
      id: "org-1",
      name: "Example Revenue Team",
      slug: "example",
    },
    role,
    authMode: "mock",
    requestId: "request-1",
  };
}

describe("SettingsExperience", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps organisation administration out of the member experience", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(me("member")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<SettingsExperience />);
    expect(await screen.findByText("Alex Morgan")).toBeVisible();
    expect(
      screen.getByText(/administrator manages methodology/i),
    ).toBeVisible();
    expect(
      screen.queryByText("Administrator controls"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Methodology controls")).not.toBeInTheDocument();
  });

  it("shows methodology and beta controls to administrators", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(me("admin")), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<SettingsExperience />);
    expect(await screen.findByText("Methodology controls")).toBeVisible();
    expect(screen.getByText("Administrator controls")).toBeVisible();
  });
});
