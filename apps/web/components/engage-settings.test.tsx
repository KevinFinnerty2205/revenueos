import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { EngageSettings } from "@/components/engage-settings";

function response(payload: object) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const availability = {
  moduleKey: "engage",
  state: "available",
  enabled: true,
  canManage: true,
  message: "Engage is available.",
};

const policy = {
  configured: true,
  outboundEnabled: true,
  providerSuppliedEmailAllowed: true,
  cooldownHours: 72,
  maxDailySendsUser: 25,
  maxDailySendsOrg: 100,
  requireOptOutMechanism: false,
  offeringName: "Multi-site Access Management",
  valueProposition: "Coordinate secure access across locations.",
  approvedCta: "Would a short conversation next week be useful?",
  canManage: true,
  complianceNotice:
    "RevenueOS provides configurable product controls, not legal advice.",
};

afterEach(() => vi.restoreAllMocks());

it("saves approved seller context and conservative outreach controls", async () => {
  const requests: Array<{ url: string; body: string | null }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    requests.push({
      url,
      body: typeof init?.body === "string" ? init.body : null,
    });
    if (url.endsWith("/api/v1/engage/availability"))
      return response(availability);
    if (url.endsWith("/api/v1/engage/policy") && init?.method === "PUT")
      return response(policy);
    if (url.endsWith("/api/v1/engage/policy")) return response(policy);
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<EngageSettings />);
  expect(
    await screen.findByDisplayValue("Multi-site Access Management"),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Contact cooldown (hours)"), {
    target: { value: "96" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save Engage policy" }));
  expect(
    await screen.findByText("Engage policy and approved seller context saved."),
  ).toBeInTheDocument();
  await waitFor(() => {
    const saved = requests.find((item) =>
      item.body?.includes('"cooldownHours":96'),
    );
    expect(saved).toBeDefined();
  });
  expect(
    screen.getByText(
      /Production Gmail and Microsoft mailbox adapters are not enabled/u,
    ),
  ).toBeInTheDocument();
});
