import { describe, expect, it } from "vitest";
import {
  decodeProviderCalendarEventListResponse,
  decodeTenantPage,
  isCompanyResponse,
  isContactResponse,
  isInteractionResponse,
  isOpportunityListItemResponse,
  isOpportunityResponse,
  isProviderCalendarEventResponse,
} from "@/lib/private-response-identity";

const organisationId = "organisation-1";
const timestamps = {
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
};

const company = {
  id: "company-1",
  organisationId,
  name: "Northstar Facilities",
  website: "https://northstar.example.test",
  industry: "Facilities",
  location: "Sydney",
  employeeCount: 120,
  status: "prospect",
  ownerUserId: "user-1",
  archivedAt: null,
  ...timestamps,
};

const contact = {
  id: "contact-1",
  organisationId,
  companyId: company.id,
  firstName: "Jordan",
  lastName: "Lee",
  email: "jordan@example.test",
  phone: null,
  jobTitle: "Operations Director",
  linkedinUrl: null,
  status: "active",
  ownerUserId: "user-1",
  archivedAt: null,
  ...timestamps,
};

const opportunityBase = {
  id: "opportunity-1",
  organisationId,
  companyId: company.id,
  name: "Northstar renewal",
  stage: "proposal",
  status: "open",
  estimatedValue: "125000.50",
  currency: "AUD",
  expectedCloseDate: "2027-02-28",
  ownerUserId: "user-1",
  description: "Renewal and expansion",
  archivedAt: null,
  pipelineId: "pipeline-1",
  pipelineStageId: "pipeline-stage-1",
  stageEnteredAt: "2026-11-01T00:00:00Z",
  stageTrackingStartedAt: "2026-10-01T00:00:00Z",
  actualCloseDate: null,
  outcomeReason: null,
  outcomeProvenance: null,
  ...timestamps,
};

const opportunity = {
  ...opportunityBase,
  outcomeNote: null,
};

const opportunityListItem = {
  ...opportunityBase,
  companyName: company.name,
  ownerName: "Alex Morgan",
  latestMeetingId: null,
  latestMeetingDate: null,
  latestMeetingMomentum: null,
  latestNextBestAction: null,
};

const interaction = {
  id: "interaction-1",
  organisationId,
  companyId: company.id,
  opportunityId: null,
  contactId: contact.id,
  meetingId: null,
  eventId: null,
  interactionType: "online_meeting",
  lifecycleStatus: "planned",
  title: "Discovery",
  scheduledStartAt: "2026-11-02T00:00:00Z",
  scheduledEndAt: "2026-11-02T01:00:00Z",
  actualStartAt: null,
  actualEndAt: null,
  timezone: "Australia/Sydney",
  creationOrigin: "manual",
  callDirection: null,
  callOutcome: null,
  meetingPlatform: "zoom",
  meetingUrl: "https://zoom.example.test/meeting",
  externalMeetingId: "external-1",
  captureSource: "platform_transcript",
  ingestionState: "ready",
  durationSeconds: null,
  captureMethods: ["transcript"],
  intelligenceState: "ready",
  recordingAvailable: false,
  createdByUserId: "user-1",
  briefState: "completed",
  briefGeneratedAt: "2026-11-01T01:00:00Z",
  ...timestamps,
};

const calendarEvent = {
  id: "calendar-event-1",
  organisationId,
  title: "Discovery",
  startAt: "2026-11-02T00:00:00Z",
  endAt: "2026-11-02T01:00:00Z",
  providerTimezone: "Australia/Sydney",
  attendeeEmails: ["buyer@example.test"],
  location: null,
  onlineMeetingUrl: "https://meet.example.test/discovery",
  sensitivity: "normal",
  state: "active",
  matchState: "matched",
  contactId: contact.id,
  companyId: company.id,
  opportunityId: opportunity.id,
  interactionId: interaction.id,
  lastSyncedAt: "2026-11-01T01:00:00Z",
};

