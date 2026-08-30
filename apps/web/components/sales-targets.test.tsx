import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SalesTargets } from "@/components/sales-targets";

const currentUserId = "22222222-2222-4222-8222-222222222222";
const targetId = "33333333-3333-4333-8333-333333333333";
const pipelineId = "44444444-4444-4444-8444-444444444444";

const wonValueMetric = {
  metricId: "won_value",
  definitionVersion: "1",
  label: "Won value",
  description: "Sum of valued opportunities currently won in the period.",
  unit: "currency",
  category: "outcome",
  allowedScopes: ["personal", "organisation"],
  requiresCurrency: true,
  displayOrder: 1,
  dateSemantics: "Current close date falls in the inclusive local-date range.",
  exclusions: ["Unvalued won opportunities"],
};

const meetingsMetric = {
  metricId: "meetings_completed_count",
  definitionVersion: "1",
  label: "Completed meetings",
  description: "Count of canonical completed meeting interactions.",
  unit: "count",
  category: "activity",
  allowedScopes: ["personal", "organisation"],
  requiresCurrency: false,
  displayOrder: 4,
  dateSemantics: "Completion time falls in the inclusive local-date range.",
  exclusions: ["Cancelled meetings"],
};

const metadata = {
  currentUserId,
  currentUserRole: "admin",
  organisationTimezone: "Australia/Sydney",
  metrics: [wonValueMetric, meetingsMetric],
  owners: [
    { userId: currentUserId, displayName: "Kevin Admin" },
    {
      userId: "55555555-5555-4555-8555-555555555555",
      displayName: "Alex Seller",
    },
  ],
  pipelines: [{ id: pipelineId, name: "New business", active: true }],
  canAssignPersonalTargets: true,
  canCreateOrganisationTargets: true,
};

const revision = {
  id: "66666666-6666-4666-8666-666666666666",
  revisionNumber: 1,
  goalValue: "20000.00",
  createdByUserId: currentUserId,
  createdByDisplayName: "Kevin Admin",
  createdAt: "2026-08-01T00:00:00Z",
};

const target = {
  id: targetId,
  metric: wonValueMetric,
  scope: "personal",
  origin: "self_set",
  ownerUserId: currentUserId,
  ownerDisplayName: "Kevin Admin",
  pipelineId,
  pipelineName: "New business",
  periodType: "month",
  periodStart: "2026-08-01",
  periodEnd: "2026-08-31",
  periodLabel: "August 2026",
  timezone: "Australia/Sydney",
  currency: "AUD",
  status: "active",
  latestRevision: revision,
  revisions: [revision],
  progress: {
    state: "available",
    actualValue: "22500.00",
    targetValue: "20000.00",
    remainingValue: "0.00",
    aboveTargetValue: "2500.00",
    percentageComplete: "112.5",
    targetReached: true,
    calculatedThrough: "2026-08-30",
    generatedAt: "2026-08-30T03:00:00Z",
    disclosures: [
      "Actuals use canonical records through 30 August 2026.",
      "This is an operational goal, not a forecast or compensation measure.",
    ],
  },
  createdByUserId: currentUserId,
  createdByDisplayName: "Kevin Admin",
  archivedAt: null,
  createdAt: "2026-08-01T00:00:00Z",
  updatedAt: "2026-08-01T00:00:00Z",
  canRevise: true,
  canArchive: true,
};

