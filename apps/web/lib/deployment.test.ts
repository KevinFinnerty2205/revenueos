import { describe, expect, it } from "vitest";
import {
  assertDeploymentConfiguration,
  assertWebRuntimeConfiguration,
  isSearchIndexingAllowed,
  resolveDeploymentEnvironment,
} from "@/lib/deployment";

const productionVariables = {
  ORYNTELA_ENVIRONMENT: "production",
  NEXT_PUBLIC_SITE_URL: "https://oryntela.com.au",
  NEXT_PUBLIC_APP_URL: "https://oryntela.com.au",
  NEXT_PUBLIC_API_BASE_URL: "https://api.oryntela.com.au",
  AUTH_MODE: "clerk",
  MOCK_AUTH_ENABLED: "false",
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: `pk_live_${Buffer.from(
    "clerk.oryntela.com.au$",
  ).toString("base64url")}`,
  CLERK_SECRET_KEY: "sk_live_synthetic",
  ORYNTELA_RELEASE_SHA: "a".repeat(40),
} as const;

describe("deployment configuration", () => {
  it("allows the production authentication shell before legal activation", () => {
    expect(() =>
      assertDeploymentConfiguration(productionVariables),
    ).not.toThrow();
  });

  it("requires the Clerk secret only in the server runtime gate", () => {
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        CLERK_SECRET_KEY: undefined,
      }),
    ).not.toThrow();
    expect(() =>
      assertWebRuntimeConfiguration({
        ...productionVariables,
        CLERK_SECRET_KEY: undefined,
      }),
    ).toThrow(/CLERK_SECRET_KEY/);
  });

  it("requires an immutable release SHA at production runtime", () => {
    expect(() =>
      assertWebRuntimeConfiguration({
        ...productionVariables,
        ORYNTELA_RELEASE_SHA: undefined,
      }),
    ).toThrow(/ORYNTELA_RELEASE_SHA/);
  });

  it.each([
    ["NEXT_PUBLIC_SITE_URL", "http://oryntela.com.au"],
    ["NEXT_PUBLIC_APP_URL", "https://example.com"],
    ["NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"],
  ])("rejects unsafe production %s", (name, value) => {
    expect(() =>
      assertDeploymentConfiguration({ ...productionVariables, [name]: value }),
    ).toThrow();
  });

  it("rejects a production Clerk key for an arbitrary or malformed origin", () => {
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: `pk_live_${Buffer.from(
          "evil.example$",
        ).toString("base64url")}`,
      }),
    ).toThrow(/canonical Oryntela Clerk origin/);
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: `pk_live_${Buffer.from(
          "clerk.oryntela.com.au\r\nconnect-src *$",
        ).toString("base64url")}`,
      }),
    ).toThrow(/hostname is invalid/);
  });

  it("rejects mock auth, development Clerk keys and production HSTS in staging", () => {
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        AUTH_MODE: "mock",
      }),
    ).toThrow(/Clerk/);
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_synthetic",
      }),
    ).toThrow(/production-instance/);
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        ORYNTELA_ENVIRONMENT: "staging",
        NEXT_PUBLIC_SITE_URL: "https://preview.example.test",
        NEXT_PUBLIC_APP_URL: "https://preview.example.test",
        NEXT_PUBLIC_API_BASE_URL: "https://api-preview.example.test",
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_synthetic",
        CLERK_SECRET_KEY: "sk_test_synthetic",
        ORYNTELA_HSTS_ENABLED: "true",
      }),
    ).toThrow(/HSTS/);
  });

  it("keeps staging and test deployments out of search", () => {
    expect(isSearchIndexingAllowed("production")).toBe(true);
    expect(isSearchIndexingAllowed("staging")).toBe(false);
    expect(isSearchIndexingAllowed("development")).toBe(true);
    expect(isSearchIndexingAllowed("test")).toBe(false);
    expect(resolveDeploymentEnvironment("test")).toBe("test");
  });
});
