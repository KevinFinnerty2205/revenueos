import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExecutiveSummaryPanel } from "@/components/executive-summary-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptySummary = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  executiveSummary: null,
};

describe("ExecutiveSummaryPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("requests generation once and prevents duplicate submissions", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptySummary))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePost = resolve;
          }),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptySummary,
          state: "queued",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ExecutiveSummaryPanel meetingId="meeting-1" />);
    const button = await screen.findByRole("button", {
      name: "Generate Executive Summary",
    });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(screen.getByRole("button", { name: "Requesting…" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);

    await act(async () => {
      resolvePost?.(
        jsonResponse(
          {
            jobId: "job-1",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            requestedAt: "2026-07-18T00:00:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      );
    });
    expect(
      await screen.findByText("Executive Summary is queued…"),
    ).toBeVisible();
  });

  it("renders only the completed Executive Summary fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          state: "completed",
          generationAvailable: false,
          unavailableReason: null,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
          generatedAt: "2026-07-18T00:00:02Z",
          safeMessage: null,
          executiveSummary: {
            executiveSummary:
              "The customer discussed expansion plans and agreed on the next commercial review.",
            meetingType: "sales_discovery",
            sentiment: "positive",
            confidence: 0.82,
          },
        }),
      ),
    );

    render(<ExecutiveSummaryPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(/customer discussed expansion plans/i),
    ).toBeVisible();
    expect(screen.getByText("Sales Discovery")).toBeVisible();
    expect(screen.getByText("Positive")).toBeVisible();
    expect(screen.getByText("82%")).toBeVisible();
    expect(screen.queryByText(/action item/i)).not.toBeInTheDocument();
  });

  it("polls without overlap and stops after a terminal result", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptySummary,
          state: "running",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptySummary,
          state: "failed",
          generationAvailable: true,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
          safeMessage: "Executive Summary generation could not be completed.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ExecutiveSummaryPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Generating Executive Summary…")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(
      screen.getByText("Executive Summary generation could not be completed."),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows a safe retry control after a network error", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("The request could not be completed."))
      .mockResolvedValueOnce(jsonResponse(emptySummary));
    vi.stubGlobal("fetch", fetchMock);

    render(<ExecutiveSummaryPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText("The request could not be completed."),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Generate Executive Summary" }),
      ).toBeVisible(),
    );
  });
});
