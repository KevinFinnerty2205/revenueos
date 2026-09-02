/** FastAPI Pydantic models and the generated OpenAPI document are canonical. */
export type AuthMode = "mock" | "clerk";
export type OrganisationRole = "admin" | "member";

export interface UserSummary {
  id: string;
  externalAuthId: string;
  displayName: string;
  email: string;
}

export interface OrganisationSummary {
  id: string;
  name: string;
  slug: string;
}

export interface MeResponse {
  user: UserSummary;
  organisation: OrganisationSummary;
  role: OrganisationRole;
  authMode: AuthMode;
  requestId: string;
}

export interface DependencyCheck {
  status: "ready" | "unavailable" | "misconfigured";
  detail: string;
}

export interface ReadyResponse {
  status: "ready" | "not_ready";
  environment: string;
  dependencies: Record<string, DependencyCheck>;
  requestId: string;
}

export interface HealthResponse {
  status: "healthy";
}

export interface ApiError {
  code: string;
  message: string;
  requestId: string;
  details?: Record<string, string>;
}

export type CompanyStatus = "prospect" | "active" | "inactive";
export type OpportunityStage =
  | "qualification"
  | "discovery"
  | "evaluation"
  | "proposal"
  | "negotiation"
  | "procurement"
  | "closed_won"
  | "closed_lost"
  | "other";
export type OpportunityStatus = "open" | "won" | "lost" | "on_hold";
export type TaskStatus = "open" | "in_progress" | "completed" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type MeetingType = "remote" | "phone" | "in_person" | "other";
export type MeetingStatus = "scheduled" | "completed" | "cancelled";
export type InteractionType =
  | "online_meeting"
  | "face_to_face_meeting"
  | "presentation"
  | "workshop"
  | "site_visit"
  | "executive_lunch"
  | "phone_call"
  | "conference_interaction"
  | "trade_show_interaction"
  | "manual_interaction";
export type InteractionLifecycleStatus =
  "planned" | "in_progress" | "completed" | "cancelled";
export type InteractionCreationOrigin =
  "manual" | "meeting_compatibility" | "imported_external";
export type CallDirection = "inbound" | "outbound" | "unknown";
export type CallOutcome = "connected" | "no_answer" | "voicemail" | "cancelled";
export type InteractionCaptureMethod =
  "debrief" | "voice_journal" | "recording" | "transcript";
export type InteractionIntelligenceState =
  "not_ready" | "processing" | "review_required" | "ready" | "not_applicable";
export type PreInteractionBriefState =
  | "unavailable"
  | "not_generated"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type BriefPriority = "high" | "medium" | "low";
export type AttendanceStatus = "invited" | "attended" | "absent" | "unknown";
export type ParticipantRole = "host" | "attendee";
export type TranscriptSource =
  | "manual"
  | "upload"
  | "recorded_audio"
  | "uploaded_audio"
  | "imported_audio"
  | "platform_generated"
  | "user_uploaded"
  | "externally_generated"
  | "manually_pasted";
export type OnlineMeetingPlatform =
  "microsoft_teams" | "zoom" | "google_meet" | "other";
export type OnlineMeetingCaptureSource =
  | "platform_recording"
  | "platform_transcript"
  | "user_uploaded_recording"
  | "user_uploaded_transcript"
  | "native_integration"
  | "meeting_bot"
  | "ai_debrief"
  | "voice_journal"
  | "manual_notes";
export type OnlineMeetingIngestionState =
  "not_started" | "uploading" | "processing" | "ready" | "failed";
export type TranscriptProvenance =
  | "platform_generated"
  | "user_uploaded"
  | "externally_generated"
  | "manually_pasted";
export type MeetingAuditAction =
  | "created"
  | "updated"
  | "deleted"
  | "restored"
  | "intelligence_requested"
  | "ai_job_created"
  | "ai_job_status_changed"
  | "ai_artifact_created";
export type MeetingAuditEntityType =
  "meeting" | "participant" | "transcript" | "ai_job" | "ai_artifact";
export type ExecutiveSummaryState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type ExecutiveSummaryMeetingType =
  | "sales_discovery"
  | "sales_demo"
  | "customer_success"
  | "recruitment"
  | "internal"
  | "other";
export type ExecutiveSummarySentiment =
  "positive" | "neutral" | "negative" | "mixed";
export type BuyingSignalsState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type BuyingSignalType =
  | "budget_confirmed"
  | "budget_unconfirmed"
  | "timeline_confirmed"
  | "timeline_unclear"
  | "decision_maker_engaged"
  | "decision_maker_missing"
  | "champion_identified"
  | "champion_not_evident"
  | "procurement_active"
  | "procurement_unclear"
  | "competitor_present"
  | "competitor_absent"
  | "urgency_present"
  | "urgency_absent"
  | "commercial_intent"
  | "implementation_commitment"
  | "next_step_committed"
  | "next_step_weak"
  | "stakeholder_alignment"
  | "stakeholder_misalignment"
  | "technical_fit_confirmed"
  | "technical_fit_uncertain"
  | "security_or_legal_progress"
  | "security_or_legal_blocker"
  | "other";
export type BuyingSignalPolarity = "positive" | "neutral" | "negative";
export type BuyingSignalStrength = "strong" | "moderate" | "weak";
export type DealMomentum =
  | "strong_positive"
  | "positive"
  | "neutral"
  | "negative"
  | "strong_negative"
  | "insufficient_evidence";
export type ObjectionsCompetitiveSignalsState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type ObjectionCategory =
  | "pricing"
  | "budget"
  | "commercial"
  | "legal"
  | "security"
  | "privacy"
  | "technical"
  | "integration"
  | "implementation"
  | "resourcing"
  | "procurement"
  | "timeline"
  | "product_fit"
  | "stakeholder"
  | "change_management"
  | "competitor"
  | "trust"
  | "other";
export type ObjectionStatus =
  "resolved" | "partially_addressed" | "deferred" | "unresolved";
export type ObjectionStrength = "strong" | "moderate" | "weak";
export type CompetitorPosition =
  "stronger" | "weaker" | "neutral" | "present" | "unclear";
export type OverallObjectionPressure =
  "none" | "low" | "medium" | "high" | "severe" | "insufficient_evidence";
export type StakeholderIntelligenceState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type StakeholderRole =
  | "economic_buyer"
  | "decision_maker"
  | "champion"
  | "influencer"
  | "blocker"
  | "technical_buyer"
  | "technical_evaluator"
  | "end_user"
  | "procurement"
  | "legal"
  | "security"
  | "finance"
  | "executive_sponsor"
  | "implementation_owner"
  | "vendor_representative"
  | "participant"
  | "unknown";
export type StakeholderInfluence = "high" | "medium" | "low" | "unclear";
export type StakeholderStance =
  "supportive" | "neutral" | "resistant" | "mixed" | "unclear";
export type StakeholderEngagement =
  "active" | "passive" | "absent_but_referenced" | "unclear";
export type StakeholderCoverageState =
  "identified" | "not_identified" | "unclear" | "not_discussed";
export type NextBestActionState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type RecommendationPriority = "high" | "medium" | "low";
export type RecommendationDependency =
  | "buying_signals"
  | "stakeholders"
  | "risks"
  | "open_questions"
  | "action_items";
export type DecisionsState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type DecisionStatus =
  "confirmed" | "tentative" | "rejected" | "deferred";
export type ActionItemsState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type ActionItemPriority = "high" | "medium" | "low";
export type ActionItemStatus = "open";
export type RisksBlockersState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type RiskCategory =
  | "budget"
  | "procurement"
  | "legal"
  | "security"
  | "technical"
  | "integration"
  | "timeline"
  | "implementation"
  | "stakeholder"
  | "competitor"
  | "commercial"
  | "resourcing"
  | "dependency"
  | "other";
export type RiskSeverity = "high" | "medium" | "low";
export type OpenQuestionsState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type OpenQuestionImportance = "high" | "medium" | "low";
export type FollowUpEmailState =
  "empty" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type FollowUpEmailTone = "professional" | "friendly" | "executive";
export type MeetingIntelligenceCapabilityName =
  | "executive_summary"
  | "buying_signals"
  | "objections_competitive_signals"
  | "stakeholder_intelligence"
  | "next_best_action"
  | "decisions"
  | "action_items"
  | "risks_blockers"
  | "open_questions"
  | "follow_up_email";
export type MeetingIntelligenceCapabilityState =
  | "unavailable"
  | "not_generated"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";
export type MeetingIntelligenceOverallState =
  | "unavailable"
  | "not_started"
  | "partially_generated"
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_empty_results"
  | "partially_failed"
  | "failed";

export interface EntityPage<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  pages: number;
}

export interface TenantEntity {
  id: string;
  organisationId: string;
  createdAt: string;
  updatedAt: string;
}

export interface Company extends TenantEntity {
  name: string;
  website: string | null;
  industry: string | null;
  location: string | null;
  employeeCount: number | null;
  status: CompanyStatus;
  ownerUserId: string;
  archivedAt: string | null;
}

export interface Contact extends TenantEntity {
  companyId: string;
  firstName: string;
  lastName: string;
  email: string | null;
  phone: string | null;
  jobTitle: string | null;
  linkedinUrl: string | null;
  status: "active" | "left_company";
  ownerUserId: string;
  archivedAt: string | null;
}

export interface Opportunity extends TenantEntity {
  companyId: string | null;
  name: string;
  stage: OpportunityStage;
  status: OpportunityStatus;
  estimatedValue: string | null;
  currency: string | null;
  expectedCloseDate: string | null;
  ownerUserId: string;
  description: string | null;
  archivedAt: string | null;
  pipelineId?: string | null;
  pipelineStageId?: string | null;
  stageEnteredAt?: string | null;
  stageTrackingStartedAt?: string | null;
  actualCloseDate?: string | null;
  outcomeReason?: string | null;
  outcomeNote?: string | null;
  outcomeProvenance?: "seller_reported" | null;
}

export type PipelineStageType = "open" | "won" | "lost";

export interface PipelineStage {
  id: string;
  pipelineId: string;
  key: string;
  name: string;
  position: number;
  stageType: PipelineStageType;
  guidance: string | null;
  active: boolean;
  archivedAt: string | null;
  currentOpportunityCount: number;
}

export interface SalesPipeline {
  id: string;
  name: string;
  isDefault: boolean;
  active: boolean;
  archivedAt: string | null;
  stages: PipelineStage[];
  createdAt: string;
  updatedAt: string;
}

export interface PipelineValueSummary {
  currency: string;
  amount: string;
  opportunityCount: number;
}

export interface PipelineSummary {
  openOpportunityCount: number;
  needsAttentionCount: number;
  closeDatesThisMonthCount: number;
  unvaluedOpportunityCount: number;
  values: PipelineValueSummary[];
}

export interface PipelineCard {
  opportunityId: string;
  opportunityName: string;
  companyId: string | null;
  companyName: string | null;
  pipelineId: string;
  pipelineName: string;
  stageId: string;
  stageName: string;
  stageType: PipelineStageType;
  status: OpportunityStatus;
  estimatedValue: string | null;
  currency: string | null;
  expectedCloseDate: string | null;
  actualCloseDate: string | null;
  ownerUserId: string;
  ownerName: string;
  stageEnteredAt: string | null;
  stageTrackingStartedAt: string | null;
  daysInStage: number | null;
  nextAction: string | null;
  attentionReasons: string[];
  outcomeReason: string | null;
  outcomeProvenance: "seller_reported" | null;
}

export interface PipelineBoard {
  pipeline: SalesPipeline;
  pipelines: SalesPipeline[];
  view: "open" | "closed";
  summary: PipelineSummary;
  cards: PipelineCard[];
  stageChangesAllowed: boolean;
  managedExternally: boolean;
  authorityMessage: string | null;
  managerIntelligenceAvailable: boolean;
  generatedAt: string;
}

export interface OpportunityStageEvent {
  id: string;
  fromPipelineId: string | null;
  toPipelineId: string;
  fromStageId: string | null;
  toStageId: string;
  fromStageName: string | null;
  toStageName: string;
  fromStageType: PipelineStageType | null;
  toStageType: PipelineStageType;
  changedByUserId: string | null;
  changedByName: string | null;
  changedAt: string;
  source:
    | "system_initial"
    | "migration_baseline"
    | "import_baseline"
    | "manual"
    | "external_crm";
  isBaseline: boolean;
  previousStageEnteredAt: string | null;
  outcomeReason: string | null;
  outcomeNote: string | null;
  outcomeProvenance: "seller_reported" | null;
  actualCloseDate: string | null;
  finalAmount: string | null;
  finalCurrency: string | null;
}

export interface OpportunityPipeline {
  opportunityId: string;
  status: OpportunityStatus;
  pipeline: SalesPipeline;
  stage: PipelineStage;
  stageEnteredAt: string | null;
  stageTrackingStartedAt: string | null;
  daysInStage: number | null;
  actualCloseDate: string | null;
  outcomeReason: string | null;
  outcomeNote: string | null;
  outcomeProvenance: "seller_reported" | null;
  availablePipelines: SalesPipeline[];
  history: OpportunityStageEvent[];
  stageChangesAllowed: boolean;
  managedExternally: boolean;
  authorityMessage: string | null;
}

export type CRMEntityType = "account" | "contact" | "opportunity";
export type CRMMode = "unconfigured" | "native" | "external";
export type CRMCustomFieldType =
  "short_text" | "number" | "date" | "boolean" | "single_select" | "url";

export interface CRMAvailability {
  moduleKey: "crm";
  state:
    "available" | "not_in_plan" | "setup_required" | "temporarily_unavailable";
  enabled: boolean;
  canManage: boolean;
  mode: CRMMode;
  externalProvider: "hubspot" | null;
  externalConnected: boolean;
  customFieldsReadOnly: boolean;
  message: string;
}

export interface CRMMember {
  userId: string;
  displayName: string;
  active: boolean;
}

