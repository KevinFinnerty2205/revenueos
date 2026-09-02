import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

const sourceId = "00000000-0000-4000-8000-000000000101";
const survivorId = "00000000-0000-4000-8000-000000000102";
const pipelineId = "00000000-0000-4000-8000-000000000110";
const stageId = "00000000-0000-4000-8000-000000000111";

async function routeIdentity(page: Page) {
  await page.route("**/api/v1/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "00000000-0000-4000-8000-000000000001",
          externalAuthId: "user_wo039c_admin",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "00000000-0000-4000-8000-000000000002",
          name: "Synthetic Design Partner",
          slug: "synthetic-design-partner",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-wo039c-e2e",
      },
    }),
  );
  await page.route("**/api/v1/beta/capabilities", (route) =>
    route.fulfill({
      json: {
        featureFlags: { nativeCrm: true, nativePipeline: true },
        noticeVersion: 1,
        maxTranscriptCharacters: 200000,
      },
    }),
  );
}

function unavailable(route: Route) {
  return route.fulfill({
    status: 404,
    json: {
      code: "not_available_in_synthetic_route",
      message: "This setting is not part of this synthetic browser proof.",
      requestId: "request-wo039c-fallback",
    },
  });
}

async function mapColumn(panel: Locator, header: string, target: string) {
  await panel
    .locator("label")
    .filter({ hasText: new RegExp(`^${header}`, "u") })
    .locator("select")
    .selectOption(target);
}

test("admin previews and confirms an explicit-map Account import", async ({
  page,
}) => {
  await page.route("**/api/v1/**", unavailable);
  await routeIdentity(page);
  await page.route("**/api/v1/crm/availability", (route) =>
    route.fulfill({
      json: {
        moduleKey: "crm",
        state: "available",
        enabled: true,
        canManage: true,
        mode: "native",
        externalProvider: null,
        externalConnected: false,
        customFieldsReadOnly: false,
        message: "CRM administration is available.",
      },
    }),
  );
  await page.route("**/api/v1/crm/members", (route) =>
    route.fulfill({
      json: [
        {
          userId: "00000000-0000-4000-8000-000000000001",
          displayName: "Alex Morgan",
          active: true,
        },
      ],
    }),
  );
  await page.route("**/api/v1/crm/custom-fields", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/pipelines", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/crm/imports/preview", async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      entityType: "account",
      columnMapping: { Name: "name", Notes: null },
      defaultOwnerUserId: "00000000-0000-4000-8000-000000000001",
    });
    await route.fulfill({
      json: {
        batchId: "00000000-0000-4000-8000-000000000020",
        entityType: "account",
        state: "previewed",
        expiresAt: "2026-09-01T03:00:00Z",
        rowCount: 2,
        actionableRowCount: 1,
        importedRowCount: 0,
        rows: [
          {
            sourceRow: 2,
            disposition: "new",
            issueCode: null,
            canonicalEntityId: null,
          },
          {
            sourceRow: 3,
            disposition: "possible_duplicate",
            issueCode: "possible_account_name_duplicate",
            canonicalEntityId: null,
          },
        ],
        permissionToContactInferred: false,
        rawFileRetained: false,
      },
    });
  });
  await page.route("**/api/v1/crm/imports/confirm", (route) =>
    route.fulfill({
      json: {
        batchId: "00000000-0000-4000-8000-000000000020",
        entityType: "account",
        state: "confirmed",
        expiresAt: "2026-09-01T03:00:00Z",
        rowCount: 2,
        actionableRowCount: 1,
        importedRowCount: 1,
        rows: [
          {
            sourceRow: 2,
            disposition: "imported",
            issueCode: null,
            canonicalEntityId: "00000000-0000-4000-8000-000000000030",
          },
          {
            sourceRow: 3,
            disposition: "possible_duplicate",
            issueCode: "possible_account_name_duplicate",
            canonicalEntityId: null,
          },
        ],
        permissionToContactInferred: false,
        rawFileRetained: false,
      },
    }),
  );

  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "Import CRM data" }),
  ).toBeVisible();
  await page.getByLabel(/UTF-8 CSV/u).setInputFiles({
    name: "synthetic-accounts.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Name,Notes\r\nHarbour Labs,plain text\r\nHarbour Labs,review\r\n",
    ),
  });
  const importPanel = page.locator(
    'section[aria-labelledby="crm-import-title"]',
  );
  await mapColumn(importPanel, "Name", "name");
  await mapColumn(importPanel, "Notes", "");
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(
    page.getByText(/RevenueOS has not changed CRM records/u),
  ).toBeVisible();
  await expect(
    page.getByText("Possible duplicates", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Raw file retained/u)).toHaveCount(0);
  await importPanel.screenshot({
    path: "../../docs/07-sprints/assets/wo-039c/crm-import-preview-desktop.png",
  });
  await page
    .getByRole("checkbox", { name: /Import only the 1 rows marked new/u })
    .check();
  await page.getByRole("button", { name: "Import 1 new records" }).click();
  await expect(page.getByText(/1 Account record imported/u)).toBeVisible();
  await importPanel.screenshot({
    path: "../../docs/07-sprints/assets/wo-039c/crm-import-confirmed-desktop.png",
  });
});

