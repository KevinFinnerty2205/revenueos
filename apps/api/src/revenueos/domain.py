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


class MeetingAuditEntityType(StrEnum):
    MEETING = "meeting"
    PARTICIPANT = "participant"
    TRANSCRIPT = "transcript"
