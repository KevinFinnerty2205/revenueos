from enum import StrEnum


class CompanyStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductModule(StrEnum):
    PROSPECT = "prospect"
    ENGAGE = "engage"


class OutreachPurpose(StrEnum):
    INTRODUCTION = "introduction"
    REQUEST_MEETING = "request_meeting"
    SHARE_RELEVANT_INFORMATION = "share_relevant_information"
    RE_ENGAGE = "re_engage"


class OutreachState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    CANCELLED = "cancelled"


class OutreachContactability(StrEnum):
    ALLOWED = "allowed"
    NO_BUSINESS_EMAIL = "no_business_email"
    EMAIL_TRUST_UNKNOWN = "email_trust_unknown"
    PROVIDER_SUPPLIED_BLOCKED = "provider_supplied_blocked"
    SUPPRESSED = "suppressed"
    COOLDOWN = "cooldown"
    POLICY_NOT_CONFIGURED = "policy_not_configured"
    OUTBOUND_DISABLED = "outbound_disabled"
    ENGAGE_UNAVAILABLE = "engage_unavailable"
    SENDER_DISABLED = "sender_disabled"


class SuppressionReason(StrEnum):
    MANUAL_DO_NOT_CONTACT = "manual_do_not_contact"
    RECIPIENT_OPT_OUT = "recipient_opt_out"
    COMPLAINT = "complaint"
    PERMANENT_BOUNCE = "permanent_bounce"


class ProspectResearchRunStatus(StrEnum):
    PENDING = "pending"
    FETCHING = "fetching"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ProspectTrustState(StrEnum):
    VERIFIED = "verified"
    PROVIDER_SUPPLIED = "provider_supplied"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ProspectSourceAuthority(StrEnum):
    PRIMARY = "primary"
    OFFICIAL_PUBLIC = "official_public"
    REGULATORY = "regulatory"
    REPUTABLE_SECONDARY = "reputable_secondary"
    STRUCTURED_PROVIDER = "structured_provider"
    OTHER_PUBLIC = "other_public"


class ProspectObservationCategory(StrEnum):
    COMPANY_PROFILE = "company_profile"
    INDUSTRY = "industry"
    LOCATION = "location"
    SIZE = "size"
    BUSINESS_MODEL = "business_model"
    PRODUCT_SERVICE = "product_service"
    STRATEGIC_INITIATIVE = "strategic_initiative"
    EXPANSION = "expansion"
    HIRING = "hiring"
    LEADERSHIP_CHANGE = "leadership_change"
    FUNDING_FINANCIAL = "funding_financial"
    TECHNOLOGY = "technology"
    REGULATORY = "regulatory"
    PARTNERSHIP = "partnership"
    CUSTOMER_MARKET = "customer_market"
    TRIGGER = "trigger"
    POTENTIAL_FIT = "potential_fit"
    CURRENT_ROLE = "current_role"
    CURRENT_COMPANY = "current_company"
    CAREER_HISTORY = "career_history"
    RESPONSIBILITY = "responsibility"
    EXPERTISE = "expertise"
    PROFESSIONAL_INTEREST = "professional_interest"
    PROFESSIONAL_ACTIVITY = "professional_activity"
    COMPANY_INITIATIVE = "company_initiative"
    PUBLIC_STATEMENT = "public_statement"
    AUTHORED_CONTENT = "authored_content"
    CONFERENCE_ACTIVITY = "conference_activity"
    WHY_PERSON_MATTERS = "why_person_matters"
    CONVERSATION_CONTEXT = "conversation_context"
    OTHER_PROFESSIONAL = "other_professional"
    OTHER = "other"


class ProspectPersonEmploymentState(StrEnum):
    CURRENT = "current"
    UNCERTAIN = "uncertain"
    NO_LONGER_CURRENT = "no_longer_current"


class ProspectBuyingRole(StrEnum):
    EXECUTIVE_SPONSOR = "executive_sponsor"
    ECONOMIC_BUYER_CANDIDATE = "economic_buyer_candidate"
    CHAMPION_CANDIDATE = "champion_candidate"
    BUSINESS_BUYER = "business_buyer"
    TECHNICAL_EVALUATOR = "technical_evaluator"
    SECURITY = "security"
    PROCUREMENT = "procurement"
    LEGAL = "legal"
    FINANCE = "finance"
    END_USER_INFLUENCER = "end_user_influencer"
    OTHER_RELEVANT = "other_relevant"


class ProspectHypothesisReviewState(StrEnum):
    NEEDS_VALIDATION = "needs_validation"
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"


