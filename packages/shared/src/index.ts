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
  | "discovery"
  | "qualification"
  | "proposal"
  | "negotiation"
  | "closed_won"
  | "closed_lost";
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
export type DecisionsState =
  | "empty"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type DecisionStatus =
  | "confirmed"
  | "tentative"
  | "rejected"
  | "deferred";
export type ActionItemsState =
  | "empty"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type ActionItemPriority = "high" | "medium" | "low";
export type ActionItemStatus = "open";
export type RisksBlockersState =
  | "empty"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
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
  | "empty"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type OpenQuestionImportance = "high" | "medium" | "low";

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
  companyId: string;
  name: string;
  stage: OpportunityStage;
  value: string;
  currency: string;
  probability: number;
  expectedCloseDate: string | null;
  ownerUserId: string;
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
