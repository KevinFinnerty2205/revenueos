from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    Contact,
    EngageCampaign,
    EngageCampaignVersion,
    EventAttendee,
    EventAttendeeImport,
    EventAttendeeUserState,
    EventCampaignLink,
    EventEncounter,
    Interaction,
    Opportunity,
    OrganisationModuleEntitlement,
    ProspectDiscoveryCandidate,
    ProspectPerson,
    ProspectResearchTarget,
    SalesEvent,
)


@dataclass(frozen=True)
class EventCampaignRecord:
    link: EventCampaignLink
    campaign: EngageCampaign
    version: EngageCampaignVersion


class EventRepository:
    """Tenant-explicit Event persistence and bounded read models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def entitlement(self, organisation_id: UUID, module_key: str) -> OrganisationModuleEntitlement | None:
        return cast(
            OrganisationModuleEntitlement | None,
            await self.session.scalar(
                select(OrganisationModuleEntitlement).where(
                    OrganisationModuleEntitlement.organisation_id == organisation_id,
                    OrganisationModuleEntitlement.module_key == module_key,
                )
            ),
        )

    async def events(self, organisation_id: UUID, *, search: str | None) -> list[SalesEvent]:
        statement = select(SalesEvent).where(SalesEvent.organisation_id == organisation_id)
        if search:
            term = f"%{search.casefold()}%"
            statement = statement.where(
                or_(
                    func.lower(SalesEvent.name).like(term),
                    func.lower(func.coalesce(SalesEvent.city, "")).like(term),
                    func.lower(func.coalesce(SalesEvent.location_name, "")).like(term),
                )
            )
        values = await self.session.scalars(statement.order_by(SalesEvent.start_at.desc(), SalesEvent.id))
        return list(values.all())

    async def event(self, organisation_id: UUID, event_id: UUID, *, for_update: bool = False) -> SalesEvent | None:
        statement = select(SalesEvent).where(
            SalesEvent.organisation_id == organisation_id,
            SalesEvent.id == event_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(SalesEvent | None, await self.session.scalar(statement))

    async def active_event_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SalesEvent)
                .where(
                    SalesEvent.organisation_id == organisation_id,
                    SalesEvent.state.in_(("draft", "upcoming", "active")),
                    or_(SalesEvent.state == "draft", SalesEvent.end_at >= datetime.now(UTC)),
                )
            )
            or 0
        )

    async def event_import(
        self,
        organisation_id: UUID,
        event_id: UUID,
        import_id: UUID,
        *,
        for_update: bool = False,
    ) -> EventAttendeeImport | None:
        statement = select(EventAttendeeImport).where(
            EventAttendeeImport.organisation_id == organisation_id,
            EventAttendeeImport.event_id == event_id,
            EventAttendeeImport.id == import_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EventAttendeeImport | None, await self.session.scalar(statement))

    async def import_by_fingerprint(
        self,
        organisation_id: UUID,
        event_id: UUID,
        fingerprint: str,
        *,
        for_update: bool = False,
    ) -> EventAttendeeImport | None:
        statement = select(EventAttendeeImport).where(
            EventAttendeeImport.organisation_id == organisation_id,
            EventAttendeeImport.event_id == event_id,
            EventAttendeeImport.file_fingerprint == fingerprint,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EventAttendeeImport | None, await self.session.scalar(statement))

    async def confirmed_imports_since(self, organisation_id: UUID, event_id: UUID, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(EventAttendeeImport)
                .where(
                    EventAttendeeImport.organisation_id == organisation_id,
                    EventAttendeeImport.event_id == event_id,
                    EventAttendeeImport.state == "confirmed",
                    EventAttendeeImport.confirmed_at >= since,
                )
            )
            or 0
        )

    async def attendee_count(self, organisation_id: UUID, event_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(EventAttendee)
                .where(EventAttendee.organisation_id == organisation_id, EventAttendee.event_id == event_id)
            )
            or 0
        )

    async def attendees(
        self,
        organisation_id: UUID,
        event_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        priority: str | None,
        plan_state: str | None,
        user_id: UUID,
    ) -> tuple[list[EventAttendee], int]:
        conditions = [EventAttendee.organisation_id == organisation_id, EventAttendee.event_id == event_id]
        if search:
            term = f"%{search.casefold()}%"
            conditions.append(
                or_(
                    func.lower(func.coalesce(EventAttendee.first_name, "")).like(term),
                    func.lower(func.coalesce(EventAttendee.last_name, "")).like(term),
                    func.lower(func.coalesce(EventAttendee.company_name, "")).like(term),
                    func.lower(func.coalesce(EventAttendee.job_title, "")).like(term),
                )
            )
        if priority:
            conditions.append(EventAttendee.priority_state == priority)
        statement = select(EventAttendee).where(*conditions)
        count_statement = select(func.count()).select_from(EventAttendee).where(*conditions)
        if plan_state:
            state_join = and_(
                EventAttendeeUserState.organisation_id == EventAttendee.organisation_id,
                EventAttendeeUserState.event_id == EventAttendee.event_id,
                EventAttendeeUserState.attendee_id == EventAttendee.id,
                EventAttendeeUserState.user_id == user_id,
            )
            statement = statement.join(EventAttendeeUserState, state_join).where(
                EventAttendeeUserState.plan_state == plan_state
            )
            count_statement = count_statement.join(EventAttendeeUserState, state_join).where(
                EventAttendeeUserState.plan_state == plan_state
            )
        total = int(await self.session.scalar(count_statement) or 0)
        values = await self.session.scalars(
            statement.order_by(
                EventAttendee.priority_state,
                EventAttendee.last_name,
                EventAttendee.first_name,
                EventAttendee.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(values.all()), total

    async def all_attendees(self, organisation_id: UUID, event_id: UUID) -> list[EventAttendee]:
        values = await self.session.scalars(
            select(EventAttendee).where(
                EventAttendee.organisation_id == organisation_id,
                EventAttendee.event_id == event_id,
            )
        )
        return list(values.all())

    async def event_summary_counts(
        self, organisation_id: UUID, event_ids: list[UUID], user_id: UUID
    ) -> dict[UUID, dict[str, int]]:
        if not event_ids:
            return {}
        result = {
            event_id: {
                "attendees_imported": 0,
                "priority_people": 0,
                "planned": 0,
                "met": 0,
                "follow_up": 0,
                "added_to_sales": 0,
                "interactions_captured": 0,
                "active_opportunity_contacts": 0,
            }
            for event_id in event_ids
        }
        attendee_rows = (
            await self.session.execute(
                select(
                    EventAttendee.event_id,
                    func.count(),
                    func.sum(case((EventAttendee.priority_state == "priority_to_meet", 1), else_=0)),
                    func.sum(case((EventAttendee.contact_id.is_not(None), 1), else_=0)),
                    func.sum(case((EventAttendee.active_opportunity_id.is_not(None), 1), else_=0)),
                )
                .where(
                    EventAttendee.organisation_id == organisation_id,
                    EventAttendee.event_id.in_(event_ids),
                )
                .group_by(EventAttendee.event_id)
            )
        ).all()
        for event_id, total, priority, added, opportunities in attendee_rows:
            values = result[event_id]
            values["attendees_imported"] = int(total or 0)
            values["priority_people"] = int(priority or 0)
            values["added_to_sales"] = int(added or 0)
            values["active_opportunity_contacts"] = int(opportunities or 0)
        state_rows = (
            await self.session.execute(
                select(
                    EventAttendeeUserState.event_id,
                    func.sum(case((EventAttendeeUserState.plan_state == "planned", 1), else_=0)),
                    func.sum(case((EventAttendeeUserState.plan_state == "follow_up", 1), else_=0)),
                )
                .where(
                    EventAttendeeUserState.organisation_id == organisation_id,
                    EventAttendeeUserState.event_id.in_(event_ids),
                    EventAttendeeUserState.user_id == user_id,
                )
                .group_by(EventAttendeeUserState.event_id)
            )
        ).all()
        for event_id, planned, follow_up in state_rows:
            result[event_id]["planned"] = int(planned or 0)
            result[event_id]["follow_up"] = int(follow_up or 0)
        encounter_rows = (
            await self.session.execute(
                select(
                    EventEncounter.event_id,
                    func.count(),
                    func.sum(case((EventEncounter.interaction_id.is_not(None), 1), else_=0)),
                )
                .where(
                    EventEncounter.organisation_id == organisation_id,
                    EventEncounter.event_id.in_(event_ids),
                    EventEncounter.user_id == user_id,
                )
                .group_by(EventEncounter.event_id)
            )
        ).all()
        for event_id, met, captured in encounter_rows:
            result[event_id]["met"] = int(met or 0)
            result[event_id]["interactions_captured"] = int(captured or 0)
        return result

    async def attendee(
        self,
        organisation_id: UUID,
        event_id: UUID,
        attendee_id: UUID,
        *,
        for_update: bool = False,
    ) -> EventAttendee | None:
        statement = select(EventAttendee).where(
            EventAttendee.organisation_id == organisation_id,
            EventAttendee.event_id == event_id,
            EventAttendee.id == attendee_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EventAttendee | None, await self.session.scalar(statement))

    async def user_states(
        self, organisation_id: UUID, event_id: UUID, attendee_ids: list[UUID]
    ) -> list[EventAttendeeUserState]:
        if not attendee_ids:
            return []
        values = await self.session.scalars(
            select(EventAttendeeUserState).where(
                EventAttendeeUserState.organisation_id == organisation_id,
                EventAttendeeUserState.event_id == event_id,
                EventAttendeeUserState.attendee_id.in_(attendee_ids),
            )
        )
        return list(values.all())

    async def user_state(
        self,
        organisation_id: UUID,
        event_id: UUID,
        attendee_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> EventAttendeeUserState | None:
        statement = select(EventAttendeeUserState).where(
            EventAttendeeUserState.organisation_id == organisation_id,
            EventAttendeeUserState.event_id == event_id,
            EventAttendeeUserState.attendee_id == attendee_id,
            EventAttendeeUserState.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EventAttendeeUserState | None, await self.session.scalar(statement))

    async def encounters(self, organisation_id: UUID, event_id: UUID, attendee_ids: list[UUID]) -> list[EventEncounter]:
        if not attendee_ids:
            return []
        values = await self.session.scalars(
            select(EventEncounter).where(
                EventEncounter.organisation_id == organisation_id,
                EventEncounter.event_id == event_id,
                EventEncounter.attendee_id.in_(attendee_ids),
            )
        )
        return list(values.all())

    async def encounter(
        self,
        organisation_id: UUID,
        event_id: UUID,
        attendee_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> EventEncounter | None:
        statement = select(EventEncounter).where(
            EventEncounter.organisation_id == organisation_id,
            EventEncounter.event_id == event_id,
            EventEncounter.attendee_id == attendee_id,
            EventEncounter.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EventEncounter | None, await self.session.scalar(statement))

    async def contacts_by_emails(self, organisation_id: UUID, emails: list[str]) -> list[Contact]:
        if not emails:
            return []
        values = await self.session.scalars(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                func.lower(Contact.email).in_(emails),
            )
        )
        return list(values.all())

    async def contacts_by_ids(self, organisation_id: UUID, contact_ids: list[UUID]) -> list[Contact]:
        if not contact_ids:
            return []
        values = await self.session.scalars(
            select(Contact).where(Contact.organisation_id == organisation_id, Contact.id.in_(contact_ids))
        )
        return list(values.all())

    async def possible_contacts_by_names(self, organisation_id: UUID, first_names: list[str]) -> list[Contact]:
        if not first_names:
            return []
        values = await self.session.scalars(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                func.lower(Contact.first_name).in_(first_names),
            )
        )
        return list(values.all())

    async def companies_by_domains(self, organisation_id: UUID, domains: list[str]) -> list[Company]:
        if not domains:
            return []
        values = await self.session.scalars(
            select(Company).where(
                Company.organisation_id == organisation_id,
                Company.normalized_domain.in_(domains),
            )
        )
        return list(values.all())

    async def companies_by_ids(self, organisation_id: UUID, company_ids: list[UUID]) -> list[Company]:
        if not company_ids:
            return []
        values = await self.session.scalars(
            select(Company).where(Company.organisation_id == organisation_id, Company.id.in_(company_ids))
        )
        return list(values.all())

    async def prospect_people_by_profiles(self, organisation_id: UUID, profiles: list[str]) -> list[ProspectPerson]:
        if not profiles:
            return []
        values = await self.session.scalars(
            select(ProspectPerson).where(
                ProspectPerson.organisation_id == organisation_id,
                ProspectPerson.public_profile_url.in_(profiles),
                ProspectPerson.employment_state == "current",
            )
        )
        return list(values.all())

    async def target_priority_by_domains(self, organisation_id: UUID, domains: list[str]) -> dict[str, str]:
        if not domains:
            return {}
        rows = (
            await self.session.execute(
                select(ProspectResearchTarget.normalized_domain, ProspectDiscoveryCandidate.priority)
                .join(
                    ProspectDiscoveryCandidate,
                    and_(
                        ProspectDiscoveryCandidate.organisation_id == ProspectResearchTarget.organisation_id,
                        ProspectDiscoveryCandidate.target_id == ProspectResearchTarget.id,
                    ),
                )
                .where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.normalized_domain.in_(domains),
                    ProspectDiscoveryCandidate.priority.in_(("high", "worth_researching")),
                )
            )
        ).all()
        result: dict[str, str] = {}
        for domain, priority in rows:
            if priority == "high" or domain not in result:
                result[str(domain)] = str(priority)
        return result

    async def open_opportunities_by_companies(
        self, organisation_id: UUID, company_ids: list[UUID]
    ) -> dict[UUID, Opportunity]:
        if not company_ids:
            return {}
        values = await self.session.scalars(
            select(Opportunity)
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.company_id.in_(company_ids),
                Opportunity.status == "open",
            )
            .order_by(Opportunity.updated_at.desc(), Opportunity.id)
        )
        result: dict[UUID, Opportunity] = {}
        for opportunity in values.all():
            if opportunity.company_id is not None:
                result.setdefault(opportunity.company_id, opportunity)
        return result

    async def possible_contact_by_name(
        self, organisation_id: UUID, first_name: str, last_name: str | None, company_id: UUID | None
    ) -> Contact | None:
        statement = select(Contact).where(
            Contact.organisation_id == organisation_id,
            func.lower(Contact.first_name) == first_name.casefold(),
        )
        if last_name:
            statement = statement.where(func.lower(Contact.last_name) == last_name.casefold())
        if company_id:
            statement = statement.where(Contact.company_id == company_id)
        return cast(Contact | None, await self.session.scalar(statement.limit(1)))

    async def company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
            ),
        )

    async def contact(self, organisation_id: UUID, contact_id: UUID) -> Contact | None:
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact).where(Contact.organisation_id == organisation_id, Contact.id == contact_id)
            ),
        )

    async def event_campaigns(self, organisation_id: UUID, event_id: UUID) -> list[EventCampaignRecord]:
        return (await self.event_campaigns_for_events(organisation_id, [event_id])).get(event_id, [])

    async def event_campaigns_for_events(
        self, organisation_id: UUID, event_ids: list[UUID]
    ) -> dict[UUID, list[EventCampaignRecord]]:
        if not event_ids:
            return {}
        rows = (
            await self.session.execute(
                select(EventCampaignLink, EngageCampaign, EngageCampaignVersion)
                .join(
                    EngageCampaign,
                    and_(
                        EngageCampaign.organisation_id == EventCampaignLink.organisation_id,
                        EngageCampaign.id == EventCampaignLink.campaign_id,
                    ),
                )
                .join(
                    EngageCampaignVersion,
                    and_(
                        EngageCampaignVersion.organisation_id == EngageCampaign.organisation_id,
                        EngageCampaignVersion.campaign_id == EngageCampaign.id,
                        EngageCampaignVersion.version == EngageCampaign.current_version,
                    ),
                )
                .where(
                    EventCampaignLink.organisation_id == organisation_id,
                    EventCampaignLink.event_id.in_(event_ids),
                )
                .order_by(EventCampaignLink.created_at, EventCampaignLink.id)
            )
        ).all()
        result: dict[UUID, list[EventCampaignRecord]] = {event_id: [] for event_id in event_ids}
        for link, campaign, version in rows:
            result[link.event_id].append(EventCampaignRecord(link, campaign, version))
        return result

    async def preserved_counts(self, organisation_id: UUID, event_id: UUID) -> tuple[int, int, int]:
        contacts = int(
            await self.session.scalar(
                select(func.count(func.distinct(EventAttendee.contact_id))).where(
                    EventAttendee.organisation_id == organisation_id,
                    EventAttendee.event_id == event_id,
                    EventAttendee.contact_id.is_not(None),
                )
            )
            or 0
        )
        interactions = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Interaction)
                .where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.event_id == event_id,
                )
            )
            or 0
        )
        campaigns = int(
            await self.session.scalar(
                select(func.count())
                .select_from(EventCampaignLink)
                .where(
                    EventCampaignLink.organisation_id == organisation_id,
                    EventCampaignLink.event_id == event_id,
                )
            )
            or 0
        )
        return contacts, interactions, campaigns

    def add(self, record: object) -> None:
        self.session.add(record)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh_event(self, event: SalesEvent) -> None:
        await self.session.refresh(event)

    async def delete(self, record: object) -> None:
        await self.session.delete(record)
