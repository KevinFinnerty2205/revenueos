import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  MethodologyDefinitionSummary,
  MethodologyProjectionItem,
  OpportunityMethodologyResponse,
} from "@revenueos/shared";
import { OpportunityMethodology } from "@/components/opportunity-methodology";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const definition: MethodologyDefinitionSummary = {
  id: null,
  key: "meddpicc",
  name: "MEDDPICC",
  description: "Evidence-backed deal qualification.",
  version: 1,
  standard: true,
  status: "active",
  fieldCount: 4,
  fields: [],
  createdAt: null,
};

function item(
  fieldKey: string,
  displayName: string,
  state: MethodologyProjectionItem["state"],
  conclusion: string | null,
): MethodologyProjectionItem {
  const supported = state !== "unknown";
  return {
    fieldKey,
    displayName,
    explanation: supported
      ? "Current validated evidence supports this interpretation."
      : "No reliable current evidence identifies the commercial approver.",
    required: true,
    state,
    conclusion,
    sources: supported
      ? [
          {
            sourceType: "interaction_intelligence",
            sourceId: `source-${fieldKey}`,
            itemKey: fieldKey,
            label: "Final interaction intelligence",
            origin: "customer_direct",
            supportedAt: "2026-08-15T03:00:00Z",
            sourceClassification: "final_validated",
          },
        ]
      : [],
    conflicts: [],
    lastSupportedAt: supported ? "2026-08-15T03:00:00Z" : null,
    freshness: "current",
    suggestedQuestion:
      state === "confirmed"
        ? null
        : "Who ultimately owns commercial approval for this project?",
    stageExpectation: "evaluation",
    reviews: [],
  };
}

function methodology(
  overrides: Partial<OpportunityMethodologyResponse> = {},
): OpportunityMethodologyResponse {
  return {
    state: "current",
    generationAvailable: true,
    needsRefresh: false,
    safeMessage: "Current evidence-backed methodology view.",
    definition,
    projectionId: "projection-1",
    projection: {
      opportunityId: "opportunity-1",
      methodologyKey: "meddpicc",
      methodologyName: "MEDDPICC",
      definitionVersion: 1,
      projectionVersion: 2,
      engineVersion: 1,
      stateCounts: {
        confirmed: 1,
        partiallySupported: 1,
        unknown: 1,
        conflicting: 1,
        stale: 0,
      },
      items: [
        item(
          "champion",
          "Champion",
          "confirmed",
          "Jordan is an active internal supporter.",
        ),
        item("economic_buyer", "Economic Buyer", "unknown", null),
        item(
          "paper_process",
          "Paper Process",
          "partially_supported",
          "Procurement is involved; the final path is unclear.",
        ),
        item(
          "decision_process",
          "Decision Process",
          "conflicting",
          "Current dates disagree.",
        ),
      ],
      generatedAt: "2026-08-15T03:00:00Z",
    },
    generatedAt: "2026-08-15T03:00:00Z",
    ...overrides,
  };
}

describe("OpportunityMethodology", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("leads with plain-language gaps and reveals lineage progressively", () => {
    render(
      <OpportunityMethodology
        opportunityId="opportunity-1"
        initialMethodology={methodology()}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Sales Methodology" }),
    ).toBeVisible();
    expect(
      screen.getByText(/without scoring or blocking deal stages/i),
    ).toBeVisible();
    expect(screen.getByText("Economic Buyer")).toBeVisible();
    expect(screen.getByText("Decision Process")).toBeVisible();
    expect(screen.queryByText("Champion")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "View all 4 fields" }));
    const champion = screen.getByText("Champion").closest("li");
    expect(champion).not.toBeNull();
    expect(within(champion!).getByText("Confirmed")).toBeVisible();
    fireEvent.click(within(champion!).getByText(/Why this state/i));
    expect(
      within(champion!).getByText("Final interaction intelligence"),
    ).toBeVisible();
    expect(within(champion!).getByText(/Customer direct/i)).toBeVisible();
  });

  it("records clarification as salesperson-reported evidence without rewriting sources", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      response({
        reviewId: "review-1",
        clarificationEvidenceId: "evidence-1",
        methodology: methodology({
          state: "needs_refresh",
          needsRefresh: true,
          projection: null,
          safeMessage: "Evidence changed. Refresh the methodology view.",
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <OpportunityMethodology
        opportunityId="opportunity-1"
        initialMethodology={methodology()}
      />,
    );

    const economicBuyer = screen.getByText("Economic Buyer").closest("li");
    fireEvent.click(within(economicBuyer!).getByText("Review or correct"));
    fireEvent.click(
      within(economicBuyer!).getByRole("button", { name: "Add clarification" }),
    );
    expect(
      within(economicBuyer!).getByText(/does not become customer-confirmed/i),
    ).toBeVisible();
    fireEvent.change(
      within(economicBuyer!).getByLabelText(
        "Salesperson-reported clarification",
      ),
      {
        target: {
          value: "Finance owns final approval, according to my notes.",
        },
      },
    );
    fireEvent.click(
      within(economicBuyer!).getByRole("button", {
        name: "Save clarification",
      }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      expectedProjectionId: "projection-1",
      action: "clarify",
      clarification: "Finance owns final approval, according to my notes.",
    });
    expect(
      await screen.findByText(/saved as salesperson-reported evidence/i),
    ).toBeVisible();
    expect(screen.getByText(/conclusions are hidden here/i)).toBeVisible();
  });

  it("keeps the empty state useful when no methodology is configured", () => {
    render(
      <OpportunityMethodology
        opportunityId="opportunity-1"
        initialMethodology={methodology({
          state: "not_configured",
          generationAvailable: false,
          needsRefresh: false,
          definition: null,
          projectionId: null,
          projection: null,
          generatedAt: null,
          safeMessage:
            "Your organisation has not selected a sales methodology.",
        })}
      />,
    );
    expect(
      screen.getAllByText(/has not selected a sales methodology/i),
    ).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: /Generate|Refresh/i }),
    ).toBeNull();
  });
});