test("admin imports Contacts and open Opportunities with explicit relationship maps", async ({
  page,
}) => {
  await page.route("**/api/v1/**", unavailable);
  await routeIdentity(page);
  await page.route("**/api/v1/crm/availability", (route) =>
    route.fulfill({
      json: {
        moduleKey: "crm",
        state: "available",
        enabled: true,
        canManage: true,
        mode: "native",
        externalProvider: null,
        externalConnected: false,
        customFieldsReadOnly: false,
        message: "CRM administration is available.",
      },
    }),
  );
  await page.route("**/api/v1/crm/members", (route) =>
    route.fulfill({
      json: [
        {
          userId: "00000000-0000-4000-8000-000000000001",
          displayName: "Alex Morgan",
          active: true,
        },
      ],
    }),
  );
  await page.route("**/api/v1/crm/custom-fields", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/pipelines", (route) =>
    route.fulfill({
      json: [
        {
          id: pipelineId,
          name: "Sales",
          active: true,
          isDefault: true,
          stages: [
            {
              id: stageId,
              name: "Discovery",
              stageType: "open",
              active: true,
              position: 1,
            },
          ],
        },
      ],
    }),
  );
  await page.route("**/api/v1/crm/imports/preview", async (route) => {
    const body = route.request().postDataJSON() as {
      entityType: "contact" | "opportunity";
      columnMapping: Record<string, string | null>;
      pipelineId: string | null;
      stageValueMapping: Record<string, string>;
    };
    if (body.entityType === "contact") {
      expect(body.columnMapping).toEqual({
        Account: "account_domain",
        DNC: "do_not_contact",
        Email: "email",
        First: "first_name",
        Last: "last_name",
      });
    } else {
      expect(body.pipelineId).toBe(pipelineId);
      expect(body.stageValueMapping).toEqual({ Discovery: stageId });
    }
    await route.fulfill({
      json: {
        batchId:
          body.entityType === "contact"
            ? "00000000-0000-4000-8000-000000000120"
            : "00000000-0000-4000-8000-000000000121",
        entityType: body.entityType,
        state: "previewed",
        expiresAt: "2026-09-01T23:00:00Z",
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
      },
    });
  });
  await page.route("**/api/v1/crm/imports/confirm", async (route) => {
    const body = route.request().postDataJSON() as {
      entityType: "contact" | "opportunity";
    };
    await route.fulfill({
      json: {
        batchId:
          body.entityType === "contact"
            ? "00000000-0000-4000-8000-000000000120"
            : "00000000-0000-4000-8000-000000000121",
        entityType: body.entityType,
        state: "confirmed",
        expiresAt: "2026-09-01T23:00:00Z",
        rowCount: 1,
        actionableRowCount: 1,
        importedRowCount: 1,
        rows: [
          {
            sourceRow: 2,
            disposition: "imported",
            issueCode: null,
            canonicalEntityId:
              body.entityType === "contact"
                ? "00000000-0000-4000-8000-000000000130"
                : "00000000-0000-4000-8000-000000000131",
          },
        ],
        permissionToContactInferred: false,
        rawFileRetained: false,
      },
    });
  });

  await page.goto("/settings");
  const importPanel = page.locator(
    'section[aria-labelledby="crm-import-title"]',
  );
  await importPanel.getByLabel("Record type").selectOption("contact");
  await importPanel.getByLabel(/UTF-8 CSV/u).setInputFiles({
    name: "synthetic-contacts.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "First,Last,Email,Account,DNC\r\nCasey,Ng,casey@example.test,harbour.example.test,yes\r\n",
    ),
  });
  await mapColumn(importPanel, "First", "first_name");
  await mapColumn(importPanel, "Last", "last_name");
  await mapColumn(importPanel, "Email", "email");
  await mapColumn(importPanel, "Account", "account_domain");
  await mapColumn(importPanel, "DNC", "do_not_contact");
  await importPanel.getByRole("button", { name: "Preview import" }).click();
  await expect(
    importPanel.getByText(/Permission to contact is never inferred/u),
  ).toBeVisible();
  await importPanel.getByRole("checkbox", { name: /Import only/u }).check();
  await importPanel
    .getByRole("button", { name: "Import 1 new records" })
    .click();
  await expect(
    importPanel.getByText(/1 Contact record imported/u),
  ).toBeVisible();

  await importPanel.getByLabel("Record type").selectOption("opportunity");
  await importPanel.getByLabel(/UTF-8 CSV/u).setInputFiles({
    name: "synthetic-opportunities.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Name,Account,Stage,Value,Currency\r\nHarbour expansion,harbour.example.test,Discovery,12000,AUD\r\n",
    ),
  });
  await mapColumn(importPanel, "Name", "name");
  await mapColumn(importPanel, "Account", "account_domain");
  await mapColumn(importPanel, "Stage", "stage");
  await mapColumn(importPanel, "Value", "estimated_value");
  await mapColumn(importPanel, "Currency", "currency");
  await importPanel
    .locator("fieldset")
    .filter({ hasText: "Open stage values" })
    .locator("label")
    .filter({ hasText: /^Discovery/u })
    .locator("select")
    .selectOption(stageId);
  await importPanel.getByRole("button", { name: "Preview import" }).click();
  await importPanel.getByRole("checkbox", { name: /Import only/u }).check();
  await importPanel
    .getByRole("button", { name: "Import 1 new records" })
    .click();
  await expect(
    importPanel.getByText(/1 Opportunity record imported/u),
  ).toBeVisible();
});

