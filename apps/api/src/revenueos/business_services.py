from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

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
from revenueos.domain import OpportunityAuditAction
from revenueos.errors import PublicAPIError
from revenueos.models import Company, Contact, Opportunity, OpportunityAuditEvent, Task
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.opportunities")


class BusinessService:
    """Tenant-aware business rules around the persistence layer."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.repository = BusinessRepository(session)
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
        )

    async def get_company(self, company_id: UUID) -> Company:
        company = await self.repository.get_company(self.tenant.organisation_id, company_id)
        if company is None:
            raise self._not_found("company")
        return company

    async def create_company(self, request: CompanyCreate) -> Company:
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        company = Company(
            organisation_id=self.tenant.organisation_id,
            owner_user_id=owner_user_id,
            name=request.name,
            website=str(request.website) if request.website else None,
            industry=request.industry,
            employee_count=request.employee_count,
            status=request.status.value,
        )
        return await self._save(company)

    async def update_company(self, company_id: UUID, request: CompanyUpdate) -> Company:
        company = await self.get_company(company_id)
        values = request.model_dump(exclude_unset=True)
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        self._apply_values(company, values)
        return await self._save(company)

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
    ) -> PageResult[Contact]:
        return await self.repository.list_contacts(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_contact(self, contact_id: UUID) -> Contact:
        contact = await self.repository.get_contact(self.tenant.organisation_id, contact_id)
        if contact is None:
            raise self._not_found("contact")
        return contact

    async def create_contact(self, request: ContactCreate) -> Contact:
        await self.get_company(request.company_id)
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        contact = Contact(
            organisation_id=self.tenant.organisation_id,
            company_id=request.company_id,
            first_name=request.first_name,
            last_name=request.last_name,
            email=str(request.email),
            phone=request.phone,
            job_title=request.job_title,
            linkedin_url=str(request.linkedin_url) if request.linkedin_url else None,
            owner_user_id=owner_user_id,
        )
        return await self._save(contact)

    async def update_contact(self, contact_id: UUID, request: ContactUpdate) -> Contact:
        contact = await self.get_contact(contact_id)
        values = request.model_dump(exclude_unset=True)
        if "company_id" in values:
            await self.get_company(values["company_id"])
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        self._apply_values(contact, values)
        return await self._save(contact)

    async def delete_contact(self, contact_id: UUID) -> None:
        await self._delete(await self.get_contact(contact_id), "contact")

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
        self._apply_values(opportunity, values)
        opportunity.updated_at = datetime.now(UTC)
        self.repository.add(
            self._opportunity_audit(
                opportunity.id,
                OpportunityAuditAction.UPDATED,
                list(values),
            )
        )
        saved = await self._save(opportunity)
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
        if not await self.repository.membership_exists(self.tenant.organisation_id, user_id):
            raise PublicAPIError(
                "invalid_relationship",
                f"{field_name} must identify a member of the current organisation.",
                422,
            )

    async def _save[TEntity: (Company, Contact, Opportunity, Task)](
        self,
        entity: TEntity,
    ) -> TEntity:
        self.repository.add(entity)
        try:
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
