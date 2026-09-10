import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import IntegrationsPage from "@/app/(marketing)/integrations/page";
import PricingPage from "@/app/(marketing)/pricing/page";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";
import {
  integrations,
  pricingPlans,
  resolveSiteOrigin,
  siteOrigin,
  trialOffer,
} from "@/lib/marketing";
import { isIdentityAwareWebPath } from "@/lib/public-routes";

describe("marketing commercial truth", () => {
  it("matches the canonical server plan catalogue", () => {
    expect(
      pricingPlans.map((plan) => [
        plan.code,
        plan.name,
        plan.monthlyAmount,
        plan.annualAmount,
        plan.includedUsers,
      ]),
    ).toEqual([
      ["core", "Core", 200, 2_000, 5],
      ["growth", "Growth", 350, 3_500, 10],
      ["complete", "Complete", 500, 5_000, 15],
      ["enterprise", "Enterprise", null, null, null],
    ]);

    const catalogue = readFileSync(
      join(
        process.cwd(),
        "..",
        "api",
        "src",
        "revenueos",
        "commercial_services.py",
      ),
      "utf8",
    ).replaceAll(/\s+/gu, " ");
    expect(catalogue).toContain(
      'PlanDefinition("core", "Core", 1, Decimal("200.00"), Decimal("2000.00"), 5, ("core",))',
    );
    expect(catalogue).toContain(
      '"growth", "Growth", 1, Decimal("350.00"), Decimal("3500.00"), 10',
    );
    expect(catalogue).toContain(
      '"complete", "Complete", 1, Decimal("500.00"), Decimal("5000.00"), 15',
    );
    expect(catalogue).toContain(
      'PlanDefinition("enterprise", "Enterprise", 1, None, None, None, ALL_MODULES)',
    );
  });

  it("publishes the canonical trial without card, charge or conversion", () => {
    expect(trialOffer).toEqual({
      lengthDays: 14,
      planName: "Complete",
      paymentMethodRequired: false,
      automaticCharge: false,
      automaticConversion: false,
    });

    const sharedContract = readFileSync(
      join(process.cwd(), "..", "..", "packages", "shared", "src", "index.ts"),
      "utf8",
    );
    expect(sharedContract).toContain("lengthDays: 14;");
    expect(sharedContract).toContain("automaticCharge: false;");
    expect(sharedContract).toContain("paymentMethodRequired: false;");
  });

  it("renders annual prices as prepayment and no fake checkout", () => {
    render(<PricingPage />);

    expect(screen.getByText("AUD $2,000/year")).toBeVisible();
    expect(screen.getByText("AUD $3,500/year")).toBeVisible();
    expect(screen.getByText("AUD $5,000/year")).toBeVisible();
    expect(
      screen.getAllByText(/billed annually as an annual prepayment/i),
    ).toHaveLength(3);
    expect(
      screen.getByText(
        /provider-backed research, external sending and CRM connections remain unavailable/i,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/2 months free/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /checkout/i })).toBeNull();
  });
});

describe("marketing claim and metadata boundaries", () => {
  it("accepts HTTPS and local HTTP canonical origins but rejects unsafe schemes", () => {
    expect(resolveSiteOrigin("https://preview.example.test/path?q=1")).toBe(
      "https://preview.example.test",
    );
    expect(resolveSiteOrigin("http://localhost:3000/platform")).toBe(
      "http://localhost:3000",
    );
    expect(resolveSiteOrigin("http://127.0.0.1:3000")).toBe(
      "http://127.0.0.1:3000",
    );
    expect(resolveSiteOrigin("ftp://localhost/public")).toBe(
      "https://oryntela.com.au",
    );
    expect(resolveSiteOrigin("http://preview.example.test")).toBe(
      "https://oryntela.com.au",
    );
  });

  it("names only the four approved integration families and says activation is pending", () => {
    expect(integrations.map((integration) => integration.name)).toEqual([
      "Microsoft 365",
      "Google Workspace",
      "HubSpot",
      "Salesforce",
    ]);
    expect(JSON.stringify(integrations)).not.toMatch(/Apollo/iu);

    render(<IntegrationsPage />);
    expect(screen.getAllByText("Built · activation pending")).toHaveLength(4);
    expect(screen.getAllByText(/not yet production-active/i)).toHaveLength(4);
    expect(screen.queryByText(/connect instantly/i)).toBeNull();
    expect(screen.queryByText(/live now/i)).toBeNull();
  });

  it("publishes only indexable marketing routes in the sitemap", () => {
    const urls = sitemap().map((entry) => entry.url);
    expect(urls).toEqual([
      siteOrigin,
      `${siteOrigin}/platform`,
      `${siteOrigin}/pricing`,
      `${siteOrigin}/integrations`,
      `${siteOrigin}/security`,
      `${siteOrigin}/contact`,
    ]);
    expect(urls.join(" ")).not.toMatch(
      /dashboard|deal-room|sign-in|privacy|terms/iu,
    );
  });

  it("keeps every current protected route root inside the identity boundary", () => {
    const protectedRouteRoots = readdirSync(
      join(process.cwd(), "app", "(protected)"),
      { withFileTypes: true },
    )
      .filter((entry) => entry.isDirectory())
      .map((entry) => `/${entry.name}`)
      .sort();

    expect(protectedRouteRoots).not.toHaveLength(0);
    expect(
      protectedRouteRoots.filter((path) => !isIdentityAwareWebPath(path)),
    ).toEqual([]);
    for (const path of protectedRouteRoots) {
      expect(isIdentityAwareWebPath(`${path}/nested/private-route`)).toBe(true);
    }
  });

  it("keeps authenticated, Deal Room and incomplete legal routes out of search", () => {
    const rules = robots().rules;
    expect(Array.isArray(rules)).toBe(false);
    if (Array.isArray(rules))
      throw new Error("Expected one global robots rule");
    const disallowed = Array.isArray(rules.disallow)
      ? rules.disallow
      : rules.disallow
        ? [rules.disallow]
        : [];
    expect(disallowed).toContain("/deal-room");
    expect(disallowed).toContain("/dashboard");
    expect(disallowed).toContain("/sign-in");
    expect(disallowed.filter((path) => path.endsWith("/"))).toEqual([]);
    expect(disallowed).toContain("/privacy");
    expect(disallowed).toContain("/terms");
  });

  it("ships every curated real-product screenshot", () => {
    for (const filename of [
      "sales-brain.jpg",
      "prospect.jpg",
      "engage.jpg",
      "create.jpg",
      "opportunity-workspace.jpg",
      "pipeline.jpg",
      "deal-room.jpg",
      "handover.jpg",
      "analytics.jpg",
    ]) {
      expect(
        existsSync(
          join(process.cwd(), "public", "marketing", "product", filename),
        ),
      ).toBe(true);
    }
  });
});
