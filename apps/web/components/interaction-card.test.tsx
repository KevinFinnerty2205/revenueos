import type { Interaction } from "@revenueos/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InteractionCard } from "@/components/interaction-card";

const interaction: Interaction = {
  id: "../settings",
  organisationId: "organisation-1",
  companyId: "company-1",
  opportunityId: null,
  contactId: null,
  meetingId: null,
  interactionType: "workshop",
  lifecycleStatus: "planned",
  title: "Encoded interaction",
  scheduledStartAt: "2026-11-02T00:00:00Z",
  scheduledEndAt: null,
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  durationSeconds: null,
  captureMethods: [],
  intelligenceState: "not_ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "not_generated",
  briefGeneratedAt: null,
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
};

describe("InteractionCard", () => {
  it("encodes the response ID in every interaction route", () => {
    render(<InteractionCard interaction={interaction} />);

    expect(
      screen.getByRole("link", { name: "Encoded interaction" }),
    ).toHaveAttribute("href", "/conversations/..%2Fsettings");
    expect(
      screen.getByRole("link", { name: "Open live workspace" }),
    ).toHaveAttribute("href", "/conversations/..%2Fsettings?view=capture");
    expect(screen.getByRole("link", { name: "Prepare brief" })).toHaveAttribute(
      "href",
      "/conversations/..%2Fsettings#preparation",
    );
  });
});
