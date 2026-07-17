import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MeetingForm } from "@/components/meeting-form";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const emptyPage = {
  items: [],
  page: 1,
  pageSize: 100,
  total: 0,
  pages: 0,
};

describe("MeetingForm", () => {
  afterEach(() => {
    router.push.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates a meeting with a participant and supplied transcript", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "meeting-1" }, 201));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(
          jsonResponse({
            ...emptyPage,
            items: [{ id: "company-1", name: "Acme Australia" }],
            total: 1,
            pages: 1,
          }),
        );
      }
      return Promise.resolve(jsonResponse(emptyPage));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm />);
    expect(
      await screen.findByRole("heading", { name: "Create meeting" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Acme discovery" },
    });
    fireEvent.change(screen.getByLabelText(/meeting date/i), {
      target: { value: "2026-08-01T10:00" },
    });
    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "company-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add participant" }));
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Jordan Lee" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "jordan@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Jordan confirmed the next discussion." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create meeting" }));

    await waitFor(() => expect(router.push).toHaveBeenCalled());
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/meetings") && init?.method === "POST",
    );
    expect(createCall).toBeDefined();
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: "Acme discovery",
      companyId: "company-1",
      participants: [
        {
          displayName: "Jordan Lee",
          email: "jordan@example.com",
        },
      ],
      transcript: {
        rawText: "Jordan confirmed the next discussion.",
        language: "en",
        source: "manual",
      },
    });
    expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1");
  });

  it("loads and updates all meeting aggregate fields", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method) {
        if (url.endsWith("/transcript")) {
          return Promise.resolve(
            jsonResponse({ id: "transcript-1", version: 2 }),
          );
        }
        return Promise.resolve(jsonResponse({ id: "meeting-1" }));
      }
      if (url.includes("/companies")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "participant-1",
              contactId: null,
              displayName: "Jordan Lee",
              email: "jordan@example.com",
              attendanceStatus: "invited",
              role: "attendee",
            },
          ]),
        );
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            rawText: "Original text.",
            language: "en",
            version: 1,
            source: "manual",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          id: "meeting-1",
          title: "Original meeting",
          description: "Original description",
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm meetingId="meeting-1" />);
    expect(await screen.findByDisplayValue("Original meeting")).toBeVisible();
    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Updated meeting" },
    });
    fireEvent.change(screen.getByLabelText("Attendance"), {
      target: { value: "attended" },
    });
    fireEvent.change(screen.getByLabelText("Transcript text"), {
      target: { value: "Corrected text." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1"),
    );
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/meetings/meeting-1") &&
          init?.method === "PATCH",
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/participants/participant-1") &&
          init?.method === "PATCH",
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/transcript") && init?.method === "PATCH",
      ),
    ).toBe(true);
  });

  it("does not audit or version unchanged participants and transcript", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method) {
        return Promise.resolve(jsonResponse({ id: "meeting-1" }));
      }
      if (url.includes("/companies") || url.includes("/contacts?")) {
        return Promise.resolve(jsonResponse(emptyPage));
      }
      if (url.endsWith("/participants")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "participant-1",
              contactId: null,
              displayName: "Jordan Lee",
              email: "jordan@example.com",
              attendanceStatus: "attended",
              role: "attendee",
            },
          ]),
        );
      }
      if (url.endsWith("/transcript")) {
        return Promise.resolve(
          jsonResponse({
            id: "transcript-1",
            rawText: "Original text.",
            language: "en",
            version: 1,
            source: "manual",
          }),
        );
      }
      return Promise.resolve(
        jsonResponse({
          id: "meeting-1",
          title: "Original meeting",
          description: null,
          meetingDate: "2026-08-01T00:00:00Z",
          meetingType: "remote",
          status: "scheduled",
          companyId: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm meetingId="meeting-1" />);
    fireEvent.change(await screen.findByDisplayValue("Original meeting"), {
      target: { value: "Updated title only" },
    });
    expect(screen.getByLabelText("Transcript text")).toHaveValue(
      "Original text.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save meeting" }));

    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/meetings/meeting-1"),
    );
    const mutationCalls = fetchMock.mock.calls.filter(([, init]) =>
      Boolean(init?.method),
    );
    expect(
      mutationCalls.map(([url, init]) => [
        String(url).replace("http://localhost:8000", ""),
        init?.method,
      ]),
    ).toEqual([["/api/v1/meetings/meeting-1", "PATCH"]]);
  });

  it("shows participant validation without sending a mutation", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(emptyPage)));
    vi.stubGlobal("fetch", fetchMock);

    render(<MeetingForm />);
    fireEvent.change(await screen.findByLabelText(/title/i), {
      target: { value: "Discovery" },
    });
    fireEvent.change(screen.getByLabelText(/meeting date/i), {
      target: { value: "2026-08-01T10:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add participant" }));
    fireEvent.click(screen.getByRole("button", { name: "Create meeting" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Each participant needs",
    );
    expect(router.push).not.toHaveBeenCalled();
  });
});
