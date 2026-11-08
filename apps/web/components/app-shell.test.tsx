import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { resolveAuthState } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  usePathname: () => "/frameworks",
}));

describe("conversation-first application shell", () => {
  it("keeps four primary destinations and administration secondary", () => {
    const authState = resolveAuthState({
      NODE_ENV: "test",
      AUTH_MODE: "mock",
      MOCK_AUTH_ENABLED: "true",
    });

    render(
      <AppShell authState={authState}>
        <h1>Test content</h1>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "Oryntela Home" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    const navigation = screen.getByRole("navigation", {
      name: "Main navigation",
    });
    for (const label of ["Home", "Conversations", "Knowledge", "Frameworks"]) {
      expect(
        within(navigation).getByRole("link", { name: label }),
      ).toBeVisible();
    }
    expect(
      within(navigation).getByRole("link", { name: "Search / Ask Oryntela" }),
    ).toHaveAttribute("href", "/assistant");
    expect(
      within(navigation).getByRole("link", { name: "Settings" }),
    ).toBeVisible();
    for (const hiddenLegacyLabel of [
      "Accounts",
      "People",
      "Tasks",
      "Pipeline",
      "Insights",
      "Campaigns",
      "Create",
    ]) {
      expect(
        within(navigation).queryByRole("link", { name: hiddenLegacyLabel }),
      ).not.toBeInTheDocument();
    }
    expect(
      within(navigation).getByRole("link", { name: "Frameworks" }),
    ).toHaveAttribute("aria-current", "page");

    const mobileNavigation = screen.getByRole("navigation", {
      name: "Mobile navigation",
    });
    for (const label of ["Home", "Conversations", "Knowledge", "Frameworks"]) {
      expect(
        within(mobileNavigation).getByRole("link", { name: label }),
      ).toBeVisible();
    }
    expect(screen.getByText(/mock authentication is active/i)).toBeVisible();
    for (const link of screen.getAllByRole("link", { name: "Sign out" })) {
      expect(link).toHaveAttribute("href", "/sign-out");
    }
  });
});
