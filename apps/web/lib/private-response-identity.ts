import type {
  Company,
  Contact,
  Interaction,
  Opportunity,
  OpportunityListItem,
  ProviderCalendarEvent,
  ProviderCalendarEventListResponse,
  TenantEntityPage,
} from "@revenueos/shared";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value);
}

function isNullableDecimalString(value: unknown): value is string | null {
  return value === null || (isString(value) && /^\d+(?:\.\d+)?$/.test(value));
}

function isNullableSafeInteger(value: unknown): value is number | null {
  return (
    value === null ||
    (Number.isSafeInteger(value) &&
      (value as number) >= 0 &&
      (value as number) <= 2_147_483_647)
  );
}

function isDate(value: unknown): value is string {
  return isString(value) && !Number.isNaN(Date.parse(value));
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isDate(value);
}

function isOptionalNullableString(value: unknown): boolean {
  return value === undefined || isNullableString(value);
}

function isOptionalNullableAllowed(
  value: unknown,
  allowed: ReadonlySet<string>,
): boolean {
  return value === undefined || value === null || isAllowed(value, allowed);
}

function isAllowed(value: unknown, allowed: ReadonlySet<string>): boolean {
  return typeof value === "string" && allowed.has(value);
}

const interactionTypes = new Set([
  "online_meeting",
  "face_to_face_meeting",
  "presentation",
  "workshop",
  "site_visit",
  "executive_lunch",
  "phone_call",
  "conference_interaction",
  "trade_show_interaction",
  "manual_interaction",
]);
const companyStatuses = new Set(["prospect", "active", "inactive"]);
const contactStatuses = new Set(["active", "left_company"]);
const opportunityStages = new Set([
  "qualification",
  "discovery",
  "evaluation",
  "proposal",
  "negotiation",
  "procurement",
  "closed_won",
  "closed_lost",
  "other",
]);
const opportunityStatuses = new Set(["open", "won", "lost", "on_hold"]);
const interactionStatuses = new Set([
  "planned",
  "in_progress",
  "completed",
  "cancelled",
]);
const interactionCreationOrigins = new Set([
  "manual",
  "meeting_compatibility",
  "imported_external",
]);
const callDirections = new Set(["inbound", "outbound", "unknown"]);
const callOutcomes = new Set([
  "connected",
  "no_answer",
  "voicemail",
  "cancelled",
]);
const captureMethods = new Set([
  "debrief",
  "voice_journal",
  "recording",
  "transcript",
]);
const intelligenceStates = new Set([
  "not_ready",
  "processing",
  "review_required",
  "ready",
  "not_applicable",
]);
const briefStates = new Set(["unavailable", "not_generated", "completed"]);
const onlineMeetingPlatforms = new Set([
  "microsoft_teams",
  "zoom",
  "google_meet",
  "other",
]);
const onlineMeetingCaptureSources = new Set([
  "platform_recording",
  "platform_transcript",
  "user_uploaded_recording",
  "user_uploaded_transcript",
  "native_integration",
  "meeting_bot",
  "ai_debrief",
  "voice_journal",
  "manual_notes",
]);
const onlineMeetingIngestionStates = new Set([
  "not_started",
  "uploading",
  "processing",
  "ready",
  "failed",
]);
const providerCalendarEventStates = new Set(["active", "cancelled", "deleted"]);
const providerCalendarMatchStates = new Set([
  "unmatched",
  "matched",
  "review_required",
  "internal",
  "private",
]);

function hasTenantIdentity(
  value: Record<string, unknown>,
  organisationId: string,
): boolean {
  return isNonEmptyString(value.id) && value.organisationId === organisationId;
}

export function isCompanyResponse(
  value: unknown,
  organisationId: string,
): value is Company {
  return (
    isRecord(value) &&
    hasTenantIdentity(value, organisationId) &&
    isString(value.name) &&
    isNullableString(value.website) &&
    isNullableString(value.industry) &&
    isNullableString(value.location) &&
    isNullableSafeInteger(value.employeeCount) &&
    isAllowed(value.status, companyStatuses) &&
    isNonEmptyString(value.ownerUserId) &&
    isNullableDate(value.archivedAt) &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt)
  );
}

export function isContactResponse(
  value: unknown,
  organisationId: string,
): value is Contact {
  return (
    isRecord(value) &&
    hasTenantIdentity(value, organisationId) &&
    isString(value.companyId) &&
    isString(value.firstName) &&
    isString(value.lastName) &&
    isNullableString(value.email) &&
    isNullableString(value.phone) &&
    isNullableString(value.jobTitle) &&
    isNullableString(value.linkedinUrl) &&
    isAllowed(value.status, contactStatuses) &&
    isNonEmptyString(value.ownerUserId) &&
    isNullableDate(value.archivedAt) &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt)
  );
}

function hasOpportunityResponseFields(
  value: Record<string, unknown>,
  organisationId: string,
): boolean {
  return (
    hasTenantIdentity(value, organisationId) &&
    isNullableString(value.companyId) &&
    isString(value.name) &&
    isAllowed(value.stage, opportunityStages) &&
    isAllowed(value.status, opportunityStatuses) &&
    isNullableDecimalString(value.estimatedValue) &&
    isNullableString(value.currency) &&
    isNullableDate(value.expectedCloseDate) &&
    isNonEmptyString(value.ownerUserId) &&
    isNullableString(value.description) &&
    isNullableDate(value.archivedAt) &&
    isNullableString(value.pipelineId) &&
    isNullableString(value.pipelineStageId) &&
    isNullableDate(value.stageEnteredAt) &&
    isNullableDate(value.stageTrackingStartedAt) &&
    isNullableDate(value.actualCloseDate) &&
    isNullableString(value.outcomeReason) &&
    (value.outcomeProvenance === null ||
      value.outcomeProvenance === "seller_reported") &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt)
  );
}

