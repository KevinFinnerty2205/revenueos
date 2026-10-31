import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BetaAdmin } from "@/components/beta-admin";
import { apiBlob, apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiBlob: vi.fn(), apiRequest: vi.fn() }));
const mockedApiRequest = vi.mocked(apiRequest);
const mockedApiBlob = vi.mocked(apiBlob);

const overview = {
  organisation: { id: "org-1", name: "Example Team", slug: "example" },
  members: [
    {
      user: {
        id: "user-1",
        displayName: "Alex Admin",
        email: "alex@example.test",
      },
      role: "admin",
      status: "active",
      joinedAt: "2026-01-01T00:00:00Z",
    },
    {
      user: {
        id: "user-2",
        displayName: "Taylor Seller",
        email: "taylor@example.test",
      },
      role: "member",
      status: "active",
      joinedAt: "2026-01-02T00:00:00Z",
    },
  ],
  retention: { policy: "days_90", defaultApplied: true },
  noticeVersion: 1,
  acknowledgementCount: 2,
  activeMemberCount: 2,
  featureFlags: {
    integrations: false,
    dataExport: false,
    organisationDeletion: false,
  },
  usage: {
    date: "2026-10-24",
    generations: 0,
    generationLimit: 10,
    providerRequests: 0,
    providerRequestLimit: 10,
    estimatedCostAvailable: false,
  },
  recentEvents: [],
  dataRequests: [],
} as const;

describe("BetaAdmin", () => {
  afterEach(() => {
    mockedApiRequest.mockReset();
    mockedApiBlob.mockReset();
    vi.restoreAllMocks();
  });

  it("does not offer the signed-in administrator a self-disable action", async () => {
    mockedApiRequest.mockResolvedValueOnce(overview);

    render(<BetaAdmin currentUserId="user-1" />);

    const currentMember = (await screen.findByText("Alex Admin")).closest("li");
    expect(currentMember).not.toBeNull();
    expect(within(currentMember!).getByText("Current user")).toBeVisible();
    expect(
      within(currentMember!).queryByRole("button", {
        name: "Disable Alex Admin",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Disable Taylor Seller" }),
    ).toBeVisible();
  });

  it("shows readable capabilities and downloads an available export with authenticated API access", async () => {
    const downloadOverview = {
      ...overview,
      featureFlags: {
        ...overview.featureFlags,
        salesforceCrm: false,
        futureSafeCapability: true,
      },
      dataRequests: [
        {
          id: "export-1",
          requestType: "export" as const,
          status: "completed",
          requestedAt: "2026-10-24T00:00:00Z",
          completedAt: "2026-10-24T00:01:00Z",
          expiresAt: "2026-10-25T00:01:00Z",
          downloadAvailable: true,
          failureCode: null,
        },
      ],
    };
    mockedApiRequest.mockResolvedValueOnce(downloadOverview);
    mockedApiBlob.mockResolvedValueOnce(
      new Blob(["{}"], { type: "application/json" }),
    );
    const createObjectURL = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:owner-export");
    const revokeObjectURL = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    render(<BetaAdmin currentUserId="user-1" />);

    const diagnosticsSummary = await screen.findByText("Technical diagnostics");
    const diagnostics = diagnosticsSummary.closest("details");
    expect(diagnostics).not.toHaveAttribute("open");
    fireEvent.click(diagnosticsSummary.closest("summary")!);
    expect(diagnostics).toHaveAttribute("open");
    expect(await screen.findByText("Salesforce CRM sync")).toBeVisible();
    expect(screen.getByText("Future Safe Capability")).toBeVisible();
    expect(
      screen.queryByText("Unrecognised capability"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download export" }));

    await waitFor(() =>
      expect(mockedApiBlob).toHaveBeenCalledWith(
        "/api/v1/beta/admin/exports/export-1/download",
      ),
    );
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:owner-export");
  });
});
