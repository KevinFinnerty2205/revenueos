import { describe, expect, it } from "vitest";
import { isRouteAccessAllowed, resolveAuthState } from "@/lib/auth";

describe("authentication policy", () => {
  it("enables a clearly labelled mock identity in development", () => {
    const state = resolveAuthState({
      NODE_ENV: "development",
      AUTH_MODE: "mock",
      MOCK_AUTH_ENABLED: "true",
    });

    expect(state.mode).toBe("mock");
    expect(state.authenticated).toBe(true);
    expect(state.organisation?.name).toBe("Example Revenue Team");
    expect(isRouteAccessAllowed(state)).toBe(true);
  });

  it("never enables mock authentication in production", () => {
    const state = resolveAuthState({
      NODE_ENV: "production",
      AUTH_MODE: "mock",
      MOCK_AUTH_ENABLED: "true",
    });

    expect(state.authenticated).toBe(false);
    expect(isRouteAccessAllowed(state)).toBe(false);
    expect(state.message).toMatch(/never available in production/i);
  });

  it("fails closed when Clerk is selected but not configured", () => {
    const state = resolveAuthState({
      NODE_ENV: "development",
      AUTH_MODE: "clerk",
    });

    expect(state.mode).toBe("clerk");
    expect(state.authenticated).toBe(false);
    expect(state.message).toMatch(/not configured/i);
  });
});
