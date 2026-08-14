from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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
    CaptureSessionStatus,
    CaptureSessionType,
    CompanyStatus,
    EvidenceLifecycleStatus,
    EvidenceOriginClass,
    EvidenceRetentionClass,
    EvidenceSupportClass,
    EvidenceType,
    EvidenceValidationState,
    InteractionCreationOrigin,
    InteractionLifecycleStatus,
    InteractionType,
    MeetingStatus,
    MeetingType,
    OpportunityAuditAction,
    OpportunityStage,
    OpportunityStatus,
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
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organisations_slug"),
        UniqueConstraint("external_auth_id", name="uq_organisations_external_auth_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    external_auth_id: Mapped[str | None] = mapped_column(String(255))

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
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_auth_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")

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
        CheckConstraint("role IN ('admin', 'member')", name="ck_memberships_role"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_memberships_status"),
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
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

    organisation: Mapped[Organisation] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class OrganisationBetaSettings(TimestampMixin, Base):
    __tablename__ = "organisation_beta_settings"
    __table_args__ = (
        CheckConstraint(
            "retention_days IS NULL OR retention_days IN (30, 90, 180)",
            name="ck_organisation_beta_settings_retention",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    retention_days: Mapped[int | None] = mapped_column(Integer)


class DataNoticeAcknowledgement(Base):
    __tablename__ = "data_notice_acknowledgements"
    __table_args__ = (
        CheckConstraint("notice_version > 0", name="ck_data_notice_acknowledgements_version"),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_data_notice_acknowledgements_membership",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organisation_id",
            "user_id",
            "notice_version",
            name="uq_data_notice_acknowledgements_version",
        ),
        Index(
            "ix_data_notice_acknowledgements_organisation_version",
            "organisation_id",
            "notice_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    notice_version: Mapped[int] = mapped_column(Integer, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"
    __table_args__ = (
        CheckConstraint("current_step >= 0 AND current_step <= 9", name="ck_onboarding_progress_step"),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_onboarding_progress_membership",
            ondelete="CASCADE",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AIUsageCounter(Base):
    __tablename__ = "ai_usage_counters"
    __table_args__ = (
        CheckConstraint("generation_count >= 0", name="ck_ai_usage_counters_generations"),
        CheckConstraint("provider_request_count >= 0", name="ck_ai_usage_counters_provider_requests"),
        Index("ix_ai_usage_counters_organisation_date", "organisation_id", "usage_date"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


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
            "stage IN ('qualification', 'discovery', 'evaluation', 'proposal', "
            "'negotiation', 'procurement', 'closed_won', 'closed_lost', 'other')",
            name="ck_opportunities_stage",
        ),
        CheckConstraint(
            "status IN ('open', 'won', 'lost', 'on_hold')",
            name="ck_opportunities_status",
        ),
        CheckConstraint(
            "(estimated_value IS NULL AND currency IS NULL) OR "
            "(estimated_value IS NOT NULL AND estimated_value >= 0 AND currency IS NOT NULL)",
            name="ck_opportunities_value_currency",
        ),
        CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_opportunities_currency",
        ),
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
        Index("ix_opportunities_organisation_status", "organisation_id", "status"),
        Index("ix_opportunities_organisation_close", "organisation_id", "expected_close_date"),
        Index("ix_opportunities_organisation_updated", "organisation_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OpportunityStage.DISCOVERY.value,
        server_default=OpportunityStage.DISCOVERY.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OpportunityStatus.OPEN.value,
        server_default=OpportunityStatus.OPEN.value,
    )
    estimated_value: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class OpportunityAuditEvent(Base):
    __tablename__ = "opportunity_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('created', 'updated', 'deleted', 'meeting_associated', 'meeting_disassociated')",
            name="ck_opportunity_audit_events_action",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_opportunity_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_opportunity_audit_events_organisation_entity_created",
            "organisation_id",
            "opportunity_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=OpportunityAuditAction.UPDATED.value,
    )
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


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


class Interaction(TimestampMixin, Base):
    __tablename__ = "interactions"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_interactions_title"),
        CheckConstraint(
            "interaction_type IN ("
            "'online_meeting', 'face_to_face_meeting', 'presentation', 'workshop', "
            "'site_visit', 'executive_lunch', 'phone_call', 'conference_interaction', "
            "'trade_show_interaction', 'manual_interaction'"
            ")",
            name="ck_interactions_type",
        ),
        CheckConstraint(
            "lifecycle_status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_interactions_lifecycle_status",
        ),
        CheckConstraint(
            "creation_origin IN ('manual', 'meeting_compatibility', 'imported_external')",
            name="ck_interactions_creation_origin",
        ),
        CheckConstraint(
            "scheduled_end_at IS NULL OR scheduled_start_at IS NULL OR scheduled_end_at >= scheduled_start_at",
            name="ck_interactions_scheduled_range",
        ),
        CheckConstraint(
            "actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at",
            name="ck_interactions_actual_range",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_interactions_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_interactions_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_interactions_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_interactions_organisation_id_id"),
        Index("ix_interactions_organisation_scheduled", "organisation_id", "scheduled_start_at"),
        Index("ix_interactions_organisation_status", "organisation_id", "lifecycle_status"),
        Index("ix_interactions_organisation_type", "organisation_id", "interaction_type"),
        Index("ix_interactions_organisation_company", "organisation_id", "company_id"),
        Index("ix_interactions_organisation_opportunity", "organisation_id", "opportunity_id"),
        Index("ix_interactions_organisation_deleted", "organisation_id", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    interaction_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=InteractionType.MANUAL_INTERACTION.value,
        server_default=InteractionType.MANUAL_INTERACTION.value,
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InteractionLifecycleStatus.PLANNED.value,
        server_default=InteractionLifecycleStatus.PLANNED.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(64))
    creation_origin: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=InteractionCreationOrigin.MANUAL.value,
        server_default=InteractionCreationOrigin.MANUAL.value,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PreInteractionBrief(Base):
    __tablename__ = "pre_interaction_briefs"
    __table_args__ = (
        CheckConstraint("brief_version > 0", name="ck_pre_interaction_briefs_version"),
        CheckConstraint("schema_version > 0", name="ck_pre_interaction_briefs_schema_version"),
        CheckConstraint("status IN ('completed', 'failed', 'cancelled')", name="ck_pre_interaction_briefs_status"),
        CheckConstraint(
            "length(source_context_fingerprint) = 64",
            name="ck_pre_interaction_briefs_fingerprint",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_pre_interaction_briefs_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_pre_interaction_briefs_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_pre_interaction_briefs_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_pre_interaction_briefs_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_pre_interaction_briefs_reviewer_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_pre_interaction_briefs_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "brief_version",
            name="uq_pre_interaction_briefs_logical_version",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "source_context_fingerprint",
            "schema_version",
            name="uq_pre_interaction_briefs_idempotency",
        ),
        Index(
            "ix_pre_interaction_briefs_organisation_interaction_created",
            "organisation_id",
            "interaction_id",
            "created_at",
        ),
        Index(
            "ix_pre_interaction_briefs_organisation_company",
            "organisation_id",
            "company_id",
        ),
        Index(
            "ix_pre_interaction_briefs_organisation_opportunity",
            "organisation_id",
            "opportunity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    brief_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed", server_default="completed")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    source_references_json: Mapped[list[dict[str, object]]] = mapped_column(JSON(none_as_null=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


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
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_meetings_interaction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_meetings_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_meetings_opportunity_tenant",
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
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            name="uq_meetings_organisation_interaction",
        ),
        Index("ix_meetings_organisation_date", "organisation_id", "meeting_date"),
        Index("ix_meetings_organisation_status", "organisation_id", "status"),
        Index("ix_meetings_organisation_type", "organisation_id", "meeting_type"),
        Index("ix_meetings_organisation_company", "organisation_id", "company_id"),
        Index("ix_meetings_organisation_opportunity_date", "organisation_id", "opportunity_id", "meeting_date"),
        Index("ix_meetings_organisation_deleted", "organisation_id", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
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
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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


class CaptureSession(TimestampMixin, Base):
    __tablename__ = "capture_sessions"
    __table_args__ = (
        CheckConstraint(
            "capture_type IN ("
            "'ai_debrief', 'voice_journal', 'live_recording', 'visual_capture', "
            "'uploaded_transcript', 'uploaded_recording', 'manual_notes'"
            ")",
            name="ck_capture_sessions_type",
        ),
        CheckConstraint(
            "status IN ('created', 'capturing', 'completed', 'abandoned', 'failed')",
            name="ck_capture_sessions_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_capture_sessions_time_range",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_capture_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "started_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_capture_sessions_starter_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_capture_sessions_organisation_id_id"),
        Index("ix_capture_sessions_organisation_interaction", "organisation_id", "interaction_id"),
        Index("ix_capture_sessions_organisation_status", "organisation_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capture_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=CaptureSessionType.MANUAL_NOTES.value,
        server_default=CaptureSessionType.MANUAL_NOTES.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CaptureSessionStatus.CREATED.value,
        server_default=CaptureSessionStatus.CREATED.value,
    )
    started_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('transcript', 'user_observation', 'recording', 'visual', "
            "'document', 'email', 'system_metadata')",
            name="ck_evidence_type",
        ),
        CheckConstraint(
            "origin_class IN ('customer_direct', 'salesperson_reported', 'system_metadata', "
            "'imported_external', 'seller_prepared', 'ai_inferred')",
            name="ck_evidence_origin_class",
        ),
        CheckConstraint(
            "support_class IN ('direct', 'reported', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded')",
            name="ck_evidence_support_class",
        ),
        CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'disputed', 'rejected', 'not_applicable')",
            name="ck_evidence_validation_state",
        ),
        CheckConstraint(
            "lifecycle_status IN ('received', 'available', 'excluded', 'superseded', 'deleted')",
            name="ck_evidence_lifecycle_status",
        ),
        CheckConstraint(
            "retention_class IN ('inherited', 'short_lived', 'standard')",
            name="ck_evidence_retention_class",
        ),
        CheckConstraint(
            "effective_end_at IS NULL OR effective_start_at IS NULL OR effective_end_at >= effective_start_at",
            name="ck_evidence_effective_range",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_evidence_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_evidence_capture_session_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "captured_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_evidence_captured_by_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_evidence_organisation_id_id"),
        Index("ix_evidence_organisation_interaction", "organisation_id", "interaction_id"),
        Index("ix_evidence_organisation_capture_session", "organisation_id", "capture_session_id"),
        Index("ix_evidence_organisation_status", "organisation_id", "lifecycle_status"),
        Index("ix_evidence_organisation_type", "organisation_id", "evidence_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capture_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=EvidenceType.SYSTEM_METADATA.value,
        server_default=EvidenceType.SYSTEM_METADATA.value,
    )
    origin_class: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=EvidenceOriginClass.SYSTEM_METADATA.value,
        server_default=EvidenceOriginClass.SYSTEM_METADATA.value,
    )
    support_class: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EvidenceSupportClass.DIRECT.value,
        server_default=EvidenceSupportClass.DIRECT.value,
    )
    validation_state: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=EvidenceValidationState.NOT_APPLICABLE.value,
        server_default=EvidenceValidationState.NOT_APPLICABLE.value,
    )
    captured_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    effective_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifecycle_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EvidenceLifecycleStatus.RECEIVED.value,
        server_default=EvidenceLifecycleStatus.RECEIVED.value,
    )
    retention_class: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EvidenceRetentionClass.INHERITED.value,
        server_default=EvidenceRetentionClass.INHERITED.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InteractionAuditEvent(Base):
    __tablename__ = "interaction_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('created', 'updated', 'completed', 'cancelled', 'deleted', 'meeting_linked')",
            name="ck_interaction_audit_events_action",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_audit_events_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_interaction_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_interaction_audit_events_organisation_id_id",
        ),
        Index(
            "ix_interaction_audit_events_organisation_interaction_created",
            "organisation_id",
            "interaction_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AIJob(TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('infrastructure_test', 'executive_summary', 'decisions', 'action_items', 'risks_blockers', 'open_questions', 'buying_signals', 'objections_competitive_signals', 'stakeholder_intelligence', 'next_best_action', 'follow_up_email')",
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
        CheckConstraint(
            "(job_type = 'follow_up_email' AND composition_tone IS NOT NULL AND "
            "composition_tone IN ('professional', 'friendly', 'executive')) OR "
            "(job_type <> 'follow_up_email' AND composition_tone IS NULL)",
            name="ck_ai_jobs_composition_tone",
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
    composition_tone: Mapped[str | None] = mapped_column(String(20))
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
            "artifact_type IN ('infrastructure_test', 'executive_summary', 'decisions', 'action_items', 'risks_blockers', 'open_questions', 'buying_signals', 'objections_competitive_signals', 'stakeholder_intelligence', 'next_best_action', 'follow_up_email')",
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


class RevenueBrainSnapshot(Base):
    __tablename__ = "revenue_brain_snapshots"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_revenue_brain_snapshots_version"),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_snapshots_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_snapshots_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_revenue_brain_snapshots_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "summary_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_summary_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "buying_signals_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_buying_signals_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "objections_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_objections_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "stakeholders_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_stakeholders_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "decisions_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_decisions_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "actions_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_actions_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "risks_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_risks_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "questions_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_questions_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "next_best_action_reference"],
            ["ai_artifacts.organisation_id", "ai_artifacts.id"],
            name="fk_revenue_brain_snapshots_next_best_action_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_revenue_brain_snapshots_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_version_id",
            name="uq_revenue_brain_snapshots_meeting_transcript_version",
        ),
        Index(
            "ix_revenue_brain_snapshots_organisation_company_created",
            "organisation_id",
            "company_id",
            "created_at",
        ),
        Index(
            "ix_revenue_brain_snapshots_organisation_meeting",
            "organisation_id",
            "meeting_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    summary_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    buying_signals_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    objections_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stakeholders_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    decisions_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actions_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    risks_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    questions_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    next_best_action_reference: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RevenueBrainInsight(Base):
    __tablename__ = "revenue_brain_insights"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('account', 'opportunity')",
            name="ck_revenue_brain_insights_scope",
        ),
        CheckConstraint(
            "status = 'completed'",
            name="ck_revenue_brain_insights_status",
        ),
        CheckConstraint(
            "reasoning_version > 0",
            name="ck_revenue_brain_insights_reasoning_version",
        ),
        CheckConstraint(
            "from_snapshot_id <> to_snapshot_id",
            name="ck_revenue_brain_insights_distinct_snapshots",
        ),
        CheckConstraint(
            "(scope = 'account' AND opportunity_id IS NULL AND scope_target_id = company_id) "
            "OR (scope = 'opportunity' AND opportunity_id IS NOT NULL "
            "AND scope_target_id = opportunity_id)",
            name="ck_revenue_brain_insights_scope_target",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_insights_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_insights_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "from_snapshot_id"],
            ["revenue_brain_snapshots.organisation_id", "revenue_brain_snapshots.id"],
            name="fk_revenue_brain_insights_from_snapshot_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "to_snapshot_id"],
            ["revenue_brain_snapshots.organisation_id", "revenue_brain_snapshots.id"],
            name="fk_revenue_brain_insights_to_snapshot_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_revenue_brain_insights_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "scope",
            "scope_target_id",
            "from_snapshot_id",
            "to_snapshot_id",
            "reasoning_version",
            name="uq_revenue_brain_insights_comparison_version",
        ),
        Index(
            "ix_revenue_brain_insights_organisation_company_created",
            "organisation_id",
            "company_id",
            "created_at",
        ),
        Index(
            "ix_revenue_brain_insights_organisation_opportunity_created",
            "organisation_id",
            "opportunity_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    to_snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reasoning_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed", server_default="completed")
    content_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BetaFeedback(Base):
    __tablename__ = "beta_feedback"
    __table_args__ = (
        CheckConstraint(
            "category IN ('bug', 'confusing', 'inaccurate_intelligence', 'missing_feature', 'other')",
            name="ck_beta_feedback_category",
        ),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_beta_feedback_rating"),
        CheckConstraint("length(trim(message)) BETWEEN 1 AND 2000", name="ck_beta_feedback_message"),
        CheckConstraint("length(current_route) BETWEEN 1 AND 500", name="ck_beta_feedback_route"),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_beta_feedback_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_beta_feedback_meeting_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_beta_feedback_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_beta_feedback_organisation_id_id"),
        Index("ix_beta_feedback_organisation_created", "organisation_id", "created_at"),
        Index("ix_beta_feedback_user_created", "organisation_id", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    current_route: Mapped[str] = mapped_column(String(500), nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BetaDataRequest(TimestampMixin, Base):
    __tablename__ = "beta_data_requests"
    __table_args__ = (
        CheckConstraint("request_type IN ('export', 'organisation_deletion')", name="ck_beta_data_requests_type"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_beta_data_requests_status",
        ),
        CheckConstraint(
            "failure_code IS NULL OR length(failure_code) <= 100",
            name="ck_beta_data_requests_failure_code",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_beta_data_requests_requester",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_beta_data_requests_organisation_id_id"),
        Index("ix_beta_data_requests_organisation_status", "organisation_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output_path: Mapped[str | None] = mapped_column(String(1000))
    failure_code: Mapped[str | None] = mapped_column(String(100))


class BetaSystemEvent(Base):
    __tablename__ = "beta_system_events"
    __table_args__ = (
        CheckConstraint("length(event_type) BETWEEN 1 AND 100", name="ck_beta_system_events_type"),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_beta_system_events_actor_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_beta_system_events_organisation_id_id"),
        Index("ix_beta_system_events_organisation_created", "organisation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
