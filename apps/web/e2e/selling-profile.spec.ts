import { expect, test } from "@playwright/test";

const profileContent = {
  companyDescription:
    "We help relationship-led sales teams preserve context and follow through.",
  offerings: [
    {
      name: "Sales Brain",
      description: "A reviewed workspace for relationship intelligence.",
      whoNormallyBuys: ["Founders and sales leaders"],
      problemsSolved: ["Scattered relationship context"],
      intendedOutcomes: ["Clearer seller follow-through"],
      differentiators: ["Evidence-aware human review"],
      competitorsAlternatives: ["Manual notes and CRM-only workflows"],
      approvedProof: ["Approved internal product demonstration"],
      approvedClaims: ["Keeps approved context available to members"],
    },
  ],
};

function revision(state: "draft" | "approved") {
  return {
    id: `revision-${state}`,
    profileId: "profile-wo-046",
    revisionNumber: 1,
    state,
    lockVersion: 1,
    content: profileContent,
    contentFingerprint: "a".repeat(64),
    createdByUserId: "user-1",
    approvedByUserId: state === "approved" ? "user-1" : null,
    createdAt: "2026-09-04T00:00:00Z",
    updatedAt: "2026-09-04T00:00:00Z",
    approvedAt: state === "approved" ? "2026-09-04T00:01:00Z" : null,
    supersededAt: null,
    retiredAt: null,
  };
}

function management(state: "empty" | "draft" | "current") {
  const draft = state === "draft" ? revision("draft") : null;
  const current = state === "current" ? revision("approved") : null;
  return {
    status: state,
    canManage: true,
    draft,
    current,
    history: draft ? [draft] : current ? [current] : [],
    authority: "organisation_approved",
    authorityNote: "Organisation-approved context only.",
  };
}

test("administrator creates, reviews and approves selling context responsively", async ({
  page,
}) => {
  let state: "empty" | "draft" | "current" = "empty";
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/me") {
      await route.fulfill({
        json: {
          user: {
            id: "user-1",
            externalAuthId: "user_dev_001",
            displayName: "Synthetic Administrator",
            email: "admin@example.test",
          },
          organisation: {
            id: "organisation-1",
            name: "Synthetic Revenue Team",
            slug: "synthetic-revenue-team",
          },
          role: "admin",
          authMode: "mock",
          requestId: "request-wo-046",
        },
      });
      return;
    }
    if (url.pathname.startsWith("/api/v1/selling-profile")) {
      if (
        route.request().method() === "POST" &&
        url.pathname.endsWith("/revisions")
      ) {
        state = "draft";
        await route.fulfill({ status: 201, json: management(state) });
        return;
      }
      if (url.pathname.endsWith("/approve")) state = "current";
      await route.fulfill({ json: management(state) });
      return;
    }
    await route.fulfill({
      status: 503,
      json: {
        code: "not_in_test",
        message: "Not part of this bounded test.",
        requestId: "wo-046",
      },
    });
  });

  await page.goto("/settings");
  const section = page.locator("#company-selling-profile");
  await expect(
    section.getByRole("heading", { name: "Company & Selling Profile" }),
  ).toBeVisible();
  await expect(
    section.getByText(/not customer Evidence, prospect research, CRM truth/i),
  ).toBeVisible();
  await section.getByRole("button", { name: "Create draft" }).click();
  await expect(section.getByLabel(/^Company description/i)).toBeFocused();
  expect(state).toBe("empty");
  await section
    .getByLabel(/^Company description/i)
    .fill(profileContent.companyDescription);
  await section.getByLabel("Offering name").fill("Sales Brain");
  await section
    .getByLabel("Concise description")
    .fill(profileContent.offerings[0].description);
  await section.getByText("Optional approved selling context").click();
  await section
    .getByLabel(/Who normally buys/i)
    .fill("Founders and sales leaders");
  await section.getByRole("button", { name: "Create draft" }).click();
  await expect(section.getByText(/not current until approved/i)).toBeVisible();
  await section
    .getByLabel(/^Company description/i)
    .fill(`${profileContent.companyDescription} Updated`);
  await expect(
    section.getByRole("button", { name: "Approve as current" }),
  ).toBeDisabled();
  await expect(
    section.getByText(/Save this draft before approving your latest changes/i),
  ).toBeVisible();
  await section.getByRole("button", { name: "Save draft" }).click();
  await expect(
    section.getByRole("button", { name: "Approve as current" }),
  ).toBeEnabled();
  await section.getByRole("button", { name: "Approve as current" }).focus();
  await expect(
    section.getByRole("button", { name: "Approve as current" }),
  ).toBeFocused();
  await section
    .getByRole("button", { name: "Approve as current" })
    .press("Enter");
  await expect(
    section.getByText("Approved current", { exact: true }),
  ).toBeVisible();
  await expect(
    section.getByText(/Revision 1 is now the approved current context/i),
  ).toBeVisible();

  if (process.env.CAPTURE_WO_046_SCREENSHOTS === "1") {
    await section.screenshot({
      path: "../../docs/07-sprints/assets/wo-046-selling-profile-desktop.png",
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(section).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  if (process.env.CAPTURE_WO_046_SCREENSHOTS === "1") {
    await page.setViewportSize({ width: 390, height: 1100 });
    await section.screenshot({
      path: "../../docs/07-sprints/assets/wo-046-selling-profile-mobile.png",
    });
  }
});
