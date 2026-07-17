import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppShell } from "@/components/app-shell";
import { resolveAuthState } from "@/lib/auth";

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
      "Dashboard",
      "Companies",
      "Meetings",
      "Tasks",
      "Assistant",
      "Settings",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeVisible();
    }
    expect(navigation).toBeVisible();
    expect(screen.getByText(/mock authentication is active/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign out" })).toHaveAttribute(
      "href",
      "/sign-out",
    );
  });
});
