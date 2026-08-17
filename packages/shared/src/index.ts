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
  employeeCount: number | null;
  status: CompanyStatus;
  ownerUserId: string;
}

export interface Contact extends TenantEntity {
  companyId: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string | null;
  jobTitle: string | null;
  linkedinUrl: string | null;
  ownerUserId: string;
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
  | "send_requested_material"
  | "create_task"
  | "follow_up_stakeholder"
  | "schedule_interaction"
  | "update_opportunity"
  | "update_contact"
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

export type ActionPayload =
  | FollowUpEmailActionPayload
  | CreateTaskActionPayload
  | ({
      kind: Exclude<ActionType, "follow_up_email" | "create_task">;
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
  "mock_email" | "mock_calendar" | "mock_crm" | "mock_task";
export type ConnectorCapability =
  | "send_email"
  | "create_calendar_event"
  | "update_opportunity"
  | "update_contact"
  | "create_task"
  | "post_internal_message"
  | "upload_or_share_document";
export type ConnectionStatus = "active" | "revoked";
export type ExecutionStatus =
  | "queued"
  | "executing"
  | "simulated_success"
  | "failed_retryable"
  | "failed_permanent"
  | "cancelled"
  | "unknown_external_state";

export interface ConnectorDefinition {
  connectorKey: ConnectorKey;
  displayName: string;
  providerFamily: "mock";
  supportedCapabilities: ConnectorCapability[];
  authenticationType: "mock_local";
  executionRiskClasses: ActionRiskClass[];
  configurationSchemaVersion: number;
  executionMode: "simulation";
  available: boolean;
  simulationOnly: true;
}

export interface IntegrationCatalogResponse {
  connectors: ConnectorDefinition[];
  executionMode: "simulation";
  externalActionsEnabled: false;
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
  metadataVersion: number;
  executionMode: "simulation";
  simulationOnly: true;
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
  executionMode: "simulation";
  simulationOnly: true;
}

export interface ActionExecutionOptionListResponse {
  items: ActionExecutionOption[];
  total: number;
}

export type ExecutionPreviewContent =
  | {
      kind: "email";
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
      action: "update_opportunity" | "update_contact";
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
  executionMode: "simulation";
  simulationOnly: true;
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
  executionMode: "simulation";
  simulationOnly: true;
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
