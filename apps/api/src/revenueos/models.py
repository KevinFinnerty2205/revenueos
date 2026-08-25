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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from revenueos.domain import (
    ActionAudience,
    ActionPriority,
    ActionRiskClass,
    ActionStatus,
    ActionType,
    AIArtifactType,
    AIJobStatus,
    AIJobType,
    AttendanceStatus,
    CaptureSessionStatus,
    CaptureSessionType,
    CompanyStatus,
    ConnectionStatus,
    ConnectorKey,
    EvidenceLifecycleStatus,
    EvidenceOriginClass,
    EvidenceRetentionClass,
    EvidenceSupportClass,
    EvidenceType,
    EvidenceValidationState,
    ExecutionStatus,
    InteractionCreationOrigin,
    InteractionLifecycleStatus,
    InteractionType,
    LiveInteractionStatus,
    LiveSignalResolution,
    MeetingStatus,
    MeetingType,
    OnlineMeetingIngestionState,
    OnlineMeetingPlatform,
    OpportunityAuditAction,
    OpportunityStage,
    OpportunityStatus,
    ParticipantRole,
    ProspectResearchRunStatus,
    ProvisionalSignalLifecycle,
    TaskPriority,
    TaskStatus,
    TranscriptProvenance,
    TranscriptSource,
    TranscriptSpeakerRole,
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


class OrganisationModuleEntitlement(TimestampMixin, Base):
    __tablename__ = "organisation_module_entitlements"
    __table_args__ = (
        CheckConstraint("module_key = 'prospect'", name="ck_module_entitlements_key"),
        CheckConstraint("source = 'manual_private_beta'", name="ck_module_entitlements_source"),
        ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_module_entitlements_configurer",
            ondelete="RESTRICT",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    module_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    source: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="manual_private_beta",
        server_default="manual_private_beta",
    )
    configured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProspectUsageCounter(Base):
    __tablename__ = "prospect_usage_counters"
    __table_args__ = (
        CheckConstraint(
            "scope_key = 'organisation' OR scope_key LIKE 'user:%'",
            name="ck_prospect_usage_scope",
        ),
        CheckConstraint("research_run_count >= 0", name="ck_prospect_usage_count"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    research_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


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


class RecordingUsageCounter(Base):
    __tablename__ = "recording_usage_counters"
    __table_args__ = (
        CheckConstraint("uploaded_bytes >= 0", name="ck_recording_usage_uploaded_bytes"),
        CheckConstraint("transcription_minutes >= 0", name="ck_recording_usage_transcription_minutes"),
        CheckConstraint("transcription_request_count >= 0", name="ck_recording_usage_request_count"),
        Index("ix_recording_usage_organisation_date", "organisation_id", "usage_date"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    transcription_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    transcription_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
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
        Index("ix_companies_organisation_domain", "organisation_id", "normalized_domain"),
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
    normalized_domain: Mapped[str | None] = mapped_column(String(253))
    industry: Mapped[str | None] = mapped_column(String(120))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CompanyStatus.PROSPECT.value,
        server_default=CompanyStatus.PROSPECT.value,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class ProspectResearchTarget(TimestampMixin, Base):
    __tablename__ = "prospect_research_targets"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_prospect_targets_name"),
        CheckConstraint("length(trim(normalized_domain)) > 0", name="ck_prospect_targets_domain"),
        CheckConstraint(
            "(promoted_company_id IS NULL AND promoted_by_user_id IS NULL AND promoted_at IS NULL) OR "
            "(promoted_company_id IS NOT NULL AND promoted_by_user_id IS NOT NULL AND promoted_at IS NOT NULL)",
            name="ck_prospect_targets_promotion",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "promoted_company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_prospect_targets_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "promoted_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_prospect_targets_promoter",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_targets_org_id"),
        UniqueConstraint("organisation_id", "normalized_domain", name="uq_prospect_targets_org_domain"),
        UniqueConstraint(
            "organisation_id",
            "provider_key",
            "provider_candidate_id",
            name="uq_prospect_targets_provider_candidate",
        ),
        Index("ix_prospect_targets_org_updated", "organisation_id", "updated_at"),
        Index("ix_prospect_targets_org_company", "organisation_id", "promoted_company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_candidate_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    website_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(120))
    provider_attribution: Mapped[str] = mapped_column(String(120), nullable=False)
    promoted_company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    promoted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProspectResearchRun(TimestampMixin, Base):
    __tablename__ = "prospect_research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'fetching', 'synthesizing', 'completed', 'partial', 'failed')",
            name="ck_prospect_runs_status",
        ),
        CheckConstraint("schema_version > 0", name="ck_prospect_runs_schema_version"),
        CheckConstraint("attempt_count >= 0", name="ck_prospect_runs_attempts"),
        CheckConstraint("max_attempts >= 1", name="ck_prospect_runs_max_attempts"),
        CheckConstraint(
            "last_error_message_safe IS NULL OR length(last_error_message_safe) <= 500",
            name="ck_prospect_runs_error_length",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_runs_target",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_prospect_runs_requester",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "refresh_of_run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_runs_refresh",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_runs_org_id"),
        UniqueConstraint("organisation_id", "id", "target_id", name="uq_prospect_runs_org_id_target"),
        UniqueConstraint(
            "organisation_id",
            "target_id",
            "idempotency_key",
            name="uq_prospect_runs_idempotency",
        ),
        Index("ix_prospect_runs_org_target_created", "organisation_id", "target_id", "created_at"),
        Index("ix_prospect_runs_org_status", "organisation_id", "status"),
        Index("ix_prospect_runs_status_attempt", "status", "next_attempt_at"),
        Index("ix_prospect_runs_status_lease", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    refresh_of_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=ProspectResearchRunStatus.PENDING.value,
        server_default=ProspectResearchRunStatus.PENDING.value,
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message_safe: Mapped[str | None] = mapped_column(String(500))
    source_fingerprint: Mapped[str | None] = mapped_column(String(64))


class ProspectResearchSource(Base):
    __tablename__ = "prospect_research_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('official_website', 'company_newsroom', 'careers_page', "
            "'structured_provider', 'public_filing', 'reputable_news', 'other_public')",
            name="ck_prospect_sources_type",
        ),
        CheckConstraint(
            "authority_class IN ('primary', 'official_public', 'regulatory', 'reputable_secondary', "
            "'structured_provider', 'other_public')",
            name="ck_prospect_sources_authority",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_sources_run",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_sources_org_id"),
        UniqueConstraint("organisation_id", "id", "run_id", name="uq_prospect_sources_org_id_run"),
        UniqueConstraint("organisation_id", "run_id", "source_key", name="uq_prospect_sources_run_key"),
        UniqueConstraint("organisation_id", "run_id", "canonical_url", name="uq_prospect_sources_run_url"),
        UniqueConstraint(
            "organisation_id",
            "run_id",
            "content_fingerprint",
            name="uq_prospect_sources_run_fingerprint",
        ),
        Index("ix_prospect_sources_org_run", "organisation_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authority_class: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_source_id: Mapped[str | None] = mapped_column(String(200))
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class ProspectResearchObservation(Base):
    __tablename__ = "prospect_research_observations"
    __table_args__ = (
        CheckConstraint(
            "category IN ('company_profile', 'industry', 'location', 'size', 'business_model', "
            "'product_service', 'strategic_initiative', 'expansion', 'hiring', 'leadership_change', "
            "'funding_financial', 'technology', 'regulatory', 'partnership', 'customer_market', "
            "'trigger', 'potential_fit', 'other')",
            name="ck_prospect_observations_category",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_observations_trust",
        ),
        CheckConstraint("relevance IN ('high', 'normal')", name="ck_prospect_observations_relevance"),
        CheckConstraint(
            "freshness IN ('stable', 'time_sensitive')",
            name="ck_prospect_observations_freshness",
        ),
        CheckConstraint("status = 'current'", name="ck_prospect_observations_status"),
        CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 600",
            name="ck_prospect_observations_statement",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_observations_run",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_observations_org_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "run_id",
            name="uq_prospect_observations_org_id_run",
        ),
        UniqueConstraint(
            "organisation_id",
            "run_id",
            "observation_key",
            name="uq_prospect_observations_run_key",
        ),
        Index("ix_prospect_observations_org_run", "organisation_id", "run_id"),
        Index("ix_prospect_observations_org_trust", "organisation_id", "trust_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    observation_key: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    statement: Mapped[str] = mapped_column(String(600), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    relevance: Mapped[str] = mapped_column(String(12), nullable=False, default="normal", server_default="normal")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="current", server_default="current")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProspectResearchObservationSource(Base):
    __tablename__ = "prospect_research_observation_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "observation_id", "run_id"],
            [
                "prospect_research_observations.organisation_id",
                "prospect_research_observations.id",
                "prospect_research_observations.run_id",
            ],
            name="fk_prospect_observation_sources_observation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_observation_sources_source",
            ondelete="CASCADE",
        ),
        Index("ix_prospect_observation_sources_org_run", "organisation_id", "run_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


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


class MethodologyDefinition(TimestampMixin, Base):
    __tablename__ = "methodology_definitions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_methodology_definitions_status"),
        CheckConstraint("current_version > 0", name="ck_methodology_definitions_version"),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_definitions_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_methodology_definitions_org_id"),
        Index("ix_methodology_definitions_org_status", "organisation_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MethodologyDefinitionVersion(Base):
    __tablename__ = "methodology_definition_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_methodology_versions_version"),
        CheckConstraint("schema_version = 1", name="ck_methodology_versions_schema"),
        CheckConstraint("length(content_fingerprint) = 64", name="ck_methodology_versions_fingerprint"),
        ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_versions_definition",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_versions_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_methodology_versions_org_id"),
        UniqueConstraint(
            "organisation_id",
            "definition_id",
            "version",
            name="uq_methodology_versions_definition_version",
        ),
        Index(
            "ix_methodology_versions_org_definition",
            "organisation_id",
            "definition_id",
            "version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrganisationMethodologySetting(TimestampMixin, Base):
    __tablename__ = "organisation_methodology_settings"
    __table_args__ = (
        CheckConstraint(
            "selection IN ('none', 'meddic', 'meddpicc', 'bant', 'spiced', 'custom')",
            name="ck_methodology_settings_selection",
        ),
        CheckConstraint(
            "(selection = 'custom' AND custom_definition_id IS NOT NULL) OR "
            "(selection <> 'custom' AND custom_definition_id IS NULL)",
            name="ck_methodology_settings_custom",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "custom_definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_settings_custom",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "updated_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_settings_updater",
            ondelete="RESTRICT",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    selection: Mapped[str] = mapped_column(String(16), nullable=False, default="none", server_default="none")
    custom_definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class MethodologyProjection(Base):
    __tablename__ = "methodology_projections"
    __table_args__ = (
        CheckConstraint("methodology_kind IN ('standard', 'custom')", name="ck_methodology_projections_kind"),
        CheckConstraint("definition_version > 0", name="ck_methodology_projections_definition_version"),
        CheckConstraint("projection_version > 0", name="ck_methodology_projections_version"),
        CheckConstraint("engine_version = 1", name="ck_methodology_projections_engine"),
        CheckConstraint("schema_version = 1", name="ck_methodology_projections_schema"),
        CheckConstraint("length(source_fingerprint) = 64", name="ck_methodology_projections_fingerprint"),
        CheckConstraint(
            "(methodology_kind = 'custom' AND definition_id IS NOT NULL) OR "
            "(methodology_kind = 'standard' AND definition_id IS NULL)",
            name="ck_methodology_projections_definition",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_methodology_projections_opportunity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_projections_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "generated_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_projections_generator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_methodology_projections_org_id"),
        UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "definition_key",
            "definition_version",
            "source_fingerprint",
            name="uq_methodology_projections_idempotency",
        ),
        UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "projection_version",
            name="uq_methodology_projections_logical_version",
        ),
        Index(
            "ix_methodology_projections_org_opportunity_generated",
            "organisation_id",
            "opportunity_id",
            "generated_at",
        ),
        Index(
            "ix_methodology_projections_org_definition",
            "organisation_id",
            "definition_key",
            "definition_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    methodology_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    definition_key: Mapped[str] = mapped_column(String(100), nullable=False)
    definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MethodologyReview(Base):
    __tablename__ = "methodology_reviews"
    __table_args__ = (
        CheckConstraint(
            "action IN ('confirm_interpretation', 'clarify', 'mark_not_known', 'mark_incorrect')",
            name="ck_methodology_reviews_action",
        ),
        CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 64", name="ck_methodology_reviews_field"),
        CheckConstraint("length(trim(idempotency_key)) BETWEEN 1 AND 200", name="ck_methodology_reviews_key"),
        CheckConstraint(
            "(action = 'clarify' AND clarification_text IS NOT NULL AND clarification_evidence_id IS NOT NULL) OR "
            "(action <> 'clarify' AND clarification_text IS NULL AND clarification_evidence_id IS NULL)",
            name="ck_methodology_reviews_clarification",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "projection_id"],
            ["methodology_projections.organisation_id", "methodology_projections.id"],
            name="fk_methodology_reviews_projection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_methodology_reviews_opportunity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_reviews_reviewer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "clarification_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_methodology_reviews_evidence",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_methodology_reviews_org_id"),
        UniqueConstraint(
            "organisation_id",
            "reviewed_by_user_id",
            "idempotency_key",
            name="uq_methodology_reviews_idempotency",
        ),
        Index(
            "ix_methodology_reviews_org_opportunity_field",
            "organisation_id",
            "opportunity_id",
            "field_key",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    projection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    clarification_text: Mapped[str | None] = mapped_column(String(1000))
    clarification_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ActionProposal(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('follow_up_email', 'send_requested_material', 'create_task', "
            "'follow_up_stakeholder', 'schedule_interaction', 'update_opportunity', "
            "'update_contact', 'log_interaction', 'update_stakeholder', 'add_decision', 'add_commitment', "
            "'add_risk', 'update_timeline', 'update_procurement', 'update_security_legal', "
            "'create_reminder', 'notify_internal', 'prepare_next_interaction', "
            "'resolve_open_question', 'review_conflict', 'other')",
            name="ck_action_proposals_type",
        ),
        CheckConstraint(
            "status IN ('proposed', 'edited', 'approved', 'rejected', 'superseded', 'completed_manually')",
            name="ck_action_proposals_status",
        ),
        CheckConstraint(
            "priority IN ('high', 'normal', 'low')",
            name="ck_action_proposals_priority",
        ),
        CheckConstraint(
            "audience IN ('internal', 'customer_facing')",
            name="ck_action_proposals_audience",
        ),
        CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_action_proposals_risk",
        ),
        CheckConstraint("current_version > 0", name="ck_action_proposals_current_version"),
        CheckConstraint(
            "approved_version IS NULL OR approved_version BETWEEN 1 AND current_version",
            name="ck_action_proposals_approved_version",
        ),
        CheckConstraint("length(source_fingerprint) = 64", name="ck_action_proposals_fingerprint"),
        CheckConstraint("length(semantic_key) = 64", name="ck_action_proposals_semantic_key"),
        CheckConstraint(
            "rejection_reason_code IS NULL OR rejection_reason_code IN "
            "('already_done', 'incorrect', 'not_relevant', 'unsupported', 'duplicate', 'not_now', 'other')",
            name="ck_action_proposals_rejection_reason",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_action_proposals_opportunity_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_action_proposals_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_action_proposals_creator_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_action_proposals_reviewer_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "completed_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_action_proposals_completer_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "supersedes_action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_proposals_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_action_proposals_org_id"),
        UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "source_fingerprint",
            name="uq_action_proposals_source_fingerprint",
        ),
        Index(
            "ix_action_proposals_org_opportunity_status",
            "organisation_id",
            "opportunity_id",
            "status",
        ),
        Index(
            "ix_action_proposals_org_created",
            "organisation_id",
            "generated_at",
        ),
        Index(
            "ix_action_proposals_org_semantic",
            "organisation_id",
            "opportunity_id",
            "semantic_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    action_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=ActionType.OTHER.value, server_default=ActionType.OTHER.value
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ActionStatus.PROPOSED.value, server_default=ActionStatus.PROPOSED.value
    )
    priority: Mapped[str] = mapped_column(
        String(12), nullable=False, default=ActionPriority.NORMAL.value, server_default=ActionPriority.NORMAL.value
    )
    audience: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActionAudience.INTERNAL.value, server_default=ActionAudience.INTERNAL.value
    )
    risk_class: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ActionRiskClass.INTERNAL_LOW_RISK.value,
        server_default=ActionRiskClass.INTERNAL_LOW_RISK.value,
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    approved_version: Mapped[int | None] = mapped_column(Integer)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason_code: Mapped[str | None] = mapped_column(String(24))
    supersedes_action_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionProposalVersion(Base):
    __tablename__ = "action_proposal_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_action_versions_version"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_action_versions_title"),
        CheckConstraint(
            "length(trim(description)) BETWEEN 1 AND 2000",
            name="ck_action_versions_description",
        ),
        CheckConstraint(
            "target_entity_type IS NULL OR target_entity_type IN "
            "('opportunity', 'contact', 'stakeholder', 'interaction', 'task', 'internal_user')",
            name="ck_action_versions_target_type",
        ),
        CheckConstraint(
            "(target_entity_type IS NULL AND target_entity_id IS NULL) OR target_entity_type IS NOT NULL",
            name="ck_action_versions_target_pair",
        ),
        CheckConstraint(
            "length(trim(provenance_summary)) BETWEEN 1 AND 2000",
            name="ck_action_versions_provenance",
        ),
        CheckConstraint("length(content_fingerprint) = 64", name="ck_action_versions_fingerprint"),
        ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_versions_action_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_action_versions_creator_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_action_versions_org_id"),
        UniqueConstraint("organisation_id", "action_id", "version", name="uq_action_versions_action_version"),
        Index(
            "ix_action_versions_org_action",
            "organisation_id",
            "action_id",
            "version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    proposed_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_entity_type: Mapped[str | None] = mapped_column(String(24))
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    source_refs_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    provenance_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ActionAuditEvent(Base):
    __tablename__ = "action_audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('proposed', 'edited', 'approved', 'rejected', 'superseded', 'completed_manually')",
            name="ck_action_audit_events_type",
        ),
        CheckConstraint("proposal_version > 0", name="ck_action_audit_events_version"),
        ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_audit_events_action_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_action_audit_events_actor_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_action_audit_events_org_id"),
        Index(
            "ix_action_audit_events_org_action_created",
            "organisation_id",
            "action_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IntegrationConnection(TimestampMixin, Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot')",
            name="ck_integration_connections_key",
        ),
        CheckConstraint(
            "connection_status IN ('active', 'reauthorisation_required', 'revoked')",
            name="ck_integration_connections_status",
        ),
        CheckConstraint("metadata_version > 0", name="ck_integration_connections_version"),
        CheckConstraint(
            "(connection_status IN ('active', 'reauthorisation_required') AND revoked_at IS NULL) OR "
            "(connection_status = 'revoked' AND revoked_at IS NOT NULL)",
            name="ck_integration_connections_revoked",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_integration_connections_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_integration_connections_org_id"),
        UniqueConstraint(
            "organisation_id",
            "connector_key",
            name="uq_integration_connections_org_key",
        ),
        Index(
            "ix_integration_connections_org_status",
            "organisation_id",
            "connection_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False, default=ConnectorKey.MOCK_EMAIL.value)
    connection_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConnectionStatus.ACTIVE.value, server_default="active"
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_reference: Mapped[str | None] = mapped_column(String(255))
    capability_state_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    external_account_id: Mapped[str | None] = mapped_column(String(128))
    external_account_name: Mapped[str | None] = mapped_column(String(200))
    granted_scopes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    metadata_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OAuthConnectionState(Base):
    __tablename__ = "oauth_connection_states"
    __table_args__ = (
        CheckConstraint("connector_key = 'hubspot'", name="ck_oauth_connection_states_connector"),
        CheckConstraint("length(state_hash) = 64", name="ck_oauth_connection_states_hash"),
        CheckConstraint("length(trim(redirect_uri)) > 0", name="ck_oauth_connection_states_redirect"),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_oauth_connection_states_membership",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_oauth_connection_states_org_id"),
        UniqueConstraint("state_hash", name="uq_oauth_connection_states_hash"),
        Index("ix_oauth_connection_states_org_expiry", "organisation_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False, default="hubspot")
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EncryptedConnectorCredential(TimestampMixin, Base):
    __tablename__ = "encrypted_connector_credentials"
    __table_args__ = (
        CheckConstraint("connector_key = 'hubspot'", name="ck_encrypted_connector_credentials_connector"),
        CheckConstraint("length(nonce) = 12", name="ck_encrypted_connector_credentials_nonce"),
        CheckConstraint("key_version > 0", name="ck_encrypted_connector_credentials_key_version"),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_encrypted_connector_credentials_connection",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_encrypted_connector_credentials_org_id"),
        UniqueConstraint("organisation_id", "connection_id", name="uq_encrypted_connector_credentials_connection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False, default="hubspot")
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class CRMEntityMapping(TimestampMixin, Base):
    __tablename__ = "crm_entity_mappings"
    __table_args__ = (
        CheckConstraint(
            "revenueos_entity_type IN ('company', 'contact', 'opportunity')",
            name="ck_crm_entity_mappings_entity_type",
        ),
        CheckConstraint(
            "external_object_type IN ('company', 'contact', 'deal')",
            name="ck_crm_entity_mappings_object_type",
        ),
        CheckConstraint("sync_state IN ('active', 'external_missing')", name="ck_crm_entity_mappings_state"),
        CheckConstraint(
            "length(trim(external_object_id)) BETWEEN 1 AND 128", name="ck_crm_entity_mappings_external_id"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_entity_mappings_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_entity_mappings_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_entity_mappings_org_id"),
        UniqueConstraint(
            "organisation_id",
            "connection_id",
            "revenueos_entity_type",
            "revenueos_entity_id",
            name="uq_crm_entity_mappings_revenueos_entity",
        ),
        UniqueConstraint(
            "organisation_id",
            "connection_id",
            "external_object_type",
            "external_object_id",
            name="uq_crm_entity_mappings_external_object",
        ),
        Index("ix_crm_entity_mappings_org_entity", "organisation_id", "revenueos_entity_type", "revenueos_entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revenueos_entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    revenueos_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    external_object_type: Mapped[str] = mapped_column(String(24), nullable=False)
    external_object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_state: Mapped[str] = mapped_column(String(24), nullable=False, default="active", server_default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class CRMFieldMapping(TimestampMixin, Base):
    __tablename__ = "crm_field_mappings"
    __table_args__ = (
        CheckConstraint("entity_type IN ('opportunity', 'contact')", name="ck_crm_field_mappings_entity_type"),
        CheckConstraint(
            "external_property_type IN ('string', 'number', 'date', 'datetime', 'enumeration')",
            name="ck_crm_field_mappings_property_type",
        ),
        CheckConstraint(
            "authority IN ('crm_authoritative', 'revenueos_authoritative', 'review_before_sync')",
            name="ck_crm_field_mappings_authority",
        ),
        CheckConstraint("length(trim(revenueos_field)) BETWEEN 1 AND 64", name="ck_crm_field_mappings_field"),
        CheckConstraint(
            "length(trim(external_property_name)) BETWEEN 1 AND 128", name="ck_crm_field_mappings_property"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_field_mappings_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_field_mappings_configurer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_field_mappings_org_id"),
        UniqueConstraint(
            "organisation_id",
            "connection_id",
            "entity_type",
            "revenueos_field",
            name="uq_crm_field_mappings_field",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    revenueos_field: Mapped[str] = mapped_column(String(64), nullable=False)
    external_property_name: Mapped[str] = mapped_column(String(128), nullable=False)
    external_property_type: Mapped[str] = mapped_column(String(24), nullable=False)
    authority: Mapped[str] = mapped_column(String(32), nullable=False, default="review_before_sync")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    configured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class CRMStageMapping(TimestampMixin, Base):
    __tablename__ = "crm_stage_mappings"
    __table_args__ = (
        CheckConstraint(
            "revenueos_stage IN ('qualification', 'discovery', 'evaluation', 'proposal', 'negotiation', "
            "'procurement', 'closed_won', 'closed_lost', 'other')",
            name="ck_crm_stage_mappings_stage",
        ),
        CheckConstraint("length(trim(external_pipeline_id)) BETWEEN 1 AND 128", name="ck_crm_stage_mappings_pipeline"),
        CheckConstraint(
            "length(trim(external_stage_id)) BETWEEN 1 AND 128", name="ck_crm_stage_mappings_external_stage"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_stage_mappings_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_stage_mappings_configurer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_stage_mappings_org_id"),
        UniqueConstraint("organisation_id", "connection_id", "revenueos_stage", name="uq_crm_stage_mappings_stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revenueos_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    external_pipeline_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_stage_id: Mapped[str] = mapped_column(String(128), nullable=False)
    configured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class ExecutionPreview(Base):
    __tablename__ = "execution_previews"
    __table_args__ = (
        CheckConstraint(
            "capability IN ('send_email', 'create_calendar_event', 'update_opportunity', "
            "'update_contact', 'create_activity', 'create_task')",
            name="ck_execution_previews_capability",
        ),
        CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_execution_previews_risk",
        ),
        CheckConstraint("length(preview_fingerprint) = 64", name="ck_execution_previews_fingerprint"),
        ForeignKeyConstraint(
            ["organisation_id", "action_id", "action_version"],
            [
                "action_proposal_versions.organisation_id",
                "action_proposal_versions.action_id",
                "action_proposal_versions.version",
            ],
            name="fk_execution_previews_action_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_execution_previews_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "confirmed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_execution_previews_confirmer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_execution_previews_org_id"),
        Index("ix_execution_previews_org_action", "organisation_id", "action_id", "created_at"),
        Index("ix_execution_previews_org_connection", "organisation_id", "connection_id"),
        Index("ix_execution_previews_org_expiry", "organisation_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_version: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(32), nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ActionExecution(TimestampMixin, Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot')",
            name="ck_action_executions_connector",
        ),
        CheckConstraint(
            "capability IN ('send_email', 'create_calendar_event', 'update_opportunity', "
            "'update_contact', 'create_activity', 'create_task')",
            name="ck_action_executions_capability",
        ),
        CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_action_executions_risk",
        ),
        CheckConstraint(
            "execution_status IN ('queued', 'executing', 'simulated_success', 'succeeded', "
            "'failed_retryable', 'failed_permanent', 'cancelled', 'unknown_external_state')",
            name="ck_action_executions_status",
        ),
        CheckConstraint("execution_mode IN ('simulation', 'live')", name="ck_action_executions_mode"),
        CheckConstraint("length(idempotency_key) = 64", name="ck_action_executions_idempotency"),
        CheckConstraint("length(preview_fingerprint) = 64", name="ck_action_executions_preview"),
        CheckConstraint("attempt_count >= 0", name="ck_action_executions_attempts"),
        CheckConstraint("max_attempts BETWEEN 1 AND 20", name="ck_action_executions_max_attempts"),
        ForeignKeyConstraint(
            ["organisation_id", "action_id", "action_version"],
            [
                "action_proposal_versions.organisation_id",
                "action_proposal_versions.action_id",
                "action_proposal_versions.version",
            ],
            name="fk_action_executions_action_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_action_executions_connection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "preview_id"],
            ["execution_previews.organisation_id", "execution_previews.id"],
            name="fk_action_executions_preview",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "confirmed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_executions_confirmer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_action_executions_org_id"),
        UniqueConstraint("organisation_id", "preview_id", name="uq_action_executions_preview"),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_action_executions_idempotency"),
        UniqueConstraint(
            "organisation_id",
            "action_id",
            "action_version",
            "connection_id",
            "capability",
            name="uq_action_executions_action_connection",
        ),
        Index(
            "ix_action_executions_org_status_next",
            "organisation_id",
            "execution_status",
            "next_attempt_at",
        ),
        Index(
            "ix_action_executions_org_connection_status",
            "organisation_id",
            "connection_id",
            "execution_status",
        ),
        Index("ix_action_executions_org_action", "organisation_id", "action_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_version: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    preview_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ExecutionStatus.QUEUED.value, server_default="queued"
    )
    execution_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="simulation", server_default="simulation"
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_failure_code: Mapped[str | None] = mapped_column(String(80))
    external_result_id: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    worker_id: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionExecutionAttempt(Base):
    __tablename__ = "action_execution_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_action_execution_attempts_number"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_action_execution_attempts_duration"),
        ForeignKeyConstraint(
            ["organisation_id", "execution_id"],
            ["action_executions.organisation_id", "action_executions.id"],
            name="fk_action_execution_attempts_execution",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_action_execution_attempts_org_id"),
        UniqueConstraint(
            "organisation_id",
            "execution_id",
            "attempt_number",
            name="uq_action_execution_attempts_number",
        ),
        Index(
            "ix_action_execution_attempts_org_execution",
            "organisation_id",
            "execution_id",
            "attempt_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_failure_code: Mapped[str | None] = mapped_column(String(80))
    external_result_id: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class IntegrationAuditEvent(Base):
    __tablename__ = "integration_audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('connection_created', 'connection_tested', 'connection_revoked', "
            "'connection_reauthorisation_required', 'mapping_created', 'mapping_changed', 'mapping_removed', "
            "'field_mapping_changed', 'stage_mapping_changed', "
            "'execution_preview_created', 'execution_confirmed', 'execution_started', "
            "'execution_succeeded', 'execution_failed', 'execution_unknown_state', 'execution_reconciled')",
            name="ck_integration_audit_events_type",
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_integration_audit_events_duration"),
        ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_integration_audit_events_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_integration_audit_events_org_id"),
        Index(
            "ix_integration_audit_events_org_subject",
            "organisation_id",
            "subject_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(24), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False)
    capability: Mapped[str | None] = mapped_column(String(40))
    risk_class: Mapped[str | None] = mapped_column(String(32))
    attempt_count: Mapped[int | None] = mapped_column(Integer)
    safe_failure_code: Mapped[str | None] = mapped_column(String(80))
    external_result_id: Mapped[str | None] = mapped_column(String(255))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MockConnectorObject(TimestampMixin, Base):
    __tablename__ = "mock_connector_objects"
    __table_args__ = (
        CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task')",
            name="ck_mock_connector_objects_key",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_mock_connector_objects_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "last_execution_id"],
            ["action_executions.organisation_id", "action_executions.id"],
            name="fk_mock_connector_objects_execution",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_mock_connector_objects_org_id"),
        UniqueConstraint(
            "organisation_id",
            "connection_id",
            "object_key",
            name="uq_mock_connector_objects_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_execution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(40), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    last_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    external_result_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=dict)


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
            "call_direction IS NULL OR call_direction IN ('inbound', 'outbound', 'unknown')",
            name="ck_interactions_call_direction",
        ),
        CheckConstraint(
            "call_outcome IS NULL OR call_outcome IN ('connected', 'no_answer', 'voicemail', 'cancelled')",
            name="ck_interactions_call_outcome",
        ),
        CheckConstraint(
            "(interaction_type = 'phone_call' AND call_direction IS NOT NULL) OR "
            "(interaction_type <> 'phone_call' AND contact_id IS NULL AND "
            "call_direction IS NULL AND call_outcome IS NULL)",
            name="ck_interactions_phone_metadata_scope",
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
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_interactions_contact_tenant",
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
        Index("ix_interactions_organisation_contact", "organisation_id", "contact_id"),
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
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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
    call_direction: Mapped[str | None] = mapped_column(String(20))
    call_outcome: Mapped[str | None] = mapped_column(String(20))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OnlineMeetingMetadata(TimestampMixin, Base):
    __tablename__ = "online_meeting_metadata"
    __table_args__ = (
        CheckConstraint(
            "meeting_platform IN ('microsoft_teams', 'zoom', 'google_meet', 'other')",
            name="ck_online_meeting_metadata_platform",
        ),
        CheckConstraint(
            "capture_source IS NULL OR capture_source IN ("
            "'platform_recording', 'platform_transcript', 'user_uploaded_recording', "
            "'user_uploaded_transcript', 'native_integration', 'meeting_bot', "
            "'ai_debrief', 'voice_journal', 'manual_notes')",
            name="ck_online_meeting_metadata_capture_source",
        ),
        CheckConstraint(
            "ingestion_state IN ('not_started', 'uploading', 'processing', 'ready', 'failed')",
            name="ck_online_meeting_metadata_ingestion_state",
        ),
        CheckConstraint(
            "safe_meeting_url IS NULL OR length(trim(safe_meeting_url)) BETWEEN 1 AND 1000",
            name="ck_online_meeting_metadata_safe_url",
        ),
        CheckConstraint(
            "meeting_host IS NULL OR length(trim(meeting_host)) BETWEEN 1 AND 255",
            name="ck_online_meeting_metadata_host",
        ),
        CheckConstraint(
            "external_meeting_id IS NULL OR length(trim(external_meeting_id)) BETWEEN 1 AND 255",
            name="ck_online_meeting_metadata_external_id",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_online_meeting_metadata_interaction_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_online_meeting_metadata_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            name="uq_online_meeting_metadata_interaction",
        ),
        Index(
            "ix_online_meeting_metadata_organisation_platform",
            "organisation_id",
            "meeting_platform",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    meeting_platform: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=OnlineMeetingPlatform.OTHER.value,
        server_default=OnlineMeetingPlatform.OTHER.value,
    )
    safe_meeting_url: Mapped[str | None] = mapped_column(String(1000))
    meeting_host: Mapped[str | None] = mapped_column(String(255))
    external_meeting_id: Mapped[str | None] = mapped_column(String(255))
    capture_source: Mapped[str | None] = mapped_column(String(40))
    ingestion_state: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=OnlineMeetingIngestionState.NOT_STARTED.value,
        server_default=OnlineMeetingIngestionState.NOT_STARTED.value,
    )


class InteractionMarker(Base):
    __tablename__ = "interaction_markers"
    __table_args__ = (
        CheckConstraint(
            "marker_type IN ('buying_signal', 'objection', 'decision', 'action_item', "
            "'risk', 'stakeholder', 'timeline', 'budget', 'procurement', 'follow_up', "
            "'important_moment', 'customer_question', 'requested_material', 'strong_engagement')",
            name="ck_interaction_markers_type",
        ),
        CheckConstraint(
            "recording_offset_ms IS NULL OR recording_offset_ms BETWEEN 0 AND 14400000",
            name="ck_interaction_markers_offset",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_interaction_markers_idempotency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_markers_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_interaction_markers_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_interaction_markers_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_interaction_markers_idempotency",
        ),
        Index(
            "ix_interaction_markers_organisation_interaction_created",
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
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    marker_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recording_offset_ms: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
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
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio', "
            "'platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')",
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


class TranscriptVersion(Base):
    __tablename__ = "transcript_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_transcript_versions_version"),
        CheckConstraint("length(trim(raw_text)) > 0", name="ck_transcript_versions_raw_text"),
        CheckConstraint(
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio', "
            "'platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted', 'progressive')",
            name="ck_transcript_versions_source",
        ),
        CheckConstraint("status IN ('provisional', 'final', 'deleted')", name="ck_transcript_versions_status"),
        CheckConstraint(
            "transcript_id IS NOT NULL OR recording_session_id IS NOT NULL",
            name="ck_transcript_versions_trace",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_transcript_versions_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_transcript_versions_meeting_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            ["transcripts.organisation_id", "transcripts.id", "transcripts.meeting_id"],
            name="fk_transcript_versions_transcript_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_transcript_versions_recording_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_transcript_versions_evidence_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_transcript_versions_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "transcript_id",
            "version",
            name="uq_transcript_versions_logical_version",
        ),
        UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            name="uq_transcript_versions_recording",
        ),
        Index(
            "ix_transcript_versions_organisation_interaction_created",
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
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    transcript_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    recording_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="final", server_default="final")
    provider_name: Mapped[str | None] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        CheckConstraint("sequence_number >= 0", name="ck_transcript_segments_sequence"),
        CheckConstraint("start_ms >= 0 AND end_ms >= start_ms", name="ck_transcript_segments_time_range"),
        CheckConstraint(
            "length(trim(text)) BETWEEN 1 AND 12000",
            name="ck_transcript_segments_text",
        ),
        CheckConstraint(
            "speaker_label IS NULL OR length(trim(speaker_label)) BETWEEN 1 AND 80",
            name="ck_transcript_segments_speaker_label",
        ),
        CheckConstraint(
            "speaker_role IS NULL OR speaker_role IN ('customer', 'salesperson', 'unknown')",
            name="ck_transcript_segments_speaker_role",
        ),
        CheckConstraint(
            "source_confidence IS NULL OR (source_confidence >= 0 AND source_confidence <= 1)",
            name="ck_transcript_segments_confidence",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_transcript_segments_version_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_transcript_segments_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "transcript_version_id",
            "sequence_number",
            name="uq_transcript_segments_sequence",
        ),
        Index(
            "ix_transcript_segments_organisation_version_sequence",
            "organisation_id",
            "transcript_version_id",
            "sequence_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    transcript_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(80))
    speaker_role: Mapped[str | None] = mapped_column(
        String(20),
        default=TranscriptSpeakerRole.UNKNOWN.value,
        server_default=TranscriptSpeakerRole.UNKNOWN.value,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LiveInteractionSession(TimestampMixin, Base):
    __tablename__ = "live_interaction_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'processing', 'stopped', 'completed', 'failed', 'expired')",
            name="ck_live_interaction_sessions_status",
        ),
        CheckConstraint(
            "source_kind = 'progressive_transcript'",
            name="ck_live_interaction_sessions_source",
        ),
        CheckConstraint("last_processed_sequence >= -1", name="ck_live_interaction_sessions_cursor"),
        CheckConstraint("processed_character_count >= 0", name="ck_live_interaction_sessions_characters"),
        CheckConstraint("processing_request_count >= 0", name="ck_live_interaction_sessions_requests"),
        CheckConstraint(
            "failure_code IS NULL OR length(trim(failure_code)) BETWEEN 1 AND 100",
            name="ck_live_interaction_sessions_failure_code",
        ),
        CheckConstraint(
            "stopped_at IS NULL OR stopped_at >= started_at",
            name="ck_live_interaction_sessions_time_range",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_live_interaction_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_live_interaction_sessions_transcript_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "brief_id"],
            ["pre_interaction_briefs.organisation_id", "pre_interaction_briefs.id"],
            name="fk_live_interaction_sessions_brief_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_live_interaction_sessions_creator_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "final_intelligence_id"],
            ["interaction_intelligence_snapshots.organisation_id", "interaction_intelligence_snapshots.id"],
            name="fk_live_interaction_sessions_final_intelligence_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_live_interaction_sessions_org_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            name="uq_live_interaction_sessions_interaction",
        ),
        Index(
            "ix_live_sessions_org_status_updated",
            "organisation_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_live_sessions_org_retention",
            "organisation_id",
            "retention_expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    final_intelligence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=LiveInteractionStatus.ACTIVE.value,
        server_default=LiveInteractionStatus.ACTIVE.value,
    )
    source_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="progressive_transcript", server_default="progressive_transcript"
    )
    last_processed_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=-1, server_default="-1")
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_window_fingerprint: Mapped[str | None] = mapped_column(String(64))
    processed_character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processing_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LiveProcessingWindow(Base):
    __tablename__ = "live_processing_windows"
    __table_args__ = (
        CheckConstraint("first_sequence >= 0", name="ck_live_processing_windows_first_sequence"),
        CheckConstraint("last_sequence >= first_sequence", name="ck_live_processing_windows_last_sequence"),
        CheckConstraint("segment_count BETWEEN 1 AND 50", name="ck_live_processing_windows_segment_count"),
        CheckConstraint(
            "character_count BETWEEN 1 AND 50000",
            name="ck_live_processing_windows_character_count",
        ),
        CheckConstraint(
            "status IN ('processing', 'completed', 'no_signal', 'failed')",
            name="ck_live_processing_windows_status",
        ),
        CheckConstraint("length(window_fingerprint) = 64", name="ck_live_processing_windows_fingerprint"),
        CheckConstraint("signal_count >= 0", name="ck_live_processing_windows_signals"),
        ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_live_processing_windows_session_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_live_processing_windows_org_id"),
        UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "window_fingerprint",
            name="uq_live_processing_windows_fingerprint",
        ),
        UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "trigger_idempotency_key",
            name="uq_live_processing_windows_trigger",
        ),
        Index(
            "ix_live_windows_org_created",
            "organisation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    live_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    trigger_idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    window_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    first_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing", server_default="processing")
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProvisionalSignal(TimestampMixin, Base):
    __tablename__ = "provisional_signals"
    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('buying_signal', 'objection', 'stakeholder', 'decision', 'action_item', "
            "'risk', 'timeline', 'procurement', 'security_legal', 'customer_request', 'commercial_intent', "
            "'objective_progress', 'open_question_progress', 'other')",
            name="ck_provisional_signals_type",
        ),
        CheckConstraint(
            "lifecycle_status IN ('detected', 'updated', 'superseded', 'dismissed', 'promoted_candidate', 'expired')",
            name="ck_provisional_signals_lifecycle",
        ),
        CheckConstraint("is_provisional = true", name="ck_provisional_signals_provisional"),
        CheckConstraint("priority IN ('high', 'normal')", name="ck_provisional_signals_priority"),
        CheckConstraint(
            "evidence_strength IN ('customer_attributed', 'speaker_uncertain', 'context_only')",
            name="ck_provisional_signals_strength",
        ),
        CheckConstraint(
            "resolution_status IN ('pending', 'confirmed', 'revised', 'unsupported', 'unresolved')",
            name="ck_provisional_signals_resolution",
        ),
        CheckConstraint("length(trim(statement)) BETWEEN 1 AND 500", name="ck_provisional_signals_statement"),
        CheckConstraint("source_sequence_start >= 0", name="ck_provisional_signals_source_start"),
        CheckConstraint(
            "source_sequence_end >= source_sequence_start",
            name="ck_provisional_signals_source_end",
        ),
        CheckConstraint("length(signal_fingerprint) = 64", name="ck_provisional_signals_fingerprint"),
        CheckConstraint("length(subject_fingerprint) = 64", name="ck_provisional_signals_subject"),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_provisional_signals_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_provisional_signals_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_provisional_signals_transcript_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "superseded_by_id"],
            ["provisional_signals.organisation_id", "provisional_signals.id"],
            name="fk_provisional_signals_superseded_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_provisional_signals_org_id"),
        UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "signal_fingerprint",
            name="uq_provisional_signals_fingerprint",
        ),
        Index(
            "ix_provisional_signals_org_interaction_status",
            "organisation_id",
            "interaction_id",
            "lifecycle_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    live_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(String(500), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=ProvisionalSignalLifecycle.DETECTED.value,
        server_default=ProvisionalSignalLifecycle.DETECTED.value,
    )
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    priority: Mapped[str] = mapped_column(String(12), nullable=False, default="normal", server_default="normal")
    evidence_strength: Mapped[str] = mapped_column(String(24), nullable=False)
    resolution_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=LiveSignalResolution.PENDING.value,
        server_default=LiveSignalResolution.PENDING.value,
    )
    signal_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sequence_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sequence_end: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LiveBriefProgress(TimestampMixin, Base):
    __tablename__ = "live_brief_progress"
    __table_args__ = (
        CheckConstraint("item_type IN ('objective', 'open_question')", name="ck_live_brief_progress_type"),
        CheckConstraint("item_index BETWEEN 0 AND 20", name="ck_live_brief_progress_index"),
        CheckConstraint("length(item_fingerprint) = 64", name="ck_live_brief_progress_fingerprint"),
        CheckConstraint(
            "progress_status IN ('unresolved', 'possibly_addressed', 'possibly_answered')",
            name="ck_live_brief_progress_status",
        ),
        CheckConstraint(
            "source_sequence_end IS NULL OR source_sequence_end >= 0",
            name="ck_live_brief_progress_source",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_live_brief_progress_session_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_live_brief_progress_org_id"),
        UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "item_type",
            "item_index",
            name="uq_live_brief_progress_item",
        ),
        Index("ix_live_brief_progress_org_session", "organisation_id", "live_session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    live_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    progress_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unresolved")
    source_sequence_end: Mapped[int | None] = mapped_column(Integer)


class OnlineMeetingTranscriptImport(Base):
    __tablename__ = "online_meeting_transcript_imports"
    __table_args__ = (
        CheckConstraint(
            "provenance IN ('platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')",
            name="ck_online_meeting_transcript_imports_provenance",
        ),
        CheckConstraint(
            "source_format IN ('txt', 'vtt', 'srt')",
            name="ck_online_meeting_transcript_imports_format",
        ),
        CheckConstraint(
            "character_count BETWEEN 1 AND 1000000",
            name="ck_online_meeting_transcript_imports_character_count",
        ),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_online_meeting_transcript_imports_checksum",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_online_meeting_transcript_imports_idempotency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_online_meeting_transcript_imports_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_online_meeting_transcript_imports_capture_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_online_meeting_transcript_imports_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_online_meeting_transcript_imports_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "imported_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_online_meeting_transcript_imports_user_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_online_meeting_transcript_imports_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "imported_by_user_id",
            "idempotency_key",
            name="uq_online_meeting_transcript_imports_idempotency",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "content_sha256",
            name="uq_online_meeting_transcript_imports_content",
        ),
        UniqueConstraint(
            "organisation_id",
            "transcript_version_id",
            name="uq_online_meeting_transcript_imports_version",
        ),
        Index(
            "ix_online_meeting_transcript_imports_org_interaction_at",
            "organisation_id",
            "interaction_id",
            "imported_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capture_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    imported_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provenance: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=TranscriptProvenance.USER_UPLOADED.value,
        server_default=TranscriptProvenance.USER_UPLOADED.value,
    )
    source_format: Mapped[str] = mapped_column(String(8), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamps_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    speaker_labels_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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
            "'ai_debrief', 'voice_journal', 'live_recording', 'live_audio_recording', "
            "'visual_capture', 'uploaded_transcript', 'uploaded_recording', "
            "'uploaded_audio_recording', 'imported_audio_recording', 'document_import', "
            "'email_import', 'manual_notes'"
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
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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
            "support_class IN ('direct', 'reported', 'context', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded', 'observed')",
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
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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


class RecordingSession(TimestampMixin, Base):
    __tablename__ = "recording_sessions"
    __table_args__ = (
        CheckConstraint(
            "recording_type IN ('live_audio_recording', 'uploaded_audio_recording', 'imported_audio_recording')",
            name="ck_recording_sessions_type",
        ),
        CheckConstraint(
            "recording_source IS NULL OR recording_source IN ("
            "'customer_call_recording', 'business_phone_recording', 'user_uploaded_recording', "
            "'external_provider_recording', 'platform_recording')",
            name="ck_recording_sessions_source",
        ),
        CheckConstraint(
            "(recording_type = 'live_audio_recording' AND recording_source IS NULL) OR "
            "(recording_type <> 'live_audio_recording' AND recording_source IS NOT NULL)",
            name="ck_recording_sessions_import_source",
        ),
        CheckConstraint(
            "lifecycle_status IN ('created', 'recording', 'uploading', 'uploaded', 'transcribing', "
            "'completed', 'failed', 'cancelled', 'deleting', 'deleted')",
            name="ck_recording_sessions_lifecycle",
        ),
        CheckConstraint("consent_state = 'acknowledged'", name="ck_recording_sessions_consent"),
        CheckConstraint(
            "expected_mime_type IN ('audio/webm', 'audio/mp4', 'audio/m4a')",
            name="ck_recording_sessions_expected_mime",
        ),
        CheckConstraint(
            "final_mime_type IS NULL OR final_mime_type IN ('audio/webm', 'audio/mp4', 'audio/m4a')",
            name="ck_recording_sessions_final_mime",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds BETWEEN 1 AND 14400",
            name="ck_recording_sessions_duration",
        ),
        CheckConstraint("total_bytes >= 0", name="ck_recording_sessions_total_bytes"),
        CheckConstraint("chunk_count >= 0", name="ck_recording_sessions_chunk_count"),
        CheckConstraint(
            "transcription_attempts BETWEEN 0 AND 5",
            name="ck_recording_sessions_transcription_attempts",
        ),
        CheckConstraint(
            "stopped_at IS NULL OR started_at IS NULL OR stopped_at >= started_at",
            name="ck_recording_sessions_time_range",
        ),
        CheckConstraint(
            "auto_intelligence_status IN ('disabled', 'not_requested', 'requested', 'failed')",
            name="ck_recording_sessions_auto_intelligence",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_recording_sessions_idempotency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_recording_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_recording_sessions_capture_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_recording_sessions_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_recording_sessions_transcript_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_recording_sessions_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_recording_sessions_transcript_version_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_recording_sessions_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "capture_session_id",
            name="uq_recording_sessions_capture_session",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_recording_sessions_idempotency",
        ),
        Index(
            "ix_recording_sessions_organisation_interaction_created",
            "organisation_id",
            "interaction_id",
            "created_at",
        ),
        Index(
            "ix_recording_sessions_organisation_lifecycle",
            "organisation_id",
            "lifecycle_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capture_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transcript_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recording_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recording_source: Mapped[str | None] = mapped_column(String(40))
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created", server_default="created"
    )
    consent_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="acknowledged", server_default="acknowledged"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    expected_mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    final_mime_type: Mapped[str | None] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(16))
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcription_provider_key: Mapped[str | None] = mapped_column(String(40))
    transcription_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    transcription_request_id: Mapped[str | None] = mapped_column(String(255))
    transcription_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcription_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcript_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    session_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_intelligence_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disabled", server_default="disabled"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecordingConsent(Base):
    __tablename__ = "recording_consents"
    __table_args__ = (
        CheckConstraint("notice_version > 0", name="ck_recording_consents_notice_version"),
        CheckConstraint(
            "consent_method IN ('participant_notice_confirmed', 'platform_notice', 'contractual_authority')",
            name="ck_recording_consents_method",
        ),
        CheckConstraint("user_attested_authority", name="ck_recording_consents_authority"),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_recording_consents_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_recording_consents_recording_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_recording_consents_user_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_recording_consents_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            name="uq_recording_consents_recording",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recording_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    notice_version: Mapped[int] = mapped_column(Integer, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    consent_method: Mapped[str] = mapped_column(String(40), nullable=False)
    user_attested_authority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class RecordingChunk(Base):
    __tablename__ = "recording_chunks"
    __table_args__ = (
        CheckConstraint("sequence_number >= 0", name="ck_recording_chunks_sequence"),
        CheckConstraint("byte_size BETWEEN 1 AND 25000000", name="ck_recording_chunks_byte_size"),
        CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_recording_chunks_checksum",
        ),
        CheckConstraint(
            "upload_state IN ('pending', 'uploaded', 'verified', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_recording_chunks_upload_state",
        ),
        CheckConstraint(
            "length(trim(upload_idempotency_key)) BETWEEN 1 AND 200",
            name="ck_recording_chunks_upload_idempotency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_recording_chunks_recording_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_recording_chunks_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            "sequence_number",
            name="uq_recording_chunks_sequence",
        ),
        UniqueConstraint("storage_key", name="uq_recording_chunks_storage_key"),
        Index(
            "ix_recording_chunks_organisation_recording_sequence",
            "organisation_id",
            "recording_session_id",
            "sequence_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recording_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(360), nullable=False)
    upload_state: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    upload_idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    completion_idempotency_key: Mapped[str | None] = mapped_column(String(200))
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VisualAsset(TimestampMixin, Base):
    __tablename__ = "visual_assets"
    __table_args__ = (
        CheckConstraint(
            "visual_type IN ('whiteboard', 'workshop_output', 'architecture_diagram', "
            "'handwritten_notes', 'agenda', 'business_card', 'presentation_slide', "
            "'presentation_deck_page', 'customer_document_photo', 'site_photo', "
            "'product_photo', 'screenshot', 'other')",
            name="ck_visual_assets_type",
        ),
        CheckConstraint(
            "source_ownership IN ('customer_created', 'salesperson_created', 'jointly_created', 'unknown_origin')",
            name="ck_visual_assets_source_ownership",
        ),
        CheckConstraint("mime_type IN ('image/jpeg', 'image/png')", name="ck_visual_assets_mime_type"),
        CheckConstraint("byte_size BETWEEN 1 AND 25000000", name="ck_visual_assets_byte_size"),
        CheckConstraint("upload_byte_size BETWEEN 1 AND 25000000", name="ck_visual_assets_upload_byte_size"),
        CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width BETWEEN 1 AND 30000 AND height BETWEEN 1 AND 30000)",
            name="ck_visual_assets_dimensions",
        ),
        CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_visual_assets_checksum",
        ),
        CheckConstraint(
            "length(upload_checksum_sha256) = 64 AND upload_checksum_sha256 = lower(upload_checksum_sha256)",
            name="ck_visual_assets_upload_checksum",
        ),
        CheckConstraint(
            "processing_status IN ('uploading', 'uploaded', 'processing', 'review', "
            "'completed', 'failed', 'cancelled', 'deletion_pending', 'deleted')",
            name="ck_visual_assets_processing_status",
        ),
        CheckConstraint(
            "storage_status IN ('pending', 'available', 'missing', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_visual_assets_storage_status",
        ),
        CheckConstraint(
            "processing_attempts BETWEEN 0 AND 5",
            name="ck_visual_assets_processing_attempts",
        ),
        CheckConstraint(
            "length(trim(upload_idempotency_key)) BETWEEN 1 AND 200",
            name="ck_visual_assets_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_visual_assets_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_visual_assets_capture_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_visual_assets_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "captured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_visual_assets_captured_by_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_visual_assets_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "capture_session_id",
            name="uq_visual_assets_capture_session",
        ),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "captured_by_user_id",
            "upload_idempotency_key",
            name="uq_visual_assets_upload_idempotency",
        ),
        UniqueConstraint("storage_key", name="uq_visual_assets_storage_key"),
        Index(
            "ix_visual_assets_organisation_interaction_created",
            "organisation_id",
            "interaction_id",
            "created_at",
        ),
        Index(
            "ix_visual_assets_organisation_processing",
            "organisation_id",
            "processing_status",
        ),
        Index(
            "ix_visual_assets_organisation_storage",
            "organisation_id",
            "storage_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capture_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    captured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    visual_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ownership: Mapped[str] = mapped_column(String(30), nullable=False)
    context_label: Mapped[str | None] = mapped_column(String(200))
    display_filename: Mapped[str] = mapped_column(String(160), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(30), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    upload_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upload_idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    completion_idempotency_key: Mapped[str | None] = mapped_column(String(200))
    processing_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="uploading", server_default="uploading"
    )
    storage_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider_name: Mapped[str | None] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VisualCandidateEvidence(TimestampMixin, Base):
    __tablename__ = "visual_candidate_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_category IN ('stakeholder', 'customer_request', 'decision', 'action_item', "
            "'risk', 'technical_constraint', 'implementation_requirement', 'timeline', "
            "'procurement', 'security_legal', 'budget', 'objection', 'commercial_intent', "
            "'contact_detail', 'other')",
            name="ck_visual_candidate_category",
        ),
        CheckConstraint("origin_class = 'ai_inferred'", name="ck_visual_candidate_origin"),
        CheckConstraint(
            "source_ownership IN ('customer_created', 'salesperson_created', 'jointly_created', 'unknown_origin')",
            name="ck_visual_candidate_source_ownership",
        ),
        CheckConstraint(
            "support_classification IN ('direct', 'observed', 'context')",
            name="ck_visual_candidate_support",
        ),
        CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')",
            name="ck_visual_candidate_validation",
        ),
        CheckConstraint(
            "review_state IN ('pending', 'accepted', 'rejected')",
            name="ck_visual_candidate_review",
        ),
        CheckConstraint(
            "conflict_state IN ('not_assessed', 'conflicting')",
            name="ck_visual_candidate_conflict",
        ),
        CheckConstraint(
            "confidence_class IS NULL OR confidence_class IN ('low', 'medium', 'high')",
            name="ck_visual_candidate_confidence",
        ),
        CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_visual_candidate_statements",
        ),
        CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_visual_candidate_review_consistency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_visual_candidate_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_visual_id"],
            ["visual_assets.organisation_id", "visual_assets.id"],
            name="fk_visual_candidate_visual_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_visual_candidate_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_visual_candidate_reviewer_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_visual_candidate_organisation_id_id",
        ),
        UniqueConstraint(
            "organisation_id",
            "source_visual_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_visual_candidate_statement",
        ),
        Index(
            "ix_visual_candidate_organisation_visual_review",
            "organisation_id",
            "source_visual_id",
            "review_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_visual_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accepted_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_category: Mapped[str] = mapped_column(String(40), nullable=False)
    statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    statement_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ownership: Mapped[str] = mapped_column(String(30), nullable=False)
    origin_class: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ai_inferred", server_default="ai_inferred"
    )
    support_classification: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unreviewed", server_default="unreviewed"
    )
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    conflict_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_assessed", server_default="not_assessed"
    )
    confidence_class: Mapped[str | None] = mapped_column(String(10))
    evidence_region_json: Mapped[dict[str, object] | None] = mapped_column(JSON(none_as_null=True))
    entity_reference: Mapped[str | None] = mapped_column(String(200))
    extracted_text_snippet: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DebriefSession(TimestampMixin, Base):
    __tablename__ = "debrief_sessions"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('created', 'collecting', 'processing', 'review', 'completed', 'cancelled', 'failed')",
            name="ck_debrief_sessions_lifecycle_status",
        ),
        CheckConstraint("question_count >= 0", name="ck_debrief_sessions_question_count"),
        CheckConstraint(
            "max_questions BETWEEN 1 AND 10",
            name="ck_debrief_sessions_max_questions",
        ),
        CheckConstraint(
            "question_count <= max_questions",
            name="ck_debrief_sessions_question_cap",
        ),
        CheckConstraint(
            "failure_code IS NULL OR length(failure_code) <= 100",
            name="ck_debrief_sessions_failure_code",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_debrief_sessions_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_debrief_sessions_capture_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_debrief_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "started_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_debrief_sessions_starter_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_debrief_sessions_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "started_by_user_id",
            "idempotency_key",
            name="uq_debrief_sessions_idempotency",
        ),
        Index(
            "ix_debrief_sessions_organisation_interaction_created",
            "organisation_id",
            "interaction_id",
            "created_at",
        ),
        Index(
            "ix_debrief_sessions_organisation_status",
            "organisation_id",
            "lifecycle_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    started_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="created",
        server_default="created",
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    current_question_json: Mapped[dict[str, object] | None] = mapped_column(JSON(none_as_null=True))
    safety_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voice_processing_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_early: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DebriefTurn(Base):
    __tablename__ = "debrief_turns"
    __table_args__ = (
        CheckConstraint("turn_number > 0", name="ck_debrief_turns_number"),
        CheckConstraint("input_mode IN ('text', 'voice')", name="ck_debrief_turns_input_mode"),
        CheckConstraint(
            "length(trim(answer_text)) BETWEEN 1 AND 12000",
            name="ck_debrief_turns_answer_text",
        ),
        CheckConstraint(
            "audio_duration_seconds IS NULL OR audio_duration_seconds BETWEEN 0 AND 180",
            name="ck_debrief_turns_audio_duration",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_debrief_turns_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_debrief_turns_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_debrief_turns_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_debrief_turns_evidence_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_debrief_turns_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "session_id",
            "turn_number",
            name="uq_debrief_turns_session_number",
        ),
        UniqueConstraint(
            "organisation_id",
            "session_id",
            "idempotency_key",
            name="uq_debrief_turns_idempotency",
        ),
        Index(
            "ix_debrief_turns_organisation_session_number",
            "organisation_id",
            "session_id",
            "turn_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    audio_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transcription_provider: Mapped[str | None] = mapped_column(String(40))
    transcription_request_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DocumentSource(TimestampMixin, Base):
    __tablename__ = "document_sources"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('proposal', 'rfp', 'rfq', 'requirements', 'contract', 'sow', "
            "'pricing', 'procurement', 'security_questionnaire', 'implementation_plan', "
            "'technical_specification', 'customer_presentation', 'sales_material', 'other')",
            name="ck_document_sources_type",
        ),
        CheckConstraint(
            "source_ownership IN ('customer_provided', 'salesperson_provided', 'jointly_created', "
            "'externally_generated', 'system_imported', 'unknown')",
            name="ck_document_sources_ownership",
        ),
        CheckConstraint(
            "mime_type IN ('application/pdf', 'text/plain')",
            name="ck_document_sources_mime",
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 50000000", name="ck_document_sources_size"),
        CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_document_sources_checksum",
        ),
        CheckConstraint(
            "processing_status IN ('received', 'processing', 'review', 'completed', 'failed', "
            "'deletion_pending', 'deleted')",
            name="ck_document_sources_processing",
        ),
        CheckConstraint(
            "storage_status IN ('available', 'missing', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_document_sources_storage",
        ),
        CheckConstraint("processing_attempts BETWEEN 0 AND 5", name="ck_document_sources_attempts"),
        CheckConstraint("page_count IS NULL OR page_count BETWEEN 1 AND 500", name="ck_document_sources_pages"),
        CheckConstraint(
            "extracted_character_count IS NULL OR extracted_character_count BETWEEN 1 AND 2000000",
            name="ck_document_sources_characters",
        ),
        CheckConstraint(
            "company_id IS NOT NULL OR opportunity_id IS NOT NULL OR interaction_id IS NOT NULL",
            name="ck_document_sources_association",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_document_sources_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_document_sources_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_document_sources_interaction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_document_sources_capture_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_document_sources_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "uploaded_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_document_sources_user_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_document_sources_org_id"),
        UniqueConstraint("organisation_id", "source_evidence_id", name="uq_document_sources_evidence"),
        UniqueConstraint("organisation_id", "checksum_sha256", name="uq_document_sources_content"),
        UniqueConstraint(
            "organisation_id",
            "uploaded_by_user_id",
            "idempotency_key",
            name="uq_document_sources_idempotency",
        ),
        UniqueConstraint("storage_key", name="uq_document_sources_storage_key"),
        Index("ix_document_sources_org_opportunity", "organisation_id", "opportunity_id", "created_at"),
        Index("ix_document_sources_org_company", "organisation_id", "company_id", "created_at"),
        Index("ix_document_sources_org_status", "organisation_id", "processing_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    capture_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ownership: Mapped[str] = mapped_column(String(30), nullable=False)
    display_filename: Mapped[str] = mapped_column(String(160), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(360), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    document_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="received", server_default="received"
    )
    storage_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="available", server_default="available"
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_character_count: Mapped[int | None] = mapped_column(Integer)
    provider_name: Mapped[str | None] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    authority_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_processing_acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentFragment(Base):
    __tablename__ = "document_fragments"
    __table_args__ = (
        CheckConstraint("page_number IS NULL OR page_number BETWEEN 1 AND 500", name="ck_document_fragments_page"),
        CheckConstraint("paragraph_index BETWEEN 0 AND 100000", name="ck_document_fragments_paragraph"),
        CheckConstraint("length(trim(content_text)) BETWEEN 1 AND 12000", name="ck_document_fragments_content"),
        ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_document_fragments_source_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_document_fragments_evidence_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_document_fragments_org_id"),
        UniqueConstraint(
            "organisation_id",
            "document_source_id",
            "page_number",
            "paragraph_index",
            name="uq_document_fragments_locator",
        ),
        Index("ix_document_fragments_org_source", "organisation_id", "document_source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    document_source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSource(TimestampMixin, Base):
    __tablename__ = "email_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('customer_sent', 'salesperson_sent', 'internal_forward', "
            "'manually_pasted', 'external_provider_import')",
            name="ck_email_sources_type",
        ),
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal', 'unknown')", name="ck_email_sources_direction"
        ),
        CheckConstraint(
            "sender_identity_state IN ('verified_contact', 'unknown')",
            name="ck_email_sources_sender_identity",
        ),
        CheckConstraint(
            "origin_class IN ('customer_direct', 'salesperson_reported', 'imported_external')",
            name="ck_email_sources_origin",
        ),
        CheckConstraint("support_class IN ('direct', 'reported', 'context')", name="ck_email_sources_support"),
        CheckConstraint(
            "quote_handling IN ('none', 'stripped', 'ambiguous')",
            name="ck_email_sources_quote_handling",
        ),
        CheckConstraint(
            "processing_status IN ('received', 'processing', 'review', 'completed', 'failed', 'deleted')",
            name="ck_email_sources_processing",
        ),
        CheckConstraint("processing_attempts BETWEEN 0 AND 5", name="ck_email_sources_attempts"),
        CheckConstraint("length(trim(body_text)) BETWEEN 1 AND 200000", name="ck_email_sources_body"),
        CheckConstraint(
            "length(trim(normalized_body_text)) BETWEEN 1 AND 200000",
            name="ck_email_sources_normalized_body",
        ),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_email_sources_checksum",
        ),
        CheckConstraint(
            "company_id IS NOT NULL OR opportunity_id IS NOT NULL OR interaction_id IS NOT NULL",
            name="ck_email_sources_association",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_email_sources_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_email_sources_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_email_sources_interaction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_email_sources_capture_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_email_sources_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "sender_contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_email_sources_contact_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "submitted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_email_sources_user_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_email_sources_org_id"),
        UniqueConstraint("organisation_id", "source_evidence_id", name="uq_email_sources_evidence"),
        UniqueConstraint("organisation_id", "content_sha256", name="uq_email_sources_content"),
        UniqueConstraint(
            "organisation_id",
            "submitted_by_user_id",
            "idempotency_key",
            name="uq_email_sources_idempotency",
        ),
        Index("ix_email_sources_org_opportunity", "organisation_id", "opportunity_id", "message_at"),
        Index("ix_email_sources_org_company", "organisation_id", "company_id", "message_at"),
        Index("ix_email_sources_org_status", "organisation_id", "processing_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    capture_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sender_contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_identity_state: Mapped[str] = mapped_column(String(24), nullable=False)
    origin_class: Mapped[str] = mapped_column(String(30), nullable=False)
    support_class: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_body_text: Mapped[str] = mapped_column(Text, nullable=False)
    quote_handling: Mapped[str] = mapped_column(String(16), nullable=False)
    message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="received", server_default="received"
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    provider_name: Mapped[str | None] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    authority_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_processing_acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceCandidateEvidence(TimestampMixin, Base):
    __tablename__ = "source_candidate_evidence"
    __table_args__ = (
        CheckConstraint("source_kind IN ('document', 'email')", name="ck_source_candidates_kind"),
        CheckConstraint(
            "(source_kind = 'document' AND document_source_id IS NOT NULL AND email_source_id IS NULL) OR "
            "(source_kind = 'email' AND email_source_id IS NOT NULL AND document_source_id IS NULL)",
            name="ck_source_candidates_source",
        ),
        CheckConstraint(
            "evidence_category IN ('buying_signal', 'objection', 'competitor', 'stakeholder', 'decision', "
            "'action_item', 'risk', 'open_question', 'commitment', 'timeline', 'budget', 'procurement', "
            "'security_legal', 'implementation', 'commercial_intent', 'customer_request', "
            "'technical_requirement', 'contractual_requirement', 'pricing_requirement', "
            "'renewal_signal', 'expansion_signal', 'other')",
            name="ck_source_candidates_category",
        ),
        CheckConstraint("interpretation_origin = 'ai_inferred'", name="ck_source_candidates_interpretation"),
        CheckConstraint(
            "origin_class IN ('customer_direct', 'seller_prepared', 'salesperson_reported', 'imported_external')",
            name="ck_source_candidates_origin",
        ),
        CheckConstraint("support_class IN ('direct', 'reported', 'context')", name="ck_source_candidates_support"),
        CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')",
            name="ck_source_candidates_validation",
        ),
        CheckConstraint("review_state IN ('pending', 'accepted', 'rejected')", name="ck_source_candidates_review"),
        CheckConstraint(
            "conflict_state IN ('not_assessed', 'conflicting', 'supersedes', 'superseded')",
            name="ck_source_candidates_conflict",
        ),
        CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_source_candidates_statements",
        ),
        CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_source_candidates_review_consistency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_source_candidates_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "email_source_id"],
            ["email_sources.organisation_id", "email_sources.id"],
            name="fk_source_candidates_email_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_source_candidates_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_source_candidates_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "document_fragment_id"],
            ["document_fragments.organisation_id", "document_fragments.id"],
            name="fk_source_candidates_fragment_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_source_candidates_reviewer_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "supersedes_candidate_id"],
            ["source_candidate_evidence.organisation_id", "source_candidate_evidence.id"],
            name="fk_source_candidates_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_source_candidates_org_id"),
        UniqueConstraint(
            "organisation_id",
            "source_evidence_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_source_candidates_statement",
        ),
        Index("ix_source_candidates_org_document", "organisation_id", "document_source_id", "review_state"),
        Index("ix_source_candidates_org_email", "organisation_id", "email_source_id", "review_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    document_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    email_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_fragment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    accepted_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_category: Mapped[str] = mapped_column(String(40), nullable=False)
    statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    statement_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    interpretation_origin: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ai_inferred", server_default="ai_inferred"
    )
    origin_class: Mapped[str] = mapped_column(String(30), nullable=False)
    support_class: Mapped[str] = mapped_column(String(20), nullable=False)
    source_location_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    validation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unreviewed", server_default="unreviewed"
    )
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    conflict_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_assessed", server_default="not_assessed"
    )
    supersedes_candidate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RevenueBrainSourceSnapshot(Base):
    __tablename__ = "revenue_brain_source_snapshots"
    __table_args__ = (
        CheckConstraint("source_kind IN ('document', 'email')", name="ck_brain_source_snapshots_kind"),
        CheckConstraint(
            "(source_kind = 'document' AND document_source_id IS NOT NULL AND email_source_id IS NULL) OR "
            "(source_kind = 'email' AND email_source_id IS NOT NULL AND document_source_id IS NULL)",
            name="ck_brain_source_snapshots_source",
        ),
        CheckConstraint("schema_version = 1", name="ck_brain_source_snapshots_schema"),
        CheckConstraint("version > 0", name="ck_brain_source_snapshots_version"),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_brain_source_snapshots_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_brain_source_snapshots_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_brain_source_snapshots_interaction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_brain_source_snapshots_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_brain_source_snapshots_document_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "email_source_id"],
            ["email_sources.organisation_id", "email_sources.id"],
            name="fk_brain_source_snapshots_email_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_brain_source_snapshots_org_id"),
        UniqueConstraint(
            "organisation_id",
            "source_evidence_id",
            "version",
            name="uq_brain_source_snapshots_version",
        ),
        Index("ix_brain_source_snapshots_org_company", "organisation_id", "company_id", "created_at"),
        Index("ix_brain_source_snapshots_org_opportunity", "organisation_id", "opportunity_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    document_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    email_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvidenceFragment(Base):
    __tablename__ = "evidence_fragments"
    __table_args__ = (
        CheckConstraint("locator_type = 'debrief_turn'", name="ck_evidence_fragments_locator_type"),
        CheckConstraint(
            "length(trim(content_text)) BETWEEN 1 AND 12000",
            name="ck_evidence_fragments_content_text",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_evidence_fragments_evidence_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_evidence_fragments_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "turn_id"],
            ["debrief_turns.organisation_id", "debrief_turns.id"],
            name="fk_evidence_fragments_turn_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_evidence_fragments_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "turn_id",
            name="uq_evidence_fragments_turn",
        ),
        Index(
            "ix_evidence_fragments_organisation_evidence",
            "organisation_id",
            "evidence_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    locator_type: Mapped[str] = mapped_column(String(30), nullable=False, default="debrief_turn")
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateEvidence(TimestampMixin, Base):
    __tablename__ = "candidate_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_category IN ('stakeholder', 'buying_signal', 'objection', 'competitor', "
            "'risk', 'decision', 'action_item', 'open_question', 'commitment', 'timeline', "
            "'procurement', 'budget', 'security_legal', 'implementation', 'commercial_intent', "
            "'customer_request', 'other')",
            name="ck_candidate_evidence_category",
        ),
        CheckConstraint("origin_class = 'salesperson_reported'", name="ck_candidate_evidence_origin"),
        CheckConstraint("support_class = 'reported'", name="ck_candidate_evidence_support"),
        CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')",
            name="ck_candidate_evidence_validation_state",
        ),
        CheckConstraint(
            "review_state IN ('pending', 'accepted', 'rejected')",
            name="ck_candidate_evidence_review_state",
        ),
        CheckConstraint(
            "conflict_state IN ('not_assessed', 'conflicting', 'unresolved', 'corroborated')",
            name="ck_candidate_evidence_conflict_state",
        ),
        CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_candidate_evidence_statements",
        ),
        CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_candidate_evidence_review_consistency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_candidate_evidence_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_candidate_evidence_session_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_fragment_id"],
            ["evidence_fragments.organisation_id", "evidence_fragments.id"],
            name="fk_candidate_evidence_fragment_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_candidate_evidence_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_candidate_evidence_reviewer_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_candidate_evidence_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "session_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_candidate_evidence_session_statement",
        ),
        Index(
            "ix_candidate_evidence_organisation_session_review",
            "organisation_id",
            "session_id",
            "review_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_fragment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accepted_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_category: Mapped[str] = mapped_column(String(30), nullable=False)
    statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    statement_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_class: Mapped[str] = mapped_column(
        String(30), nullable=False, default="salesperson_reported", server_default="salesperson_reported"
    )
    support_class: Mapped[str] = mapped_column(
        String(20), nullable=False, default="reported", server_default="reported"
    )
    validation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unreviewed", server_default="unreviewed"
    )
    entity_reference: Mapped[str | None] = mapped_column(String(200))
    explicitly_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    conflict_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_assessed", server_default="not_assessed"
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InteractionIntelligenceSnapshot(Base):
    __tablename__ = "interaction_intelligence_snapshots"
    __table_args__ = (
        CheckConstraint("schema_version > 0", name="ck_interaction_intelligence_schema_version"),
        CheckConstraint("version > 0", name="ck_interaction_intelligence_version"),
        CheckConstraint("validation_state = 'validated'", name="ck_interaction_intelligence_validation"),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_intelligence_interaction_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_interaction_intelligence_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_interaction_intelligence_session_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_interaction_intelligence_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "version",
            name="uq_interaction_intelligence_logical_version",
        ),
        UniqueConstraint(
            "organisation_id",
            "session_id",
            name="uq_interaction_intelligence_session",
        ),
        Index(
            "ix_interaction_intelligence_organisation_opportunity_created",
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
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    validation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="validated", server_default="validated"
    )
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RevenueBrainInteractionSnapshot(Base):
    __tablename__ = "revenue_brain_interaction_snapshots"
    __table_args__ = (
        CheckConstraint("schema_version > 0", name="ck_revenue_brain_interaction_schema_version"),
        CheckConstraint("version > 0", name="ck_revenue_brain_interaction_version"),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_interaction_company_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_interaction_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_revenue_brain_interaction_interaction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_intelligence_id"],
            ["interaction_intelligence_snapshots.organisation_id", "interaction_intelligence_snapshots.id"],
            name="fk_revenue_brain_interaction_intelligence_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_revenue_brain_interaction_organisation_id_id"),
        UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "interaction_intelligence_id",
            name="uq_revenue_brain_interaction_source",
        ),
        Index(
            "ix_revenue_brain_interaction_organisation_opportunity_created",
            "organisation_id",
            "opportunity_id",
            "created_at",
        ),
        Index(
            "ix_revenue_brain_interaction_organisation_company_created",
            "organisation_id",
            "company_id",
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
    interaction_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    interaction_intelligence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


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
