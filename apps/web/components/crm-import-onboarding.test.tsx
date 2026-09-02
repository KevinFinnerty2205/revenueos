import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CRMImportOnboarding } from "@/components/crm-import-onboarding";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("CRMImportOnboarding", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/crm/availability"))
        return Promise.resolve(
          jsonResponse({
            enabled: true,
            canManage: true,
            mode: "native",
            state: "available",
          }),
        );
      if (url.endsWith("/crm/members"))
        return Promise.resolve(
          jsonResponse([
            {
              userId: "00000000-0000-4000-8000-000000000001",
              displayName: "Alex Morgan",
              active: true,
            },
          ]),
        );
      if (url.endsWith("/crm/custom-fields"))
        return Promise.resolve(jsonResponse([]));
      if (url.endsWith("/pipelines"))
        return Promise.resolve(
          jsonResponse([
            {
              id: "00000000-0000-4000-8000-000000000010",
              name: "Sales",
              active: true,
              isDefault: true,
              stages: [],
            },
          ]),
        );
      if (url.endsWith("/crm/imports/preview"))
        return Promise.resolve(
          jsonResponse({
            batchId: "00000000-0000-4000-8000-000000000020",
            entityType: "account",
            state: "previewed",
            expiresAt: "2026-09-01T01:00:00Z",
            rowCount: 1,
            actionableRowCount: 1,
            importedRowCount: 0,
            rows: [
              {
                sourceRow: 2,
                disposition: "new",
                issueCode: null,
                canonicalEntityId: null,
              },
            ],
            permissionToContactInferred: false,
            rawFileRetained: false,
          }),
        );
      if (url.endsWith("/crm/imports/confirm"))
        return Promise.resolve(
          jsonResponse({
            batchId: "00000000-0000-4000-8000-000000000020",
            entityType: "account",
            state: "confirmed",
            expiresAt: "2026-09-01T01:00:00Z",
            rowCount: 1,
            actionableRowCount: 1,
            importedRowCount: 1,
            rows: [
              {
                sourceRow: 2,
                disposition: "imported",
                issueCode: null,
                canonicalEntityId: "00000000-0000-4000-8000-000000000030",
              },
            ],
            permissionToContactInferred: false,
            rawFileRetained: false,
          }),
        );
      throw new Error(`Unexpected request: ${url}`);
    });
  });

  it("requires explicit mapping, previews without mutation and confirms reviewed new rows", async () => {
    render(<CRMImportOnboarding />);
    expect(
      await screen.findByRole("heading", { name: "Import CRM data" }),
    ).toBeVisible();
    const bytes = new TextEncoder().encode(
      "Name,Notes\r\nAcme,private note\r\n",
    );
    const file = {
      name: "accounts.csv",
      size: bytes.byteLength,
      arrayBuffer: async () => bytes.buffer,
    };
    fireEvent.change(screen.getByLabelText(/UTF-8 CSV/u), {
      target: { files: [file] },
    });
    const nameMapping = await screen.findByLabelText("Name");
    const notesMapping = screen.getByLabelText("Notes");
    expect(
      screen.getByRole("button", { name: "Preview import" }),
    ).toBeDisabled();
    fireEvent.change(nameMapping, { target: { value: "name" } });
    fireEvent.change(notesMapping, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));

    expect(
      await screen.findByRole("heading", { name: "Import preview" }),
    ).toBeVisible();
    expect(
      screen.getByText(/RevenueOS has not changed CRM records/u),
    ).toBeVisible();
    const previewCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/crm/imports/preview"),
    );
    const previewBody = JSON.parse(
      String((previewCall?.[1] as RequestInit | undefined)?.body),
    ) as Record<string, unknown>;
    expect(previewBody.columnMapping).toEqual({ Name: "name", Notes: null });
    expect(previewBody.defaultOwnerUserId).toBe(
      "00000000-0000-4000-8000-000000000001",
    );

    const review = screen.getByRole("checkbox", {
      name: /Import only the 1 rows marked new/u,
    });
    fireEvent.click(review);
    fireEvent.click(
      screen.getByRole("button", { name: "Import 1 new records" }),
    );
    expect(await screen.findByText(/1 Account record imported/u)).toBeVisible();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/crm/imports/confirm"),
        ),
      ).toBe(true),
    );
    expect(
      screen.getByText(/Import confirmed · 1 records created/u),
    ).toBeVisible();
    expect(screen.getByText("Imported records")).toBeVisible();
  });
});
