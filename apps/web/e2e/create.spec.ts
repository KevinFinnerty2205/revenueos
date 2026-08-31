import { expect, test, type Page } from "@playwright/test";

const availability = {
  moduleKey: "create",
  state: "available",
  enabled: true,
  canManage: true,
  canUploadTemplates: true,
  canCreatePresentations: true,
  message: "Create is ready for approved PowerPoint templates.",
  description: "Build reviewed presentations.",
  learnMorePath: "/create",
};

const template = {
  id: "template-1",
  name: "Approved company story",
  state: "active",
  latestVersion: {
    id: "template-version-1",
    templateId: "template-1",
    version: 1,
    processingState: "ready",
    approvalState: "approved",
    fileName: "approved-company-story.pptx",
    byteSize: 42_000,
    checksumSha256: "a".repeat(64),
    slideCount: 4,
    approvedSlideCount: 4,
    requiredSlideCount: 1,
    widthEmu: 12_192_000,
    heightEmu: 6_858_000,
    warningCodes: [],
    safeFailureCode: null,
    compatibilityState: "compatible",
    compatibilityDetails: [],
    validationProfileVersion: 1,
    validatedAt: "2026-08-27T00:01:00Z",
    authorityAttestationVersion: 1,
    authorityAttestedAt: "2026-08-27T00:00:00Z",
    processedAt: "2026-08-27T00:01:00Z",
    approvedAt: "2026-08-27T00:02:00Z",
    slides: [],
    contentItems: [],
    createdAt: "2026-08-27T00:00:00Z",
  },
  createdAt: "2026-08-27T00:00:00Z",
  updatedAt: "2026-08-27T00:02:00Z",
};

function presentation(
  id: "presentation-plan" | "presentation-review",
  state: "draft_plan" | "needs_review" | "ready",
) {
  const claimState = state === "ready" ? "kept" : "pending";
  return {
    id,
    title: "Northstar solution overview",
    accountId: "company-1",
    accountName: "Northstar Facilities Group",
    opportunityId: "opportunity-1",
    opportunityName: "National operations rollout",
    objective: "solution_overview",
    audience: [
      {
        contactId: "contact-1",
        name: "Jordan Lee",
        role: "Chief Operating Officer",
        audienceType: "executive",
      },
    ],
    focusInstruction: "Keep the implementation discussion concise.",
    templateVersionId: "template-version-1",
    templateName: "Approved company story",
    templateVersion: 1,
    state,
    reviewState: state === "ready" ? "approved" : "pending",
    plan: [
      {
        id: "plan-title",
        templateSlideId: "slide-title",
        order: 1,
        title: "Approved company story",
        category: "title",
        required: true,
        modificationPolicy: "locked",
        sourceClasses: ["approved_company_content"],
        included: true,
      },
      {
        id: "plan-solution",
        templateSlideId: "slide-solution",
        order: 2,
        title: "A staged approach to the national rollout",
        category: "solution",
        required: false,
        modificationPolicy: "text_placeholders_only",
        sourceClasses: ["approved_company_content", "customer_direct"],
        included: true,
      },
      {
        id: "plan-next-steps",
        templateSlideId: "slide-next-steps",
        order: 3,
        title: "Confirm the implementation workshop",
        category: "next_steps",
        required: false,
        modificationPolicy: "editable_text",
        sourceClasses: ["approved_company_content", "salesperson_reported"],
        included: true,
      },
    ],
    currentVersion:
      state === "draft_plan"
        ? null
        : {
            id: "version-1",
            version: 1,
            state: state === "ready" ? "ready" : "needs_review",
            reviewState: state === "ready" ? "approved" : "pending",
            slides: [
              {
                planItemId: "plan-solution",
                templateSlideId: "slide-solution",
                order: 1,
                title: "A staged approach to the national rollout",
                bodyBlocks: [
                  "Northstar requested a staged implementation across its Australian sites.",
                ],
                required: false,
                modificationPolicy: "text_placeholders_only",
                reviewState: "needs_review",
                warningCodes: ["claim_review_required"],
              },
            ],
            claims: [
              {
                id: "claim-1",
                planItemId: "plan-solution",
                blockIndex: 0,
                claim:
                  "Northstar requested a staged implementation across its Australian sites.",
                contentType: "implementation",
                origin: "salesperson_reported",
                supportState: "reported",
                customerSafeClassification: "requires_review",
                sourceIds: ["source-1"],
                sourceLabels: ["Reviewed customer evidence"],
                freshness: "current",
                paraphraseAllowed: true,
                exactTextRequired: false,
                reviewState: claimState,
              },
            ],
            warningCodes: ["review_required"],
            safeFailureCode: null,
            validationProfileVersion: 1,
            validatedAt: "2026-08-27T00:03:00Z",
            generatedAt: "2026-08-27T00:03:00Z",
            approvedAt: state === "ready" ? "2026-08-27T00:05:00Z" : null,
            downloadAvailable: state === "ready",
            createdAt: "2026-08-27T00:02:00Z",
          },
    createdByUserId: "user-1",
    createdAt: "2026-08-27T00:02:00Z",
    updatedAt: "2026-08-27T00:03:00Z",
  };
}

