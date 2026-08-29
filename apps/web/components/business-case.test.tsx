import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BusinessCaseReview } from "@/components/business-case-review";
import { ValueModelAdmin } from "@/components/value-model-admin";

vi.mock("next/navigation", () => ({
  usePathname: () => "/create/business-cases/case-1",
}));

function jsonResponse(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const inputDefinition = {
  key: "implementation_cost",
  label: "Implementation cost",
  description: "Approved implementation cost.",
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
  scenarioPreset: null,
  displayOrder: 1,
};

const roiOutput = {
  key: "roi_percentage",
  label: "First-year ROI",
  description: "First-year net benefit divided by approved cost.",
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
  ...roiOutput,
  key: "payback_months",
  label: "Payback",
  description: "Payback under positive annual net benefit.",
  unit: "months",
  exactValue: null,
  displayValue: null,
  unavailableReason: "non_positive_denominator",
  formula: "payback_months(implementation_cost, annual_net_benefit)",
};

const businessCase = {
  id: "case-1",
  title: "Northstar Access Business Case",
  accountId: "account-1",
  accountName: "Northstar Facilities",
  opportunityId: "opportunity-1",
  opportunityName: "Access transformation",
  modelId: "model-1",
  modelName: "Multi-Site Access Efficiency",
  modelVersionId: "model-version-1",
  modelVersion: 1,
  modelDefinition: {
    inputs: [inputDefinition],
    outputs: [
      {
        key: roiOutput.key,
        label: roiOutput.label,
        description: roiOutput.description,
        formula: roiOutput.formula,
        unit: roiOutput.unit,
        displayPrecision: 1,
        customerFacing: true,
        highlight: true,
        scenarioSensitive: true,
        displayOrder: 1,
      },
    ],
    customerDisclaimer: "Based on the assumptions shown.",
  },
  currency: "AUD",
  state: "approved",
  currentVersion: {
    id: "case-version-1",
    version: 1,
    currency: "AUD",
    modelVersionId: "model-version-1",
    modelVersion: 1,
    formulaEngineVersion: "bounded_decimal_v1",
    modelFingerprint: "a".repeat(64),
    calculationFingerprint: "b".repeat(64),
    inputs: [
      {
        key: "implementation_cost",
        label: "Implementation cost",
        value: "25000",
        calculationValue: "25000",
        unit: "currency",
        origin: "organisation_assumption",
        sourceId: null,
        sourceLabel: "Approved organisation assumption",
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
        overrides: [{ key: "implementation_cost", value: "30000" }],
        outputs: [{ ...roiOutput, displayValue: "-40.0" }, paybackOutput],
      },
      {
        name: "upside",
        overrides: [{ key: "implementation_cost", value: "20000" }],
        outputs: [{ ...roiOutput, displayValue: "5.0" }, paybackOutput],
      },
    ],
    sensitivity: null,
    reviewState: "approved",
    approvedByUserId: "user-1",
    approvedAt: "2026-08-29T01:00:00Z",
    createdByUserId: "user-1",
    createdAt: "2026-08-29T00:00:00Z",
  },
  createdByUserId: "user-1",
  createdAt: "2026-08-29T00:00:00Z",
  updatedAt: "2026-08-29T01:00:00Z",
};

describe("ROI and Business Case Builder", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows negative results, unavailable payback, provenance, formula lineage and explicit scenarios", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse(businessCase)),
    );
    render(<BusinessCaseReview caseId="case-1" />);

    expect(
      await screen.findByRole("heading", {
        name: "Northstar Access Business Case",
      }),
    ).toBeVisible();
    expect(screen.getAllByText("-29.2%").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Not achieved under these assumptions").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Material", { exact: true })[0]).toBeVisible();
    expect(screen.getByText("Approved organisation assumption")).toBeVisible();
    expect(
      screen.getByText(
        "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
      ),
    ).toBeInTheDocument();
    const scenarios = screen.getByRole("heading", {
      name: "Conservative, base and upside",
    }).parentElement;
    expect(scenarios).not.toBeNull();
    expect(
      within(scenarios!).getByRole("heading", { name: "Base" }),
    ).toBeVisible();
    expect(
      within(scenarios!).getByRole("heading", { name: "Conservative" }),
    ).toBeVisible();
    expect(
      within(scenarios!).getByRole("heading", { name: "Upside" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Use in presentation" }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("businessCaseVersionId=case-version-1"),
    );
    expect(screen.queryByText(/you will save/i)).not.toBeInTheDocument();
  });

  it("gives administrators a bounded form builder rather than a spreadsheet or JSON editor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        jsonResponse({ items: [], canManage: true, maxActiveModels: 50 }),
      ),
    );
    render(<ValueModelAdmin />);

    expect(
      await screen.findByRole("heading", { name: "Value Models" }),
    ).toBeVisible();
    expect(
      screen.getAllByLabelText("Key", { selector: "input" })[0],
    ).toHaveValue("input_1");
    expect(screen.getByLabelText(/Bounded formula/)).toHaveValue("input_1");
    expect(screen.getByText(/no code execution/i)).toBeVisible();
    expect(screen.queryByText(/spreadsheet grid/i)).not.toBeInTheDocument();
  });
});
