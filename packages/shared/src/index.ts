/** FastAPI Pydantic models and the generated OpenAPI document are canonical. */
export type AuthMode = "mock" | "clerk";
export type OrganisationRole = "admin" | "manager" | "member";

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
export type AttendanceStatus = "invited" | "attended" | "absent" | "unknown";
export type ParticipantRole = "host" | "attendee";
export type TranscriptSource = "manual" | "upload";
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

export interface Meeting extends TenantEntity {
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

export interface OpportunityWorkspaceResponse {
  opportunity: OpportunityWorkspaceOpportunity;
  latestMeeting: OpportunityMeetingSummary | null;
  recentMeetings: OpportunityMeetingSummary[];
  intelligence: MeetingIntelligenceResponse | null;
  intelligenceSectionsAvailable: number;
  partialData: boolean;
  generatedAt: string;
}
