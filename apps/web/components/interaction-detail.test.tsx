import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InteractionDetail } from "@/components/interaction-detail";

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const interaction = {
  id: "interaction-1",
  organisationId: "organisation-1",
  companyId: null,
  opportunityId: null,
  meetingId: "meeting-1",
  interactionType: "online_meeting",
  lifecycleStatus: "planned",
  title: "Acme discovery",
  scheduledStartAt: "2026-08-01T00:00:00Z",
  scheduledEndAt: null,
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "meeting_compatibility",
  createdByUserId: "user-1",
  createdAt: "2026-07-26T00:00:00Z",
  updatedAt: "2026-07-26T00:00:00Z",
};

describe("InteractionDetail", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("completes a planned interaction and keeps Meeting Intelligence available", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          init?.method === "POST"
            ? {
                ...interaction,
                lifecycleStatus: "completed",
                actualEndAt: "2026-08-01T01:00:00Z",
              }
            : interaction,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<InteractionDetail interactionId="interaction-1" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading interaction");
    expect(
      await screen.findByRole("heading", { name: "Acme discovery" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open Meeting Intelligence" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    fireEvent.click(
      screen.getByRole("button", { name: "Complete interaction" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Complete interaction" }),
      ).not.toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/interactions/interaction-1/complete"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("renders a safe error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              code: "interaction_not_found",
              message: "Interaction not found.",
              requestId: "request-3",
            },
            404,
          ),
        ),
      ),
    );

    render(<InteractionDetail interactionId="missing" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Interaction not found.",
    );
  });
});