test("admin explicitly merges an Account and the source becomes a tombstone", async ({
  page,
}) => {
  await page.route("**/api/v1/**", unavailable);
  await routeIdentity(page);
  let merged = false;
  const record = () => ({
    entityType: "account",
    entityId: sourceId,
    title: "Harbour Labs duplicate",
    ownerUserId: "00000000-0000-4000-8000-000000000001",
    ownerName: "Alex Morgan",
    archivedAt: merged ? "2026-09-01T02:00:00Z" : null,
    recordUpdatedAt: "2026-09-01T02:00:00Z",
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
    customFields: [],
    history: [],
    activity: [],
    mergedIntoEntityId: merged ? survivorId : null,
    mergeId: merged ? "00000000-0000-4000-8000-000000000103" : null,
  });
  await page.route(`**/api/v1/crm/records/account/${sourceId}`, (route) =>
    route.fulfill({ json: record() }),
  );
  await page.route("**/api/v1/crm/merges/preview", (route) =>
    route.fulfill({
      json: {
        entityType: "account",
        sourceEntityId: sourceId,
        survivorEntityId: survivorId,
        previewFingerprint: "a".repeat(64),
        conflicts: [
          {
            fieldKey: "industry",
            sourceValue: "Software",
            survivorValue: "Business software",
            selected: "survivor",
          },
        ],
        blockedReasons: [],
      },
    }),
  );
  await page.route("**/api/v1/crm/merges/confirm", async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      entityType: "account",
      sourceEntityId: sourceId,
      survivorEntityId: survivorId,
      fieldSelection: { industry: "survivor" },
    });
    merged = true;
    await route.fulfill({
      json: {
        mergeId: "00000000-0000-4000-8000-000000000103",
        entityType: "account",
        sourceEntityId: sourceId,
        survivorEntityId: survivorId,
        mergedAt: "2026-09-01T02:00:00Z",
        alreadyApplied: false,
      },
    });
  });

  await page.goto(`/companies/${sourceId}`);
  await page.getByText("Merge a duplicate").click();
  await page.getByLabel("Survivor Account ID").fill(survivorId);
  await page.getByRole("button", { name: "Preview merge" }).click();
  await expect(
    page.getByRole("heading", { name: "Merge impact" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Suppression remains restrictive/u),
  ).toBeVisible();
  await page
    .locator("details")
    .filter({ hasText: "Merge a duplicate" })
    .screenshot({
      path: "../../docs/07-sprints/assets/wo-039c/crm-merge-preview-desktop.png",
    });
  await page.getByRole("checkbox", { name: /cannot be undone/u }).check();
  await page.getByRole("button", { name: "Merge into survivor" }).click();
  await expect(
    page.getByText(/retained as a read-only tombstone/u),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "surviving record" }),
  ).toHaveAttribute("href", `/companies/${survivorId}`);
  await expect(page.getByText("Merge a duplicate")).toHaveCount(0);
  await page.locator('section[aria-labelledby="crm-record-title"]').screenshot({
    path: "../../docs/07-sprints/assets/wo-039c/crm-merged-tombstone-desktop.png",
  });
});
