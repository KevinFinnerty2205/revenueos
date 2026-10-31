import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationDeliveryPreferences } from "@/components/conversation-delivery-preferences";

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const preferences = {
  exists: true,
  lockVersion: 2,
  timezone: "Australia/Sydney",
  morningDigestEnabled: true,
  morningDigestTime: "07:15",
  preMeetingEnabled: true,
  preMeetingMinutes: 45,
  importedFromBrowserAt: null,
  updatedAt: "2026-10-31T00:00:00Z",
};

describe("ConversationDeliveryPreferences", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("persists versioned preferences and previews the exact local-outbox content", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(preferences))
      .mockResolvedValueOnce(response({ ...preferences, lockVersion: 3 }))
      .mockResolvedValueOnce(
        response({
          id: "outbox-1",
          kind: "morning_digest",
          status: "prepared",
          subject: "Your Oryntela briefing for 2026-10-31",
          bodyText:
            "Good morning, Kevin.\n\nToday’s conversations\n- Synthetic review",
          href: "/",
          preparedForAt: "2026-10-30T20:15:00Z",
          duplicateSuppressed: false,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationDeliveryPreferences />);

    expect(await screen.findByDisplayValue("Australia/Sydney")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Briefing lead time (minutes)"), {
      target: { value: "60" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    expect(
      await screen.findByText(/Preferences saved privately/i),
    ).toBeVisible();
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      expectedLockVersion: 2,
      preMeetingMinutes: 60,
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Preview morning digest" }),
    );
    expect(
      await screen.findByText("Your Oryntela briefing for 2026-10-31"),
    ).toBeVisible();
    expect(screen.getByText(/Today’s conversations/)).toBeVisible();
    expect(screen.getByText(/Nothing was sent/i)).toBeVisible();
  });

  it("does not allow an edit to race and be overwritten by the initial preference load", async () => {
    let resolveInitial!: (value: Response) => void;
    const initialResponse = new Promise<Response>((resolve) => {
      resolveInitial = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(initialResponse)
      .mockResolvedValueOnce(
        response({
          ...preferences,
          lockVersion: 1,
          preMeetingMinutes: 75,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationDeliveryPreferences />);

    const leadTime = screen.getByLabelText("Briefing lead time (minutes)");
    expect(leadTime).toBeDisabled();
    resolveInitial(response({ ...preferences, lockVersion: 0 }));
    await waitFor(() => expect(leadTime).toBeEnabled());

    fireEvent.change(leadTime, { target: { value: "75" } });
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      expectedLockVersion: 0,
      preMeetingMinutes: 75,
    });
  });

  it("imports earlier browser preferences only after an explicit owner action", async () => {
    window.localStorage.setItem(
      "revenueos:conversation-delivery-preferences",
      JSON.stringify({ preMeetingMinutes: 90, morningDigestTime: "08:30" }),
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(preferences))
      .mockResolvedValueOnce(
        response({
          ...preferences,
          lockVersion: 3,
          preMeetingMinutes: 90,
          morningDigestTime: "08:30",
          importedFromBrowserAt: "2026-10-31T01:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationDeliveryPreferences />);

    const importButton = await screen.findByRole("button", {
      name: "Import browser preferences",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(importButton);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      expectedLockVersion: 2,
      preMeetingMinutes: 90,
      morningDigestTime: "08:30",
      importFromBrowser: true,
    });
    expect(
      window.localStorage.getItem(
        "revenueos:conversation-delivery-preferences",
      ),
    ).toBeNull();
  });
});
