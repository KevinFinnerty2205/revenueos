import { expect, test, type Page } from "@playwright/test";

const accountId = "account-native-crm";
const fieldId = "field-segment";

async function routeShell(page: Page, role: "admin" | "member" = "admin") {
  await page.route("http://localhost:8000/api/v1/me", async (route) => {
    await route.fulfill({
      json: {
        user: {
          id: "user-1",
          externalAuthId: "user_dev_001",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "organisation-1",
          name: "Synthetic Revenue Team",
          slug: "synthetic-revenue-team",
        },
        role,
        authMode: "mock",
        requestId: "request-native-crm-e2e",
      },
    });
  });
  await page.route(
    "http://localhost:8000/api/v1/beta/capabilities",
    async (route) => {
      await route.fulfill({
        json: {
          featureFlags: { revenueBrain: false },
          noticeVersion: 1,
          maxTranscriptCharacters: 200000,
        },
      });
    },
  );
}

test("admin deliberately selects RevenueOS as the CRM system of record", async ({
  page,
}) => {
  await routeShell(page);
  let mode: "unconfigured" | "native" = "unconfigured";

  await page.route(
    "http://localhost:8000/api/v1/crm/availability",
    async (route) => {
      await route.fulfill({
        json: {
          moduleKey: "crm",
          state: mode === "native" ? "available" : "setup_required",
          enabled: true,
          canManage: true,
          mode,
          externalProvider: null,
          externalConnected: false,
          customFieldsReadOnly: false,
          message:
            mode === "native"
              ? "CRM administration is available."
              : "Choose RevenueOS or an external CRM as the system of record.",
        },
      });
    },
  );
  await page.route(
    "http://localhost:8000/api/v1/crm/custom-fields",
    async (route) => route.fulfill({ json: [] }),
  );
  await page.route(
    "http://localhost:8000/api/v1/crm/settings",
    async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        mode: "native",
        confirmed: true,
      });
      mode = "native";
      await route.fulfill({
        json: {
          moduleKey: "crm",
          state: "available",
          enabled: true,
          canManage: true,
          mode,
          externalProvider: null,
          externalConnected: false,
          customFieldsReadOnly: false,
          message: "CRM administration is available.",
        },
      });
    },
  );

  await page.goto("/settings");
  const nativeButton = page.getByRole("button", {
    name: "Use RevenueOS as our CRM",
  });
  await expect(nativeButton).toBeDisabled();
  await page
    .getByLabel(/changing the system of record affects which mapped fields/i)
    .check();
  await nativeButton.click();
  await expect(
    page.getByText(/now the native CRM system of record/i),
  ).toBeVisible();
});

test("member can review a simple mobile account, edit a custom field and inspect history", async ({
  page,
}) => {
  await routeShell(page, "member");
  let segment = "Mid-market";
  let updatedAt = "2026-08-29T10:00:00Z";

  const record = () => ({
    entityType: "account",
    entityId: accountId,
    title: "Northstar Facilities Group",
    ownerUserId: "user-1",
    ownerName: "Alex Morgan",
    archivedAt: null,
    recordUpdatedAt: updatedAt,
    mode: "native",
    crmEnabled: true,
    canManage: false,
    customFieldsReadOnly: false,
    fieldAuthority: {},
    coreFields: [
      {
        key: "industry",
        label: "Industry",
        value: "Facilities management",
        authority: "revenueos_authoritative",
      },
      {
        key: "location",
        label: "Location",
        value: "Sydney, NSW",
        authority: "revenueos_authoritative",
      },
    ],
    customFields: [
      {
        definition: {
          id: fieldId,
          entityType: "account",
          fieldKey: "segment",
          label: "Segment",
          fieldType: "single_select",
          options: ["Enterprise", "Mid-market"],
          active: true,
          displayOrder: 0,
          createdByUserId: "user-1",
          archivedAt: null,
          createdAt: "2026-08-29T09:00:00Z",
          updatedAt,
        },
        value: segment,
        source: "manual_user_entry",
        changedByUserId: "user-1",
        updatedAt,
        editable: true,
      },
    ],
    history: [
      {
        id: "change-owner",
        fieldKey: "owner_user_id",
        oldValue: null,
        newValue: "user-1",
        source: "manual_user_entry",
        changedByUserId: "user-1",
        changedByName: "Alex Morgan",
        changedAt: "2026-08-29T09:00:00Z",
      },
      {
        id: "change-segment",
        fieldKey: "custom.segment",
        oldValue: "Mid-market",
        newValue: segment,
        source: "manual_user_entry",
        changedByUserId: "user-1",
        changedByName: "Alex Morgan",
        changedAt: updatedAt,
      },
    ],
    activity: [
      {
        id: "interaction-1",
        activityType: "interaction",
        title: "Discovery with Jane Smith",
        detail: "Completed",
        occurredAt: "2026-08-28T04:00:00Z",
        href: "/interactions/interaction-1",
        sourceLabel: "Interaction",
      },
    ],
  });

  await page.route(
    `http://localhost:8000/api/v1/crm/records/account/${accountId}`,
    async (route) => route.fulfill({ json: record() }),
  );
  await page.route(
    `http://localhost:8000/api/v1/crm/records/account/${accountId}/custom-fields/${fieldId}`,
    async (route) => {
      const body = route.request().postDataJSON() as {
        value: string;
        expectedRecordUpdatedAt: string;
      };
      expect(body).toEqual({
        value: "Enterprise",
        expectedRecordUpdatedAt: updatedAt,
      });
      segment = body.value;
      updatedAt = "2026-08-29T10:01:00Z";
      await route.fulfill({ json: record().customFields[0] });
    },
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/companies/${accountId}`);
  await expect(
    page.getByRole("heading", { name: "Northstar Facilities Group" }),
  ).toBeVisible();
  await expect(page.getByText(/Owned by Alex Morgan/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Archive" })).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Discovery with Jane Smith" }),
  ).toBeVisible();
  await expect(page.getByLabel("Segment")).not.toBeVisible();

  await page.getByText("CRM details").click();
  await page.getByLabel("Segment").selectOption("Enterprise");
  await page.getByRole("button", { name: "Save field" }).click();
  await expect(page.getByLabel("Segment")).toHaveValue("Enterprise");

  await page.getByText("Record history").click();
  await expect(page.getByText("Owner")).toBeVisible();
  await expect(page.getByText(/Unassigned → Alex Morgan/)).toBeVisible();
  await expect(page.getByText("user-1")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
