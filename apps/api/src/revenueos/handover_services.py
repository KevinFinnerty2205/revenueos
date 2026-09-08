from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import ClosedWonHandoverStatus, HandoverAuthorityType, HandoverSourceType
from revenueos.errors import PublicAPIError
from revenueos.handover_contracts import (
    MAX_HANDOVER_ITEMS,
    SECTION_ITEM_LIMITS,
    SECTION_KEYS,
    HandoverClaimConfirmationRequest,
    HandoverContent,
    HandoverContentUpdate,
    HandoverItem,
    HandoverLifecycleRequest,
    HandoverRevisionResponse,
    HandoverRevisionSummary,
    HandoverSectionKey,
    HandoverSourceResponse,
    HandoverWorkspaceResponse,
)
from revenueos.handover_repositories import HandoverRepository
from revenueos.models import (
    ClosedWonHandover,
    ClosedWonHandoverAuditEvent,
    ClosedWonHandoverRevision,
    ClosedWonHandoverSource,
    Opportunity,
)
from revenueos.tenant import TenantContext


@dataclass(frozen=True)
class SourceDefinition:
    reference_id: UUID
    source_type: HandoverSourceType
    source_id: UUID
    source_version_id: UUID | None
    source_version: int | None
    authority_type: HandoverAuthorityType
    label: str
    snapshot: dict[str, object]
    fingerprint: str

    @property
    def stable_key(self) -> tuple[str, UUID, UUID | None, int | None]:
        return (self.source_type.value, self.source_id, self.source_version_id, self.source_version)


