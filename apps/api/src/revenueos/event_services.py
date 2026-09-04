from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.crm_history import crm_creation_changes
from revenueos.domain import (
    EventAttendeeMatchState,
    EventAttendeePriority,
    EventGoal,
    EventPlanState,
    EventState,
    EventType,
)
from revenueos.errors import PublicAPIError
from revenueos.event_contracts import (
    EventAttendeeListResponse,
    EventAttendeePlanRequest,
    EventAttendeePromotionRequest,
    EventAttendeePromotionResponse,
    EventAttendeeResponse,
    EventCampaignResponse,
    EventCreateRequest,
    EventDeleteResponse,
    EventEncounterRequest,
    EventImportColumnResponse,
    EventImportConfirmRequest,
    EventImportConfirmResponse,
    EventImportIssueResponse,
    EventImportPreviewRequest,
    EventImportPreviewResponse,
    EventImportPreviewRowResponse,
    EventListResponse,
    EventOutreachRequest,
    EventOutreachResponse,
    EventResponse,
    EventSummaryResponse,
    EventUpdateRequest,
)
from revenueos.event_import import (
    AUTHORITY_STATEMENT,
    PERMISSION_NOTICE,
    EventImportError,
    ParsedAttendeeRow,
    decode_csv,
    is_strong_business_email,
    parse_event_csv,
)
from revenueos.event_repositories import EventCampaignRecord, EventRepository
from revenueos.models import (
    Company,
    Contact,
    ContactFieldSource,
    EventAttendee,
    EventAttendeeImport,
    EventAttendeeUserState,
    EventEncounter,
    Interaction,
    SalesEvent,
)
from revenueos.outreach_services import OutreachService
from revenueos.prospect_url_security import PublicUrlSafetyError, canonicalize_public_https_url
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.events")

_RELEVANT_ROLE_TERMS = frozenset(
    {
        "chief",
        "cio",
        "cto",
        "ciso",
        "cfo",
        "director",
        "vice president",
        "vp",
        "head",
        "procurement",
        "security",
        "operations",
        "technology",
        "facilities",
        "finance",
        "partner",
        "alliances",
    }
)


