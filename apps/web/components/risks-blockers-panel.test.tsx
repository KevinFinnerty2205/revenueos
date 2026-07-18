import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RisksBlockersPanel } from "@/components/risks-blockers-panel";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyRisksBlockers = {
  state: "empty",
  generationAvailable: true,
  unavailableReason: null,
  jobId: null,
  transcriptVersion: null,
  requestedAt: null,
  startedAt: null,
  generatedAt: null,
  safeMessage: null,
  risksBlockers: null,
};

describe("RisksBlockersPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows transcript unavailability without a generation control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyRisksBlockers,
          generationAvailable: false,
          unavailableReason:
            "Add a usable transcript before generating Risks & Blockers.",
        }),
      ),
    );

    render(<RisksBlockersPanel meetingId="meeting-1" />);

    expect(
      await screen.findByText(
        "Add a usable transcript before generating Risks & Blockers.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generate Risks & Blockers" }),
    ).not.toBeInTheDocument();
  });

  it("requests generation once and prevents duplicate submissions", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(emptyRisksBlockers))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePost = resolve;
          }),
      )
      .mockResolvedValue(
        jsonResponse({
          ...emptyRisksBlockers,
          state: "queued",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<RisksBlockersPanel meetingId="meeting-1" />);
    const button = await screen.findByRole("button", {
      name: "Generate Risks & Blockers",
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
      await screen.findByText("Risks & Blockers generation is queued…"),
    ).toBeVisible();
  });

  it("polls without overlap, renders risks and stops at completion", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...emptyRisksBlockers,
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
          state: "completed",
          generationAvailable: false,
          unavailableReason: null,
          jobId: "job-1",
          transcriptVersion: 1,
          requestedAt: "2026-07-18T00:00:00Z",
          startedAt: "2026-07-18T00:00:01Z",
          generatedAt: "2026-07-18T00:00:02Z",
          safeMessage: null,
          risksBlockers: {
            risks: [
              {
                risk: "Procurement approval may delay implementation.",
                category: "procurement",
                severity: "high",
                owner: "Customer Procurement",
                confidence: 0.93,
                evidence:
                  "The customer said procurement usually takes six weeks.",
              },
              {
                risk: "Budget approval remains outstanding.",
                category: "budget",
                severity: "medium",
                owner: null,
                confidence: 0.81,
                evidence:
                  "The transcript establishes that funding has not been approved.",
              },
            ],
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<RisksBlockersPanel meetingId="meeting-1" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Generating Risks & Blockers…")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(
      screen.getByText("Procurement approval may delay implementation."),
    ).toBeVisible();
    expect(screen.getByText("Customer Procurement")).toBeVisible();
    expect(screen.getByText("Procurement")).toBeVisible();
    expect(screen.getByText("High")).toBeVisible();
    expect(screen.getByText("93%")).toBeVisible();
    expect(screen.getByText("81%")).toBeVisible();
    expect(screen.getAllByText("Owner")).toHaveLength(1);
    expect(screen.queryByText(/probability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/mitigation/i)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("treats an empty list as a successful result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...emptyRisksBlockers,
          state: "completed",
          generationAvailable: false,
          jobId: "job-1",
          transcriptVersion: 1,
          generatedAt: "2026-07-18T00:00:02Z",
          risksBlockers: { risks: [] },
        }),
      ),
    );

    render(<RisksBlockersPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "No risks or blockers were identified in this meeting.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe failure, retries, and aborts an in-flight load on unmount", async () => {
    const failed = {
      ...emptyRisksBlockers,
      state: "failed",
      generationAvailable: true,
      jobId: "job-1",
      transcriptVersion: 1,
      safeMessage: "Risks & Blockers generation could not be completed.",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(failed))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            jobId: "job-2",
            status: "queued",
            created: true,
            transcriptVersion: 1,
            requestedAt: "2026-07-18T00:00:00Z",
            startedAt: null,
            completedAt: null,
          },
          202,
        ),
      )
      .mockImplementation(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<RisksBlockersPanel meetingId="meeting-1" />);
    expect(
      await screen.findByText(
        "Risks & Blockers generation could not be completed.",
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Try generation again" }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(3),
    );
    const signal = fetchMock.mock.calls.at(-1)?.[1]?.signal;
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
