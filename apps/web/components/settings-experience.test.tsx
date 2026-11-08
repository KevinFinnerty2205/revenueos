import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsExperience } from "@/components/settings-experience";

vi.mock("@/components/beta-admin", () => ({
  BetaAdmin: ({ currentUserId }: { currentUserId: string }) => (
    <section>Administrator controls for {currentUserId}</section>
  ),
}));
vi.mock("@/components/commercial-plan-settings", () => ({
  CommercialPlanSettings: () => <section>Commercial plan controls</section>,
}));
vi.mock("@/components/credits-settings", () => ({
  CreditsSettings: () => <section>Credit controls</section>,
}));
vi.mock("@/components/prospect-module-settings", () => ({
  ProspectModuleSettings: () => <section>Prospect controls</section>,
}));
vi.mock("@/components/sales-methodology-settings", () => ({
  SalesMethodologySettings: () => <section>Methodology controls</section>,
}));
vi.mock("@/components/selling-profile-settings", () => ({
  SellingProfileSettings: () => (
    <section>Company and selling profile controls</section>
  ),
}));
vi.mock("@/components/crm-settings", () => ({
  CRMSettings: () => <section>CRM controls</section>,
}));
vi.mock("@/components/pipeline-settings", () => ({
  PipelineSettings: () => <section>Pipeline controls</section>,
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

  it("keeps conversation settings focused and links administrators to knowledge and frameworks", async () => {
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
    expect(
      await screen.findByRole("heading", {
        name: "Digest and pre-meeting preferences",
      }),
    ).toBeVisible();
    const settingsNavigation = screen.getByRole("navigation", {
      name: "Settings sections",
    });
    for (const label of ["Company knowledge", "Frameworks", "Team & safety"]) {
      expect(
        within(settingsNavigation).getByRole("link", {
          name: new RegExp(label, "i"),
        }),
      ).toBeVisible();
    }
    expect(
      screen.queryByText("Commercial plan controls"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Credit controls")).not.toBeInTheDocument();
    expect(screen.queryByText("Prospect controls")).not.toBeInTheDocument();
    expect(screen.queryByText("CRM controls")).not.toBeInTheDocument();
    expect(screen.queryByText("Pipeline controls")).not.toBeInTheDocument();
    expect(screen.getByText("Administrator controls for user-1")).toBeVisible();
  });
});
