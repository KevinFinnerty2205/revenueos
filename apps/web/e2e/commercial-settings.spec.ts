import { expect, test, type Page } from "@playwright/test";

const apiOrigin = "http://localhost:8000";

const commercialProjection = {
  plan: { code: "complete", displayName: "Complete", version: 1 },
  status: "trial_active",
  billingInterval: null,
  trial: {
    lengthDays: 14,
    startedAt: "2032-04-05T06:30:00Z",
    endsAt: "2032-04-19T06:30:00Z",
    graceEndsAt: "2032-05-19T06:30:00Z",
    daysRemaining: 8,
    automaticCharge: false,
    paymentMethodRequired: false,
  },
  includedUserLimit: 15,
  activeUserCount: 4,
  seatsAvailable: 11,
  seatLimitStatus: "within_limit",
  modules: [
    {
      code: "core",
      displayName: "Core",
      accessLevel: "write",
      commerciallyIncluded: true,
      operationalStatus: "available",
    },
    {
      code: "prospect",
      displayName: "Prospect",
      accessLevel: "write",
      commerciallyIncluded: true,
      operationalStatus: "mock_only",
    },
    {
      code: "engage",
      displayName: "Engage",
      accessLevel: "write",
      commerciallyIncluded: true,
      operationalStatus: "mock_only",
    },
    {
      code: "create",
      displayName: "Create",
      accessLevel: "write",
      commerciallyIncluded: true,
      operationalStatus: "available",
    },
    {
      code: "crm",
      displayName: "CRM connectors",
      accessLevel: "write",
      commerciallyIncluded: true,
      operationalStatus: "unavailable",
    },
  ],
  effectiveAt: "2032-04-05T06:30:00Z",
  stateVersion: 1,
  canCreateNewWork: true,
  readAccessEndsAt: null,
  message:
    "Your 14-day trial is active. No payment method is required and you will not be charged automatically.",
};

const billingProjection = {
  configured: false,
  provider: "deterministic",
  mode: "test",
  legalEntityName: "Management Services Australia Pty. Ltd.",
  legalEntityAbn: "15 113 119 556",
  subscription: null,
  invoices: [],
  checkoutOptions: [
    ["core", "Core", "monthly", "200.00", 5, "AUD $200 billed monthly."],
    [
      "core",
      "Core",
      "annual",
      "2000.00",
      5,
      "AUD $2,000 billed annually as an annual prepayment.",
    ],
    ["growth", "Growth", "monthly", "350.00", 10, "AUD $350 billed monthly."],
    [
      "growth",
      "Growth",
      "annual",
      "3500.00",
      10,
      "AUD $3,500 billed annually as an annual prepayment.",
    ],
    [
      "complete",
      "Complete",
      "monthly",
      "500.00",
      15,
      "AUD $500 billed monthly.",
    ],
    [
      "complete",
      "Complete",
      "annual",
      "5000.00",
      15,
      "AUD $5,000 billed annually as an annual prepayment.",
    ],
  ].map(
    ([
      planCode,
      displayName,
      billingInterval,
      amount,
      includedUserLimit,
      paymentStatement,
    ]) => ({
      planCode,
      displayName,
      billingInterval,
      amount,
      currency: "AUD",
      includedUserLimit,
      selfServiceAvailable: true,
      paymentStatement,
    }),
  ),
  portalAvailable: false,
  message:
    "Billing is not configured or is manually managed. No provider subscription is being represented.",
};

const creditsProjection = {
  unitName: "Oryntela Credit",
  balance: {
    available: 1000,
    purchasedAvailable: 800,
    promotionalAvailable: 200,
    reserved: 20,
    purchasedReserved: 20,
    promotionalReserved: 0,
    totalHeld: 1020,
  },
  recentActivity: [
    {
      id: "00000000-0000-4000-9000-000000000501",
      eventType: "purchase",
      creditType: "purchased",
      availableChange: 1000,
      reservedChange: 0,
      actionCode: null,
      operationId: null,
      reason: "Verified test purchase.",
      createdAt: "2032-04-05T06:30:00Z",
    },
    {
      id: "00000000-0000-4000-9000-000000000502",
      eventType: "reservation",
      creditType: "purchased",
      availableChange: -20,
      reservedChange: 20,
      actionCode: "PROSPECT_COMPANY_RESEARCH",
      operationId: "00000000-0000-4000-9000-000000000601",
      reason: "Reserved before deterministic work.",
      createdAt: "2032-04-06T06:30:00Z",
    },
  ],
  testPacks: [
    {
      id: "00000000-0000-4000-9000-000000000049",
      packCode: "TEST_100",
      displayName: "100 test Credits",
      version: 1,
      creditQuantity: 100,
      amountMinorUnits: 2000,
      currency: "AUD",
      testOnly: true,
      purchaseAvailable: false,
      pricingNote: "TEST ONLY / NOT CUSTOMER PRICING",
    },
  ],
  lowBalance: false,
  autoTopUp: false,
  productionPricesAvailable: false,
  message:
    "Credits cover meaningful metered external services. Ordinary Oryntela software use is not metered. Test catalogue values are not customer pricing.",
};

