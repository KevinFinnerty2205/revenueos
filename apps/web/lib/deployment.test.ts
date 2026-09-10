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
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_live_synthetic",
  CLERK_SECRET_KEY: "sk_live_synthetic",
  ORYNTELA_RELEASE_SHA: "a".repeat(40),
} as const;

const approvedLegalContent = {
  privacy: {
    status: "approved",
    version: "2026-09-10",
    effectiveDate: "2026-09-10",
    sha256: `sha256:${"a".repeat(64)}`,
  },
  terms: {
    status: "approved",
    version: "2026-09-10",
    effectiveDate: "2026-09-10",
    sha256: `sha256:${"b".repeat(64)}`,
  },
} as const;

describe("deployment configuration", () => {
  it("fails a production build while committed legal copy is a gap", () => {
    expect(() => assertDeploymentConfiguration(productionVariables)).toThrow(
      /Privacy and Terms/,
    );
  });

  it("accepts an exact canonical production configuration after legal approval", () => {
    expect(() =>
      assertDeploymentConfiguration(productionVariables, approvedLegalContent),
    ).not.toThrow();
  });

  it("requires the Clerk secret only in the server runtime gate", () => {
    const contentStatus = approvedLegalContent;
    expect(() =>
      assertDeploymentConfiguration(
        { ...productionVariables, CLERK_SECRET_KEY: undefined },
        contentStatus,
      ),
    ).not.toThrow();
    expect(() =>
      assertWebRuntimeConfiguration(
        { ...productionVariables, CLERK_SECRET_KEY: undefined },
        contentStatus,
      ),
    ).toThrow(/CLERK_SECRET_KEY/);
  });

  it("requires an immutable release SHA at production runtime", () => {
    expect(() =>
      assertWebRuntimeConfiguration(
        { ...productionVariables, ORYNTELA_RELEASE_SHA: undefined },
        approvedLegalContent,
      ),
    ).toThrow(/ORYNTELA_RELEASE_SHA/);
  });

  it.each([
    ["NEXT_PUBLIC_SITE_URL", "http://oryntela.com.au"],
    ["NEXT_PUBLIC_APP_URL", "https://example.com"],
    ["NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"],
  ])("rejects unsafe production %s", (name, value) => {
    expect(() =>
      assertDeploymentConfiguration(
        { ...productionVariables, [name]: value },
        approvedLegalContent,
      ),
    ).toThrow();
  });

  it("rejects mock auth, development Clerk keys and production HSTS in staging", () => {
    expect(() =>
      assertDeploymentConfiguration({
        ...productionVariables,
        AUTH_MODE: "mock",
      }),
    ).toThrow(/Clerk/);
    expect(() =>
      assertDeploymentConfiguration(
        {
          ...productionVariables,
          NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_synthetic",
        },
        approvedLegalContent,
      ),
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

  it("rejects an approved legal status without immutable release metadata", () => {
    expect(() =>
      assertDeploymentConfiguration(productionVariables, {
        ...approvedLegalContent,
        privacy: {
          status: "approved",
          version: "2026-09-10",
          effectiveDate: "2026-09-10",
          sha256: null,
        },
      }),
    ).toThrow(/fingerprinted/);
  });

  it("keeps staging and test deployments out of search", () => {
    expect(isSearchIndexingAllowed("production")).toBe(true);
    expect(isSearchIndexingAllowed("staging")).toBe(false);
    expect(isSearchIndexingAllowed("development")).toBe(true);
    expect(isSearchIndexingAllowed("test")).toBe(false);
    expect(resolveDeploymentEnvironment("test")).toBe("test");
  });
});
