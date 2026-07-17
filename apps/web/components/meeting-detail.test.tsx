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
    expect(screen.getByRole("tab", { name: "Transcript" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Transcript" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
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
