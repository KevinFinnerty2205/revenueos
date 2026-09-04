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
    false,
    func,
    text,
    true,
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
    CampaignApprovalMode,
    CampaignEnrollmentState,
    CampaignState,
    CampaignStepState,
    CaptureSessionStatus,
    CaptureSessionType,
    CompanyStatus,
    ConnectionStatus,
    ConnectorKey,
    EventAttendeeMatchState,
    EventAttendeePriority,
    EventPlanState,
    EventState,
    EventType,
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
    OutreachPurpose,
    OutreachState,
    ParticipantRole,
    ProspectCandidateFeedbackState,
    ProspectDiscoveryRunStatus,
    ProspectRelationshipState,
    ProspectResearchRunStatus,
    ProspectTargetMarketStatus,
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
        CheckConstraint("length(trim(timezone)) BETWEEN 1 AND 64", name="ck_organisations_timezone"),
        UniqueConstraint("slug", name="uq_organisations_slug"),
        UniqueConstraint("external_auth_id", name="uq_organisations_external_auth_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    external_auth_id: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC", server_default="UTC")

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
        CheckConstraint("module_key IN ('prospect', 'engage', 'create', 'crm')", name="ck_module_entitlements_key"),
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


class SellingProfile(TimestampMixin, Base):
    __tablename__ = "selling_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profiles_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", name="uq_selling_profiles_organisation"),
        UniqueConstraint("organisation_id", "id", name="uq_selling_profiles_org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class SellingProfileRevision(TimestampMixin, Base):
    __tablename__ = "selling_profile_revisions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'approved', 'superseded', 'retired')",
            name="ck_selling_profile_revisions_state",
        ),
        CheckConstraint("revision_number > 0", name="ck_selling_profile_revisions_number"),
        CheckConstraint("schema_version = 1", name="ck_selling_profile_revisions_schema"),
        CheckConstraint("lock_version > 0", name="ck_selling_profile_revisions_lock"),
        CheckConstraint("length(content_fingerprint) = 64", name="ck_selling_profile_revisions_fingerprint"),
        CheckConstraint(
            "(state = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND superseded_at IS NULL AND retired_at IS NULL) OR "
            "(state = 'approved' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NULL AND retired_at IS NULL) OR "
            "(state = 'superseded' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NOT NULL AND retired_at IS NULL) OR "
            "(state = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NULL AND retired_at IS NOT NULL)",
            name="ck_selling_profile_revisions_lifecycle",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "profile_id"],
            ["selling_profiles.organisation_id", "selling_profiles.id"],
            name="fk_selling_profile_revisions_profile",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profile_revisions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profile_revisions_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_selling_profile_revisions_org_id"),
        UniqueConstraint(
            "organisation_id",
            "profile_id",
            "revision_number",
            name="uq_selling_profile_revisions_number",
        ),
        UniqueConstraint(
            "organisation_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_selling_profile_revisions_idempotency",
        ),
        Index(
            "uq_selling_profile_revisions_draft",
            "organisation_id",
            "profile_id",
            unique=True,
            postgresql_where=text("state = 'draft'"),
            sqlite_where=text("state = 'draft'"),
        ),
        Index(
            "uq_selling_profile_revisions_approved",
            "organisation_id",
            "profile_id",
            unique=True,
            postgresql_where=text("state = 'approved'"),
            sqlite_where=text("state = 'approved'"),
        ),
        Index(
            "ix_selling_profile_revisions_org_history",
            "organisation_id",
            "profile_id",
            "revision_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProspectUsageCounter(Base):
    __tablename__ = "prospect_usage_counters"
    __table_args__ = (
        CheckConstraint(
            "scope_key = 'organisation' OR scope_key LIKE 'user:%'",
            name="ck_prospect_usage_scope",
        ),
        CheckConstraint("research_run_count >= 0", name="ck_prospect_usage_count"),
        CheckConstraint("people_discovery_count >= 0", name="ck_prospect_people_discovery_count"),
        CheckConstraint("discovery_run_count >= 0", name="ck_prospect_discovery_count"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    research_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    people_discovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    discovery_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProspectTargetMarket(TimestampMixin, Base):
    __tablename__ = "prospect_target_markets"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_prospect_markets_name"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_prospect_markets_status"),
        CheckConstraint("current_version > 0", name="ck_prospect_markets_version"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_prospect_markets_archive",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_markets_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_markets_org_id"),
        UniqueConstraint("organisation_id", "name", name="uq_prospect_markets_org_name"),
        Index("ix_prospect_markets_org_status", "organisation_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProspectTargetMarketStatus.ACTIVE.value,
        server_default=ProspectTargetMarketStatus.ACTIVE.value,
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProspectTargetMarketVersion(Base):
    __tablename__ = "prospect_target_market_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_prospect_market_versions_number"),
        CheckConstraint(
            "description IS NULL OR length(description) <= 400",
            name="ck_prospect_market_versions_description",
        ),
        CheckConstraint(
            "research_objective IS NULL OR length(research_objective) <= 300",
            name="ck_prospect_market_versions_objective",
        ),
        CheckConstraint(
            "minimum_employee_band IS NULL OR minimum_employee_band IN "
            "('50_199', '200_499', '500_999', '1000_4999', '5000_plus')",
            name="ck_prospect_market_versions_employee_band",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_market_id"],
            ["prospect_target_markets.organisation_id", "prospect_target_markets.id"],
            name="fk_prospect_market_versions_market",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_market_versions_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_market_versions_org_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "target_market_id",
            name="uq_prospect_market_versions_org_id_market",
        ),
        UniqueConstraint(
            "organisation_id",
            "target_market_id",
            "version",
            name="uq_prospect_market_versions_number",
        ),
        Index(
            "ix_prospect_market_versions_org_market",
            "organisation_id",
            "target_market_id",
            "version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_market_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(400))
    industries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    countries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    minimum_employee_band: Mapped[str | None] = mapped_column(String(20))
    organisation_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_business_characteristics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    excluded_industries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exclude_existing_accounts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    research_objective: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProspectDiscoveryRun(Base):
    __tablename__ = "prospect_discovery_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial', 'failed')",
            name="ck_prospect_discovery_runs_status",
        ),
        CheckConstraint("schema_version > 0", name="ck_prospect_discovery_runs_schema"),
        CheckConstraint(
            "candidate_count >= 0 AND eligible_count >= 0 AND excluded_count >= 0 AND partial_count >= 0",
            name="ck_prospect_discovery_runs_counts",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_market_id"],
            ["prospect_target_markets.organisation_id", "prospect_target_markets.id"],
            name="fk_prospect_discovery_runs_market",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_market_version_id", "target_market_id"],
            [
                "prospect_target_market_versions.organisation_id",
                "prospect_target_market_versions.id",
                "prospect_target_market_versions.target_market_id",
            ],
            name="fk_prospect_discovery_runs_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_discovery_runs_requester",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "refresh_of_run_id"],
            ["prospect_discovery_runs.organisation_id", "prospect_discovery_runs.id"],
            name="fk_prospect_discovery_runs_refresh",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_discovery_runs_org_id"),
        UniqueConstraint(
            "organisation_id",
            "target_market_id",
            "idempotency_key",
            name="uq_prospect_discovery_runs_idempotency",
        ),
        Index(
            "ix_prospect_discovery_runs_org_market",
            "organisation_id",
            "target_market_id",
            "created_at",
        ),
        Index("ix_prospect_discovery_runs_org_status", "organisation_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_market_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_market_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProspectDiscoveryRunStatus.PENDING.value,
        server_default=ProspectDiscoveryRunStatus.PENDING.value,
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    refresh_of_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    partial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProspectDiscoveryCandidate(Base):
    __tablename__ = "prospect_discovery_candidates"
    __table_args__ = (
        CheckConstraint("match_state IN ('match', 'partial', 'excluded')", name="ck_prospect_candidates_state"),
        CheckConstraint(
            "priority IN ('high', 'worth_researching', 'needs_more_information', 'excluded')",
            name="ck_prospect_candidates_priority",
        ),
        CheckConstraint(
            "relationship_state IN ('new_prospect', 'existing_account_no_active_opportunity', 'active_opportunity')",
            name="ck_prospect_candidates_relationship",
        ),
        CheckConstraint(
            "(match_state = 'excluded' AND priority = 'excluded') OR "
            "(match_state <> 'excluded' AND priority <> 'excluded')",
            name="ck_prospect_candidates_state_priority",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "run_id"],
            ["prospect_discovery_runs.organisation_id", "prospect_discovery_runs.id"],
            name="fk_prospect_candidates_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_candidates_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "matched_company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_prospect_candidates_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "active_opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_prospect_candidates_opportunity",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_candidates_org_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "run_id",
            name="uq_prospect_candidates_org_id_run",
        ),
        UniqueConstraint(
            "organisation_id",
            "run_id",
            "target_id",
            name="uq_prospect_candidates_run_target",
        ),
        Index("ix_prospect_candidates_org_run", "organisation_id", "run_id", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    match_state: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(30), nullable=False)
    relationship_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProspectRelationshipState.NEW_PROSPECT.value,
        server_default=ProspectRelationshipState.NEW_PROSPECT.value,
    )
    matched_company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    active_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    employee_band: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(120))
    organisation_type: Mapped[str | None] = mapped_column(String(40))
    business_characteristics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    provider_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProspectCandidateReason(Base):
    __tablename__ = "prospect_candidate_reasons"
    __table_args__ = (
        CheckConstraint("state IN ('matched', 'missing', 'excluded', 'context')", name="ck_prospect_reasons_state"),
        CheckConstraint(
            "data_origin IN ('provider_supplied', 'verified_research', 'existing_revenueos_data', 'unknown')",
            name="ck_prospect_reasons_origin",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_reasons_trust",
        ),
        CheckConstraint(
            "length(trim(product_safe_text)) BETWEEN 1 AND 300",
            name="ck_prospect_reasons_text",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "candidate_id", "run_id"],
            [
                "prospect_discovery_candidates.organisation_id",
                "prospect_discovery_candidates.id",
                "prospect_discovery_candidates.run_id",
            ],
            name="fk_prospect_reasons_candidate",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_reasons_org_id"),
        UniqueConstraint(
            "organisation_id",
            "candidate_id",
            "reason_code",
            name="uq_prospect_reasons_candidate_code",
        ),
        Index("ix_prospect_reasons_org_candidate", "organisation_id", "candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    criterion_key: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    product_safe_text: Mapped[str] = mapped_column(String(300), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(40), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_value_class: Mapped[str | None] = mapped_column(String(80))
    source_reference: Mapped[str | None] = mapped_column(String(2048))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProspectTargetFeedback(TimestampMixin, Base):
    __tablename__ = "prospect_target_feedback"
    __table_args__ = (
        CheckConstraint("state IN ('saved', 'excluded')", name="ck_prospect_feedback_state"),
        CheckConstraint(
            "exclusion_reason IS NULL OR exclusion_reason IN "
            "('wrong_industry', 'too_small', 'too_large', 'outside_territory', "
            "'existing_relationship', 'not_relevant', 'other')",
            name="ck_prospect_feedback_reason",
        ),
        CheckConstraint(
            "(state = 'saved' AND exclusion_reason IS NULL) OR state = 'excluded'",
            name="ck_prospect_feedback_state_reason",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_feedback_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_feedback_target",
            ondelete="CASCADE",
        ),
        Index("ix_prospect_feedback_org_user", "organisation_id", "user_id", "state"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProspectCandidateFeedbackState.SAVED.value,
        server_default=ProspectCandidateFeedbackState.SAVED.value,
    )
    exclusion_reason: Mapped[str | None] = mapped_column(String(40))


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
        Index("ix_companies_org_archived", "organisation_id", "archived_at", "name"),
        Index(
            "uq_companies_org_normalized_domain",
            "organisation_id",
            "normalized_domain",
            unique=True,
            postgresql_where=text("normalized_domain IS NOT NULL"),
            sqlite_where=text("normalized_domain IS NOT NULL"),
        ),
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
    location: Mapped[str | None] = mapped_column(String(200))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CompanyStatus.PROSPECT.value,
        server_default=CompanyStatus.PROSPECT.value,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class ProspectPerson(TimestampMixin, Base):
    __tablename__ = "prospect_people"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="ck_prospect_people_name"),
        CheckConstraint("length(trim(first_name)) > 0", name="ck_prospect_people_first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="ck_prospect_people_last_name"),
        CheckConstraint(
            "identity_state IN ('supported', 'ambiguous')",
            name="ck_prospect_people_identity_state",
        ),
        CheckConstraint(
            "employment_state IN ('current', 'uncertain', 'no_longer_current')",
            name="ck_prospect_people_employment_state",
        ),
        CheckConstraint(
            "(promoted_contact_id IS NULL AND promoted_by_user_id IS NULL AND promoted_at IS NULL) OR "
            "(promoted_contact_id IS NOT NULL AND promoted_by_user_id IS NOT NULL AND promoted_at IS NOT NULL)",
            name="ck_prospect_people_promotion",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_people_target",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "promoted_contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_prospect_people_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "promoted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_people_promoter",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_people_org_id"),
        UniqueConstraint("organisation_id", "id", "target_id", name="uq_prospect_people_org_id_target"),
        UniqueConstraint(
            "organisation_id",
            "target_id",
            "provider_key",
            "provider_person_id",
            name="uq_prospect_people_provider_identity",
        ),
        Index("ix_prospect_people_org_target", "organisation_id", "target_id"),
        Index("ix_prospect_people_org_contact", "organisation_id", "promoted_contact_id"),
        Index("ix_prospect_people_org_name", "organisation_id", "display_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_person_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_role: Mapped[str] = mapped_column(String(200), nullable=False)
    current_company: Mapped[str] = mapped_column(String(200), nullable=False)
    public_professional_location: Mapped[str | None] = mapped_column(String(200))
    public_profile_url: Mapped[str | None] = mapped_column(String(2048))
    relevant_function: Mapped[str] = mapped_column(String(80), nullable=False)
    why_may_matter: Mapped[str] = mapped_column(String(600), nullable=False)
    discovery_source: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_attribution: Mapped[str] = mapped_column(String(120), nullable=False)
    identity_state: Mapped[str] = mapped_column(String(20), nullable=False, default="supported")
    employment_state: Mapped[str] = mapped_column(String(24), nullable=False, default="current")
    promoted_contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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
            ["organisation_id", "person_id", "target_id"],
            ["prospect_people.organisation_id", "prospect_people.id", "prospect_people.target_id"],
            name="fk_prospect_runs_person",
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
        Index("ix_prospect_runs_org_person_created", "organisation_id", "person_id", "created_at"),
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
    person_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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
            "'structured_provider', 'public_filing', 'reputable_news', 'other_public', "
            "'company_leadership', 'professional_profile', 'professional_article', "
            "'professional_post', 'interview', 'conference', 'association', 'contact_provider', "
            "'company_contact_page')",
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
            "'trigger', 'potential_fit', 'current_role', 'current_company', 'career_history', "
            "'responsibility', 'expertise', 'professional_interest', 'professional_activity', "
            "'company_initiative', 'public_statement', 'authored_content', 'conference_activity', "
            "'why_person_matters', 'conversation_context', 'other_professional', 'other')",
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


class ProspectBuyingRoleHypothesis(Base):
    __tablename__ = "prospect_buying_role_hypotheses"
    __table_args__ = (
        CheckConstraint(
            "hypothesized_role IN ('executive_sponsor', 'economic_buyer_candidate', 'champion_candidate', "
            "'business_buyer', 'technical_evaluator', 'security', 'procurement', 'legal', 'finance', "
            "'end_user_influencer', 'other_relevant')",
            name="ck_prospect_buying_roles_role",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_buying_roles_trust",
        ),
        CheckConstraint(
            "review_state IN ('needs_validation', 'relevant', 'not_relevant')",
            name="ck_prospect_buying_roles_review",
        ),
        CheckConstraint(
            "assessment_origin IN ('system_hypothesis', 'seller_assessed')",
            name="ck_prospect_buying_roles_origin",
        ),
        CheckConstraint("length(trim(rationale)) BETWEEN 1 AND 600", name="ck_prospect_buying_roles_rationale"),
        ForeignKeyConstraint(
            ["organisation_id", "person_id", "target_id"],
            ["prospect_people.organisation_id", "prospect_people.id", "prospect_people.target_id"],
            name="fk_prospect_buying_roles_person",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_buying_roles_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_buying_roles_reviewer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_buying_roles_org_id"),
        UniqueConstraint(
            "organisation_id", "run_id", "person_id", "hypothesized_role", name="uq_prospect_buying_roles_run_role"
        ),
        Index("ix_prospect_buying_roles_org_person", "organisation_id", "person_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    hypothesized_role: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(String(600), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    review_state: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_validation")
    assessment_origin: Mapped[str] = mapped_column(String(24), nullable=False, default="system_hypothesis")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProspectBuyingRoleSource(Base):
    __tablename__ = "prospect_buying_role_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "hypothesis_id"],
            ["prospect_buying_role_hypotheses.organisation_id", "prospect_buying_role_hypotheses.id"],
            name="fk_prospect_buying_role_sources_hypothesis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_buying_role_sources_source",
            ondelete="CASCADE",
        ),
        Index("ix_prospect_buying_role_sources_org_run", "organisation_id", "run_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class ProspectContactPoint(Base):
    __tablename__ = "prospect_contact_points"
    __table_args__ = (
        CheckConstraint(
            "point_type IN ('business_email', 'business_phone', 'company_switchboard', 'public_professional_profile')",
            name="ck_prospect_contact_points_type",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_contact_points_trust",
        ),
        CheckConstraint(
            "verification_method IN ('authoritative_public', 'provider_reported', 'not_verified')",
            name="ck_prospect_contact_points_verification",
        ),
        CheckConstraint("length(trim(value)) BETWEEN 1 AND 2048", name="ck_prospect_contact_points_value"),
        ForeignKeyConstraint(
            ["organisation_id", "person_id", "target_id"],
            ["prospect_people.organisation_id", "prospect_people.id", "prospect_people.target_id"],
            name="fk_prospect_contact_points_person",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_contact_points_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_contact_points_source",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_prospect_contact_points_org_id"),
        UniqueConstraint(
            "organisation_id",
            "run_id",
            "person_id",
            "point_type",
            "value_fingerprint",
            name="uq_prospect_contact_points_run_value",
        ),
        Index("ix_prospect_contact_points_org_person", "organisation_id", "person_id"),
        Index("ix_prospect_contact_points_org_fingerprint", "organisation_id", "point_type", "value_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    point_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    value_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    export_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ContactFieldSource(Base):
    __tablename__ = "contact_field_sources"
    __table_args__ = (
        CheckConstraint(
            "field_key IN ('email', 'phone', 'job_title', 'linkedin_url')",
            name="ck_contact_field_sources_field",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_contact_field_sources_trust",
        ),
        CheckConstraint("source_type IN ('prospect_person', 'event_list')", name="ck_contact_field_sources_type"),
        CheckConstraint(
            "source_organisation_id IS NULL OR source_organisation_id = organisation_id",
            name="ck_contact_field_sources_tenant",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_contact_field_sources_contact",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_organisation_id", "source_prospect_person_id"],
            ["prospect_people.organisation_id", "prospect_people.id"],
            name="fk_contact_field_sources_person",
            ondelete="SET NULL",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_contact_field_sources_org_id"),
        UniqueConstraint(
            "organisation_id", "contact_id", "field_key", "value_fingerprint", name="uq_contact_field_sources_value"
        ),
        Index("ix_contact_field_sources_org_contact", "organisation_id", "contact_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    field_key: Mapped[str] = mapped_column(String(40), nullable=False)
    value_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="prospect_person")
    source_organisation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_prospect_person_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="ck_contacts_first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="ck_contacts_last_name"),
        CheckConstraint("status IN ('active', 'left_company')", name="ck_contacts_status"),
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
        Index("ix_contacts_org_archived", "organisation_id", "archived_at", "last_name", "first_name"),
        Index(
            "uq_contacts_org_business_email",
            "organisation_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
            sqlite_where=text("email IS NOT NULL"),
        ),
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
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    job_title: Mapped[str | None] = mapped_column(String(150))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", server_default="active")
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalesPipeline(TimestampMixin, Base):
    __tablename__ = "sales_pipelines"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="ck_sales_pipelines_name"),
        CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_sales_pipelines_archive",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_pipelines_org_id"),
        Index("ix_sales_pipelines_org_active", "organisation_id", "active", "created_at"),
        Index(
            "uq_sales_pipelines_org_default",
            "organisation_id",
            unique=True,
            postgresql_where=text("is_default AND active"),
            sqlite_where=text("is_default = 1 AND active = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalesPipelineStage(TimestampMixin, Base):
    __tablename__ = "sales_pipeline_stages"
    __table_args__ = (
        CheckConstraint("length(trim(stage_key)) BETWEEN 1 AND 64", name="ck_pipeline_stages_key"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="ck_pipeline_stages_name"),
        CheckConstraint("position BETWEEN 0 AND 11", name="ck_pipeline_stages_position"),
        CheckConstraint("stage_type IN ('open', 'won', 'lost')", name="ck_pipeline_stages_type"),
        CheckConstraint(
            "guidance IS NULL OR length(guidance) BETWEEN 1 AND 300",
            name="ck_pipeline_stages_guidance",
        ),
        CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_pipeline_stages_archive",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_pipeline_stages_pipeline",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_pipeline_stages_org_id"),
        UniqueConstraint("organisation_id", "pipeline_id", "id", name="uq_pipeline_stages_org_pipeline_id"),
        UniqueConstraint("organisation_id", "pipeline_id", "stage_key", name="uq_pipeline_stages_org_pipeline_key"),
        Index(
            "ix_pipeline_stages_org_pipeline",
            "organisation_id",
            "pipeline_id",
            "active",
            "position",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(12), nullable=False)
    guidance: Mapped[str | None] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
        CheckConstraint(
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
            name="ck_opportunities_outcome_provenance",
        ),
        CheckConstraint(
            "outcome_note IS NULL OR length(outcome_note) BETWEEN 1 AND 500",
            name="ck_opportunities_outcome_note",
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
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_opportunities_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id", "pipeline_stage_id"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_opportunities_pipeline_stage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_opportunities_organisation_id_id"),
        Index("ix_opportunities_organisation_name", "organisation_id", "name"),
        Index("ix_opportunities_organisation_company", "organisation_id", "company_id"),
        Index("ix_opportunities_organisation_stage", "organisation_id", "stage"),
        Index("ix_opportunities_organisation_status", "organisation_id", "status"),
        Index("ix_opportunities_organisation_close", "organisation_id", "expected_close_date"),
        Index("ix_opportunities_organisation_updated", "organisation_id", "updated_at"),
        Index("ix_opportunities_org_archived", "organisation_id", "archived_at", "updated_at"),
        Index(
            "ix_opportunities_org_pipeline_stage",
            "organisation_id",
            "pipeline_id",
            "pipeline_stage_id",
            "status",
        ),
        Index("ix_opportunities_org_stage_entered", "organisation_id", "stage_entered_at"),
        Index(
            "ix_opportunities_org_actual_close_status",
            "organisation_id",
            "actual_close_date",
            "status",
        ),
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
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    pipeline_stage_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage_tracking_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_close_date: Mapped[date | None] = mapped_column(Date)
    outcome_reason: Mapped[str | None] = mapped_column(String(40))
    outcome_note: Mapped[str | None] = mapped_column(String(500))
    outcome_provenance: Mapped[str | None] = mapped_column(String(32))


class OpportunityStageEvent(Base):
    __tablename__ = "opportunity_stage_events"
    __table_args__ = (
        CheckConstraint(
            "source IN ('system_initial', 'migration_baseline', 'import_baseline', 'manual', 'external_crm')",
            name="ck_opportunity_stage_events_source",
        ),
        CheckConstraint(
            "from_stage_type IS NULL OR from_stage_type IN ('open', 'won', 'lost')",
            name="ck_opportunity_stage_events_from_type",
        ),
        CheckConstraint(
            "to_stage_type IN ('open', 'won', 'lost')",
            name="ck_opportunity_stage_events_to_type",
        ),
        CheckConstraint(
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
            name="ck_opportunity_stage_events_provenance",
        ),
        CheckConstraint(
            "outcome_note IS NULL OR length(outcome_note) BETWEEN 1 AND 500",
            name="ck_opportunity_stage_events_note",
        ),
        CheckConstraint(
            "(final_amount IS NULL AND final_currency IS NULL) OR "
            "(final_amount IS NOT NULL AND final_amount >= 0 AND final_currency IS NOT NULL)",
            name="ck_opportunity_stage_events_value_currency",
        ),
        CheckConstraint(
            "final_currency IS NULL OR (length(final_currency) = 3 AND final_currency = upper(final_currency))",
            name="ck_opportunity_stage_events_currency",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_opportunity_stage_events_opportunity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "from_pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_opportunity_stage_events_from_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "to_pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_opportunity_stage_events_to_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "from_pipeline_id", "from_stage_id"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_opportunity_stage_events_from_stage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "to_pipeline_id", "to_stage_id"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_opportunity_stage_events_to_stage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_opportunity_stage_events_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_opportunity_stage_events_org_id"),
        UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "idempotency_key",
            name="uq_opportunity_stage_events_idempotency",
        ),
        Index(
            "ix_opportunity_stage_events_org_opportunity",
            "organisation_id",
            "opportunity_id",
            "changed_at",
        ),
        Index(
            "ix_opportunity_stage_events_org_to_pipeline_time",
            "organisation_id",
            "to_pipeline_id",
            "changed_at",
        ),
        Index(
            "ix_opportunity_stage_events_org_from_pipeline_time",
            "organisation_id",
            "from_pipeline_id",
            "changed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_pipeline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    to_pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    to_stage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_stage_name: Mapped[str | None] = mapped_column(String(100))
    to_stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    from_stage_type: Mapped[str | None] = mapped_column(String(12))
    to_stage_type: Mapped[str] = mapped_column(String(12), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    previous_stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_reason: Mapped[str | None] = mapped_column(String(40))
    outcome_note: Mapped[str | None] = mapped_column(String(500))
    outcome_provenance: Mapped[str | None] = mapped_column(String(32))
    actual_close_date: Mapped[date | None] = mapped_column(Date)
    final_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    final_currency: Mapped[str | None] = mapped_column(String(3))
    idempotency_key: Mapped[str | None] = mapped_column(String(100))


class OpportunityAuditEvent(Base):
    __tablename__ = "opportunity_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('created', 'updated', 'deleted', 'meeting_associated', 'meeting_disassociated', "
            "'stage_changed', 'closed_won', 'closed_lost', 'reopened')",
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


class OutreachPolicy(TimestampMixin, Base):
    __tablename__ = "outreach_policies"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_outreach_policies_version"),
        CheckConstraint("cooldown_hours BETWEEN 0 AND 720", name="ck_outreach_policies_cooldown"),
        CheckConstraint("max_daily_sends_user BETWEEN 1 AND 500", name="ck_outreach_policies_user_limit"),
        CheckConstraint("max_daily_sends_org BETWEEN 1 AND 2000", name="ck_outreach_policies_org_limit"),
        CheckConstraint("length(trim(offering_name)) BETWEEN 1 AND 120", name="ck_outreach_policies_offering"),
        CheckConstraint(
            "length(trim(value_proposition)) BETWEEN 1 AND 1000",
            name="ck_outreach_policies_value",
        ),
        CheckConstraint("length(trim(approved_cta)) BETWEEN 1 AND 300", name="ck_outreach_policies_cta"),
        ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_policies_configurer",
            ondelete="RESTRICT",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    provider_supplied_email_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    cooldown_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72, server_default="72")
    max_daily_sends_user: Mapped[int] = mapped_column(Integer, nullable=False, default=25, server_default="25")
    max_daily_sends_org: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    campaign_auto_send_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    require_opt_out_mechanism: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    offering_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value_proposition: Mapped[str] = mapped_column(String(1000), nullable=False)
    approved_cta: Mapped[str] = mapped_column(String(300), nullable=False)
    configured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class OutreachMessage(TimestampMixin, Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('introduction', 'request_meeting', 'share_relevant_information', 're_engage')",
            name="ck_outreach_messages_purpose",
        ),
        CheckConstraint("state IN ('draft', 'approved', 'cancelled')", name="ck_outreach_messages_state"),
        CheckConstraint("current_version > 0", name="ck_outreach_messages_version"),
        CheckConstraint(
            "approved_version IS NULL OR approved_version BETWEEN 1 AND current_version",
            name="ck_outreach_messages_approved",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_outreach_messages_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_messages_sender",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_messages_approver",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_outreach_messages_action",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_outreach_messages_org_id"),
        UniqueConstraint("organisation_id", "action_id", name="uq_outreach_messages_action"),
        Index("ix_outreach_messages_org_contact", "organisation_id", "contact_id", "created_at"),
        Index("ix_outreach_messages_org_sender", "organisation_id", "sender_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False, default=OutreachPurpose.INTRODUCTION.value)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OutreachState.DRAFT.value, server_default=OutreachState.DRAFT.value
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    approved_version: Mapped[int | None] = mapped_column(Integer)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutreachVersion(Base):
    __tablename__ = "outreach_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_outreach_versions_version"),
        CheckConstraint("length(trim(subject)) BETWEEN 1 AND 200", name="ck_outreach_versions_subject"),
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_outreach_versions_body"),
        CheckConstraint(
            "creation_type IN ('generated', 'user_edited')",
            name="ck_outreach_versions_creation",
        ),
        CheckConstraint("recipient_trust IN ('verified', 'provider_supplied')", name="ck_outreach_versions_trust"),
        CheckConstraint("length(content_fingerprint) = 64", name="ck_outreach_versions_fingerprint"),
        ForeignKeyConstraint(
            ["organisation_id", "outreach_id"],
            ["outreach_messages.organisation_id", "outreach_messages.id"],
            name="fk_outreach_versions_message",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_versions_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_outreach_versions_org_id"),
        UniqueConstraint("organisation_id", "outreach_id", "version", name="uq_outreach_versions_number"),
        Index("ix_outreach_versions_org_message", "organisation_id", "outreach_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    outreach_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sender_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient_trust: Mapped[str] = mapped_column(String(24), nullable=False)
    offering_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value_proposition: Mapped[str] = mapped_column(String(1000), nullable=False)
    approved_cta: Mapped[str] = mapped_column(String(300), nullable=False)
    personalization_plan_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict, server_default="{}"
    )
    composer_version: Mapped[str] = mapped_column(String(80), nullable=False, default="outreach_deterministic_v1")
    creation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OutreachPersonalizationSource(Base):
    __tablename__ = "outreach_personalization_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('prospect_observation', 'prospect_person_observation', 'approved_seller_context', "
            "'event_attendance', 'event_encounter')",
            name="ck_outreach_sources_type",
        ),
        CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'approved', 'seller_reported')",
            name="ck_outreach_sources_trust",
        ),
        CheckConstraint("length(trim(label)) BETWEEN 1 AND 300", name="ck_outreach_sources_label"),
        ForeignKeyConstraint(
            ["organisation_id", "outreach_version_id"],
            ["outreach_versions.organisation_id", "outreach_versions.id"],
            name="fk_outreach_sources_version",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_outreach_sources_org_id"),
        UniqueConstraint(
            "organisation_id", "outreach_version_id", "source_type", "source_id", name="uq_outreach_sources_ref"
        ),
        Index("ix_outreach_sources_org_version", "organisation_id", "outreach_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    outreach_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    supporting_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    trust_state: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ContactSuppression(Base):
    __tablename__ = "contact_suppressions"
    __table_args__ = (
        CheckConstraint("length(email_fingerprint) = 64", name="ck_contact_suppressions_fingerprint"),
        CheckConstraint(
            "reason IN ('manual_do_not_contact', 'recipient_opt_out', 'complaint', 'permanent_bounce')",
            name="ck_contact_suppressions_reason",
        ),
        CheckConstraint("source IN ('user', 'recipient', 'provider')", name="ck_contact_suppressions_source"),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_contact_suppressions_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_contact_suppressions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "revoked_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_contact_suppressions_revoker",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_contact_suppressions_org_id"),
        UniqueConstraint("organisation_id", "email_fingerprint", name="uq_contact_suppressions_email"),
        Index("ix_contact_suppressions_org_contact", "organisation_id", "contact_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    email_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreateUsageCounter(Base):
    __tablename__ = "create_usage_counters"
    __table_args__ = (
        CheckConstraint(
            "scope_key = 'organisation' OR scope_key LIKE 'user:%'",
            name="ck_create_usage_scope",
        ),
        CheckConstraint("generation_count >= 0", name="ck_create_usage_generations"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CreateValueModel(TimestampMixin, Base):
    __tablename__ = "create_value_models"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="ck_create_value_models_name"),
        CheckConstraint("length(trim(description)) BETWEEN 1 AND 800", name="ck_create_value_models_description"),
        CheckConstraint("state IN ('active', 'archived')", name="ck_create_value_models_state"),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_models_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_value_models_org_id"),
        UniqueConstraint("organisation_id", "name", name="uq_create_value_models_org_name"),
        UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_value_models_idempotency"
        ),
        Index("ix_create_value_models_org_state", "organisation_id", "state", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(800), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreateValueModelVersion(Base):
    __tablename__ = "create_value_model_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_create_value_model_versions_number"),
        CheckConstraint("state IN ('draft', 'approved', 'archived')", name="ck_create_value_model_versions_state"),
        CheckConstraint("formula_engine_version = 'bounded_decimal_v1'", name="ck_create_value_model_versions_engine"),
        CheckConstraint("length(fingerprint) = 64", name="ck_create_value_model_versions_fingerprint"),
        ForeignKeyConstraint(
            ["organisation_id", "model_id"],
            ["create_value_models.organisation_id", "create_value_models.id"],
            name="fk_create_value_model_versions_model",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_model_versions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_model_versions_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_value_model_versions_org_id"),
        UniqueConstraint("organisation_id", "id", "model_id", name="uq_create_value_model_versions_org_id_model"),
        UniqueConstraint("organisation_id", "model_id", "version", name="uq_create_value_model_versions_number"),
        UniqueConstraint(
            "organisation_id", "model_id", "idempotency_key", name="uq_create_value_model_versions_idempotency"
        ),
        Index(
            "ix_create_value_model_versions_org_model",
            "organisation_id",
            "model_id",
            "version",
        ),
        Index(
            "ix_create_value_model_versions_org_state",
            "organisation_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    definition_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    canonical_ast_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    formula_engine_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="bounded_decimal_v1", server_default="bounded_decimal_v1"
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreateBusinessCase(TimestampMixin, Base):
    __tablename__ = "create_business_cases"
    __table_args__ = (
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_business_cases_title"),
        CheckConstraint(
            "state IN ('draft', 'calculated', 'needs_review', 'approved', 'archived')",
            name="ck_create_business_cases_state",
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_create_business_cases_currency"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "account_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_create_business_cases_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_create_business_cases_opportunity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "model_id"],
            ["create_value_models.organisation_id", "create_value_models.id"],
            name="fk_create_business_cases_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "model_version_id", "model_id"],
            [
                "create_value_model_versions.organisation_id",
                "create_value_model_versions.id",
                "create_value_model_versions.model_id",
            ],
            name="fk_create_business_cases_model_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_cases_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_business_cases_org_id"),
        UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_business_cases_idempotency"
        ),
        Index("ix_create_business_cases_org_account", "organisation_id", "account_id", "updated_at"),
        Index(
            "ix_create_business_cases_org_opportunity",
            "organisation_id",
            "opportunity_id",
            "updated_at",
        ),
        Index("ix_create_business_cases_org_state", "organisation_id", "state", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreateBusinessCaseVersion(Base):
    __tablename__ = "create_business_case_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_create_business_case_versions_number"),
        CheckConstraint(
            "review_state IN ('pending', 'approved', 'needs_review')",
            name="ck_create_business_case_versions_review",
        ),
        CheckConstraint(
            "formula_engine_version = 'bounded_decimal_v1'", name="ck_create_business_case_versions_engine"
        ),
        CheckConstraint("length(model_fingerprint) = 64", name="ck_create_business_case_versions_model_hash"),
        CheckConstraint(
            "length(calculation_fingerprint) = 64", name="ck_create_business_case_versions_calculation_hash"
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_create_business_case_versions_currency"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "case_id"],
            ["create_business_cases.organisation_id", "create_business_cases.id"],
            name="fk_create_business_case_versions_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "model_version_id", "model_id"],
            [
                "create_value_model_versions.organisation_id",
                "create_value_model_versions.id",
                "create_value_model_versions.model_id",
            ],
            name="fk_create_business_case_versions_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_case_versions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_case_versions_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_business_case_versions_org_id"),
        UniqueConstraint(
            "organisation_id",
            "id",
            "case_id",
            name="uq_create_business_case_versions_org_id_case",
        ),
        UniqueConstraint("organisation_id", "case_id", "version", name="uq_create_business_case_versions_number"),
        UniqueConstraint(
            "organisation_id", "case_id", "idempotency_key", name="uq_create_business_case_versions_idempotency"
        ),
        Index(
            "ix_create_business_case_versions_org_case",
            "organisation_id",
            "case_id",
            "version",
        ),
        Index(
            "ix_create_business_case_versions_org_model",
            "organisation_id",
            "model_version_id",
        ),
        Index(
            "ix_create_business_case_versions_org_review",
            "organisation_id",
            "review_state",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    formula_engine_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="bounded_decimal_v1", server_default="bounded_decimal_v1"
    )
    model_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    inputs_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    scenarios_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    sensitivity_json: Mapped[dict[str, object] | None] = mapped_column(JSON(none_as_null=True))
    lineage_json: Mapped[dict[str, object]] = mapped_column(JSON(none_as_null=True), nullable=False)
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreateTemplate(TimestampMixin, Base):
    __tablename__ = "create_templates"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="ck_create_templates_name"),
        CheckConstraint("state IN ('active', 'archived')", name="ck_create_templates_state"),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_templates_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_templates_org_id"),
        UniqueConstraint("organisation_id", "name", name="uq_create_templates_org_name"),
        Index("ix_create_templates_org_state", "organisation_id", "state", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreateTemplateVersion(Base):
    __tablename__ = "create_template_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_create_template_versions_number"),
        CheckConstraint(
            "processing_state IN ('processing', 'ready', 'partial', 'failed', 'archived')",
            name="ck_create_template_versions_processing",
        ),
        CheckConstraint(
            "approval_state IN ('pending', 'approved', 'revoked')",
            name="ck_create_template_versions_approval",
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 52428800", name="ck_create_template_versions_bytes"),
        CheckConstraint("length(checksum_sha256) = 64", name="ck_create_template_versions_checksum"),
        CheckConstraint("slide_count BETWEEN 0 AND 100", name="ck_create_template_versions_slides"),
        CheckConstraint("processing_schema_version = 1", name="ck_create_template_versions_schema"),
        CheckConstraint("authority_attestation_version = 1", name="ck_create_template_versions_attestation"),
        CheckConstraint("processing_attempts BETWEEN 0 AND 3", name="ck_create_template_versions_attempts"),
        CheckConstraint(
            "compatibility_state IN ('compatible', 'needs_attention', 'unsupported')",
            name="ck_create_template_versions_compatibility",
        ),
        CheckConstraint("validation_profile_version = 1", name="ck_create_template_versions_profile"),
        CheckConstraint(
            "storage_status IN ('available', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_create_template_versions_storage",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "template_id"],
            ["create_templates.organisation_id", "create_templates.id"],
            name="fk_create_template_versions_template",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "uploaded_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_uploader",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "authority_attested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_attester",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_template_versions_org_id"),
        UniqueConstraint("organisation_id", "id", "template_id", name="uq_create_template_versions_org_id_template"),
        UniqueConstraint("organisation_id", "template_id", "version", name="uq_create_template_versions_number"),
        UniqueConstraint("organisation_id", "checksum_sha256", name="uq_create_template_versions_checksum"),
        UniqueConstraint("organisation_id", "storage_key", name="uq_create_template_versions_storage"),
        Index(
            "ix_create_template_versions_org_template",
            "organisation_id",
            "template_id",
            "version",
        ),
        Index(
            "ix_create_template_versions_org_processing",
            "organisation_id",
            "processing_state",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    processing_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing", server_default="processing"
    )
    approval_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="available", server_default="available"
    )
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    width_emu: Mapped[int | None] = mapped_column(BigInteger)
    height_emu: Mapped[int | None] = mapped_column(BigInteger)
    warning_codes_json: Mapped[list[object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=list, server_default="[]"
    )
    manifest_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict, server_default="{}"
    )
    compatibility_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="needs_attention", server_default="needs_attention"
    )
    compatibility_details_json: Mapped[list[object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=list, server_default="[]"
    )
    validation_profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_failure_code: Mapped[str | None] = mapped_column(String(100))
    authority_attestation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    authority_attested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    authority_attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    worker_id: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreateTemplateSlide(TimestampMixin, Base):
    __tablename__ = "create_template_slides"
    __table_args__ = (
        CheckConstraint("slide_number BETWEEN 1 AND 100", name="ck_create_template_slides_number"),
        CheckConstraint(
            "category IN ('title', 'agenda', 'company_overview', 'problem', 'solution', 'product', "
            "'capability', 'architecture', 'case_study', 'proof_point', 'process', 'pricing_placeholder', "
            "'next_steps', 'appendix', 'unknown')",
            name="ck_create_template_slides_category",
        ),
        CheckConstraint("reuse_state IN ('pending', 'approved', 'excluded')", name="ck_create_template_slides_reuse"),
        CheckConstraint(
            "modification_policy IN ('locked', 'text_placeholders_only', 'editable_text', 'reuse_as_is')",
            name="ck_create_template_slides_modification",
        ),
        CheckConstraint(
            "NOT required OR (reuse_state = 'approved' AND customer_safe)", name="ck_create_template_slides_required"
        ),
        CheckConstraint(
            "NOT exact_text_required OR modification_policy IN ('locked', 'reuse_as_is')",
            name="ck_create_template_slides_exact",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_template_slides_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_slides_reviewer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_template_slides_org_id"),
        UniqueConstraint(
            "organisation_id", "template_version_id", "slide_number", name="uq_create_template_slides_number"
        ),
        Index(
            "ix_create_template_slides_org_version",
            "organisation_id",
            "template_version_id",
            "slide_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    slide_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    reuse_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    modification_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="reuse_as_is", server_default="reuse_as_is"
    )
    customer_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    exact_text_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    approved_description: Mapped[str | None] = mapped_column(String(400))
    text_blocks_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    placeholder_mappings_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict, server_default="{}"
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreateApprovedContentItem(Base):
    __tablename__ = "create_approved_content_items"
    __table_args__ = (
        CheckConstraint("status IN ('approved', 'revoked')", name="ck_create_content_items_status"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_content_items_title"),
        CheckConstraint("length(trim(approved_text)) BETWEEN 1 AND 12000", name="ck_create_content_items_text"),
        ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_content_items_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "slide_id"],
            ["create_template_slides.organisation_id", "create_template_slides.id"],
            name="fk_create_content_items_slide",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_content_items_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_content_items_org_id"),
        UniqueConstraint("organisation_id", "slide_id", name="uq_create_content_items_slide"),
        Index(
            "ix_create_content_items_org_version",
            "organisation_id",
            "template_version_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    slide_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    approved_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved", server_default="approved")
    modification_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_safe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_text_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreatePresentation(TimestampMixin, Base):
    __tablename__ = "create_presentations"
    __table_args__ = (
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_presentations_title"),
        CheckConstraint(
            "objective IN ('introductory_meeting', 'discovery_follow_up', 'solution_overview', "
            "'technical_workshop', 'executive_presentation', 'proposal_presentation', 'business_case', "
            "'event_follow_up')",
            name="ck_create_presentations_objective",
        ),
        CheckConstraint(
            "state IN ('draft_plan', 'generating', 'needs_review', 'ready', 'failed', 'archived')",
            name="ck_create_presentations_state",
        ),
        CheckConstraint("review_state IN ('pending', 'approved')", name="ck_create_presentations_review"),
        CheckConstraint(
            "(business_case_id IS NULL AND business_case_version_id IS NULL AND business_case_scenario IS NULL) "
            "OR (business_case_id IS NOT NULL AND business_case_version_id IS NOT NULL "
            "AND business_case_scenario IN ('base', 'all'))",
            name="ck_create_presentations_business_case_selection",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "account_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_create_presentations_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_create_presentations_opportunity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_presentations_template_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "business_case_id"],
            ["create_business_cases.organisation_id", "create_business_cases.id"],
            name="fk_create_presentations_business_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "business_case_version_id", "business_case_id"],
            [
                "create_business_case_versions.organisation_id",
                "create_business_case_versions.id",
                "create_business_case_versions.case_id",
            ],
            name="fk_create_presentations_business_case_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentations_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_presentations_org_id"),
        UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_presentations_idempotency"
        ),
        Index("ix_create_presentations_org_created", "organisation_id", "created_at"),
        Index("ix_create_presentations_org_account", "organisation_id", "account_id", "updated_at"),
        Index("ix_create_presentations_org_opportunity", "organisation_id", "opportunity_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    business_case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    business_case_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    business_case_scenario: Mapped[str | None] = mapped_column(String(12))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    objective: Mapped[str] = mapped_column(String(40), nullable=False)
    audience_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    focus_instruction: Mapped[str | None] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="draft_plan", server_default="draft_plan")
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    plan_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    source_context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreatePresentationVersion(Base):
    __tablename__ = "create_presentation_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_create_presentation_versions_number"),
        CheckConstraint(
            "state IN ('generating', 'needs_review', 'ready', 'failed')",
            name="ck_create_presentation_versions_state",
        ),
        CheckConstraint("review_state IN ('pending', 'approved')", name="ck_create_presentation_versions_review"),
        CheckConstraint("renderer_version = 'deterministic_pptx_v1'", name="ck_create_presentation_versions_renderer"),
        CheckConstraint("generation_schema_version = 1", name="ck_create_presentation_versions_schema"),
        CheckConstraint(
            "validation_profile_version IS NULL OR validation_profile_version = 1",
            name="ck_create_presentation_versions_profile",
        ),
        CheckConstraint("processing_attempts BETWEEN 0 AND 3", name="ck_create_presentation_versions_attempts"),
        CheckConstraint(
            "storage_status IN ('pending', 'available', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_create_presentation_versions_storage",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "presentation_id"],
            ["create_presentations.organisation_id", "create_presentations.id"],
            name="fk_create_presentation_versions_presentation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_presentation_versions_template",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentation_versions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentation_versions_approver",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_presentation_versions_org_id"),
        UniqueConstraint(
            "organisation_id", "presentation_id", "version", name="uq_create_presentation_versions_number"
        ),
        UniqueConstraint(
            "organisation_id", "presentation_id", "idempotency_key", name="uq_create_presentation_versions_key"
        ),
        UniqueConstraint("organisation_id", "pptx_storage_key", name="uq_create_presentation_versions_storage"),
        Index(
            "ix_create_presentation_versions_org_presentation",
            "organisation_id",
            "presentation_id",
            "version",
        ),
        Index(
            "ix_create_presentation_versions_org_state",
            "organisation_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="generating", server_default="generating")
    review_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    plan_snapshot_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    audience_snapshot_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    source_context_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict, server_default="{}"
    )
    source_context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_content_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    claim_manifest_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    warning_codes_json: Mapped[list[object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=list, server_default="[]"
    )
    renderer_version: Mapped[str] = mapped_column(
        String(60), nullable=False, default="deterministic_pptx_v1", server_default="deterministic_pptx_v1"
    )
    generation_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    worker_id: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pptx_storage_key: Mapped[str | None] = mapped_column(String(255))
    storage_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    validation_profile_version: Mapped[int | None] = mapped_column(Integer)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_failure_code: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreateDownloadGrant(Base):
    __tablename__ = "create_download_grants"
    __table_args__ = (
        CheckConstraint(
            "length(token_hash) = 64 AND token_hash = lower(token_hash)",
            name="ck_create_download_grants_token_hash",
        ),
        CheckConstraint(
            "length(approval_fingerprint) = 64 AND approval_fingerprint = lower(approval_fingerprint)",
            name="ck_create_download_grants_approval_fingerprint",
        ),
        CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="ck_create_download_grants_consumed"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_create_download_grants_revoked"),
        CheckConstraint("expires_at > created_at", name="ck_create_download_grants_expiry"),
        ForeignKeyConstraint(
            ["organisation_id", "presentation_version_id"],
            ["create_presentation_versions.organisation_id", "create_presentation_versions.id"],
            name="fk_create_download_grants_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_download_grants_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_create_download_grants_org_id"),
        UniqueConstraint("token_hash", name="uq_create_download_grants_token_hash"),
        Index(
            "ix_create_download_grants_org_expiry",
            "organisation_id",
            "expires_at",
        ),
        Index(
            "ix_create_download_grants_org_version",
            "organisation_id",
            "presentation_version_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    presentation_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SalesEvent(TimestampMixin, Base):
    __tablename__ = "sales_events"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_sales_events_name"),
        CheckConstraint(
            "event_type IN ('conference', 'trade_show', 'networking_event', 'customer_event', "
            "'partner_event', 'industry_event', 'executive_roundtable', 'internal_hosted_event', "
            "'other_business_event')",
            name="ck_sales_events_type",
        ),
        CheckConstraint(
            "state IN ('draft', 'upcoming', 'active', 'completed', 'archived')",
            name="ck_sales_events_state",
        ),
        CheckConstraint(
            "goal_type IS NULL OR goal_type IN ('meet_new_prospects', 'progress_active_opportunities', "
            "'meet_strategic_accounts', 'reconnect_existing_contacts', 'find_partners', 'other')",
            name="ck_sales_events_goal",
        ),
        CheckConstraint("end_at >= start_at", name="ck_sales_events_range"),
        CheckConstraint("length(trim(timezone)) BETWEEN 1 AND 64", name="ck_sales_events_timezone"),
        CheckConstraint("description IS NULL OR length(description) <= 1000", name="ck_sales_events_description"),
        CheckConstraint("goal_detail IS NULL OR length(goal_detail) <= 300", name="ck_sales_events_goal_detail"),
        CheckConstraint("source_type = 'manual'", name="ck_sales_events_source"),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_events_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_events_org_id"),
        Index("ix_sales_events_org_time", "organisation_id", "start_at", "end_at"),
        Index("ix_sales_events_org_state", "organisation_id", "state", "start_at"),
        Index("ix_sales_events_org_owner", "organisation_id", "owner_user_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, default=EventType.CONFERENCE.value)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(100))
    event_url: Mapped[str | None] = mapped_column(String(1000))
    organiser: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(1000))
    goal_type: Mapped[str | None] = mapped_column(String(40))
    goal_detail: Mapped[str | None] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EventState.UPCOMING.value, server_default=EventState.UPCOMING.value
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventAttendeeImport(TimestampMixin, Base):
    __tablename__ = "event_attendee_imports"
    __table_args__ = (
        CheckConstraint("state IN ('previewed', 'confirmed', 'expired', 'failed')", name="ck_event_imports_state"),
        CheckConstraint("length(file_fingerprint) = 64", name="ck_event_imports_fingerprint"),
        CheckConstraint("row_count BETWEEN 0 AND 500", name="ck_event_imports_rows"),
        CheckConstraint("valid_row_count BETWEEN 0 AND 500", name="ck_event_imports_valid_rows"),
        CheckConstraint("imported_row_count BETWEEN 0 AND 500", name="ck_event_imports_imported_rows"),
        CheckConstraint("attestation_version IS NULL OR attestation_version = 1", name="ck_event_imports_attestation"),
        ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_imports_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_imports_requester",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "attested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_imports_attester",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_event_imports_org_id"),
        UniqueConstraint("organisation_id", "event_id", "id", name="uq_event_imports_org_event_id"),
        UniqueConstraint("organisation_id", "event_id", "file_fingerprint", name="uq_event_imports_org_event_file"),
        Index("ix_event_imports_org_event", "organisation_id", "event_id", "created_at"),
        Index("ix_event_imports_org_expiry", "organisation_id", "state", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="previewed", server_default="previewed")
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    valid_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    imported_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    column_mapping_json: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=dict
    )
    recognised_columns_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    ignored_columns_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    issues_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    preview_rows_json: Mapped[list[object]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attestation_version: Mapped[int | None] = mapped_column(Integer)
    attested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventAttendee(TimestampMixin, Base):
    __tablename__ = "event_attendees"
    __table_args__ = (
        CheckConstraint(
            "COALESCE(length(trim(normalised_business_email)), 0) > 0 OR "
            "(COALESCE(length(trim(first_name)), 0) > 0 AND COALESCE(length(trim(company_name)), 0) > 0)",
            name="ck_event_attendees_identity",
        ),
        CheckConstraint("source_type = 'event_list'", name="ck_event_attendees_source"),
        CheckConstraint("email_trust_state IN ('provider_supplied', 'unknown')", name="ck_event_attendees_email_trust"),
        CheckConstraint(
            "match_state IN ('matched_contact', 'matched_prospect_person', 'matched_company', "
            "'possible_match', 'unmatched')",
            name="ck_event_attendees_match",
        ),
        CheckConstraint(
            "priority_state IN ('priority_to_meet', 'worth_meeting', 'context_only', 'needs_more_information')",
            name="ck_event_attendees_priority",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_attendees_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "event_id", "import_id"],
            ["event_attendee_imports.organisation_id", "event_attendee_imports.event_id", "event_attendee_imports.id"],
            name="fk_event_attendees_import",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_event_attendees_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_event_attendees_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "prospect_person_id"],
            ["prospect_people.organisation_id", "prospect_people.id"],
            name="fk_event_attendees_person",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "active_opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_event_attendees_opportunity",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_event_attendees_org_id"),
        UniqueConstraint("organisation_id", "event_id", "id", name="uq_event_attendees_org_event_id"),
        UniqueConstraint(
            "organisation_id", "event_id", "normalised_business_email", name="uq_event_attendees_org_event_email"
        ),
        UniqueConstraint(
            "organisation_id", "event_id", "normalised_profile_url", name="uq_event_attendees_org_event_profile"
        ),
        UniqueConstraint(
            "organisation_id", "event_id", "import_id", "source_row", name="uq_event_attendees_import_row"
        ),
        Index("ix_event_attendees_org_event_name", "organisation_id", "event_id", "last_name", "first_name"),
        Index("ix_event_attendees_org_event_company", "organisation_id", "event_id", "company_name"),
        Index("ix_event_attendees_org_event_priority", "organisation_id", "event_id", "priority_state"),
        Index("ix_event_attendees_org_contact", "organisation_id", "contact_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    business_email: Mapped[str | None] = mapped_column(String(320))
    normalised_business_email: Mapped[str | None] = mapped_column(String(320))
    country_or_location: Mapped[str | None] = mapped_column(String(200))
    profile_url: Mapped[str | None] = mapped_column(String(1000))
    normalised_profile_url: Mapped[str | None] = mapped_column(String(1000))
    company_domain: Mapped[str | None] = mapped_column(String(253))
    registration_category: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="event_list", server_default="event_list"
    )
    email_trust_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unknown", server_default="unknown"
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    prospect_person_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    match_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EventAttendeeMatchState.UNMATCHED.value,
        server_default=EventAttendeeMatchState.UNMATCHED.value,
    )
    priority_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EventAttendeePriority.NEEDS_MORE_INFORMATION.value,
        server_default=EventAttendeePriority.NEEDS_MORE_INFORMATION.value,
    )
    priority_reasons_json: Mapped[list[object]] = mapped_column(
        JSON(none_as_null=True), nullable=False, default=list, server_default="[]"
    )
    active_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))


class EventAttendeeUserState(TimestampMixin, Base):
    __tablename__ = "event_attendee_user_states"
    __table_args__ = (
        CheckConstraint(
            "plan_state IN ('not_planned', 'planned', 'met', 'follow_up', 'complete', 'not_relevant')",
            name="ck_event_user_states_plan",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_user_states_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "event_id", "attendee_id"],
            ["event_attendees.organisation_id", "event_attendees.event_id", "event_attendees.id"],
            name="fk_event_user_states_attendee",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_user_states_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_event_user_states_org_id"),
        UniqueConstraint("organisation_id", "event_id", "attendee_id", "user_id", name="uq_event_user_states_person"),
        Index("ix_event_user_states_org_event_user", "organisation_id", "event_id", "user_id", "plan_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendee_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    plan_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default=EventPlanState.NOT_PLANNED.value, server_default="not_planned"
    )
    meeting_arranged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class EventEncounter(TimestampMixin, Base):
    __tablename__ = "event_encounters"
    __table_args__ = (
        CheckConstraint("state IN ('met', 'follow_up', 'complete')", name="ck_event_encounters_state"),
        CheckConstraint("seller_note IS NULL OR length(seller_note) <= 1000", name="ck_event_encounters_note"),
        CheckConstraint("note_origin = 'seller_reported_activity'", name="ck_event_encounters_origin"),
        ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_encounters_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "event_id", "attendee_id"],
            ["event_attendees.organisation_id", "event_attendees.event_id", "event_attendees.id"],
            name="fk_event_encounters_attendee",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_encounters_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_event_encounters_interaction",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_event_encounters_org_id"),
        UniqueConstraint("organisation_id", "event_id", "attendee_id", "user_id", name="uq_event_encounters_person"),
        Index("ix_event_encounters_org_event_user", "organisation_id", "event_id", "user_id", "occurred_at"),
        Index("ix_event_encounters_org_interaction", "organisation_id", "interaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendee_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="met", server_default="met")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seller_note: Mapped[str | None] = mapped_column(String(1000))
    note_origin: Mapped[str] = mapped_column(
        String(32), nullable=False, default="seller_reported_activity", server_default="seller_reported_activity"
    )
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))


class EventCampaignLink(Base):
    __tablename__ = "event_campaign_links"
    __table_args__ = (
        CheckConstraint("stage IN ('pre_event', 'post_event')", name="ck_event_campaign_links_stage"),
        ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_campaign_links_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_event_campaign_links_campaign",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_campaign_links_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_event_campaign_links_org_id"),
        UniqueConstraint("organisation_id", "event_id", "campaign_id", name="uq_event_campaign_links_pair"),
        Index("ix_event_campaign_links_org_event", "organisation_id", "event_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EngageCampaign(TimestampMixin, Base):
    __tablename__ = "engage_campaigns"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'ready', 'active', 'paused', 'completed', 'stopped', 'needs_attention')",
            name="ck_engage_campaigns_state",
        ),
        CheckConstraint("current_version > 0", name="ck_engage_campaigns_version"),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaigns_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_campaigns_org_id"),
        Index("ix_engage_campaigns_org_owner_state", "organisation_id", "owner_user_id", "state", "updated_at"),
        Index("ix_engage_campaigns_org_state", "organisation_id", "state", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default=CampaignState.DRAFT.value, server_default=CampaignState.DRAFT.value
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    needs_attention_reason: Mapped[str | None] = mapped_column(String(64))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EngageCampaignVersion(Base):
    __tablename__ = "engage_campaign_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_engage_campaign_versions_number"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_engage_campaign_versions_status"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_engage_campaign_versions_name"),
        CheckConstraint("length(trim(purpose)) BETWEEN 1 AND 300", name="ck_engage_campaign_versions_purpose"),
        CheckConstraint(
            "approval_mode IN ('review_each_send', 'approved_campaign_auto_send')",
            name="ck_engage_campaign_versions_approval",
        ),
        CheckConstraint(
            "source_type IN ('manual_contacts', 'target_market', 'event_attendees')",
            name="ck_engage_campaign_versions_source",
        ),
        CheckConstraint(
            "send_window_start_minutes BETWEEN 0 AND 1438 AND "
            "send_window_end_minutes BETWEEN 1 AND 1439 AND "
            "send_window_start_minutes < send_window_end_minutes",
            name="ck_engage_campaign_versions_window",
        ),
        CheckConstraint("audience_count BETWEEN 0 AND 50", name="ck_engage_campaign_versions_audience"),
        CheckConstraint(
            "policy_fingerprint IS NULL OR length(policy_fingerprint) = 64",
            name="ck_engage_campaign_versions_policy_fp",
        ),
        CheckConstraint(
            "launch_fingerprint IS NULL OR length(launch_fingerprint) = 64",
            name="ck_engage_campaign_versions_launch_fp",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_engage_campaign_versions_campaign",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_sender",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_approver",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_versions_org_id"),
        UniqueConstraint("organisation_id", "campaign_id", "version", name="uq_engage_campaign_versions_number"),
        UniqueConstraint("organisation_id", "campaign_id", "id", name="uq_engage_campaign_versions_campaign_id"),
        Index("ix_engage_campaign_versions_org_campaign", "organisation_id", "campaign_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    approval_mode: Mapped[str] = mapped_column(
        String(40), nullable=False, default=CampaignApprovalMode.REVIEW_EACH_SEND.value
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_contacts")
    sender_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    send_days_json: Mapped[list[int]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    send_window_start_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=510, server_default="510")
    send_window_end_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1020, server_default="1020")
    stop_on_active_opportunity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    policy_version: Mapped[int | None] = mapped_column(Integer)
    policy_fingerprint: Mapped[str | None] = mapped_column(String(64))
    launch_fingerprint: Mapped[str | None] = mapped_column(String(64))
    audience_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_send_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EngageSequenceStep(Base):
    __tablename__ = "engage_sequence_steps"
    __table_args__ = (
        CheckConstraint("step_order BETWEEN 1 AND 4", name="ck_engage_sequence_steps_order"),
        CheckConstraint("delay_days BETWEEN 0 AND 30", name="ck_engage_sequence_steps_delay"),
        CheckConstraint(
            "objective IN ('introduction', 'follow_up', 'share_relevant_information', 'different_angle', "
            "'meeting_request', 'final_follow_up')",
            name="ck_engage_sequence_steps_objective",
        ),
        CheckConstraint(
            "content_strategy IN ('source_backed_value', 'truthful_follow_up', 'source_backed_new_angle', "
            "'respectful_close')",
            name="ck_engage_sequence_steps_strategy",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_version_id"],
            ["engage_campaign_versions.organisation_id", "engage_campaign_versions.id"],
            name="fk_engage_sequence_steps_version",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_sequence_steps_org_id"),
        UniqueConstraint("organisation_id", "campaign_version_id", "step_order", name="uq_engage_sequence_steps_order"),
        Index("ix_engage_sequence_steps_org_version", "organisation_id", "campaign_version_id", "step_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    campaign_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False)
    objective: Mapped[str] = mapped_column(String(40), nullable=False)
    content_strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EngageCampaignAudience(Base):
    __tablename__ = "engage_campaign_audience"
    __table_args__ = (
        CheckConstraint(
            "recipient_trust IN ('verified', 'provider_supplied', 'unknown')",
            name="ck_engage_campaign_audience_trust",
        ),
        CheckConstraint("length(trim(eligibility_code)) BETWEEN 1 AND 64", name="ck_engage_campaign_audience_code"),
        CheckConstraint(
            "length(trim(eligibility_reason)) BETWEEN 1 AND 300", name="ck_engage_campaign_audience_reason"
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_version_id"],
            ["engage_campaign_versions.organisation_id", "engage_campaign_versions.id"],
            name="fk_engage_campaign_audience_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_engage_campaign_audience_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_engage_campaign_audience_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_audience_org_id"),
        UniqueConstraint(
            "organisation_id", "campaign_version_id", "contact_id", name="uq_engage_campaign_audience_contact"
        ),
        Index(
            "ix_engage_campaign_audience_org_version",
            "organisation_id",
            "campaign_version_id",
            "eligible",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    campaign_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    recipient_trust: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    eligibility_code: Mapped[str] = mapped_column(String(64), nullable=False)
    eligibility_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EngageCampaignEnrollment(TimestampMixin, Base):
    __tablename__ = "engage_campaign_enrollments"
    __table_args__ = (
        CheckConstraint(
            "state IN ('ready', 'active', 'paused', 'stopped', 'completed', 'blocked', 'needs_attention')",
            name="ck_engage_campaign_enrollments_state",
        ),
        CheckConstraint("current_step_order BETWEEN 1 AND 4", name="ck_engage_campaign_enrollments_step"),
        CheckConstraint(
            "recipient_trust IN ('verified', 'provider_supplied')",
            name="ck_engage_campaign_enrollments_trust",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('replied', 'meeting_booked', 'not_interested')",
            name="ck_engage_campaign_enrollments_outcome",
        ),
        CheckConstraint(
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
            name="ck_engage_campaign_enrollments_provenance",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_engage_campaign_enrollments_campaign",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "campaign_id", "campaign_version_id"],
            [
                "engage_campaign_versions.organisation_id",
                "engage_campaign_versions.campaign_id",
                "engage_campaign_versions.id",
            ],
            name="fk_engage_campaign_enrollments_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_engage_campaign_enrollments_contact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_engage_campaign_enrollments_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_sender",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "outcome_reported_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_outcome_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_enrollments_org_id"),
        UniqueConstraint("organisation_id", "campaign_id", "contact_id", name="uq_engage_campaign_enrollments_contact"),
        Index(
            "ix_engage_campaign_enrollments_org_campaign",
            "organisation_id",
            "campaign_id",
            "state",
            "next_scheduled_at",
        ),
        Index("ix_engage_campaign_enrollments_org_contact", "organisation_id", "contact_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    campaign_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient_trust: Mapped[str] = mapped_column(String(24), nullable=False)
    job_title_snapshot: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CampaignEnrollmentState.READY.value,
        server_default=CampaignEnrollmentState.READY.value,
    )
    current_step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    next_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str | None] = mapped_column(String(32))
    outcome_provenance: Mapped[str | None] = mapped_column(String(24))
    outcome_reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    outcome_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_source_ids_json: Mapped[list[str]] = mapped_column(JSON(none_as_null=True), nullable=False, default=list)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class EngageEnrollmentStep(TimestampMixin, Base):
    __tablename__ = "engage_enrollment_steps"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'processing', 'ready_for_review', 'prepared', 'queued', 'sent', "
            "'deferred', 'blocked', 'cancelled', 'unknown_delivery_state')",
            name="ck_engage_enrollment_steps_state",
        ),
        CheckConstraint("attempt_count BETWEEN 0 AND 20", name="ck_engage_enrollment_steps_attempts"),
        ForeignKeyConstraint(
            ["organisation_id", "enrollment_id"],
            ["engage_campaign_enrollments.organisation_id", "engage_campaign_enrollments.id"],
            name="fk_engage_enrollment_steps_enrollment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "sequence_step_id"],
            ["engage_sequence_steps.organisation_id", "engage_sequence_steps.id"],
            name="fk_engage_enrollment_steps_sequence",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "outreach_message_id"],
            ["outreach_messages.organisation_id", "outreach_messages.id"],
            name="fk_engage_enrollment_steps_outreach",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_engage_enrollment_steps_org_id"),
        UniqueConstraint(
            "organisation_id", "enrollment_id", "sequence_step_id", name="uq_engage_enrollment_steps_sequence"
        ),
        UniqueConstraint("organisation_id", "outreach_message_id", name="uq_engage_enrollment_steps_outreach"),
        Index("ix_engage_enrollment_steps_due", "organisation_id", "state", "prepare_at", "scheduled_at"),
        Index("ix_engage_enrollment_steps_lease", "organisation_id", "state", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence_step_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prepare_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CampaignStepState.PENDING.value,
        server_default=CampaignStepState.PENDING.value,
    )
    outreach_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    safe_status_code: Mapped[str | None] = mapped_column(String(64))
    worker_id: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionProposal(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('follow_up_email', 'personalized_outreach', 'send_requested_material', 'create_task', "
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
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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


class OrganisationCRMSetting(TimestampMixin, Base):
    __tablename__ = "organisation_crm_settings"
    __table_args__ = (
        CheckConstraint("mode IN ('native', 'external')", name="ck_organisation_crm_settings_mode"),
        CheckConstraint(
            "(mode = 'native' AND external_provider IS NULL) OR (mode = 'external' AND external_provider = 'hubspot')",
            name="ck_organisation_crm_settings_provider",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_organisation_crm_settings_configurer",
            ondelete="RESTRICT",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    external_provider: Mapped[str | None] = mapped_column(String(40))
    configured_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    configured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CRMCustomFieldDefinition(TimestampMixin, Base):
    __tablename__ = "crm_custom_field_definitions"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_custom_fields_entity_type",
        ),
        CheckConstraint(
            "field_type IN ('short_text', 'number', 'date', 'boolean', 'single_select', 'url')",
            name="ck_crm_custom_fields_field_type",
        ),
        CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 64", name="ck_crm_custom_fields_key"),
        CheckConstraint("length(trim(label)) BETWEEN 1 AND 100", name="ck_crm_custom_fields_label"),
        CheckConstraint("display_order BETWEEN 0 AND 24", name="ck_crm_custom_fields_order"),
        CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_crm_custom_fields_archive",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_custom_fields_creator",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_custom_fields_org_id"),
        UniqueConstraint("organisation_id", "entity_type", "field_key", name="uq_crm_custom_fields_org_entity_key"),
        Index(
            "ix_crm_custom_fields_org_entity",
            "organisation_id",
            "entity_type",
            "active",
            "display_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(24), nullable=False)
    options_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CRMCustomFieldValue(TimestampMixin, Base):
    __tablename__ = "crm_custom_field_values"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_custom_values_entity_type",
        ),
        CheckConstraint(
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'record_merge', 'system')",
            name="ck_crm_custom_values_source",
        ),
        CheckConstraint(
            "(CASE WHEN text_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN number_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN date_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN boolean_value IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_crm_custom_values_one_typed_value",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["crm_custom_field_definitions.organisation_id", "crm_custom_field_definitions.id"],
            name="fk_crm_custom_values_definition",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_custom_values_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_custom_values_org_id"),
        UniqueConstraint(
            "organisation_id",
            "definition_id",
            "entity_type",
            "entity_id",
            name="uq_crm_custom_values_record_field",
        ),
        Index("ix_crm_custom_values_org_record", "organisation_id", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    text_value: Mapped[str | None] = mapped_column(String(2048))
    number_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    date_value: Mapped[date | None] = mapped_column(Date)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_user_entry")
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class CRMRecordChange(Base):
    __tablename__ = "crm_record_changes"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_record_changes_entity_type",
        ),
        CheckConstraint(
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'record_merge', 'system')",
            name="ck_crm_record_changes_source",
        ),
        CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 80", name="ck_crm_record_changes_field"),
        ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_record_changes_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_record_changes_org_id"),
        Index(
            "ix_crm_record_changes_org_record",
            "organisation_id",
            "entity_type",
            "entity_id",
            "changed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value_json: Mapped[object | None] = mapped_column(JSON(none_as_null=True))
    new_value_json: Mapped[object | None] = mapped_column(JSON(none_as_null=True))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OperatorProvisioningEvent(Base):
    __tablename__ = "operator_provisioning_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('organisation_provisioned', 'member_provisioned')",
            name="ck_operator_provisioning_events_action",
        ),
        CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash = lower(idempotency_key_hash)",
            name="ck_operator_provisioning_events_key",
        ),
        CheckConstraint(
            "length(trim(operator_reference)) BETWEEN 1 AND 200",
            name="ck_operator_provisioning_events_operator",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_operator_provisioning_events_org_id"),
        UniqueConstraint(
            "organisation_id",
            "action",
            "idempotency_key_hash",
            name="uq_operator_provisioning_events_key",
        ),
        Index("ix_operator_provisioning_events_org_time", "organisation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    operator_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CRMImportBatch(TimestampMixin, Base):
    __tablename__ = "crm_import_batches"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_import_batches_entity_type",
        ),
        CheckConstraint(
            "state IN ('previewed', 'confirmed', 'expired', 'failed')",
            name="ck_crm_import_batches_state",
        ),
        CheckConstraint(
            "length(file_fingerprint) = 64 AND file_fingerprint = lower(file_fingerprint)",
            name="ck_crm_import_batches_file_hash",
        ),
        CheckConstraint(
            "length(mapping_fingerprint) = 64 AND mapping_fingerprint = lower(mapping_fingerprint)",
            name="ck_crm_import_batches_mapping_hash",
        ),
        CheckConstraint(
            "row_count BETWEEN 0 AND 5000 AND actionable_row_count BETWEEN 0 AND row_count "
            "AND imported_row_count BETWEEN 0 AND actionable_row_count",
            name="ck_crm_import_batches_counts",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_import_batches_requester",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_import_batches_org_id"),
        UniqueConstraint(
            "organisation_id",
            "entity_type",
            "file_fingerprint",
            "mapping_fingerprint",
            name="uq_crm_import_batches_fingerprint",
        ),
        Index("ix_crm_import_batches_org_state", "organisation_id", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="previewed", server_default="previewed")
    file_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    actionable_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CRMImportRow(Base):
    __tablename__ = "crm_import_rows"
    __table_args__ = (
        CheckConstraint("source_row BETWEEN 2 AND 5001", name="ck_crm_import_rows_source_row"),
        CheckConstraint(
            "disposition IN ('new', 'matches_existing', 'possible_duplicate', 'invalid', 'imported', 'skipped')",
            name="ck_crm_import_rows_disposition",
        ),
        CheckConstraint(
            "issue_code IS NULL OR length(trim(issue_code)) BETWEEN 1 AND 80",
            name="ck_crm_import_rows_issue",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "batch_id"],
            ["crm_import_batches.organisation_id", "crm_import_batches.id"],
            name="fk_crm_import_rows_batch",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_import_rows_org_id"),
        UniqueConstraint("organisation_id", "batch_id", "source_row", name="uq_crm_import_rows_source"),
        Index("ix_crm_import_rows_org_batch", "organisation_id", "batch_id", "source_row"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(24), nullable=False)
    issue_code: Mapped[str | None] = mapped_column(String(80))
    canonical_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CRMRecordMerge(Base):
    __tablename__ = "crm_record_merges"
    __table_args__ = (
        CheckConstraint("entity_type IN ('account', 'contact')", name="ck_crm_record_merges_entity_type"),
        CheckConstraint("source_entity_id <> survivor_entity_id", name="ck_crm_record_merges_distinct"),
        CheckConstraint(
            "length(preview_fingerprint) = 64 AND preview_fingerprint = lower(preview_fingerprint)",
            name="ck_crm_record_merges_preview_hash",
        ),
        CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash = lower(idempotency_key_hash)",
            name="ck_crm_record_merges_key_hash",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "merged_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_record_merges_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_crm_record_merges_org_id"),
        UniqueConstraint(
            "organisation_id",
            "entity_type",
            "source_entity_id",
            name="uq_crm_record_merges_source",
        ),
        UniqueConstraint(
            "organisation_id",
            "entity_type",
            "idempotency_key_hash",
            name="uq_crm_record_merges_key",
        ),
        Index(
            "ix_crm_record_merges_org_survivor",
            "organisation_id",
            "entity_type",
            "survivor_entity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    survivor_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    field_selection_json: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    merged_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_interactions_event_tenant",
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
        Index("ix_interactions_organisation_event", "organisation_id", "event_id"),
        Index("ix_interactions_organisation_deleted", "organisation_id", "deleted_at"),
        Index(
            "ix_interactions_org_completed_type",
            "organisation_id",
            "actual_end_at",
            "interaction_type",
            "lifecycle_status",
        ),
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
    event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
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


class SalesTarget(TimestampMixin, Base):
    __tablename__ = "sales_targets"
    __table_args__ = (
        CheckConstraint("scope IN ('personal', 'organisation')", name="ck_sales_targets_scope"),
        CheckConstraint("origin IN ('self_set', 'admin_assigned')", name="ck_sales_targets_origin"),
        CheckConstraint("period_type IN ('month', 'quarter', 'year')", name="ck_sales_targets_period_type"),
        CheckConstraint("period_end >= period_start", name="ck_sales_targets_period_bounds"),
        CheckConstraint("length(trim(metric_id)) BETWEEN 1 AND 80", name="ck_sales_targets_metric_id"),
        CheckConstraint(
            "length(trim(metric_definition_version)) BETWEEN 1 AND 20",
            name="ck_sales_targets_metric_version",
        ),
        CheckConstraint("length(trim(timezone)) BETWEEN 1 AND 64", name="ck_sales_targets_timezone"),
        CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_sales_targets_currency",
        ),
        CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR "
            "(scope = 'organisation' AND owner_user_id IS NULL AND origin = 'admin_assigned')",
            name="ck_sales_targets_scope_owner",
        ),
        CheckConstraint(
            "origin <> 'self_set' OR (scope = 'personal' AND owner_user_id = created_by_user_id)",
            name="ck_sales_targets_self_origin",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_targets_owner_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_sales_targets_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_targets_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_targets_org_id"),
        Index("ix_sales_targets_org_owner_period", "organisation_id", "owner_user_id", "period_end"),
        Index("ix_sales_targets_org_scope_period", "organisation_id", "scope", "period_end"),
        Index(
            "uq_sales_targets_active_identity",
            "organisation_id",
            "metric_id",
            "metric_definition_version",
            "scope",
            "origin",
            text("COALESCE(owner_user_id, '00000000-0000-0000-0000-000000000000')"),
            text("COALESCE(pipeline_id, '00000000-0000-0000-0000-000000000000')"),
            "period_start",
            "period_end",
            text("COALESCE(currency, '')"),
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
            sqlite_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_id: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_definition_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    period_type: Mapped[str] = mapped_column(String(12), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalesTargetRevision(Base):
    __tablename__ = "sales_target_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="ck_sales_target_revisions_number"),
        CheckConstraint(
            "goal_value > 0 AND goal_value <= 1000000000000000",
            name="ck_sales_target_revisions_goal",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["sales_targets.organisation_id", "sales_targets.id"],
            name="fk_sales_target_revisions_target",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_target_revisions_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_target_revisions_org_id"),
        UniqueConstraint("target_id", "revision_number", name="uq_sales_target_revisions_target_number"),
        Index(
            "ix_sales_target_revisions_org_target",
            "organisation_id",
            "target_id",
            "revision_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SalesForecastPeriod(Base):
    __tablename__ = "sales_forecast_periods"
    __table_args__ = (
        CheckConstraint("period_type IN ('month', 'quarter')", name="ck_sales_forecast_periods_type"),
        CheckConstraint("period_end >= period_start", name="ck_sales_forecast_periods_bounds"),
        CheckConstraint(
            "length(trim(timezone)) BETWEEN 1 AND 64",
            name="ck_sales_forecast_periods_timezone",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_periods_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_periods_org_id"),
        UniqueConstraint(
            "organisation_id",
            "period_type",
            "period_start",
            "period_end",
            name="uq_sales_forecast_periods_identity",
        ),
        Index(
            "ix_sales_forecast_periods_org_end",
            "organisation_id",
            "period_type",
            "period_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_type: Mapped[str] = mapped_column(String(12), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SalesForecastJudgment(Base):
    __tablename__ = "sales_forecast_judgments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "period_id"],
            ["sales_forecast_periods.organisation_id", "sales_forecast_periods.id"],
            name="fk_sales_forecast_judgments_period",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_sales_forecast_judgments_opportunity",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_judgments_org_id"),
        UniqueConstraint(
            "organisation_id",
            "period_id",
            "opportunity_id",
            name="uq_sales_forecast_judgments_identity",
        ),
        Index(
            "ix_sales_forecast_judgments_org_period",
            "organisation_id",
            "period_id",
            "opportunity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SalesForecastJudgmentRevision(Base):
    __tablename__ = "sales_forecast_judgment_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="ck_sales_forecast_revisions_number"),
        CheckConstraint(
            "category IN ('commit', 'likely', 'possible', 'not_this_period')",
            name="ck_sales_forecast_revisions_category",
        ),
        CheckConstraint(
            "(amount_snapshot IS NULL AND currency_snapshot IS NULL) OR "
            "(amount_snapshot IS NOT NULL AND amount_snapshot >= 0 AND currency_snapshot IS NOT NULL)",
            name="ck_sales_forecast_revisions_value_currency",
        ),
        CheckConstraint(
            "currency_snapshot IS NULL OR "
            "(length(currency_snapshot) = 3 AND currency_snapshot = upper(currency_snapshot))",
            name="ck_sales_forecast_revisions_currency",
        ),
        CheckConstraint(
            "opportunity_status_snapshot IN ('open', 'on_hold')",
            name="ck_sales_forecast_revisions_opportunity_status",
        ),
        CheckConstraint(
            "model_status IN ('available', 'insufficient_sample', 'unavailable_stage')",
            name="ck_sales_forecast_revisions_model_status",
        ),
        CheckConstraint("model_won_count >= 0", name="ck_sales_forecast_revisions_won_count"),
        CheckConstraint("model_lost_count >= 0", name="ck_sales_forecast_revisions_lost_count"),
        CheckConstraint("model_minimum_sample >= 1", name="ck_sales_forecast_revisions_minimum_sample"),
        CheckConstraint(
            "model_lookback_end >= model_lookback_start",
            name="ck_sales_forecast_revisions_lookback",
        ),
        CheckConstraint(
            "length(trim(model_version)) BETWEEN 1 AND 80",
            name="ck_sales_forecast_revisions_model_version",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "judgment_id"],
            ["sales_forecast_judgments.organisation_id", "sales_forecast_judgments.id"],
            name="fk_sales_forecast_revisions_judgment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_revisions_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id_snapshot"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_revisions_owner_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_sales_forecast_revisions_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot", "stage_id_snapshot"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_sales_forecast_revisions_stage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_revisions_org_id"),
        UniqueConstraint(
            "judgment_id",
            "revision_number",
            name="uq_sales_forecast_revisions_judgment_number",
        ),
        Index(
            "ix_sales_forecast_revisions_org_judgment",
            "organisation_id",
            "judgment_id",
            "revision_number",
        ),
        Index(
            "ix_sales_forecast_revisions_org_created",
            "organisation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    judgment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    amount_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency_snapshot: Mapped[str | None] = mapped_column(String(3))
    expected_close_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    pipeline_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stage_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    opportunity_status_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_status: Mapped[str] = mapped_column(String(24), nullable=False)
    model_won_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_lost_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_minimum_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    model_lookback_start: Mapped[date] = mapped_column(Date, nullable=False)
    model_lookback_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SalesForecastReviewerJudgment(Base):
    __tablename__ = "sales_forecast_reviewer_judgments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "period_id"],
            ["sales_forecast_periods.organisation_id", "sales_forecast_periods.id"],
            name="fk_forecast_reviewer_judgments_period",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_forecast_reviewer_judgments_opportunity",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_forecast_reviewer_judgments_org_id"),
        UniqueConstraint(
            "organisation_id",
            "period_id",
            "opportunity_id",
            name="uq_forecast_reviewer_judgments_identity",
        ),
        Index(
            "ix_forecast_reviewer_judgments_org_period",
            "organisation_id",
            "period_id",
            "opportunity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SalesForecastReviewerRevision(Base):
    __tablename__ = "sales_forecast_reviewer_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="ck_forecast_reviewer_revisions_number"),
        CheckConstraint(
            "category IN ('commit', 'likely', 'possible', 'not_this_period')",
            name="ck_forecast_reviewer_revisions_category",
        ),
        CheckConstraint(
            "(amount_snapshot IS NULL AND currency_snapshot IS NULL) OR "
            "(amount_snapshot IS NOT NULL AND amount_snapshot >= 0 AND currency_snapshot IS NOT NULL)",
            name="ck_forecast_reviewer_revisions_value_currency",
        ),
        CheckConstraint(
            "currency_snapshot IS NULL OR "
            "(length(currency_snapshot) = 3 AND currency_snapshot = upper(currency_snapshot))",
            name="ck_forecast_reviewer_revisions_currency",
        ),
        CheckConstraint(
            "opportunity_status_snapshot IN ('open', 'on_hold')",
            name="ck_forecast_reviewer_revisions_status",
        ),
        CheckConstraint(
            "model_status IN ('available', 'insufficient_sample', 'unavailable_stage')",
            name="ck_forecast_reviewer_revisions_model_status",
        ),
        CheckConstraint("model_won_count >= 0", name="ck_forecast_reviewer_revisions_won"),
        CheckConstraint("model_lost_count >= 0", name="ck_forecast_reviewer_revisions_lost"),
        CheckConstraint("model_minimum_sample >= 1", name="ck_forecast_reviewer_revisions_sample"),
        CheckConstraint(
            "model_lookback_end >= model_lookback_start",
            name="ck_forecast_reviewer_revisions_lookback",
        ),
        CheckConstraint(
            "length(trim(model_version)) BETWEEN 1 AND 80",
            name="ck_forecast_reviewer_revisions_model_version",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "reviewer_judgment_id"],
            ["sales_forecast_reviewer_judgments.organisation_id", "sales_forecast_reviewer_judgments.id"],
            name="fk_forecast_reviewer_revisions_judgment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_forecast_reviewer_revisions_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "owner_user_id_snapshot"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_forecast_reviewer_revisions_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_forecast_reviewer_revisions_pipeline",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot", "stage_id_snapshot"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_forecast_reviewer_revisions_stage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "id", name="uq_forecast_reviewer_revisions_org_id"),
        UniqueConstraint(
            "reviewer_judgment_id",
            "revision_number",
            name="uq_forecast_reviewer_revisions_number",
        ),
        Index(
            "ix_forecast_reviewer_revisions_org_judgment",
            "organisation_id",
            "reviewer_judgment_id",
            "revision_number",
        ),
        Index(
            "ix_forecast_reviewer_revisions_org_created",
            "organisation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_judgment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    amount_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency_snapshot: Mapped[str | None] = mapped_column(String(3))
    expected_close_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    pipeline_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stage_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    opportunity_status_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_status: Mapped[str] = mapped_column(String(24), nullable=False)
    model_won_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_lost_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_minimum_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    model_lookback_start: Mapped[date] = mapped_column(Date, nullable=False)
    model_lookback_end: Mapped[date] = mapped_column(Date, nullable=False)
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
