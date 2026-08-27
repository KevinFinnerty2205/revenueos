import { expect, test, type Page } from "@playwright/test";

const eventId = "event-security-expo";
let imported = false;
let met = false;

function salesEvent() {
  return {
    id: eventId,
    name: "Security Expo Australia",
    eventType: "trade_show",
    startAt: "2026-08-27T00:00:00Z",
    endAt: "2026-08-28T07:00:00Z",
    timezone: "Australia/Sydney",
    locationName: "ICC Sydney",
    city: "Sydney",
    country: "Australia",
    eventUrl: null,
    organiser: null,
    description: null,
    goalType: "meet_new_prospects",
    goalDetail: null,
    sourceType: "manual",
    state: "active",
    ownerUserId: "user-1",
    readOnly: false,
    prospectEnrichmentAvailable: true,
    summary: {
      attendeesImported: imported ? 1 : 0,
      priorityPeople: imported ? 1 : 0,
      planned: 0,
      met: met ? 1 : 0,
      followUp: 0,
      addedToSales: imported ? 1 : 0,
      interactionsCaptured: 0,
      activeOpportunityContacts: imported ? 1 : 0,
    },
    campaigns: [],
    createdAt: "2026-08-27T00:00:00Z",
    updatedAt: "2026-08-27T00:00:00Z",
  };
}

function jane() {
  return {
    id: "attendee-jane",
    eventId,
    firstName: "Jane",
    lastName: "Smith",
    displayName: "Jane Smith",
    companyName: "Northstar Systems",
    jobTitle: "Chief Information Officer",
    businessEmail: "jane@northstar.example",
    emailTrustState: "provider_supplied",
    permissionStatus: "not_assessed",
    countryOrLocation: "Australia",
    profileUrl: "https://profiles.example.test/jane",
    companyDomain: "northstar.example",
    registrationCategory: "Delegate",
    matchState: "matched_contact",
    priorityState: "priority_to_meet",
    priorityReasons: [
      "Active Opportunity relationship.",
      "Senior technology role is relevant to the Event goal.",
    ],
    contactId: "contact-jane",
    companyId: "company-northstar",
    prospectPersonId: "person-jane",
    activeOpportunityId: "opportunity-northstar",
    planState: met ? "met" : "not_planned",
    meetingArranged: false,
    plannedByTeammateCount: 0,
    encounterId: met ? "encounter-jane" : null,
    interactionId: null,
    sellerNote: met ? "Discussed a technical workshop next week." : null,
    canResearch: true,
    createdAt: "2026-08-27T00:00:00Z",
  };
}

async function capture(page: Page, name: string) {
  if (process.env.WO031_SCREENSHOTS !== "1") return;
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({
    path: `../../docs/07-sprints/images/wo-031/${name}.png`,
    fullPage: true,
  });
}

test.beforeEach(() => {
  imported = false;
  met = false;
});

