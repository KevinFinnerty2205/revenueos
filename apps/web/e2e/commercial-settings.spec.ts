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
    plan.getByText(/payment, invoice or Credit balances/i),
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