async function routeSettingsBase(page: Page) {
  await page.route(`${apiOrigin}/api/v1/**`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        code: "fixture_unavailable",
        message: "This unrelated settings fixture is unavailable.",
        requestId: "request-commercial-fallback",
      }),
    });
  });
  await page.route(`${apiOrigin}/api/v1/me`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "00000000-0000-4000-8000-000000000001",
          externalAuthId: "user_dev_001",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "00000000-0000-4000-8000-000000000002",
          name: "Example Revenue Team",
          slug: "example-revenue-team",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-commercial-me",
      }),
    });
  });
}

async function routeSettings(page: Page) {
  await routeSettingsBase(page);
  await page.route(`${apiOrigin}/api/v1/commercial`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(commercialProjection),
    });
  });
  await page.route(`${apiOrigin}/api/v1/billing`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(billingProjection),
    });
  });
  await page.route(`${apiOrigin}/api/v1/credits`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(creditsProjection),
    });
  });
}

test("commercial settings are clear, keyboard reachable and responsive", async ({
  page,
}) => {
  await routeSettings(page);
  await page.goto("/settings");

  const plan = page.getByRole("region", { name: "Billing & plan" });
  await expect(plan).toBeVisible();
  await expect(plan.getByText("Complete", { exact: true })).toBeVisible();
  await expect(plan.getByText("Trial active")).toBeVisible();
  await expect(plan.getByText(/8 days remaining/i)).toBeVisible();
  await expect(plan.getByText(/no card is required/i)).toBeVisible();
  await expect(
    plan.getByText(/operational provider is not available yet/i),
  ).toBeVisible();
  await expect(
    plan.getByText(/server-authoritative plan and entitlement view/i),
  ).toBeVisible();
  await plan.screenshot({
    path: "../../docs/07-sprints/assets/wo-047-commercial-settings-desktop.png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await plan.scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await expect(
    plan.getByRole("list", { name: "Commercial module access" }),
  ).toBeVisible();
  await plan.screenshot({
    path: "../../docs/07-sprints/assets/wo-047-commercial-settings-mobile.png",
  });
});

test("test billing checkout preparation is keyboard reachable and responsive", async ({
  page,
}) => {
  await routeSettings(page);
  await page.goto("/settings");

  const billing = page.getByRole("region", { name: "Subscription & invoices" });
  await expect(billing).toBeVisible();
  await expect(
    billing.getByText(/deterministic · test mode only/i),
  ).toBeVisible();
  await expect(billing.getByText(/Billing not configured/i)).toBeVisible();
  const annual = billing.getByRole("radio", { name: /Core · annual/i });
  await annual.focus();
  await expect(annual).toBeFocused();
  await page.keyboard.press("Space");
  await expect(billing.getByText("Review before continuing")).toBeVisible();
  await expect(billing.getByText(/annual prepayment/i).last()).toBeVisible();
  await billing.screenshot({
    path: "../../docs/07-sprints/assets/wo-048-billing-settings-desktop.png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await billing.scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await expect(
    billing.getByRole("button", { name: "Prepare secure checkout" }),
  ).toBeVisible();
  await billing.screenshot({
    path: "../../docs/07-sprints/assets/wo-048-billing-settings-mobile.png",
  });
});

test("Credits settings are clear, bounded and responsive", async ({ page }) => {
  await routeSettings(page);
  await page.goto("/settings");

  const credits = page.getByRole("region", { name: "Oryntela Credits" });
  await expect(credits).toBeVisible();
  await expect(credits.getByText("1,000", { exact: true })).toBeVisible();
  await expect(credits.getByText("800", { exact: true })).toBeVisible();
  await expect(credits.getByText("200", { exact: true })).toBeVisible();
  await expect(credits.getByText(/20 Credits are reserved/i)).toBeVisible();
  await expect(
    credits.getByText("TEST ONLY / NOT CUSTOMER PRICING"),
  ).toBeVisible();
  await expect(credits.getByText("100 Credits · $20.00")).toBeVisible();
  await expect(
    credits.getByRole("button", { name: "Purchase unavailable" }),
  ).toBeDisabled();
  await expect(credits.getByText(/provider cost/i)).toHaveCount(0);
  await credits.screenshot({
    path: "../../docs/07-sprints/assets/wo-049-credits-settings-desktop.png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await credits.scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await expect(credits.getByText("1,000", { exact: true })).toBeVisible();
  await credits.screenshot({
    path: "../../docs/07-sprints/assets/wo-049-credits-settings-mobile.png",
  });
});

test("commercial settings recovery is keyboard operable and restores focus", async ({
  page,
}) => {
  await routeSettingsBase(page);
  let attempt = 0;
  await page.route(`${apiOrigin}/api/v1/commercial`, async (route) => {
    attempt += 1;
    await route.fulfill(
      attempt === 1
        ? {
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({
              code: "commercial_unavailable",
              message:
                "Commercial plan information is temporarily unavailable.",
              requestId: "request-commercial-error",
            }),
          }
        : {
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(commercialProjection),
          },
    );
  });
  await page.goto("/settings");

  const plan = page.getByRole("region", { name: "Billing & plan" });
  const retry = plan.getByRole("button", { name: "Try again" });
  await expect(retry).toBeVisible();
  await retry.focus();
  await expect(retry).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(plan.getByText("Complete", { exact: true })).toBeVisible();
  await expect(
    plan.getByRole("heading", { name: "Billing & plan" }),
  ).toBeFocused();
});
