import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  MethodologyCatalogueResponse,
  MethodologyDefinitionSummary,
} from "@revenueos/shared";
import { SalesMethodologySettings } from "@/components/sales-methodology-settings";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function standard(
  key: "meddic" | "meddpicc" | "bant" | "spiced",
): MethodologyDefinitionSummary {
  return {
    id: null,
    key,
    name: key.toUpperCase(),
    description: `${key.toUpperCase()} standard definition.`,
    version: 1,
    standard: true,
    status: "active",
    fieldCount: 1,
    fields: [
      {
        key: "need",
        displayName: "Need",
        explanation: "The problem that justifies change.",
        order: 1,
        required: true,
        evidenceExpectations: ["Current customer evidence"],
        canonicalFacts: ["need"],
        evidenceCategories: ["commercial_intent"],
        freshnessDays: 90,
        suggestedQuestions: ["What needs to change?"],
        stageExpectation: "discovery",
      },
    ],
    createdAt: null,
  };
}

function catalogue(
  selection: "none" | "meddpicc" = "none",
): MethodologyCatalogueResponse {
  return {
    standards: [
      standard("meddic"),
      standard("meddpicc"),
      standard("bant"),
      standard("spiced"),
    ],
    custom: [],
    current: {
      selection,
      customDefinitionId: null,
      effectiveDefinition:
        selection === "meddpicc" ? standard("meddpicc") : null,
      updatedAt: null,
    },
    customMethodologyLimit: 5,
    fieldLimit: 20,
    executableRulesSupported: false,
  };
}

describe("SalesMethodologySettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("selects an organisation default while explaining the safe boundaries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(catalogue()))
      .mockResolvedValueOnce(response(catalogue("meddpicc").current))
      .mockResolvedValueOnce(response(catalogue("meddpicc")));
    vi.stubGlobal("fetch", fetchMock);
    render(<SalesMethodologySettings />);

    expect(
      await screen.findByRole("heading", { name: "Sales Methodology" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /do not score opportunities, block stages, or execute rules/i,
      ),
    ).toBeVisible();
    const card = screen.getByText("MEDDPICC").closest("div.rounded-2xl");
    fireEvent.click(card!.querySelector("button")!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(
      JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body)),
    ).toEqual({
      selection: "meddpicc",
      customDefinitionId: null,
    });
    expect(
      await screen.findByText(
        /Existing evidence and review history are preserved/i,
      ),
    ).toBeVisible();
  });

  it("creates a bounded custom definition through the guided form", async () => {
    const saved = {
      ...standard("bant"),
      id: "custom-1",
      key: "custom_custom1",
      name: "Mutual plan",
      standard: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(catalogue()))
      .mockResolvedValueOnce(response(saved, 201))
      .mockResolvedValueOnce(response({ ...catalogue(), custom: [saved] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<SalesMethodologySettings />);

    await screen.findByRole("heading", { name: "Custom methodology builder" });
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Mutual plan" },
    });
    fireEvent.change(screen.getByLabelText("Purpose"), {
      target: { value: "Understand the jointly agreed path." },
    });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Success outcome" },
    });
    fireEvent.change(screen.getByLabelText("Stable key"), {
      target: { value: "success_outcome" },
    });
    fireEvent.change(screen.getByLabelText("What this field means"), {
      target: { value: "The outcome both teams have agreed matters." },
    });
    fireEvent.change(screen.getByLabelText("Expected evidence"), {
      target: { value: "Current customer-direct evidence" },
    });
    fireEvent.change(screen.getByLabelText("Suggested discovery question"), {
      target: { value: "What outcome should we agree together?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create methodology" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body).toMatchObject({
      name: "Mutual plan",
      fields: [
        {
          key: "success_outcome",
          canonicalFacts: ["need"],
          evidenceCategories: ["buying_signal"],
          suggestedQuestions: ["What outcome should we agree together?"],
        },
      ],
    });
    expect(await screen.findByText(/Created Mutual plan/i)).toBeVisible();
  });
});
