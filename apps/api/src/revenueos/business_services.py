from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import and_, case, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_contracts import (
    CompanyCreate,
    CompanyUpdate,
    ContactCreate,
    ContactUpdate,
    OpportunityCreate,
    OpportunityUpdate,
    TaskCreate,
    TaskUpdate,
)
from revenueos.business_repositories import BusinessRepository, PageResult
from revenueos.crm_repositories import CRMRepository
from revenueos.domain import OpportunityAuditAction
from revenueos.errors import PublicAPIError
from revenueos.models import (
    ActionExecution,
    Company,
    Contact,
    ContactSuppression,
    CRMCustomFieldValue,
    CRMRecordChange,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EngageEnrollmentStep,
    EventAttendee,
    Evidence,
    MethodologyProjection,
    MethodologyReview,
    Opportunity,
    OpportunityAuditEvent,
    OutreachMessage,
    ProspectPerson,
    Task,
)
from revenueos.prospect_url_security import (
    PublicUrlSafetyError,
    normalise_company_website,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.opportunities")


class BusinessService:
    """Tenant-aware business rules around the persistence layer."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.repository = BusinessRepository(session)
        self.crm_repository = CRMRepository(session)
        self.tenant = tenant

    async def list_companies(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        industry: str | None,
        sort_by: str,
        sort_order: str,
        include_archived: bool = False,
    ) -> PageResult[Company]:
        return await self.repository.list_companies(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            industry=industry,
            sort_by=sort_by,
            sort_order=sort_order,
            include_archived=include_archived,
        )

    async def get_company(self, company_id: UUID) -> Company:
        company = await self.repository.get_company(self.tenant.organisation_id, company_id)
        if company is None:
            raise self._not_found("company")
        return company

    async def create_company(self, request: CompanyCreate) -> Company:
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        website = str(request.website) if request.website else None
        normalized_domain = self._normalise_website_domain(website) if website else None
        if normalized_domain is not None:
            await self._reject_duplicate_company(normalized_domain)
        company = Company(
            organisation_id=self.tenant.organisation_id,
            owner_user_id=owner_user_id,
            name=request.name,
            website=website,
            normalized_domain=normalized_domain,
            industry=request.industry,
            location=request.location,
            employee_count=request.employee_count,
            status=request.status.value,
        )
        return await self._save(
            company,
            crm_entity_type="account",
            changes=self._creation_changes(
                company,
                ("name", "website", "industry", "location", "employee_count", "status", "owner_user_id"),
            ),
        )

    async def update_company(self, company_id: UUID, request: CompanyUpdate) -> Company:
        company = await self.get_company(company_id)
        self._require_active_record(company)
        values = request.model_dump(exclude_unset=True)
        expected_updated_at = values.pop("expected_updated_at", None)
        self._check_concurrency(company.updated_at, expected_updated_at, "company")
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        if "website" in values:
            website = str(values["website"]) if values["website"] else None
            values["website"] = website
            values["normalized_domain"] = self._normalise_website_domain(website) if website else None
            if values["normalized_domain"] is not None:
                await self._reject_duplicate_company(values["normalized_domain"], excluding=company.id)
        changes = self._changed_values(company, values)
        self._apply_values(company, values)
        company.updated_at = datetime.now(UTC)
        return await self._save(company, crm_entity_type="account", changes=changes)

    async def delete_company(self, company_id: UUID) -> None:
        await self._delete(await self.get_company(company_id), "company")

    async def list_contacts(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        sort_by: str,
        sort_order: str,
        include_archived: bool = False,
    ) -> PageResult[Contact]:
        return await self.repository.list_contacts(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            sort_by=sort_by,
            sort_order=sort_order,
            include_archived=include_archived,
        )

    async def get_contact(self, contact_id: UUID) -> Contact:
        contact = await self.repository.get_contact(self.tenant.organisation_id, contact_id)
        if contact is None:
            raise self._not_found("contact")
        return contact

    async def create_contact(self, request: ContactCreate) -> Contact:
        await self.get_company(request.company_id)
        await self._guard_authoritative_fields(
            "contact",
            set(request.model_dump(exclude_none=True)),
        )
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        email = str(request.email) if request.email else None
        if email is not None:
            await self._reject_duplicate_contact(email)
        contact = Contact(
            organisation_id=self.tenant.organisation_id,
            company_id=request.company_id,
            first_name=request.first_name,
            last_name=request.last_name,
            email=email,
            phone=request.phone,
            job_title=request.job_title,
            linkedin_url=str(request.linkedin_url) if request.linkedin_url else None,
            status=request.status,
            owner_user_id=owner_user_id,
        )
        return await self._save(
            contact,
            crm_entity_type="contact",
            changes=self._creation_changes(
                contact,
                (
                    "company_id",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "job_title",
                    "linkedin_url",
                    "status",
                    "owner_user_id",
                ),
            ),
        )

    async def update_contact(self, contact_id: UUID, request: ContactUpdate) -> Contact:
        contact = await self.get_contact(contact_id)
        self._require_active_record(contact)
        values = request.model_dump(exclude_unset=True)
        expected_updated_at = values.pop("expected_updated_at", None)
        self._check_concurrency(contact.updated_at, expected_updated_at, "contact")
        if "company_id" in values:
            await self.get_company(values["company_id"])
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        await self._guard_authoritative_fields("contact", set(values))
        if "email" in values and values["email"] is not None:
            email = str(values["email"])
            values["email"] = email
            await self._reject_duplicate_contact(email, excluding=contact.id)
        changes = self._changed_values(contact, values)
        self._apply_values(contact, values)
        contact.updated_at = datetime.now(UTC)
        return await self._save(contact, crm_entity_type="contact", changes=changes)

    async def delete_contact(self, contact_id: UUID) -> None:
        contact = await self.get_contact(contact_id)
        organisation_id = self.tenant.organisation_id
        enrollment_ids = select(EngageCampaignEnrollment.id).where(
            EngageCampaignEnrollment.organisation_id == organisation_id,
            EngageCampaignEnrollment.contact_id == contact.id,
        )
        outreach_action_ids = (
            select(OutreachMessage.action_id)
            .join(
                EngageEnrollmentStep,
                and_(
                    EngageEnrollmentStep.organisation_id == OutreachMessage.organisation_id,
                    EngageEnrollmentStep.outreach_message_id == OutreachMessage.id,
                ),
            )
            .where(
                OutreachMessage.organisation_id == organisation_id,
                EngageEnrollmentStep.organisation_id == organisation_id,
                EngageEnrollmentStep.enrollment_id.in_(enrollment_ids),
            )
        )
        now = datetime.now(UTC)
        await self.repository.session.execute(
            update(ActionExecution)
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.action_id.in_(outreach_action_ids),
                ActionExecution.execution_status.in_(("queued", "failed_retryable")),
            )
            .values(
                execution_status="cancelled",
                completed_at=now,
                next_attempt_at=None,
                safe_failure_code="contact_deleted",
                worker_id=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await self.repository.session.execute(
            update(EngageEnrollmentStep)
            .where(
                EngageEnrollmentStep.organisation_id == organisation_id,
                EngageEnrollmentStep.enrollment_id.in_(enrollment_ids),
                EngageEnrollmentStep.state.in_(
                    ("pending", "processing", "ready_for_review", "prepared", "queued", "deferred")
                ),
            )
            .values(
                state="cancelled",
                safe_status_code="contact_deleted",
                worker_id=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await self.repository.session.execute(
            update(EngageCampaignEnrollment)
            .where(
                EngageCampaignEnrollment.organisation_id == organisation_id,
                EngageCampaignEnrollment.contact_id == contact.id,
            )
            .values(
                contact_id=None,
                state="stopped",
                stop_reason="contact_deleted",
                next_scheduled_at=None,
                updated_at=now,
            )
        )
        await self.repository.session.execute(
            update(EngageCampaignAudience)
            .where(
                EngageCampaignAudience.organisation_id == organisation_id,
                EngageCampaignAudience.contact_id == contact.id,
            )
            .values(contact_id=None)
        )
        await self.repository.session.execute(
            update(OutreachMessage)
            .where(
                OutreachMessage.organisation_id == organisation_id,
                OutreachMessage.contact_id == contact.id,
            )
            .values(contact_id=None)
        )
        await self.repository.session.execute(
            update(ContactSuppression)
            .where(
                ContactSuppression.organisation_id == organisation_id,
                ContactSuppression.contact_id == contact.id,
            )
            .values(contact_id=None)
        )
        await self.repository.session.execute(
            update(ProspectPerson)
            .where(
                ProspectPerson.organisation_id == organisation_id,
                ProspectPerson.promoted_contact_id == contact.id,
            )
            .values(promoted_contact_id=None, promoted_by_user_id=None, promoted_at=None)
        )
        await self.repository.session.execute(
            update(EventAttendee)
            .where(
                EventAttendee.organisation_id == organisation_id,
                EventAttendee.contact_id == contact.id,
            )
            .values(
                contact_id=None,
                match_state=case(
                    (EventAttendee.prospect_person_id.is_not(None), "matched_prospect_person"),
                    (EventAttendee.company_id.is_not(None), "matched_company"),
                    else_="unmatched",
                ),
            )
        )
        await self._delete(contact, "contact")

    async def list_opportunities(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        stage: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Opportunity]:
        return await self.repository.list_opportunities(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            stage=stage,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_opportunity(self, opportunity_id: UUID) -> Opportunity:
        opportunity = await self.repository.get_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if opportunity is None:
            raise self._not_found("opportunity")
        return opportunity

    def record_opportunity_view(self, opportunity_id: UUID) -> None:
        logger.info(
            "opportunity_viewed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "opportunity_id": str(opportunity_id),
            },
        )

    async def _get_opportunity_for_update(self, opportunity_id: UUID) -> Opportunity:
        opportunity = await self.repository.get_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if opportunity is None:
            raise self._not_found("opportunity")
        return opportunity

    async def create_opportunity(self, request: OpportunityCreate) -> Opportunity:
        if request.company_id is not None:
            await self.get_company(request.company_id)
        await self._guard_authoritative_fields(
            "opportunity",
            set(request.model_dump(exclude_none=True)),
        )
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        opportunity = Opportunity(
            organisation_id=self.tenant.organisation_id,
            company_id=request.company_id,
            name=request.name,
            stage=request.stage.value,
            status=request.status.value,
            estimated_value=request.estimated_value,
            currency=request.currency,
            expected_close_date=request.expected_close_date,
            owner_user_id=owner_user_id,
            description=request.description,
        )
        self.repository.add(opportunity)
        try:
            await self.repository.flush()
            for change in self._creation_changes(
                opportunity,
                (
                    "company_id",
                    "name",
                    "stage",
                    "status",
                    "estimated_value",
                    "currency",
                    "expected_close_date",
                    "owner_user_id",
                    "description",
                ),
            ).items():
                field_name, (old_value, new_value) = change
                self.repository.add(self._crm_change("opportunity", opportunity.id, field_name, old_value, new_value))
            self.repository.add(
                self._opportunity_audit(
                    opportunity.id,
                    OpportunityAuditAction.CREATED,
                    [
                        "company_id",
                        "name",
                        "stage",
                        "status",
                        "estimated_value",
                        "currency",
                        "expected_close_date",
                        "owner_user_id",
                        "description",
                    ],
                )
            )
            await self.repository.flush()
            await self.repository.refresh(opportunity)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The record conflicts with existing or related data.",
                409,
            ) from exc
        logger.info(
            "opportunity_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "opportunity_id": str(opportunity.id),
            },
        )
        return opportunity

    async def update_opportunity(
        self,
        opportunity_id: UUID,
        request: OpportunityUpdate,
    ) -> Opportunity:
        opportunity = await self._get_opportunity_for_update(opportunity_id)
        self._require_active_record(opportunity)
        values = request.model_dump(exclude_unset=True)
        expected_updated_at = values.pop("expected_updated_at", None)
        if expected_updated_at is not None and not self._same_instant(
            opportunity.updated_at,
            expected_updated_at,
        ):
            raise PublicAPIError(
                "stale_write",
                "This opportunity changed after it was loaded. Refresh and try again.",
                409,
            )
        if "company_id" in values:
            if values["company_id"] is not None:
                await self.get_company(values["company_id"])
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        await self._guard_authoritative_fields("opportunity", set(values))
        changes = self._changed_values(opportunity, values)
        self._apply_values(opportunity, values)
        opportunity.updated_at = datetime.now(UTC)
        self.repository.add(
            self._opportunity_audit(
                opportunity.id,
                OpportunityAuditAction.UPDATED,
                list(values),
            )
        )
        saved = await self._save(opportunity, crm_entity_type="opportunity", changes=changes)
        logger.info(
            "opportunity_updated",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "opportunity_id": str(opportunity.id),
                "changed_field_count": len(values),
            },
        )
        return saved

    async def delete_opportunity(self, opportunity_id: UUID) -> None:
        opportunity = await self._get_opportunity_for_update(opportunity_id)
        clarification_evidence_ids = list(
            (
                await self.repository.session.scalars(
                    select(MethodologyReview.clarification_evidence_id).where(
                        MethodologyReview.organisation_id == self.tenant.organisation_id,
                        MethodologyReview.opportunity_id == opportunity_id,
                        MethodologyReview.clarification_evidence_id.is_not(None),
                    )
                )
            ).all()
        )
        await self.repository.session.execute(
            delete(MethodologyReview).where(
                MethodologyReview.organisation_id == self.tenant.organisation_id,
                MethodologyReview.opportunity_id == opportunity_id,
            )
        )
        await self.repository.session.execute(
            delete(MethodologyProjection).where(
                MethodologyProjection.organisation_id == self.tenant.organisation_id,
                MethodologyProjection.opportunity_id == opportunity_id,
            )
        )
        if clarification_evidence_ids:
            await self.repository.session.execute(
                delete(Evidence).where(
                    Evidence.organisation_id == self.tenant.organisation_id,
                    Evidence.id.in_(clarification_evidence_ids),
                )
            )
        self.repository.add(
            self._opportunity_audit(
                opportunity.id,
                OpportunityAuditAction.DELETED,
                ["deleted"],
            )
        )
        await self._delete(opportunity, "opportunity")

    async def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        contact_id: UUID | None,
        opportunity_id: UUID | None,
        assigned_user_id: UUID | None,
        status: str | None,
        priority: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Task]:
        return await self.repository.list_tasks(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            contact_id=contact_id,
            opportunity_id=opportunity_id,
            assigned_user_id=assigned_user_id,
            status=status,
            priority=priority,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_task(self, task_id: UUID) -> Task:
        task = await self.repository.get_task(self.tenant.organisation_id, task_id)
        if task is None:
            raise self._not_found("task")
        return task

    async def create_task(self, request: TaskCreate) -> Task:
        assigned_user_id = request.assigned_user_id
        if assigned_user_id is not None:
            await self._require_member(assigned_user_id, "assignedUserId")
        company_id = await self._validate_task_relationships(
            company_id=request.company_id,
            contact_id=request.contact_id,
            opportunity_id=request.opportunity_id,
        )
        task = Task(
            organisation_id=self.tenant.organisation_id,
            company_id=company_id,
            contact_id=request.contact_id,
            opportunity_id=request.opportunity_id,
            title=request.title,
            description=request.description,
            status=request.status.value,
            priority=request.priority.value,
            due_at=request.due_at,
            assigned_user_id=assigned_user_id,
            created_by_user_id=self.tenant.user_id,
        )
        return await self._save(task)

    async def update_task(self, task_id: UUID, request: TaskUpdate) -> Task:
        task = await self.get_task(task_id)
        values = request.model_dump(exclude_unset=True)
        if "assigned_user_id" in values and values["assigned_user_id"] is not None:
            await self._require_member(values["assigned_user_id"], "assignedUserId")
        company_id = await self._validate_task_relationships(
            company_id=values.get("company_id", task.company_id),
            contact_id=values.get("contact_id", task.contact_id),
            opportunity_id=values.get("opportunity_id", task.opportunity_id),
        )
        values["company_id"] = company_id
        self._apply_values(task, values)
        return await self._save(task)

    async def delete_task(self, task_id: UUID) -> None:
        await self._delete(await self.get_task(task_id), "task")

    async def _validate_task_relationships(
        self,
        *,
        company_id: UUID | None,
        contact_id: UUID | None,
        opportunity_id: UUID | None,
    ) -> UUID | None:
        related_company_ids: set[UUID] = set()
        if company_id is not None:
            await self.get_company(company_id)
            related_company_ids.add(company_id)
        if contact_id is not None:
            related_company_ids.add((await self.get_contact(contact_id)).company_id)
        if opportunity_id is not None:
            opportunity_company_id = (await self.get_opportunity(opportunity_id)).company_id
            if opportunity_company_id is not None:
                related_company_ids.add(opportunity_company_id)
        if len(related_company_ids) > 1:
            raise PublicAPIError(
                "inconsistent_relationship",
                "Task relationships must refer to the same company.",
                422,
            )
        return next(iter(related_company_ids), None)

    async def _require_member(self, user_id: UUID, field_name: str) -> None:
        if not self.tenant.can_manage() and user_id != self.tenant.user_id:
            raise PublicAPIError(
                "forbidden_owner_assignment",
                "Members can only assign CRM records to themselves.",
                403,
            )
        if not await self.repository.membership_exists(self.tenant.organisation_id, user_id):
            raise PublicAPIError(
                "invalid_relationship",
                f"{field_name} must identify a member of the current organisation.",
                422,
            )

    async def _save[TEntity: (Company, Contact, Opportunity, Task)](
        self,
        entity: TEntity,
        *,
        crm_entity_type: str | None = None,
        changes: dict[str, tuple[object | None, object | None]] | None = None,
    ) -> TEntity:
        self.repository.add(entity)
        try:
            await self.repository.flush()
            if crm_entity_type is not None and changes:
                for field_name, (old_value, new_value) in changes.items():
                    self.repository.add(self._crm_change(crm_entity_type, entity.id, field_name, old_value, new_value))
                await self.repository.flush()
            await self.repository.refresh(entity)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The record conflicts with existing or related data.",
                409,
            ) from exc
        return entity

    async def _delete(
        self,
        entity: Company | Contact | Opportunity | Task,
        entity_name: str,
    ) -> None:
        if isinstance(entity, (Company, Contact, Opportunity)):
            crm_entity_type = (
                "account"
                if isinstance(entity, Company)
                else "contact"
                if isinstance(entity, Contact)
                else "opportunity"
            )
            await self.repository.session.execute(
                delete(CRMCustomFieldValue).where(
                    CRMCustomFieldValue.organisation_id == self.tenant.organisation_id,
                    CRMCustomFieldValue.entity_type == crm_entity_type,
                    CRMCustomFieldValue.entity_id == entity.id,
                )
            )
            await self.repository.session.execute(
                delete(CRMRecordChange).where(
                    CRMRecordChange.organisation_id == self.tenant.organisation_id,
                    CRMRecordChange.entity_type == crm_entity_type,
                    CRMRecordChange.entity_id == entity.id,
                )
            )
        await self.repository.delete(entity)
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "resource_in_use",
                f"The {entity_name} cannot be deleted while related records exist.",
                409,
            ) from exc

    @staticmethod
    def _apply_values(entity: Company | Contact | Opportunity | Task, values: dict[str, Any]) -> None:
        for field_name, value in values.items():
            if hasattr(value, "value"):
                value = value.value
            elif field_name in {"website", "linkedin_url", "email"} and value is not None:
                value = str(value)
            setattr(entity, field_name, value)

    def _opportunity_audit(
        self,
        opportunity_id: UUID,
        action: OpportunityAuditAction,
        changed_fields: list[str],
        *,
        metadata: dict[str, object] | None = None,
    ) -> OpportunityAuditEvent:
        return OpportunityAuditEvent(
            organisation_id=self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            actor_user_id=self.tenant.user_id,
            action=action.value,
            changed_fields=sorted(changed_fields),
            metadata_json=metadata or {},
        )

    async def _guard_authoritative_fields(self, entity_type: str, fields: set[str]) -> None:
        setting = await self.crm_repository.setting(self.tenant.organisation_id)
        connection = await self.crm_repository.active_hubspot_connection(self.tenant.organisation_id)
        external = (setting is not None and setting.mode == "external") or (setting is None and connection is not None)
        if not external:
            return
        authority = await self.crm_repository.field_authority(self.tenant.organisation_id, entity_type)
        blocked = sorted(field for field in fields if authority.get(field) == "crm_authoritative")
        if blocked:
            raise PublicAPIError(
                "crm_authoritative_field",
                "One or more fields are controlled by the connected CRM.",
                409,
                details={"fields": ",".join(blocked)},
            )

    async def _reject_duplicate_company(self, domain: str, *, excluding: UUID | None = None) -> None:
        existing = await self.repository.company_by_domain(self.tenant.organisation_id, domain)
        if existing is not None and existing.id != excluding:
            raise PublicAPIError(
                "duplicate_company_domain",
                "An account with this website domain already exists.",
                409,
                details={"entityType": "account", "entityId": str(existing.id)},
            )

    async def _reject_duplicate_contact(self, email: str, *, excluding: UUID | None = None) -> None:
        existing = await self.repository.contact_by_email(self.tenant.organisation_id, email)
        if existing is not None and existing.id != excluding:
            raise PublicAPIError(
                "duplicate_contact_email",
                "A contact with this business email already exists.",
                409,
                details={"entityType": "contact", "entityId": str(existing.id)},
            )

    def _crm_change(
        self,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
        old_value: object | None,
        new_value: object | None,
    ) -> CRMRecordChange:
        return CRMRecordChange(
            organisation_id=self.tenant.organisation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=field_name,
            old_value_json=self._json_value(old_value),
            new_value_json=self._json_value(new_value),
            source="manual_user_entry",
            changed_by_user_id=self.tenant.user_id,
        )

    @classmethod
    def _creation_changes(
        cls, entity: Company | Contact | Opportunity, fields: tuple[str, ...]
    ) -> dict[str, tuple[object | None, object | None]]:
        return {
            field: (None, cls._plain_value(getattr(entity, field)))
            for field in fields
            if getattr(entity, field) is not None
        }

    @classmethod
    def _changed_values(
        cls, entity: Company | Contact | Opportunity, values: dict[str, Any]
    ) -> dict[str, tuple[object | None, object | None]]:
        return {
            field: (cls._plain_value(getattr(entity, field)), cls._plain_value(value))
            for field, value in values.items()
            if field != "normalized_domain" and cls._plain_value(getattr(entity, field)) != cls._plain_value(value)
        }

    @staticmethod
    def _plain_value(value: object | None) -> object | None:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _json_value(value: object | None) -> object | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "isoformat"):
            return str(value.isoformat())
        if hasattr(value, "value"):
            return str(value.value)
        return str(value) if value is not None and not isinstance(value, (str, int, float, bool)) else value

    def _check_concurrency(self, current: datetime, expected: datetime | None, entity_name: str) -> None:
        if expected is not None and not self._same_instant(current, expected):
            raise PublicAPIError(
                "stale_write",
                f"This {entity_name} changed after it was loaded. Refresh and try again.",
                409,
            )

    @staticmethod
    def _require_active_record(entity: Company | Contact | Opportunity) -> None:
        if entity.archived_at is not None:
            raise PublicAPIError(
                "record_archived",
                "Restore this record before changing it.",
                409,
            )

    @staticmethod
    def _same_instant(first: datetime, second: datetime) -> bool:
        def normalise(value: datetime) -> datetime:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        return normalise(first) == normalise(second)

    @staticmethod
    def _not_found(entity_name: str) -> PublicAPIError:
        return PublicAPIError(
            f"{entity_name}_not_found",
            f"The requested {entity_name} was not found.",
            404,
        )

    @staticmethod
    def _normalise_website_domain(value: str) -> str | None:
        try:
            host = urlsplit(value).hostname
            if host is None:
                return None
            return normalise_company_website(f"https://{host}/").domain
        except (PublicUrlSafetyError, ValueError):
            return None
