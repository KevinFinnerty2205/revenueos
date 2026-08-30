import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PipelineSettings } from "@/components/pipeline-settings";

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const availability = {
  moduleKey: "crm",
  state: "available",
  enabled: true,
  canManage: true,
  mode: "native",
  externalProvider: null,
  externalConnected: false,
  customFieldsReadOnly: false,
  message: "RevenueOS CRM is ready.",
};

const pipeline = {
  id: "pipeline-1",
  name: "RevenueOS Sales Pipeline",
  isDefault: true,
  active: true,
  archivedAt: null,
  createdAt: "2026-08-30T00:00:00Z",
  updatedAt: "2026-08-30T00:00:00Z",
  stages: [
    {
      id: "stage-open",
      pipelineId: "pipeline-1",
      key: "discovery",
      name: "Discovery",
      position: 0,
      stageType: "open",
      guidance: null,
      active: true,
      archivedAt: null,
      currentOpportunityCount: 1,
    },
    {
      id: "stage-won",
      pipelineId: "pipeline-1",
      key: "closed_won",
      name: "Closed Won",
      position: 1,
      stageType: "won",
      guidance: null,
      active: true,
      archivedAt: null,
      currentOpportunityCount: 0,
    },
    {
      id: "stage-lost",
      pipelineId: "pipeline-1",
      key: "closed_lost",
      name: "Closed Lost",
      position: 2,
      stageType: "lost",
      guidance: null,
      active: true,
      archivedAt: null,
      currentOpportunityCount: 0,
    },
  ],
};

describe("PipelineSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows bounded native configuration and creates a pipeline", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST")
        return Promise.resolve(response(pipeline, 201));
      if (url.endsWith("/crm/availability"))
        return Promise.resolve(response(availability));
      return Promise.resolve(response([pipeline]));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PipelineSettings />);

    expect(
      await screen.findByRole("heading", { name: "Pipelines" }),
    ).toBeVisible();
    expect(screen.getByDisplayValue("Discovery")).toBeVisible();
    expect(screen.getByText("1 current opportunities")).toBeVisible();
    fireEvent.change(screen.getAllByLabelText("Stage guidance (optional)")[0], {
      target: { value: "Confirm the customer need." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "PATCH"),
      ).toBe(true),
    );
    const guidanceCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "PATCH",
    );
    expect(JSON.parse(String(guidanceCall?.[1]?.body))).toMatchObject({
      name: "Discovery",
      guidance: "Confirm the customer need.",
    });
    fireEvent.change(screen.getByLabelText("Pipeline name"), {
      target: { value: "Enterprise sales" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create pipeline" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
      ).toBe(true),
    );
    const createCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      name: "Enterprise sales",
      isDefault: false,
    });
  });

  it("explains that externally managed pipeline definitions are read-only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          response(
            String(input).endsWith("/crm/availability")
              ? {
                  ...availability,
                  mode: "external",
                  externalProvider: "hubspot",
                }
              : [pipeline],
          ),
        ),
      ),
    );
    render(<PipelineSettings />);

    expect(
      await screen.findByText(/Pipeline stages are managed in HubSpot/),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Create pipeline" }),
    ).not.toBeInTheDocument();
  });

  it("keeps native definition administration hidden from members", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          response(
            String(input).endsWith("/crm/availability")
              ? { ...availability, canManage: false }
              : [pipeline],
          ),
        ),
      ),
    );
    render(<PipelineSettings />);

    expect(
      await screen.findByText(
        "An organisation administrator manages native pipeline definitions.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Create pipeline" }),
    ).not.toBeInTheDocument();
  });
});