class ProspectContactPointType(StrEnum):
    BUSINESS_EMAIL = "business_email"
    BUSINESS_PHONE = "business_phone"
    COMPANY_SWITCHBOARD = "company_switchboard"
    PUBLIC_PROFESSIONAL_PROFILE = "public_professional_profile"


class ProspectTargetMarketStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProspectDiscoveryRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ProspectCandidateMatchState(StrEnum):
    MATCH = "match"
    PARTIAL = "partial"
    EXCLUDED = "excluded"


class ProspectCandidatePriority(StrEnum):
    HIGH = "high"
    WORTH_RESEARCHING = "worth_researching"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    EXCLUDED = "excluded"


class ProspectRelationshipState(StrEnum):
    NEW_PROSPECT = "new_prospect"
    EXISTING_ACCOUNT_NO_ACTIVE_OPPORTUNITY = "existing_account_no_active_opportunity"
    ACTIVE_OPPORTUNITY = "active_opportunity"


class ProspectCandidateFeedbackState(StrEnum):
    SAVED = "saved"
    EXCLUDED = "excluded"


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


class ActionType(StrEnum):
    FOLLOW_UP_EMAIL = "follow_up_email"
    PERSONALIZED_OUTREACH = "personalized_outreach"
    SEND_REQUESTED_MATERIAL = "send_requested_material"
    CREATE_TASK = "create_task"
    FOLLOW_UP_STAKEHOLDER = "follow_up_stakeholder"
    SCHEDULE_INTERACTION = "schedule_interaction"
    UPDATE_OPPORTUNITY = "update_opportunity"
    UPDATE_CONTACT = "update_contact"
    LOG_INTERACTION = "log_interaction"
    UPDATE_STAKEHOLDER = "update_stakeholder"
    ADD_DECISION = "add_decision"
    ADD_COMMITMENT = "add_commitment"
    ADD_RISK = "add_risk"
    UPDATE_TIMELINE = "update_timeline"
    UPDATE_PROCUREMENT = "update_procurement"
    UPDATE_SECURITY_LEGAL = "update_security_legal"
    CREATE_REMINDER = "create_reminder"
    NOTIFY_INTERNAL = "notify_internal"
    PREPARE_NEXT_INTERACTION = "prepare_next_interaction"
    RESOLVE_OPEN_QUESTION = "resolve_open_question"
    REVIEW_CONFLICT = "review_conflict"
    OTHER = "other"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    COMPLETED_MANUALLY = "completed_manually"


class ActionPriority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ActionAudience(StrEnum):
    INTERNAL = "internal"
    CUSTOMER_FACING = "customer_facing"


class ActionRiskClass(StrEnum):
    INTERNAL_LOW_RISK = "internal_low_risk"
    EXTERNAL_CUSTOMER_FACING = "external_customer_facing"
    DATA_MUTATION = "data_mutation"


class ActionRejectionReason(StrEnum):
    ALREADY_DONE = "already_done"
    INCORRECT = "incorrect"
    NOT_RELEVANT = "not_relevant"
    UNSUPPORTED = "unsupported"
    DUPLICATE = "duplicate"
    NOT_NOW = "not_now"
    OTHER = "other"


class ConnectorKey(StrEnum):
    MOCK_EMAIL = "mock_email"
    MOCK_CALENDAR = "mock_calendar"
    MOCK_CRM = "mock_crm"
    MOCK_TASK = "mock_task"
    HUBSPOT = "hubspot"


class ConnectorCapability(StrEnum):
    SEND_EMAIL = "send_email"
    CREATE_CALENDAR_EVENT = "create_calendar_event"
    UPDATE_OPPORTUNITY = "update_opportunity"
    UPDATE_CONTACT = "update_contact"
    CREATE_TASK = "create_task"
    CREATE_ACTIVITY = "create_activity"
    POST_INTERNAL_MESSAGE = "post_internal_message"
    UPLOAD_OR_SHARE_DOCUMENT = "upload_or_share_document"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    REAUTHORISATION_REQUIRED = "reauthorisation_required"
    REVOKED = "revoked"


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    EXECUTING = "executing"
    SIMULATED_SUCCESS = "simulated_success"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"
    UNKNOWN_EXTERNAL_STATE = "unknown_external_state"


class CRMFieldAuthority(StrEnum):
    CRM_AUTHORITATIVE = "crm_authoritative"
    REVENUEOS_AUTHORITATIVE = "revenueos_authoritative"
    REVIEW_BEFORE_SYNC = "review_before_sync"


class CRMEntityType(StrEnum):
    COMPANY = "company"
    CONTACT = "contact"
    OPPORTUNITY = "opportunity"


