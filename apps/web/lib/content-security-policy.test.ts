import { describe, expect, it } from "vitest";
import { buildContentSecurityPolicy } from "@/lib/content-security-policy";

const productionPublishableKey = `pk_live_${Buffer.from(
  "clerk.oryntela.com.au$",
).toString("base64url")}`;

const productionVariables = {
  ORYNTELA_ENVIRONMENT: "production",
  NEXT_PUBLIC_SITE_URL: "https://oryntela.com.au",
  NEXT_PUBLIC_API_BASE_URL: "https://api.oryntela.com.au",
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: productionPublishableKey,
} as const;

function directive(csp: string, name: string): string[] {
  const value = csp
    .split("; ")
    .find((candidate) => candidate.startsWith(`${name} `));
  if (!value) throw new Error(`Missing ${name} directive.`);
  return value.split(" ").slice(1);
}

describe("content security policy", () => {
  it("allows only the required production Clerk network origins", () => {
    const csp = buildContentSecurityPolicy(productionVariables);

    expect(directive(csp, "script-src")).toEqual([
      "'self'",
      "'unsafe-inline'",
      "https://clerk.oryntela.com.au",
      "https://challenges.cloudflare.com",
      "https://*.protect.clerk.com",
    ]);
    expect(directive(csp, "connect-src")).toEqual([
      "'self'",
      "https://api.oryntela.com.au",
      "https://clerk.oryntela.com.au",
      "https://*.protect.clerk.com:*",
    ]);
    expect(directive(csp, "frame-src")).toEqual([
      "'self'",
      "https://challenges.cloudflare.com",
      "https://*.protect.clerk.com",
    ]);
    expect(directive(csp, "worker-src")).toEqual(["'self'", "blob:"]);
    expect(directive(csp, "img-src")).toContain("https:");
    expect(directive(csp, "style-src")).toContain("'unsafe-inline'");
  });

  it("preserves restrictive directives without a bare wildcard or unsafe-eval", () => {
    const csp = buildContentSecurityPolicy(productionVariables);
    const sources = csp.split(/[; ]+/u);

    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(sources).not.toContain("*");
    expect(sources).not.toContain("'unsafe-eval'");
    expect(csp).not.toContain("http://clerk.");
  });

  it("does not leak development Clerk origins into production", () => {
    const productionCsp = buildContentSecurityPolicy(productionVariables);
    const developmentCsp = buildContentSecurityPolicy({
      ORYNTELA_ENVIRONMENT: "development",
      NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
    });

    expect(productionCsp).not.toContain("clerk.accounts.dev");
    expect(developmentCsp).toContain("https://*.clerk.accounts.dev");
    expect(developmentCsp).toContain("'unsafe-eval'");
    expect(developmentCsp).not.toContain("clerk.oryntela.com.au");
  });

  it.each([
    [
      "an arbitrary Clerk origin",
      `pk_live_${Buffer.from("evil.example$").toString("base64url")}`,
    ],
    [
      "a header-injection-shaped Clerk origin",
      `pk_live_${Buffer.from("clerk.oryntela.com.au\r\nscript-src *$").toString(
        "base64url",
      )}`,
    ],
  ])("rejects %s", (_description, publishableKey) => {
    expect(() =>
      buildContentSecurityPolicy({
        ...productionVariables,
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: publishableKey,
      }),
    ).toThrow(/Clerk/);
  });

  it.each([
    "http://api.oryntela.com.au",
    "https://evil.example",
    "https://api.oryntela.com.au\r\nscript-src *",
  ])("rejects an unsafe production API origin: %s", (apiOrigin) => {
    expect(() =>
      buildContentSecurityPolicy({
        ...productionVariables,
        NEXT_PUBLIC_API_BASE_URL: apiOrigin,
      }),
    ).toThrow(/API HTTPS origin/);
  });
});
