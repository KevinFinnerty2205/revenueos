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

describe("RevenueBrainTimeline", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the account snapshot timeline using meeting dates only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/brain")
            ? jsonResponse([
                snapshot("new", "2026-07-20T10:00:00Z"),
                snapshot("old", "2026-07-10T10:00:00Z"),
              ])
            : jsonResponse(company),
        ),
      ),
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
  });

  it("shows an empty state when the account has no snapshots", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/brain")
            ? jsonResponse([])
            : jsonResponse(company),
        ),
      ),
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
      .mockResolvedValueOnce(jsonResponse(company))
      .mockResolvedValueOnce(jsonResponse([]));
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
