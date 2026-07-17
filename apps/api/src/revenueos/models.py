from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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

from revenueos.domain import CompanyStatus, OpportunityStage, TaskPriority, TaskStatus


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
