import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AskAnswer, AskCapabilities } from "@revenueos/shared";
import { AskRevenueOS } from "@/components/ask-revenueos";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const capabilities: AskCapabilities = {
  enabled: true,
  scope: {
    type: "opportunity",
    id: "opportunity-1",
    label: "Qantas expansion",
  },
  supportedScopes: ["opportunity", "account", "workspace"],
  retainedHistory: false,
  publicWebResearch: false,
  actionExecution: false,
  maxQuestionCharacters: 1000,
  maxSources: 12,
  safeMessage:
    "Ask answers from authorised RevenueOS evidence. It does not search the public web or perform actions.",
};

function answer(overrides: Partial<AskAnswer> = {}): AskAnswer {
  return {
    schemaVersion: 1,
    askRequestId: "request-1",
    answer:
      "Security review is the clearest current blocker, and the approval path is still incomplete.",
    answerStatus: "partially_supported",
    questionClass: "blocker_risk",
    summaryPoints: [
      {
        text: "The customer requires security review before pilot approval.",
        sourceIds: ["evidence-1"],
      },
    ],
    sources: [
      {
        id: "evidence-1",
        sourceType: "accepted_evidence",
        label: "Verified inbound customer email",
        occurredAt: "2026-08-23T01:00:00Z",
        excerpt: "The customer requires security review before pilot approval.",
        provenance: "customer_direct",
        href: "/opportunities/opportunity-1#customer-evidence",
      },
    ],
    uncertainties: ["The final security review date is not confirmed."],
    suggestedAction: {
      label: "Review opportunity",
      href: "/opportunities/opportunity-1",
      sourceId: "evidence-1",
    },
    followUpQuestions: ["Who is the economic buyer?"],
    scope: {
      type: "opportunity",
      id: "opportunity-1",
      label: "Qantas expansion",
    },
    generatedAt: "2026-08-24T01:00:00Z",
    ...overrides,
  };
}

