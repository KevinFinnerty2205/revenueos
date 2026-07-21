import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingDetail } from "@/components/meeting-detail";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MeetingDetail", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders accessible tabs and saves a versioned plain-text transcript", async () => {
    const history = [
      {
        id: "audit-1",
        meetingId: "meeting-1",
        actorUserId: "user-1",
        action: "created",
        entityType: "meeting",
        entityId: "meeting-1",
        changedFields: ["title"],
        version: null,
        createdAt: "2026-07-17T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            meetingId: "meeting-1",
            rawText: "Corrected text.",
            language: "en-AU",
            version: 2,
            source: "manual",
            createdAt: "2026-07-17T00:00:00Z",
            updatedAt: "2026-07-18T00:00:00Z",
          }),
        );
      }
      if (url.endsWith("/participants"))
        return Promise.resolve(jsonResponse([]));
      if (url.endsWith("/intelligence"))
        return Promise.resolve(
          jsonResponse({
            overallState: "unavailable",
            generationAvailable: false,
            retryAvailable: false,
            lastUpdatedAt: null,
            progress: {
              ready: 0,
              queued: 0,
              processing: 0,
              failed: 0,
              notGenerated: 8,
              total: 8,
              summary: "0 of 8 ready",
            },
            executiveSummary: unavailableCapability(),
            buyingSignals: unavailableCapability(),
            objectionsCompetitiveSignals: unavailableCapability(),
            decisions: unavailableCapability(),
            actionItems: unavailableCapability(),
            risksBlockers: unavailableCapability(),
            openQuestions: unavailableCapability(),
            followUpEmail: {
              ...unavailableCapability(),
              tone: null,
            },
          }),
        );
      if (url.endsWith("/intelligence/executive-summary"))
        return Promise.resolve(
          jsonResponse({
            state: "empty",
            generationAvailable: false,
            unavailableReason: "Add a usable transcript first.",
            jobId: null,
            transcriptVersion: null,
            requestedAt: null,
            startedAt: null,
            generatedAt: null,
            safeMessage: null,
            executiveSummary: null,
          }),
        );
      if (url.endsWith("/intelligence/decisions"))
        return Promise.resolve(
          jsonResponse({
            state: "empty",
            generationAvailable: false,
            unavailableReason: "Add a usable transcript first.",
            jobId: null,
            transcriptVersion: null,
            requestedAt: null,
            startedAt: null,
            generatedAt: null,
            safeMessage: null,
            decisions: null,
          }),
        );
      if (url.endsWith("/history"))
        return Promise.resolve(jsonResponse(history));
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            meetingId: "meeting-1",
            rawText: "Original text.",
            language: "en",
            version: 1,
            source: "manual",
            createdAt: "2026-07-17T00:00:00Z",
            updatedAt: "2026-07-17T00:00:00Z",
          }),
        );
      }
      if (url.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            items: [],
            page: 1,
            pageSize: 100,
            total: 0,
            pages: 0,
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          id: "meeting-1",
          organisationId: "organisation-1",
          title: "Acme discovery",
          description: "Discuss expansion.",
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
          ownerUserId: "user-1",
          createdBy: "user-1",
          updatedBy: "user-1",
          createdAt: "2026-07-17T00:00:00Z",
          updatedAt: "2026-07-17T00:00:00Z",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingDetail meetingId="meeting-1" />);
    expect(
      await screen.findByRole("heading", { name: "Acme discovery" }),
    ).toBeVisible();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    overviewTab.focus();
    fireEvent.keyDown(overviewTab, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Intelligence" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Intelligence" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Corrected text." },
    });
    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "en-AU" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save transcript" }));

    expect(
      await screen.findByRole("status", {
        name: "",
      }),
    ).toHaveTextContent("version 2");
    const patchCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/transcript") && init?.method === "PATCH",
    );
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      rawText: "Corrected text.",
      language: "en-AU",
      version: 1,
    });

    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    expect(screen.getByRole("tabpanel", { name: "History" })).toHaveTextContent(
      "Meeting created",
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/history")),
      ).toBe(true),
    );
  });
});

function unavailableCapability() {
  return {
    state: "unavailable",
    generationAvailable: false,
    message: "Add a usable transcript first.",
    generatedAt: null,
    emptyResult: false,
    content: null,
  };
}