HIGH_RISK_AUTHORITIES = frozenset(
    {
        HandoverAuthorityType.CUSTOMER_EVIDENCE,
        HandoverAuthorityType.SELLER_CONFIRMED,
        HandoverAuthorityType.COMMERCIAL_RECORD,
        HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
    }
)
HIGH_RISK_SECTIONS = ("commercial_scope", "commitments", "implementation_expectations")


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iso(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


class HandoverService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = HandoverRepository(session)

    async def workspace(self, opportunity_id: UUID) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=False)
        opportunity = await self._opportunity(opportunity_id)
        handover = await self.repository.handover(self.tenant.organisation_id, opportunity_id)
        return await self._workspace_response(opportunity, handover)

    async def revision(self, opportunity_id: UUID, revision_id: UUID) -> HandoverRevisionResponse:
        await self._require_entitlement(write=False)
        opportunity = await self._opportunity(opportunity_id)
        handover = await self.repository.handover(self.tenant.organisation_id, opportunity_id)
        if handover is None:
            raise PublicAPIError("handover_not_found", "This opportunity does not have a handover.", 404)
        revision = await self.repository.revision(
            self.tenant.organisation_id,
            handover.id,
            revision_id,
        )
        if revision is None:
            raise PublicAPIError("handover_revision_not_found", "The handover revision was not found.", 404)
        if not self._can_manage(opportunity) and revision.status not in {"approved", "superseded", "retired"}:
            raise PublicAPIError("handover_revision_not_found", "The handover revision was not found.", 404)
        return await self._revision_response(opportunity, revision)

    async def prepare(self, opportunity_id: UUID) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity = await self._opportunity(opportunity_id, for_update=True)
        self._require_manage(opportunity)
        self._require_preparable(opportunity)
        handover = await self.repository.handover(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if handover is None:
            handover = ClosedWonHandover(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                opportunity_id=opportunity.id,
                created_by_user_id=self.tenant.user_id,
                lock_version=1,
            )
            self.repository.add(handover)
            await self.session.flush()
        existing = await self.repository.editable_revision(
            self.tenant.organisation_id,
            handover.id,
            for_update=True,
        )
        if existing is not None:
            return await self._workspace_response(opportunity, handover)

        history = await self.repository.revisions(self.tenant.organisation_id, handover.id)
        revision = ClosedWonHandoverRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            handover_id=handover.id,
            opportunity_id=opportunity.id,
            revision=history[0].revision + 1 if history else 1,
            status="draft",
            content_schema_version=1,
            content_json=HandoverContent().model_dump(mode="json", by_alias=True),
            source_pack_fingerprint="0" * 64,
            lock_version=1,
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(revision)
        await self.session.flush()
        definitions = await self._source_definitions(opportunity)
        sources = self._persist_sources(revision, definitions)
        revision.source_pack_fingerprint = self._source_pack_fingerprint(definitions)
        revision.content_json = self._initial_content(opportunity, definitions).model_dump(mode="json", by_alias=True)
        handover.updated_at = datetime.now(UTC)
        if history:
            handover.lock_version += 1
        self._audit(handover, revision, "draft_created", {"revision": revision.revision, "source_count": len(sources)})
        await self._commit("The handover draft could not be prepared.")
        return await self._workspace_response(opportunity, handover)

    async def update_draft(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverContentUpdate,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        self._require_manage(opportunity)
        self._require_preparable(opportunity)
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status not in {"draft", "in_review"}:
            raise PublicAPIError(
                "handover_immutable",
                "Approved handovers are immutable. Prepare a new revision to make changes.",
                409,
            )
        sources = await self.repository.sources(self.tenant.organisation_id, revision.id)
        source_ids = {source.id for source in sources}
        try:
            existing = HandoverContent.model_validate(revision.content_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "handover_content_invalid", "The handover draft could not be safely read.", 409
            ) from exc
        normalised, changed_count = self._normalise_manual_edits(existing, request.content, source_ids)
        now = datetime.now(UTC)
        revision.content_json = normalised.model_dump(mode="json", by_alias=True)
        revision.status = "draft"
        revision.submitted_at = None
        revision.submitted_by_user_id = None
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(
            handover,
            revision,
            "draft_updated",
            {"revision": revision.revision, "changed_item_count": changed_count},
        )
        await self._commit("The handover draft could not be saved.")
        return await self._workspace_response(opportunity, handover)

    async def confirm_claim(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverClaimConfirmationRequest,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        self._require_manage(opportunity)
        self._require_preparable(opportunity)
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status not in {"draft", "in_review"}:
            raise PublicAPIError("handover_immutable", "Approved handover claims cannot be changed.", 409)
        content = HandoverContent.model_validate(revision.content_json)
        found = False
        previous_authority: HandoverAuthorityType | None = None
        previous_source_count = 0
        now = datetime.now(UTC)
        updated: dict[str, list[HandoverItem]] = {}
        for key in SECTION_KEYS:
            section_items: list[HandoverItem] = []
            for item in getattr(content, key):
                if item.id == request.item_id:
                    found = True
                    previous_authority = item.authority_type
                    previous_source_count = len(item.source_ids)
                    item = item.model_copy(
                        update={
                            "authority_type": HandoverAuthorityType.SELLER_CONFIRMED,
                            "confirmed_by_user_id": self.tenant.user_id,
                            "confirmed_at": now,
                            "risk_kind": "seller_concern" if key == "risks" else item.risk_kind,
                        }
                    )
                section_items.append(item)
            updated[key] = section_items
        if not found:
            raise PublicAPIError("handover_claim_not_found", "The handover item was not found.", 404)
        revision.content_json = HandoverContent(schema_version=1, **updated).model_dump(mode="json", by_alias=True)
        revision.status = "draft"
        revision.submitted_at = None
        revision.submitted_by_user_id = None
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(
            handover,
            revision,
            "claim_confirmed",
            {
                "revision": revision.revision,
                "item_id": str(request.item_id),
                "previous_authority": previous_authority.value if previous_authority is not None else "unknown",
                "reason": "explicit_seller_confirmation",
                "source_count": previous_source_count,
            },
        )
        await self._commit("The handover item could not be confirmed.")
        return await self._workspace_response(opportunity, handover)

    async def refresh_sources(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverLifecycleRequest,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        self._require_manage(opportunity)
        self._require_preparable(opportunity)
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status not in {"draft", "in_review"}:
            raise PublicAPIError("handover_immutable", "Approved handover sources cannot be refreshed.", 409)
        existing_content = HandoverContent.model_validate(revision.content_json)
        existing_sources = await self.repository.sources(self.tenant.organisation_id, revision.id)
        existing_key_by_id = {
            source.id: (source.source_type, source.source_id, source.source_version_id, source.source_version)
            for source in existing_sources
        }
        definitions = await self._source_definitions(opportunity)
        new_id_by_key = {definition.stable_key: definition.reference_id for definition in definitions}
        generated = self._initial_content(opportunity, definitions)
        preserved_by_section: dict[HandoverSectionKey, list[HandoverItem]] = {}
        for section_key in SECTION_KEYS:
            preserved: list[HandoverItem] = []
            for item in getattr(existing_content, section_key):
                if item.authority_type not in {
                    HandoverAuthorityType.SELLER_CONFIRMED,
                    HandoverAuthorityType.INFERENCE,
                    HandoverAuthorityType.UNKNOWN,
                }:
                    continue
                refreshed_ids = [
                    new_id
                    for old_id in item.source_ids
                    if (stable_key := existing_key_by_id.get(old_id)) is not None
                    if (new_id := new_id_by_key.get(stable_key)) is not None
                ]
                preserved.append(item.model_copy(update={"source_ids": refreshed_ids}))
            preserved_by_section[section_key] = preserved
        refreshed_content = self._merge_refreshed_content(preserved_by_section, generated)
        await self.repository.delete_sources(self.tenant.organisation_id, revision.id)
        await self.session.flush()
        self._persist_sources(revision, definitions)
        now = datetime.now(UTC)
        revision.content_json = refreshed_content.model_dump(mode="json", by_alias=True)
        revision.source_pack_fingerprint = self._source_pack_fingerprint(definitions)
        revision.status = "draft"
        revision.submitted_by_user_id = None
        revision.submitted_at = None
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(
            handover,
            revision,
            "draft_updated",
            {"revision": revision.revision, "sources_refreshed": True, "source_count": len(definitions)},
        )
        await self._commit("The handover source pack could not be refreshed.")
        return await self._workspace_response(opportunity, handover)

    async def submit_for_review(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverLifecycleRequest,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        self._require_manage(opportunity)
        self._require_preparable(opportunity)
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status != "draft":
            raise PublicAPIError("handover_not_draft", "Only a draft handover can be submitted for review.", 409)
        now = datetime.now(UTC)
        revision.status = "in_review"
        revision.submitted_by_user_id = self.tenant.user_id
        revision.submitted_at = now
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(handover, revision, "submitted_for_review", {"revision": revision.revision})
        await self._commit("The handover could not be submitted for review.")
        return await self._workspace_response(opportunity, handover)

    async def approve(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverLifecycleRequest,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        if self.tenant.role != "admin":
            raise PublicAPIError(
                "handover_approval_forbidden",
                "Only an organisation administrator can approve a Closed-Won Handover.",
                403,
            )
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status != "in_review":
            raise PublicAPIError("handover_not_in_review", "Submit this handover for review before approval.", 409)
        if opportunity.status != "won" or opportunity.archived_at is not None:
            raise PublicAPIError(
                "handover_opportunity_not_won",
                "A handover can be approved only while the canonical Opportunity status is Closed Won.",
                409,
            )
        blockers = await self._approval_blockers(opportunity, revision)
        if blockers:
            raise PublicAPIError(
                "handover_approval_blocked",
                "Resolve the handover review blockers before approval.",
                422,
                details={str(index): blocker for index, blocker in enumerate(blockers, start=1)},
            )
        now = datetime.now(UTC)
        current = await self.repository.current_approved_revision(
            self.tenant.organisation_id,
            handover.id,
            for_update=True,
        )
        if current is not None and current.id != revision.id:
            current.status = "superseded"
            current.superseded_at = now
            current.lock_version += 1
            current.updated_at = now
            self._audit(
                handover, current, "superseded", {"revision": current.revision, "by_revision": revision.revision}
            )
            await self.session.flush()
        revision.status = "approved"
        revision.approved_by_user_id = self.tenant.user_id
        revision.approved_at = now
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(handover, revision, "approved", {"revision": revision.revision})
        await self._commit("The handover could not be approved.")
        return await self._workspace_response(opportunity, handover)

    async def retire(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
        request: HandoverLifecycleRequest,
    ) -> HandoverWorkspaceResponse:
        await self._require_entitlement(write=True)
        opportunity, handover, revision = await self._locked(opportunity_id, revision_id)
        self._require_manage(opportunity)
        self._check_versions(handover, revision, request.expected_handover_version, request.expected_revision_version)
        if revision.status != "approved":
            raise PublicAPIError("handover_not_current", "Only the current approved handover can be retired.", 409)
        now = datetime.now(UTC)
        revision.status = "retired"
        revision.retired_at = now
        revision.retired_by_user_id = self.tenant.user_id
        revision.retirement_reason = "authorised_user_retired"
        revision.lock_version += 1
        revision.updated_at = now
        handover.lock_version += 1
        handover.updated_at = now
        self._audit(
            handover, revision, "retired", {"revision": revision.revision, "reason": revision.retirement_reason}
        )
        await self._commit("The handover could not be retired.")
        return await self._workspace_response(opportunity, handover)

    async def _opportunity(self, opportunity_id: UUID, *, for_update: bool = False) -> Opportunity:
        opportunity = await self.repository.opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=for_update,
        )
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        return opportunity

    async def _locked(
        self,
        opportunity_id: UUID,
        revision_id: UUID,
    ) -> tuple[Opportunity, ClosedWonHandover, ClosedWonHandoverRevision]:
        opportunity = await self._opportunity(opportunity_id, for_update=True)
        handover = await self.repository.handover(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if handover is None:
            raise PublicAPIError("handover_not_found", "This opportunity does not have a handover.", 404)
        revision = await self.repository.revision(
            self.tenant.organisation_id,
            handover.id,
            revision_id,
            for_update=True,
        )
        if revision is None:
            raise PublicAPIError("handover_revision_not_found", "The handover revision was not found.", 404)
        return opportunity, handover, revision

    def _can_manage(self, opportunity: Opportunity) -> bool:
        return self.tenant.role == "admin" or opportunity.owner_user_id == self.tenant.user_id

    def _require_manage(self, opportunity: Opportunity) -> None:
        if not self._can_manage(opportunity):
            raise PublicAPIError(
                "handover_forbidden",
                "Only the Opportunity owner or an organisation administrator can manage this handover.",
                403,
            )

    @staticmethod
    def _require_preparable(opportunity: Opportunity) -> None:
        if opportunity.archived_at is not None or opportunity.status not in {"open", "won"}:
            raise PublicAPIError(
                "handover_not_preparable",
                "A handover draft can be prepared only for an active open or Closed-Won Opportunity.",
                409,
            )

    async def _require_entitlement(self, *, write: bool) -> None:
        commercial = CommercialService(self.session, self.settings)
        if write:
            await commercial.require_module_write(self.tenant.organisation_id, "create")
            return
        if await commercial.module_access(self.tenant.organisation_id, "create") == "none":
            raise PublicAPIError(
                "create_not_in_plan",
                "Create isn't included in your organisation's current plan.",
                403,
            )

    @staticmethod
    def _check_versions(
        handover: ClosedWonHandover,
        revision: ClosedWonHandoverRevision,
        expected_handover_version: int,
        expected_revision_version: int,
    ) -> None:
        if handover.lock_version != expected_handover_version or revision.lock_version != expected_revision_version:
            raise PublicAPIError("handover_stale", "The handover changed; refresh and try again.", 409)

    def _persist_sources(
        self,
        revision: ClosedWonHandoverRevision,
        definitions: list[SourceDefinition],
    ) -> list[ClosedWonHandoverSource]:
        pinned_at = datetime.now(UTC)
        sources: list[ClosedWonHandoverSource] = []
        for definition in definitions:
            source = ClosedWonHandoverSource(
                id=definition.reference_id,
                organisation_id=self.tenant.organisation_id,
                revision_id=revision.id,
                opportunity_id=revision.opportunity_id,
                source_type=definition.source_type.value,
                source_id=definition.source_id,
                source_version_id=definition.source_version_id,
                source_version=definition.source_version,
                authority_type=definition.authority_type.value,
                label=definition.label,
                snapshot_json=definition.snapshot,
                source_fingerprint=definition.fingerprint,
                pinned_at=pinned_at,
            )
            sources.append(source)
            self.repository.add(source)
        return sources

    @staticmethod
    def _source_pack_fingerprint(definitions: list[SourceDefinition]) -> str:
        return _canonical_hash(
            [
                {
                    "type": definition.source_type.value,
                    "id": str(definition.source_id),
                    "versionId": str(definition.source_version_id) if definition.source_version_id else None,
                    "version": definition.source_version,
                    "fingerprint": definition.fingerprint,
                }
                for definition in definitions
            ]
        )

    async def _source_definitions(self, opportunity: Opportunity) -> list[SourceDefinition]:
        definitions: list[SourceDefinition] = []

        def append(
            source_type: HandoverSourceType,
            source_id: UUID,
            authority_type: HandoverAuthorityType,
            label: str,
            snapshot: dict[str, object],
            *,
            source_version_id: UUID | None = None,
            source_version: int | None = None,
            fingerprint: str | None = None,
        ) -> None:
            definitions.append(
                SourceDefinition(
                    reference_id=uuid.uuid4(),
                    source_type=source_type,
                    source_id=source_id,
                    source_version_id=source_version_id,
                    source_version=source_version,
                    authority_type=authority_type,
                    label=label[:240],
                    snapshot=snapshot,
                    fingerprint=fingerprint or _canonical_hash(snapshot),
                )
            )

        company = await self.repository.company(self.tenant.organisation_id, opportunity.company_id)
        opportunity_snapshot: dict[str, object] = {
            "schemaVersion": 1,
            "name": opportunity.name,
            "companyId": str(opportunity.company_id) if opportunity.company_id else None,
            "companyName": company.name if company is not None else None,
            "status": opportunity.status,
            "stage": opportunity.stage,
            "estimatedValue": _decimal(opportunity.estimated_value),
            "currency": opportunity.currency,
            "expectedCloseDate": _iso(opportunity.expected_close_date),
            "actualCloseDate": _iso(opportunity.actual_close_date),
        }
        append(
            HandoverSourceType.OPPORTUNITY,
            opportunity.id,
            HandoverAuthorityType.COMMERCIAL_RECORD,
            "Canonical Opportunity record",
            opportunity_snapshot,
        )

        deal_room = await self.repository.latest_published_deal_room(self.tenant.organisation_id, opportunity.id)
        if deal_room is not None:
            room, published = deal_room
            append(
                HandoverSourceType.DEAL_ROOM,
                room.id,
                HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                f"Published Deal Room revision {published.revision}",
                published.snapshot_json,
                source_version_id=published.id,
                source_version=published.revision,
                fingerprint=published.content_fingerprint,
            )

        for business_case, case_version in await self.repository.approved_business_cases(
            self.tenant.organisation_id, opportunity.id
        ):
            snapshot = {
                "schemaVersion": 1,
                "title": business_case.title,
                "currency": case_version.currency,
                "version": case_version.version,
                "approvedAt": _iso(case_version.approved_at),
                "calculationFingerprint": case_version.calculation_fingerprint,
            }
            append(
                HandoverSourceType.BUSINESS_CASE,
                business_case.id,
                HandoverAuthorityType.COMMERCIAL_RECORD,
                f"Approved Business Case: {business_case.title} · revision {case_version.version}",
                snapshot,
                source_version_id=case_version.id,
                source_version=case_version.version,
                fingerprint=case_version.calculation_fingerprint,
            )

        for evidence in await self.repository.evidence_snapshots(self.tenant.organisation_id, opportunity.id):
            content = evidence.content_json
            raw_label = content.get("sourceLabel")
            label = raw_label if isinstance(raw_label, str) and raw_label.strip() else "Reviewed customer Evidence"
            has_customer_direct = self._snapshot_has_customer_direct_evidence(content)
            append(
                HandoverSourceType.EVIDENCE,
                evidence.source_evidence_id,
                HandoverAuthorityType.CUSTOMER_EVIDENCE
                if has_customer_direct
                else HandoverAuthorityType.SELLER_CONFIRMED,
                f"Reviewed Evidence: {label}",
                content,
                source_version_id=evidence.id,
                source_version=evidence.version,
            )

        for contact in await self.repository.contacts(self.tenant.organisation_id, opportunity.company_id):
            full_name = f"{contact.first_name} {contact.last_name}".strip()
            snapshot = {
                "schemaVersion": 1,
                "name": full_name,
                "jobTitle": contact.job_title,
                "companyId": str(contact.company_id),
                "status": contact.status,
            }
            append(
                HandoverSourceType.CONTACT,
                contact.id,
                HandoverAuthorityType.SYSTEM_DERIVED,
                f"Canonical Contact: {full_name}",
                snapshot,
            )

        for interaction in await self.repository.interactions(self.tenant.organisation_id, opportunity.id):
            snapshot = {
                "schemaVersion": 1,
                "title": interaction.title,
                "type": interaction.interaction_type,
                "status": interaction.lifecycle_status,
                "scheduledStartAt": _iso(interaction.scheduled_start_at),
                "actualStartAt": _iso(interaction.actual_start_at),
                "actualEndAt": _iso(interaction.actual_end_at),
            }
            append(
                HandoverSourceType.INTERACTION,
                interaction.id,
                HandoverAuthorityType.SYSTEM_DERIVED,
                f"Linked Interaction: {interaction.title}",
                snapshot,
            )

        for action, action_version in await self.repository.approved_actions(
            self.tenant.organisation_id, opportunity.id
        ):
            snapshot = {
                "schemaVersion": 1,
                "title": action_version.title,
                "status": action.status,
                "actionType": action.action_type,
                "proposedDueAt": _iso(action_version.proposed_due_at),
                "approvedAt": _iso(action.approved_at),
                "reviewedByUserId": str(action.reviewed_by_user_id) if action.reviewed_by_user_id else None,
            }
            append(
                HandoverSourceType.ACTION,
                action.id,
                HandoverAuthorityType.SELLER_CONFIRMED,
                f"Approved Action: {action_version.title}",
                snapshot,
                source_version_id=action_version.id,
                source_version=action_version.version,
                fingerprint=action_version.content_fingerprint,
            )

        for task in await self.repository.tasks(self.tenant.organisation_id, opportunity.id):
            snapshot = {
                "schemaVersion": 1,
                "title": task.title,
                "status": task.status,
                "dueAt": _iso(task.due_at),
                "assignedUserId": str(task.assigned_user_id) if task.assigned_user_id else None,
            }
            append(
                HandoverSourceType.TASK,
                task.id,
                HandoverAuthorityType.SYSTEM_DERIVED,
                f"Opportunity Task: {task.title}",
                snapshot,
            )
        return definitions

    def _initial_content(
        self,
        opportunity: Opportunity,
        definitions: list[SourceDefinition],
    ) -> HandoverContent:
        sections: dict[HandoverSectionKey, list[HandoverItem]] = {key: [] for key in SECTION_KEYS}
        opportunity_source = next(item for item in definitions if item.source_type == HandoverSourceType.OPPORTUNITY)
        company_name = opportunity_source.snapshot.get("companyName")
        company_label = f" at {company_name}" if isinstance(company_name, str) and company_name else ""
        executive_text = f"Internal transition handover for {opportunity.name}{company_label}."
        sections["executive_summary"].append(
            HandoverItem(
                id=uuid.uuid4(),
                text=executive_text,
                authority_type=HandoverAuthorityType.SYSTEM_DERIVED,
                source_ids=[opportunity_source.reference_id],
            )
        )
        if opportunity.estimated_value is not None and opportunity.currency is not None:
            sections["commercial_scope"].append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text=(
                        f"Canonical Opportunity value: {opportunity.currency} {_decimal(opportunity.estimated_value)}. "
                        "This is an Opportunity record, not a contract."
                    ),
                    authority_type=HandoverAuthorityType.COMMERCIAL_RECORD,
                    source_ids=[opportunity_source.reference_id],
                )
            )
        if opportunity.status == "won" and opportunity.actual_close_date is not None:
            sections["timeline"].append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text=f"Opportunity recorded Closed Won on {opportunity.actual_close_date.isoformat()}.",
                    authority_type=HandoverAuthorityType.COMMERCIAL_RECORD,
                    source_ids=[opportunity_source.reference_id],
                )
            )

        for definition in definitions:
            if definition.source_type == HandoverSourceType.DEAL_ROOM:
                self._deal_room_items(sections, definition)
            elif definition.source_type == HandoverSourceType.EVIDENCE:
                self._evidence_items(sections, definition)
            elif definition.source_type == HandoverSourceType.CONTACT:
                name = definition.snapshot.get("name")
                job_title = definition.snapshot.get("jobTitle")
                if isinstance(name, str) and name.strip():
                    suffix = f" — {job_title}" if isinstance(job_title, str) and job_title.strip() else ""
                    sections["key_stakeholders"].append(
                        HandoverItem(
                            id=uuid.uuid4(),
                            text=f"{name}{suffix}",
                            authority_type=HandoverAuthorityType.SYSTEM_DERIVED,
                            source_ids=[definition.reference_id],
                        )
                    )
            elif definition.source_type == HandoverSourceType.TASK:
                title = definition.snapshot.get("title")
                if isinstance(title, str):
                    due = definition.snapshot.get("dueAt")
                    task_status = definition.snapshot.get("status")
                    if task_status not in {"open", "in_progress", "completed", "cancelled"}:
                        continue
                    sections["next_actions"].append(
                        HandoverItem(
                            id=uuid.uuid4(),
                            text=title,
                            authority_type=HandoverAuthorityType.SYSTEM_DERIVED,
                            source_ids=[definition.reference_id],
                            owner=None,
                            due_date=date.fromisoformat(due[:10]) if isinstance(due, str) else None,
                            action_status=cast(Literal["open", "in_progress", "completed", "cancelled"], task_status),
                        )
                    )
            elif definition.source_type == HandoverSourceType.ACTION:
                title = definition.snapshot.get("title")
                approved_at = definition.snapshot.get("approvedAt")
                reviewer_id = definition.snapshot.get("reviewedByUserId")
                if isinstance(title, str) and isinstance(approved_at, str) and isinstance(reviewer_id, str):
                    sections["next_actions"].append(
                        HandoverItem(
                            id=uuid.uuid4(),
                            text=title,
                            authority_type=HandoverAuthorityType.SELLER_CONFIRMED,
                            source_ids=[definition.reference_id],
                            confirmed_by_user_id=UUID(reviewer_id),
                            confirmed_at=datetime.fromisoformat(approved_at),
                            due_date=None,
                            action_status="open",
                        )
                    )
        return self._bounded_content(sections)

    @staticmethod
    def _bounded_content(sections: dict[HandoverSectionKey, list[HandoverItem]]) -> HandoverContent:
        bounded: dict[HandoverSectionKey, list[HandoverItem]] = {key: [] for key in SECTION_KEYS}
        total = 0
        for item_index in range(max(SECTION_ITEM_LIMITS.values())):
            for key in SECTION_KEYS:
                if total == MAX_HANDOVER_ITEMS:
                    return HandoverContent(schema_version=1, **bounded)
                items = sections[key]
                if item_index < min(len(items), SECTION_ITEM_LIMITS[key]):
                    bounded[key].append(items[item_index])
                    total += 1
        return HandoverContent(schema_version=1, **bounded)

    @staticmethod
    def _merge_refreshed_content(
        preserved: dict[HandoverSectionKey, list[HandoverItem]],
        generated: HandoverContent,
    ) -> HandoverContent:
        merged = {key: list(preserved[key]) for key in SECTION_KEYS}
        total = sum(len(items) for items in merged.values())
        for item_index in range(max(SECTION_ITEM_LIMITS.values())):
            for key in SECTION_KEYS:
                if total == MAX_HANDOVER_ITEMS:
                    return HandoverContent(schema_version=1, **merged)
                generated_items = getattr(generated, key)
                if item_index < len(generated_items) and len(merged[key]) < SECTION_ITEM_LIMITS[key]:
                    merged[key].append(generated_items[item_index])
                    total += 1
        return HandoverContent(schema_version=1, **merged)

    @staticmethod
    def _deal_room_items(sections: dict[HandoverSectionKey, list[HandoverItem]], definition: SourceDefinition) -> None:
        snapshot = definition.snapshot
        overview = snapshot.get("overview")
        if isinstance(overview, str) and overview.strip():
            sections["executive_summary"].append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text=overview,
                    authority_type=HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                    source_ids=[definition.reference_id],
                )
            )
        commercial = snapshot.get("commercialSummary")
        if isinstance(commercial, str) and commercial.strip():
            sections["commercial_scope"].append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text=commercial,
                    authority_type=HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                    source_ids=[definition.reference_id],
                )
            )
        stakeholders = snapshot.get("stakeholders")
        if isinstance(stakeholders, list):
            for stakeholder in stakeholders[:12]:
                if not isinstance(stakeholder, dict):
                    continue
                name = stakeholder.get("name")
                role = stakeholder.get("role")
                company = stakeholder.get("company")
                if all(isinstance(value, str) and value.strip() for value in (name, role, company)):
                    sections["key_stakeholders"].append(
                        HandoverItem(
                            id=uuid.uuid4(),
                            text=f"{name} — {role}, {company}",
                            authority_type=HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                            source_ids=[definition.reference_id],
                        )
                    )
        milestones = snapshot.get("milestones")
        if isinstance(milestones, list):
            for milestone in milestones[:20]:
                if not isinstance(milestone, dict):
                    continue
                title = milestone.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue
                target_date = milestone.get("targetDate")
                owner = milestone.get("ownerParty")
                suffix = f" · target {target_date}" if isinstance(target_date, str) else ""
                sections["timeline"].append(
                    HandoverItem(
                        id=uuid.uuid4(),
                        text=f"{title}{suffix}",
                        authority_type=HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                        source_ids=[definition.reference_id],
                    )
                )
                sections["next_actions"].append(
                    HandoverItem(
                        id=uuid.uuid4(),
                        text=title,
                        authority_type=HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                        source_ids=[definition.reference_id],
                        owner=owner if isinstance(owner, str) else None,
                        due_date=date.fromisoformat(target_date) if isinstance(target_date, str) else None,
                        action_status="completed" if milestone.get("status") == "done" else "open",
                    )
                )

    @staticmethod
    def _snapshot_has_customer_direct_evidence(snapshot: dict[str, object]) -> bool:
        raw_items = snapshot.get("items")
        return isinstance(raw_items, list) and any(
            isinstance(item, dict)
            and item.get("originClass") == "customer_direct"
            and item.get("supportClass") in {"direct", "reported", "corroborated", "verified"}
            and item.get("conflictState") not in {"conflicting", "superseded"}
            for item in raw_items
        )

    @staticmethod
    def _evidence_items(sections: dict[HandoverSectionKey, list[HandoverItem]], definition: SourceDefinition) -> None:
        section_for_category: dict[str, HandoverSectionKey] = {
            "commitment": "commitments",
            "implementation": "implementation_expectations",
            "technical_requirement": "implementation_expectations",
            "risk": "risks",
            "open_question": "open_items",
            "timeline": "timeline",
        }
        raw_items = definition.snapshot.get("items")
        if not isinstance(raw_items, list):
            return
        for raw_item in raw_items[:100]:
            if not isinstance(raw_item, dict):
                continue
            if raw_item.get("originClass") != "customer_direct":
                continue
            if raw_item.get("supportClass") not in {"direct", "reported", "corroborated", "verified"}:
                continue
            if raw_item.get("conflictState") in {"conflicting", "superseded"}:
                continue
            category = raw_item.get("category")
            statement = raw_item.get("statement")
            section = section_for_category.get(category) if isinstance(category, str) else None
            if section is None or not isinstance(statement, str) or not statement.strip():
                continue
            sections[section].append(
                HandoverItem(
                    id=uuid.uuid4(),
                    text=statement,
                    authority_type=HandoverAuthorityType.CUSTOMER_EVIDENCE,
                    source_ids=[definition.reference_id],
                    risk_kind="observed_risk" if section == "risks" else None,
                )
            )

    def _normalise_manual_edits(
        self,
        existing: HandoverContent,
        incoming: HandoverContent,
        source_ids: set[UUID],
    ) -> tuple[HandoverContent, int]:
        existing_positions: dict[UUID, tuple[str, HandoverItem]] = {}
        for key in SECTION_KEYS:
            for item in getattr(existing, key):
                existing_positions[item.id] = (key, item)
        changed = 0
        now = datetime.now(UTC)
        normalised: dict[str, list[HandoverItem]] = {}
        for key in SECTION_KEYS:
            items: list[HandoverItem] = []
            for item in getattr(incoming, key):
                if not set(item.source_ids).issubset(source_ids):
                    raise PublicAPIError(
                        "handover_source_invalid",
                        "Every handover source must come from this revision's server-owned source pack.",
                        422,
                    )
                prior = existing_positions.get(item.id)
                if prior is not None and prior[0] == key and prior[1] == item:
                    items.append(item)
                    continue
                changed += 1
                items.append(
                    item.model_copy(
                        update={
                            "authority_type": HandoverAuthorityType.SELLER_CONFIRMED,
                            "confirmed_by_user_id": self.tenant.user_id,
                            "confirmed_at": now,
                            "risk_kind": "seller_concern" if key == "risks" else item.risk_kind,
                        }
                    )
                )
            normalised[key] = items
        return HandoverContent(schema_version=1, **normalised), changed

    async def _approval_blockers(
        self,
        opportunity: Opportunity,
        revision: ClosedWonHandoverRevision,
    ) -> list[str]:
        blockers: list[str] = []
        try:
            content = HandoverContent.model_validate(revision.content_json)
        except ValidationError:
            return ["The handover content does not match the approved schema."]
        sources = await self.repository.sources(self.tenant.organisation_id, revision.id)
        source_by_id = {source.id: source for source in sources}
        for key in SECTION_KEYS:
            for item in getattr(content, key):
                if item.authority_type == HandoverAuthorityType.INFERENCE:
                    blockers.append(f"{key}: confirm or remove the inference before approval.")
                if item.authority_type == HandoverAuthorityType.UNKNOWN:
                    blockers.append(f"{key}: confirm or remove the unknown item before approval.")
                if key in HIGH_RISK_SECTIONS and item.authority_type not in HIGH_RISK_AUTHORITIES:
                    blockers.append(f"{key}: an item does not have an approved high-risk authority.")
                if not set(item.source_ids).issubset(source_by_id):
                    blockers.append(f"{key}: an item references a source outside this handover revision.")
                cited_sources = [source_by_id[source_id] for source_id in item.source_ids if source_id in source_by_id]
                if item.authority_type == HandoverAuthorityType.CUSTOMER_EVIDENCE and not any(
                    source.source_type == "evidence"
                    and source.authority_type == HandoverAuthorityType.CUSTOMER_EVIDENCE.value
                    for source in cited_sources
                ):
                    blockers.append(f"{key}: Customer Evidence authority requires a pinned Evidence source.")
                if item.authority_type == HandoverAuthorityType.COMMERCIAL_RECORD and not any(
                    source.source_type in {"opportunity", "business_case"}
                    and source.authority_type == HandoverAuthorityType.COMMERCIAL_RECORD.value
                    for source in cited_sources
                ):
                    blockers.append(f"{key}: Commercial Record authority requires a canonical commercial source.")
                if item.authority_type == HandoverAuthorityType.CUSTOMER_FACING_APPROVED and not any(
                    source.source_type == "deal_room"
                    and source.authority_type == HandoverAuthorityType.CUSTOMER_FACING_APPROVED.value
                    for source in cited_sources
                ):
                    blockers.append(f"{key}: customer-facing approved context requires a published Deal Room source.")

        current_definitions = await self._source_definitions(opportunity)
        current_by_key = {definition.stable_key: definition for definition in current_definitions}
        for key in SECTION_KEYS:
            for item in getattr(content, key):
                if item.authority_type == HandoverAuthorityType.SELLER_CONFIRMED:
                    continue
                for source_id in item.source_ids:
                    source = source_by_id.get(source_id)
                    if source is None:
                        continue
                    stable_key = (
                        source.source_type,
                        source.source_id,
                        source.source_version_id,
                        source.source_version,
                    )
                    current = current_by_key.get(stable_key)
                    if current is None or current.fingerprint != source.source_fingerprint:
                        version = f" revision {source.source_version}" if source.source_version is not None else ""
                        blockers.append(
                            f"A pinned {source.source_type.replace('_', ' ')} source{version} changed or is no "
                            "longer available; review its items again."
                        )
        return list(dict.fromkeys(blockers))

    async def _workspace_response(
        self,
        opportunity: Opportunity,
        handover: ClosedWonHandover | None,
    ) -> HandoverWorkspaceResponse:
        can_manage = self._can_manage(opportunity)
        if handover is None:
            return HandoverWorkspaceResponse(
                handover_id=None,
                opportunity_id=opportunity.id,
                opportunity_status=cast(Literal["open", "won", "lost", "on_hold"], opportunity.status),
                handover_lock_version=None,
                active_revision=None,
                current_approved_revision=None,
                history=[],
                can_manage=can_manage,
                can_approve=self.tenant.role == "admin",
            )
        revisions = await self.repository.revisions(self.tenant.organisation_id, handover.id)
        editable = next((item for item in revisions if item.status in {"draft", "in_review"}), None)
        current = next((item for item in revisions if item.status == "approved"), None)
        active = editable if can_manage and editable is not None else current
        visible_history = (
            revisions
            if can_manage
            else [item for item in revisions if item.status in {"approved", "superseded", "retired"}]
        )
        return HandoverWorkspaceResponse(
            handover_id=handover.id,
            opportunity_id=opportunity.id,
            opportunity_status=cast(Literal["open", "won", "lost", "on_hold"], opportunity.status),
            handover_lock_version=handover.lock_version,
            active_revision=await self._revision_response(opportunity, active) if active is not None else None,
            current_approved_revision=self._revision_summary(current) if current is not None else None,
            history=[self._revision_summary(item) for item in visible_history],
            can_manage=can_manage,
            can_approve=self.tenant.role == "admin",
        )

    async def _revision_response(
        self,
        opportunity: Opportunity,
        revision: ClosedWonHandoverRevision,
    ) -> HandoverRevisionResponse:
        sources = await self.repository.sources(self.tenant.organisation_id, revision.id)
        blockers = (
            await self._approval_blockers(opportunity, revision) if revision.status in {"draft", "in_review"} else []
        )
        return HandoverRevisionResponse(
            **self._revision_summary(revision).model_dump(),
            handover_id=revision.handover_id,
            opportunity_id=revision.opportunity_id,
            content_schema_version=cast(Literal[1], revision.content_schema_version),
            content=HandoverContent.model_validate(revision.content_json),
            sources=[
                HandoverSourceResponse(
                    id=source.id,
                    source_type=cast(HandoverSourceType, source.source_type),
                    source_id=source.source_id,
                    source_version_id=source.source_version_id,
                    source_version=source.source_version,
                    authority_type=cast(HandoverAuthorityType, source.authority_type),
                    label=source.label,
                    source_fingerprint=source.source_fingerprint,
                    pinned_at=source.pinned_at,
                )
                for source in sources
            ],
            lock_version=revision.lock_version,
            approval_blockers=blockers,
        )

    @staticmethod
    def _revision_summary(revision: ClosedWonHandoverRevision) -> HandoverRevisionSummary:
        return HandoverRevisionSummary(
            id=revision.id,
            revision=revision.revision,
            status=cast(ClosedWonHandoverStatus, revision.status),
            created_by_user_id=revision.created_by_user_id,
            submitted_at=revision.submitted_at,
            approved_by_user_id=revision.approved_by_user_id,
            approved_at=revision.approved_at,
            superseded_at=revision.superseded_at,
            retired_at=revision.retired_at,
            retirement_reason=revision.retirement_reason,
            created_at=revision.created_at,
            updated_at=revision.updated_at,
        )

    def _audit(
        self,
        handover: ClosedWonHandover,
        revision: ClosedWonHandoverRevision,
        action: str,
        metadata: dict[str, object],
    ) -> None:
        self.repository.add(
            ClosedWonHandoverAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                handover_id=handover.id,
                revision_id=revision.id,
                actor_user_id=self.tenant.user_id,
                action=action,
                metadata_json=metadata,
            )
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("handover_conflict", message, 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("handover_persistence_failure", message, 500) from exc
