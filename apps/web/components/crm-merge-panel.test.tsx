import type { CRMRecord } from "@revenueos/shared";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CRMMergePanel } from "@/components/crm-merge-panel";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

const record: CRMRecord = {
  entityType: "account",
  entityId: "00000000-0000-4000-8000-000000000001",
  title: "Duplicate account",
  ownerUserId: "00000000-0000-4000-8000-000000000010",
  ownerName: "Alex Morgan",
  archivedAt: null,
  recordUpdatedAt: "2026-09-01T00:00:00Z",
  mode: "native",
  crmEnabled: true,
  canManage: true,
  customFieldsReadOnly: false,
  fieldAuthority: {},
  coreFields: [],
  customFields: [],
  history: [],
  activity: [],
  mergedIntoEntityId: null,
  mergeId: null,
};

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("CRMMergePanel", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("crypto", {
      randomUUID: () => "00000000-0000-4000-8000-000000000099",
    });
  });

  it("previews conflicts and requires an irreversible confirmation", async () => {
    const onMerged = vi.fn().mockResolvedValue(undefined);
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          entityType: "account",
          sourceEntityId: record.entityId,
          survivorEntityId: "00000000-0000-4000-8000-000000000002",
          previewFingerprint: "a".repeat(64),
          conflicts: [
            {
              fieldKey: "name",
              sourceValue: "Duplicate",
              survivorValue: "Canonical",
              selected: "survivor",
            },
          ],
          blockedReasons: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          mergeId: "00000000-0000-4000-8000-000000000003",
          entityType: "account",
          sourceEntityId: record.entityId,
          survivorEntityId: "00000000-0000-4000-8000-000000000002",
          mergedAt: "2026-09-01T00:05:00Z",
          alreadyApplied: false,
        }),
      );
    render(<CRMMergePanel record={record} onMerged={onMerged} />);
    fireEvent.click(screen.getByText("Merge a duplicate"));
    fireEvent.change(screen.getByLabelText("Survivor Account ID"), {
      target: { value: "00000000-0000-4000-8000-000000000002" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview merge" }));
    expect(
      await screen.findByRole("heading", { name: "Merge impact" }),
    ).toBeVisible();
    expect(screen.getByText("Canonical")).toBeVisible();
    const mergeButton = screen.getByRole("button", {
      name: "Merge into survivor",
    });
    expect(mergeButton).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Source/u }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: /cannot be undone/u }),
    );
    fireEvent.click(mergeButton);
    await waitFor(() => expect(onMerged).toHaveBeenCalledOnce());
    const confirmBody = JSON.parse(
      String((fetchMock.mock.calls[1][1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(confirmBody.fieldSelection).toEqual({ name: "source" });
    expect(confirmBody.previewFingerprint).toBe("a".repeat(64));
  });
});
