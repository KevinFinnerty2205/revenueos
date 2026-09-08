from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from time import monotonic
from typing import Literal, NoReturn, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_case_contracts import ScenarioCalculationResponse
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.deal_room_contracts import (
    DealRoomAdminResponse,
    DealRoomBusinessCaseOption,
    DealRoomDraftContent,
    DealRoomDraftUpdate,
    DealRoomLifecycleRequest,
    DealRoomLinkRotationRequest,
    DealRoomLinkSummary,
    DealRoomMutationResponse,
    DealRoomPresentationOption,
    DealRoomPublishRequest,
    DealRoomRevisionSummary,
    DealRoomWorkspaceResponse,
    PublicDealRoomBusinessCase,
    PublicDealRoomBusinessCaseOutput,
    PublicDealRoomBusinessCaseScenario,
    PublicDealRoomMilestone,
    PublicDealRoomProjection,
    PublicDealRoomResolveResponse,
    PublicDealRoomResource,
    PublicDealRoomStakeholder,
)
from revenueos.deal_room_repositories import DealRoomRepository, PublicPresentationRecord
from revenueos.domain import DealRoomResourceKind, DealRoomStatus
from revenueos.errors import PublicAPIError
from revenueos.models import (
    DealRoom,
    DealRoomAccessLink,
    DealRoomAuditEvent,
    DealRoomRevision,
    Opportunity,
)
from revenueos.tenant import TenantContext
from revenueos.visual_storage import VisualObjectMissingError, VisualStorage, VisualStorageError

_SHARE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{40,200}$")
_PUBLIC_UNAVAILABLE = "This Deal Room is no longer available."


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _safe_file_name(value: str) -> str:
    normalised = re.sub(r"[^A-Za-z0-9 ._-]+", "", value).strip(" .")
    return f"{normalised[:100] or 'Presentation'}.pptx"


class PublicDealRoomRateLimiter:
    """Process-local defence in depth without plaintext address or token retention."""

    def __init__(self) -> None:
        self._secret = secrets.token_bytes(32)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_address: str, access_token: str, limit: int) -> None:
        key_material = f"{client_address}\0{access_token}".encode()
        key = hmac.digest(self._secret, key_material, "sha256").hex()
        current = monotonic()
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= current - 60:
                requests.popleft()
            if len(requests) >= limit:
                raise PublicAPIError(
                    "deal_room_rate_limited",
                    "Too many Deal Room requests. Wait a moment and try again.",
                    429,
                )
            requests.append(current)
            if len(self._requests) > 10_000:
                self._requests = defaultdict(deque, {key: requests})


public_rate_limiter = PublicDealRoomRateLimiter()