function json(payload: object, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("sales targets", () => {
  it("shows exact progress above 100%, calculation detail and revision history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.includes("/metadata")) return json(metadata);
        if (url.endsWith(`/${targetId}`)) return json(target);
        return json({
          items: [target],
          canAssignPersonalTargets: true,
          canCreateOrganisationTargets: true,
          maximumVisibleTargets: 200,
        });
      }),
    );

    render(<SalesTargets />);

    expect(await screen.findByText("112.5%")).toBeVisible();
    expect(screen.getByText(/\$22,500\.00/)).toBeVisible();
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "100");
    expect(progress).toHaveAccessibleName(/112\.5% complete/i);

    fireEvent.click(screen.getByRole("button", { name: "View details" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "How this is calculated",
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "not a forecast or compensation measure",
    );
    expect(
      screen.getByRole("link", { name: "View this metric in Insights" }),
    ).toHaveAttribute(
      "href",
      expect.stringMatching(
        /tab=overview.*metric=won_value.*timezone=Australia%2FSydney.*pipelineId=.*ownerUserId=/u,
      ),
    );
    expect(screen.getByText(/revision 1/)).toBeVisible();
  });

  it("creates an organisation target without accepting an actual value", async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/metadata")) return json(metadata);
        if (init?.method === "POST") {
          requests.push(init);
          return json(target, 201);
        }
        return json({
          items: [],
          canAssignPersonalTargets: true,
          canCreateOrganisationTargets: true,
          maximumVisibleTargets: 200,
        });
      }),
    );

    render(<SalesTargets />);
    fireEvent.click(await screen.findByRole("button", { name: "Set target" }));
    const form = screen
      .getByRole("heading", { name: "Set target" })
      .closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(screen.getByLabelText("Who is this for?"), {
      target: { value: "organisation" },
    });
    fireEvent.change(screen.getByLabelText("Goal"), {
      target: { value: "25000" },
    });
    fireEvent.click(
      within(form as HTMLFormElement).getByRole("button", {
        name: "Set target",
      }),
    );

    await waitFor(() => expect(requests).toHaveLength(1));
    const body = JSON.parse(String(requests[0]?.body)) as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      metricId: "won_value",
      metricDefinitionVersion: "1",
      scope: "organisation",
      origin: "admin_assigned",
      ownerUserId: null,
      goalValue: "25000",
      currency: "AUD",
    });
    expect(body).not.toHaveProperty("actualValue");
    expect(
      await screen.findByText(
        /actual progress is calculated from Sales Analytics/i,
      ),
    ).toBeVisible();
  });

  it("offers Pipeline binding only for Opportunity metrics", async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/metadata")) return json(metadata);
        if (init?.method === "POST") {
          requests.push(init);
          return json(target, 201);
        }
        return json({
          items: [],
          canAssignPersonalTargets: true,
          canCreateOrganisationTargets: true,
          maximumVisibleTargets: 200,
        });
      }),
    );

    render(<SalesTargets />);
    fireEvent.click(await screen.findByRole("button", { name: "Set target" }));
    expect(screen.getByLabelText(/Pipeline/u)).toBeVisible();
    fireEvent.change(screen.getByLabelText("What do you want to achieve?"), {
      target: { value: "meetings_completed_count" },
    });
    expect(screen.queryByLabelText(/Pipeline/u)).not.toBeInTheDocument();
    expect(
      screen.getByText(/more activity does not by itself mean better/u),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Goal"), {
      target: { value: "8" },
    });
    const form = screen
      .getByRole("heading", { name: "Set target" })
      .closest("form");
    fireEvent.click(
      within(form as HTMLFormElement).getByRole("button", {
        name: "Set target",
      }),
    );

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(JSON.parse(String(requests[0]?.body))).toMatchObject({
      metricId: "meetings_completed_count",
      pipelineId: null,
      currency: null,
    });
  });

  it("requires confirmation and preserves the earlier value when revising", async () => {
    const requests: RequestInit[] = [];
    const revisedTarget = {
      ...target,
      latestRevision: { ...revision, revisionNumber: 2, goalValue: "30000.00" },
      revisions: [
        {
          ...revision,
          id: "77777777-7777-4777-8777-777777777777",
          revisionNumber: 2,
          goalValue: "30000.00",
        },
        revision,
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/metadata")) return json(metadata);
        if (url.includes("/revisions") && init?.method === "POST") {
          requests.push(init);
          return json(revisedTarget, 201);
        }
        return json({
          items: [target],
          canAssignPersonalTargets: true,
          canCreateOrganisationTargets: true,
          maximumVisibleTargets: 200,
        });
      }),
    );

    render(<SalesTargets />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Change target" }),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "The earlier target of $20,000.00 will remain in history",
    );
    fireEvent.change(screen.getByLabelText("New target"), {
      target: { value: "30000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm change" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(JSON.parse(String(requests[0]?.body))).toEqual({
      goalValue: "30000",
      expectedRevisionNumber: 1,
    });
    expect(
      await screen.findByText(/previous value remains in history/i),
    ).toBeVisible();
  });
});