async function mockCreateApi(page: Page) {
  let reviewState: "needs_review" | "ready" = "needs_review";
  let claimReviewed = false;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/create/availability") {
      await route.fulfill({ json: availability });
      return;
    }
    if (
      path === "/api/v1/prospect/availability" ||
      path === "/api/v1/engage/availability"
    ) {
      await route.fulfill({ json: { enabled: false } });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await route.fulfill({ json: { featureFlags: { engageEvents: false } } });
      return;
    }
    if (path === "/api/v1/create/templates") {
      await route.fulfill({
        json: { items: [template], canUpload: true, maxActiveTemplates: 20 },
      });
      return;
    }
    if (path === "/api/v1/create/templates/template-1") {
      await route.fulfill({ json: template });
      return;
    }
    if (path === "/api/v1/create/templates/template-needs-attention") {
      await route.fulfill({
        json: {
          ...template,
          id: "template-needs-attention",
          latestVersion: {
            ...template.latestVersion,
            approvalState: "pending",
            compatibilityState: "needs_attention",
            compatibilityDetails: ["pptx_unmapped_text_requires_lock"],
          },
        },
      });
      return;
    }
    if (path === "/api/v1/create/templates/template-unsupported") {
      await route.fulfill({
        json: {
          ...template,
          id: "template-unsupported",
          latestVersion: {
            ...template.latestVersion,
            processingState: "failed",
            approvalState: "pending",
            compatibilityState: "unsupported",
            compatibilityDetails: ["unsafe_pptx"],
            safeFailureCode: "unsafe_pptx",
          },
        },
      });
      return;
    }
    if (path === "/api/v1/create/presentations") {
      await route.fulfill({
        json: {
          items: [presentation("presentation-review", "needs_review")],
          canCreate: true,
          maxPresentationsPerUserPerDay: 10,
          maxPresentationsPerOrganisationPerDay: 50,
        },
      });
      return;
    }
    if (path === "/api/v1/create/business-cases") {
      await route.fulfill({
        json: { items: [], canCreate: true, maxActiveCasesPerAccount: 20 },
      });
      return;
    }
    if (path === "/api/v1/create/value-models") {
      await route.fulfill({
        json: { items: [], canManage: true, maxActiveModels: 50 },
      });
      return;
    }
    if (path === "/api/v1/create/presentations/presentation-plan/plan") {
      await route.fulfill({
        json: presentation("presentation-plan", "draft_plan"),
      });
      return;
    }
    if (path === "/api/v1/create/presentations/presentation-plan") {
      await route.fulfill({
        json: presentation("presentation-plan", "draft_plan"),
      });
      return;
    }
    if (path === "/api/v1/create/presentations/presentation-review/review") {
      claimReviewed = true;
      await route.fulfill({
        json: reviewedPresentation(reviewState, claimReviewed),
      });
      return;
    }
    if (path === "/api/v1/create/presentations/presentation-review/approve") {
      reviewState = "ready";
      await route.fulfill({ json: reviewedPresentation(reviewState, true) });
      return;
    }
    if (path === "/api/v1/create/presentations/presentation-review") {
      await route.fulfill({
        json: reviewedPresentation(reviewState, claimReviewed),
      });
      return;
    }
    await route.fulfill({ status: 404, json: { message: "Not found" } });
  });
}

