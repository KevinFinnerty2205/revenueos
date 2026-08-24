import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { resolveAuthState } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  usePathname: () => "/opportunities/opportunity-1",
}));

describe("application shell", () => {
  it("renders required navigation and the development-auth warning", () => {
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

    const navigation = screen.getByRole("navigation", {
      name: "Main navigation",
    });
    for (const label of [
      "Home",
      "Accounts",
      "People",
      "Pipeline",
      "Interactions",
      "Search",
      "Settings",
    ]) {
      expect(
        within(navigation).getByRole("link", { name: label }),
      ).toBeVisible();
    }
    const mobileNavigation = screen.getByRole("navigation", {
      name: "Mobile navigation",
    });
    expect(mobileNavigation).toBeVisible();
    for (const label of ["Today", "Actions"]) {
      expect(
        within(mobileNavigation).getByRole("link", { name: label }),
      ).toBeVisible();
    }
    expect(
      screen.queryByRole("link", { name: "Getting started" }),
    ).not.toBeInTheDocument();
    expect(navigation).toBeVisible();
    expect(
      within(navigation).getByRole("link", { name: "Pipeline" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/mock authentication is active/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign out" })).toHaveAttribute(
      "href",
      "/sign-out",
    );
  });
});
