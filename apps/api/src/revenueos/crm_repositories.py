from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Base,
    Company,
    Contact,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMFieldMapping,
    CRMRecordChange,
    CRMRecordMerge,
    EventAttendee,
    EventEncounter,
    IntegrationConnection,
    Interaction,
    Opportunity,
    OrganisationCRMSetting,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    OutreachMessage,
    SalesEvent,
    Task,
    User,
)


@dataclass(frozen=True)
class CRMHistoryRecord:
    change: CRMRecordChange
    actor_name: str


@dataclass(frozen=True)
class CRMMemberRecord:
    user_id: UUID
    display_name: str
    active: bool


class CRMRepository:
    """Explicitly tenant-scoped persistence for the native CRM layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def entitlement(
        self,
        organisation_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganisationModuleEntitlement | None:
        statement = select(OrganisationModuleEntitlement).where(
            OrganisationModuleEntitlement.organisation_id == organisation_id,
            OrganisationModuleEntitlement.module_key == "crm",
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(
            OrganisationModuleEntitlement | None,
            await self.session.scalar(statement),
        )

    async def module_enabled(self, organisation_id: UUID, module_key: str) -> bool:
        enabled = await self.session.scalar(
            select(OrganisationModuleEntitlement.enabled).where(
                OrganisationModuleEntitlement.organisation_id == organisation_id,
                OrganisationModuleEntitlement.module_key == module_key,
            )
        )
        return bool(enabled)

    async def setting(self, organisation_id: UUID, *, for_update: bool = False) -> OrganisationCRMSetting | None:
        statement = select(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == organisation_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(OrganisationCRMSetting | None, await self.session.scalar(statement))

    async def active_hubspot_connection(self, organisation_id: UUID) -> IntegrationConnection | None:
        return cast(
            IntegrationConnection | None,
            await self.session.scalar(
                select(IntegrationConnection)
                .where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.connector_key == "hubspot",
                    IntegrationConnection.connection_status.in_(("active", "reauthorisation_required")),
                )
                .order_by(IntegrationConnection.connected_at.desc(), IntegrationConnection.id.desc())
                .limit(1)
            ),
        )

    async def has_active_field_mappings(self, organisation_id: UUID) -> bool:
        result = await self.session.scalar(
            select(CRMFieldMapping.id)
            .join(
                IntegrationConnection,
                and_(
                    IntegrationConnection.organisation_id == CRMFieldMapping.organisation_id,
                    IntegrationConnection.id == CRMFieldMapping.connection_id,
                ),
            )
            .where(
                CRMFieldMapping.organisation_id == organisation_id,
                CRMFieldMapping.enabled.is_(True),
                IntegrationConnection.connector_key == "hubspot",
                IntegrationConnection.connection_status.in_(("active", "reauthorisation_required")),
            )
            .limit(1)
        )
        return result is not None

    async def record(
        self,
        organisation_id: UUID,
        entity_type: str,
        entity_id: UUID,
        *,
        for_update: bool = False,
    ) -> Company | Contact | Opportunity | None:
        model: type[Company] | type[Contact] | type[Opportunity]
        if entity_type == "account":
            model = Company
        elif entity_type == "contact":
            model = Contact
        else:
            model = Opportunity
        statement = select(model).where(model.organisation_id == organisation_id, model.id == entity_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(Company | Contact | Opportunity | None, await self.session.scalar(statement))

    async def field_authority(self, organisation_id: UUID, entity_type: str) -> dict[str, str]:
        rows = (
            await self.session.execute(
                select(CRMFieldMapping.revenueos_field, CRMFieldMapping.authority)
                .join(
                    IntegrationConnection,
                    and_(
                        IntegrationConnection.organisation_id == CRMFieldMapping.organisation_id,
                        IntegrationConnection.id == CRMFieldMapping.connection_id,
                    ),
                )
                .where(
                    CRMFieldMapping.organisation_id == organisation_id,
                    CRMFieldMapping.entity_type == entity_type,
                    CRMFieldMapping.enabled.is_(True),
                    IntegrationConnection.connector_key == "hubspot",
                    IntegrationConnection.connection_status.in_(("active", "reauthorisation_required")),
                )
            )
        ).all()
        return {str(field): str(authority) for field, authority in rows}

    async def members(self, organisation_id: UUID) -> list[CRMMemberRecord]:
        rows = (
            await self.session.execute(
                select(User.id, User.display_name, OrganisationMembership.status)
                .join(OrganisationMembership, OrganisationMembership.user_id == User.id)
                .where(OrganisationMembership.organisation_id == organisation_id)
                .order_by(User.display_name, User.id)
            )
        ).all()
        return [CRMMemberRecord(user_id=row[0], display_name=row[1], active=row[2] == "active") for row in rows]

    async def definitions(
        self,
        organisation_id: UUID,
        *,
        entity_type: str | None = None,
        include_archived: bool = False,
    ) -> list[CRMCustomFieldDefinition]:
        statement = select(CRMCustomFieldDefinition).where(CRMCustomFieldDefinition.organisation_id == organisation_id)
        if entity_type is not None:
            statement = statement.where(CRMCustomFieldDefinition.entity_type == entity_type)
        if not include_archived:
            statement = statement.where(CRMCustomFieldDefinition.active.is_(True))
        return list(
            (
                await self.session.scalars(
                    statement.order_by(
                        CRMCustomFieldDefinition.entity_type,
                        CRMCustomFieldDefinition.display_order,
                        CRMCustomFieldDefinition.label,
                        CRMCustomFieldDefinition.id,
                    )
                )
            ).all()
        )

    async def definition(
        self, organisation_id: UUID, definition_id: UUID, *, for_update: bool = False
    ) -> CRMCustomFieldDefinition | None:
        statement = select(CRMCustomFieldDefinition).where(
            CRMCustomFieldDefinition.organisation_id == organisation_id,
            CRMCustomFieldDefinition.id == definition_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(CRMCustomFieldDefinition | None, await self.session.scalar(statement))

    async def definition_count(self, organisation_id: UUID, entity_type: str) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(CRMCustomFieldDefinition)
            .where(
                CRMCustomFieldDefinition.organisation_id == organisation_id,
                CRMCustomFieldDefinition.entity_type == entity_type,
                CRMCustomFieldDefinition.active.is_(True),
            )
        )
        return int(count or 0)

    async def value(
        self,
        organisation_id: UUID,
        definition_id: UUID,
        entity_type: str,
        entity_id: UUID,
        *,
        for_update: bool = False,
    ) -> CRMCustomFieldValue | None:
        statement = select(CRMCustomFieldValue).where(
            CRMCustomFieldValue.organisation_id == organisation_id,
            CRMCustomFieldValue.definition_id == definition_id,
            CRMCustomFieldValue.entity_type == entity_type,
            CRMCustomFieldValue.entity_id == entity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(CRMCustomFieldValue | None, await self.session.scalar(statement))

    async def values_for_record(
        self, organisation_id: UUID, entity_type: str, entity_id: UUID
    ) -> dict[UUID, CRMCustomFieldValue]:
        records = list(
            (
                await self.session.scalars(
                    select(CRMCustomFieldValue).where(
                        CRMCustomFieldValue.organisation_id == organisation_id,
                        CRMCustomFieldValue.entity_type == entity_type,
                        CRMCustomFieldValue.entity_id == entity_id,
                    )
                )
            ).all()
        )
        return {record.definition_id: record for record in records}

    async def history(
        self, organisation_id: UUID, entity_type: str, entity_id: UUID, *, limit: int = 50
    ) -> list[CRMHistoryRecord]:
        rows = (
            await self.session.execute(
                select(CRMRecordChange, User.display_name)
                .join(User, User.id == CRMRecordChange.changed_by_user_id)
                .where(
                    CRMRecordChange.organisation_id == organisation_id,
                    CRMRecordChange.entity_type == entity_type,
                    CRMRecordChange.entity_id == entity_id,
                )
                .order_by(CRMRecordChange.changed_at.desc(), CRMRecordChange.id.desc())
                .limit(limit)
            )
        ).all()
        return [CRMHistoryRecord(change=row[0], actor_name=row[1]) for row in rows]

    async def interactions(
        self, organisation_id: UUID, entity_type: str, entity_id: UUID, *, limit: int
    ) -> list[Interaction]:
        statement = select(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.deleted_at.is_(None),
        )
        if entity_type == "account":
            statement = statement.where(Interaction.company_id == entity_id)
        elif entity_type == "contact":
            statement = statement.where(Interaction.contact_id == entity_id)
        else:
            statement = statement.where(Interaction.opportunity_id == entity_id)
        return list(
            (
                await self.session.scalars(
                    statement.order_by(
                        func.coalesce(
                            Interaction.actual_end_at,
                            Interaction.actual_start_at,
                            Interaction.scheduled_start_at,
                            Interaction.created_at,
                        ).desc(),
                        Interaction.id.desc(),
                    ).limit(limit)
                )
            ).all()
        )

    async def tasks(self, organisation_id: UUID, entity_type: str, entity_id: UUID, *, limit: int) -> list[Task]:
        statement = select(Task).where(Task.organisation_id == organisation_id)
        if entity_type == "account":
            statement = statement.where(Task.company_id == entity_id)
        elif entity_type == "contact":
            statement = statement.where(Task.contact_id == entity_id)
        else:
            statement = statement.where(Task.opportunity_id == entity_id)
        return list(
            (await self.session.scalars(statement.order_by(Task.updated_at.desc(), Task.id.desc()).limit(limit))).all()
        )

    async def outreach(
        self, organisation_id: UUID, entity_type: str, entity_id: UUID, *, limit: int
    ) -> list[OutreachMessage]:
        statement = select(OutreachMessage).where(
            OutreachMessage.organisation_id == organisation_id,
            OutreachMessage.contact_id.is_not(None),
        )
        if entity_type == "contact":
            statement = statement.where(OutreachMessage.contact_id == entity_id)
        elif entity_type == "account":
            statement = statement.join(
                Contact,
                and_(
                    Contact.organisation_id == OutreachMessage.organisation_id,
                    Contact.id == OutreachMessage.contact_id,
                ),
            ).where(Contact.company_id == entity_id)
        else:
            return []
        return list(
            (
                await self.session.scalars(
                    statement.order_by(OutreachMessage.updated_at.desc(), OutreachMessage.id.desc()).limit(limit)
                )
            ).all()
        )

    async def event_encounters(
        self, organisation_id: UUID, entity_type: str, entity_id: UUID, *, limit: int
    ) -> list[tuple[EventEncounter, SalesEvent]]:
        statement = (
            select(EventEncounter, SalesEvent)
            .join(
                EventAttendee,
                and_(
                    EventAttendee.organisation_id == EventEncounter.organisation_id,
                    EventAttendee.event_id == EventEncounter.event_id,
                    EventAttendee.id == EventEncounter.attendee_id,
                ),
            )
            .join(
                SalesEvent,
                and_(
                    SalesEvent.organisation_id == EventEncounter.organisation_id,
                    SalesEvent.id == EventEncounter.event_id,
                ),
            )
            .where(EventEncounter.organisation_id == organisation_id)
        )
        if entity_type == "account":
            statement = statement.where(EventAttendee.company_id == entity_id)
        elif entity_type == "contact":
            statement = statement.where(EventAttendee.contact_id == entity_id)
        else:
            return []
        rows = (
            await self.session.execute(
                statement.order_by(EventEncounter.occurred_at.desc(), EventEncounter.id.desc()).limit(limit)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def opportunities_for_account(
        self, organisation_id: UUID, account_id: UUID, *, limit: int
    ) -> list[Opportunity]:
        return list(
            (
                await self.session.scalars(
                    select(Opportunity)
                    .where(
                        Opportunity.organisation_id == organisation_id,
                        Opportunity.company_id == account_id,
                    )
                    .order_by(Opportunity.created_at.desc(), Opportunity.id.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def owner_name(self, user_id: UUID) -> str:
        return str(await self.session.scalar(select(User.display_name).where(User.id == user_id)) or "Unknown member")

    async def merge_for_source(self, organisation_id: UUID, entity_type: str, entity_id: UUID) -> CRMRecordMerge | None:
        return cast(
            CRMRecordMerge | None,
            await self.session.scalar(
                select(CRMRecordMerge).where(
                    CRMRecordMerge.organisation_id == organisation_id,
                    CRMRecordMerge.entity_type == entity_type,
                    CRMRecordMerge.source_entity_id == entity_id,
                )
            ),
        )

    def add(self, record: Base) -> None:
        self.session.add(record)

    async def delete(self, record: Base) -> None:
        await self.session.delete(record)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, record: Base) -> None:
        await self.session.refresh(record)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
