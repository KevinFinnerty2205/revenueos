from enum import StrEnum


class CompanyStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"


class OpportunityStage(StrEnum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MeetingType(StrEnum):
    REMOTE = "remote"
    PHONE = "phone"
    IN_PERSON = "in_person"
    OTHER = "other"


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(StrEnum):
    INVITED = "invited"
    ATTENDED = "attended"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ParticipantRole(StrEnum):
    HOST = "host"
    ATTENDEE = "attendee"


class TranscriptSource(StrEnum):
    MANUAL = "manual"
    UPLOAD = "upload"


class MeetingAuditAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RESTORED = "restored"
    INTELLIGENCE_REQUESTED = "intelligence_requested"
    AI_JOB_CREATED = "ai_job_created"
    AI_JOB_STATUS_CHANGED = "ai_job_status_changed"
    AI_ARTIFACT_CREATED = "ai_artifact_created"


class MeetingAuditEntityType(StrEnum):
    MEETING = "meeting"
    PARTICIPANT = "participant"
    TRANSCRIPT = "transcript"
    AI_JOB = "ai_job"
    AI_ARTIFACT = "ai_artifact"


class AIJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJobType(StrEnum):
    INFRASTRUCTURE_TEST = "infrastructure_test"
    EXECUTIVE_SUMMARY = "executive_summary"
    DECISIONS = "decisions"
    ACTION_ITEMS = "action_items"
    RISKS_BLOCKERS = "risks_blockers"


class AIArtifactType(StrEnum):
    INFRASTRUCTURE_TEST = "infrastructure_test"
    EXECUTIVE_SUMMARY = "executive_summary"
    DECISIONS = "decisions"
    ACTION_ITEMS = "action_items"
    RISKS_BLOCKERS = "risks_blockers"


class RiskCategory(StrEnum):
    BUDGET = "budget"
    PROCUREMENT = "procurement"
    LEGAL = "legal"
    SECURITY = "security"
    TECHNICAL = "technical"
    INTEGRATION = "integration"
    TIMELINE = "timeline"
    IMPLEMENTATION = "implementation"
    STAKEHOLDER = "stakeholder"
    COMPETITOR = "competitor"
    COMMERCIAL = "commercial"
    RESOURCING = "resourcing"
    DEPENDENCY = "dependency"
    OTHER = "other"


class RiskSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemStatus(StrEnum):
    OPEN = "open"


class DecisionStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ExecutiveSummaryMeetingType(StrEnum):
    SALES_DISCOVERY = "sales_discovery"
    SALES_DEMO = "sales_demo"
    CUSTOMER_SUCCESS = "customer_success"
    RECRUITMENT = "recruitment"
    INTERNAL = "internal"
    OTHER = "other"


class ExecutiveSummarySentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"
