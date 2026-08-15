from enum import StrEnum


class CompanyStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"


class OpportunityStage(StrEnum):
    QUALIFICATION = "qualification"
    DISCOVERY = "discovery"
    EVALUATION = "evaluation"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    PROCUREMENT = "procurement"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    OTHER = "other"


class OpportunityStatus(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    ON_HOLD = "on_hold"


class OpportunityAuditAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MEETING_ASSOCIATED = "meeting_associated"
    MEETING_DISASSOCIATED = "meeting_disassociated"


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


class InteractionType(StrEnum):
    ONLINE_MEETING = "online_meeting"
    FACE_TO_FACE_MEETING = "face_to_face_meeting"
    PRESENTATION = "presentation"
    WORKSHOP = "workshop"
    SITE_VISIT = "site_visit"
    EXECUTIVE_LUNCH = "executive_lunch"
    PHONE_CALL = "phone_call"
    CONFERENCE_INTERACTION = "conference_interaction"
    TRADE_SHOW_INTERACTION = "trade_show_interaction"
    MANUAL_INTERACTION = "manual_interaction"


class InteractionLifecycleStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InteractionCreationOrigin(StrEnum):
    MANUAL = "manual"
    MEETING_COMPATIBILITY = "meeting_compatibility"
    IMPORTED_EXTERNAL = "imported_external"


class InteractionAuditAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"
    MEETING_LINKED = "meeting_linked"


class InteractionMarkerType(StrEnum):
    BUYING_SIGNAL = "buying_signal"
    OBJECTION = "objection"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    RISK = "risk"
    STAKEHOLDER = "stakeholder"
    TIMELINE = "timeline"
    BUDGET = "budget"
    PROCUREMENT = "procurement"
    FOLLOW_UP = "follow_up"
    IMPORTANT_MOMENT = "important_moment"
    CUSTOMER_QUESTION = "customer_question"
    REQUESTED_MATERIAL = "requested_material"
    STRONG_ENGAGEMENT = "strong_engagement"


class EvidenceType(StrEnum):
    TRANSCRIPT = "transcript"
    USER_OBSERVATION = "user_observation"
    RECORDING = "recording"
    VISUAL = "visual"
    DOCUMENT = "document"
    EMAIL = "email"
    SYSTEM_METADATA = "system_metadata"


class EvidenceOriginClass(StrEnum):
    CUSTOMER_DIRECT = "customer_direct"
    SALESPERSON_REPORTED = "salesperson_reported"
    SYSTEM_METADATA = "system_metadata"
    IMPORTED_EXTERNAL = "imported_external"
    SELLER_PREPARED = "seller_prepared"
    AI_INFERRED = "ai_inferred"


class EvidenceSupportClass(StrEnum):
    DIRECT = "direct"
    REPORTED = "reported"
    INFERRED = "inferred"
    CORROBORATED = "corroborated"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    STALE = "stale"
    SUPERSEDED = "superseded"
    OBSERVED = "observed"


class EvidenceValidationState(StrEnum):
    UNREVIEWED = "unreviewed"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class EvidenceLifecycleStatus(StrEnum):
    RECEIVED = "received"
    AVAILABLE = "available"
    EXCLUDED = "excluded"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


class EvidenceRetentionClass(StrEnum):
    INHERITED = "inherited"
    SHORT_LIVED = "short_lived"
    STANDARD = "standard"


class CaptureSessionType(StrEnum):
    AI_DEBRIEF = "ai_debrief"
    VOICE_JOURNAL = "voice_journal"
    LIVE_RECORDING = "live_recording"
    LIVE_AUDIO_RECORDING = "live_audio_recording"
    VISUAL_CAPTURE = "visual_capture"
    UPLOADED_TRANSCRIPT = "uploaded_transcript"
    UPLOADED_RECORDING = "uploaded_recording"
    UPLOADED_AUDIO_RECORDING = "uploaded_audio_recording"
    IMPORTED_AUDIO_RECORDING = "imported_audio_recording"
    MANUAL_NOTES = "manual_notes"


class CaptureSessionStatus(StrEnum):
    CREATED = "created"
    CAPTURING = "capturing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class VisualType(StrEnum):
    WHITEBOARD = "whiteboard"
    WORKSHOP_OUTPUT = "workshop_output"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    HANDWRITTEN_NOTES = "handwritten_notes"
    AGENDA = "agenda"
    BUSINESS_CARD = "business_card"
    PRESENTATION_SLIDE = "presentation_slide"
    PRESENTATION_DECK_PAGE = "presentation_deck_page"
    CUSTOMER_DOCUMENT_PHOTO = "customer_document_photo"
    SITE_PHOTO = "site_photo"
    PRODUCT_PHOTO = "product_photo"
    SCREENSHOT = "screenshot"
    OTHER = "other"


class VisualSourceOwnership(StrEnum):
    CUSTOMER_CREATED = "customer_created"
    SALESPERSON_CREATED = "salesperson_created"
    JOINTLY_CREATED = "jointly_created"
    UNKNOWN_ORIGIN = "unknown_origin"


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
    RECORDED_AUDIO = "recorded_audio"
    UPLOADED_AUDIO = "uploaded_audio"
    IMPORTED_AUDIO = "imported_audio"


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
    STAKEHOLDER_INTELLIGENCE = "stakeholder_intelligence"
    NEXT_BEST_ACTION = "next_best_action"
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
    STAKEHOLDER_INTELLIGENCE = "stakeholder_intelligence"
    NEXT_BEST_ACTION = "next_best_action"
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


class StakeholderRole(StrEnum):
    ECONOMIC_BUYER = "economic_buyer"
    DECISION_MAKER = "decision_maker"
    CHAMPION = "champion"
    INFLUENCER = "influencer"
    BLOCKER = "blocker"
    TECHNICAL_BUYER = "technical_buyer"
    TECHNICAL_EVALUATOR = "technical_evaluator"
    END_USER = "end_user"
    PROCUREMENT = "procurement"
    LEGAL = "legal"
    SECURITY = "security"
    FINANCE = "finance"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    IMPLEMENTATION_OWNER = "implementation_owner"
    VENDOR_REPRESENTATIVE = "vendor_representative"
    PARTICIPANT = "participant"
    UNKNOWN = "unknown"


class StakeholderInfluence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCLEAR = "unclear"


class StakeholderStance(StrEnum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    RESISTANT = "resistant"
    MIXED = "mixed"
    UNCLEAR = "unclear"


class StakeholderEngagement(StrEnum):
    ACTIVE = "active"
    PASSIVE = "passive"
    ABSENT_BUT_REFERENCED = "absent_but_referenced"
    UNCLEAR = "unclear"


class StakeholderCoverageState(StrEnum):
    IDENTIFIED = "identified"
    NOT_IDENTIFIED = "not_identified"
    UNCLEAR = "unclear"
    NOT_DISCUSSED = "not_discussed"


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