class DealRoomService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = DealRoomRepository(session)

    async def workspace(self, opportunity_id: UUID) -> DealRoomWorkspaceResponse:
        await self._require_entitlement(write=False)
        opportunity = await self._opportunity(opportunity_id)
        self._require_authority(opportunity)
        room = await self.repository.room_for_opportunity(self.tenant.organisation_id, opportunity_id)
        return await self._workspace_response(opportunity, room)

    async def create(self, opportunity_id: UUID) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity = await self._opportunity(opportunity_id, for_update=True)
        self._require_authority(opportunity)
        self._require_open(opportunity)
        existing = await self.repository.room_for_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if existing is not None:
            raise PublicAPIError(
                "deal_room_exists",
                "This opportunity already has a Deal Room.",
                409,
            )
        room = DealRoom(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            created_by_user_id=self.tenant.user_id,
            draft_content_json=DealRoomDraftContent().model_dump(mode="json", by_alias=True),
        )
        self.repository.add(room)
        await self.session.flush()
        self._audit(room, "created", {"draft_version": 1})
        await self._commit("The Deal Room could not be created.")
        return DealRoomMutationResponse(workspace=await self._workspace_response(opportunity, room))

    async def update_draft(
        self,
        opportunity_id: UUID,
        request: DealRoomDraftUpdate,
    ) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity, room = await self._locked(opportunity_id)
        self._require_authority(opportunity)
        self._require_open(opportunity)
        self._check_versions(
            room,
            expected_draft_version=request.expected_draft_version,
            expected_lock_version=request.expected_lock_version,
        )
        await self._validate_draft_sources(opportunity, request.content)
        previous = DealRoomDraftContent.model_validate(room.draft_content_json)
        next_json = request.content.model_dump(mode="json", by_alias=True)
        changed_sections = sorted(
            key for key in next_json if previous.model_dump(mode="json", by_alias=True).get(key) != next_json.get(key)
        )
        if changed_sections:
            room.draft_content_json = next_json
            room.draft_version += 1
            room.lock_version += 1
            room.updated_at = datetime.now(UTC)
            self._audit(
                room,
                "draft_updated",
                {"draft_version": room.draft_version, "changed_sections": changed_sections},
            )
            if "resources" in changed_sections:
                self._audit(room, "resource_changed", {"resource_count": len(request.content.resources)})
            if "businessCaseVersionId" in changed_sections or "resources" in changed_sections:
                self._audit(
                    room,
                    "publication_source_changed",
                    {
                        "business_case_selected": request.content.business_case_version_id is not None,
                        "presentation_count": sum(
                            item.kind == DealRoomResourceKind.PRESENTATION for item in request.content.resources
                        ),
                    },
                )
        await self._commit("The Deal Room draft could not be saved.")
        return DealRoomMutationResponse(workspace=await self._workspace_response(opportunity, room))

    async def publish(
        self,
        opportunity_id: UUID,
        request: DealRoomPublishRequest,
    ) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity, room = await self._locked(opportunity_id)
        self._require_authority(opportunity)
        self._require_open(opportunity)
        self._check_versions(
            room,
            expected_draft_version=request.expected_draft_version,
            expected_lock_version=request.expected_lock_version,
        )
        draft = DealRoomDraftContent.model_validate(room.draft_content_json)
        await self._validate_draft_sources(opportunity, draft)
        now = datetime.now(UTC)
        if request.link_expires_at is not None and _utc(request.link_expires_at) <= now:
            raise PublicAPIError("deal_room_expiry_invalid", "Choose a future link expiry.", 422)
        revisions = await self.repository.revisions(self.tenant.organisation_id, room.id)
        revision_number = revisions[0].revision + 1 if revisions else 1
        snapshot = await self._snapshot(opportunity, draft, revision_number, now)
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        revision = DealRoomRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            room_id=room.id,
            revision=revision_number,
            snapshot_schema_version=1,
            snapshot_json=snapshot,
            content_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            published_by_user_id=self.tenant.user_id,
            published_at=now,
        )
        self.repository.add(revision)
        await self.session.flush()
        active_link = await self.repository.active_link(self.tenant.organisation_id, room.id)
        share_token: str | None = None
        if active_link is None:
            share_token, active_link = self._new_link(room, request.link_expires_at, now)
            self.repository.add(active_link)
        else:
            active_link.expires_at = request.link_expires_at
        action: Literal["published", "republished"] = "republished" if revisions else "published"
        room.published_revision_id = revision.id
        room.status = DealRoomStatus.PUBLISHED.value
        room.last_published_at = now
        room.paused_at = None
        room.revoked_at = None
        room.lock_version += 1
        room.updated_at = now
        self._audit(
            room,
            action,
            {
                "revision": revision_number,
                "draft_version": room.draft_version,
                "link_created": share_token is not None,
                "link_expiry_set": request.link_expires_at is not None,
            },
        )
        await self._commit("The Deal Room could not be published.")
        return DealRoomMutationResponse(
            workspace=await self._workspace_response(opportunity, room),
            share_token=share_token,
        )

    async def pause(
        self,
        opportunity_id: UUID,
        request: DealRoomLifecycleRequest,
    ) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity, room = await self._locked(opportunity_id)
        self._require_authority(opportunity)
        self._check_lock(room, request.expected_lock_version)
        if room.status != DealRoomStatus.PUBLISHED.value:
            raise PublicAPIError("deal_room_not_published", "Only a published Deal Room can be paused.", 409)
        now = datetime.now(UTC)
        room.status = DealRoomStatus.PAUSED.value
        room.paused_at = now
        room.lock_version += 1
        room.updated_at = now
        self._audit(room, "paused", {"published_revision_id": str(room.published_revision_id)})
        await self._commit("The Deal Room could not be paused.")
        return DealRoomMutationResponse(workspace=await self._workspace_response(opportunity, room))

    async def revoke(
        self,
        opportunity_id: UUID,
        request: DealRoomLifecycleRequest,
    ) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity, room = await self._locked(opportunity_id)
        self._require_authority(opportunity)
        if room.published_revision_id is None:
            raise PublicAPIError("deal_room_not_published", "Publish this Deal Room before revoking it.", 409)
        # Revocation is deliberately safety-biased: a stale revoke still terminates
        # whichever link is current after waiting for the publication row lock.
        # A concurrent publish that runs second still fails its optimistic check.
        stale_request = room.lock_version != request.expected_lock_version
        now = datetime.now(UTC)
        active_link = await self.repository.active_link(self.tenant.organisation_id, room.id)
        if active_link is not None:
            active_link.revoked_at = now
            active_link.revoked_by_user_id = self.tenant.user_id
        room.status = DealRoomStatus.REVOKED.value
        room.revoked_at = now
        room.lock_version += 1
        room.updated_at = now
        self._audit(
            room,
            "revoked",
            {"link_revoked": active_link is not None, "stale_request_applied_for_safety": stale_request},
        )
        await self._commit("The Deal Room could not be revoked.")
        return DealRoomMutationResponse(workspace=await self._workspace_response(opportunity, room))

    async def rotate_link(
        self,
        opportunity_id: UUID,
        request: DealRoomLinkRotationRequest,
    ) -> DealRoomMutationResponse:
        await self._require_entitlement(write=True)
        opportunity, room = await self._locked(opportunity_id)
        self._require_authority(opportunity)
        self._require_open(opportunity)
        self._check_lock(room, request.expected_lock_version)
        if room.status != DealRoomStatus.PUBLISHED.value:
            raise PublicAPIError("deal_room_not_published", "Publish this Deal Room before rotating its link.", 409)
        now = datetime.now(UTC)
        if request.expires_at is not None and _utc(request.expires_at) <= now:
            raise PublicAPIError("deal_room_expiry_invalid", "Choose a future link expiry.", 422)
        active_link = await self.repository.active_link(self.tenant.organisation_id, room.id)
        if active_link is not None:
            active_link.revoked_at = now
            active_link.revoked_by_user_id = self.tenant.user_id
            await self.session.flush()
        share_token, next_link = self._new_link(room, request.expires_at, now)
        self.repository.add(next_link)
        room.lock_version += 1
        room.updated_at = now
        self._audit(room, "link_rotated", {"expires": request.expires_at is not None})
        await self._commit("The Deal Room link could not be rotated.")
        return DealRoomMutationResponse(
            workspace=await self._workspace_response(opportunity, room),
            share_token=share_token,
        )

    async def _opportunity(self, opportunity_id: UUID, *, for_update: bool = False) -> Opportunity:
        opportunity = await self.repository.opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=for_update,
        )
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        return opportunity

    async def _locked(self, opportunity_id: UUID) -> tuple[Opportunity, DealRoom]:
        opportunity = await self._opportunity(opportunity_id, for_update=True)
        room = await self.repository.room_for_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=True,
        )
        if room is None:
            raise PublicAPIError("deal_room_not_found", "This opportunity does not have a Deal Room.", 404)
        return opportunity, room

    def _require_authority(self, opportunity: Opportunity) -> None:
        if self.tenant.role != "admin" and opportunity.owner_user_id != self.tenant.user_id:
            raise PublicAPIError(
                "deal_room_forbidden",
                "Only the opportunity owner or an organisation administrator can manage this Deal Room.",
                403,
            )

    @staticmethod
    def _require_open(opportunity: Opportunity) -> None:
        if opportunity.status != "open" or opportunity.archived_at is not None:
            raise PublicAPIError(
                "opportunity_not_active",
                "A Deal Room can be changed or published only for an active opportunity.",
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
    def _check_lock(room: DealRoom, expected: int) -> None:
        if room.lock_version != expected:
            raise PublicAPIError("deal_room_stale", "The Deal Room changed; refresh and try again.", 409)

    @classmethod
    def _check_versions(cls, room: DealRoom, *, expected_draft_version: int, expected_lock_version: int) -> None:
        cls._check_lock(room, expected_lock_version)
        if room.draft_version != expected_draft_version:
            raise PublicAPIError("deal_room_draft_stale", "The Deal Room draft changed; refresh and try again.", 409)

    async def _validate_draft_sources(self, opportunity: Opportunity, draft: DealRoomDraftContent) -> None:
        if draft.business_case_version_id is not None:
            selected = await self.repository.approved_business_case(
                self.tenant.organisation_id,
                opportunity.id,
                draft.business_case_version_id,
            )
            if selected is None:
                raise PublicAPIError(
                    "deal_room_business_case_invalid",
                    "Choose an approved Business Case revision for this opportunity.",
                    422,
                )
        for stakeholder in draft.stakeholders:
            if stakeholder.source_contact_id is None:
                continue
            contact = await self.repository.contact(
                self.tenant.organisation_id,
                opportunity.company_id,
                stakeholder.source_contact_id,
            )
            if contact is None or stakeholder.party != "customer":
                raise PublicAPIError(
                    "deal_room_stakeholder_invalid",
                    "A selected customer stakeholder is not available for this opportunity.",
                    422,
                )
        for resource in draft.resources:
            if resource.kind != DealRoomResourceKind.PRESENTATION:
                continue
            assert resource.presentation_version_id is not None
            presentation_selection = await self.repository.approved_presentation(
                self.tenant.organisation_id,
                opportunity.id,
                resource.presentation_version_id,
            )
            if presentation_selection is None:
                raise PublicAPIError(
                    "deal_room_presentation_invalid",
                    "Choose an approved, available presentation revision for this opportunity.",
                    422,
                )

    async def _snapshot(
        self,
        opportunity: Opportunity,
        draft: DealRoomDraftContent,
        revision_number: int,
        published_at: datetime,
    ) -> dict[str, object]:
        organisation = await self.repository.organisation(self.tenant.organisation_id)
        if organisation is None:
            raise PublicAPIError("organisation_not_found", "The organisation was not found.", 404)
        company = await self.repository.company(self.tenant.organisation_id, opportunity.company_id)
        business_case = await self._business_case_snapshot(opportunity, draft.business_case_version_id)
        resources: list[PublicDealRoomResource] = []
        for resource in draft.resources:
            if resource.kind == DealRoomResourceKind.EXTERNAL_LINK:
                resources.append(
                    PublicDealRoomResource(
                        id=resource.id,
                        kind=resource.kind,
                        title=resource.title,
                        url=resource.external_url,
                    )
                )
                continue
            assert resource.presentation_version_id is not None
            resources.append(
                PublicDealRoomResource(
                    id=resource.id,
                    kind=resource.kind,
                    title=resource.title,
                    presentation_version_id=resource.presentation_version_id,
                    download_available=True,
                )
            )
        projection = PublicDealRoomProjection(
            revision=revision_number,
            published_at=published_at,
            seller_company_name=organisation.name,
            customer_company_name=company.name if company is not None else None,
            opportunity_name=opportunity.name,
            overview=draft.overview,
            business_case=business_case,
            commercial_summary=draft.commercial_summary,
            stakeholders=[
                PublicDealRoomStakeholder(
                    id=item.id,
                    name=item.name,
                    role=item.role,
                    company=item.company,
                    party=item.party,
                )
                for item in draft.stakeholders
            ],
            milestones=[
                PublicDealRoomMilestone(
                    id=item.id,
                    title=item.title,
                    owner_party=item.owner_party,
                    target_date=item.target_date,
                    status=item.status,
                    note=item.note,
                )
                for item in draft.milestones
            ],
            resources=resources,
            next_meeting_at=draft.next_meeting_at,
        )
        snapshot = cast(dict[str, object], projection.model_dump(mode="json", by_alias=True))
        if business_case is not None:
            snapshot_business_case = cast(dict[str, object], snapshot["businessCase"])
            snapshot_business_case["caseId"] = str(business_case.case_id)
            snapshot_business_case["versionId"] = str(business_case.version_id)
        snapshot_resources = cast(list[dict[str, object]], snapshot["resources"])
        for resource_snapshot, published_resource in zip(snapshot_resources, resources, strict=True):
            if published_resource.presentation_version_id is not None:
                resource_snapshot["presentationVersionId"] = str(published_resource.presentation_version_id)
        return snapshot

    async def _business_case_snapshot(
        self,
        opportunity: Opportunity,
        version_id: UUID | None,
    ) -> PublicDealRoomBusinessCase | None:
        if version_id is None:
            return None
        selected = await self.repository.approved_business_case(
            self.tenant.organisation_id,
            opportunity.id,
            version_id,
        )
        if selected is None:
            raise PublicAPIError(
                "deal_room_business_case_invalid",
                "Choose an approved Business Case revision for this opportunity.",
                422,
            )
        business_case, version = selected
        scenarios: list[PublicDealRoomBusinessCaseScenario] = []
        try:
            parsed_scenarios = [ScenarioCalculationResponse.model_validate(item) for item in version.scenarios_json]
        except ValidationError as exc:
            raise PublicAPIError(
                "deal_room_business_case_invalid",
                "The approved Business Case revision could not be safely published.",
                409,
            ) from exc
        for scenario in parsed_scenarios[:3]:
            outputs = [
                PublicDealRoomBusinessCaseOutput(
                    label=output.label,
                    value=output.display_value or "Unavailable",
                    unit=output.unit,
                )
                for output in scenario.outputs
                if output.customer_facing
            ][:8]
            if outputs:
                scenarios.append(PublicDealRoomBusinessCaseScenario(name=scenario.name, outputs=outputs))
        return PublicDealRoomBusinessCase(
            title=business_case.title,
            case_id=business_case.id,
            version_id=version.id,
            version=version.version,
            currency=version.currency,
            scenarios=scenarios,
        )

    def _new_link(
        self,
        room: DealRoom,
        expires_at: datetime | None,
        now: datetime,
    ) -> tuple[str, DealRoomAccessLink]:
        token = secrets.token_urlsafe(32)
        return token, DealRoomAccessLink(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            room_id=room.id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
            created_by_user_id=self.tenant.user_id,
            created_at=now,
        )

    def _audit(self, room: DealRoom, action: str, metadata: dict[str, object]) -> None:
        self.repository.add(
            DealRoomAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                room_id=room.id,
                actor_user_id=self.tenant.user_id,
                action=action,
                metadata_json=metadata,
            )
        )

    async def _workspace_response(
        self,
        opportunity: Opportunity,
        room: DealRoom | None,
    ) -> DealRoomWorkspaceResponse:
        case_rows = await self.repository.approved_business_cases(self.tenant.organisation_id, opportunity.id)
        presentation_rows = await self.repository.approved_presentations(
            self.tenant.organisation_id,
            opportunity.id,
        )
        room_response: DealRoomAdminResponse | None = None
        if room is not None:
            revisions = await self.repository.revisions(self.tenant.organisation_id, room.id)
            link = await self.repository.active_link(self.tenant.organisation_id, room.id)
            published = next((item for item in revisions if item.id == room.published_revision_id), None)
            room_response = DealRoomAdminResponse(
                id=room.id,
                opportunity_id=room.opportunity_id,
                status=cast(DealRoomStatus, room.status),
                effective_access=(
                    "available"
                    if room.status == DealRoomStatus.PUBLISHED.value
                    and opportunity.status == "open"
                    and opportunity.archived_at is None
                    and link is not None
                    and (link.expires_at is None or _utc(link.expires_at) > datetime.now(UTC))
                    else "unavailable"
                ),
                draft_version=room.draft_version,
                lock_version=room.lock_version,
                draft=DealRoomDraftContent.model_validate(room.draft_content_json),
                published_revision_id=room.published_revision_id,
                published_revision=published.revision if published is not None else None,
                last_published_at=room.last_published_at,
                link=DealRoomLinkSummary(
                    active=link is not None and link.revoked_at is None,
                    expires_at=link.expires_at if link is not None else None,
                    created_at=link.created_at if link is not None else None,
                ),
                revisions=[
                    DealRoomRevisionSummary(
                        id=item.id,
                        revision=item.revision,
                        published_at=item.published_at,
                        published_by_user_id=item.published_by_user_id,
                        content_fingerprint=item.content_fingerprint,
                    )
                    for item in revisions
                ],
                created_at=room.created_at,
                updated_at=room.updated_at,
            )
        return DealRoomWorkspaceResponse(
            room=room_response,
            business_cases=[
                DealRoomBusinessCaseOption(
                    case_id=case.id,
                    version_id=version.id,
                    title=case.title,
                    version=version.version,
                    approved_at=cast(datetime, version.approved_at),
                )
                for case, version in case_rows
            ],
            presentations=[
                DealRoomPresentationOption(
                    presentation_id=presentation.id,
                    version_id=version.id,
                    title=presentation.title,
                    version=version.version,
                    approved_at=cast(datetime, version.approved_at),
                )
                for presentation, version in presentation_rows
            ],
        )

    async def _commit(self, safe_message: str) -> None:
        try:
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError("deal_room_persistence_failure", safe_message, 500) from exc