class CRMExternalObjectType(StrEnum):
    COMPANY = "company"
    CONTACT = "contact"
    DEAL = "deal"


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


class OnlineMeetingPlatform(StrEnum):
    MICROSOFT_TEAMS = "microsoft_teams"
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    OTHER = "other"


class OnlineMeetingCaptureSource(StrEnum):
    PLATFORM_RECORDING = "platform_recording"
    PLATFORM_TRANSCRIPT = "platform_transcript"
    USER_UPLOADED_RECORDING = "user_uploaded_recording"
    USER_UPLOADED_TRANSCRIPT = "user_uploaded_transcript"
    NATIVE_INTEGRATION = "native_integration"
    MEETING_BOT = "meeting_bot"
    AI_DEBRIEF = "ai_debrief"
    VOICE_JOURNAL = "voice_journal"
    MANUAL_NOTES = "manual_notes"


class OnlineMeetingIngestionState(StrEnum):
    NOT_STARTED = "not_started"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TranscriptProvenance(StrEnum):
    PLATFORM_GENERATED = "platform_generated"
    USER_UPLOADED = "user_uploaded"
    EXTERNALLY_GENERATED = "externally_generated"
    MANUALLY_PASTED = "manually_pasted"


class InteractionLifecycleStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InteractionCreationOrigin(StrEnum):
    MANUAL = "manual"
    MEETING_COMPATIBILITY = "meeting_compatibility"
    IMPORTED_EXTERNAL = "imported_external"


class CallDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    UNKNOWN = "unknown"


class CallOutcome(StrEnum):
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    CANCELLED = "cancelled"


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
    CONTEXT = "context"
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
    DOCUMENT_IMPORT = "document_import"
    EMAIL_IMPORT = "email_import"
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


class DocumentType(StrEnum):
    PROPOSAL = "proposal"
    RFP = "rfp"
    RFQ = "rfq"
    REQUIREMENTS = "requirements"
    CONTRACT = "contract"
    SOW = "sow"
    PRICING = "pricing"
    PROCUREMENT = "procurement"
    SECURITY_QUESTIONNAIRE = "security_questionnaire"
    IMPLEMENTATION_PLAN = "implementation_plan"
    TECHNICAL_SPECIFICATION = "technical_specification"
    CUSTOMER_PRESENTATION = "customer_presentation"
    SALES_MATERIAL = "sales_material"
    OTHER = "other"


class DocumentSourceOwnership(StrEnum):
    CUSTOMER_PROVIDED = "customer_provided"
    SALESPERSON_PROVIDED = "salesperson_provided"
    JOINTLY_CREATED = "jointly_created"
    EXTERNALLY_GENERATED = "externally_generated"
    SYSTEM_IMPORTED = "system_imported"
    UNKNOWN = "unknown"


class EmailSourceType(StrEnum):
    CUSTOMER_SENT = "customer_sent"
    SALESPERSON_SENT = "salesperson_sent"
    INTERNAL_FORWARD = "internal_forward"
    MANUALLY_PASTED = "manually_pasted"
    EXTERNAL_PROVIDER_IMPORT = "external_provider_import"


class EmailDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


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
    PLATFORM_GENERATED = "platform_generated"
    USER_UPLOADED = "user_uploaded"
    EXTERNALLY_GENERATED = "externally_generated"
    MANUALLY_PASTED = "manually_pasted"
    PROGRESSIVE = "progressive"


class TranscriptSpeakerRole(StrEnum):
    CUSTOMER = "customer"
    SALESPERSON = "salesperson"
    UNKNOWN = "unknown"


class LiveInteractionStatus(StrEnum):
    ACTIVE = "active"
    PROCESSING = "processing"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class LiveSignalType(StrEnum):
    BUYING_SIGNAL = "buying_signal"
    OBJECTION = "objection"
    STAKEHOLDER = "stakeholder"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    RISK = "risk"
    TIMELINE = "timeline"
    PROCUREMENT = "procurement"
    SECURITY_LEGAL = "security_legal"
    CUSTOMER_REQUEST = "customer_request"
    COMMERCIAL_INTENT = "commercial_intent"
    OBJECTIVE_PROGRESS = "objective_progress"
    OPEN_QUESTION_PROGRESS = "open_question_progress"
    OTHER = "other"


class ProvisionalSignalLifecycle(StrEnum):
    DETECTED = "detected"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    DISMISSED = "dismissed"
    PROMOTED_CANDIDATE = "promoted_candidate"
    EXPIRED = "expired"


class LiveSignalResolution(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REVISED = "revised"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


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
