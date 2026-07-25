import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevenueBrainTimeline } from "@/components/revenue-brain-timeline";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const company = {
  id: "company-1",
  organisationId: "organisation-1",
  name: "Acme Australia",
  website: null,
  industry: "Technology",
  employeeCount: 120,
  status: "active",
  ownerUserId: "user-1",
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
};

function snapshot(id: string, meetingDate: string) {
  return {
    id,
    organisationId: "organisation-1",
    companyId: "company-1",
    opportunityId: null,
    meetingId: `meeting-${id}`,
    transcriptVersionId: `transcript-version-${id}`,
    createdAt: "2026-07-20T00:00:00Z",
    meetingDate,
    summaryReference: `summary-${id}`,
    buyingSignalsReference: `buying-${id}`,
    objectionsReference: `objections-${id}`,
    stakeholdersReference: `stakeholders-${id}`,
    decisionsReference: `decisions-${id}`,
    actionsReference: `actions-${id}`,
    risksReference: `risks-${id}`,
    questionsReference: `questions-${id}`,
    nextBestActionReference: `next-${id}`,
    version: 1,
  };
}

const insufficientReasoning = {
  state: "insufficient_history",
  message:
    "Revenue Brain needs at least two completed meeting snapshots before it can identify changes.",
  latest: null,
  history: [],
};

function completedReasoning() {
  const insight = {
    id: "insight-1",
    companyId: "company-1",
    opportunityId: null,
    reasoningVersion: 1,
    createdAt: "2026-07-20T12:00:00Z",
    content: {
      scope: "account",
      fromSnapshotId: "old",
      toSnapshotId: "new",
      fromMeetingId: "meeting-old",
      toMeetingId: "meeting-new",
      fromMeetingDate: "2026-07-10",
      toMeetingDate: "2026-07-20",
      changes: [
        {
          changeType: "budget_confirmed",
          direction: "improved",
          importance: "high",
          title: "Budget was confirmed",
          description: "Budget moved from explicitly unconfirmed to confirmed.",
          confidence: 0.91,
          sourceCapabilities: ["buying_signals"],
          evidence: [
            {
              snapshotId: "new",
              artefactId: "buying-new",
              artefactType: "buying_signals",
              entityKey: "signal:budget_confirmed",
              field: "signal_type",
              value: "budget_confirmed",
            },
          ],
        },
      ],
      summary:
        "The most important supported change was: Budget was confirmed. 1 material supported change was identified.",
      confidence: 0.91,
    },
  };
  return {
    state: "completed",
    message: "Longitudinal reasoning is available.",
    latest: insight,
    history: [insight],
  };
}

describe("RevenueBrainTimeline", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the account snapshot timeline using meeting dates only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        return Promise.resolve(
          path.endsWith("/brain/reasoning")
            ? jsonResponse(completedReasoning())
            : path.endsWith("/brain")
              ? jsonResponse([
                  snapshot("new", "2026-07-20T10:00:00Z"),
                  snapshot("old", "2026-07-10T10:00:00Z"),
                ])
              : jsonResponse(company),
        );
      }),
    );

    render(<RevenueBrainTimeline accountId="company-1" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading Revenue Brain",
    );
    expect(
      await screen.findByRole("heading", { name: "Acme Australia" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Revenue Brain" }),
    ).toBeVisible();
    const timeline = screen.getByRole("list", { name: "Snapshot timeline" });
    expect(timeline).toHaveTextContent("20 July 2026");
    expect(timeline).toHaveTextContent("10 July 2026");
    expect(timeline).not.toHaveTextContent("summary-new");
    expect(screen.getAllByText("Meeting snapshot")).toHaveLength(2);
    expect(screen.getAllByText(/Budget was confirmed/).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getAllByRole("link", { name: "Open meeting" })[0],
    ).toHaveAttribute("href", "/meetings/meeting-new");
  });

  it("shows an empty state when the account has no snapshots", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        return Promise.resolve(
          path.endsWith("/brain/reasoning")
            ? jsonResponse(insufficientReasoning)
            : path.endsWith("/brain")
              ? jsonResponse([])
              : jsonResponse(company),
        );
      }),
    );

    render(<RevenueBrainTimeline accountId="company-1" />);

    expect(
      await screen.findByRole("heading", { name: "No snapshots yet" }),
    ).toBeVisible();
  });

  it("shows a recoverable error state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(company))
      .mockResolvedValueOnce(
        jsonResponse(
          { code: "request_failed", message: "Revenue Brain is unavailable." },
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(insufficientReasoning))
      .mockResolvedValueOnce(jsonResponse(company))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(insufficientReasoning));
    vi.stubGlobal("fetch", fetchMock);

    render(<RevenueBrainTimeline accountId="company-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Revenue Brain is unavailable.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "No snapshots yet" }),
    ).toBeVisible();
  });
});
