import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CRMRecordPanel } from "@/components/crm-record-panel";

function response(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const record = {
  entityType: "account",
  entityId: "account-1",
  title: "Acme Australia",
  ownerUserId: "user-1",
  ownerName: "Alex Morgan",
  archivedAt: null,
  recordUpdatedAt: "2026-08-29T10:00:00Z",
  mode: "native",
  crmEnabled: true,
  canManage: true,
  customFieldsReadOnly: false,
  fieldAuthority: {},
  coreFields: [
    {
      key: "industry",
      label: "Industry",
      value: "Software",
      authority: "revenueos_authoritative",
    },
  ],
  customFields: [
    {
      definition: {
        id: "field-1",
        entityType: "account",
        fieldKey: "customer_tier",
        label: "Customer tier",
        fieldType: "single_select",
        options: ["Strategic", "Growth"],
        active: true,
        displayOrder: 0,
        createdByUserId: "user-1",
        archivedAt: null,
        createdAt: "2026-08-29T09:00:00Z",
        updatedAt: "2026-08-29T09:00:00Z",
      },
      value: "Strategic",
      source: "manual_user_entry",
      changedByUserId: "user-1",
      updatedAt: "2026-08-29T10:00:00Z",
      editable: true,
    },
  ],
  history: [
    {
      id: "change-1",
      fieldKey: "customer_tier",
      oldValue: "Growth",
      newValue: "Strategic",
      source: "manual_user_entry",
      changedByUserId: "user-1",
      changedByName: "Alex Morgan",
      changedAt: "2026-08-29T10:00:00Z",
    },
    {
      id: "change-2",
      fieldKey: "owner_user_id",
      oldValue: null,
      newValue: "user-1",
      source: "manual_user_entry",
      changedByUserId: "user-1",
      changedByName: "Alex Morgan",
      changedAt: "2026-08-29T09:55:00Z",
    },
  ],
  activity: [
    {
      id: "interaction:1",
      activityType: "interaction",
      title: "Discovery workshop",
      detail: "Completed",
      occurredAt: "2026-08-28T10:00:00Z",
      href: "/interactions/interaction-1",
      sourceLabel: "Interaction",
    },
  ],
};

describe("CRMRecordPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows ownership, custom fields, history and bounded relationship activity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(record)));
    render(<CRMRecordPanel entityType="account" entityId="account-1" />);

    expect(
      await screen.findByRole("heading", { name: "Acme Australia" }),
    ).toBeVisible();
    expect(screen.getByText(/Owned by Alex Morgan/)).toBeVisible();
    expect(screen.getByText("Software")).toBeVisible();
    fireEvent.click(screen.getByText("CRM details"));
    fireEvent.click(screen.getByText("Record history"));
    expect(screen.getByLabelText("Customer tier")).toHaveValue("Strategic");
    expect(
      screen.getByRole("link", { name: "Discovery workshop" }),
    ).toHaveAttribute("href", "/interactions/interaction-1");
    expect(screen.getByText(/Growth → Strategic/)).toBeVisible();
    expect(screen.getByText("Owner")).toBeVisible();
    expect(screen.getByText(/Unassigned → Alex Morgan/)).toBeVisible();
    expect(screen.queryByText("user-1")).not.toBeInTheDocument();
  });

  it("saves a typed custom field with optimistic concurrency", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(record))
      .mockResolvedValueOnce(response(record.customFields[0]))
      .mockResolvedValueOnce(
        response({ ...record, recordUpdatedAt: "2026-08-29T10:01:00Z" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<CRMRecordPanel entityType="account" entityId="account-1" />);

    fireEvent.click(await screen.findByText("CRM details"));
    fireEvent.change(await screen.findByLabelText("Customer tier"), {
      target: { value: "Growth" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save field" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "PUT" });
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      value: "Growth",
      expectedRecordUpdatedAt: "2026-08-29T10:00:00Z",
    });
  });

  it("clears a boolean custom field back to not set", async () => {
    const booleanRecord = {
      ...record,
      customFields: [
        {
          ...record.customFields[0],
          definition: {
            ...record.customFields[0].definition,
            id: "field-boolean",
            fieldKey: "priority_account",
            label: "Priority account",
            fieldType: "boolean",
            options: [],
          },
          value: true,
        },
      ],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(booleanRecord))
      .mockResolvedValueOnce(response(booleanRecord.customFields[0]))
      .mockResolvedValueOnce(response(booleanRecord));
    vi.stubGlobal("fetch", fetchMock);
    render(<CRMRecordPanel entityType="account" entityId="account-1" />);

    fireEvent.click(await screen.findByText("CRM details"));
    fireEvent.change(await screen.findByLabelText("Priority account"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save field" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      value: null,
    });
  });
});
