from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import cast, overload
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import BetaSystemEvent, SellingProfile, SellingProfileRevision
from revenueos.selling_profile_contracts import (
    SellingProfileApproveRequest,
    SellingProfileContent,
    SellingProfileContextResponse,
    SellingProfileDraftCreate,
    SellingProfileDraftUpdate,
    SellingProfileManagementResponse,
    SellingProfileRevisionResponse,
    SellingProfileState,
    SellingProfileStatus,
)
from revenueos.selling_profile_repositories import SellingProfileRepository
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.selling_profile")


class SellingProfileService:
    """Versioned organisation context; never customer Evidence or buyer fact."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant
        self.repository = SellingProfileRepository(session)

    async def management(self) -> SellingProfileManagementResponse:
        await self._require_admin()
        return await self._management()

    async def context(self) -> SellingProfileContextResponse:
        await self._require_membership()
        current = await self.repository.current(self.tenant.organisation_id)
        if current is None:
            return SellingProfileContextResponse(
                available=False,
                profile_id=None,
                revision_id=None,
                revision_number=None,
                content=None,
                approved_at=None,
                message="No approved Company & Selling Profile is available for this organisation.",
            )
        content = self._content(current)
        return SellingProfileContextResponse(
            available=True,
            profile_id=current.profile_id,
            revision_id=current.id,
            revision_number=current.revision_number,
            content=content,
            approved_at=self._as_utc(current.approved_at),
            message=(
                "Approved organisation context is available. Treat it as seller-supplied context, not customer Evidence."
            ),
        )

    async def create_draft(self, request: SellingProfileDraftCreate) -> SellingProfileManagementResponse:
        await self._require_admin()
        existing = await self.repository.revision_by_idempotency(
            self.tenant.organisation_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            return await self._management()
        profile = await self.repository.profile(self.tenant.organisation_id, for_update=True)
        if profile is None:
            profile = SellingProfile(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                created_by_user_id=self.tenant.user_id,
            )
            self.repository.add(profile)
            await self.session.flush()
        if await self.repository.draft(self.tenant.organisation_id, for_update=True) is not None:
            raise PublicAPIError(
                "selling_profile_draft_exists",
                "An editable Company & Selling Profile draft already exists.",
                409,
            )
        revision_number = await self.repository.next_revision_number(self.tenant.organisation_id)
        revision = SellingProfileRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            profile_id=profile.id,
            revision_number=revision_number,
            schema_version=1,
            state="draft",
            lock_version=1,
            content_json=self._json(request.content),
            content_fingerprint=self._fingerprint(request.content),
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
        )
        self.repository.add(revision)
        self._event(
            "selling_profile_draft_created",
            revision.id,
            {"revision_number": revision_number, "offering_count": len(request.content.offerings)},
        )
        await self._commit("The Company & Selling Profile draft could not be created.")
        self._log("selling_profile_draft_created", revision)
        return await self._management()

    async def update_draft(
        self,
        revision_id: UUID,
        request: SellingProfileDraftUpdate,
    ) -> SellingProfileManagementResponse:
        await self._require_admin()
        revision = await self.repository.revision(
            self.tenant.organisation_id,
            revision_id,
            for_update=True,
        )
        if revision is None:
            raise PublicAPIError("selling_profile_revision_not_found", "The profile revision was not found.", 404)
        if revision.state != "draft":
            raise PublicAPIError(
                "selling_profile_revision_immutable",
                "Approved and historical profile revisions cannot be edited.",
                409,
            )
        if revision.lock_version != request.expected_lock_version:
            raise PublicAPIError(
                "stale_selling_profile_revision",
                "This draft changed after it was loaded. Refresh and try again.",
                409,
            )
        revision.content_json = self._json(request.content)
        revision.content_fingerprint = self._fingerprint(request.content)
        revision.lock_version += 1
        revision.updated_at = datetime.now(UTC)
        self._event(
            "selling_profile_draft_updated",
            revision.id,
            {"revision_number": revision.revision_number, "offering_count": len(request.content.offerings)},
        )
        await self._commit("The Company & Selling Profile draft could not be saved.")
        self._log("selling_profile_draft_updated", revision)
        return await self._management()

    async def approve(
        self,
        revision_id: UUID,
        request: SellingProfileApproveRequest,
    ) -> SellingProfileManagementResponse:
        await self._require_admin()
        revision = await self.repository.revision(
            self.tenant.organisation_id,
            revision_id,
            for_update=True,
        )
        if revision is None:
            raise PublicAPIError("selling_profile_revision_not_found", "The profile revision was not found.", 404)
        if revision.state == "approved":
            return await self._management()
        if revision.state != "draft":
            raise PublicAPIError(
                "selling_profile_revision_immutable",
                "Only the current draft can be approved.",
                409,
            )
        if revision.lock_version != request.expected_lock_version:
            raise PublicAPIError(
                "stale_selling_profile_revision",
                "This draft changed after it was loaded. Refresh and review it before approval.",
                409,
            )
        self._content(revision)
        now = datetime.now(UTC)
        previous = await self.repository.current(self.tenant.organisation_id, for_update=True)
        if previous is not None:
            previous.state = "superseded"
            previous.superseded_at = now
            previous.updated_at = now
            await self.session.flush()
        revision.state = "approved"
        revision.approved_by_user_id = self.tenant.user_id
        revision.approved_at = now
        revision.updated_at = now
        self._event(
            "selling_profile_revision_approved",
            revision.id,
            {
                "revision_number": revision.revision_number,
                "superseded_revision_id": str(previous.id) if previous is not None else None,
            },
        )
        await self._commit("The Company & Selling Profile revision could not be approved.")
        self._log("selling_profile_revision_approved", revision)
        return await self._management()

    async def retire(self, revision_id: UUID) -> SellingProfileManagementResponse:
        await self._require_admin()
        revision = await self.repository.revision(
            self.tenant.organisation_id,
            revision_id,
            for_update=True,
        )
        if revision is None:
            raise PublicAPIError("selling_profile_revision_not_found", "The profile revision was not found.", 404)
        if revision.state == "retired":
            return await self._management()
        if revision.state != "approved":
            raise PublicAPIError(
                "selling_profile_revision_not_current",
                "Only the current approved profile can be retired.",
                409,
            )
        now = datetime.now(UTC)
        revision.state = "retired"
        revision.retired_at = now
        revision.updated_at = now
        self._event(
            "selling_profile_revision_retired",
            revision.id,
            {"revision_number": revision.revision_number},
        )
        await self._commit("The Company & Selling Profile revision could not be retired.")
        self._log("selling_profile_revision_retired", revision)
        return await self._management()

    async def _management(self) -> SellingProfileManagementResponse:
        draft = await self.repository.draft(self.tenant.organisation_id)
        current = await self.repository.current(self.tenant.organisation_id)
        history = await self.repository.history(self.tenant.organisation_id)
        status = (
            "current" if current is not None else "draft" if draft is not None else "retired" if history else "empty"
        )
        return SellingProfileManagementResponse(
            status=cast(SellingProfileStatus, status),
            can_manage=self.tenant.can_manage(),
            draft=self._response(draft) if draft is not None else None,
            current=self._response(current) if current is not None else None,
            history=tuple(self._response(item) for item in history),
        )

    async def _require_membership(self) -> None:
        if not await self.repository.active_membership(self.tenant.organisation_id, self.tenant.user_id):
            raise PublicAPIError("forbidden", "You do not have permission to use this organisation profile.", 403)

    async def _require_admin(self) -> None:
        await self._require_membership()
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You do not have permission to manage this organisation profile.", 403)

    async def _commit(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failure", message, 500) from exc

    def _event(self, event_type: str, subject_id: UUID, metadata: dict[str, object]) -> None:
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=subject_id,
                metadata_json=metadata,
            )
        )

    @staticmethod
    def _json(content: SellingProfileContent) -> dict[str, object]:
        return content.model_dump(mode="json", by_alias=True)

    @classmethod
    def _fingerprint(cls, content: SellingProfileContent) -> str:
        encoded = json.dumps(cls._json(content), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _content(revision: SellingProfileRevision) -> SellingProfileContent:
        try:
            return SellingProfileContent.model_validate(revision.content_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "selling_profile_content_invalid",
                "The stored Company & Selling Profile revision is invalid.",
                500,
            ) from exc

    @classmethod
    def _response(cls, revision: SellingProfileRevision) -> SellingProfileRevisionResponse:
        return SellingProfileRevisionResponse(
            id=revision.id,
            profile_id=revision.profile_id,
            revision_number=revision.revision_number,
            state=cast(SellingProfileState, revision.state),
            lock_version=revision.lock_version,
            content=cls._content(revision),
            content_fingerprint=revision.content_fingerprint,
            created_by_user_id=revision.created_by_user_id,
            approved_by_user_id=revision.approved_by_user_id,
            created_at=cls._as_utc(revision.created_at),
            updated_at=cls._as_utc(revision.updated_at),
            approved_at=cls._as_utc(revision.approved_at),
            superseded_at=cls._as_utc(revision.superseded_at),
            retired_at=cls._as_utc(revision.retired_at),
        )

    @staticmethod
    @overload
    def _as_utc(value: datetime) -> datetime: ...

    @staticmethod
    @overload
    def _as_utc(value: None) -> None: ...

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _log(self, event: str, revision: SellingProfileRevision) -> None:
        logger.info(
            event,
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "state": revision.state,
            },
        )