export interface CRMCustomFieldDefinition {
  id: string;
  entityType: CRMEntityType;
  fieldKey: string;
  label: string;
  fieldType: CRMCustomFieldType;
  options: string[];
  active: boolean;
  displayOrder: number;
  createdByUserId: string;
  archivedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CRMCustomFieldValue {
  definition: CRMCustomFieldDefinition;
  value: string | boolean | null;
  source: string | null;
  changedByUserId: string | null;
  updatedAt: string | null;
  editable: boolean;
}

export interface CRMRecordChange {
  id: string;
  fieldKey: string;
  oldValue: unknown;
  newValue: unknown;
  source: string;
  changedByUserId: string;
  changedByName: string;
  changedAt: string;
}

export interface CRMActivityItem {
  id: string;
  activityType: "interaction" | "outreach" | "action" | "event" | "opportunity";
  title: string;
  detail: string | null;
  occurredAt: string;
  href: string | null;
  sourceLabel: string;
}

export interface CRMCoreField {
  key: string;
  label: string;
  value: string | null;
  authority:
    "revenueos_authoritative" | "crm_authoritative" | "review_before_sync";
}

export interface CRMRecord {
  entityType: CRMEntityType;
  entityId: string;
  title: string;
  ownerUserId: string;
  ownerName: string;
  archivedAt: string | null;
  recordUpdatedAt: string;
  mode: CRMMode;
  crmEnabled: boolean;
  canManage: boolean;
  customFieldsReadOnly: boolean;
  fieldAuthority: Record<
    string,
    "revenueos_authoritative" | "crm_authoritative" | "review_before_sync"
  >;
  coreFields: CRMCoreField[];
  customFields: CRMCustomFieldValue[];
  history: CRMRecordChange[];
  activity: CRMActivityItem[];
  mergedIntoEntityId: string | null;
  mergeId: string | null;
}

export type CRMImportDisposition =
  | "new"
  | "matches_existing"
  | "possible_duplicate"
  | "invalid"
  | "imported"
  | "skipped";

export interface CRMImportRow {
  sourceRow: number;
  disposition: CRMImportDisposition;
  issueCode: string | null;
  canonicalEntityId: string | null;
}

export interface CRMImportPreview {
  batchId: string;
  entityType: CRMEntityType;
  state: "previewed" | "confirmed" | "expired" | "failed";
  expiresAt: string;
  rowCount: number;
  actionableRowCount: number;
  importedRowCount: number;
  rows: CRMImportRow[];
  permissionToContactInferred: false;
  rawFileRetained: false;
}

export interface CRMMergeFieldConflict {
  fieldKey: string;
  sourceValue: unknown;
  survivorValue: unknown;
  selected: "source" | "survivor";
}

export interface CRMMergePreview {
  entityType: "account" | "contact";
  sourceEntityId: string;
  survivorEntityId: string;
  previewFingerprint: string;
  conflicts: CRMMergeFieldConflict[];
  blockedReasons: string[];
}

export interface CRMMergeResult {
  mergeId: string;
  entityType: "account" | "contact";
  sourceEntityId: string;
  survivorEntityId: string;
  mergedAt: string;
  alreadyApplied: boolean;
}

export interface OpportunityListItem extends Opportunity {
  companyName: string | null;
  ownerName: string;
  latestMeetingId: string | null;
  latestMeetingDate: string | null;
  latestMeetingMomentum: string | null;
  latestNextBestAction: string | null;
}

export interface Task extends TenantEntity {
  companyId: string | null;
  contactId: string | null;
  opportunityId: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  dueAt: string | null;
  assignedUserId: string | null;
  createdByUserId: string;
}

export type DailyPriorityKind =
  "interaction" | "action" | "deal" | "recommendation";
export type DailyInteractionState =
  "prepared" | "not_prepared" | "active" | "capture_needed" | "complete";
export type DailyActionTiming =
  "overdue" | "due_today" | "upcoming" | "no_due_date";
export type DailyDealReasonCode =
  | "overdue_action"
  | "unresolved_risk"
  | "methodology_gap"
  | "conflicting_evidence"
  | "upcoming_close_with_blocker"
  | "interaction_stale"
  | "next_action_pending";

export interface DailyPriority {
  kind: DailyPriorityKind;
  reasonCode:
    | "active_interaction"
    | "interaction_needs_preparation"
    | "overdue_high_priority_action"
    | "interaction_needs_capture"
    | "time_sensitive_deal_blocker"
    | "high_priority_action"
    | "next_best_action"
    | "next_upcoming_interaction";
  title: string;
  context: string;
  reason: string;
  ctaLabel: string;
  href: string;
  sourceId: string;
  startsAt: string | null;
  dueAt: string | null;
}

export interface DailyInteraction {
  id: string;
  title: string;
  companyId: string | null;
  companyName: string | null;
  opportunityId: string | null;
  opportunityName: string | null;
  interactionType: string;
  lifecycleStatus: string;
  startsAt: string;
  preparationState: DailyInteractionState;
  context: string;
  ctaLabel: string;
  href: string;
}

export interface DailyAction {
  id: string;
  title: string;
  opportunityId: string;
  opportunityName: string;
  companyName: string | null;
  priority: "high" | "normal" | "low";
  reviewStatus: "proposed" | "edited" | "approved";
  timing: DailyActionTiming;
  dueAt: string | null;
  state:
    | "needs_review"
    | "approved_not_complete"
    | "simulation_in_progress"
    | "simulation_completed_action_open"
    | "simulation_needs_review";
  stateLabel: string;
  ctaLabel: string;
  href: string;
}

export interface DailyActionSection {
  attentionCount: number;
  overdueCount: number;
  dueTodayCount: number;
  pendingReviewCount: number;
  approvedOpenCount: number;
  items: DailyAction[];
  truncated: boolean;
}

export interface DailyDealReason {
  code: DailyDealReasonCode;
  text: string;
}

export interface DailyDealAttention {
  opportunityId: string;
  opportunityName: string;
  companyName: string | null;
  estimatedValue: string | null;
  currency: string | null;
  expectedCloseDate: string | null;
  priority: "urgent" | "needs_attention" | "watch";
  reasons: DailyDealReason[];
  href: string;
}

export interface DailyDealSection {
  attentionCount: number;
  items: DailyDealAttention[];
  truncated: boolean;
}

export interface DailyPipelineCurrency {
  currency: string;
  openValue: string;
  closingThisMonthValue: string;
  openOpportunityCount: number;
  closingThisMonthCount: number;
}

export interface DailyPipelineSummary {
  state: "empty" | "single_currency" | "multiple_currencies";
  openOpportunityCount: number;
  unvaluedOpportunityCount: number;
  currencyCount: number;
  currencies: DailyPipelineCurrency[];
  safeMessage: string;
}

export interface DailyRecommendation {
  sourceId: string;
  opportunityId: string;
  opportunityName: string;
  recommendation: string;
  priority: "high" | "medium" | "low";
  reason: string;
  ctaLabel: "Review";
  href: string;
}

export interface DailyAvailability {
  interactions: boolean;
  actions: boolean;
  dealAttention: boolean;
  pipeline: boolean;
  recommendations: boolean;
  methodology: boolean;
  revenueBrain: boolean;
  targets: false;
  forecast: false;
}

export interface DailyResponse {
  generatedAt: string;
  localDate: string;
  timezone: string;
  userDisplayName: string;
  topPriority: DailyPriority | null;
  nextInteraction: DailyInteraction | null;
  todayInteractions: DailyInteraction[];
  totalTodayInteractions: number;
  actions: DailyActionSection;
  dealAttention: DailyDealSection;
  pipeline: DailyPipelineSummary;
  recommendations: DailyRecommendation[];
  availability: DailyAvailability;
  hasOpportunities: boolean;
  caughtUp: boolean;
}

export interface Meeting extends TenantEntity {
  interactionId: string;
  title: string;
  description: string | null;
  meetingDate: string;
  meetingType: MeetingType;
  status: MeetingStatus;
  companyId: string | null;
  opportunityId: string | null;
  ownerUserId: string;
  createdBy: string;
  updatedBy: string;
}

export interface Interaction extends TenantEntity {
  companyId: string | null;
  opportunityId: string | null;
  contactId: string | null;
  meetingId: string | null;
  eventId?: string | null;
  interactionType: InteractionType;
  lifecycleStatus: InteractionLifecycleStatus;
  title: string;
  scheduledStartAt: string | null;
  scheduledEndAt: string | null;
  actualStartAt: string | null;
  actualEndAt: string | null;
  timezone: string | null;
  creationOrigin: InteractionCreationOrigin;
  callDirection: CallDirection | null;
  callOutcome: CallOutcome | null;
  meetingPlatform?: OnlineMeetingPlatform | null;
  meetingUrl?: string | null;
  externalMeetingId?: string | null;
  captureSource?: OnlineMeetingCaptureSource | null;
  ingestionState?: OnlineMeetingIngestionState | null;
  durationSeconds: number | null;
  captureMethods: InteractionCaptureMethod[];
  intelligenceState: InteractionIntelligenceState;
  recordingAvailable: boolean;
  createdByUserId: string;
  briefState: "unavailable" | "not_generated" | "completed";
  briefGeneratedAt: string | null;
}

export type InteractionMarkerType =
  | "buying_signal"
  | "objection"
  | "decision"
  | "action_item"
  | "risk"
  | "stakeholder"
  | "timeline"
  | "budget"
  | "procurement"
  | "follow_up"
  | "important_moment"
  | "customer_question"
  | "requested_material"
  | "strong_engagement";

export interface InteractionMarker {
  id: string;
  interactionId: string;
  createdByUserId: string;
  markerType: InteractionMarkerType;
  recordingOffsetMs: number | null;
  createdAt: string;
}

export type LiveIntelligenceAvailability =
  "available" | "unavailable" | "disabled";
export type LiveIntelligenceState =
  | "available"
  | "unavailable"
  | "disabled"
  | "active"
  | "processing"
  | "completed"
  | "failed";
export type LiveSignalType =
  | "buying_signal"
  | "objection"
  | "stakeholder"
  | "decision"
  | "action_item"
  | "risk"
  | "timeline"
  | "procurement"
  | "security_legal"
  | "customer_request"
  | "commercial_intent"
  | "objective_progress"
  | "open_question_progress"
  | "other";
export type LiveSignalLifecycle =
  | "detected"
  | "updated"
  | "superseded"
  | "dismissed"
  | "promoted_candidate"
  | "expired";
export type LiveSignalResolution =
  "pending" | "confirmed" | "revised" | "unsupported" | "unresolved";

export interface LiveSourceReference {
  transcriptVersionId: string;
  sequenceStart: number;
  sequenceEnd: number;
}

export interface ProvisionalLiveSignal {
  id: string;
  signalType: LiveSignalType;
  statement: string;
  lifecycleStatus: LiveSignalLifecycle;
  provisional: true;
  priority: "high" | "normal";
  evidenceStrength:
    "customer_attributed" | "speaker_uncertain" | "context_only";
  resolutionStatus: LiveSignalResolution;
  source: LiveSourceReference;
  detectedAt: string;
  lastUpdatedAt: string;
  supersededBy: string | null;
}

export interface LiveBriefProgress {
  itemType: "objective" | "open_question";
  itemIndex: number;
  label: string;
  progressStatus: "unresolved" | "possibly_addressed" | "possibly_answered";
}

export interface LiveReconciliationSummary {
  confirmed: number;
  revised: number;
  unsupported: number;
  unresolved: number;
}

export interface LiveIntelligenceResponse {
  availability: LiveIntelligenceAvailability;
  state: LiveIntelligenceState;
  safeMessage: string;
  sourceKind: "progressive_transcript" | null;
  sessionId: string | null;
  signals: ProvisionalLiveSignal[];
  objectives: LiveBriefProgress[];
  openQuestions: LiveBriefProgress[];
  reconciliation: LiveReconciliationSummary | null;
  generatedAt: string | null;
  updatedAt: string | null;
  nextPollSeconds: number;
}

export interface LiveProcessResponse extends LiveIntelligenceResponse {
  processed: boolean;
  newSegmentCount: number;
}

export type DebriefCaptureType = "ai_debrief" | "voice_journal";
export type DebriefInputMode = "text" | "voice";
export type DebriefLifecycleStatus =
  | "created"
  | "collecting"
  | "processing"
  | "review"
  | "completed"
  | "cancelled"
  | "failed";
export type DebriefQuestionTarget =
  | "stakeholder"
  | "budget"
  | "timeline"
  | "procurement"
  | "security_legal"
  | "objection"
  | "competitor"
  | "decision"
  | "action_item"
  | "open_question"
  | "commitment"
  | "implementation"
  | "commercial_intent"
  | "next_step"
  | "other";
export type CandidateEvidenceCategory =
  DebriefQuestionTarget | "buying_signal" | "risk" | "customer_request";

export interface DebriefQuestion {
  status: "ask" | "complete";
  question: string | null;
  reason: string;
  target: DebriefQuestionTarget | null;
  priority: BriefPriority | null;
}

export interface DebriefTurn {
  id: string;
  turnNumber: number;
  question: DebriefQuestion;
  answerText: string;
  inputMode: DebriefInputMode;
  createdAt: string;
}

export interface CandidateEvidence {
  id: string;
  evidenceCategory: CandidateEvidenceCategory;
  statement: string;
  originalStatement: string;
  origin: "salesperson_reported";
  sourceLabel: "Reported by you";
  supportClassification: "reported";
  validationState: "unreviewed" | "verified" | "rejected";
  userReviewState: "pending" | "accepted" | "rejected";
  conflictState: "not_assessed" | "conflicting" | "unresolved" | "corroborated";
  sourceCaptureSessionId: string;
  evidenceFragmentId: string;
  acceptedEvidenceId: string | null;
  entityReference: string | null;
  explicitlyReportedAt: string | null;
  edited: boolean;
}

export interface DebriefSession {
  id: string;
  interactionId: string;
  captureType: DebriefCaptureType;
  lifecycleStatus: DebriefLifecycleStatus;
  questionCount: number;
  maxQuestions: number;
  currentQuestion: DebriefQuestion | null;
  canFinish: boolean;
  finishedEarly: boolean;
  turns: DebriefTurn[];
  candidates: CandidateEvidence[];
  interactionIntelligenceId: string | null;
  revenueBrainSnapshotId: string | null;
  startedAt: string;
  updatedAt: string;
  completedAt: string | null;
}

export interface DebriefReviewResponse extends DebriefSession {
  acceptedCount: number;
  rejectedCount: number;
  interactionUpdated: boolean;
  revenueBrainUpdated: boolean;
}

export interface BriefRecentChange {
  change: string;
  importance: BriefPriority;
  source: "revenue_brain";
}

export interface BriefObjective {
  objective: string;
  priority: BriefPriority;
  reason: string;
}

export interface BriefQuestion {
  question: string;
  purpose: string;
  priority: BriefPriority;
}

export interface BriefStakeholder {
  name: string;
  role: string;
  focus: string;
}

export interface BriefCommitment {
  commitment: string;
  owner: string | null;
  dueDate: string | null;
}

export interface BriefRisk {
  risk: string;
  severity: BriefPriority;
}

export interface PreInteractionBriefContent {
  interactionId: string;
  interactionType: InteractionType;
  briefVersion: number;
  headline: string;
  accountContext: string;
  recentChanges: BriefRecentChange[];
  objectives: BriefObjective[];
  questionsToAsk: BriefQuestion[];
  stakeholderFocus: BriefStakeholder[];
  openCommitments: BriefCommitment[];
  risksToWatch: BriefRisk[];
  successCriteria: string[];
  interactionGuidance: string;
  confidence: number;
  companyName: string | null;
  opportunityName: string | null;
  participants: Array<{ name: string; role: string }>;
  nextBestAction: string | null;
}

export interface BriefVersionSummary {
  briefVersion: number;
  generatedAt: string;
  reviewed: boolean;
  reviewedAt: string | null;
}

export interface PreInteractionBriefResponse {
  state: PreInteractionBriefState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  safeMessage: string | null;
  brief: PreInteractionBriefContent | null;
  generatedAt: string | null;
  reviewed: boolean;
  reviewedAt: string | null;
  priorVersions: BriefVersionSummary[];
  sourceLabels: string[];
}

export interface PreInteractionBriefRequestResponse extends PreInteractionBriefResponse {
  created: boolean;
}

export interface RevenueBrainSnapshot {
  id: string;
  organisationId: string;
  companyId: string;
  opportunityId: string | null;
  meetingId: string;
  transcriptVersionId: string;
  createdAt: string;
  meetingDate: string;
  summaryReference: string;
  buyingSignalsReference: string;
  objectionsReference: string;
  stakeholdersReference: string;
  decisionsReference: string;
  actionsReference: string;
  risksReference: string;
  questionsReference: string;
  nextBestActionReference: string;
  version: number;
}

export interface RevenueBrainVisualEvidenceItem {
  evidenceId: string;
  category: string;
  statement: string;
  origin: "ai_inferred";
  sourceOwnership: VisualSourceOwnership;
  supportClassification: VisualSupportClassification;
  sourceLabel: string;
  validationState: "verified";
}

export interface RevenueBrainVisualSnapshot {
  id: string;
  interactionId: string;
  opportunityId: string | null;
  interactionTitle: string;
  interactionType: string;
  interactionDate: string;
  createdAt: string;
  sourceLabel: string;
  visualType: VisualType;
  items: RevenueBrainVisualEvidenceItem[];
}

export interface RevenueBrainReportedEvidenceItem {
  evidenceId: string;
  category: string;
  statement: string;
  origin: "salesperson_reported";
  sourceLabel: "Reported by you";
  validationState: "verified";
  conflictState: "not_assessed" | "conflicting" | "unresolved" | "corroborated";
}

export interface RevenueBrainReportedSnapshot {
  id: string;
  interactionId: string;
  opportunityId: string | null;
  interactionTitle: string;
  interactionType: string;
  interactionDate: string;
  createdAt: string;
  sourceLabel: "Reported by you";
  items: RevenueBrainReportedEvidenceItem[];
}

export type RevenueBrainScope = "account" | "opportunity";
export type RevenueBrainReasoningState =
  | "insufficient_history"
  | "not_generated"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type RevenueBrainDirection =
  | "improved"
  | "worsened"
  | "changed"
  | "resolved"
  | "introduced"
  | "unchanged"
  | "unclear";
export type RevenueBrainImportance = "high" | "medium" | "low";
export type RevenueBrainSourceCapability =
  | "executive_summary"
  | "buying_signals"
  | "objections_competitive_signals"
  | "stakeholder_intelligence"
  | "decisions"
  | "action_items"
  | "risks_blockers"
  | "open_questions"
  | "next_best_action";
export type RevenueBrainChangeType =
  | "budget_confirmed"
  | "budget_became_unclear"
  | "timeline_confirmed"
  | "timeline_became_unclear"
  | "decision_maker_entered"
  | "decision_maker_missing"
  | "champion_emerged"
  | "champion_strengthened"
  | "champion_weakened"
  | "champion_disappeared"
  | "procurement_entered"
  | "procurement_progressed"
  | "procurement_became_unclear"
  | "competitor_introduced"
  | "competitor_removed"
  | "competitor_position_strengthened"
  | "competitor_position_weakened"
  | "urgency_increased"
  | "urgency_decreased"
  | "commercial_intent_increased"
  | "commercial_intent_decreased"
  | "next_step_strengthened"
  | "next_step_weakened"
  | "stakeholder_alignment_improved"
  | "stakeholder_alignment_worsened"
  | "technical_fit_improved"
  | "technical_fit_worsened"
  | "security_or_legal_progressed"
  | "security_or_legal_blocker_introduced"
  | "security_or_legal_blocker_resolved"
  | "objection_introduced"
  | "objection_strengthened"
  | "objection_weakened"
  | "objection_resolved"
  | "objection_reopened"
  | "competitive_pressure_increased"
  | "competitive_pressure_decreased"
  | "stakeholder_added"
  | "stakeholder_removed"
  | "stakeholder_role_changed"
  | "stakeholder_influence_increased"
  | "stakeholder_influence_decreased"
  | "stakeholder_stance_improved"
  | "stakeholder_stance_worsened"
  | "economic_buyer_identified"
  | "economic_buyer_became_unclear"
  | "technical_buyer_identified"
  | "technical_buyer_became_unclear"
  | "blocker_emerged"
  | "blocker_resolved"
  | "risk_introduced"
  | "risk_severity_increased"
  | "risk_severity_decreased"
  | "risk_resolved"
  | "risk_persisted"
  | "open_question_introduced"
  | "open_question_answered"
  | "open_question_persisted"
  | "open_question_importance_increased"
  | "open_question_importance_decreased"
  | "decision_added"
  | "decision_changed"
  | "decision_reversed"
  | "action_item_added"
  | "action_item_completed"
  | "action_item_removed"
  | "action_item_owner_changed"
  | "action_item_due_date_changed"
  | "action_item_overdue_evidence"
  | "commitment_persisted"
  | "next_best_action_changed"
  | "next_best_action_priority_increased"
  | "next_best_action_priority_decreased"
  | "next_best_action_unchanged"
  | "no_material_change"
  | "other";

export interface RevenueBrainEvidence {
  snapshotId: string;
  artefactId: string;
  artefactType: RevenueBrainSourceCapability;
  entityKey: string;
  field: string;
  value: string;
}

export interface RevenueBrainChange {
  changeType: RevenueBrainChangeType;
  direction: RevenueBrainDirection;
  importance: RevenueBrainImportance;
  title: string;
  description: string;
  confidence: number;
  sourceCapabilities: RevenueBrainSourceCapability[];
  evidence: RevenueBrainEvidence[];
}

export interface RevenueBrainInsightContent {
  scope: RevenueBrainScope;
  fromSnapshotId: string;
  toSnapshotId: string;
  fromMeetingId: string;
  toMeetingId: string;
  fromMeetingDate: string;
  toMeetingDate: string;
  changes: RevenueBrainChange[];
  summary: string;
  confidence: number;
}

export interface RevenueBrainInsight {
  id: string;
  companyId: string;
  opportunityId: string | null;
  reasoningVersion: number;
  createdAt: string;
  content: RevenueBrainInsightContent;
}

export interface RevenueBrainReasoningResponse {
  state: RevenueBrainReasoningState;
  message: string;
  latest: RevenueBrainInsight | null;
  history: RevenueBrainInsight[];
}

export interface RevenueBrainReasoningRequestResponse extends RevenueBrainReasoningResponse {
  created: boolean;
}

export interface MeetingParticipant {
  id: string;
  organisationId: string;
  meetingId: string;
  contactId: string | null;
  displayName: string | null;
  email: string | null;
  attendanceStatus: AttendanceStatus;
  role: ParticipantRole;
  createdAt: string;
}

export interface Transcript extends TenantEntity {
  meetingId: string;
  rawText: string;
  language: string;
  version: number;
  source: TranscriptSource;
}

export interface MeetingAuditEvent {
  id: string;
  meetingId: string;
  actorUserId: string;
  action: MeetingAuditAction;
  entityType: MeetingAuditEntityType;
  entityId: string;
  changedFields: string[];
  version: number | null;
  createdAt: string;
}

export interface ExecutiveSummaryContent {
  executiveSummary: string;
  meetingType: ExecutiveSummaryMeetingType;
  sentiment: ExecutiveSummarySentiment;
  confidence: number;
}

export interface ExecutiveSummaryResponse {
  state: ExecutiveSummaryState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  executiveSummary: ExecutiveSummaryContent | null;
}

export interface ExecutiveSummaryRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface BuyingSignal {
  signalType: BuyingSignalType;
  polarity: BuyingSignalPolarity;
  strength: BuyingSignalStrength;
  confidence: number;
  evidence: string;
}

export interface BuyingSignalsContent {
  signals: BuyingSignal[];
  overallMomentum: DealMomentum;
  momentumSummary: string;
  confidence: number;
}

export interface BuyingSignalsResponse {
  state: BuyingSignalsState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  buyingSignals: BuyingSignalsContent | null;
}

export interface BuyingSignalsRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ObjectionItem {
  objection: string;
  category: ObjectionCategory;
  status: ObjectionStatus;
  strength: ObjectionStrength;
  owner: string | null;
  confidence: number;
  evidence: string;
}

export interface CompetitorSignal {
  name: string;
  position: CompetitorPosition;
  confidence: number;
  evidence: string;
}

export interface ObjectionsCompetitiveSignalsContent {
  objections: ObjectionItem[];
  competitors: CompetitorSignal[];
  overallObjectionPressure: OverallObjectionPressure;
  summary: string;
}

export interface ObjectionsCompetitiveSignalsResponse {
  state: ObjectionsCompetitiveSignalsState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  objectionsCompetitiveSignals: ObjectionsCompetitiveSignalsContent | null;
}

export interface ObjectionsCompetitiveSignalsRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface StakeholderItem {
  name: string;
  organisation: string | null;
  role: StakeholderRole;
  influence: StakeholderInfluence;
  stance: StakeholderStance;
  engagement: StakeholderEngagement;
  confidence: number;
  evidence: string;
}

export interface StakeholderRoleCoverage {
  economicBuyer: StakeholderCoverageState;
  decisionMaker: StakeholderCoverageState;
  champion: StakeholderCoverageState;
  technicalBuyer: StakeholderCoverageState;
  procurement: StakeholderCoverageState;
  legalSecurity: StakeholderCoverageState;
}

export interface StakeholderIntelligenceContent {
  stakeholders: StakeholderItem[];
  roleCoverage: StakeholderRoleCoverage;
  stakeholderSummary: string;
  confidence: number;
}

export interface StakeholderIntelligenceResponse {
  state: StakeholderIntelligenceState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  stakeholderIntelligence: StakeholderIntelligenceContent | null;
}

export interface StakeholderIntelligenceRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface RecommendedAction {
  action: string;
  reason: string;
  priority: RecommendationPriority;
  confidence: number;
  dependsOn: RecommendationDependency[];
}

export interface NextBestActionContent {
  overallRecommendation: string;
  priority: RecommendationPriority;
  confidence: number;
  reasoning: string[];
  recommendedActions: RecommendedAction[];
}

export interface NextBestActionResponse {
  state: NextBestActionState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  nextBestAction: NextBestActionContent | null;
}

export interface NextBestActionRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface DecisionItem {
  decision: string;
  owner: string | null;
  status: DecisionStatus;
  confidence: number;
  evidence: string;
}

export interface DecisionsContent {
  decisions: DecisionItem[];
}

export interface DecisionsResponse {
  state: DecisionsState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  decisions: DecisionsContent | null;
}

export interface DecisionsRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ActionItem {
  task: string;
  owner: string | null;
  dueDate: string | null;
  priority: ActionItemPriority;
  status: ActionItemStatus;
  confidence: number;
  evidence: string;
}

export interface ActionItemsContent {
  actionItems: ActionItem[];
}

export interface ActionItemsResponse {
  state: ActionItemsState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  actionItems: ActionItemsContent | null;
}

export interface ActionItemsRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface RiskItem {
  risk: string;
  category: RiskCategory;
  severity: RiskSeverity;
  owner: string | null;
  confidence: number;
  evidence: string;
}

export interface RisksBlockersContent {
  risks: RiskItem[];
}

export interface RisksBlockersResponse {
  state: RisksBlockersState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  risksBlockers: RisksBlockersContent | null;
}

export interface RisksBlockersRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface OpenQuestionItem {
  question: string;
  owner: string | null;
  importance: OpenQuestionImportance;
  confidence: number;
  evidence: string;
}

export interface OpenQuestionsContent {
  openQuestions: OpenQuestionItem[];
}

export interface OpenQuestionsResponse {
  state: OpenQuestionsState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  openQuestions: OpenQuestionsContent | null;
}

export interface OpenQuestionsRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface FollowUpEmailContent {
  subject: string;
  greeting: string;
  summary: string;
  decisions: string[];
  actionItems: string[];
  openQuestions: string[];
  closing: string;
  tone: FollowUpEmailTone;
  confidence: number;
}

export interface FollowUpEmailResponse {
  state: FollowUpEmailState;
  generationAvailable: boolean;
  unavailableReason: string | null;
  jobId: string | null;
  transcriptVersion: number | null;
  requestedAt: string | null;
  startedAt: string | null;
  generatedAt: string | null;
  safeMessage: string | null;
  tone: FollowUpEmailTone | null;
  followUpEmail: FollowUpEmailContent | null;
}

export interface FollowUpEmailRequestResponse {
  jobId: string;
  status: "queued" | "running" | "completed";
  created: boolean;
  transcriptVersion: number;
  tone: FollowUpEmailTone;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface MeetingIntelligenceCapability<TContent> {
  state: MeetingIntelligenceCapabilityState;
  generationAvailable: boolean;
  message: string | null;
  generatedAt: string | null;
  emptyResult: boolean;
  content: TContent | null;
}

export interface MeetingIntelligenceFollowUpEmailCapability extends MeetingIntelligenceCapability<FollowUpEmailContent> {
  tone: FollowUpEmailTone | null;
}

export interface MeetingIntelligenceProgress {
  ready: number;
  queued: number;
  processing: number;
  failed: number;
  notGenerated: number;
  total: 10;
  summary: string;
}

export interface MeetingIntelligenceResponse {
  overallState: MeetingIntelligenceOverallState;
  generationAvailable: boolean;
  retryAvailable: boolean;
  lastUpdatedAt: string | null;
  progress: MeetingIntelligenceProgress;
  executiveSummary: MeetingIntelligenceCapability<ExecutiveSummaryContent>;
  buyingSignals: MeetingIntelligenceCapability<BuyingSignalsContent>;
  objectionsCompetitiveSignals: MeetingIntelligenceCapability<ObjectionsCompetitiveSignalsContent>;
  stakeholderIntelligence: MeetingIntelligenceCapability<StakeholderIntelligenceContent>;
  nextBestAction: MeetingIntelligenceCapability<NextBestActionContent>;
  decisions: MeetingIntelligenceCapability<DecisionsContent>;
  actionItems: MeetingIntelligenceCapability<ActionItemsContent>;
  risksBlockers: MeetingIntelligenceCapability<RisksBlockersContent>;
  openQuestions: MeetingIntelligenceCapability<OpenQuestionsContent>;
  followUpEmail: MeetingIntelligenceFollowUpEmailCapability;
}

export interface MeetingIntelligenceGenerationResponse extends MeetingIntelligenceResponse {
  createdCapabilities: MeetingIntelligenceCapabilityName[];
  reusedCapabilities: MeetingIntelligenceCapabilityName[];
}

export type IntelligenceReadiness =
  "unavailable" | "not_generated" | "partial" | "ready";

export interface OpportunityWorkspaceOpportunity {
  id: string;
  companyId: string | null;
  companyName: string | null;
  name: string;
  stage: OpportunityStage;
  status: OpportunityStatus;
  estimatedValue: string | null;
  currency: string | null;
  expectedCloseDate: string | null;
  ownerUserId: string;
  ownerName: string;
  description: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface OpportunityMeetingSummary {
  id: string;
  title: string;
  meetingDate: string;
  status: MeetingStatus;
  companyId: string | null;
  companyName: string | null;
  participantCount: number;
  transcriptAvailable: boolean;
  transcriptVersion: number | null;
  intelligenceReadiness: IntelligenceReadiness;
  intelligenceSectionsAvailable: number;
  updatedAt: string;
}

export interface ReportedIntelligenceItem {
  evidenceId: string;
  category: string;
  statement: string;
  origin: "salesperson_reported";
  sourceLabel: "Reported by you";
  validationState: "verified";
  conflictState: "not_assessed" | "conflicting" | "unresolved" | "corroborated";
}

export interface ReportedInteractionIntelligence {
  id: string;
  interactionId: string;
  generatedAt: string;
  sourceLabel: "Reported by you";
  items: ReportedIntelligenceItem[];
}

export type VisualType =
  | "whiteboard"
  | "workshop_output"
  | "architecture_diagram"
  | "handwritten_notes"
  | "agenda"
  | "business_card"
  | "presentation_slide"
  | "presentation_deck_page"
  | "customer_document_photo"
  | "site_photo"
  | "product_photo"
  | "screenshot"
  | "other";
export type VisualSourceOwnership =
  | "customer_created"
  | "salesperson_created"
  | "jointly_created"
  | "unknown_origin";
export type VisualProcessingStatus =
  | "uploading"
  | "uploaded"
  | "processing"
  | "review"
  | "completed"
  | "failed"
  | "cancelled"
  | "deletion_pending"
  | "deleted";
export type VisualSupportClassification = "direct" | "observed" | "context";
export type VisualEvidenceCategory =
  | "stakeholder"
  | "customer_request"
  | "decision"
  | "action_item"
  | "risk"
  | "technical_constraint"
  | "implementation_requirement"
  | "timeline"
  | "procurement"
  | "security_legal"
  | "budget"
  | "objection"
  | "commercial_intent"
  | "contact_detail"
  | "other";

export interface VisualCandidateRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface VisualCandidateEvidence {
  id: string;
  category: VisualEvidenceCategory;
  statement: string;
  originalStatement: string;
  sourceVisualId: string;
  sourceOwnership: VisualSourceOwnership;
  origin: "ai_inferred";
  supportClassification: VisualSupportClassification;
  validationState: "unreviewed" | "verified" | "rejected";
  reviewState: "pending" | "accepted" | "rejected";
  conflictState: "not_assessed" | "conflicting";
  confidenceClass: "low" | "medium" | "high" | null;
  evidenceRegion: VisualCandidateRegion | null;
  relatedEntity: string | null;
  extractedTextSnippet: string | null;
  acceptedEvidenceId: string | null;
  edited: boolean;
}

export interface VisualEvidence {
  id: string;
  interactionId: string;
  captureSessionId: string;
  visualType: VisualType;
  sourceOwnership: VisualSourceOwnership;
  contextLabel: string | null;
  filename: string;
  mimeType: "image/jpeg" | "image/png";
  byteSize: number;
  width: number | null;
  height: number | null;
  checksumSha256: string;
  capturedAt: string;
  processingStatus: VisualProcessingStatus;
  processingAttempts: number;
  failureCode: string | null;
  providerMode: "mock" | "openai";
  externalProcessing: boolean;
  candidates: VisualCandidateEvidence[];
  downloadUrl: string | null;
  interactionIntelligenceId: string | null;
  revenueBrainSnapshotId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface VisualUploadCreateResponse extends VisualEvidence {
  uploadUrl: string;
  uploadExpiresAt: string;
}

export interface VisualReviewResponse extends VisualEvidence {
  acceptedCount: number;
  rejectedCount: number;
  interactionUpdated: boolean;
  revenueBrainUpdated: boolean;
}

export interface VisualIntelligenceItem {
  evidenceId: string;
  category: string;
  statement: string;
  origin: "ai_inferred";
  sourceOwnership: VisualSourceOwnership;
  supportClassification: VisualSupportClassification;
  sourceLabel: string;
  validationState: "verified";
  conflictState: "not_assessed" | "conflicting";
}

export interface VisualInteractionIntelligence {
  id: string;
  interactionId: string;
  generatedAt: string;
  sourceLabel: string;
  visualType: VisualType;
  items: VisualIntelligenceItem[];
}

export type DocumentEvidenceType =
  | "proposal"
  | "rfp"
  | "rfq"
  | "requirements"
  | "contract"
  | "sow"
  | "pricing"
  | "procurement"
  | "security_questionnaire"
  | "implementation_plan"
  | "technical_specification"
  | "customer_presentation"
  | "sales_material"
  | "other";
export type DocumentSourceOwnership =
  | "customer_provided"
  | "salesperson_provided"
  | "jointly_created"
  | "externally_generated"
  | "system_imported"
  | "unknown";
export type EmailEvidenceSourceType =
  | "customer_sent"
  | "salesperson_sent"
  | "internal_forward"
  | "manually_pasted"
  | "external_provider_import";
export type EmailEvidenceDirection =
  "inbound" | "outbound" | "internal" | "unknown";

export interface SourceEvidenceLocation {
  reference: string;
  pageNumber: number | null;
  section: string | null;
  paragraphIndex: number | null;
}

export interface SourceEvidenceCandidate {
  id: string;
  category: string;
  statement: string;
  originalStatement: string;
  sourceKind: "document" | "email";
  sourceId: string;
  sourceEvidenceId: string;
  sourceLabel: string;
  sourceOrigin: string;
  interpretationOrigin: "ai_inferred";
  originClass:
    | "customer_direct"
    | "seller_prepared"
    | "salesperson_reported"
    | "imported_external";
  supportClass: "direct" | "reported" | "context";
  sourceLocation: SourceEvidenceLocation;
  validationState: "unreviewed" | "verified" | "rejected";
  reviewState: "pending" | "accepted" | "rejected";
  conflictState: "not_assessed" | "conflicting" | "supersedes" | "superseded";
  supersedesCandidateId: string | null;
  acceptedEvidenceId: string | null;
  edited: boolean;
}

export interface DocumentEvidenceSource {
  id: string;
  sourceEvidenceId: string;
  companyId: string | null;
  opportunityId: string | null;
  interactionId: string | null;
  documentType: DocumentEvidenceType;
  sourceOwnership: DocumentSourceOwnership;
  filename: string;
  mimeType: "application/pdf" | "text/plain";
  byteSize: number;
  checksumSha256: string;
  documentAt: string;
  processingStatus:
    | "received"
    | "processing"
    | "review"
    | "completed"
    | "failed"
    | "deletion_pending"
    | "deleted";
  storageStatus:
    "available" | "missing" | "deletion_pending" | "delete_failed" | "deleted";
  pageCount: number | null;
  extractedCharacterCount: number | null;
  failureCode: string | null;
  candidates: SourceEvidenceCandidate[];
  downloadUrl: string | null;
  revenueBrainSnapshotId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentEmailEvidenceCapabilities {
  documentEvidence: boolean;
  emailEvidence: boolean;
  supportedDocumentMimeTypes: ("application/pdf" | "text/plain")[];
  emailProviderImport: false;
  documentProviderImport: false;
  safeMessage: string;
}

export interface EmailEvidenceSource {
  id: string;
  sourceEvidenceId: string;
  companyId: string | null;
  opportunityId: string | null;
  interactionId: string | null;
  sourceType: EmailEvidenceSourceType;
  direction: EmailEvidenceDirection;
  senderContactId: string | null;
  senderIdentityState: "verified_contact" | "unknown";
  subjectPresent: boolean;
  messageAt: string;
  quoteHandling: "none" | "stripped" | "ambiguous";
  processingStatus:
    "received" | "processing" | "review" | "completed" | "failed" | "deleted";
  failureCode: string | null;
  candidates: SourceEvidenceCandidate[];
  revenueBrainSnapshotId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SourceEvidenceReviewResponse {
  sourceKind: "document" | "email";
  sourceId: string;
  acceptedCount: number;
  rejectedCount: number;
  opportunityUpdated: boolean;
  revenueBrainUpdated: boolean;
  revenueBrainSnapshotId: string | null;
  candidates: SourceEvidenceCandidate[];
}

export interface OpportunitySourceEvidenceItem {
  snapshotId: string;
  sourceKind: "document" | "email";
  sourceId: string;
  sourceType: string;
  sourceLabel: string;
  sourceOrigin: string;
  occurredAt: string;
  category: string;
  statement: string;
  evidenceId: string;
  location: SourceEvidenceLocation;
  originClass:
    | "customer_direct"
    | "seller_prepared"
    | "salesperson_reported"
    | "imported_external";
  supportClass: "direct" | "reported" | "context";
  conflictState: "not_assessed" | "conflicting" | "supersedes" | "superseded";
}

export interface RevenueBrainSourceSnapshot {
  id: string;
  sourceKind: "document" | "email";
  sourceId: string;
  opportunityId: string | null;
  interactionId: string | null;
  sourceType: string;
  sourceLabel: string;
  sourceOrigin: string;
  occurredAt: string;
  createdAt: string;
  items: OpportunitySourceEvidenceItem[];
}

export type RecordingType =
  | "live_audio_recording"
  | "uploaded_audio_recording"
  | "imported_audio_recording";
export type RecordingSource =
  | "customer_call_recording"
  | "business_phone_recording"
  | "user_uploaded_recording"
  | "external_provider_recording"
  | "platform_recording";
export type RecordingLifecycleStatus =
  | "created"
  | "recording"
  | "uploading"
  | "uploaded"
  | "transcribing"
  | "completed"
  | "failed"
  | "cancelled"
  | "deleting"
  | "deleted";
export type RecordingMimeType = "audio/webm" | "audio/mp4" | "audio/m4a";
export type RecordingTranscriptionStatus =
  "disabled" | "queued" | "processing" | "completed" | "failed";

export interface RecordingSession {
  id: string;
  interactionId: string;
  captureSessionId: string;
  recordingType: RecordingType;
  recordingSource: RecordingSource | null;
  lifecycleStatus: RecordingLifecycleStatus;
  consentState: "acknowledged";
  startedAt: string | null;
  stoppedAt: string | null;
  durationSeconds: number | null;
  expectedMimeType: RecordingMimeType;
  finalMimeType: RecordingMimeType | null;
  totalBytes: number;
  chunkCount: number;
  uploadCompletedAt: string | null;
  transcriptionStatus: RecordingTranscriptionStatus;
  transcriptionAttempts: number;
  failureCode: string | null;
  autoIntelligenceStatus: "disabled" | "not_requested" | "requested" | "failed";
  sessionExpiresAt: string;
  providerMode: "mock" | "openai";
  externalProcessing: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface RecordingChunkUpload {
  id: string;
  recordingSessionId: string;
  sequenceNumber: number;
  byteSize: number;
  checksumSha256: string;
  uploadState:
    | "pending"
    | "uploaded"
    | "verified"
    | "deletion_pending"
    | "delete_failed"
    | "deleted";
  uploadedAt: string | null;
  createdAt: string;
  uploadUrl: string;
  uploadExpiresAt: string;
}

export interface RecordingTranscriptSegment {
  sequenceNumber: number;
  startMs: number;
  endMs: number;
  speakerLabel: string | null;
  text: string;
  sourceConfidence: string | null;
}

export interface RecordingTranscription {
  recordingId: string;
  status: RecordingTranscriptionStatus;
  transcriptVersionId: string | null;
  transcriptId: string | null;
  meetingId: string | null;
  version: number | null;
  source: "recorded_audio" | "uploaded_audio" | "imported_audio" | null;
  language: string | null;
  text: string | null;
  segments: RecordingTranscriptSegment[];
  completedAt: string | null;
  safeMessage: string;
}

export interface OnlineMeetingCapabilities {
  meetingPlatform: OnlineMeetingPlatform;
  recordingImport: boolean;
  transcriptImport: boolean;
  nativeFetch: false;
  aiDebrief: boolean;
  voiceJournal: boolean;
  nativeConnectionState: "not_configured";
  safeMessage: string;
}

export interface OnlineMeetingTranscriptSegment {
  sequenceNumber: number;
  startMs: number;
  endMs: number;
  speakerLabel: string | null;
  text: string;
}

export interface OnlineMeetingTranscriptImport {
  id: string;
  interactionId: string;
  captureSessionId: string;
  meetingId: string;
  transcriptVersionId: string;
  transcriptId: string;
  meetingPlatform: OnlineMeetingPlatform;
  provenance: TranscriptProvenance;
  sourceFormat: "txt" | "vtt" | "srt";
  language: string;
  version: number;
  characterCount: number;
  timestampsPresent: boolean;
  speakerLabelsPresent: boolean;
  importedAt: string;
  duplicate: boolean;
  text: string;
  segments: OnlineMeetingTranscriptSegment[];
  safeMessage: string;
}

export type MethodologyKey = "meddic" | "meddpicc" | "bant" | "spiced";
export type MethodologySelection = "none" | MethodologyKey | "custom";
export type MethodologyState =
  "confirmed" | "partially_supported" | "unknown" | "conflicting" | "stale";

export interface MethodologyFieldDefinition {
  key: string;
  displayName: string;
  explanation: string;
  order: number;
  required: boolean;
  evidenceExpectations: string[];
  canonicalFacts: string[];
  evidenceCategories: string[];
  freshnessDays: number | null;
  suggestedQuestions: string[];
  stageExpectation: OpportunityStage | null;
}

export interface MethodologyDefinitionSummary {
  id: string | null;
  key: string;
  name: string;
  description: string;
  version: number;
  standard: boolean;
  status: "active" | "archived";
  fieldCount: number;
  fields: MethodologyFieldDefinition[];
  createdAt: string | null;
}

export interface MethodologySelectionResponse {
  selection: MethodologySelection;
  customDefinitionId: string | null;
  effectiveDefinition: MethodologyDefinitionSummary | null;
  updatedAt: string | null;
}

export interface MethodologyCatalogueResponse {
  standards: MethodologyDefinitionSummary[];
  custom: MethodologyDefinitionSummary[];
  current: MethodologySelectionResponse;
  customMethodologyLimit: number;
  fieldLimit: number;
  executableRulesSupported: false;
}

export interface MethodologySourceReference {
  sourceType:
    | "ai_artifact"
    | "accepted_evidence"
    | "interaction_intelligence"
    | "opportunity_state"
    | "methodology_review";
  sourceId: string;
  itemKey: string;
  label: string;
  origin:
    | "customer_direct"
    | "salesperson_reported"
    | "system_metadata"
    | "imported_external"
    | "seller_prepared"
    | "validated_intelligence";
  supportedAt: string;
  sourceClassification: string;
}

export interface MethodologyProjectionItem {
  fieldKey: string;
  displayName: string;
  explanation: string;
  required: boolean;
  state: MethodologyState;
  conclusion: string | null;
  sources: MethodologySourceReference[];
  conflicts: MethodologySourceReference[];
  lastSupportedAt: string | null;
  freshness: "current" | "stale" | "not_applicable";
  suggestedQuestion: string | null;
  stageExpectation: OpportunityStage | null;
  reviews: Array<{
    action:
      | "confirm_interpretation"
      | "clarify"
      | "mark_not_known"
      | "mark_incorrect";
    reviewedAt: string;
    reviewedByUserId: string;
    clarificationEvidenceId: string | null;
  }>;
}

export interface MethodologyStateCounts {
  confirmed: number;
  partiallySupported: number;
  unknown: number;
  conflicting: number;
  stale: number;
}

export interface MethodologyProjectionContent {
  opportunityId: string;
  methodologyKey: string;
  methodologyName: string;
  definitionVersion: number;
  projectionVersion: number;
  engineVersion: number;
  stateCounts: MethodologyStateCounts;
  items: MethodologyProjectionItem[];
  generatedAt: string;
}

export interface OpportunityMethodologyResponse {
  state:
    | "disabled"
    | "not_configured"
    | "not_generated"
    | "current"
    | "needs_refresh";
  generationAvailable: boolean;
  needsRefresh: boolean;
  safeMessage: string;
  definition: MethodologyDefinitionSummary | null;
  projectionId: string | null;
  projection: MethodologyProjectionContent | null;
  generatedAt: string | null;
}

export interface MethodologyGenerationResponse extends OpportunityMethodologyResponse {
  created: boolean;
  reused: boolean;
}

export interface MethodologyHistoryResponse {
  currentProjectionId: string | null;
  items: Array<{
    id: string;
    methodologyKey: string;
    methodologyName: string;
    definitionVersion: number;
    projectionVersion: number;
    stateCounts: MethodologyStateCounts;
    generatedAt: string;
    projection: MethodologyProjectionContent;
  }>;
}

export interface OpportunityWorkspaceResponse {
  opportunity: OpportunityWorkspaceOpportunity;
  reasoning: RevenueBrainReasoningResponse;
  latestMeeting: OpportunityMeetingSummary | null;
  recentMeetings: OpportunityMeetingSummary[];
  intelligence: MeetingIntelligenceResponse | null;
  reportedIntelligence: ReportedInteractionIntelligence | null;
  visualIntelligence: VisualInteractionIntelligence | null;
  latestInteractionCapture: OpportunityInteractionCaptureStatus | null;
  methodology: OpportunityMethodologyResponse;
  intelligenceSectionsAvailable: number;
  partialData: boolean;
  generatedAt: string;
}

export type InteractionCaptureStatus =
  | "planned"
  | "interaction_in_progress"
  | "processing_transcription"
  | "recording_needs_attention"
  | "debrief_review_required"
  | "mixed_capture_complete"
  | "recorded_and_processed"
  | "debrief_completed"
  | "visual_evidence_captured"
  | "interaction_completed";

export interface OpportunityInteractionCaptureStatus {
  interactionId: string;
  title: string;
  interactionType: InteractionType;
  lifecycleStatus: InteractionLifecycleStatus;
  captureStatus: InteractionCaptureStatus;
  recordingStatus: string | null;
  recordingDurationSeconds: number | null;
  debriefStatus: string | null;
  visualCount: number;
  markerCount: number;
  updatedAt: string;
}

export type ActionType =
  | "follow_up_email"
  | "personalized_outreach"
  | "send_requested_material"
  | "create_task"
  | "follow_up_stakeholder"
  | "schedule_interaction"
  | "update_opportunity"
  | "update_contact"
  | "log_interaction"
  | "update_stakeholder"
  | "add_decision"
  | "add_commitment"
  | "add_risk"
  | "update_timeline"
  | "update_procurement"
  | "update_security_legal"
  | "create_reminder"
  | "notify_internal"
  | "prepare_next_interaction"
  | "resolve_open_question"
  | "review_conflict"
  | "other";
export type ActionStatus =
  | "proposed"
  | "edited"
  | "approved"
  | "rejected"
  | "superseded"
  | "completed_manually";
export type ActionPriority = "high" | "normal" | "low";
export type ActionAudience = "internal" | "customer_facing";
export type ActionRiskClass =
  "internal_low_risk" | "external_customer_facing" | "data_mutation";
export type ActionRejectionReason =
  | "already_done"
  | "incorrect"
  | "not_relevant"
  | "unsupported"
  | "duplicate"
  | "not_now"
  | "other";

interface ActionPayloadBase {
  kind: ActionType;
}

export interface FollowUpEmailActionPayload extends ActionPayloadBase {
  kind: "follow_up_email";
  draftArtifactId: string;
  recipientContactId: string | null;
  recipientEmail: string | null;
  recipientConfirmed: boolean;
  subject: string;
  body: string;
}

export interface CreateTaskActionPayload extends ActionPayloadBase {
  kind: "create_task";
  title: string;
  ownerName: string | null;
  ownerUserId: string | null;
  dueAt: string | null;
  context: string;
  linkedOpportunityId: string;
  linkedInteractionId: string | null;
}

export interface LogInteractionActionPayload extends ActionPayloadBase {
  kind: "log_interaction";
  interactionId: string;
  occurredAt: string;
  interactionType: InteractionType;
  title: string;
  summary: string;
  agreedNextSteps: string[];
}

export type ActionPayload =
  | FollowUpEmailActionPayload
  | CreateTaskActionPayload
  | LogInteractionActionPayload
  | ({
      kind: Exclude<
        ActionType,
        "follow_up_email" | "create_task" | "log_interaction"
      >;
    } & Record<string, unknown>);

export interface ActionSourceReference {
  sourceType:
    | "ai_artifact"
    | "accepted_evidence"
    | "interaction_intelligence"
    | "revenue_brain_insight"
    | "methodology_projection";
  sourceId: string;
  itemKey: string;
  label: string;
  origin:
    | "customer_direct"
    | "salesperson_reported"
    | "validated_intelligence"
    | "revenue_brain"
    | "methodology";
}

export interface ActionProposal {
  id: string;
  organisationId: string;
  opportunityId: string;
  interactionId: string | null;
  actionType: ActionType;
  status: ActionStatus;
  priority: ActionPriority;
  audience: ActionAudience;
  riskClass: ActionRiskClass;
  currentVersion: number;
  approvedVersion: number | null;
  title: string;
  description: string;
  proposedDueAt: string | null;
  targetEntityType: string | null;
  targetEntityId: string | null;
  proposedPayload: ActionPayload;
  sourceRefs: ActionSourceReference[];
  provenanceSummary: string;
  generatedAt: string;
  versionCreatedAt: string;
  createdByUserId: string;
  reviewedByUserId: string | null;
  reviewedAt: string | null;
  approvedAt: string | null;
  rejectedAt: string | null;
  rejectionReasonCode: ActionRejectionReason | null;
  supersedesActionId: string | null;
  completedByUserId: string | null;
  completedAt: string | null;
  executionState: "not_executed";
  sendReady: false;
}

export interface ActionListResponse {
  items: ActionProposal[];
  total: number;
}

export interface ActionGenerationResponse {
  actions: ActionProposal[];
  createdCount: number;
  reusedCount: number;
  supersededCount: number;
  proposalLimit: number;
  providerCompositionUsed: false;
  externalActionsExecuted: false;
}

export type ConnectorKey =
  "mock_email" | "mock_calendar" | "mock_crm" | "mock_task" | "hubspot";
export type ConnectorCapability =
  | "send_email"
  | "create_calendar_event"
  | "update_opportunity"
  | "update_contact"
  | "create_activity"
  | "create_task"
  | "post_internal_message"
  | "upload_or_share_document";
export type ConnectionStatus =
  "active" | "reauthorisation_required" | "revoked";
export type ExecutionStatus =
  | "queued"
  | "executing"
  | "simulated_success"
  | "succeeded"
  | "failed_retryable"
  | "failed_permanent"
  | "cancelled"
  | "unknown_external_state";

export interface ConnectorDefinition {
  connectorKey: ConnectorKey;
  displayName: string;
  providerFamily: "mock" | "crm";
  supportedCapabilities: ConnectorCapability[];
  authenticationType: "mock_local" | "oauth2_authorisation_code";
  executionRiskClasses: ActionRiskClass[];
  configurationSchemaVersion: number;
  executionMode: "simulation" | "live";
  available: boolean;
  simulationOnly: boolean;
}

export interface IntegrationCatalogResponse {
  connectors: ConnectorDefinition[];
  executionMode: "simulation" | "mixed";
  externalActionsEnabled: boolean;
}

export interface OrganisationConnection {
  id: string;
  connectorKey: ConnectorKey;
  displayName: string;
  connectionStatus: ConnectionStatus;
  supportedCapabilities: ConnectorCapability[];
  capabilityState: ConnectorCapability[];
  createdByUserId: string;
  connectedAt: string;
  lastVerifiedAt: string | null;
  revokedAt: string | null;
  externalAccountId: string | null;
  externalAccountName: string | null;
  grantedScopes: string[];
  metadataVersion: number;
  executionMode: "simulation" | "live";
  simulationOnly: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConnectionListResponse {
  items: OrganisationConnection[];
  total: number;
}

export interface ActionExecutionOption {
  connectionId: string;
  connectorKey: ConnectorKey;
  connectorDisplayName: string;
  capability: ConnectorCapability;
  riskClass: ActionRiskClass;
  executionMode: "simulation" | "live";
  simulationOnly: boolean;
}

export interface ActionExecutionOptionListResponse {
  items: ActionExecutionOption[];
  total: number;
}

export type ExecutionPreviewContent =
  | {
      kind: "email";
      senderName?: string;
      senderEmail?: string;
      recipientName?: string;
      recipient: string;
      subject: string;
      body: string;
      action: "send_email";
    }
  | {
      kind: "calendar";
      event: string;
      participantContactIds: string[];
      participants: {
        contactId: string;
        displayName: string;
        email: string;
      }[];
      scheduledAt: string;
      timezone: string;
      purpose: string;
      action: "create_calendar_event";
    }
  | {
      kind: "crm";
      targetType: "opportunity" | "contact";
      targetId: string;
      field: string;
      currentExternalValue: string | number | null;
      expectedExternalValue: string | number | null;
      newValue: string | number | null;
      fieldAuthority:
        | "crm_authoritative"
        | "revenueos_authoritative"
        | "review_before_sync"
        | null;
      externalUpdatedAt: string | null;
      action: "update_opportunity" | "update_contact";
    }
  | {
      kind: "crm_activity";
      interactionId: string;
      occurredAt: string;
      title: string;
      summary: string;
      agreedNextSteps: string[];
      rawTranscriptIncluded: false;
      action: "create_activity";
    }
  | {
      kind: "task";
      title: string;
      ownerUserId: string | null;
      dueAt: string | null;
      opportunityId: string;
      context: string;
      action: "create_task";
    };

export interface ExecutionPreview {
  id: string;
  actionProposalId: string;
  actionVersion: number;
  connectionId: string;
  connectorKey: ConnectorKey;
  connectorDisplayName: string;
  capability: ConnectorCapability;
  riskClass: ActionRiskClass;
  executionMode: "simulation" | "live";
  simulationOnly: boolean;
  readiness: "ready";
  summary: string;
  confirmationLabel: string;
  previewFingerprint: string;
  content: ExecutionPreviewContent;
  expiresAt: string;
  createdAt: string;
}

export interface ActionExecution {
  id: string;
  actionProposalId: string;
  actionVersion: number;
  connectionId: string;
  connectorKey: ConnectorKey;
  connectorDisplayName: string;
  capability: ConnectorCapability;
  riskClass: ActionRiskClass;
  executionStatus: ExecutionStatus;
  executionMode: "simulation" | "live";
  simulationOnly: boolean;
  confirmedByUserId: string;
  confirmedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  safeFailureCode: string | null;
  externalResultId: string | null;
  attemptCount: number;
  retryable: boolean;
  safeMessage: string;
  createdAt: string;
  updatedAt: string;
}

export interface ActionExecutionListResponse {
  items: ActionExecution[];
  total: number;
}

export interface OAuthStartResponse {
  authorisationUrl: string;
  expiresAt: string;
}

export type CRMObjectType = "company" | "contact" | "deal";

export interface CRMSearchResult {
  externalObjectType: CRMObjectType;
  externalObjectId: string;
  displayName: string;
  secondaryLabel: string | null;
  updatedAt: string | null;
}

export interface CRMSearchResponse {
  items: CRMSearchResult[];
  total: number;
}

export interface CRMEntityMapping {
  id: string;
  connectionId: string;
  connectorKey: "hubspot";
  revenueosEntityType: "company" | "contact" | "opportunity";
  revenueosEntityId: string;
  externalObjectType: CRMObjectType;
  externalObjectId: string;
  externalUpdatedAt: string | null;
  lastSyncedAt: string | null;
  syncState: "active" | "external_missing";
  createdAt: string;
  updatedAt: string;
}

export interface CRMPropertyDefinition {
  entityType: "opportunity" | "contact";
  externalPropertyName: string;
  label: string;
  propertyType: "string" | "number" | "date" | "datetime" | "enumeration";
  options: { label: string; value: string }[];
  readOnly: boolean;
}

export interface CRMFieldMapping {
  id: string;
  connectionId: string;
  entityType: "opportunity" | "contact";
  revenueosField: string;
  externalPropertyName: string;
  externalPropertyType:
    "string" | "number" | "date" | "datetime" | "enumeration";
  authority:
    "crm_authoritative" | "revenueos_authoritative" | "review_before_sync";
  enabled: boolean;
}

export interface CRMFieldConfiguration {
  properties: CRMPropertyDefinition[];
  mappings: CRMFieldMapping[];
}

export interface CRMStageDefinition {
  pipelineId: string;
  pipelineLabel: string;
  stageId: string;
  stageLabel: string;
}

export interface CRMStageMapping {
  revenueosStage: string;
  externalPipelineId: string;
  externalStageId: string;
}

export interface CRMStageConfiguration {
  availableStages: CRMStageDefinition[];
  mappings: CRMStageMapping[];
}

export type AskScopeType = "opportunity" | "account" | "workspace";
export type AskQuestionClass =
  | "deal_summary"
  | "blocker_risk"
  | "stakeholder"
  | "methodology"
  | "timeline"
  | "commitment"
  | "action"
  | "buying_signal"
  | "objection"
  | "competitor"
  | "decision"
  | "customer_request"
  | "security_legal"
  | "procurement"
  | "pricing_commercial"
  | "recent_change"
  | "evidence_lookup"
  | "opportunity_filter"
  | "daily_focus"
  | "unsupported_public_web"
  | "general_sales_question";
export type AskAnswerStatus =
  "supported" | "partially_supported" | "conflicting" | "unknown";

export interface AskScope {
  type: AskScopeType;
  id: string | null;
  label: string;
}

export interface AskSource {
  id: string;
  sourceType:
    | "interaction"
    | "accepted_evidence"
    | "methodology"
    | "revenue_brain"
    | "action"
    | "daily"
    | "opportunity";
  label: string;
  occurredAt: string | null;
  excerpt: string | null;
  provenance:
    | "customer_direct"
    | "salesperson_reported"
    | "seller_prepared"
    | "imported_external"
    | "validated_intelligence"
    | "system_metadata";
  href: string;
}

export interface AskSummaryPoint {
  text: string;
  sourceIds: string[];
}

export interface AskSuggestedAction {
  label: string;
  href: string;
  sourceId: string | null;
}

export interface AskAnswer {
  schemaVersion: 1;
  askRequestId: string;
  answer: string;
  answerStatus: AskAnswerStatus;
  questionClass: AskQuestionClass;
  summaryPoints: AskSummaryPoint[];
  sources: AskSource[];
  uncertainties: string[];
  suggestedAction: AskSuggestedAction | null;
  followUpQuestions: string[];
  scope: AskScope;
  generatedAt: string;
}

export interface AskCapabilities {
  enabled: boolean;
  scope: AskScope;
  supportedScopes: AskScopeType[];
  retainedHistory: false;
  publicWebResearch: false;
  actionExecution: false;
  maxQuestionCharacters: number;
  maxSources: number;
  safeMessage: string;
}

export type ProspectAvailabilityState =
  "available" | "temporarily_unavailable" | "not_in_plan";
export type ProspectTrustState =
  "verified" | "provider_supplied" | "inferred" | "unknown";
export type ProspectResearchStatus =
  "not_started" | "pending" | "researching" | "ready" | "partial" | "failed";
export type ProspectRunStatus =
  "pending" | "fetching" | "synthesizing" | "completed" | "partial" | "failed";

export interface ProspectAvailability {
  moduleKey: "prospect";
  state: ProspectAvailabilityState;
  enabled: boolean;
  canManage: boolean;
  message: string;
}

export type OutreachPurpose =
  | "introduction"
  | "request_meeting"
  | "share_relevant_information"
  | "re_engage";

export type OutreachContactability =
  | "allowed"
  | "no_business_email"
  | "email_trust_unknown"
  | "provider_supplied_blocked"
  | "suppressed"
  | "cooldown"
  | "quota_reached"
  | "policy_not_configured"
  | "outbound_disabled"
  | "engage_unavailable"
  | "sender_disabled";

export interface EngageAvailability {
  moduleKey: "engage";
  state: ProspectAvailabilityState;
  enabled: boolean;
  canManage: boolean;
  message: string;
}

export interface OutreachPolicy {
  version: number;
  configured: boolean;
  outboundEnabled: boolean;
  providerSuppliedEmailAllowed: boolean;
  campaignAutoSendAllowed: boolean;
  cooldownHours: number;
  maxDailySendsUser: number;
  maxDailySendsOrg: number;
  requireOptOutMechanism: boolean;
  offeringName: string | null;
  valueProposition: string | null;
  approvedCta: string | null;
  canManage: boolean;
  complianceNotice: string;
}

export interface Contactability {
  state: OutreachContactability;
  allowed: boolean;
  reason: string;
  trustState: "verified" | "provider_supplied" | "unknown";
  permissionAssessedSeparately: true;
}

export interface OutreachSource {
  id: string;
  sourceType:
    | "prospect_observation"
    | "prospect_person_observation"
    | "approved_seller_context"
    | "event_attendance"
    | "event_encounter";
  sourceId: string;
  label: string;
  trustState: "verified" | "provider_supplied" | "approved" | "seller_reported";
  publisher: string | null;
  publishedAt: string | null;
  url: string | null;
}

export interface OutreachVersion {
  id: string;
  version: number;
  subject: string;
  body: string;
  senderName: string;
  senderEmail: string;
  recipientName: string;
  recipientEmail: string;
  recipientTrust: "verified" | "provider_supplied";
  creationType: "generated" | "user_edited";
  composerVersion: string;
  personalizationUsed: boolean;
  sources: OutreachSource[];
  warnings: string[];
  createdAt: string;
}

export interface OutreachExecutionSummary {
  id: string;
  status:
    | "queued"
    | "sending"
    | "submitted"
    | "sent"
    | "failed"
    | "unknown_delivery_state"
    | "cancelled"
    | "simulated";
  simulationOnly: boolean;
  safeMessage: string;
  createdAt: string;
  completedAt: string | null;
}

export interface OutreachMessage {
  id: string;
  actionId: string;
  contactId: string | null;
  purpose: OutreachPurpose;
  state: "draft" | "approved" | "cancelled";
  currentVersion: number;
  approvedVersion: number | null;
  version: OutreachVersion;
  contactability: Contactability;
  relationshipWarning: string | null;
  execution: OutreachExecutionSummary | null;
  createdAt: string;
  updatedAt: string;
}

export interface OutreachHistoryItem {
  id: string;
  purpose: OutreachPurpose;
  subject: string;
  status: string;
  simulationOnly: boolean;
  createdAt: string;
  completedAt: string | null;
}

export interface ContactOutreachWorkspace {
  availability: EngageAvailability;
  contactId: string;
  contactName: string;
  companyId: string;
  companyName: string;
  jobTitle: string | null;
  email: string | null;
  emailTrust: "verified" | "provider_supplied" | "unknown";
  permissionStatus: "assessed_by_organisation_policy" | "not_assessed";
  contactability: Contactability;
  policyConfigured: boolean;
  productionMailboxAvailable: false;
  simulationAvailable: boolean;
  history: OutreachHistoryItem[];
}

export type CampaignState =
  | "draft"
  | "ready"
  | "active"
  | "paused"
  | "completed"
  | "stopped"
  | "needs_attention";
export type CampaignApprovalMode =
  "review_each_send" | "approved_campaign_auto_send";
export type CampaignEnrollmentState =
  | "ready"
  | "active"
  | "paused"
  | "stopped"
  | "completed"
  | "blocked"
  | "needs_attention";
export type CampaignStepState =
  | "pending"
  | "processing"
  | "ready_for_review"
  | "prepared"
  | "queued"
  | "sent"
  | "deferred"
  | "blocked"
  | "cancelled"
  | "unknown_delivery_state";
export type CampaignStepObjective =
  | "introduction"
  | "follow_up"
  | "share_relevant_information"
  | "different_angle"
  | "meeting_request"
  | "final_follow_up";
export type CampaignOutcome = "replied" | "meeting_booked" | "not_interested";

export interface CampaignSequenceStep {
  id: string;
  stepOrder: number;
  delayDays: number;
  objective: CampaignStepObjective;
  contentStrategy: string;
  enabled: boolean;
}

export interface CampaignAudienceItem {
  id: string;
  contactId: string | null;
  companyId: string | null;
  recipientName: string;
  recipientEmail: string | null;
  recipientTrust: "verified" | "provider_supplied" | "unknown";
  eligible: boolean;
  eligibilityCode: string;
  eligibilityReason: string;
}

export interface CampaignMetrics {
  recipients: number;
  active: number;
  completed: number;
  stopped: number;
  blocked: number;
  needsAttention: number;
  messagesSent: number;
  messagesReadyForReview: number;
  messagesFailed: number;
  repliesReported: number;
  meetingsReported: number;
}

export interface CampaignListItem {
  id: string;
  name: string;
  purpose: string;
  state: CampaignState;
  approvalMode: CampaignApprovalMode;
  ownerUserId: string;
  audienceCount: number;
  eligibleCount: number;
  blockedCount: number;
  currentVersion: number;
  launchedAt: string | null;
  updatedAt: string;
}

export interface CampaignListResponse {
  items: CampaignListItem[];
  total: number;
  canCreate: boolean;
  simulationOnly: boolean;
  productionMailboxAvailable: false;
}

export interface Campaign {
  id: string;
  versionId: string;
  version: number;
  name: string;
  purpose: string;
  state: CampaignState;
  approvalMode: CampaignApprovalMode;
  ownerUserId: string;
  senderUserId: string;
  sourceType: "manual_contacts" | "target_market" | "event_attendees";
  eventId: string | null;
  eventStage: "pre_event" | "post_event" | null;
  senderTimezone: string;
  sendDays: number[];
  sendWindowStartMinutes: number;
  sendWindowEndMinutes: number;
  stopOnActiveOpportunity: boolean;
  policyVersion: number | null;
  audienceCount: number;
  eligibleCount: number;
  blockedCount: number;
  steps: CampaignSequenceStep[];
  audience: CampaignAudienceItem[];
  metrics: CampaignMetrics;
  canManage: boolean;
  canLaunch: boolean;
  campaignAutoSendAllowed: boolean;
  simulationOnly: boolean;
  productionMailboxAvailable: false;
  launchWarning: string | null;
  needsAttentionReason: string | null;
  launchedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CampaignEnrollmentStep {
  id: string;
  stepOrder: number;
  objective: CampaignStepObjective;
  scheduledAt: string;
  state: CampaignStepState;
  safeStatusCode: string | null;
  outreachMessageId: string | null;
  preparedAt: string | null;
  sentAt: string | null;
}

export interface CampaignEnrollment {
  id: string;
  campaignId: string;
  contactId: string | null;
  companyId: string | null;
  recipientName: string;
  recipientEmail: string;
  recipientTrust: "verified" | "provider_supplied";
  state: CampaignEnrollmentState;
  currentStepOrder: number;
  nextScheduledAt: string | null;
  stopReason: string | null;
  outcome: CampaignOutcome | null;
  outcomeProvenance: "seller_reported" | null;
  steps: CampaignEnrollmentStep[];
  currentOutreach: OutreachMessage | null;
  createdAt: string;
  updatedAt: string;
}

export interface CampaignEnrollmentListResponse {
  items: CampaignEnrollment[];
  total: number;
}

export interface ProspectCompanyCandidate {
  candidateId: string;
  name: string;
  domain: string;
  websiteUrl: string;
  location: string | null;
  industry: string | null;
  providerAttribution: string;
}

export interface ProspectCompanySearch {
  items: ProspectCompanyCandidate[];
  query: string;
  ambiguous: boolean;
}

export interface ProspectResearchTarget {
  id: string;
  name: string;
  domain: string;
  websiteUrl: string;
  location: string | null;
  industry: string | null;
  providerAttribution: string;
  promotedCompanyId: string | null;
  promotedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProspectResearchRun {
  id: string;
  status: ProspectRunStatus;
  refreshOfRunId: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  sourceCount: number;
  observationCount: number;
  errorCode: string | null;
}

export interface ProspectResearchSource {
  id: string;
  sourceType: string;
  url: string;
  canonicalUrl: string;
  domain: string;
  title: string;
  publisher: string;
  publishedAt: string | null;
  retrievedAt: string;
  authorityClass: string;
}

export interface ProspectResearchObservation {
  id: string;
  observationKey: string;
  category: string;
  statement: string;
  trustState: ProspectTrustState;
  relevance: "high" | "normal";
  observedAt: string | null;
  freshness: "stable" | "time_sensitive";
  sourceIds: string[];
}

export interface ProspectResearchChange {
  changeType: "new" | "changed" | "no_longer_supported";
  observationKey: string;
  statement: string;
  previousStatement: string | null;
}

export interface ProspectExistingCompanyMatch {
  id: string;
  name: string;
  domain: string;
}

export interface ProspectResearchBrief {
  target: ProspectResearchTarget;
  status: ProspectResearchStatus;
  statusMessage: string;
  currentRun: ProspectResearchRun | null;
  latestRun: ProspectResearchRun | null;
  observations: ProspectResearchObservation[];
  sources: ProspectResearchSource[];
  changes: ProspectResearchChange[];
  history: ProspectResearchRun[];
  existingCompanyMatch: ProspectExistingCompanyMatch | null;
}

export interface ProspectRecentResearch {
  items: Array<{
    target: ProspectResearchTarget;
    status: ProspectResearchStatus;
    updatedAt: string;
  }>;
}

export interface ProspectPromotion {
  status: "created" | "attached" | "already_promoted";
  companyId: string;
  companyName: string;
  researchTargetId: string;
  message: string;
}

export interface ProspectAccountResearchLink {
  targetId: string;
  companyId: string;
  updatedAt: string;
  status: "ready" | "partial";
}

export type ProspectTargetMarketStatus = "draft" | "active" | "archived";
export type ProspectEmployeeBand =
  "50_199" | "200_499" | "500_999" | "1000_4999" | "5000_plus";
export type ProspectOrganisationType =
  | "private_company"
  | "public_company"
  | "government"
  | "education"
  | "healthcare"
  | "not_for_profit";
export type ProspectBusinessCharacteristic =
  "multi_site" | "international" | "expanding" | "regulated" | "b2b";
export type ProspectDiscoveryStatus =
  "pending" | "running" | "completed" | "partial" | "failed";
export type ProspectCandidatePriority =
  "high" | "worth_researching" | "needs_more_information" | "excluded";
export type ProspectCandidateMatchState = "match" | "partial" | "excluded";
export type ProspectRelationshipState =
  | "new_prospect"
  | "existing_account_no_active_opportunity"
  | "active_opportunity";

export interface ProspectDiscoveryCapabilities {
  industries: string[];
  countries: string[];
  regions: string[];
  employeeBands: ProspectEmployeeBand[];
  organisationTypes: ProspectOrganisationType[];
  businessCharacteristics: ProspectBusinessCharacteristic[];
  maxCandidatesPerRun: number;
  maxActiveTargetMarkets: number;
  liveData: boolean;
  message: string;
}

export interface ProspectTargetMarketVersion {
  id: string;
  version: number;
  description: string | null;
  industries: string[];
  countries: string[];
  regions: string[];
  minimumEmployeeBand: ProspectEmployeeBand | null;
  organisationTypes: ProspectOrganisationType[];
  preferredBusinessCharacteristics: ProspectBusinessCharacteristic[];
  excludedIndustries: string[];
  excludeExistingAccounts: boolean;
  researchObjective: string | null;
  createdAt: string;
}

export interface ProspectDiscoveryRun {
  id: string;
  targetMarketId: string;
  targetMarketVersionId: string;
  targetMarketVersion: number;
  status: ProspectDiscoveryStatus;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  candidateCount: number;
  eligibleCount: number;
  excludedCount: number;
  partialCount: number;
  failureCode: string | null;
  refreshedFromRunId: string | null;
}

export interface ProspectTargetMarket {
  id: string;
  name: string;
  status: ProspectTargetMarketStatus;
  currentVersion: number;
  canManage: boolean;
  definition: ProspectTargetMarketVersion;
  latestRun: ProspectDiscoveryRun | null;
  recentRuns: ProspectDiscoveryRun[];
  createdAt: string;
  updatedAt: string;
}

export interface ProspectTargetMarketList {
  items: ProspectTargetMarket[];
  activeLimit: number;
  canCreate: boolean;
}

export interface ProspectCandidateReason {
  reasonCode: string;
  criterionKey: string;
  state: "matched" | "missing" | "excluded" | "context";
  text: string;
  dataOrigin:
    | "provider_supplied"
    | "verified_research"
    | "existing_revenueos_data"
    | "unknown";
  trustState: ProspectTrustState;
  observedValueClass: string | null;
  sourceReference: string | null;
}

export interface ProspectDiscoveryCandidate {
  id: string;
  prospectTargetId: string;
  providerCandidateId: string;
  companyName: string;
  domain: string;
  location: string | null;
  industry: string | null;
  employeeBand: ProspectEmployeeBand | null;
  matchState: ProspectCandidateMatchState;
  priority: ProspectCandidatePriority;
  reasons: ProspectCandidateReason[];
  missingInformation: string[];
  relationshipState: ProspectRelationshipState;
  matchedCompanyId: string | null;
  activeOpportunityId: string | null;
  saved: boolean;
  excludedByUser: boolean;
  exclusionReason: string | null;
  researchStatus:
    "not_started" | "pending" | "researching" | "ready" | "partial" | "failed";
}

export interface ProspectDiscovery {
  targetMarket: ProspectTargetMarket;
  run: ProspectDiscoveryRun;
  summary: {
    totalCandidates: number;
    highPriority: number;
    worthResearching: number;
    needsMoreInformation: number;
    excluded: number;
    existingAccounts: number;
    activeOpportunities: number;
    newProspects: number;
  };
  candidates: ProspectDiscoveryCandidate[];
  message: string;
  highPriorityExplanation: string;
}

export interface ProspectCandidateFeedback {
  prospectTargetId: string;
  saved: boolean;
  excludedByUser: boolean;
  exclusionReason: string | null;
}

export type ProspectPersonEmploymentState =
  "current" | "uncertain" | "no_longer_current";
export type ProspectBuyingRole =
  | "executive_sponsor"
  | "economic_buyer_candidate"
  | "champion_candidate"
  | "business_buyer"
  | "technical_evaluator"
  | "security"
  | "procurement"
  | "legal"
  | "finance"
  | "end_user_influencer"
  | "other_relevant";
export type ProspectContactPointType =
  | "business_email"
  | "business_phone"
  | "company_switchboard"
  | "public_professional_profile";

export interface ProspectRelevantFunction {
  functionKey: string;
  label: string;
  whyItMayMatter: string;
}

export interface ProspectPerson {
  id: string;
  companyTargetId: string;
  displayName: string;
  currentRole: string;
  currentCompany: string;
  publicProfessionalLocation: string | null;
  publicProfileUrl: string | null;
  relevantFunction: string;
  whyMayMatter: string;
  providerAttribution: string;
  identityState: "supported" | "ambiguous";
  employmentState: ProspectPersonEmploymentState;
  researchStatus:
    "not_started" | "pending" | "researching" | "ready" | "partial" | "failed";
  promotedContactId: string | null;
  promotedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProspectBuyingCommitteeGap {
  role: ProspectBuyingRole;
  label: string;
  message: string;
}

export interface ProspectPersonDiscovery {
  companyTargetId: string;
  functions: ProspectRelevantFunction[];
  people: ProspectPerson[];
  gaps: ProspectBuyingCommitteeGap[];
  resultLimit: number;
  message: string;
}

export interface ProspectBuyingRoleHypothesis {
  id: string;
  role: ProspectBuyingRole;
  rationale: string;
  trustState: ProspectTrustState;
  reviewState: "needs_validation" | "relevant" | "not_relevant";
  assessmentOrigin: "system_hypothesis" | "seller_assessed";
  sourceIds: string[];
  reviewedAt: string | null;
}

export interface ProspectContactPoint {
  id: string;
  pointType: ProspectContactPointType;
  value: string;
  trustState: ProspectTrustState;
  verificationMethod:
    "authoritative_public" | "provider_reported" | "not_verified";
  sourceId: string;
  observedAt: string;
  expiresAt: string | null;
  exportAllowed: boolean;
  permissionStatus: "not_assessed";
}

export interface ProspectExistingContactMatch {
  id: string;
  displayName: string;
  email: string | null;
  companyId: string;
  matchStrength: "strong" | "possible";
  matchReason: "exact_business_email" | "same_name_and_company";
}

export interface ProspectPersonResearchBrief {
  person: ProspectPerson;
  status: ProspectResearchStatus;
  statusMessage: string;
  currentRun: ProspectResearchRun | null;
  latestRun: ProspectResearchRun | null;
  observations: ProspectResearchObservation[];
  sources: ProspectResearchSource[];
  buyingRoles: ProspectBuyingRoleHypothesis[];
  contactPoints: ProspectContactPoint[];
  changes: ProspectResearchChange[];
  history: ProspectResearchRun[];
  existingContactMatches: ProspectExistingContactMatch[];
}

export interface ProspectPersonPromotion {
  status: "created" | "attached" | "already_promoted";
  contactId: string;
  companyId: string;
  prospectPersonId: string;
  message: string;
}

export interface ContactProspectResearchLink {
  contactId: string;
  prospectPersonId: string;
  companyTargetId: string;
  updatedAt: string;
  label: "Public professional research";
}

export type SalesEventType =
  | "conference"
  | "trade_show"
  | "networking_event"
  | "customer_event"
  | "partner_event"
  | "industry_event"
  | "executive_roundtable"
  | "internal_hosted_event"
  | "other_business_event";

export type SalesEventState =
  "draft" | "upcoming" | "active" | "completed" | "archived";

export type SalesEventGoal =
  | "meet_new_prospects"
  | "progress_active_opportunities"
  | "meet_strategic_accounts"
  | "reconnect_existing_contacts"
  | "find_partners"
  | "other";

export type EventPlanState =
  "not_planned" | "planned" | "met" | "follow_up" | "complete" | "not_relevant";

export interface SalesEventSummary {
  attendeesImported: number;
  priorityPeople: number;
  planned: number;
  met: number;
  followUp: number;
  addedToSales: number;
  interactionsCaptured: number;
  activeOpportunityContacts: number;
}

export interface EventCampaignLinkSummary {
  campaignId: string;
  name: string;
  state: string;
  stage: "pre_event" | "post_event";
}

export interface SalesEvent {
  id: string;
  name: string;
  eventType: SalesEventType;
  startAt: string;
  endAt: string;
  timezone: string;
  locationName: string | null;
  city: string | null;
  country: string | null;
  eventUrl: string | null;
  organiser: string | null;
  description: string | null;
  goalType: SalesEventGoal | null;
  goalDetail: string | null;
  sourceType: "manual";
  state: SalesEventState;
  ownerUserId: string;
  readOnly: boolean;
  prospectEnrichmentAvailable: boolean;
  summary: SalesEventSummary;
  campaigns: EventCampaignLinkSummary[];
  createdAt: string;
  updatedAt: string;
}

export interface SalesEventList {
  items: SalesEvent[];
  total: number;
  canCreate: boolean;
  readOnly: boolean;
  maxActiveEvents: number;
}

export interface EventImportColumn {
  sourceColumn: string;
  mappedField: string | null;
  reason: string | null;
}

export interface EventImportIssue {
  code: string;
  count: number;
  rows: number[];
  message: string;
}

export interface EventImportPreview {
  id: string;
  eventId: string;
  fileName: string;
  fileSizeBytes: number;
  rowCount: number;
  validRowCount: number;
  recognised: EventImportColumn[];
  ignored: EventImportColumn[];
  issues: EventImportIssue[];
  previewRows: Array<{
    sourceRow: number;
    firstName: string | null;
    lastName: string | null;
    companyName: string | null;
    jobTitle: string | null;
    businessEmail: string | null;
  }>;
  expiresAt: string;
  alreadyImported: boolean;
  authorityStatement: string;
  permissionNotice: string;
}

export interface EventAttendee {
  id: string;
  eventId: string;
  firstName: string | null;
  lastName: string | null;
  displayName: string;
  companyName: string | null;
  jobTitle: string | null;
  businessEmail: string | null;
  emailTrustState: "provider_supplied" | "unknown";
  permissionStatus: "not_assessed";
  countryOrLocation: string | null;
  profileUrl: string | null;
  companyDomain: string | null;
  registrationCategory: string | null;
  matchState:
    | "matched_contact"
    | "matched_prospect_person"
    | "matched_company"
    | "possible_match"
    | "unmatched";
  priorityState:
    | "priority_to_meet"
    | "worth_meeting"
    | "context_only"
    | "needs_more_information";
  priorityReasons: string[];
  contactId: string | null;
  companyId: string | null;
  prospectPersonId: string | null;
  activeOpportunityId: string | null;
  planState: EventPlanState;
  meetingArranged: boolean;
  plannedByTeammateCount: number;
  encounterId: string | null;
  interactionId: string | null;
  sellerNote: string | null;
  canResearch: boolean;
  createdAt: string;
}

export interface EventAttendeeList {
  items: EventAttendee[];
  total: number;
  page: number;
  pageSize: number;
}

export type CreateAvailabilityState =
  "available" | "temporarily_unavailable" | "not_in_plan";
export type CreateTemplateProcessingState =
  "processing" | "ready" | "partial" | "failed" | "archived";
export type CreateSlideCategory =
  | "title"
  | "agenda"
  | "company_overview"
  | "problem"
  | "solution"
  | "product"
  | "capability"
  | "architecture"
  | "case_study"
  | "proof_point"
  | "process"
  | "pricing_placeholder"
  | "next_steps"
  | "appendix"
  | "unknown";
export type CreateModificationPolicy =
  "locked" | "text_placeholders_only" | "editable_text" | "reuse_as_is";
export type CreatePresentationObjective =
  | "introductory_meeting"
  | "discovery_follow_up"
  | "solution_overview"
  | "technical_workshop"
  | "executive_presentation"
  | "proposal_presentation"
  | "business_case"
  | "event_follow_up";
export type ValueUnit =
  | "count"
  | "currency"
  | "currency_per_year"
  | "currency_per_hour"
  | "percentage"
  | "hours"
  | "hours_per_year"
  | "minutes"
  | "days"
  | "months"
  | "years"
  | "dimensionless";
export type BusinessCaseInputOrigin =
  | "validated_customer_evidence"
  | "salesperson_reported"
  | "organisation_assumption"
  | "approved_company_data"
  | "prospect_public"
  | "user_entered"
  | "unknown";

export interface ValueModelInputDefinition {
  key: string;
  label: string;
  description: string;
  valueType:
    | "integer"
    | "decimal"
    | "currency"
    | "percentage"
    | "hours"
    | "days"
    | "minutes"
    | "count";
  unit: ValueUnit;
  required: boolean;
  minimum: string | null;
  maximum: string | null;
  decimalPrecision: number;
  defaultValue: string | null;
  defaultOrigin: "organisation_assumption" | "approved_company_data" | null;
  defaultSourceReference: string | null;
  reviewExpiresOn: string | null;
  maxSourceAgeDays: number | null;
  assumptionLocked: boolean;
  sourcePolicy:
    | "reviewed_manual"
    | "customer_or_manual"
    | "approved_org_only"
    | "public_or_manual";
  customerFacing: boolean;
  material: boolean;
  sensitivityEligible: boolean;
  scenarioPreset: {
    conservative: string | null;
    base: string | null;
    upside: string | null;
  } | null;
  displayOrder: number;
}

export interface ValueModelOutputDefinition {
  key: string;
  label: string;
  description: string;
  formula: string;
  unit: ValueUnit;
  displayPrecision: number;
  customerFacing: boolean;
  highlight: boolean;
  scenarioSensitive: boolean;
  displayOrder: number;
}

export interface ValueModelDefinition {
  inputs: ValueModelInputDefinition[];
  outputs: ValueModelOutputDefinition[];
  customerDisclaimer: string | null;
}

export interface ValueModelVersion {
  id: string;
  version: number;
  state: "draft" | "approved" | "archived";
  definition: ValueModelDefinition;
  formulaEngineVersion: "bounded_decimal_v1";
  fingerprint: string;
  approvedByUserId: string | null;
  approvedAt: string | null;
  createdByUserId: string;
  createdAt: string;
}

export interface ValueModel {
  id: string;
  name: string;
  description: string;
  state: "active" | "archived";
  latestVersion: ValueModelVersion;
  canManage: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ValueModelList {
  items: ValueModel[];
  canManage: boolean;
  maxActiveModels: number;
}

export interface BusinessCaseCalculationInput {
  key: string;
  label: string;
  value: string;
  calculationValue: string;
  unit: ValueUnit;
  origin: BusinessCaseInputOrigin;
  sourceId: string | null;
  sourceLabel: string;
  assumption: boolean;
  material: boolean;
  customerFacing: boolean;
  observedAt: string;
  freshness: "current" | "stale" | "unknown" | "deleted_source";
}

export interface BusinessCaseCalculationOutput {
  key: string;
  label: string;
  description: string;
  unit: ValueUnit;
  exactValue: string | null;
  displayValue: string | null;
  unavailableReason:
    | "division_by_zero"
    | "non_positive_denominator"
    | "dependency_unavailable"
    | null;
  formula: string;
  inputDependencies: string[];
  outputDependencies: string[];
  customerFacing: boolean;
  highlight: boolean;
}

export interface BusinessCaseScenario {
  name: "base" | "conservative" | "upside";
  overrides: Array<{ key: string; value: string }>;
  outputs: BusinessCaseCalculationOutput[];
}

export interface BusinessCaseVersion {
  id: string;
  version: number;
  currency: string;
  modelVersionId: string;
  modelVersion: number;
  formulaEngineVersion: "bounded_decimal_v1";
  modelFingerprint: string;
  calculationFingerprint: string;
  inputs: BusinessCaseCalculationInput[];
  scenarios: BusinessCaseScenario[];
  sensitivity: {
    inputKey: string;
    rows: Array<{
      inputValue: string;
      outputs: BusinessCaseCalculationOutput[];
    }>;
  } | null;
  reviewState: "pending" | "approved" | "needs_review";
  approvedByUserId: string | null;
  approvedAt: string | null;
  createdByUserId: string;
  createdAt: string;
}

export interface BusinessCase {
  id: string;
  title: string;
  accountId: string;
  accountName: string;
  opportunityId: string | null;
  opportunityName: string | null;
  modelId: string;
  modelName: string;
  modelVersionId: string;
  modelVersion: number;
  modelDefinition: ValueModelDefinition;
  currency: string;
  state: "draft" | "calculated" | "needs_review" | "approved" | "archived";
  currentVersion: BusinessCaseVersion | null;
  createdByUserId: string;
  createdAt: string;
  updatedAt: string;
}

export interface BusinessCaseList {
  items: BusinessCase[];
  canCreate: boolean;
  maxActiveCasesPerAccount: number;
}

export interface CreateAvailability {
  moduleKey: "create";
  state: CreateAvailabilityState;
  enabled: boolean;
  canManage: boolean;
  canUploadTemplates: boolean;
  canCreatePresentations: boolean;
  message: string;
  description: string;
  learnMorePath: "/create";
}

export interface CreateTemplateTextBlock {
  shapeId: number;
  shapeName: string;
  text: string;
  placeholderType: string | null;
  editable: boolean;
  mappedRole: string | null;
}

export interface CreateTemplateSlide {
  id: string;
  slideNumber: number;
  title: string;
  category: CreateSlideCategory;
  reuseState: "pending" | "approved" | "excluded";
  modificationPolicy: CreateModificationPolicy;
  customerSafe: boolean;
  required: boolean;
  exactTextRequired: boolean;
  hidden: boolean;
  approvedDescription: string | null;
  textBlocks: CreateTemplateTextBlock[];
  createdAt: string;
  updatedAt: string;
}

export interface CreateApprovedContentItem {
  id: string;
  slideId: string;
  contentType: CreateSlideCategory;
  title: string;
  approvedText: string;
  status: "approved" | "revoked";
  modificationPolicy: CreateModificationPolicy;
  customerSafe: boolean;
  exactTextRequired: boolean;
  approvedByUserId: string;
  approvedAt: string;
}

export interface CreateTemplateVersion {
  id: string;
  templateId: string;
  version: number;
  processingState: CreateTemplateProcessingState;
  approvalState: "pending" | "approved" | "revoked";
  fileName: string;
  byteSize: number;
  checksumSha256: string;
  slideCount: number;
  approvedSlideCount: number;
  requiredSlideCount: number;
  widthEmu: number | null;
  heightEmu: number | null;
  warningCodes: string[];
  safeFailureCode: string | null;
  compatibilityState: "compatible" | "needs_attention" | "unsupported";
  compatibilityDetails: string[];
  validationProfileVersion: 1;
  validatedAt: string | null;
  authorityAttestationVersion: 1;
  authorityAttestedAt: string;
  processedAt: string | null;
  approvedAt: string | null;
  slides: CreateTemplateSlide[];
  contentItems: CreateApprovedContentItem[];
  createdAt: string;
}

export interface CreateTemplateSummary {
  id: string;
  name: string;
  state: "active" | "archived";
  latestVersion: CreateTemplateVersion;
  createdAt: string;
  updatedAt: string;
}

export interface CreateTemplateList {
  items: CreateTemplateSummary[];
  canUpload: boolean;
  maxActiveTemplates: number;
}

export interface CreateAudience {
  contactId: string | null;
  name: string | null;
  role: string | null;
  audienceType:
    "executive" | "technical" | "finance" | "procurement" | "mixed" | "other";
}

export interface CreatePresentationPlanItem {
  id: string;
  templateSlideId: string;
  order: number;
  title: string;
  category: CreateSlideCategory;
  required: boolean;
  exactTextRequired: boolean;
  modificationPolicy: CreateModificationPolicy;
  sourceClasses: string[];
  included: boolean;
}

export interface CreatePresentationClaim {
  id: string;
  planItemId: string;
  blockIndex: number;
  claim: string;
  contentType: string;
  origin: string;
  supportState: string;
  customerSafeClassification:
    "customer_safe" | "requires_review" | "internal_only";
  sourceIds: string[];
  sourceLabels: string[];
  freshness: "current" | "stale" | "unknown";
  paraphraseAllowed: boolean;
  exactTextRequired: boolean;
  reviewState: "not_required" | "pending" | "kept" | "removed";
}

export interface CreateGeneratedSlide {
  planItemId: string;
  templateSlideId: string;
  order: number;
  title: string;
  bodyBlocks: string[];
  required: boolean;
  modificationPolicy: CreateModificationPolicy;
  reviewState: "ready" | "needs_review" | "blocked";
  warningCodes: string[];
}

export interface CreatePresentationVersion {
  id: string;
  version: number;
  state: "generating" | "needs_review" | "ready" | "failed";
  reviewState: "pending" | "approved";
  slides: CreateGeneratedSlide[];
  claims: CreatePresentationClaim[];
  warningCodes: string[];
  safeFailureCode: string | null;
  validationProfileVersion: 1 | null;
  validatedAt: string | null;
  generatedAt: string | null;
  approvedAt: string | null;
  downloadAvailable: boolean;
  createdAt: string;
}

export interface CreatePresentation {
  id: string;
  title: string;
  accountId: string;
  accountName: string;
  opportunityId: string | null;
  opportunityName: string | null;
  objective: CreatePresentationObjective;
  audience: CreateAudience[];
  focusInstruction: string | null;
  templateVersionId: string;
  templateName: string;
  templateVersion: number;
  businessCaseId: string | null;
  businessCaseVersionId: string | null;
  businessCaseScenario: "base" | "all" | null;
  state:
    | "draft_plan"
    | "generating"
    | "needs_review"
    | "ready"
    | "failed"
    | "archived";
  reviewState: "pending" | "approved";
  plan: CreatePresentationPlanItem[];
  currentVersion: CreatePresentationVersion | null;
  createdByUserId: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreatePresentationList {
  items: CreatePresentation[];
  canCreate: boolean;
  maxPresentationsPerUserPerDay: number;
  maxPresentationsPerOrganisationPerDay: number;
}

export interface CreateDownloadGrant {
  downloadUrl: string;
  grantToken: string;
  expiresAt: string;
  fileName: string;
}

export type SalesMetricUnit = "count" | "percent" | "days" | "currency";
export type SalesMetricFilter =
  "date_range" | "timezone" | "pipeline" | "owner" | "currency";

export interface SalesMetricDefinition {
  id: string;
  definitionVersion: string;
  label: string;
  description: string;
  unit: SalesMetricUnit;
  targetable: boolean;
  supportedFilters: SalesMetricFilter[];
  dateSemantics: string;
  numerator: string | null;
  denominator: string | null;
  exclusions: string[];
  sourceDomain: string;
}

export interface SalesInsightsOwner {
  userId: string;
  displayName: string;
  active: boolean;
}

export interface SalesInsightsStage {
  id: string;
  name: string;
  position: number;
  stageType: "open" | "won" | "lost";
  active: boolean;
}

export interface SalesInsightsPipeline {
  id: string;
  name: string;
  isDefault: boolean;
  active: boolean;
  stages: SalesInsightsStage[];
}

export interface SalesInsightsMetadata {
  currentUserId: string;
  pipelines: SalesInsightsPipeline[];
  owners: SalesInsightsOwner[];
  metrics: SalesMetricDefinition[];
  outcomeWindowDays: 30;
  maximumRangeDays: number;
  generatedAt: string;
}

export interface SalesInsightsScope {
  startDate: string;
  endDate: string;
  timezone: string;
  pipelineId: string | null;
  ownerUserId: string | null;
  generatedAt: string;
}

export interface SalesCurrencyAmount {
  currency: string;
  amount: string;
  opportunityCount: number;
}

export interface SalesOverview {
  scope: SalesInsightsScope;
  openOpportunityCount: number;
  opportunitiesCreatedCount: number;
  wonCount: number;
  lostCount: number;
  closedCount: number;
  winRate: string | null;
  medianSalesCycleDays: string | null;
  wonValues: SalesCurrencyAmount[];
  unvaluedWonCount: number;
  hasOpportunities: boolean;
}

export interface SalesFunnelStage {
  stageId: string;
  stageName: string;
  position: number;
  enteredCount: number;
  advancedCount: number;
  stillOpenCount: number;
  closedLostCount: number;
  otherNotAdvancedCount: number;
  advanceRate: string | null;
}

export interface SalesStageDuration {
  stageId: string;
  stageName: string;
  medianCompletedDays: string | null;
  completedIntervalCount: number;
}

export interface SalesFunnel {
  scope: SalesInsightsScope;
  pipelineId: string;
  pipelineName: string;
  cohortDefinition: string;
  cohortCount: number;
  currentOpenCount: number;
  currentWonCount: number;
  currentLostCount: number;
  stages: SalesFunnelStage[];
  stageDurations: SalesStageDuration[];
  coverage: {
    reliableOpportunityCount: number;
    baselineOnlyOpportunityCount: number;
    earliestReliableEventAt: string | null;
    disclosure: string;
  };
}

export interface SalesFollowOnRate {
  cohortCount: number;
  eligibleMatureCount: number;
  followedByOutcomeCount: number;
  rate: string | null;
  immatureCount: number;
  excludedUnassociatedCount: number;
  excludedUntrackedCount: number;
  windowDays: 30;
}

export interface SalesActivity {
  scope: SalesInsightsScope;
  phoneCallsCompletedCount: number;
  meetingsCompletedCount: number;
  callsFollowedByMeeting: SalesFollowOnRate;
  meetingsFollowedByProgression: SalesFollowOnRate;
  outreachAvailable: boolean;
  liveOutreachSentCount: number;
  outreachFollowedByMeeting: SalesFollowOnRate | null;
  associationDisclosure: string;
}

export interface SalesOutcomeReason {
  reason: string;
  label: string;
  count: number;
  percentage: string | null;
}

export interface SalesWinLoss {
  scope: SalesInsightsScope;
  wonCount: number;
  lostCount: number;
  winRate: string | null;
  wonReasons: SalesOutcomeReason[];
  lostReasons: SalesOutcomeReason[];
  lossStages: Array<{
    stageId: string | null;
    stageName: string;
    count: number;
  }>;
  salesCycles: Array<{
    outcome: "won" | "lost";
    medianDays: string | null;
    sampleSize: number;
  }>;
  values: Array<{
    outcome: "won" | "lost";
    currency: string;
    amount: string;
    medianAmount: string;
    opportunityCount: number;
  }>;
  unvaluedWonCount: number;
  unvaluedLostCount: number;
  reasonProvenance: "seller_reported";
  notesAggregated: false;
}

export type SalesForecastPeriodType = "month" | "quarter";
export type SalesForecastPeriodStatus = "upcoming" | "active" | "past";
export type SalesForecastCategory =
  "commit" | "likely" | "possible" | "not_this_period";
export type SalesForecastModelStatus =
  "available" | "insufficient_sample" | "unavailable_stage";
export type SalesForecastStaleReason =
  | "owner_changed"
  | "amount_changed"
  | "currency_changed"
  | "expected_close_changed"
  | "pipeline_changed"
  | "stage_changed"
  | "status_changed";

export interface SalesForecastMetadata {
  currentUserId: string;
  currentUserRole: "admin" | "member";
  organisationTimezone: string;
  owners: Array<{ userId: string; displayName: string; active: boolean }>;
  pipelines: Array<{ id: string; name: string; active: boolean }>;
  canViewOrganisationForecast: boolean;
  canReviewManagerView: boolean;
  modelVersion: string;
  modelLookbackDays: number;
  modelMinimumSample: number;
  supportedPeriodTypes: SalesForecastPeriodType[];
  categories: SalesForecastCategory[];
}

export interface SalesForecastPeriod {
  id: string | null;
  periodType: SalesForecastPeriodType;
  periodStart: string;
  periodEnd: string;
  periodLabel: string;
  timezone: string;
  status: SalesForecastPeriodStatus;
}

export interface SalesForecastCase {
  amount: string;
  opportunityCount: number;
  unvaluedCount: number;
}

export interface SalesForecastBaseline {
  status: SalesForecastModelStatus;
  modelVersion: string;
  pipelineId: string | null;
  pipelineName: string | null;
  stageId: string | null;
  stageName: string | null;
  wonCount: number;
  lostCount: number;
  sampleSize: number;
  observedWinRate: string | null;
  expectedContribution: string | null;
  lookbackStart: string;
  lookbackEnd: string;
  minimumSample: number;
  explanation: string;
}

export interface SalesForecastJudgment {
  judgmentId: string;
  revisionId: string;
  revisionNumber: number;
  category: SalesForecastCategory;
  createdByUserId: string;
  createdByDisplayName: string;
  createdAt: string;
  staleReasons: SalesForecastStaleReason[];
  canReview: boolean;
}

export interface SalesForecastOpportunity {
  opportunityId: string;
  opportunityName: string;
  companyName: string | null;
  ownerUserId: string;
  ownerDisplayName: string;
  amount: string | null;
  currency: string | null;
  expectedCloseDate: string;
  pipelineId: string;
  pipelineName: string;
  stageId: string;
  stageName: string;
  stageEnteredAt: string | null;
  status: "open" | "on_hold";
  judgment: SalesForecastJudgment | null;
  managerJudgment: SalesForecastJudgment | null;
  historicalBaseline: SalesForecastBaseline;
}

export interface SalesForecastRange {
  commit: SalesForecastCase;
  likely: SalesForecastCase;
  possible: SalesForecastCase;
  unreviewedCount: number;
  notThisPeriodCount: number;
  needsReviewCount: number;
  disclosure: string;
}

export interface SalesForecastResponse {
  period: SalesForecastPeriod;
  currency: string;
  pipelineId: string | null;
  ownerUserId: string | null;
  organisationScope: boolean;
  actual: {
    state: "available" | "upcoming" | "unavailable";
    amount: string | null;
    calculatedThrough: string | null;
    metricId: "won_value";
    metricDefinitionVersion: "1";
  };
  targets: Array<{
    id: string;
    label: string;
    scope: "personal" | "organisation";
    origin: "self_set" | "admin_assigned";
    targetValue: string;
  }>;
  sellerForecast: SalesForecastRange;
  managerForecast: SalesForecastRange | null;
  revenueosBaseline: {
    expectedContribution: string | null;
    coveredOpportunityCount: number;
    uncoveredOpportunityCount: number;
    coveredAmount: string;
    uncoveredAmount: string;
    unvaluedOpportunityCount: number;
    modelVersion: string;
    lookbackDays: number;
    minimumSample: number;
    disclosure: string;
  };
  inputQuality: {
    eligibleOpportunityCount: number;
    valuedOpportunityCount: number;
    unvaluedOpportunityCount: number;
    missingExpectedCloseCount: number;
    insufficientHistoryCount: number;
  };
  opportunities: SalesForecastOpportunity[];
  totalOpportunities: number;
  page: number;
  pageSize: number;
  generatedAt: string;
}

export type ManagerAttentionCode =
  | "close_date_passed"
  | "overdue_high_priority_action"
  | "evidence_conflict"
  | "forecast_needs_review"
  | "forecast_not_reviewed"
  | "methodology_priority_gap"
  | "no_next_action"
  | "stale_evidence"
  | "customer_blocker";

export interface ManagerSource {
  sourceType:
    | "opportunity"
    | "task"
    | "methodology_projection"
    | "evidence"
    | "forecast_revision"
    | "revenue_brain_insight"
    | "interaction"
    | "pipeline_stage_event"
    | "crm_change";
  sourceId: string;
  label: string;
  href: string | null;
}

export interface ManagerAttentionReason {
  id: string;
  code: ManagerAttentionCode;
  label: string;
  explanation: string;
  detectedAt: string;
  sources: ManagerSource[];
}

export interface ManagerForecastView {
  category: SalesForecastCategory;
  revisionNumber: number;
  reviewedAt: string;
  staleReasons: SalesForecastStaleReason[];
}

export interface ManagerDealAttention {
  opportunityId: string;
  opportunityName: string;
  companyName: string | null;
  ownerUserId: string;
  ownerDisplayName: string;
  pipelineId: string;
  pipelineName: string;
  stageId: string;
  stageName: string;
  amount: string | null;
  currency: string | null;
  expectedCloseDate: string | null;
  sellerForecast: ManagerForecastView | null;
  managerForecast: ManagerForecastView | null;
  reasons: ManagerAttentionReason[];
  href: string;
}

export interface ManagerAttentionSummary {
  code: ManagerAttentionCode;
  label: string;
  dealCount: number;
}

export interface ManagerDealAttentionList {
  total: number;
  summaries: ManagerAttentionSummary[];
  items: ManagerDealAttention[];
  page: number;
  pageSize: number;
  generatedAt: string;
}

export interface ManagerMethodologyGap {
  fieldKey: string;
  displayName: string;
  state: "partially_supported" | "unknown" | "conflicting" | "stale";
  explanation: string;
  suggestedQuestion: string | null;
  sources: ManagerSource[];
}

export interface ManagerDealReview {
  deal: ManagerDealAttention;
  historicalBaseline: {
    state: SalesForecastModelStatus;
    expectedContribution: string | null;
    wonCount: number;
    lostCount: number;
    explanation: string;
  };
  methodologyGaps: ManagerMethodologyGap[];
  currentActions: Array<{
    id: string;
    title: string;
    status: "open" | "in_progress";
    priority: "low" | "medium" | "high" | "urgent";
    dueAt: string | null;
    href: string;
  }>;
  latestInteraction: {
    id: string;
    title: string;
    interactionType: string;
    occurredAt: string;
    href: string;
  } | null;
  recentChanges: Array<{
    id: string;
    changeType:
      | "stage_changed"
      | "seller_forecast_changed"
      | "manager_forecast_changed"
      | "amount_changed"
      | "expected_close_changed"
      | "owner_changed"
      | "customer_context_changed"
      | "action_completed"
      | "interaction_completed";
    label: string;
    changedAt: string;
    source: ManagerSource;
  }>;
  questions: Array<{
    id: string;
    question: string;
    whyShown: string;
    sourceReasonIds: string[];
    sources: ManagerSource[];
  }>;
  generatedAt: string;
}

export interface ManagerSummary {
  periodLabel: string;
  currency: string;
  actual: SalesForecastResponse["actual"];
  organisationTargets: SalesForecastResponse["targets"];
  sellerForecast: SalesForecastRange;
  managerForecast: SalesForecastRange;
  revenueosBaseline: SalesForecastResponse["revenueosBaseline"];
  dealsNeedingAttention: number;
  topAttentionReasons: ManagerAttentionSummary[];
  generatedAt: string;
}

export interface SalesForecastRevision {
  id: string;
  revisionNumber: number;
  category: SalesForecastCategory;
  createdByUserId: string;
  createdByDisplayName: string;
  ownerUserIdSnapshot: string;
  amountSnapshot: string | null;
  currencySnapshot: string | null;
  expectedCloseDateSnapshot: string;
  pipelineIdSnapshot: string;
  pipelineNameSnapshot: string;
  stageIdSnapshot: string;
  stageNameSnapshot: string;
  opportunityStatusSnapshot: "open" | "on_hold";
  historicalBaseline: SalesForecastBaseline;
  createdAt: string;
}

export interface SalesForecastHistory {
  opportunityId: string;
  opportunityName: string;
  period: SalesForecastPeriod;
  latestStaleReasons: SalesForecastStaleReason[];
  revisions: SalesForecastRevision[];
}

export interface SalesForecastCalibration {
  periodType: SalesForecastPeriodType;
  periodsIncluded: number;
  categories: Array<{
    category: "commit" | "likely" | "possible";
    assessedCount: number;
    realisedWonCount: number;
    realisationRate: string | null;
  }>;
  minimumRateSample: number;
  disclosure: string;
  generatedAt: string;
}

export type SalesTargetCategory =
  "outcome" | "pipeline_development" | "activity";
export type SalesTargetScope = "personal" | "organisation";
export type SalesTargetOrigin = "self_set" | "admin_assigned";
export type SalesTargetPeriodType = "month" | "quarter" | "year";
export type SalesTargetStatus = "upcoming" | "active" | "past" | "archived";

export interface SalesTargetMetricPolicy {
  metricId: string;
  definitionVersion: string;
  label: string;
  description: string;
  unit: SalesMetricUnit;
  category: SalesTargetCategory;
  allowedScopes: SalesTargetScope[];
  requiresCurrency: boolean;
  displayOrder: number;
  dateSemantics: string;
  exclusions: string[];
}

export interface SalesTargetMetadata {
  currentUserId: string;
  currentUserRole: "admin" | "member";
  organisationTimezone: string;
  metrics: SalesTargetMetricPolicy[];
  owners: Array<{ userId: string; displayName: string }>;
  pipelines: Array<{ id: string; name: string; active: boolean }>;
  canAssignPersonalTargets: boolean;
  canCreateOrganisationTargets: boolean;
}

export interface SalesTargetRevision {
  id: string;
  revisionNumber: number;
  goalValue: string;
  createdByUserId: string;
  createdByDisplayName: string;
  createdAt: string;
}

export interface SalesTargetProgress {
  state: "available" | "upcoming" | "unavailable";
  actualValue: string | null;
  targetValue: string;
  remainingValue: string | null;
  aboveTargetValue: string | null;
  percentageComplete: string | null;
  targetReached: boolean | null;
  calculatedThrough: string | null;
  generatedAt: string;
  disclosures: string[];
}

export interface SalesTarget {
  id: string;
  metric: SalesTargetMetricPolicy;
  scope: SalesTargetScope;
  origin: SalesTargetOrigin;
  ownerUserId: string | null;
  ownerDisplayName: string | null;
  pipelineId: string | null;
  pipelineName: string | null;
  periodType: SalesTargetPeriodType;
  periodStart: string;
  periodEnd: string;
  periodLabel: string;
  timezone: string;
  currency: string | null;
  status: SalesTargetStatus;
  latestRevision: SalesTargetRevision;
  revisions: SalesTargetRevision[];
  progress: SalesTargetProgress;
  createdByUserId: string;
  createdByDisplayName: string;
  archivedAt: string | null;
  createdAt: string;
  updatedAt: string;
  canRevise: boolean;
  canArchive: boolean;
}

export interface SalesTargetList {
  items: SalesTarget[];
  canAssignPersonalTargets: boolean;
  canCreateOrganisationTargets: boolean;
  maximumVisibleTargets: 200;
}