describe("private response identity decoders", () => {
  it("validates the complete Company response contract", () => {
    expect(isCompanyResponse(company, organisationId)).toBe(true);
    expect(
      isCompanyResponse({ ...company, createdAt: undefined }, organisationId),
    ).toBe(false);
    expect(
      isCompanyResponse({ ...company, status: "unknown" }, organisationId),
    ).toBe(false);
  });

  it("validates the complete Contact response contract", () => {
    expect(isContactResponse(contact, organisationId)).toBe(true);
    expect(
      isContactResponse({ ...contact, email: undefined }, organisationId),
    ).toBe(false);
    expect(
      isContactResponse({ ...contact, status: "unknown" }, organisationId),
    ).toBe(false);
  });

  it("validates the complete Interaction response contract", () => {
    expect(isInteractionResponse(interaction, organisationId)).toBe(true);
    expect(
      isInteractionResponse(
        { ...interaction, opportunityId: undefined },
        organisationId,
      ),
    ).toBe(false);
    expect(
      isInteractionResponse(
        { ...interaction, ingestionState: "unknown" },
        organisationId,
      ),
    ).toBe(false);
    expect(
      isInteractionResponse(
        { ...interaction, createdAt: "not-a-date" },
        organisationId,
      ),
    ).toBe(false);
  });

  it("validates the distinct complete Opportunity response contracts", () => {
    expect(isOpportunityResponse(opportunity, organisationId)).toBe(true);
    expect(
      isOpportunityResponse(
        { ...opportunity, organisationId: "organisation-2" },
        organisationId,
      ),
    ).toBe(false);
    expect(
      isOpportunityResponse(
        { ...opportunity, outcomeNote: undefined },
        organisationId,
      ),
    ).toBe(false);

    expect(
      isOpportunityListItemResponse(opportunityListItem, organisationId),
    ).toBe(true);
    expect(
      isOpportunityListItemResponse(
        { ...opportunityListItem, organisationId: "organisation-2" },
        organisationId,
      ),
    ).toBe(false);
    expect(
      isOpportunityListItemResponse(
        { ...opportunityListItem, latestMeetingMomentum: undefined },
        organisationId,
      ),
    ).toBe(false);
  });

  it("validates provider calendar events and list envelopes atomically", () => {
    expect(isProviderCalendarEventResponse(calendarEvent, organisationId)).toBe(
      true,
    );
    expect(
      isProviderCalendarEventResponse(
        { ...calendarEvent, organisationId: "organisation-2" },
        organisationId,
      ),
    ).toBe(false);
    expect(
      isProviderCalendarEventResponse(
        { ...calendarEvent, attendeeEmails: [null] },
        organisationId,
      ),
    ).toBe(false);

    const list = {
      organisationId,
      items: [calendarEvent],
      total: 1,
    };
    expect(
      decodeProviderCalendarEventListResponse(list, organisationId),
    ).toEqual(list);
    expect(
      decodeProviderCalendarEventListResponse(
        {
          ...list,
          items: [
            calendarEvent,
            {
              ...calendarEvent,
              id: "calendar-event-2",
              organisationId: "organisation-2",
            },
          ],
          total: 2,
        },
        organisationId,
      ),
    ).toBeNull();
    expect(
      decodeProviderCalendarEventListResponse(
        { ...list, organisationId: "organisation-2" },
        organisationId,
      ),
    ).toBeNull();
  });

  it("decodes Opportunity tenant pages atomically, including empty pages", () => {
    const page = {
      organisationId,
      items: [opportunityListItem],
      page: 1,
      pageSize: 10,
      total: 1,
      pages: 1,
    };
    expect(
      decodeTenantPage(page, organisationId, isOpportunityListItemResponse, {
        expectedPage: 1,
      }),
    ).toEqual(page);
    expect(
      decodeTenantPage(
        {
          ...page,
          items: [
            opportunityListItem,
            {
              ...opportunityListItem,
              id: "opportunity-2",
              organisationId: "organisation-2",
            },
          ],
          total: 2,
        },
        organisationId,
        isOpportunityListItemResponse,
        { expectedPage: 1 },
      ),
    ).toBeNull();

    const emptyPage = {
      organisationId,
      items: [],
      page: 1,
      pageSize: 10,
      total: 0,
      pages: 0,
    };
    expect(
      decodeTenantPage(
        emptyPage,
        organisationId,
        isOpportunityListItemResponse,
        { expectedPage: 1 },
      ),
    ).toEqual(emptyPage);
  });

  it("rejects a tenant page atomically when one complete item is invalid", () => {
    expect(
      decodeTenantPage(
        {
          organisationId,
          items: [company, { ...company, id: "company-2", updatedAt: null }],
          page: 1,
          pageSize: 10,
          total: 2,
          pages: 1,
        },
        organisationId,
        isCompanyResponse,
        { expectedPage: 1 },
      ),
    ).toBeNull();
  });

  it("accepts only page one when an empty tenant page has no pages", () => {
    const emptyPage = {
      organisationId,
      items: [],
      page: 1,
      pageSize: 10,
      total: 0,
      pages: 0,
    };

    expect(
      decodeTenantPage(emptyPage, organisationId, isCompanyResponse, {
        expectedPage: 1,
      }),
    ).toEqual(emptyPage);
    expect(
      decodeTenantPage(
        { ...emptyPage, page: 2 },
        organisationId,
        isCompanyResponse,
        { expectedPage: 2 },
      ),
    ).toBeNull();
  });
});