class EventService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = EventRepository(session)

    async def list_events(self, *, search: str | None) -> EventListResponse:
        read_only = await self._require_read_access()
        records = await self.repository.events(self.tenant.organisation_id, search=search)
        event_ids = [record.id for record in records]
        summaries = await self.repository.event_summary_counts(
            self.tenant.organisation_id, event_ids, self.tenant.user_id
        )
        campaigns = await self.repository.event_campaigns_for_events(self.tenant.organisation_id, event_ids)
        prospect_access = await CommercialService(self.session, self.settings).module_access(
            self.tenant.organisation_id, "prospect"
        )
        prospect_available = prospect_access == "write" and self.settings.feature_prospect_enabled
        return EventListResponse(
            items=[
                await self._event_response(
                    record,
                    read_only=read_only,
                    summary_values=summaries.get(record.id),
                    campaigns=campaigns.get(record.id, []),
                    prospect_available=prospect_available,
                )
                for record in records
            ],
            total=len(records),
            can_create=not read_only,
            read_only=read_only,
            max_active_events=self.settings.private_beta_max_active_events_per_organisation,
        )

    async def create_event(self, request: EventCreateRequest) -> EventResponse:
        await self._require_write_access()
        if (
            await self.repository.active_event_count(self.tenant.organisation_id)
            >= self.settings.private_beta_max_active_events_per_organisation
        ):
            raise PublicAPIError(
                "active_event_limit",
                "The organisation's active and upcoming Event limit has been reached.",
                429,
            )
        event_url = self._safe_event_url(request.event_url)
        event = SalesEvent(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            owner_user_id=self.tenant.user_id,
            name=request.name,
            event_type=request.event_type.value,
            start_at=request.start_at,
            end_at=request.end_at,
            timezone=request.timezone,
            location_name=request.location_name,
            city=request.city,
            country=request.country,
            event_url=event_url,
            organiser=request.organiser,
            description=request.description,
            goal_type=request.goal_type.value if request.goal_type is not None else None,
            goal_detail=request.goal_detail,
            source_type="manual",
            state=request.state.value,
        )
        self.repository.add(event)
        await self._commit("The Event could not be created.")
        logger.info(
            "event_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event.id),
                "event_type": event.event_type,
                "state": event.state,
            },
        )
        return await self._event_response(event, read_only=False)

    async def get_event(self, event_id: UUID) -> EventResponse:
        read_only = await self._require_read_access()
        return await self._event_response(await self._event(event_id), read_only=read_only)

    async def update_event(self, event_id: UUID, request: EventUpdateRequest) -> EventResponse:
        await self._require_write_access()
        event = await self._event(event_id, for_update=True)
        self._require_event_manager(event)
        values = request.model_dump(exclude_unset=True)
        for key in ("event_type", "goal_type", "state"):
            if key in values and values[key] is not None:
                values[key] = values[key].value
        start_at = cast(datetime, values.get("start_at", event.start_at))
        end_at = cast(datetime, values.get("end_at", event.end_at))
        if end_at < start_at or end_at - start_at > timedelta(days=30):
            raise PublicAPIError(
                "invalid_event_range", "An Event must end after it starts and span at most 30 days.", 422
            )
        if "event_url" in values:
            values["event_url"] = self._safe_event_url(cast(str | None, values["event_url"]))
        target_goal_type = cast(str | None, values.get("goal_type", event.goal_type))
        target_goal_detail = cast(str | None, values.get("goal_detail", event.goal_detail))
        if target_goal_type == EventGoal.OTHER.value and not target_goal_detail:
            raise PublicAPIError(
                "event_goal_detail_required",
                "Describe the bounded Event goal when choosing Other.",
                422,
            )
        target_state = cast(str, values.get("state", event.state))
        values["archived_at"] = datetime.now(UTC) if target_state == "archived" else None
        for key, value in values.items():
            setattr(event, key, value)
        await self._commit("The Event could not be updated.")
        await self.repository.refresh_event(event)
        return await self._event_response(event, read_only=False)

    async def preview_import(
        self,
        event_id: UUID,
        request: EventImportPreviewRequest,
    ) -> EventImportPreviewResponse:
        await self._require_write_access()
        await self._event(event_id)
        try:
            safe_name, content = decode_csv(request.file_name, request.content_base64)
            preview = parse_event_csv(safe_name, content, request.column_mapping)
        except EventImportError as exc:
            status = 413 if exc.code in {"file_too_large", "too_many_rows", "too_many_columns"} else 422
            raise PublicAPIError(exc.code, exc.message, status) from exc
        now = datetime.now(UTC)
        record = await self.repository.import_by_fingerprint(
            self.tenant.organisation_id,
            event_id,
            preview.file_fingerprint,
            for_update=True,
        )
        if record is not None and record.state == "confirmed":
            raise PublicAPIError(
                "attendee_list_already_imported",
                "This attendee list has already been imported for the Event.",
                409,
            )
        if record is None:
            record = EventAttendeeImport(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                event_id=event_id,
                requested_by_user_id=self.tenant.user_id,
                state="previewed",
                display_filename=preview.file_name,
                file_fingerprint=preview.file_fingerprint,
                file_size_bytes=preview.file_size_bytes,
                row_count=preview.row_count,
                valid_row_count=len(preview.rows),
                imported_row_count=0,
                column_mapping_json=cast(dict[str, object], preview.mapping),
                recognised_columns_json=[item.json() for item in preview.recognised],
                ignored_columns_json=[item.json() for item in preview.ignored],
                issues_json=[item.json() for item in preview.issues],
                preview_rows_json=[row.json() for row in preview.rows],
                expires_at=now + timedelta(hours=1),
            )
            self.repository.add(record)
        else:
            record.state = "previewed"
            record.requested_by_user_id = self.tenant.user_id
            record.display_filename = preview.file_name
            record.file_size_bytes = preview.file_size_bytes
            record.row_count = preview.row_count
            record.valid_row_count = len(preview.rows)
            record.imported_row_count = 0
            record.column_mapping_json = cast(dict[str, object], preview.mapping)
            record.recognised_columns_json = [item.json() for item in preview.recognised]
            record.ignored_columns_json = [item.json() for item in preview.ignored]
            record.issues_json = [item.json() for item in preview.issues]
            record.preview_rows_json = [row.json() for row in preview.rows]
            record.expires_at = now + timedelta(hours=1)
            record.attestation_version = None
            record.attested_by_user_id = None
            record.attested_at = None
        await self._commit("The attendee preview could not be saved.")
        logger.info(
            "attendee_import_started",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "import_id": str(record.id),
                "row_count": preview.row_count,
                "valid_row_count": len(preview.rows),
                "recognised_column_count": len(preview.recognised),
                "ignored_column_count": len(preview.ignored),
            },
        )
        return self._preview_response(record, already_imported=False)

    async def get_import_preview(self, event_id: UUID, import_id: UUID) -> EventImportPreviewResponse:
        await self._require_write_access()
        record = await self.repository.event_import(self.tenant.organisation_id, event_id, import_id)
        if record is None or record.state != "previewed":
            raise PublicAPIError("attendee_preview_not_found", "The attendee import preview was not found.", 404)
        if self._normalise_datetime(record.expires_at) <= datetime.now(UTC):
            record.state = "expired"
            record.preview_rows_json = []
            await self._commit("The attendee preview could not be expired.")
            raise PublicAPIError(
                "attendee_preview_expired", "This attendee preview expired. Upload the CSV again.", 410
            )
        return self._preview_response(record, already_imported=False)

    async def confirm_import(
        self,
        event_id: UUID,
        import_id: UUID,
        request: EventImportConfirmRequest,
    ) -> EventImportConfirmResponse:
        del request
        await self._require_write_access()
        event = await self._event(event_id)
        record = await self.repository.event_import(
            self.tenant.organisation_id,
            event_id,
            import_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError("attendee_preview_not_found", "The attendee import preview was not found.", 404)
        if record.state == "confirmed":
            return await self._confirm_response(record, duplicate_count=0)
        if record.state != "previewed" or self._normalise_datetime(record.expires_at) <= datetime.now(UTC):
            record.state = "expired"
            record.preview_rows_json = []
            await self._commit("The attendee preview could not be expired.")
            raise PublicAPIError(
                "attendee_preview_expired", "This attendee preview expired. Upload the CSV again.", 410
            )
        today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        if (
            await self.repository.confirmed_imports_since(self.tenant.organisation_id, event_id, today)
            >= self.settings.private_beta_max_event_imports_per_day
        ):
            raise PublicAPIError("event_import_limit", "The Event's attendee import limit has been reached today.", 429)
        existing_count = await self.repository.attendee_count(self.tenant.organisation_id, event_id)
        parsed_rows = [self._parsed_row(value) for value in record.preview_rows_json]
        existing_attendees = await self.repository.all_attendees(self.tenant.organisation_id, event_id)
        existing_emails = {
            item.normalised_business_email for item in existing_attendees if item.normalised_business_email is not None
        }
        existing_profiles = {
            item.normalised_profile_url for item in existing_attendees if item.normalised_profile_url is not None
        }
        rows = [
            item
            for item in parsed_rows
            if not (
                item.business_email
                and is_strong_business_email(item.business_email)
                and item.business_email in existing_emails
            )
            and item.profile_url not in existing_profiles
        ]
        duplicate_count = len(parsed_rows) - len(rows)
        if existing_count + len(rows) > self.settings.private_beta_max_event_attendees:
            raise PublicAPIError(
                "event_attendee_limit",
                f"An Event may contain at most {self.settings.private_beta_max_event_attendees} attendees.",
                413,
            )
        emails = [
            item.business_email
            for item in rows
            if item.business_email and is_strong_business_email(item.business_email)
        ]
        domains = [item.company_domain for item in rows if item.company_domain]
        profiles = [item.profile_url for item in rows if item.profile_url]
        contacts = await self.repository.contacts_by_emails(self.tenant.organisation_id, emails)
        companies = await self.repository.companies_by_domains(self.tenant.organisation_id, domains)
        people = await self.repository.prospect_people_by_profiles(self.tenant.organisation_id, profiles)
        contact_by_email = {item.email.casefold(): item for item in contacts if item.email}
        company_by_domain = {item.normalized_domain: item for item in companies if item.normalized_domain}
        person_by_profile = {item.public_profile_url: item for item in people if item.public_profile_url}
        promoted_contact_ids = [item.promoted_contact_id for item in people if item.promoted_contact_id is not None]
        promoted_contacts = await self.repository.contacts_by_ids(self.tenant.organisation_id, promoted_contact_ids)
        contact_by_id = {item.id: item for item in (*contacts, *promoted_contacts)}
        company_ids = list({item.id for item in companies} | {item.company_id for item in contact_by_id.values()})
        companies_by_id = {
            item.id: item for item in await self.repository.companies_by_ids(self.tenant.organisation_id, company_ids)
        }
        possible_contacts = await self.repository.possible_contacts_by_names(
            self.tenant.organisation_id,
            list({item.first_name.casefold() for item in rows if item.first_name}),
        )
        possible_names_without_company = {
            (item.first_name.casefold(), item.last_name.casefold()) for item in possible_contacts
        }
        active_opportunities = await self.repository.open_opportunities_by_companies(
            self.tenant.organisation_id, company_ids
        )
        target_priorities = await self.repository.target_priority_by_domains(self.tenant.organisation_id, domains)
        imported: list[EventAttendee] = []
        for row in rows:
            strong_email = (
                row.business_email if row.business_email and is_strong_business_email(row.business_email) else None
            )
            contact = contact_by_email.get(strong_email or "")
            person = person_by_profile.get(row.profile_url or "")
            company = (
                companies_by_id.get(contact.company_id)
                if contact is not None
                else company_by_domain.get(row.company_domain or "")
            )
            if person is not None and contact is None and person.promoted_contact_id is not None:
                contact = contact_by_id.get(person.promoted_contact_id)
                if contact is not None:
                    company = companies_by_id.get(contact.company_id)
            if contact is not None:
                match_state = EventAttendeeMatchState.MATCHED_CONTACT
            elif person is not None:
                match_state = EventAttendeeMatchState.MATCHED_PROSPECT_PERSON
            elif company is not None:
                match_state = EventAttendeeMatchState.MATCHED_COMPANY
            else:
                possible = bool(
                    row.first_name
                    and (row.first_name.casefold(), (row.last_name or "").casefold()) in possible_names_without_company
                )
                match_state = EventAttendeeMatchState.POSSIBLE_MATCH if possible else EventAttendeeMatchState.UNMATCHED
            opportunity = active_opportunities.get(company.id) if company is not None else None
            priority, reasons = self._priority(event, row, contact, company, opportunity, target_priorities)
            attendee = EventAttendee(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                event_id=event_id,
                import_id=record.id,
                first_name=row.first_name,
                last_name=row.last_name,
                company_name=row.company_name,
                job_title=row.job_title,
                business_email=row.business_email,
                normalised_business_email=strong_email,
                country_or_location=row.country_or_location,
                profile_url=row.profile_url,
                normalised_profile_url=row.profile_url,
                company_domain=row.company_domain,
                registration_category=row.registration_category,
                source_row=row.source_row,
                source_type="event_list",
                email_trust_state="provider_supplied" if row.business_email else "unknown",
                contact_id=contact.id if contact is not None else None,
                company_id=company.id if company is not None else None,
                prospect_person_id=person.id if person is not None else None,
                match_state=match_state.value,
                priority_state=priority.value,
                priority_reasons_json=reasons,
                active_opportunity_id=opportunity.id if opportunity is not None else None,
            )
            self.repository.add(attendee)
            imported.append(attendee)
        now = datetime.now(UTC)
        record.state = "confirmed"
        record.imported_row_count = len(imported)
        record.attestation_version = 1
        record.attested_by_user_id = self.tenant.user_id
        record.attested_at = now
        record.confirmed_at = now
        record.preview_rows_json = []
        await self._commit("The attendee list could not be imported.")
        logger.info(
            "attendee_import_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "import_id": str(record.id),
                "imported_count": len(imported),
                "duplicate_count": duplicate_count,
                "attestation_version": 1,
            },
        )
        return await self._confirm_response(record, duplicate_count=duplicate_count)

    async def list_attendees(
        self,
        event_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        priority: str | None,
        plan_state: str | None,
    ) -> EventAttendeeListResponse:
        await self._require_read_access()
        await self._event(event_id)
        items, total = await self.repository.attendees(
            self.tenant.organisation_id,
            event_id,
            page=page,
            page_size=page_size,
            search=search,
            priority=priority,
            plan_state=plan_state,
            user_id=self.tenant.user_id,
        )
        responses = await self._attendee_responses(event_id, items)
        return EventAttendeeListResponse(items=responses, total=total, page=page, page_size=page_size)

    async def get_attendee(self, event_id: UUID, attendee_id: UUID) -> EventAttendeeResponse:
        await self._require_read_access()
        await self._event(event_id)
        attendee = await self._attendee(event_id, attendee_id)
        return (await self._attendee_responses(event_id, [attendee]))[0]

    async def plan_attendee(
        self,
        event_id: UUID,
        attendee_id: UUID,
        request: EventAttendeePlanRequest,
    ) -> EventAttendeeResponse:
        await self._require_write_access()
        await self._event(event_id)
        await self._attendee(event_id, attendee_id)
        state = await self.repository.user_state(
            self.tenant.organisation_id,
            event_id,
            attendee_id,
            self.tenant.user_id,
            for_update=True,
        )
        if state is None:
            state = EventAttendeeUserState(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                event_id=event_id,
                attendee_id=attendee_id,
                user_id=self.tenant.user_id,
                plan_state=request.plan_state.value,
                meeting_arranged=request.meeting_arranged,
            )
            self.repository.add(state)
        else:
            state.plan_state = request.plan_state.value
            state.meeting_arranged = request.meeting_arranged
        await self._commit("The Event plan could not be saved.")
        logger.info(
            "event_plan_saved",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "attendee_id": str(attendee_id),
                "plan_state": state.plan_state,
            },
        )
        return await self.get_attendee(event_id, attendee_id)

    async def record_encounter(
        self,
        event_id: UUID,
        attendee_id: UUID,
        request: EventEncounterRequest,
    ) -> EventAttendeeResponse:
        await self._require_write_access()
        event = await self._event(event_id)
        attendee = await self._attendee(event_id, attendee_id)
        occurred_at = request.occurred_at or datetime.now(UTC)
        encounter = await self.repository.encounter(
            self.tenant.organisation_id,
            event_id,
            attendee_id,
            self.tenant.user_id,
            for_update=True,
        )
        if encounter is None:
            encounter = EventEncounter(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                event_id=event_id,
                attendee_id=attendee_id,
                user_id=self.tenant.user_id,
                state=request.state,
                occurred_at=occurred_at,
                seller_note=request.seller_note,
                note_origin="seller_reported_activity",
            )
            self.repository.add(encounter)
        else:
            encounter.state = request.state
            encounter.occurred_at = occurred_at
            if request.seller_note is not None:
                encounter.seller_note = request.seller_note
        if request.create_interaction and encounter.interaction_id is None:
            completed = request.interaction_lifecycle == "completed"
            interaction = Interaction(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                company_id=attendee.company_id,
                opportunity_id=attendee.active_opportunity_id,
                contact_id=None,
                event_id=event_id,
                interaction_type=(
                    "trade_show_interaction" if event.event_type == "trade_show" else "conference_interaction"
                ),
                lifecycle_status=request.interaction_lifecycle,
                title=f"Conversation at {event.name}",
                scheduled_start_at=None if completed else occurred_at,
                scheduled_end_at=None,
                actual_start_at=occurred_at if completed else None,
                actual_end_at=occurred_at if completed else None,
                timezone=event.timezone,
                creation_origin="manual",
                call_direction=None,
                call_outcome=None,
                created_by_user_id=self.tenant.user_id,
            )
            self.repository.add(interaction)
            await self.repository.flush()
            encounter.interaction_id = interaction.id
        plan_state = {
            "met": EventPlanState.MET.value,
            "follow_up": EventPlanState.FOLLOW_UP.value,
            "complete": EventPlanState.COMPLETE.value,
        }[request.state]
        state = await self.repository.user_state(
            self.tenant.organisation_id,
            event_id,
            attendee_id,
            self.tenant.user_id,
            for_update=True,
        )
        if state is None:
            self.repository.add(
                EventAttendeeUserState(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    event_id=event_id,
                    attendee_id=attendee_id,
                    user_id=self.tenant.user_id,
                    plan_state=plan_state,
                    meeting_arranged=False,
                )
            )
        else:
            state.plan_state = plan_state
        await self._commit("The Event encounter could not be saved.")
        logger.info(
            "attendee_marked_met",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "attendee_id": str(attendee_id),
                "encounter_state": request.state,
                "interaction_created": encounter.interaction_id is not None,
            },
        )
        return await self.get_attendee(event_id, attendee_id)

    async def promote_attendee(
        self,
        event_id: UUID,
        attendee_id: UUID,
        request: EventAttendeePromotionRequest,
    ) -> EventAttendeePromotionResponse:
        await self._require_write_access()
        await self._event(event_id)
        attendee = await self._attendee(event_id, attendee_id, for_update=True)
        if attendee.contact_id is not None:
            contact = await self.repository.contact(self.tenant.organisation_id, attendee.contact_id)
            if contact is None:
                raise PublicAPIError("event_contact_inconsistent", "The linked Contact could not be found.", 409)
            return EventAttendeePromotionResponse(
                status="already_promoted",
                attendee_id=attendee.id,
                contact_id=contact.id,
                company_id=contact.company_id,
                message="This attendee is already linked to a canonical Contact.",
            )
        if attendee.business_email and is_strong_business_email(attendee.business_email):
            matches = await self.repository.contacts_by_emails(
                self.tenant.organisation_id, [attendee.business_email.casefold()]
            )
            if matches:
                contact = matches[0]
                attendee.contact_id = contact.id
                attendee.company_id = contact.company_id
                attendee.match_state = EventAttendeeMatchState.MATCHED_CONTACT.value
                await self._commit("The attendee could not be linked to the existing Contact.")
                return EventAttendeePromotionResponse(
                    status="linked",
                    attendee_id=attendee.id,
                    contact_id=contact.id,
                    company_id=contact.company_id,
                    message="The exact business email matched an existing Contact. No fields were overwritten.",
                )
        if not attendee.first_name or not attendee.last_name:
            raise PublicAPIError(
                "attendee_name_required",
                "Review and provide both first and last name before adding this attendee to Sales.",
                409,
            )
        company = await self._promotion_company(attendee, request)
        now = datetime.now(UTC)
        contact = Contact(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            company_id=company.id,
            first_name=attendee.first_name,
            last_name=attendee.last_name,
            email=(
                attendee.business_email
                if attendee.business_email and is_strong_business_email(attendee.business_email)
                else None
            ),
            phone=None,
            job_title=attendee.job_title,
            linkedin_url=attendee.profile_url,
            owner_user_id=self.tenant.user_id,
        )
        self.repository.add(contact)
        await self.repository.flush()
        for change in crm_creation_changes(
            self.tenant.organisation_id,
            self.tenant.user_id,
            "contact",
            contact.id,
            "event_promotion",
            {
                "company_id": contact.company_id,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "job_title": contact.job_title,
                "linkedin_url": contact.linkedin_url,
                "status": contact.status,
                "owner_user_id": contact.owner_user_id,
            },
        ):
            self.repository.add(change)
        for field_key, value, trust in (
            ("email", contact.email, attendee.email_trust_state),
            ("job_title", contact.job_title, "provider_supplied"),
            ("linkedin_url", contact.linkedin_url, "provider_supplied"),
        ):
            if value is None:
                continue
            self.repository.add(
                ContactFieldSource(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    contact_id=contact.id,
                    field_key=field_key,
                    value_fingerprint=hashlib.sha256(value.casefold().encode()).hexdigest(),
                    source_type="event_list",
                    source_organisation_id=None,
                    source_prospect_person_id=None,
                    provider_key="event_list",
                    trust_state=trust,
                    observed_at=attendee.created_at,
                    verified_at=None,
                    active=True,
                    created_at=now,
                )
            )
        attendee.contact_id = contact.id
        attendee.company_id = company.id
        attendee.match_state = EventAttendeeMatchState.MATCHED_CONTACT.value
        await self._commit("The attendee could not be added to Sales.")
        logger.info(
            "event_attendee_promoted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "attendee_id": str(attendee_id),
                "contact_id": str(contact.id),
                "company_created": request.create_company,
            },
        )
        return EventAttendeePromotionResponse(
            status="created",
            attendee_id=attendee.id,
            contact_id=contact.id,
            company_id=company.id,
            message=(
                "The attendee was added to Sales with Event-list provenance. No Opportunity, Evidence, "
                "Methodology field or outreach was created."
            ),
        )

    async def create_event_outreach(
        self,
        event_id: UUID,
        attendee_id: UUID,
        request: EventOutreachRequest,
    ) -> EventOutreachResponse:
        await self._require_write_access()
        event = await self._event(event_id)
        attendee = await self._attendee(event_id, attendee_id)
        if attendee.contact_id is None:
            raise PublicAPIError(
                "canonical_contact_required",
                "Add the attendee to Sales before creating Event outreach. Raw attendee rows cannot be sent.",
                409,
            )
        encounter = await self.repository.encounter(
            self.tenant.organisation_id,
            event_id,
            attendee_id,
            self.tenant.user_id,
        )
        met = encounter is not None
        local_date = self._normalise_datetime(event.start_at).astimezone(ZoneInfo(event.timezone))
        outreach_service = OutreachService(self.session, self.tenant, self.settings)
        record = await outreach_service.prepare_event_draft(
            attendee.contact_id,
            event_id=event.id,
            attendee_id=attendee.id,
            event_name=event.name,
            event_date_label=f"{local_date.day} {local_date:%B %Y}",
            stage=request.stage,
            met=met,
            encounter_id=encounter.id if encounter is not None else None,
        )
        await self._commit("The Event outreach draft could not be created.")
        logger.info(
            "event_followup_created" if request.stage == "post_event" else "event_meeting_request_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "attendee_id": str(attendee_id),
                "outreach_id": str(record.message.id),
                "met_claim_supported": met,
            },
        )
        return EventOutreachResponse(stage=request.stage, outreach=await outreach_service.get(record.message.id))

    async def delete_event(self, event_id: UUID) -> EventDeleteResponse:
        await self._require_write_access()
        event = await self._event(event_id, for_update=True)
        self._require_event_manager(event)
        contacts, interactions, campaigns = await self.repository.preserved_counts(
            self.tenant.organisation_id, event_id
        )
        await self.session.execute(
            update(Interaction)
            .where(Interaction.organisation_id == self.tenant.organisation_id, Interaction.event_id == event_id)
            .values(event_id=None)
        )
        await self.repository.delete(event)
        await self._commit("The Event could not be deleted.")
        logger.info(
            "event_deleted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "event_id": str(event_id),
                "preserved_contact_count": contacts,
                "preserved_interaction_count": interactions,
                "preserved_campaign_count": campaigns,
            },
        )
        return EventDeleteResponse(
            preserved_contacts=contacts,
            preserved_interactions=interactions,
            preserved_campaigns=campaigns,
        )

    async def _event_response(
        self,
        event: SalesEvent,
        *,
        read_only: bool,
        summary_values: dict[str, int] | None = None,
        campaigns: list[EventCampaignRecord] | None = None,
        prospect_available: bool | None = None,
    ) -> EventResponse:
        if summary_values is None:
            summary_values = (
                await self.repository.event_summary_counts(self.tenant.organisation_id, [event.id], self.tenant.user_id)
            )[event.id]
        if campaigns is None:
            campaigns = await self.repository.event_campaigns(self.tenant.organisation_id, event.id)
        if prospect_available is None:
            prospect_access = await CommercialService(self.session, self.settings).module_access(
                self.tenant.organisation_id, "prospect"
            )
            prospect_available = prospect_access == "write" and self.settings.feature_prospect_enabled
        summary = EventSummaryResponse(**summary_values)
        return EventResponse(
            id=event.id,
            name=event.name,
            event_type=EventType(event.event_type),
            start_at=self._normalise_datetime(event.start_at),
            end_at=self._normalise_datetime(event.end_at),
            timezone=event.timezone,
            location_name=event.location_name,
            city=event.city,
            country=event.country,
            event_url=event.event_url,
            organiser=event.organiser,
            description=event.description,
            goal_type=EventGoal(event.goal_type) if event.goal_type is not None else None,
            goal_detail=event.goal_detail,
            source_type="manual",
            state=self._effective_state(event),
            owner_user_id=event.owner_user_id,
            read_only=read_only,
            prospect_enrichment_available=prospect_available,
            summary=summary,
            campaigns=[
                EventCampaignResponse(
                    campaign_id=item.campaign.id,
                    name=item.version.name,
                    state=item.campaign.state,
                    stage=cast(Literal["pre_event", "post_event"], item.link.stage),
                )
                for item in campaigns
            ],
            created_at=self._normalise_datetime(event.created_at),
            updated_at=self._normalise_datetime(event.updated_at),
        )

    async def _attendee_responses(self, event_id: UUID, attendees: list[EventAttendee]) -> list[EventAttendeeResponse]:
        ids = [item.id for item in attendees]
        states = await self.repository.user_states(self.tenant.organisation_id, event_id, ids)
        encounters = await self.repository.encounters(self.tenant.organisation_id, event_id, ids)
        own_states = {item.attendee_id: item for item in states if item.user_id == self.tenant.user_id}
        teammate_counts: dict[UUID, int] = {}
        for teammate_state in states:
            if teammate_state.user_id != self.tenant.user_id and teammate_state.plan_state in {
                "planned",
                "met",
                "follow_up",
            }:
                teammate_counts[teammate_state.attendee_id] = teammate_counts.get(teammate_state.attendee_id, 0) + 1
        own_encounters = {item.attendee_id: item for item in encounters if item.user_id == self.tenant.user_id}
        prospect_access = await CommercialService(self.session, self.settings).module_access(
            self.tenant.organisation_id, "prospect"
        )
        can_research = prospect_access == "write" and self.settings.feature_prospect_enabled
        responses: list[EventAttendeeResponse] = []
        for attendee in attendees:
            state = own_states.get(attendee.id)
            encounter = own_encounters.get(attendee.id)
            name = " ".join(item for item in (attendee.first_name, attendee.last_name) if item) or "Unnamed attendee"
            responses.append(
                EventAttendeeResponse(
                    id=attendee.id,
                    event_id=event_id,
                    first_name=attendee.first_name,
                    last_name=attendee.last_name,
                    display_name=name,
                    company_name=attendee.company_name,
                    job_title=attendee.job_title,
                    business_email=attendee.business_email,
                    email_trust_state=cast(Literal["provider_supplied", "unknown"], attendee.email_trust_state),
                    country_or_location=attendee.country_or_location,
                    profile_url=attendee.profile_url,
                    company_domain=attendee.company_domain,
                    registration_category=attendee.registration_category,
                    match_state=EventAttendeeMatchState(attendee.match_state),
                    priority_state=EventAttendeePriority(attendee.priority_state),
                    priority_reasons=[str(item) for item in attendee.priority_reasons_json],
                    contact_id=attendee.contact_id,
                    company_id=attendee.company_id,
                    prospect_person_id=attendee.prospect_person_id,
                    active_opportunity_id=attendee.active_opportunity_id,
                    plan_state=(EventPlanState(state.plan_state) if state is not None else EventPlanState.NOT_PLANNED),
                    meeting_arranged=state.meeting_arranged if state is not None else False,
                    planned_by_teammate_count=teammate_counts.get(attendee.id, 0),
                    encounter_id=encounter.id if encounter is not None else None,
                    interaction_id=encounter.interaction_id if encounter is not None else None,
                    seller_note=encounter.seller_note if encounter is not None else None,
                    can_research=can_research,
                    created_at=self._normalise_datetime(attendee.created_at),
                )
            )
        return responses

    async def _confirm_response(
        self, record: EventAttendeeImport, *, duplicate_count: int
    ) -> EventImportConfirmResponse:
        attendees = [
            item
            for item in await self.repository.all_attendees(self.tenant.organisation_id, record.event_id)
            if item.import_id == record.id
        ]
        assert record.attested_at is not None
        return EventImportConfirmResponse(
            import_id=record.id,
            event_id=record.event_id,
            imported_count=record.imported_row_count,
            duplicate_count=duplicate_count,
            matched_contact_count=sum(item.match_state == "matched_contact" for item in attendees),
            matched_company_count=sum(item.match_state == "matched_company" for item in attendees),
            unmatched_count=sum(item.match_state in {"unmatched", "possible_match"} for item in attendees),
            authority_attested_at=self._normalise_datetime(record.attested_at),
            permission_notice=PERMISSION_NOTICE,
        )

    def _preview_response(self, record: EventAttendeeImport, *, already_imported: bool) -> EventImportPreviewResponse:
        recognised = [EventImportColumnResponse.model_validate(item) for item in record.recognised_columns_json]
        ignored = [EventImportColumnResponse.model_validate(item) for item in record.ignored_columns_json]
        issues = [EventImportIssueResponse.model_validate(item) for item in record.issues_json]
        rows = [self._parsed_row(item) for item in record.preview_rows_json[:10]]
        return EventImportPreviewResponse(
            id=record.id,
            event_id=record.event_id,
            file_name=record.display_filename,
            file_size_bytes=record.file_size_bytes,
            row_count=record.row_count,
            valid_row_count=record.valid_row_count,
            recognised=recognised,
            ignored=ignored,
            issues=issues,
            preview_rows=[
                EventImportPreviewRowResponse(
                    source_row=item.source_row,
                    first_name=item.first_name,
                    last_name=item.last_name,
                    company_name=item.company_name,
                    job_title=item.job_title,
                    business_email=item.business_email,
                )
                for item in rows
            ],
            expires_at=self._normalise_datetime(record.expires_at),
            already_imported=already_imported,
            authority_statement=AUTHORITY_STATEMENT,
            permission_notice=PERMISSION_NOTICE,
        )

    async def _promotion_company(self, attendee: EventAttendee, request: EventAttendeePromotionRequest) -> Company:
        company_id = request.company_id or attendee.company_id
        if company_id is not None and not request.create_company:
            company = await self.repository.company(self.tenant.organisation_id, company_id)
            if company is None:
                raise PublicAPIError("company_not_found", "The selected Company was not found.", 404)
            return company
        if not request.create_company:
            raise PublicAPIError(
                "company_review_required",
                "Review and choose an existing Company or explicitly create the attendee's Company.",
                409,
            )
        if not attendee.company_name:
            raise PublicAPIError("company_name_required", "A reviewed company name is required.", 409)
        company = Company(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            name=attendee.company_name,
            website=f"https://{attendee.company_domain}/" if attendee.company_domain else None,
            normalized_domain=attendee.company_domain,
            industry=None,
            employee_count=None,
            status="prospect",
            owner_user_id=self.tenant.user_id,
        )
        self.repository.add(company)
        await self.repository.flush()
        for change in crm_creation_changes(
            self.tenant.organisation_id,
            self.tenant.user_id,
            "account",
            company.id,
            "event_promotion",
            {
                "name": company.name,
                "website": company.website,
                "status": company.status,
                "owner_user_id": company.owner_user_id,
            },
        ):
            self.repository.add(change)
        return company

    @staticmethod
    def _priority(
        event: SalesEvent,
        row: ParsedAttendeeRow,
        contact: Contact | None,
        company: Company | None,
        opportunity: object | None,
        target_priorities: dict[str, str],
    ) -> tuple[EventAttendeePriority, list[str]]:
        role = (row.job_title or "").casefold()
        relevant_role = any(term in role for term in _RELEVANT_ROLE_TERMS)
        reasons: list[str] = []
        if opportunity is not None:
            reasons.append("An active Opportunity exists for this Account.")
        if contact is not None:
            reasons.append("This attendee is an existing Contact.")
        elif company is not None:
            reasons.append("This attendee's company is an existing Account.")
        target_priority = target_priorities.get(row.company_domain or "")
        if target_priority == "high":
            reasons.append("The company is a High Priority Target Market account.")
        elif target_priority == "worth_researching":
            reasons.append("The company matches a current Target Market.")
        if relevant_role:
            reasons.append("The supplied professional role is relevant to a business buying group.")
        if event.goal_type == "reconnect_existing_contacts" and contact is not None:
            reasons.append("The Event goal is to reconnect with existing Contacts.")
        if event.goal_type == "find_partners" and any(term in role for term in ("partner", "alliance")):
            reasons.append("The role aligns with the Event's partner goal.")
        if opportunity is not None or (target_priority == "high" and relevant_role):
            return EventAttendeePriority.PRIORITY_TO_MEET, reasons
        if (contact is not None and relevant_role) or (company is not None and relevant_role) or relevant_role:
            return EventAttendeePriority.WORTH_MEETING, reasons
        if not row.company_name or not row.job_title:
            return EventAttendeePriority.NEEDS_MORE_INFORMATION, reasons or [
                "Company or role information is missing; review before prioritising."
            ]
        return EventAttendeePriority.CONTEXT_ONLY, reasons or [
            "The attendee is available as Event context; no stronger business relevance is established."
        ]

    async def _event(self, event_id: UUID, *, for_update: bool = False) -> SalesEvent:
        event = await self.repository.event(self.tenant.organisation_id, event_id, for_update=for_update)
        if event is None:
            raise PublicAPIError("event_not_found", "The Event was not found.", 404)
        return event

    async def _attendee(self, event_id: UUID, attendee_id: UUID, *, for_update: bool = False) -> EventAttendee:
        attendee = await self.repository.attendee(
            self.tenant.organisation_id, event_id, attendee_id, for_update=for_update
        )
        if attendee is None:
            raise PublicAPIError("event_attendee_not_found", "The Event attendee was not found.", 404)
        return attendee

    async def _require_read_access(self) -> bool:
        if not self.settings.feature_engage_events_enabled:
            raise PublicAPIError("events_unavailable", "Events are unavailable in this environment.", 503)
        access = await CommercialService(self.session, self.settings).module_access(
            self.tenant.organisation_id, "engage"
        )
        if access == "none":
            raise PublicAPIError("events_not_in_plan", "RevenueOS Events requires Engage.", 403)
        return access != "write"

    async def _require_write_access(self) -> None:
        read_only = await self._require_read_access()
        if read_only or not self.settings.feature_engage_enabled:
            raise PublicAPIError(
                "events_read_only",
                "Historical Event data is read-only because Engage is not currently enabled.",
                403,
            )
        await CommercialService(self.session, self.settings).require_module_write(self.tenant.organisation_id, "engage")

    def _require_event_manager(self, event: SalesEvent) -> None:
        if event.owner_user_id != self.tenant.user_id and not self.tenant.can_manage():
            raise PublicAPIError("event_forbidden", "Only the Event owner or an administrator can change it.", 403)

    @staticmethod
    def _safe_event_url(value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return canonicalize_public_https_url(value).url
        except PublicUrlSafetyError as exc:
            raise PublicAPIError(exc.code, exc.args[0], 422) from exc

    @staticmethod
    def _effective_state(event: SalesEvent) -> EventState:
        if event.state in {"draft", "archived"}:
            return EventState(event.state)
        now = datetime.now(UTC)
        start = EventService._normalise_datetime(event.start_at)
        end = EventService._normalise_datetime(event.end_at)
        if now < start:
            return EventState.UPCOMING
        if now <= end:
            return EventState.ACTIVE
        return EventState.COMPLETED

    @staticmethod
    def _normalise_datetime(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _parsed_row(value: object) -> ParsedAttendeeRow:
        data = cast(dict[str, object], value)
        return ParsedAttendeeRow(
            source_row=cast(int, data["source_row"]),
            first_name=cast(str | None, data.get("first_name")),
            last_name=cast(str | None, data.get("last_name")),
            company_name=cast(str | None, data.get("company_name")),
            job_title=cast(str | None, data.get("job_title")),
            business_email=cast(str | None, data.get("business_email")),
            country_or_location=cast(str | None, data.get("country_or_location")),
            profile_url=cast(str | None, data.get("profile_url")),
            company_domain=cast(str | None, data.get("company_domain")),
            registration_category=cast(str | None, data.get("registration_category")),
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("event_conflict", message, 409) from exc
