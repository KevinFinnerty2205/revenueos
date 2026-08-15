from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.companion_contracts import (
    InteractionMarkerCreateRequest,
    InteractionMarkerDeleteResponse,
    InteractionMarkerResponse,
)
from revenueos.companion_repositories import CompanionRepository
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import InteractionMarker
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.companion")


class CompanionService:
    """Tenant-safe passive Companion metadata; markers are not Evidence."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.repository = CompanionRepository(session)
        self.beta = BetaService(session, tenant, settings)

    @staticmethod
    def _idempotent_marker_response(
        existing: InteractionMarker,
        request: InteractionMarkerCreateRequest,
    ) -> InteractionMarkerResponse:
        if existing.marker_type != request.marker_type or existing.recording_offset_ms != request.recording_offset_ms:
            raise PublicAPIError(
                "idempotency_conflict",
                "That request key was already used for a different marker.",
                409,
            )
        if existing.deleted_at is not None:
            raise PublicAPIError("marker_deleted", "That marker is no longer available.", 410)
        return InteractionMarkerResponse.model_validate(existing)

    async def create_marker(
        self,
        interaction_id: UUID,
        request: InteractionMarkerCreateRequest,
    ) -> InteractionMarkerResponse:
        self.beta.require_feature("aiCompanion")
        existing = await self.repository.find_idempotent_marker(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            return self._idempotent_marker_response(existing, request)

        interaction = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        existing = await self.repository.find_idempotent_marker(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            return self._idempotent_marker_response(existing, request)
        if interaction.lifecycle_status != "in_progress":
            raise PublicAPIError(
                "interaction_not_in_progress",
                "Markers can be added only while the interaction is in progress.",
                409,
            )
        marker = InteractionMarker(
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            created_by_user_id=self.tenant.user_id,
            marker_type=request.marker_type,
            recording_offset_ms=request.recording_offset_ms,
            idempotency_key=request.idempotency_key,
        )
        self.session.add(marker)
        try:
            await self.session.flush()
            await self.session.refresh(marker)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("marker_conflict", "The marker could not be saved safely.", 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("marker_save_failed", "The marker could not be saved.", 500) from exc
        logger.info(
            "marker_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "marker_id": str(marker.id),
                "has_recording_offset": marker.recording_offset_ms is not None,
            },
        )
        return InteractionMarkerResponse.model_validate(marker)

    async def list_markers(self, interaction_id: UUID) -> list[InteractionMarkerResponse]:
        self.beta.require_feature("aiCompanion")
        if await self.repository.get_interaction(self.tenant.organisation_id, interaction_id) is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        return [
            InteractionMarkerResponse.model_validate(item)
            for item in await self.repository.list_markers(self.tenant.organisation_id, interaction_id)
        ]

    async def delete_marker(
        self,
        interaction_id: UUID,
        marker_id: UUID,
    ) -> InteractionMarkerDeleteResponse:
        self.beta.require_feature("aiCompanion")
        interaction = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        if interaction.lifecycle_status != "in_progress":
            raise PublicAPIError(
                "marker_immutable",
                "Markers cannot be changed after the interaction ends.",
                409,
            )
        marker = await self.repository.get_marker(
            self.tenant.organisation_id,
            interaction_id,
            marker_id,
            for_update=True,
        )
        if marker is None:
            raise PublicAPIError("marker_not_found", "The requested marker was not found.", 404)
        marker.deleted_at = datetime.now(UTC)
        try:
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("marker_delete_failed", "The marker could not be deleted.", 500) from exc
        logger.info(
            "marker_deleted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "marker_id": str(marker_id),
            },
        )
        return InteractionMarkerDeleteResponse(id=marker_id)
