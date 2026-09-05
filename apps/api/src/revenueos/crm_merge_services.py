from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.crm_contracts import (
    CRMMergeConfirmRequest,
    CRMMergeFieldConflict,
    CRMMergePreviewRequest,
    CRMMergePreviewResponse,
    CRMMergeResponse,
)
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    Contact,
    ContactFieldSource,
    ContactSuppression,
    CreateBusinessCase,
    CreatePresentation,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMEntityMapping,
    CRMRecordChange,
    CRMRecordMerge,
    DocumentSource,
    EmailSource,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EventAttendee,
    Interaction,
    Meeting,
    MeetingParticipant,
    Opportunity,
    OrganisationCRMSetting,
    OutreachMessage,
    PreInteractionBrief,
    ProspectDiscoveryCandidate,
    ProspectPerson,
    ProspectResearchTarget,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    RevenueBrainSourceSnapshot,
    Task,
)
from revenueos.tenant import TenantContext

ACCOUNT_MERGE_FIELDS = (
    "name",
    "website",
    "industry",
    "location",
    "employee_count",
    "status",
    "owner_user_id",
)
CONTACT_MERGE_FIELDS = (
    "company_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "job_title",
    "linkedin_url",
    "status",
    "owner_user_id",
)


class CRMMergeService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings

    async def preview(self, request: CRMMergePreviewRequest) -> CRMMergePreviewResponse:
        await self._require_admin_native_crm()
        source, survivor = await self._records(request, for_update=False)
        return await self._build_preview(request, source, survivor)

    async def confirm(self, request: CRMMergeConfirmRequest) -> CRMMergeResponse:
        await self._require_admin_native_crm()
        key_hash = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
        existing = await self.session.scalar(
            select(CRMRecordMerge).where(
                CRMRecordMerge.organisation_id == self.tenant.organisation_id,
                CRMRecordMerge.entity_type == request.entity_type,
                CRMRecordMerge.idempotency_key_hash == key_hash,
            )
        )
        if existing is not None:
            if (
                existing.source_entity_id != request.source_entity_id
                or existing.survivor_entity_id != request.survivor_entity_id
            ):
                raise PublicAPIError("merge_idempotency_conflict", "This merge key was used for another merge.", 409)
            return self._response(existing, already_applied=True)
        source, survivor = await self._records(request, for_update=True)
        preview = await self._build_preview(request, source, survivor)
        if preview.blocked_reasons:
            raise PublicAPIError("merge_blocked", "Resolve the merge blockers before confirming.", 409)
        if preview.preview_fingerprint != request.preview_fingerprint:
            raise PublicAPIError(
                "merge_preview_stale", "The records changed after preview. Preview the merge again.", 409
            )
        conflict_keys = {conflict.field_key for conflict in preview.conflicts}
        if set(request.field_selection) != conflict_keys:
            raise PublicAPIError("merge_selection_incomplete", "Choose a survivor value for every merge conflict.", 422)
        now = datetime.now(UTC)
        await self._apply_fields(request, source, survivor, now)
        await self._move_relationships(request.entity_type, source.id, survivor.id, request.field_selection)
        source.archived_at = now
        source.updated_at = now
        survivor.updated_at = now
        merge = CRMRecordMerge(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            entity_type=request.entity_type,
            source_entity_id=source.id,
            survivor_entity_id=survivor.id,
            preview_fingerprint=preview.preview_fingerprint,
            idempotency_key_hash=key_hash,
            field_selection_json=request.field_selection,
            merged_by_user_id=self.tenant.user_id,
            merged_at=now,
        )
        self.session.add(merge)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            concurrent = await self.session.scalar(
                select(CRMRecordMerge).where(
                    CRMRecordMerge.organisation_id == self.tenant.organisation_id,
                    CRMRecordMerge.entity_type == request.entity_type,
                    CRMRecordMerge.idempotency_key_hash == key_hash,
                )
            )
            if concurrent is not None:
                return self._response(concurrent, already_applied=True)
            raise PublicAPIError(
                "merge_conflict", "CRM data changed while the merge was being confirmed.", 409
            ) from exc
        return self._response(merge, already_applied=False)

    async def _records(
        self, request: CRMMergePreviewRequest, *, for_update: bool
    ) -> tuple[Company | Contact, Company | Contact]:
        ordered_ids = sorted((request.source_entity_id, request.survivor_entity_id), key=str)
        if request.entity_type == "account":
            company_statement = (
                select(Company)
                .where(
                    Company.organisation_id == self.tenant.organisation_id,
                    Company.id.in_(ordered_ids),
                )
                .order_by(Company.id)
            )
            if for_update:
                company_statement = company_statement.with_for_update()
            company_records = list(await self.session.scalars(company_statement))
            by_id: dict[UUID, Company | Contact] = {record.id: record for record in company_records}
        else:
            contact_statement = (
                select(Contact)
                .where(
                    Contact.organisation_id == self.tenant.organisation_id,
                    Contact.id.in_(ordered_ids),
                )
                .order_by(Contact.id)
            )
            if for_update:
                contact_statement = contact_statement.with_for_update()
            contact_records = list(await self.session.scalars(contact_statement))
            by_id = {record.id: record for record in contact_records}
        source = by_id.get(request.source_entity_id)
        survivor = by_id.get(request.survivor_entity_id)
        if source is None or survivor is None:
            raise PublicAPIError("crm_record_not_found", "Both merge records must exist in this organisation.", 404)
        return source, survivor

    async def _build_preview(
        self,
        request: CRMMergePreviewRequest,
        source: Company | Contact,
        survivor: Company | Contact,
    ) -> CRMMergePreviewResponse:
        blocked: list[str] = []
        if source.archived_at is not None or survivor.archived_at is not None:
            blocked.append("archived_record")
        prior_merge = await self.session.scalar(
            select(CRMRecordMerge.id).where(
                CRMRecordMerge.organisation_id == self.tenant.organisation_id,
                CRMRecordMerge.entity_type == request.entity_type,
                CRMRecordMerge.source_entity_id.in_((source.id, survivor.id)),
            )
        )
        if prior_merge is not None:
            blocked.append("record_already_merged")
        source_mapping = await self.session.scalar(
            select(CRMEntityMapping.id).where(
                CRMEntityMapping.organisation_id == self.tenant.organisation_id,
                CRMEntityMapping.revenueos_entity_type
                == ("company" if request.entity_type == "account" else "contact"),
                CRMEntityMapping.revenueos_entity_id == source.id,
            )
        )
        if source_mapping is not None:
            blocked.append("source_external_crm_mapping")
        if request.entity_type == "contact":
            active_campaign = await self.session.scalar(
                select(EngageCampaignEnrollment.id).where(
                    EngageCampaignEnrollment.organisation_id == self.tenant.organisation_id,
                    EngageCampaignEnrollment.contact_id == source.id,
                    EngageCampaignEnrollment.state.not_in(("stopped", "completed", "blocked")),
                )
            )
            if active_campaign is not None:
                blocked.append("source_active_campaign")
            if await self._contact_relationship_collision(source.id, survivor.id):
                blocked.append("campaign_relationship_collision")
            if await self._contact_provenance_collision(source.id, survivor.id):
                blocked.append("contact_provenance_collision")
        fields = ACCOUNT_MERGE_FIELDS if request.entity_type == "account" else CONTACT_MERGE_FIELDS
        conflicts = [
            CRMMergeFieldConflict(
                field_key=field,
                source_value=self._json_value(getattr(source, field)),
                survivor_value=self._json_value(getattr(survivor, field)),
                selected="survivor",
            )
            for field in fields
            if self._json_value(getattr(source, field)) != self._json_value(getattr(survivor, field))
        ]
        custom_definitions = {
            item.id: item
            for item in await self.session.scalars(
                select(CRMCustomFieldDefinition).where(
                    CRMCustomFieldDefinition.organisation_id == self.tenant.organisation_id,
                    CRMCustomFieldDefinition.entity_type == request.entity_type,
                )
            )
        }
        custom_values = list(
            await self.session.scalars(
                select(CRMCustomFieldValue).where(
                    CRMCustomFieldValue.organisation_id == self.tenant.organisation_id,
                    CRMCustomFieldValue.entity_type == request.entity_type,
                    CRMCustomFieldValue.entity_id.in_((source.id, survivor.id)),
                )
            )
        )
        custom_by_record = {(value.entity_id, value.definition_id): value for value in custom_values}
        for definition_id in custom_definitions:
            source_value = self._typed_value(custom_by_record.get((source.id, definition_id)))
            survivor_value = self._typed_value(custom_by_record.get((survivor.id, definition_id)))
            if self._json_value(source_value) != self._json_value(survivor_value):
                conflicts.append(
                    CRMMergeFieldConflict(
                        field_key=f"custom:{definition_id}",
                        source_value=self._json_value(source_value),
                        survivor_value=self._json_value(survivor_value),
                        selected="survivor",
                    )
                )
        fingerprint_payload = {
            "entityType": request.entity_type,
            "sourceId": str(source.id),
            "survivorId": str(survivor.id),
            "sourceUpdatedAt": self._json_value(source.updated_at),
            "survivorUpdatedAt": self._json_value(survivor.updated_at),
            "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
            "blocked": sorted(blocked),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return CRMMergePreviewResponse(
            entity_type=request.entity_type,
            source_entity_id=source.id,
            survivor_entity_id=survivor.id,
            preview_fingerprint=fingerprint,
            conflicts=conflicts,
            blocked_reasons=sorted(blocked),
        )

    async def _apply_fields(
        self,
        request: CRMMergeConfirmRequest,
        source: Company | Contact,
        survivor: Company | Contact,
        now: datetime,
    ) -> None:
        for field_key, selection in request.field_selection.items():
            if field_key.startswith("custom:"):
                continue
            old_value = getattr(survivor, field_key)
            new_value = getattr(source, field_key) if selection == "source" else old_value
            if old_value == new_value:
                continue
            if isinstance(source, Company) and isinstance(survivor, Company) and field_key == "website":
                source.normalized_domain = None
                await self.session.flush()
                survivor.normalized_domain = normalise_domain(source.website)
            if isinstance(source, Contact) and isinstance(survivor, Contact) and field_key == "email":
                source.email = None
                await self.session.flush()
            setattr(survivor, field_key, new_value)
            self.session.add(self._change(request.entity_type, survivor.id, field_key, old_value, new_value, now))
        await self._apply_custom_fields(request, source.id, survivor.id, now)

    async def _apply_custom_fields(
        self,
        request: CRMMergeConfirmRequest,
        source_id: UUID,
        survivor_id: UUID,
        now: datetime,
    ) -> None:
        values = list(
            await self.session.scalars(
                select(CRMCustomFieldValue)
                .where(
                    CRMCustomFieldValue.organisation_id == self.tenant.organisation_id,
                    CRMCustomFieldValue.entity_type == request.entity_type,
                    CRMCustomFieldValue.entity_id.in_((source_id, survivor_id)),
                )
                .with_for_update()
            )
        )
        by_key = {(value.entity_id, value.definition_id): value for value in values}
        for field_key, selection in request.field_selection.items():
            if not field_key.startswith("custom:") or selection != "source":
                continue
            definition_id = UUID(field_key.removeprefix("custom:"))
            source_value = by_key.get((source_id, definition_id))
            survivor_value = by_key.get((survivor_id, definition_id))
            old_value = self._typed_value(survivor_value)
            new_value = self._typed_value(source_value)
            if survivor_value is not None:
                await self.session.delete(survivor_value)
                await self.session.flush()
            if source_value is not None:
                source_value.entity_id = survivor_id
                source_value.source = "record_merge"
                source_value.changed_by_user_id = self.tenant.user_id
            self.session.add(self._change(request.entity_type, survivor_id, field_key, old_value, new_value, now))

    async def _move_relationships(
        self,
        entity_type: str,
        source_id: UUID,
        survivor_id: UUID,
        selections: Mapping[str, str],
    ) -> None:
        organisation_id = self.tenant.organisation_id
        if entity_type == "account":
            account_relationships = (
                (Contact, Contact.company_id),
                (Opportunity, Opportunity.company_id),
                (Task, Task.company_id),
                (Interaction, Interaction.company_id),
                (Meeting, Meeting.company_id),
                (CreateBusinessCase, CreateBusinessCase.account_id),
                (CreatePresentation, CreatePresentation.account_id),
                (ProspectResearchTarget, ProspectResearchTarget.promoted_company_id),
                (ProspectDiscoveryCandidate, ProspectDiscoveryCandidate.matched_company_id),
                (EventAttendee, EventAttendee.company_id),
                (EngageCampaignAudience, EngageCampaignAudience.company_id),
                (EngageCampaignEnrollment, EngageCampaignEnrollment.company_id),
                (PreInteractionBrief, PreInteractionBrief.company_id),
                (DocumentSource, DocumentSource.company_id),
                (EmailSource, EmailSource.company_id),
                (RevenueBrainSourceSnapshot, RevenueBrainSourceSnapshot.company_id),
                (RevenueBrainInteractionSnapshot, RevenueBrainInteractionSnapshot.company_id),
                (RevenueBrainSnapshot, RevenueBrainSnapshot.company_id),
                (RevenueBrainInsight, RevenueBrainInsight.company_id),
            )
        else:
            contact_relationships = (
                (Task, Task.contact_id),
                (Interaction, Interaction.contact_id),
                (MeetingParticipant, MeetingParticipant.contact_id),
                (ProspectPerson, ProspectPerson.promoted_contact_id),
                (EventAttendee, EventAttendee.contact_id),
                (EngageCampaignAudience, EngageCampaignAudience.contact_id),
                (EngageCampaignEnrollment, EngageCampaignEnrollment.contact_id),
                (OutreachMessage, OutreachMessage.contact_id),
                (EmailSource, EmailSource.sender_contact_id),
                (ContactFieldSource, ContactFieldSource.contact_id),
            )
        if entity_type == "account":
            for account_model, account_column in account_relationships:
                await self.session.execute(
                    update(account_model)
                    .where(
                        account_model.organisation_id == organisation_id,
                        account_column == source_id,
                    )
                    .values({account_column.key: survivor_id})
                )
        else:
            for contact_model, contact_column in contact_relationships:
                await self.session.execute(
                    update(contact_model)
                    .where(
                        contact_model.organisation_id == organisation_id,
                        contact_column == source_id,
                    )
                    .values({contact_column.key: survivor_id})
                )
        if entity_type == "account":
            await self.session.execute(
                update(RevenueBrainInsight)
                .where(
                    RevenueBrainInsight.organisation_id == organisation_id,
                    RevenueBrainInsight.scope == "account",
                    RevenueBrainInsight.scope_target_id == source_id,
                )
                .values(scope_target_id=survivor_id)
            )
        elif selections.get("email") == "source":
            await self.session.execute(
                update(ContactSuppression)
                .where(
                    ContactSuppression.organisation_id == organisation_id,
                    ContactSuppression.contact_id == source_id,
                )
                .values(contact_id=survivor_id)
            )
        if entity_type == "contact":
            await self._preserve_contact_suppression(source_id, survivor_id)

    async def _contact_relationship_collision(self, source_id: UUID, survivor_id: UUID) -> bool:
        organisation_id = self.tenant.organisation_id
        audience_source = select(EngageCampaignAudience.campaign_version_id).where(
            EngageCampaignAudience.organisation_id == organisation_id,
            EngageCampaignAudience.contact_id == source_id,
        )
        audience_collision = await self.session.scalar(
            select(EngageCampaignAudience.id).where(
                EngageCampaignAudience.organisation_id == organisation_id,
                EngageCampaignAudience.contact_id == survivor_id,
                EngageCampaignAudience.campaign_version_id.in_(audience_source),
            )
        )
        enrollment_source = select(EngageCampaignEnrollment.campaign_id).where(
            EngageCampaignEnrollment.organisation_id == organisation_id,
            EngageCampaignEnrollment.contact_id == source_id,
        )
        enrollment_collision = await self.session.scalar(
            select(EngageCampaignEnrollment.id).where(
                EngageCampaignEnrollment.organisation_id == organisation_id,
                EngageCampaignEnrollment.contact_id == survivor_id,
                EngageCampaignEnrollment.campaign_id.in_(enrollment_source),
            )
        )
        return audience_collision is not None or enrollment_collision is not None

    async def _contact_provenance_collision(self, source_id: UUID, survivor_id: UUID) -> bool:
        organisation_id = self.tenant.organisation_id
        source_pairs = select(ContactFieldSource.field_key, ContactFieldSource.value_fingerprint).where(
            ContactFieldSource.organisation_id == organisation_id,
            ContactFieldSource.contact_id == source_id,
        )
        collision = await self.session.scalar(
            select(ContactFieldSource.id)
            .where(
                ContactFieldSource.organisation_id == organisation_id,
                ContactFieldSource.contact_id == survivor_id,
                tuple_(ContactFieldSource.field_key, ContactFieldSource.value_fingerprint).in_(source_pairs),
            )
            .limit(1)
        )
        return collision is not None

    async def _preserve_contact_suppression(self, source_id: UUID, survivor_id: UUID) -> None:
        survivor = await self.session.scalar(
            select(Contact).where(
                Contact.organisation_id == self.tenant.organisation_id,
                Contact.id == survivor_id,
            )
        )
        if survivor is None or survivor.email is None:
            return
        suppressions = list(
            await self.session.scalars(
                select(ContactSuppression)
                .where(
                    ContactSuppression.organisation_id == self.tenant.organisation_id,
                    ContactSuppression.contact_id.in_((source_id, survivor_id)),
                    ContactSuppression.active.is_(True),
                )
                .with_for_update()
            )
        )
        if not suppressions:
            return
        fingerprint = hmac.new(
            self.settings.outreach_suppression_hmac_key.get_secret_value().encode(),
            survivor.email.strip().casefold().encode(),
            hashlib.sha256,
        ).hexdigest()
        target = await self.session.scalar(
            select(ContactSuppression)
            .where(
                ContactSuppression.organisation_id == self.tenant.organisation_id,
                ContactSuppression.email_fingerprint == fingerprint,
            )
            .with_for_update()
        )
        rank = {
            "manual_do_not_contact": 0,
            "permanent_bounce": 1,
            "recipient_opt_out": 2,
            "complaint": 3,
        }
        most_restrictive = max(suppressions, key=lambda item: rank[item.reason])
        if target is None:
            target = ContactSuppression(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                contact_id=survivor_id,
                email_fingerprint=fingerprint,
                reason=most_restrictive.reason,
                source=most_restrictive.source,
                active=True,
                created_by_user_id=(
                    self.tenant.user_id if most_restrictive.source == "user" else most_restrictive.created_by_user_id
                ),
                created_at=datetime.now(UTC),
            )
            self.session.add(target)
        elif rank[most_restrictive.reason] > rank[target.reason] or not target.active:
            target.contact_id = survivor_id
            target.reason = most_restrictive.reason
            target.source = most_restrictive.source
            target.active = True
            target.revoked_by_user_id = None
            target.revoked_at = None

    async def _require_admin_native_crm(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required for CRM merge.", 403)
        if not self.settings.feature_native_crm_enabled:
            raise PublicAPIError("crm_temporarily_unavailable", "CRM administration is temporarily unavailable.", 503)
        await CommercialService(self.session, self.settings).require_module_write(self.tenant.organisation_id, "core")
        setting = await self.session.scalar(
            select(OrganisationCRMSetting).where(
                OrganisationCRMSetting.organisation_id == self.tenant.organisation_id,
                OrganisationCRMSetting.mode == "native",
            )
        )
        if setting is None:
            raise PublicAPIError("crm_setup_required", "Configure RevenueOS as the CRM before merging records.", 409)

    def _change(
        self,
        entity_type: str,
        entity_id: UUID,
        field_key: str,
        old_value: object,
        new_value: object,
        changed_at: datetime,
    ) -> CRMRecordChange:
        return CRMRecordChange(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=field_key,
            old_value_json=self._json_value(old_value),
            new_value_json=self._json_value(new_value),
            source="record_merge",
            changed_by_user_id=self.tenant.user_id,
            changed_at=changed_at,
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
    def _json_value(value: object) -> object:
        return str(value) if isinstance(value, (UUID, Decimal, date, datetime)) else value

    @staticmethod
    def _response(merge: CRMRecordMerge, *, already_applied: bool) -> CRMMergeResponse:
        return CRMMergeResponse(
            merge_id=merge.id,
            entity_type=cast(Literal["account", "contact"], merge.entity_type),
            source_entity_id=merge.source_entity_id,
            survivor_entity_id=merge.survivor_entity_id,
            merged_at=merge.merged_at,
            already_applied=already_applied,
        )


def normalise_domain(website: str | None) -> str | None:
    if website is None:
        return None
    from revenueos.prospect_url_security import normalise_company_website

    return normalise_company_website(website).domain
