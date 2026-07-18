from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from revenueos.domain import (
    AIArtifactType,
    AIJobStatus,
    AIJobType,
    AttendanceStatus,
    CompanyStatus,
    MeetingStatus,
    MeetingType,
    OpportunityStage,
    ParticipantRole,
    TaskPriority,
    TaskStatus,
    TranscriptSource,
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Organisation(TimestampMixin, Base):
    __tablename__ = "organisations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organisations_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    memberships: Mapped[list[OrganisationMembership]] = relationship(
        back_populates="organisation",
        cascade="all, delete-orphan",
    )
    ai_jobs: Mapped[list[AIJob]] = relationship(
        back_populates="organisation",
        cascade="all, delete-orphan",
        foreign_keys="AIJob.organisation_id",
    )
    ai_artifacts: Mapped[list[AIArtifact]] = relationship(
        back_populates="organisation",
        foreign_keys="AIArtifact.organisation_id",
        viewonly=True,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_auth_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    memberships: Mapped[list[OrganisationMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    requested_ai_jobs: Mapped[list[AIJob]] = relationship(
        back_populates="requested_by_user",
        foreign_keys="AIJob.requested_by_user_id",
    )


class OrganisationMembership(Base):
    __tablename__ = "organisation_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'manager', 'member')", name="ck_memberships_role"),
        Index("ix_memberships_organisation_role", "organisation_id", "role"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    organisation: Mapped[Organisation] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('prospect', 'active', 'inactive')",
            name="ck_companies_status",
        ),
        CheckConstraint(
            "employee_count IS NULL OR employee_count >= 0",
            name="ck_companies_employee_count",
        ),
        CheckConstraint("length(trim(name)) > 0", name="ck_companies_name"),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_companies_owner_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_companies_organisation_id_id"),
        Index("ix_companies_organisation_name", "organisation_id", "name"),
        Index("ix_companies_organisation_status", "organisation_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    industry: Mapped[str | None] = mapped_column(String(120))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CompanyStatus.PROSPECT.value,
        server_default=CompanyStatus.PROSPECT.value,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="ck_contacts_first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="ck_contacts_last_name"),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_contacts_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_contacts_owner_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_contacts_organisation_id_id"),
        Index("ix_contacts_organisation_name", "organisation_id", "last_name", "first_name"),
        Index("ix_contacts_organisation_company", "organisation_id", "company_id"),
        Index("ix_contacts_organisation_email", "organisation_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    job_title: Mapped[str | None] = mapped_column(String(150))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_opportunities_name"),
        CheckConstraint(
            "stage IN ('discovery', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost')",
            name="ck_opportunities_stage",
        ),
        CheckConstraint("value >= 0", name="ck_opportunities_value"),
        CheckConstraint("probability >= 0 AND probability <= 100", name="ck_opportunities_probability"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_opportunities_currency"),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_opportunities_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_opportunities_owner_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_opportunities_organisation_id_id"),
        Index("ix_opportunities_organisation_name", "organisation_id", "name"),
        Index("ix_opportunities_organisation_company", "organisation_id", "company_id"),
        Index("ix_opportunities_organisation_stage", "organisation_id", "stage"),
        Index("ix_opportunities_organisation_close", "organisation_id", "expected_close_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OpportunityStage.DISCOVERY.value,
        server_default=OpportunityStage.DISCOVERY.value,
    )
    value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD", server_default="AUD")
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title"),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_tasks_priority",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_tasks_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_tasks_contact_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_tasks_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "assigned_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_tasks_assigned_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_tasks_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_tasks_organisation_id_id"),
        Index("ix_tasks_organisation_status", "organisation_id", "status"),
        Index("ix_tasks_organisation_priority", "organisation_id", "priority"),
        Index("ix_tasks_organisation_due", "organisation_id", "due_at"),
        Index("ix_tasks_organisation_company", "organisation_id", "company_id"),
        Index("ix_tasks_organisation_contact", "organisation_id", "contact_id"),
        Index("ix_tasks_organisation_opportunity", "organisation_id", "opportunity_id"),
        Index("ix_tasks_organisation_assignee", "organisation_id", "assigned_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.OPEN.value,
        server_default=TaskStatus.OPEN.value,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskPriority.MEDIUM.value,
        server_default=TaskPriority.MEDIUM.value,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_meetings_title"),
        CheckConstraint(
            "meeting_type IN ('remote', 'phone', 'in_person', 'other')",
            name="ck_meetings_type",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_meetings_status",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_meetings_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_owner_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_created_by_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "updated_by"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_updated_by_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_meetings_organisation_id_id"),
        Index("ix_meetings_organisation_date", "organisation_id", "meeting_date"),
        Index("ix_meetings_organisation_status", "organisation_id", "status"),
        Index("ix_meetings_organisation_type", "organisation_id", "meeting_type"),
        Index("ix_meetings_organisation_company", "organisation_id", "company_id"),
        Index("ix_meetings_organisation_deleted", "organisation_id", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    meeting_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meeting_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MeetingType.OTHER.value,
        server_default=MeetingType.OTHER.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MeetingStatus.SCHEDULED.value,
        server_default=MeetingStatus.SCHEDULED.value,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ai_jobs: Mapped[list[AIJob]] = relationship(
        back_populates="meeting",
        foreign_keys="[AIJob.organisation_id, AIJob.meeting_id]",
        viewonly=True,
    )
    ai_artifacts: Mapped[list[AIArtifact]] = relationship(
        back_populates="meeting",
        foreign_keys="[AIArtifact.organisation_id, AIArtifact.meeting_id]",
        viewonly=True,
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (
        CheckConstraint(
            "contact_id IS NOT NULL "
            "OR COALESCE(length(trim(display_name)), 0) > 0 "
            "OR COALESCE(length(trim(email)), 0) > 0",
            name="ck_meeting_participants_identity",
        ),
        CheckConstraint(
            "attendance_status IN ('invited', 'attended', 'absent', 'unknown')",
            name="ck_meeting_participants_attendance",
        ),
        CheckConstraint(
            "role IN ('host', 'attendee')",
            name="ck_meeting_participants_role",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_meeting_participants_meeting_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_meeting_participants_contact_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_meeting_participants_organisation_id_id",
        ),
        Index(
            "ix_meeting_participants_organisation_meeting",
            "organisation_id",
            "meeting_id",
        ),
        Index(
            "ix_meeting_participants_organisation_contact",
            "organisation_id",
            "contact_id",
        ),
        Index(
            "ix_meeting_participants_organisation_email",
            "organisation_id",
            "email",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    display_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    attendance_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AttendanceStatus.INVITED.value,
        server_default=AttendanceStatus.INVITED.value,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ParticipantRole.ATTENDEE.value,
        server_default=ParticipantRole.ATTENDEE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Transcript(TimestampMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        CheckConstraint("length(trim(raw_text)) > 0", name="ck_transcripts_raw_text"),
        CheckConstraint("version > 0", name="ck_transcripts_version"),
        CheckConstraint(
            "source IN ('manual', 'upload')",
            name="ck_transcripts_source",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_transcripts_meeting_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_transcripts_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "meeting_id",
            name="uq_transcripts_organisation_id_meeting",
        ),
        UniqueConstraint(
            "organisation_id",
            "meeting_id",
            name="uq_transcripts_organisation_meeting",
        ),
        Index("ix_transcripts_organisation_deleted", "organisation_id", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TranscriptSource.MANUAL.value,
        server_default=TranscriptSource.MANUAL.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ai_jobs: Mapped[list[AIJob]] = relationship(
        back_populates="transcript",
        foreign_keys="[AIJob.organisation_id, AIJob.transcript_id, AIJob.meeting_id]",
        viewonly=True,
    )
    ai_artifacts: Mapped[list[AIArtifact]] = relationship(
        back_populates="transcript",
        foreign_keys="[AIArtifact.organisation_id, AIArtifact.transcript_id, AIArtifact.meeting_id]",
        viewonly=True,
    )


class MeetingAuditEvent(Base):
    __tablename__ = "meeting_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ("
            "'created', 'updated', 'deleted', 'restored', "
            "'intelligence_requested', 'ai_job_created', "
            "'ai_job_status_changed', 'ai_artifact_created'"
            ")",
            name="ck_meeting_audit_events_action",
        ),
        CheckConstraint(
            "entity_type IN ('meeting', 'participant', 'transcript', 'ai_job', 'ai_artifact')",
            name="ck_meeting_audit_events_entity_type",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_meeting_audit_events_meeting_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meeting_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_meeting_audit_events_organisation_id_id",
        ),
        Index(
            "ix_meeting_audit_events_organisation_meeting_created",
            "organisation_id",
            "meeting_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AIJob(TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('infrastructure_test', 'executive_summary', 'decisions', 'action_items', 'risks_blockers')",
            name="ck_ai_jobs_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_jobs_status",
        ),
        CheckConstraint("transcript_version > 0", name="ck_ai_jobs_transcript_version"),
        CheckConstraint(
            "prompt_version IS NULL OR prompt_version > 0",
            name="ck_ai_jobs_prompt_version",
        ),
        CheckConstraint("schema_version > 0", name="ck_ai_jobs_schema_version"),
        CheckConstraint("attempt_count >= 0", name="ck_ai_jobs_attempt_count"),
        CheckConstraint("max_attempts >= 1", name="ck_ai_jobs_max_attempts"),
        CheckConstraint(
            "input_token_count IS NULL OR input_token_count >= 0",
            name="ck_ai_jobs_input_tokens",
        ),
        CheckConstraint(
            "output_token_count IS NULL OR output_token_count >= 0",
            name="ck_ai_jobs_output_tokens",
        ),
        CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_ai_jobs_estimated_cost",
        ),
        CheckConstraint(
            "processing_duration_ms IS NULL OR processing_duration_ms >= 0",
            name="ck_ai_jobs_processing_duration",
        ),
        CheckConstraint(
            "last_error_message_safe IS NULL OR length(last_error_message_safe) <= 1000",
            name="ck_ai_jobs_safe_error_length",
        ),
        CheckConstraint(
            "idempotency_key IS NULL OR length(idempotency_key) <= 200",
            name="ck_ai_jobs_idempotency_length",
        ),
        CheckConstraint(
            "worker_id IS NULL OR (length(trim(worker_id)) > 0 AND length(worker_id) <= 200)",
            name="ck_ai_jobs_worker_id",
        ),
        CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_ai_jobs_currency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_ai_jobs_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            [
                "transcripts.organisation_id",
                "transcripts.id",
                "transcripts.meeting_id",
            ],
            name="fk_ai_jobs_transcript_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_ai_jobs_requester_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_ai_jobs_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "meeting_id",
            "transcript_id",
            "transcript_version",
            name="uq_ai_jobs_artifact_trace",
        ),
        UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_version",
            "job_type",
            "idempotency_key",
            name="uq_ai_jobs_idempotency",
        ),
        Index("ix_ai_jobs_organisation_meeting", "organisation_id", "meeting_id"),
        Index("ix_ai_jobs_organisation_status", "organisation_id", "status"),
        Index("ix_ai_jobs_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_ai_jobs_status_lease_expires", "status", "lease_expires_at"),
        Index(
            "ix_ai_jobs_transcript_version",
            "organisation_id",
            "transcript_id",
            "transcript_version",
        ),
        Index("ix_ai_jobs_organisation_created", "organisation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=AIJobType.INFRASTRUCTURE_TEST.value,
        server_default=AIJobType.INFRASTRUCTURE_TEST.value,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AIJobStatus.PENDING.value,
        server_default=AIJobStatus.PENDING.value,
    )
    provider_key: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    prompt_key: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(200))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message_safe: Mapped[str | None] = mapped_column(String(1000))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    input_token_count: Mapped[int | None] = mapped_column(Integer)
    output_token_count: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(3))
    processing_duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    organisation: Mapped[Organisation] = relationship(
        back_populates="ai_jobs",
        foreign_keys=[organisation_id],
    )
    meeting: Mapped[Meeting] = relationship(
        back_populates="ai_jobs",
        foreign_keys=[organisation_id, meeting_id],
        viewonly=True,
    )
    transcript: Mapped[Transcript] = relationship(
        back_populates="ai_jobs",
        foreign_keys=[organisation_id, transcript_id, meeting_id],
        viewonly=True,
    )
    requested_by_user: Mapped[User] = relationship(
        back_populates="requested_ai_jobs",
        foreign_keys=[requested_by_user_id],
    )
    artifacts: Mapped[list[AIArtifact]] = relationship(
        back_populates="job",
        foreign_keys=(
            "[AIArtifact.organisation_id, AIArtifact.job_id, AIArtifact.meeting_id, "
            "AIArtifact.transcript_id, AIArtifact.transcript_version]"
        ),
    )


class AIArtifact(Base):
    __tablename__ = "ai_artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('infrastructure_test', 'executive_summary', 'decisions', 'action_items', 'risks_blockers')",
            name="ck_ai_artifacts_type",
        ),
        CheckConstraint("artifact_version > 0", name="ck_ai_artifacts_version"),
        CheckConstraint("schema_version > 0", name="ck_ai_artifacts_schema_version"),
        CheckConstraint("transcript_version > 0", name="ck_ai_artifacts_transcript_version"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ai_artifacts_confidence",
        ),
        CheckConstraint(
            "prompt_version IS NULL OR prompt_version > 0",
            name="ck_ai_artifacts_prompt_version",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_ai_artifacts_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            [
                "transcripts.organisation_id",
                "transcripts.id",
                "transcripts.meeting_id",
            ],
            name="fk_ai_artifacts_transcript_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organisation_id",
                "job_id",
                "meeting_id",
                "transcript_id",
                "transcript_version",
            ],
            [
                "ai_jobs.organisation_id",
                "ai_jobs.id",
                "ai_jobs.meeting_id",
                "ai_jobs.transcript_id",
                "ai_jobs.transcript_version",
            ],
            name="fk_ai_artifacts_job_trace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_ai_artifacts_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_id",
            "transcript_version",
            "artifact_type",
            "artifact_version",
            name="uq_ai_artifacts_logical_version",
        ),
        Index(
            "ix_ai_artifacts_organisation_meeting",
            "organisation_id",
            "meeting_id",
        ),
        Index(
            "ix_ai_artifacts_organisation_meeting_type",
            "organisation_id",
            "meeting_id",
            "artifact_type",
        ),
        Index(
            "ix_ai_artifacts_transcript_version",
            "organisation_id",
            "transcript_id",
            "transcript_version",
        ),
        Index("ix_ai_artifacts_job", "organisation_id", "job_id"),
        Index(
            "ix_ai_artifacts_latest_version",
            "organisation_id",
            "meeting_id",
            "transcript_version",
            "artifact_type",
            "artifact_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    artifact_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=AIArtifactType.INFRASTRUCTURE_TEST.value,
        server_default=AIArtifactType.INFRASTRUCTURE_TEST.value,
    )
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_key: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    provider_key: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    content_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organisation: Mapped[Organisation] = relationship(
        back_populates="ai_artifacts",
        foreign_keys=[organisation_id],
        viewonly=True,
    )
    meeting: Mapped[Meeting] = relationship(
        back_populates="ai_artifacts",
        foreign_keys=[organisation_id, meeting_id],
        viewonly=True,
    )
    transcript: Mapped[Transcript] = relationship(
        back_populates="ai_artifacts",
        foreign_keys=[organisation_id, transcript_id, meeting_id],
        viewonly=True,
    )
    job: Mapped[AIJob] = relationship(
        back_populates="artifacts",
        foreign_keys=[
            organisation_id,
            job_id,
            meeting_id,
            transcript_id,
            transcript_version,
        ],
    )
