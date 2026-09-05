from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.crm_contracts import (
    CRMActivityItemResponse,
    CRMArchiveResponse,
    CRMAvailabilityResponse,
    CRMChangeSource,
    CRMCoreFieldResponse,
    CRMCustomFieldCreate,
    CRMCustomFieldDefinitionResponse,
    CRMCustomFieldUpdate,
    CRMCustomFieldValueResponse,
    CRMCustomFieldValueUpdate,
    CRMEntityType,
    CRMFieldAuthority,
    CRMFieldType,
    CRMMemberResponse,
    CRMMode,
    CRMRecordChangeResponse,
    CRMRecordResponse,
    CRMSettingsUpdate,
    validate_custom_url,
)
from revenueos.crm_repositories import CRMRepository
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    Contact,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMRecordChange,
    Opportunity,
    OrganisationCRMSetting,
)
from revenueos.tenant import TenantContext

CRMRecord = Company | Contact | Opportunity
RESERVED_CUSTOM_FIELD_KEYS = {
    "id",
    "organisation_id",
    "created_at",
    "updated_at",
    "archived_at",
    "owner_user_id",
    "name",
    "website",
    "normalized_domain",
    "industry",
    "location",
    "employee_count",
    "status",
    "company_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "job_title",
    "linkedin_url",
    "stage",
    "estimated_value",
    "currency",
    "expected_close_date",
    "description",
    "activity",
    "history",
    "custom_fields",
}