export function isOpportunityResponse(
  value: unknown,
  organisationId: string,
): value is Opportunity {
  return (
    isRecord(value) &&
    hasOpportunityResponseFields(value, organisationId) &&
    isNullableString(value.outcomeNote)
  );
}

export function isOpportunityListItemResponse(
  value: unknown,
  organisationId: string,
): value is OpportunityListItem {
  return (
    isRecord(value) &&
    hasOpportunityResponseFields(value, organisationId) &&
    isNullableString(value.companyName) &&
    isString(value.ownerName) &&
    isNullableString(value.latestMeetingId) &&
    isNullableDate(value.latestMeetingDate) &&
    isNullableString(value.latestMeetingMomentum) &&
    isNullableString(value.latestNextBestAction)
  );
}

export function isInteractionResponse(
  value: unknown,
  organisationId: string,
): value is Interaction {
  return (
    isRecord(value) &&
    hasTenantIdentity(value, organisationId) &&
    isNullableString(value.companyId) &&
    isNullableString(value.opportunityId) &&
    isNullableString(value.contactId) &&
    isNullableString(value.meetingId) &&
    isOptionalNullableString(value.eventId) &&
    isString(value.title) &&
    isAllowed(value.interactionType, interactionTypes) &&
    isAllowed(value.lifecycleStatus, interactionStatuses) &&
    isNullableDate(value.scheduledStartAt) &&
    isNullableDate(value.scheduledEndAt) &&
    isNullableDate(value.actualStartAt) &&
    isNullableDate(value.actualEndAt) &&
    isNullableString(value.timezone) &&
    isAllowed(value.creationOrigin, interactionCreationOrigins) &&
    (value.callDirection === null ||
      isAllowed(value.callDirection, callDirections)) &&
    (value.callOutcome === null ||
      isAllowed(value.callOutcome, callOutcomes)) &&
    isOptionalNullableAllowed(value.meetingPlatform, onlineMeetingPlatforms) &&
    isOptionalNullableString(value.meetingUrl) &&
    isOptionalNullableString(value.externalMeetingId) &&
    isOptionalNullableAllowed(
      value.captureSource,
      onlineMeetingCaptureSources,
    ) &&
    isOptionalNullableAllowed(
      value.ingestionState,
      onlineMeetingIngestionStates,
    ) &&
    isNullableSafeInteger(value.durationSeconds) &&
    Array.isArray(value.captureMethods) &&
    value.captureMethods.every((item) => isAllowed(item, captureMethods)) &&
    isAllowed(value.intelligenceState, intelligenceStates) &&
    typeof value.recordingAvailable === "boolean" &&
    isNonEmptyString(value.createdByUserId) &&
    isAllowed(value.briefState, briefStates) &&
    isNullableDate(value.briefGeneratedAt) &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt)
  );
}

export function isProviderCalendarEventResponse(
  value: unknown,
  organisationId: string,
): value is ProviderCalendarEvent {
  return (
    isRecord(value) &&
    hasTenantIdentity(value, organisationId) &&
    isString(value.title) &&
    isDate(value.startAt) &&
    isDate(value.endAt) &&
    isString(value.providerTimezone) &&
    Array.isArray(value.attendeeEmails) &&
    value.attendeeEmails.every(isString) &&
    isNullableString(value.location) &&
    isNullableString(value.onlineMeetingUrl) &&
    isString(value.sensitivity) &&
    isAllowed(value.state, providerCalendarEventStates) &&
    isAllowed(value.matchState, providerCalendarMatchStates) &&
    isNullableString(value.contactId) &&
    isNullableString(value.companyId) &&
    isNullableString(value.opportunityId) &&
    isNullableString(value.interactionId) &&
    isDate(value.lastSyncedAt)
  );
}

export function decodeProviderCalendarEventListResponse(
  value: unknown,
  organisationId: string,
): ProviderCalendarEventListResponse | null {
  if (
    !isRecord(value) ||
    value.organisationId !== organisationId ||
    !Array.isArray(value.items) ||
    !Number.isSafeInteger(value.total) ||
    (value.total as number) < 0 ||
    value.total !== value.items.length ||
    !value.items.every((item) =>
      isProviderCalendarEventResponse(item, organisationId),
    )
  ) {
    return null;
  }
  return value as unknown as ProviderCalendarEventListResponse;
}

export function decodeTenantPage<T>(
  value: unknown,
  organisationId: string,
  isItem: (item: unknown, organisationId: string) => item is T,
  options: { expectedPage?: number } = {},
): TenantEntityPage<T> | null {
  if (
    !isRecord(value) ||
    value.organisationId !== organisationId ||
    !Array.isArray(value.items) ||
    !Number.isSafeInteger(value.page) ||
    !Number.isSafeInteger(value.pageSize) ||
    !Number.isSafeInteger(value.total) ||
    !Number.isSafeInteger(value.pages) ||
    (value.page as number) < 1 ||
    (value.pageSize as number) < 1 ||
    (value.total as number) < 0 ||
    (value.pages as number) < 0 ||
    value.items.length > (value.pageSize as number) ||
    value.items.length > (value.total as number) ||
    ((value.pages as number) === 0
      ? (value.page as number) !== 1
      : (value.page as number) > (value.pages as number)) ||
    (value.pages as number) !==
      Math.ceil((value.total as number) / (value.pageSize as number)) ||
    (options.expectedPage !== undefined &&
      value.page !== options.expectedPage) ||
    !value.items.every((item) => isItem(item, organisationId))
  ) {
    return null;
  }
  return value as unknown as TenantEntityPage<T>;
}
