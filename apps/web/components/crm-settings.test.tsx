import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CRMSettings } from "@/components/crm-settings";

function response(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const availability = {
  moduleKey: "crm",
  state: "setup_required",
  enabled: true,
  canManage: true,
  mode: "unconfigured",
  externalProvider: null,
  externalConnected: false,
  customFieldsReadOnly: false,
  message: "Choose a system of record.",
};

describe("CRMSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requires confirmation before choosing native system-of-record mode", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT")
        return Promise.resolve(
          response({ ...availability, state: "available", mode: "native" }),
        );
      return Promise.resolve(
        response(String(input).includes("custom-fields") ? [] : availability),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CRMSettings />);

    const nativeButton = await screen.findByRole("button", {
      name: "Use RevenueOS as our CRM",
    });
    expect(nativeButton).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(nativeButton);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "PUT"),
      ).toBe(true),
    );
    expect(
      await screen.findByText(/now the native CRM system of record/i),
    ).toBeVisible();
  });

  it("creates a bounded custom field", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST")
        return Promise.resolve(
          response({
            id: "field-1",
            entityType: "account",
            label: "Customer tier",
          }),
        );
      return Promise.resolve(
        response(String(input).includes("custom-fields") ? [] : availability),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CRMSettings />);

    fireEvent.change(await screen.findByLabelText("Label"), {
      target: { value: "Customer tier" },
    });
    fireEvent.change(screen.getByLabelText("Field key"), {
      target: { value: "customer_tier" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create field" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
      ).toBe(true),
    );
    const post = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      entityType: "account",
      fieldKey: "customer_tier",
      fieldType: "short_text",
    });
  });
});