class CRMService:
    """Tenant-aware policy and read models over the canonical business records."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.repository = CRMRepository(session)
        self.tenant = tenant
        self.settings = settings

    async def availability(self) -> CRMAvailabilityResponse:
        commercial = CommercialService(self.session, self.settings)
        core_access = await commercial.module_access(self.tenant.organisation_id, "core")
        connector_access = await commercial.module_access(self.tenant.organisation_id, "crm")
        setting = await self.repository.setting(self.tenant.organisation_id)
        connection = await self.repository.active_hubspot_connection(self.tenant.organisation_id)
        connection_active = connection is not None and connection.connection_status == "active"
        mode = self._effective_mode(setting, connection is not None)
        enabled = core_access == "write" and (mode != "external" or connector_access == "write")
        if not self.settings.feature_native_crm_enabled:
            state = "temporarily_unavailable"
            message = "CRM administration is temporarily unavailable. Core records remain available."
        elif core_access == "none":
            state = "not_in_plan"
            message = "Your organisation does not have active access to the Core CRM workflow."
        elif core_access == "read":
            state = "read_only"
            message = "Historical CRM data remains available to view and export. New CRM administration is blocked."
        elif mode == "external" and connector_access == "none":
            state = "not_in_plan"
            message = "External CRM connectors aren't included in your organisation's current plan."
        elif mode == "external" and connector_access == "read":
            state = "read_only"
            message = "Historical external CRM data remains available to view and export. New sync is blocked."
        elif setting is None:
            state = "setup_required"
            message = "Choose RevenueOS or an external CRM as the system of record."
        elif setting.mode == "external" and not connection_active:
            state = "setup_required"
            message = "Reconnect HubSpot to continue using it as the external CRM."
        else:
            state = "available"
            message = "CRM administration is available."
        return CRMAvailabilityResponse(
            state=cast(
                Literal["available", "read_only", "not_in_plan", "setup_required", "temporarily_unavailable"],
                state,
            ),
            enabled=enabled,
            can_manage=self.tenant.can_manage(),
            mode=mode,
            external_provider=cast("Literal['hubspot'] | None", setting.external_provider if setting else None),
            external_connected=connection_active,
            custom_fields_read_only=not enabled or not self.settings.feature_native_crm_enabled,
            message=message,
        )

    async def update_entitlement(self, enabled: bool) -> CRMAvailabilityResponse:
        del enabled
        self._require_admin()
        raise PublicAPIError(
            "commercial_plan_managed",
            "Module access is managed by your organisation's commercial plan. Contact support to change it.",
            403,
        )

    async def update_settings(self, request: CRMSettingsUpdate) -> CRMAvailabilityResponse:
        self._require_admin()
        await self._require_crm_enabled(for_update=True)
        if request.mode == "external":
            await CommercialService(self.session, self.settings).require_module_write(
                self.tenant.organisation_id, "crm"
            )
        connection = await self.repository.active_hubspot_connection(self.tenant.organisation_id)
        if request.mode == "external" and (connection is None or connection.connection_status != "active"):
            raise PublicAPIError(
                "crm_connection_required",
                "Connect HubSpot before selecting it as the external CRM.",
                409,
            )
        if request.mode == "native" and await self.repository.has_active_field_mappings(self.tenant.organisation_id):
            raise PublicAPIError(
                "crm_mode_conflict",
                "Disable active HubSpot field mappings before using RevenueOS as your CRM.",
                409,
            )
        setting = await self.repository.setting(self.tenant.organisation_id, for_update=True)
        now = datetime.now(UTC)
        if setting is None:
            setting = OrganisationCRMSetting(
                organisation_id=self.tenant.organisation_id,
                mode=request.mode,
                external_provider="hubspot" if request.mode == "external" else None,
                configured_by_user_id=self.tenant.user_id,
                configured_at=now,
            )
            self.repository.add(setting)
        else:
            setting.mode = request.mode
            setting.external_provider = "hubspot" if request.mode == "external" else None
            setting.configured_by_user_id = self.tenant.user_id
            setting.configured_at = now
        await self._commit()
        return await self.availability()

    async def members(self) -> list[CRMMemberResponse]:
        return [
            CRMMemberResponse(user_id=item.user_id, display_name=item.display_name, active=item.active)
            for item in await self.repository.members(self.tenant.organisation_id)
        ]

    async def list_custom_fields(
        self, entity_type: CRMEntityType | None, *, include_archived: bool
    ) -> list[CRMCustomFieldDefinitionResponse]:
        definitions = await self.repository.definitions(
            self.tenant.organisation_id,
            entity_type=entity_type,
            include_archived=include_archived,
        )
        return [self._definition_response(item) for item in definitions]

    async def create_custom_field(self, request: CRMCustomFieldCreate) -> CRMCustomFieldDefinitionResponse:
        self._require_admin()
        await self._require_crm_enabled(for_update=True)
        if request.field_key in RESERVED_CUSTOM_FIELD_KEYS:
            raise PublicAPIError(
                "reserved_custom_field_key",
                "Choose a key that does not conflict with a built-in CRM field.",
                422,
            )
        if await self.repository.definition_count(self.tenant.organisation_id, request.entity_type) >= 25:
            raise PublicAPIError(
                "custom_field_limit_reached",
                "Each CRM record type supports up to 25 custom fields.",
                409,
            )
        definition = CRMCustomFieldDefinition(
            organisation_id=self.tenant.organisation_id,
            entity_type=request.entity_type,
            field_key=request.field_key,
            label=request.label,
            field_type=request.field_type,
            options_json=request.options,
            display_order=request.display_order,
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(definition)
        await self._commit()
        await self.repository.refresh(definition)
        return self._definition_response(definition)

    async def update_custom_field(
        self, definition_id: UUID, request: CRMCustomFieldUpdate
    ) -> CRMCustomFieldDefinitionResponse:
        self._require_admin()
        await self._require_crm_enabled()
        definition = await self._definition_or_404(definition_id, for_update=True)
        if not definition.active:
            raise PublicAPIError("custom_field_archived", "Archived custom fields cannot be changed.", 409)
        if request.label is not None:
            definition.label = request.label
        if request.display_order is not None:
            definition.display_order = request.display_order
        if request.options is not None:
            if definition.field_type != "single_select" or not request.options:
                raise PublicAPIError(
                    "invalid_custom_field_options",
                    "Only single-select fields accept a non-empty options list.",
                    422,
                )
            definition.options_json = request.options
        await self._commit()
        await self.repository.refresh(definition)
        return self._definition_response(definition)

    async def archive_custom_field(self, definition_id: UUID) -> CRMCustomFieldDefinitionResponse:
        self._require_admin()
        await self._require_crm_enabled()
        definition = await self._definition_or_404(definition_id, for_update=True)
        if definition.active:
            definition.active = False
            definition.archived_at = datetime.now(UTC)
            await self._commit()
            await self.repository.refresh(definition)
        return self._definition_response(definition)

    async def record(self, entity_type: CRMEntityType, entity_id: UUID) -> CRMRecordResponse:
        record = await self._record_or_404(entity_type, entity_id)
        merge = await self.repository.merge_for_source(self.tenant.organisation_id, entity_type, entity_id)
        availability = await self.availability()
        definitions = await self.repository.definitions(self.tenant.organisation_id, entity_type=entity_type)
        values = await self.repository.values_for_record(self.tenant.organisation_id, entity_type, entity_id)
        authority = await self._authority(entity_type, availability.mode)
        custom_fields = [
            self._value_response(
                definition,
                values.get(definition.id),
                editable=not availability.custom_fields_read_only,
            )
            for definition in definitions
        ]
        history = [
            CRMRecordChangeResponse(
                id=item.change.id,
                field_key=item.change.field_key,
                old_value=item.change.old_value_json,
                new_value=item.change.new_value_json,
                source=cast(CRMChangeSource, item.change.source),
                changed_by_user_id=item.change.changed_by_user_id,
                changed_by_name=item.actor_name,
                changed_at=item.change.changed_at,
            )
            for item in await self.repository.history(self.tenant.organisation_id, entity_type, entity_id)
        ]
        return CRMRecordResponse(
            entity_type=entity_type,
            entity_id=record.id,
            title=self._title(record),
            owner_user_id=record.owner_user_id,
            owner_name=await self.repository.owner_name(record.owner_user_id),
            archived_at=record.archived_at,
            record_updated_at=record.updated_at,
            mode=availability.mode,
            crm_enabled=availability.enabled,
            can_manage=availability.can_manage,
            custom_fields_read_only=availability.custom_fields_read_only,
            field_authority=authority,
            core_fields=self._core_fields(record, authority),
            custom_fields=custom_fields,
            history=history,
            activity=await self._activity(entity_type, entity_id),
            merged_into_entity_id=merge.survivor_entity_id if merge is not None else None,
            merge_id=merge.id if merge is not None else None,
        )

    async def set_custom_value(
        self,
        entity_type: CRMEntityType,
        entity_id: UUID,
        definition_id: UUID,
        request: CRMCustomFieldValueUpdate,
    ) -> CRMCustomFieldValueResponse:
        await self._require_crm_enabled()
        record = await self._record_or_404(entity_type, entity_id, for_update=True)
        self._check_concurrency(record.updated_at, request.expected_record_updated_at)
        if record.archived_at is not None:
            raise PublicAPIError("record_archived", "Restore this record before changing it.", 409)
        definition = await self._definition_or_404(definition_id)
        if definition.entity_type != entity_type:
            raise PublicAPIError("invalid_relationship", "The custom field does not belong to this record type.", 422)
        if not definition.active:
            raise PublicAPIError("custom_field_archived", "Archived custom fields cannot be changed.", 409)
        existing = await self.repository.value(
            self.tenant.organisation_id,
            definition.id,
            entity_type,
            entity_id,
            for_update=True,
        )
        old_value = self._typed_value(existing)
        new_value: str | Decimal | date | bool | None = None
        if request.value is None:
            if existing is not None:
                await self.repository.delete(existing)
        else:
            new_value = self._validate_value(definition, request.value)
            target = existing or CRMCustomFieldValue(
                organisation_id=self.tenant.organisation_id,
                definition_id=definition.id,
                entity_type=entity_type,
                entity_id=entity_id,
                source="manual_user_entry",
                changed_by_user_id=self.tenant.user_id,
            )
            self._assign_typed_value(target, definition.field_type, new_value)
            target.source = "manual_user_entry"
            target.changed_by_user_id = self.tenant.user_id
            if existing is None:
                self.repository.add(target)
        if old_value == new_value:
            return self._value_response(definition, existing, editable=True)
        record.updated_at = datetime.now(UTC)
        self.repository.add(
            self._change(entity_type, entity_id, f"custom.{definition.field_key}", old_value, new_value)
        )
        await self._commit()
        current = await self.repository.value(self.tenant.organisation_id, definition.id, entity_type, entity_id)
        return self._value_response(definition, current, editable=True)

    async def archive_record(self, entity_type: CRMEntityType, entity_id: UUID, *, restore: bool) -> CRMArchiveResponse:
        self._require_admin()
        await self._require_crm_enabled()
        record = await self._record_or_404(entity_type, entity_id, for_update=True)
        if restore and await self.repository.merge_for_source(self.tenant.organisation_id, entity_type, entity_id):
            raise PublicAPIError("record_merged", "Merged source records cannot be restored.", 409)
        before = record.archived_at
        record.archived_at = None if restore else datetime.now(UTC)
        if before != record.archived_at:
            record.updated_at = datetime.now(UTC)
            self.repository.add(self._change(entity_type, entity_id, "archived_at", before, record.archived_at))
            await self._commit()
        return CRMArchiveResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            archived_at=record.archived_at,
        )

    async def _activity(self, entity_type: CRMEntityType, entity_id: UUID) -> list[CRMActivityItemResponse]:
        items: list[CRMActivityItemResponse] = []
        for interaction in await self.repository.interactions(
            self.tenant.organisation_id, entity_type, entity_id, limit=20
        ):
            occurred_at = (
                interaction.actual_end_at
                or interaction.actual_start_at
                or interaction.scheduled_start_at
                or interaction.created_at
            )
            items.append(
                CRMActivityItemResponse(
                    id=f"interaction:{interaction.id}",
                    activity_type="interaction",
                    title=interaction.title,
                    detail=interaction.lifecycle_status.replace("_", " ").title(),
                    occurred_at=occurred_at,
                    href=f"/interactions/{interaction.id}",
                    source_label="Interaction",
                )
            )
        for task in await self.repository.tasks(self.tenant.organisation_id, entity_type, entity_id, limit=20):
            items.append(
                CRMActivityItemResponse(
                    id=f"action:{task.id}",
                    activity_type="action",
                    title=task.title,
                    detail=task.status.replace("_", " ").title(),
                    occurred_at=task.updated_at,
                    href=f"/tasks/{task.id}/edit",
                    source_label="Action",
                )
            )
        engage_enabled = self.settings.feature_engage_enabled and await self.repository.module_enabled(
            self.tenant.organisation_id, "engage"
        )
        if engage_enabled:
            for message in await self.repository.outreach(
                self.tenant.organisation_id, entity_type, entity_id, limit=20
            ):
                items.append(
                    CRMActivityItemResponse(
                        id=f"outreach:{message.id}",
                        activity_type="outreach",
                        title=message.purpose.replace("_", " ").title(),
                        detail=message.state.title(),
                        occurred_at=message.updated_at,
                        href=None,
                        source_label="Outreach",
                    )
                )
            if self.settings.feature_engage_events_enabled:
                for encounter, event in await self.repository.event_encounters(
                    self.tenant.organisation_id, entity_type, entity_id, limit=20
                ):
                    items.append(
                        CRMActivityItemResponse(
                            id=f"event:{encounter.id}",
                            activity_type="event",
                            title=event.name,
                            detail=encounter.state.replace("_", " ").title(),
                            occurred_at=encounter.occurred_at,
                            href=f"/events/{event.id}",
                            source_label="Event",
                        )
                    )
        if entity_type == "account":
            for opportunity in await self.repository.opportunities_for_account(
                self.tenant.organisation_id, entity_id, limit=20
            ):
                items.append(
                    CRMActivityItemResponse(
                        id=f"opportunity:{opportunity.id}",
                        activity_type="opportunity",
                        title=opportunity.name,
                        detail=f"{opportunity.stage.replace('_', ' ').title()} · {opportunity.status.title()}",
                        occurred_at=opportunity.updated_at,
                        href=f"/opportunities/{opportunity.id}",
                        source_label="Opportunity",
                    )
                )
        return sorted(items, key=lambda item: item.occurred_at, reverse=True)[:50]

    async def _authority(self, entity_type: CRMEntityType, mode: CRMMode) -> dict[str, CRMFieldAuthority]:
        if mode != "external" or entity_type == "account":
            return {}
        authority = await self.repository.field_authority(self.tenant.organisation_id, entity_type)
        return {key: cast(CRMFieldAuthority, value) for key, value in authority.items()}

    async def _record_or_404(
        self, entity_type: CRMEntityType, entity_id: UUID, *, for_update: bool = False
    ) -> CRMRecord:
        record = await self.repository.record(
            self.tenant.organisation_id, entity_type, entity_id, for_update=for_update
        )
        if record is None:
            raise PublicAPIError("crm_record_not_found", "The requested CRM record was not found.", 404)
        return record

    async def _definition_or_404(self, definition_id: UUID, *, for_update: bool = False) -> CRMCustomFieldDefinition:
        definition = await self.repository.definition(self.tenant.organisation_id, definition_id, for_update=for_update)
        if definition is None:
            raise PublicAPIError("custom_field_not_found", "The requested custom field was not found.", 404)
        return definition

    async def _require_crm_enabled(self, *, for_update: bool = False) -> None:
        if not self.settings.feature_native_crm_enabled:
            raise PublicAPIError("crm_temporarily_unavailable", "CRM administration is temporarily unavailable.", 503)
        del for_update
        await CommercialService(self.session, self.settings).require_module_write(self.tenant.organisation_id, "core")

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)

    async def _commit(self) -> None:
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("conflict", "The change conflicts with existing CRM data.", 409) from exc

    def _change(
        self,
        entity_type: CRMEntityType,
        entity_id: UUID,
        field_key: str,
        old_value: object | None,
        new_value: object | None,
    ) -> CRMRecordChange:
        return CRMRecordChange(
            organisation_id=self.tenant.organisation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=field_key,
            old_value_json=self._json_value(old_value),
            new_value_json=self._json_value(new_value),
            source="manual_user_entry",
            changed_by_user_id=self.tenant.user_id,
        )

    @staticmethod
    def _effective_mode(setting: OrganisationCRMSetting | None, connected: bool) -> CRMMode:
        if setting is not None:
            return cast(CRMMode, setting.mode)
        return "external" if connected else "unconfigured"

    @staticmethod
    def _definition_response(
        definition: CRMCustomFieldDefinition,
    ) -> CRMCustomFieldDefinitionResponse:
        return CRMCustomFieldDefinitionResponse(
            id=definition.id,
            entity_type=cast(CRMEntityType, definition.entity_type),
            field_key=definition.field_key,
            label=definition.label,
            field_type=cast(CRMFieldType, definition.field_type),
            options=definition.options_json,
            active=definition.active,
            display_order=definition.display_order,
            created_by_user_id=definition.created_by_user_id,
            archived_at=definition.archived_at,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
        )

    @classmethod
    def _value_response(
        cls,
        definition: CRMCustomFieldDefinition,
        value: CRMCustomFieldValue | None,
        *,
        editable: bool,
    ) -> CRMCustomFieldValueResponse:
        return CRMCustomFieldValueResponse(
            definition=cls._definition_response(definition),
            value=cls._typed_value(value),
            source=cast(CRMChangeSource | None, value.source if value else None),
            changed_by_user_id=value.changed_by_user_id if value else None,
            updated_at=value.updated_at if value else None,
            editable=editable,
        )

    @staticmethod
    def _typed_value(value: CRMCustomFieldValue | None) -> str | Decimal | date | bool | None:
        if value is None:
            return None
        if value.text_value is not None:
            return value.text_value
        if value.number_value is not None:
            return value.number_value
        if value.date_value is not None:
            return value.date_value
        return value.boolean_value

    @staticmethod
    def _validate_value(definition: CRMCustomFieldDefinition, value: object) -> str | Decimal | date | bool:
        field_type = definition.field_type
        if field_type in {"short_text", "url", "single_select"}:
            if not isinstance(value, str):
                raise PublicAPIError("invalid_custom_field_value", "This custom field requires text.", 422)
            cleaned = value.strip()
            if not cleaned:
                raise PublicAPIError("invalid_custom_field_value", "Custom field text cannot be empty.", 422)
            if field_type == "short_text" and len(cleaned) > 500:
                raise PublicAPIError("invalid_custom_field_value", "Short text is limited to 500 characters.", 422)
            if field_type == "url":
                try:
                    cleaned = validate_custom_url(cleaned)
                except ValueError as exc:
                    raise PublicAPIError("invalid_custom_field_value", "Enter a valid HTTP or HTTPS URL.", 422) from exc
                if len(cleaned) > 2048:
                    raise PublicAPIError(
                        "invalid_custom_field_value",
                        "URLs are limited to 2,048 characters.",
                        422,
                    )
            if field_type == "single_select" and cleaned not in definition.options_json:
                raise PublicAPIError("invalid_custom_field_value", "Choose one of the configured options.", 422)
            return cleaned
        if field_type == "number":
            if isinstance(value, bool) or isinstance(value, date):
                raise PublicAPIError("invalid_custom_field_value", "This custom field requires a number.", 422)
            try:
                number = Decimal(str(value))
            except InvalidOperation as exc:
                raise PublicAPIError("invalid_custom_field_value", "This custom field requires a number.", 422) from exc
            if not number.is_finite() or number.copy_abs() >= Decimal("100000000000000"):
                raise PublicAPIError(
                    "invalid_custom_field_value",
                    "Numbers must be finite and fit within 14 whole digits and 4 decimal places.",
                    422,
                )
            exponent = number.as_tuple().exponent
            if not isinstance(exponent, int) or exponent < -4:
                raise PublicAPIError(
                    "invalid_custom_field_value",
                    "Numbers support up to 4 decimal places.",
                    422,
                )
            return number
        if field_type == "date":
            if isinstance(value, str):
                try:
                    return date.fromisoformat(value)
                except ValueError as exc:
                    raise PublicAPIError(
                        "invalid_custom_field_value", "This custom field requires a date.", 422
                    ) from exc
            if isinstance(value, datetime) or not isinstance(value, date):
                raise PublicAPIError("invalid_custom_field_value", "This custom field requires a date.", 422)
            return value
        if not isinstance(value, bool):
            raise PublicAPIError("invalid_custom_field_value", "This custom field requires true or false.", 422)
        return value

    @staticmethod
    def _assign_typed_value(target: CRMCustomFieldValue, field_type: str, value: str | Decimal | date | bool) -> None:
        target.text_value = None
        target.number_value = None
        target.date_value = None
        target.boolean_value = None
        if field_type in {"short_text", "url", "single_select"}:
            target.text_value = cast(str, value)
        elif field_type == "number":
            target.number_value = cast(Decimal, value)
        elif field_type == "date":
            target.date_value = cast(date, value)
        else:
            target.boolean_value = cast(bool, value)

    @staticmethod
    def _title(record: CRMRecord) -> str:
        if isinstance(record, Contact):
            return f"{record.first_name} {record.last_name}"
        return record.name

    @classmethod
    def _core_fields(
        cls,
        record: CRMRecord,
        authority: dict[str, CRMFieldAuthority],
    ) -> list[CRMCoreFieldResponse]:
        if isinstance(record, Company):
            fields: tuple[tuple[str, str, object | None], ...] = (
                ("website", "Website", record.website),
                ("industry", "Industry", record.industry),
                ("location", "Location", record.location),
                ("employee_count", "Employee count", record.employee_count),
                ("status", "Status", record.status),
            )
        elif isinstance(record, Contact):
            fields = (
                ("first_name", "First name", record.first_name),
                ("last_name", "Last name", record.last_name),
                ("email", "Business email", record.email),
                ("phone", "Phone", record.phone),
                ("job_title", "Job title", record.job_title),
                ("linkedin_url", "LinkedIn URL", record.linkedin_url),
                ("status", "Employment status", record.status),
            )
        else:
            fields = (
                ("stage", "Stage", record.stage),
                ("status", "Status", record.status),
                ("estimated_value", "Estimated value", record.estimated_value),
                ("currency", "Currency", record.currency),
                ("expected_close_date", "Expected close date", record.expected_close_date),
                ("description", "Description", record.description),
            )
        return [
            CRMCoreFieldResponse(
                key=key,
                label=label,
                value=cls._display_value(value),
                authority=authority.get(key, "revenueos_authoritative"),
            )
            for key, label, value in fields
        ]

    @staticmethod
    def _display_value(value: object | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _check_concurrency(current: datetime, expected: datetime | None) -> None:
        if expected is None:
            return

        def normalise(value: datetime) -> datetime:
            return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).astimezone(UTC)

        if normalise(current) != normalise(expected):
            raise PublicAPIError(
                "stale_write",
                "This record changed after it was loaded. Refresh and try again.",
                409,
            )

    @staticmethod
    def _json_value(value: object | None) -> object | None:
        if isinstance(value, (date, datetime, Decimal)):
            return value.isoformat() if not isinstance(value, Decimal) else str(value)
        return value
