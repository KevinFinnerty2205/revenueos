import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingDetail } from "@/components/meeting-detail";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function meetingFixture(meetingId: string, label: string) {
  return {
    id: meetingId,
    interactionId: `interaction-${meetingId}`,
    organisationId: "organisation-1",
    title: `${label} meeting`,
    description: `${label} private description`,
    meetingDate: "2026-08-01T00:00:00Z",
    meetingType: "remote",
    status: "completed",
    companyId: null,
    opportunityId: null,
    ownerUserId: "user-1",
    createdBy: "user-1",
    updatedBy: "user-1",
    createdAt: "2026-07-17T00:00:00Z",
    updatedAt: "2026-07-17T00:00:00Z",
  };
}

function participantFixture(meetingId: string, label: string) {
  return {
    id: `participant-${meetingId}`,
    meetingId,
    contactId: null,
    displayName: `${label} participant`,
    email: `${label.toLowerCase()}@example.test`,
    role: "attendee",
    attendanceStatus: "attended",
    createdAt: "2026-07-17T00:00:00Z",
    updatedAt: "2026-07-17T00:00:00Z",
  };
}

function transcriptFixture(meetingId: string, label: string, version: number) {
  return {
    id: `transcript-${meetingId}`,
    meetingId,
    rawText: `${label} private transcript`,
    language: "en",
    version,
    source: "manual",
    createdAt: "2026-07-17T00:00:00Z",
    updatedAt: "2026-07-17T00:00:00Z",
  };
}

function historyFixture(meetingId: string, label: string) {
  return {
    id: `audit-${meetingId}`,
    meetingId,
    actorUserId: "user-1",
    action: "updated",
    entityType: "meeting",
    entityId: meetingId,
    changedFields: [`${label.toLowerCase()}_private_field`],
    version: null,
    createdAt: "2026-07-17T00:00:00Z",
  };
}

function loadFixtureResponse(url: string, meetingId: string, label: string) {
  if (url.endsWith("/participants")) {
    return jsonResponse([participantFixture(meetingId, label)]);
  }
  if (url.endsWith("/transcript")) {
    return jsonResponse(
      transcriptFixture(meetingId, label, label === "Alpha" ? 3 : 7),
    );
  }
  if (url.endsWith("/history")) {
    return jsonResponse([historyFixture(meetingId, label)]);
  }
  if (url.includes("/companies")) {
    return jsonResponse({
      items: [],
      page: 1,
      pageSize: 100,
      total: 0,
      pages: 0,
    });
  }
  return jsonResponse(meetingFixture(meetingId, label));
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
            meetingId: "meeting-1",
            overallState: "unavailable",
            generationAvailable: false,
            retryAvailable: false,
            lastUpdatedAt: null,
            progress: {
              ready: 0,
              queued: 0,
              processing: 0,
              failed: 0,
              notGenerated: 10,
              total: 10,
              summary: "0 of 10 ready",
            },
            executiveSummary: unavailableCapability(),
            buyingSignals: unavailableCapability(),
            objectionsCompetitiveSignals: unavailableCapability(),
            stakeholderIntelligence: unavailableCapability(),
            decisions: unavailableCapability(),
            actionItems: unavailableCapability(),
            risksBlockers: unavailableCapability(),
            openQuestions: unavailableCapability(),
            nextBestAction: unavailableCapability(),
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
          interactionId: "interaction-1",
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
    expect(
      screen.getByRole("link", { name: "Interaction record" }),
    ).toHaveAttribute("href", "/interactions/interaction-1");
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

  it("clears the previous meeting while loading and saves only the rendered meeting", async () => {
    const bravoMeetingLoad = createDeferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        if (!url.endsWith("/meetings/meeting-b/transcript")) {
          return Promise.reject(
            new Error(`Unexpected transcript save: ${url}`),
          );
        }
        return Promise.resolve(
          jsonResponse({
            ...transcriptFixture("meeting-b", "Bravo", 8),
            rawText: "Bravo corrected transcript",
          }),
        );
      }
      if (url.endsWith("/meetings/meeting-b")) {
        return bravoMeetingLoad.promise;
      }
      if (url.includes("/meetings/meeting-a")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-a", "Alpha"));
      }
      if (url.includes("/meetings/meeting-b")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-b", "Bravo"));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-a", "Alpha"));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<MeetingDetail meetingId="meeting-a" />);
    expect(
      await screen.findByRole("heading", { name: "Alpha meeting" }),
    ).toBeVisible();
    expect(screen.getByText("Alpha participant")).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Alpha private transcript",
    );

    rerender(<MeetingDetail meetingId="meeting-b" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading meeting");
    expect(screen.queryByText("Alpha meeting")).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("Alpha private transcript"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save transcript" }),
    ).not.toBeInTheDocument();

    bravoMeetingLoad.resolve(
      jsonResponse(meetingFixture("meeting-b", "Bravo")),
    );
    expect(
      await screen.findByRole("heading", { name: "Bravo meeting" }),
    ).toBeVisible();
    expect(screen.getByText("Bravo participant")).toBeVisible();
    expect(screen.queryByText("Alpha participant")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Bravo private transcript",
    );
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Bravo corrected transcript" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save transcript" }));
    expect(await screen.findByRole("status")).toHaveTextContent("version 8");

    const patchCalls = fetchMock.mock.calls.filter(
      ([, init]) => init?.method === "PATCH",
    );
    expect(patchCalls).toHaveLength(1);
    expect(String(patchCalls[0]?.[0])).toContain(
      "/meetings/meeting-b/transcript",
    );
    expect(JSON.parse(String(patchCalls[0]?.[1]?.body))).toEqual({
      rawText: "Bravo corrected transcript",
      language: "en",
      version: 7,
    });

    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    expect(screen.getByRole("tabpanel", { name: "History" })).toHaveTextContent(
      "Bravo Private Field",
    );
    expect(
      screen.getByRole("tabpanel", { name: "History" }),
    ).not.toHaveTextContent("Alpha Private Field");
  });

  it("ignores a previous meeting save completion after navigation", async () => {
    const alphaSave = createDeferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        if (!url.endsWith("/meetings/meeting-a/transcript")) {
          return Promise.reject(
            new Error(`Unexpected transcript save: ${url}`),
          );
        }
        return alphaSave.promise;
      }
      if (url.includes("/meetings/meeting-a")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-a", "Alpha"));
      }
      if (url.includes("/meetings/meeting-b")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-b", "Bravo"));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(loadFixtureResponse(url, "meeting-a", "Alpha"));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<MeetingDetail meetingId="meeting-a" />);
    expect(
      await screen.findByRole("heading", { name: "Alpha meeting" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Alpha pending edit" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save transcript" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/meetings/meeting-a/transcript") &&
            init?.method === "PATCH",
        ),
      ).toBe(true),
    );

    rerender(<MeetingDetail meetingId="meeting-b" />);
    expect(
      await screen.findByRole("heading", { name: "Bravo meeting" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Transcript" }));
    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Bravo private transcript",
    );

    alphaSave.resolve(
      jsonResponse({
        ...transcriptFixture("meeting-a", "Alpha", 4),
        rawText: "Alpha pending edit",
      }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) =>
          String(url).endsWith("/meetings/meeting-a/history"),
        ),
      ).toHaveLength(2),
    );

    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Bravo private transcript",
    );
    expect(
      screen.queryByText(/Transcript saved as version 4/),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).includes("/meetings/meeting-b/") &&
          init?.method === "PATCH",
      ),
    ).toHaveLength(0);
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