class PublicDealRoomService:
    def __init__(self, session: AsyncSession, storage: VisualStorage) -> None:
        self.session = session
        self.repository = DealRoomRepository(session)
        self.storage = storage

    async def resolve(self, token: str) -> PublicDealRoomResolveResponse:
        token_hash = self._token_hash(token)
        record = await self.repository.public_projection(token_hash, datetime.now(UTC))
        if record is None:
            self._unavailable()
        try:
            projection = PublicDealRoomProjection.model_validate(record.snapshot)
        except ValidationError:
            self._unavailable()
        return PublicDealRoomResolveResponse(room=projection, expires_at=record.expires_at)

    async def download(self, token: str, resource_id: UUID) -> tuple[bytes, str]:
        token_hash = self._token_hash(token)
        record = await self.repository.public_presentation(token_hash, resource_id, datetime.now(UTC))
        if record is None:
            self._unavailable()
        content = await self._read_resource(record)
        return content, _safe_file_name(record.resource_title)

    async def _read_resource(self, record: PublicPresentationRecord) -> bytes:
        try:
            content = await self.storage.read(record.storage_key)
        except (VisualObjectMissingError, VisualStorageError):
            self._unavailable()
        if record.byte_size and len(content) != record.byte_size:
            self._unavailable()
        actual = hashlib.sha256(content).hexdigest()
        if not secrets.compare_digest(actual, record.checksum_sha256):
            self._unavailable()
        return content

    @staticmethod
    def _token_hash(token: str) -> str:
        token = token.strip()
        if not _SHARE_TOKEN.fullmatch(token):
            PublicDealRoomService._unavailable()
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _unavailable() -> NoReturn:
        raise PublicAPIError("deal_room_unavailable", _PUBLIC_UNAVAILABLE, 404)
