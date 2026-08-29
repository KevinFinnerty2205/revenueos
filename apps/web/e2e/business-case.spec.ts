import { expect, test, type Page } from "@playwright/test";

const inputDefinition = {
  key: "implementation_cost",
  label: "Implementation cost",
  description: "Approved implementation and deployment cost.",
  valueType: "currency",
  unit: "currency",
  required: true,
  minimum: "0",
  maximum: "1000000",
  decimalPrecision: 2,
  defaultValue: "25000",
  defaultOrigin: "organisation_assumption",
  defaultSourceReference: "Approved Summit commercial assumption",
  reviewExpiresOn: null,
  maxSourceAgeDays: null,
  assumptionLocked: true,
  sourcePolicy: "approved_org_only",
  customerFacing: true,
  material: true,
  sensitivityEligible: true,
  scenarioPreset: { conservative: "30000", upside: "20000" },
  displayOrder: 1,
};

const modelDefinition = {
  inputs: [inputDefinition],
  outputs: [
    {
      key: "roi_percentage",
      label: "First-year ROI",
      description: "First-year net benefit divided by approved total cost.",
      formula:
        "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
      unit: "percentage",
      displayPrecision: 1,
      customerFacing: true,
      highlight: true,
      scenarioSensitive: true,
      displayOrder: 1,
    },
    {
      key: "payback_months",
      label: "Payback",
      description: "Payback under positive annual net benefit.",
      formula: "payback_months(implementation_cost, annual_net_benefit)",
      unit: "months",
      displayPrecision: 1,
      customerFacing: true,
      highlight: true,
      scenarioSensitive: true,
      displayOrder: 2,
    },
  ],
  customerDisclaimer:
    "Based on the inputs and assumptions shown; not a guarantee of future results.",
};

const model = {
  id: "model-1",
  name: "Multi-Site Access Efficiency",
  description:
    "A transparent model for administration time, implementation cost and first-year benefit.",
  state: "active",
  latestVersion: {
    id: "model-version-1",
    version: 1,
    state: "approved",
    definition: modelDefinition,
    formulaEngineVersion: "bounded_decimal_v1",
    fingerprint: "a".repeat(64),
    approvedByUserId: "admin-1",
    approvedAt: "2026-08-29T01:00:00Z",
    createdByUserId: "admin-1",
    createdAt: "2026-08-29T00:00:00Z",
  },
  createdByUserId: "admin-1",
  createdAt: "2026-08-29T00:00:00Z",
  updatedAt: "2026-08-29T01:00:00Z",
};

const roiOutput = {
  key: "roi_percentage",
  label: "First-year ROI",
  description: "First-year net benefit divided by approved total cost.",
  unit: "percentage",
  exactValue: "-29.180327868852459",
  displayValue: "-29.2",
  unavailableReason: null,
  formula: "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
  inputDependencies: ["implementation_cost"],
  outputDependencies: ["first_year_net_benefit", "first_year_total_cost"],
  customerFacing: true,
  highlight: true,
};

const paybackOutput = {
  key: "payback_months",
  label: "Payback",
  description: "Payback under positive annual net benefit.",
  unit: "months",
  exactValue: null,
  displayValue: null,
  unavailableReason: "non_positive_denominator",
  formula: "payback_months(implementation_cost, annual_net_benefit)",
  inputDependencies: ["implementation_cost"],
  outputDependencies: ["annual_net_benefit"],
  customerFacing: true,
  highlight: true,
};

