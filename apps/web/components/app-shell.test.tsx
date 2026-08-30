import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { resolveAuthState } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  usePathname: () => "/opportunities/opportunity-1",
}));

afterEach(() => vi.unstubAllGlobals());

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
      "Insights",
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

  it("hides desktop Insights when the server explicitly disables it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const payload = String(input).includes("/beta/capabilities")
          ? { featureFlags: { salesAnalytics: false } }
          : { enabled: false };
        return Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
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
    await waitFor(() =>
      expect(
        within(navigation).queryByRole("link", { name: "Insights" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      within(navigation).getByRole("link", { name: "Pipeline" }),
    ).toBeVisible();
  });
});
