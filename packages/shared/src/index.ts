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
export type TaskStatus =
  | "open"
  | "in_progress"
  | "completed"
  | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

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