function businessCase(approved: boolean) {
  return {
    id: "case-1",
    title: "Northstar Access Business Case",
    accountId: "account-1",
    accountName: "Northstar Facilities Group",
    opportunityId: "opportunity-1",
    opportunityName: "National access transformation",
    modelId: model.id,
    modelName: model.name,
    modelVersionId: model.latestVersion.id,
    modelVersion: 1,
    modelDefinition,
    currency: "AUD",
    state: approved ? "approved" : "calculated",
    currentVersion: {
      id: "case-version-1",
      version: 1,
      currency: "AUD",
      modelVersionId: model.latestVersion.id,
      modelVersion: 1,
      formulaEngineVersion: "bounded_decimal_v1",
      modelFingerprint: "a".repeat(64),
      calculationFingerprint: "b".repeat(64),
      inputs: [
        {
          key: inputDefinition.key,
          label: inputDefinition.label,
          value: "25000",
          calculationValue: "25000",
          unit: "currency",
          origin: "organisation_assumption",
          sourceId: null,
          sourceLabel: "Approved Summit commercial assumption",
          assumption: true,
          material: true,
          customerFacing: true,
          observedAt: "2026-08-29T00:00:00Z",
          freshness: "current",
        },
      ],
      scenarios: [
        { name: "base", overrides: [], outputs: [roiOutput, paybackOutput] },
        {
          name: "conservative",
          overrides: [{ key: inputDefinition.key, value: "30000" }],
          outputs: [{ ...roiOutput, displayValue: "-40.0" }, paybackOutput],
        },
        {
          name: "upside",
          overrides: [{ key: inputDefinition.key, value: "20000" }],
          outputs: [{ ...roiOutput, displayValue: "5.0" }, paybackOutput],
        },
      ],
      sensitivity: {
        inputKey: inputDefinition.key,
        rows: [
          {
            inputValue: "20000",
            outputs: [{ ...roiOutput, displayValue: "5.0" }],
          },
          { inputValue: "25000", outputs: [roiOutput] },
          {
            inputValue: "30000",
            outputs: [{ ...roiOutput, displayValue: "-40.0" }],
          },
        ],
      },
      reviewState: approved ? "approved" : "pending",
      approvedByUserId: approved ? "user-1" : null,
      approvedAt: approved ? "2026-08-29T02:00:00Z" : null,
      createdByUserId: "user-1",
      createdAt: "2026-08-29T01:30:00Z",
    },
    createdByUserId: "user-1",
    createdAt: "2026-08-29T01:00:00Z",
    updatedAt: "2026-08-29T02:00:00Z",
  };
}

async function mockBusinessCaseApi(page: Page) {
  let approved = false;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/create/availability") {
      await route.fulfill({
        json: {
          moduleKey: "create",
          state: "available",
          enabled: true,
          canManage: true,
          canUploadTemplates: true,
          canCreatePresentations: true,
          message: "Create is available.",
          description: "Build reviewed customer content.",
          learnMorePath: "/create",
        },
      });
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
    if (path === "/api/v1/create/business-cases/case-1/approve") {
      approved = true;
      await route.fulfill({ json: businessCase(approved) });
      return;
    }
    if (path === "/api/v1/create/business-cases/case-1") {
      await route.fulfill({ json: businessCase(approved) });
      return;
    }
    if (path === "/api/v1/create/value-models") {
      await route.fulfill({
        json: { items: [model], canManage: true, maxActiveModels: 50 },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { message: "Not found" } });
  });
}

test.beforeEach(async ({ page }) => mockBusinessCaseApi(page));

test("reviews provenance, negative/no-payback results and approves the exact case version", async ({
  page,
}) => {
  await page.goto("/create/business-cases/case-1");
  await expect(
    page.getByRole("heading", { name: "Northstar Access Business Case" }),
  ).toBeVisible();
  await expect(page.getByText("-29.2%").first()).toBeVisible();
  await expect(
    page.getByText("Not achieved under these assumptions").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Approved Summit commercial assumption" }),
  ).toBeVisible();
  await page.getByText("Why this number? · First-year ROI").click();
  await expect(
    page.getByText(
      "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Conservative, base and upside" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "One-variable sensitivity" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve Business Case" }).click();
  await expect(
    page.getByRole("link", { name: "Use in presentation" }),
  ).toBeVisible();
  await expect(
    page.getByText(/not a guarantee of future results/i),
  ).toBeVisible();
  await expect(page.getByText(/you will save/i)).toHaveCount(0);

  if (process.env.CAPTURE_WO_033_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-033-business-case-desktop.png",
      fullPage: true,
    });
  }
});

test("keeps Business Case review legible on a narrow mobile viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/create/business-cases/case-1");
  await expect(page.getByText("-29.2%").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve Business Case" }),
  ).toBeVisible();
  const mobile = page.getByRole("navigation", { name: "Mobile navigation" });
  await expect(mobile.getByRole("link")).toHaveCount(4);
  if (process.env.CAPTURE_WO_033_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-033-business-case-mobile.png",
      fullPage: true,
    });
  }
});

test("shows the administrator's bounded Value Model builder", async ({
  page,
}) => {
  await page.goto("/create/value-models");
  await expect(
    page.getByRole("heading", { name: "Value Models" }),
  ).toBeVisible();
  await expect(page.getByText("bounded_decimal_v1")).toBeVisible();
  await expect(page.getByText(/No code execution/i)).toBeVisible();
  await expect(page.getByLabel("Bounded formula").first()).toHaveValue(
    "input_1",
  );
  if (process.env.CAPTURE_WO_033_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "../../docs/07-sprints/assets/wo-033-value-model-admin.png",
      fullPage: true,
    });
  }
});