test("creates an Event, imports an authorised list and captures a truthful mobile encounter", async ({
  page,
}) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/beta/capabilities")
      return route.fulfill({
        json: { featureFlags: { engageEvents: true } },
      });
    if (path === "/api/v1/prospect/availability")
      return route.fulfill({
        json: {
          moduleKey: "prospect",
          state: "available",
          enabled: true,
          canManage: true,
          message: "Available",
        },
      });
    if (path === "/api/v1/engage/availability")
      return route.fulfill({
        json: {
          moduleKey: "engage",
          state: "available",
          enabled: true,
          canManage: true,
          message: "Available",
        },
      });
    if (path === "/api/v1/engage/events" && request.method() === "GET")
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          canCreate: true,
          readOnly: false,
          maxActiveEvents: 50,
        },
      });
    if (path === "/api/v1/engage/events" && request.method() === "POST") {
      expect(request.postDataJSON()).toMatchObject({
        name: "Security Expo Australia",
        eventType: "trade_show",
        locationName: "ICC Sydney",
        goalType: "meet_new_prospects",
      });
      return route.fulfill({ status: 201, json: salesEvent() });
    }
    if (path === `/api/v1/engage/events/${eventId}`)
      return route.fulfill({ json: salesEvent() });
    if (path === `/api/v1/engage/events/${eventId}/attendees`)
      return route.fulfill({
        json: {
          items: imported ? [jane()] : [],
          total: imported ? 1 : 0,
          page: 1,
          pageSize: 100,
        },
      });
    if (path.endsWith("/attendee-imports/preview")) {
      const body = request.postDataJSON() as { fileName: string };
      expect(body.fileName).toBe("security-expo.csv");
      return route.fulfill({
        json: {
          id: "import-security",
          eventId,
          fileName: body.fileName,
          fileSizeBytes: 160,
          rowCount: 1,
          validRowCount: 1,
          recognised: [
            {
              sourceColumn: "First Name",
              mappedField: "first_name",
              reason: null,
            },
            {
              sourceColumn: "Last Name",
              mappedField: "last_name",
              reason: null,
            },
            {
              sourceColumn: "Company",
              mappedField: "company_name",
              reason: null,
            },
            {
              sourceColumn: "Job Title",
              mappedField: "job_title",
              reason: null,
            },
            {
              sourceColumn: "Business Email",
              mappedField: "business_email",
              reason: null,
            },
          ],
          ignored: [
            {
              sourceColumn: "Dietary Requirements",
              mappedField: null,
              reason: "Sensitive or private registration data is not accepted.",
            },
          ],
          issues: [],
          previewRows: [
            {
              sourceRow: 2,
              firstName: "Jane",
              lastName: "Smith",
              companyName: "Northstar Systems",
              jobTitle: "Chief Information Officer",
              businessEmail: "jane@northstar.example",
            },
          ],
          expiresAt: "2026-08-27T12:00:00Z",
          alreadyImported: false,
          authorityStatement:
            "I confirm my organisation is authorised to use this attendee information for this business purpose.",
          permissionNotice:
            "Being listed as an event attendee does not automatically make a person eligible for outreach.",
        },
      });
    }
    if (path.endsWith("/attendee-imports/import-security/confirm")) {
      expect(request.postDataJSON()).toEqual({
        confirmed: true,
        authorityAttested: true,
        attestationVersion: 1,
      });
      imported = true;
      return route.fulfill({
        json: {
          id: "import-security",
          eventId,
          importedCount: 1,
          duplicateCount: 0,
          status: "confirmed",
        },
      });
    }
    if (path.endsWith("/attendee-jane/encounter")) {
      const body = request.postDataJSON() as {
        state: string;
        sellerNote: string;
        createInteraction: boolean;
      };
      expect(body).toEqual({
        state: "met",
        sellerNote: "Discussed a technical workshop next week.",
        createInteraction: false,
      });
      met = true;
      return route.fulfill({ json: jane() });
    }
    return route.fulfill({
      status: 404,
      json: {
        code: "not_mocked",
        message: `Not mocked: ${path}`,
        requestId: "e2e",
      },
    });
  });

  await page.goto("/events");
  await expect(
    page.getByRole("heading", { name: "Get more from the events you attend" }),
  ).toBeVisible();
  await capture(page, "events-first-use-desktop");
  await page.getByRole("link", { name: "Create Event" }).first().click();
  await page.getByLabel("Event name").fill("Security Expo Australia");
  await page.getByLabel("Event type").selectOption("trade_show");
  await page.getByLabel("Venue").fill("ICC Sydney");
  await page.getByRole("button", { name: "Create Event" }).click();
  await expect(
    page.getByRole("heading", { name: "Security Expo Australia" }),
  ).toBeVisible();
  await page.getByLabel("Choose CSV").setInputFiles({
    name: "security-expo.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "First Name,Last Name,Company,Job Title,Business Email,Dietary Requirements\nJane,Smith,Northstar Systems,Chief Information Officer,jane@northstar.example,None\n",
    ),
  });
  await expect(page.getByText("Dietary Requirements")).toBeVisible();
  await expect(page.getByText(/does not automatically make/u)).toBeVisible();
  await page.getByLabel(/Authority confirmation/u).check();
  await page.getByRole("button", { name: "Confirm authorised import" }).click();
  await page.getByRole("tab", { name: "People" }).click();
  await expect(page.getByRole("heading", { name: "Jane Smith" })).toBeVisible();
  await expect(
    page.getByText("Active Opportunity", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Email provider supplied/iu)).toBeVisible();
  await capture(page, "event-people-desktop");

  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByLabel(/Quick seller note/u)
    .fill("Discussed a technical workshop next week.");
  await page.getByRole("button", { name: "Mark met" }).click();
  await expect(
    page.getByText(/no Evidence or Interaction was created/u),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await capture(page, "event-day-mobile-met");
});