describe("AskRevenueOS", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows representative bounded workspace question phrasings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...capabilities,
          scope: { type: "workspace", id: null, label: "Your sales work" },
        }),
      ),
    );

    render(<AskRevenueOS scopeType="workspace" />);

    expect(
      await screen.findByRole("button", { name: "What should I do next?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "What are the biggest deal risks?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Which commitments are overdue?" }),
    ).toBeVisible();
  });

  it("renders a scoped, cited answer with progressive source disclosure and follow-ups", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockResolvedValueOnce(jsonResponse(answer()))
      .mockResolvedValueOnce(
        jsonResponse(
          answer({
            answer: "The economic buyer is not reliably identified.",
            questionClass: "stakeholder",
          }),
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);

    expect(await screen.findByText("About: Qantas expansion")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Ask RevenueOS"), {
      target: { value: "What is holding this deal back?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByRole("heading", { name: "Partially supported" }),
    ).toBeVisible();
    expect(screen.getByText(/Security review is the clearest/)).toBeVisible();
    expect(screen.getByText("Why RevenueOS believes it")).toBeVisible();
    expect(screen.getByText("Needs clarification")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Review opportunity" }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1");

    const details = screen.getByText("Sources (1)").closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Sources (1)"));
    expect(
      within(details as HTMLElement).getByText(
        "Verified inbound customer email",
      ),
    ).toBeVisible();
    expect(
      within(details as HTMLElement).getByText("Customer-direct"),
    ).toBeVisible();
    expect(
      within(details as HTMLElement).getByRole("link", {
        name: /Verified inbound customer email/i,
      }),
    ).toHaveAttribute("href", "/opportunities/opportunity-1#customer-evidence");

    fireEvent.click(
      screen.getByRole("button", { name: "Who is the economic buyer?" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const followUpBody = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body));
    expect(followUpBody).toMatchObject({
      question: "Who is the economic buyer?",
      scopeType: "opportunity",
      scopeId: "opportunity-1",
    });
    const telemetryBody = JSON.parse(
      String(fetchMock.mock.calls[3]?.[1]?.body),
    );
    expect(telemetryBody).toEqual({
      eventType: "follow_up_selected",
      askRequestId: "request-1",
    });
  });

  it("labels Selling Profile answers as organisation context rather than customer Evidence", async () => {
    const sellingAnswer = answer({
      answer: "Sales Brain: A reviewed relationship-intelligence workspace.",
      answerStatus: "supported",
      questionClass: "selling_context",
      summaryPoints: [
        {
          text: "Sales Brain: A reviewed relationship-intelligence workspace.",
          sourceIds: ["profile-revision-2"],
        },
      ],
      sources: [
        {
          id: "profile-revision-2",
          sourceType: "selling_profile",
          label: "Approved Company & Selling Profile · revision 2",
          occurredAt: "2026-09-04T00:00:00Z",
          excerpt:
            "Sales Brain: A reviewed relationship-intelligence workspace.",
          provenance: "organisation_approved",
          href: "/settings#company-selling-profile",
        },
      ],
      uncertainties: [
        "This is organisation-approved selling context, not customer Evidence or proof about a specific buyer.",
      ],
      suggestedAction: null,
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(capabilities))
        .mockResolvedValueOnce(jsonResponse(sellingAnswer)),
    );
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
    await screen.findByText("About: Qantas expansion");
    fireEvent.change(screen.getByLabelText("Ask RevenueOS"), {
      target: { value: "What do we sell?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByRole("heading", {
        name: "Approved organisation context",
        level: 2,
      }),
    ).toBeVisible();
    expect(screen.getByText(/not customer Evidence/i)).toBeVisible();
    fireEvent.click(screen.getByText("Sources (1)"));
    expect(screen.getByText("Organisation-approved context")).toBeVisible();
    expect(
      screen.queryByText("Supported by current evidence"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["conflicting", "Conflicting evidence"],
    ["unknown", "Not enough reliable evidence"],
  ] as const)(
    "renders the %s answer state without overstating confidence",
    async (status, label) => {
      const stateAnswer = answer({
        answerStatus: status,
        answer:
          status === "unknown"
            ? "I don’t have that information in RevenueOS. Ask RevenueOS does not research the public web yet."
            : "RevenueOS found material disagreement in the current evidence.",
        summaryPoints: status === "unknown" ? [] : answer().summaryPoints,
        sources: status === "unknown" ? [] : answer().sources,
        suggestedAction: null,
      });
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValueOnce(jsonResponse(capabilities))
          .mockResolvedValueOnce(jsonResponse(stateAnswer)),
      );
      render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
      await screen.findByText("About: Qantas expansion");
      fireEvent.click(
        screen.getByRole("button", { name: "What changed recently?" }),
      );
      expect(await screen.findByRole("heading", { name: label })).toBeVisible();
      if (status === "unknown") {
        expect(screen.queryByText(/Sources \(/)).not.toBeInTheDocument();
        expect(
          screen.getByText(/does not research the public web/i),
        ).toBeVisible();
      }
    },
  );

  it("shows loading and supports retry after a safe API error", async () => {
    let resolveAnswer: ((response: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveAnswer = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce(jsonResponse(answer()));
    vi.stubGlobal("fetch", fetchMock);
    render(<AskRevenueOS scopeType="opportunity" scopeId="opportunity-1" />);
    await screen.findByText("About: Qantas expansion");
    fireEvent.click(
      screen.getByRole("button", { name: "What is holding this deal back?" }),
    );
    expect(
      screen.getByRole("button", { name: "Checking RevenueOS…" }),
    ).toBeDisabled();
    resolveAnswer?.(
      jsonResponse(
        {
          code: "ask_unavailable",
          message: "RevenueOS could not answer right now.",
        },
        503,
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "RevenueOS could not answer right now.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText(/Security review is the clearest/),
    ).toBeVisible();
  });
});
