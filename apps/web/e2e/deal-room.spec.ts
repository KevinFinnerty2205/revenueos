import { expect, test } from "@playwright/test";

const publicRoom = {
  room: {
    schemaVersion: 1,
    revision: 1,
    publishedAt: "2026-09-07T01:00:00Z",
    sellerCompanyName: "Example Revenue Team",
    customerCompanyName: "Synthetic Customer",
    opportunityName: "Secure operations rollout",
    overview:
      "A shared space for the reviewed objective, agreed next steps and approved resources.",
    businessCase: {
      title: "Approved rollout business case",
      version: 1,
      currency: "AUD",
      scenarios: [
        {
          name: "Base",
          outputs: [
            { label: "First-year ROI", value: "42.0", unit: "%" },
            { label: "Payback", value: "8.5", unit: "months" },
          ],
        },
      ],
    },
    commercialSummary:
      "Approved scope: rollout support. Agreed term: 12 months.",
    stakeholders: [
      {
        id: "stakeholder-1",
        name: "Jordan Lee",
        role: "Operations Director",
        company: "Synthetic Customer",
        party: "customer",
      },
      {
        id: "stakeholder-2",
        name: "Alex Morgan",
        role: "Account lead",
        company: "Example Revenue Team",
        party: "seller",
      },
    ],
    milestones: [
      {
        id: "milestone-1",
        title: "Complete security review",
        ownerParty: "joint",
        targetDate: "2026-09-18",
        status: "in_progress",
        note: "Review the approved questionnaire together.",
      },
      {
        id: "milestone-2",
        title: "Confirm rollout plan",
        ownerParty: "our_team",
        targetDate: "2026-09-24",
        status: "not_started",
        note: null,
      },
    ],
    resources: [
      {
        id: "resource-1",
        kind: "external_link",
        title: "Implementation overview",
        url: "https://example.com/implementation",
        downloadAvailable: false,
      },
      {
        id: "resource-2",
        kind: "presentation",
        title: "Approved solution presentation",
        url: null,
        downloadAvailable: true,
      },
    ],
    nextMeetingAt: "2026-09-12T03:00:00Z",
  },
  expiresAt: "2026-10-07T01:00:00Z",
};

test("published Deal Room is customer-ready, keyboard usable and fits 390px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/deal-rooms/public/resolve", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({
      token: "secure_token_with_enough_entropy_1234567890",
    });
    await route.fulfill({ status: 200, json: publicRoom });
  });

  const navigation = await page.goto(
    "/deal-room#access=secure_token_with_enough_entropy_1234567890",
  );
  expect(navigation?.headers()["x-robots-tag"]).toBe(
    "noindex, nofollow, noarchive",
  );
  expect(navigation?.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(
    page.getByRole("heading", { name: "Secure operations rollout" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Next steps and timeline" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Documents and links" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Working together" }),
  ).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toHaveCount(
    0,
  );
});

test("invalid and revoked links share the safe unavailable experience", async ({
  page,
}) => {
  await page.route("**/api/v1/deal-rooms/public/resolve", (route) =>
    route.fulfill({
      status: 404,
      json: {
        code: "deal_room_unavailable",
        message: "This Deal Room is no longer available.",
        requestId: "synthetic-request",
      },
    }),
  );
  await page.goto("/deal-room#access=invalid_but_never_reflected_token_value");
  await expect(
    page.getByRole("heading", {
      name: "This Deal Room is no longer available.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("invalid_but_never_reflected_token_value"),
  ).toHaveCount(0);
});
