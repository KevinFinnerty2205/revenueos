import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PreInteractionBrief } from "@/components/pre-interaction-brief";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyResponse = {
  state: "not_generated",
  generationAvailable: true,
  unavailableReason: null,
  safeMessage: null,
  brief: null,
  generatedAt: null,
  reviewed: false,
  reviewedAt: null,
  priorVersions: [],
  sourceLabels: [],
};

const completedResponse = {
  ...emptyResponse,
  state: "completed",
  generatedAt: "2026-08-14T02:00:00Z",
  sourceLabels: [
    "Interaction details",
    "Opportunity record",
    "Prior validated Meeting Intelligence",
  ],
  brief: {
    interactionId: "interaction-1",
    interactionType: "phone_call",
    briefVersion: 1,
    headline: "Confirm procurement ownership and agree the next step.",
    accountContext:
      "The opportunity is in evaluation with validated prior context.",
    recentChanges: [
      {
        change: "Procurement entered the process.",
        importance: "high",
        source: "revenue_brain",
      },
    ],
    objectives: [
      {
        objective: "Clarify procurement ownership.",
        priority: "high",
        reason: "The approval path remains unresolved.",
      },
    ],
    questionsToAsk: [
      {
        question: "Who will own the procurement process from here?",
        purpose: "Clarify the approval path.",
        priority: "high",
      },
    ],
    stakeholderFocus: [
      {
        name: "Alex Morgan",
        role: "champion",
        focus: "Confirm current priorities and the next introduction.",
      },
    ],
    openCommitments: [
      {
        commitment: "Provide the security summary.",
        owner: "Revenue team",
        dueDate: null,
      },
    ],
    risksToWatch: [
      { risk: "Security review may delay progress.", severity: "high" },
    ],
    successCriteria: ["A next step, owner and timing are agreed."],
    interactionGuidance:
      "Keep the call concise, lead with the objective and close with a confirmed next step.",
    confidence: 0.82,
  },
};

describe("PreInteractionBrief", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("generates, displays and reviews a compact phone-call brief", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (String(_input).endsWith("/review")) {
        return Promise.resolve(
          jsonResponse({
            ...completedResponse,
            reviewed: true,
            reviewedAt: "2026-08-14T02:05:00Z",
          }),
        );
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({ ...completedResponse, created: true }),
        );
      }
      return Promise.resolve(jsonResponse(emptyResponse));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PreInteractionBrief
        interactionId="interaction-1"
        interactionType="phone_call"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading preparation brief",
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Prepare brief" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Confirm procurement ownership and agree the next step.",
      }),
    ).toBeVisible();
    expect(screen.getByText("Compact call brief")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Contact and role" }),
    ).toBeVisible();
    expect(screen.getByText("Alex Morgan · champion")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Purpose and desired next step" }),
    ).toBeVisible();
    expect(screen.getByText("Latest commitment")).toBeVisible();
    expect(screen.getByText("Objection or timeline issue")).toBeVisible();
    expect(screen.getByText(/Recent Revenue Brain change:/)).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Recommended questions" }),
    ).toBeVisible();
    expect(screen.getByText(/Sources: Interaction details/)).toHaveTextContent(
      "Prior validated Meeting Intelligence",
    );
    expect(screen.queryByText(/recording|prompt|provider|worker/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Mark as reviewed" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reviewed" })).toBeDisabled(),
    );
  });

  it("shows presentation-specific preparation without treating seller material as evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...completedResponse,
            brief: {
              ...completedResponse.brief,
              interactionType: "presentation",
              interactionGuidance:
                "Treat seller-prepared material as context, not customer evidence, and close with a validation step.",
            },
          }),
        ),
      ),
    );

    render(
      <PreInteractionBrief
        interactionId="interaction-1"
        interactionType="presentation"
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Presentation guidance" }),
    ).toBeVisible();
    expect(screen.getByText(/seller-prepared material/i)).toBeVisible();
  });

  it.each([
    ["unavailable", "Link account or opportunity context"],
    ["queued", "Preparing the latest brief"],
    ["running", "Preparing the latest brief"],
    ["failed", "The brief is not ready"],
    ["cancelled", "The brief is not ready"],
  ])("renders the %s state safely", async (state, expected) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...emptyResponse,
            state,
            generationAvailable: state !== "unavailable",
            safeMessage:
              state === "failed" || state === "cancelled"
                ? "The brief is not ready. You can try again."
                : null,
          }),
        ),
      ),
    );

    render(
      <PreInteractionBrief
        interactionId={`interaction-${state}`}
        interactionType="face_to_face_meeting"
      />,
    );
    expect(await screen.findByText(new RegExp(expected, "i"))).toBeVisible();
  });
});
