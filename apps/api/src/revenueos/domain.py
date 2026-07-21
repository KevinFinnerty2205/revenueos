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
    OPEN_QUESTIONS = "open_questions"
    BUYING_SIGNALS = "buying_signals"
    OBJECTIONS_COMPETITIVE_SIGNALS = "objections_competitive_signals"
    FOLLOW_UP_EMAIL = "follow_up_email"


class AIArtifactType(StrEnum):
    INFRASTRUCTURE_TEST = "infrastructure_test"
    EXECUTIVE_SUMMARY = "executive_summary"
    DECISIONS = "decisions"
    ACTION_ITEMS = "action_items"
    RISKS_BLOCKERS = "risks_blockers"
    OPEN_QUESTIONS = "open_questions"
    BUYING_SIGNALS = "buying_signals"
    OBJECTIONS_COMPETITIVE_SIGNALS = "objections_competitive_signals"
    FOLLOW_UP_EMAIL = "follow_up_email"


class FollowUpEmailTone(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    EXECUTIVE = "executive"


class BuyingSignalType(StrEnum):
    BUDGET_CONFIRMED = "budget_confirmed"
    BUDGET_UNCONFIRMED = "budget_unconfirmed"
    TIMELINE_CONFIRMED = "timeline_confirmed"
    TIMELINE_UNCLEAR = "timeline_unclear"
    DECISION_MAKER_ENGAGED = "decision_maker_engaged"
    DECISION_MAKER_MISSING = "decision_maker_missing"
    CHAMPION_IDENTIFIED = "champion_identified"
    CHAMPION_NOT_EVIDENT = "champion_not_evident"
    PROCUREMENT_ACTIVE = "procurement_active"
    PROCUREMENT_UNCLEAR = "procurement_unclear"
    COMPETITOR_PRESENT = "competitor_present"
    COMPETITOR_ABSENT = "competitor_absent"
    URGENCY_PRESENT = "urgency_present"
    URGENCY_ABSENT = "urgency_absent"
    COMMERCIAL_INTENT = "commercial_intent"
    IMPLEMENTATION_COMMITMENT = "implementation_commitment"
    NEXT_STEP_COMMITTED = "next_step_committed"
    NEXT_STEP_WEAK = "next_step_weak"
    STAKEHOLDER_ALIGNMENT = "stakeholder_alignment"
    STAKEHOLDER_MISALIGNMENT = "stakeholder_misalignment"
    TECHNICAL_FIT_CONFIRMED = "technical_fit_confirmed"
    TECHNICAL_FIT_UNCERTAIN = "technical_fit_uncertain"
    SECURITY_OR_LEGAL_PROGRESS = "security_or_legal_progress"
    SECURITY_OR_LEGAL_BLOCKER = "security_or_legal_blocker"
    OTHER = "other"


class BuyingSignalPolarity(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class BuyingSignalStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class DealMomentum(StrEnum):
    STRONG_POSITIVE = "strong_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    STRONG_NEGATIVE = "strong_negative"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ObjectionCategory(StrEnum):
    PRICING = "pricing"
    BUDGET = "budget"
    COMMERCIAL = "commercial"
    LEGAL = "legal"
    SECURITY = "security"
    PRIVACY = "privacy"
    TECHNICAL = "technical"
    INTEGRATION = "integration"
    IMPLEMENTATION = "implementation"
    RESOURCING = "resourcing"
    PROCUREMENT = "procurement"
    TIMELINE = "timeline"
    PRODUCT_FIT = "product_fit"
    STAKEHOLDER = "stakeholder"
    CHANGE_MANAGEMENT = "change_management"
    COMPETITOR = "competitor"
    TRUST = "trust"
    OTHER = "other"


class ObjectionStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_ADDRESSED = "partially_addressed"
    DEFERRED = "deferred"
    UNRESOLVED = "unresolved"


class ObjectionStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class CompetitorPosition(StrEnum):
    STRONGER = "stronger"
    WEAKER = "weaker"
    NEUTRAL = "neutral"
    PRESENT = "present"
    UNCLEAR = "unclear"


class OverallObjectionPressure(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SEVERE = "severe"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


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


class OpenQuestionImportance(StrEnum):
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