function reviewedPresentation(
  state: "needs_review" | "ready",
  claimReviewed: boolean,
) {
  const value = presentation("presentation-review", state);
  if (value.currentVersion && claimReviewed) {
    value.currentVersion.claims[0].reviewState = "kept";
  }
  return value;
}

test.beforeEach(async ({ page }) => mockCreateApi(page));

test("Create shows the studio, deterministic plan and claim approval gate", async ({
  page,
}) => {
  await page.goto("/create");
  await expect(
    page.getByRole("heading", { name: "Sales Content Studio" }),
  ).toBeVisible();
  await expect(page.getByText("Northstar solution overview")).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: /Approved company story Version 1 · 4 slides Approved/i,
    }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Studio" }),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_032_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-032-create-studio.png",
      fullPage: true,
    });
  }

  await page.goto("/create/presentations/presentation-plan");
  await expect(
    page.getByRole("heading", { name: "Review the deterministic slide plan" }),
  ).toBeVisible();
  const requiredSlide = page.getByText(/1 · Title · required/i).locator("..");
  await expect(
    requiredSlide.getByRole("button", { name: "Remove" }),
  ).toHaveCount(0);
  if (process.env.CAPTURE_WO_032_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-032-plan-review.png",
      fullPage: true,
    });
  }

  await page.goto("/create/presentations/presentation-review");
  await expect(
    page.getByRole("heading", { name: "Claim and source manifest" }),
  ).toBeVisible();
  await expect(
    page.getByText(/downloaded PowerPoint is the final file/i),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve presentation" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Keep with review" }).click();
  await expect(
    page.getByRole("button", { name: "Approve presentation" }),
  ).toBeEnabled();
  if (process.env.CAPTURE_WO_032_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-032-claim-review.png",
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Approve presentation" }).click();
  await expect(
    page.getByRole("button", { name: "Download PowerPoint" }),
  ).toBeVisible();
});

test("Create does not add a fifth mobile navigation item", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/create");
  const mobile = page.getByRole("navigation", { name: "Mobile navigation" });
  await expect(mobile.getByRole("link")).toHaveCount(4);
  await expect(mobile.getByRole("link", { name: "Studio" })).toHaveCount(0);
});

test("Create compatibility and preview trust states remain readable at 390px", async ({
  page,
}) => {
  await page.goto("/create/templates/template-1");
  await expect(
    page.getByRole("heading", { name: "Template ready" }),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_039B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-039b/ui-template-ready-desktop.png",
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/create/templates/template-1");
  await expect(
    page.getByRole("heading", { name: "Template ready" }),
  ).toBeVisible();
  await page.goto("/create/templates/template-needs-attention");
  await expect(
    page.getByRole("heading", { name: "Template needs attention" }),
  ).toBeVisible();
  await expect(page.getByText(/every customer-facing text box/i)).toBeVisible();
  await page.goto("/create/templates/template-unsupported");
  await expect(
    page.getByRole("heading", { name: "Template unsupported" }),
  ).toBeVisible();
  await expect(page.getByText("unsafe_pptx")).toHaveCount(0);
  await page.goto("/create/presentations/presentation-review");
  await expect(
    page.getByText(/Fonts, spacing and layout may vary slightly/i),
  ).toBeVisible();
  if (process.env.CAPTURE_WO_039B_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-039b/ui-presentation-review-mobile.png",
      fullPage: true,
    });
  }
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.locator("body").evaluate((body) => body.clientWidth),
  );
});
