from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, NoReturn, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.credential_store import EncryptedDatabaseCredentialStore
from revenueos.crm_provider import (
    CRMObjectType,
    CRMProviderAdapter,
    CRMProviderError,
    CRMProviderOwner,
    CRMProviderRecord,
    CRMScalar,
    rules_for,
)
from revenueos.errors import PublicAPIError
from revenueos.integration_contracts import (
    CRMConflictListResponse,
    CRMConflictResolutionRequest,
    CRMConflictResponse,
    CRMConnectionStatusResponse,
    CRMConnectorSettingRequest,
    CRMMappingReviewRequest,
    CRMOwnerMappingListResponse,
    CRMOwnerMappingRequest,
    CRMOwnerMappingResponse,
    CRMSyncCursorResponse,
    CRMSyncEnqueueRequest,
    CRMSyncJobResponse,
    CRMWritebackConfirmRequest,
    CRMWritebackPreviewRequest,
    CRMWritebackPreviewResponse,
    CRMWritebackResultResponse,
    CRMWritebackSettingRequest,
)
from revenueos.integration_executors import ExecutorConnectionContext
from revenueos.models import (
    Company,
    Contact,
    CRMConflict,
    CRMConnectionState,
    CRMEntityMapping,
    CRMFieldMapping,
    CRMOwnerMapping,
    CRMRecordChange,
    CRMStageMapping,
    CRMSyncCursor,
    CRMSyncJob,
    CRMSyncReceipt,
    CRMWritebackPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Opportunity,
    OpportunityStageEvent,
    OrganisationMembership,
)
from revenueos.pipeline_repositories import ensure_default_pipeline, initial_stage_for
from revenueos.prospect_url_security import PublicUrlSafetyError, normalise_company_website
from revenueos.tenant import TenantContext

_OBJECT_ORDER: tuple[CRMObjectType, ...] = ("account", "contact", "opportunity")
_GENERIC_EMAIL_LOCALS = frozenset({"admin", "contact", "hello", "info", "sales", "support"})


class CRMConnectorService:
    """Tenant-scoped lifecycle, reconciliation and reviewed writeback policy."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        adapters: Mapping[str, CRMProviderAdapter] | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.adapters = dict(adapters) if adapters is not None else self._configured_adapters()

    async def status(self, connection_id: UUID) -> CRMConnectionStatusResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id, require_active=False)
        state = await self._state(connection.id)
        cursors = list(
            (
                await self.session.scalars(
                    select(CRMSyncCursor)
                    .where(
                        CRMSyncCursor.organisation_id == self.tenant.organisation_id,
                        CRMSyncCursor.connection_id == connection.id,
                    )
                    .order_by(CRMSyncCursor.object_type)
                )
            ).all()
        )
        latest = await self.session.scalar(
            select(CRMSyncJob)
            .where(
                CRMSyncJob.organisation_id == self.tenant.organisation_id,
                CRMSyncJob.connection_id == connection.id,
            )
            .order_by(CRMSyncJob.created_at.desc(), CRMSyncJob.id.desc())
            .limit(1)
        )
        state.conflict_count = await self._open_conflict_count(connection.id)
        return self._status_response(state, cursors, latest)

    async def enqueue_sync(
        self,
        connection_id: UUID,
        request: CRMSyncEnqueueRequest,
    ) -> CRMSyncJobResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id, for_update=True)
        if not state.connector_enabled:
            raise PublicAPIError("crm_connector_disabled", "Enable the CRM connector before starting sync.", 409)
        key = hashlib.sha256(
            f"{self.tenant.organisation_id}:{connection.id}:{request.idempotency_key}".encode()
        ).hexdigest()
        existing = await self.session.scalar(
            select(CRMSyncJob).where(
                CRMSyncJob.organisation_id == self.tenant.organisation_id,
                CRMSyncJob.connection_id == connection.id,
                CRMSyncJob.idempotency_key == key,
            )
        )
        if existing is not None:
            return self._job_response(existing)
        active = await self.session.scalar(
            select(CRMSyncJob).where(
                CRMSyncJob.organisation_id == self.tenant.organisation_id,
                CRMSyncJob.connection_id == connection.id,
                CRMSyncJob.status.in_(("queued", "running", "paused")),
            )
        )
        if active is not None:
            raise PublicAPIError("crm_sync_already_active", "A CRM sync is already active.", 409)
        now = datetime.now(UTC)
        job = CRMSyncJob(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            provider_key=connection.connector_key,
            mode=request.mode,
            status="queued",
            idempotency_key=key,
            requested_by_user_id=self.tenant.user_id,
            attempt_count=0,
            worker_id=None,
            lease_expires_at=None,
            started_at=None,
            completed_at=None,
            safe_failure_code=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(job)
        strategy = "incremental" if request.mode == "incremental" else "full"
        cursors = (
            await self.session.scalars(
                select(CRMSyncCursor).where(
                    CRMSyncCursor.organisation_id == self.tenant.organisation_id,
                    CRMSyncCursor.connection_id == connection.id,
                )
            )
        ).all()
        for cursor in cursors:
            cursor.strategy = strategy
            cursor.cursor_token = None
            cursor.page_count = 0
            cursor.record_count = 0
            cursor.completed_at = None
            if strategy == "full":
                cursor.high_watermark_at = None
        if state.initial_sync_completed_at is None:
            state.lifecycle = "initial_sync"
        self._audit(connection, "crm_sync_queued", job.id, "sync_job", now)
        await self._commit("The CRM sync could not be queued.")
        return self._job_response(job)

    async def review_mappings(
        self,
        connection_id: UUID,
        request: CRMMappingReviewRequest,
    ) -> CRMConnectionStatusResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id, for_update=True)
        if state.initial_sync_completed_at is None:
            raise PublicAPIError(
                "crm_initial_sync_incomplete",
                "Finish the initial read-only CRM sync before approving mappings.",
                409,
            )
        if state.mapping_version != request.mapping_version:
            raise PublicAPIError("crm_mapping_stale", "CRM mappings changed; review the latest version.", 409)
        unmapped = await self.session.scalar(
            select(CRMOwnerMapping.id).where(
                CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                CRMOwnerMapping.connection_id == connection.id,
                CRMOwnerMapping.state == "unmapped",
            )
        )
        if unmapped is not None:
            raise PublicAPIError("crm_owner_mapping_required", "Map each active CRM owner before approval.", 409)
        field_entities = set(
            (
                await self.session.scalars(
                    select(CRMFieldMapping.entity_type).where(
                        CRMFieldMapping.organisation_id == self.tenant.organisation_id,
                        CRMFieldMapping.connection_id == connection.id,
                        CRMFieldMapping.enabled.is_(True),
                    )
                )
            ).all()
        )
        if field_entities != {"company", "contact", "opportunity"}:
            raise PublicAPIError("crm_field_mapping_required", "Review mappings for all three CRM objects.", 409)
        if (
            await self.session.scalar(
                select(CRMStageMapping.id).where(
                    CRMStageMapping.organisation_id == self.tenant.organisation_id,
                    CRMStageMapping.connection_id == connection.id,
                )
            )
            is None
        ):
            raise PublicAPIError("crm_stage_mapping_required", "Map at least one opportunity stage.", 409)
        conflicts = await self._open_conflict_count(connection.id)
        state.conflict_count = conflicts
        state.lifecycle = "needs_attention" if conflicts else "ready"
        state.writeback_enabled = False
        state.configured_by_user_id = self.tenant.user_id
        now = datetime.now(UTC)
        self._audit(connection, "crm_mapping_reviewed", connection.id, "connection", now)
        await self._commit("The CRM mapping review could not be saved.")
        return await self.status(connection.id)

    async def set_writeback(
        self,
        connection_id: UUID,
        request: CRMWritebackSettingRequest,
    ) -> CRMConnectionStatusResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id, for_update=True)
        if state.mapping_version != request.mapping_version:
            raise PublicAPIError("crm_mapping_stale", "CRM mappings changed; review the latest version.", 409)
        if request.enabled:
            if state.lifecycle != "ready":
                raise PublicAPIError("crm_mapping_review_required", "Approve the current CRM mappings first.", 409)
            if await self._open_conflict_count(connection.id):
                raise PublicAPIError("crm_conflicts_open", "Resolve open CRM conflicts before enabling writeback.", 409)
        state.writeback_enabled = request.enabled
        state.configured_by_user_id = self.tenant.user_id
        now = datetime.now(UTC)
        self._audit(connection, "crm_writeback_changed", connection.id, "connection", now)
        await self._commit("CRM writeback could not be changed.")
        return await self.status(connection.id)

    async def set_connector_enabled(
        self,
        connection_id: UUID,
        request: CRMConnectorSettingRequest,
    ) -> CRMConnectionStatusResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id, for_update=True)
        state.connector_enabled = request.enabled
        state.writeback_enabled = False
        state.lifecycle = "mapping_required" if request.enabled else "disabled"
        state.configured_by_user_id = self.tenant.user_id
        now = datetime.now(UTC)
        if not request.enabled:
            jobs = (
                await self.session.scalars(
                    select(CRMSyncJob).where(
                        CRMSyncJob.organisation_id == self.tenant.organisation_id,
                        CRMSyncJob.connection_id == connection.id,
                        CRMSyncJob.status.in_(("queued", "running", "paused")),
                    )
                )
            ).all()
            for job in jobs:
                job.status = "cancelled"
                job.worker_id = None
                job.lease_expires_at = None
                job.completed_at = now
        self._audit(connection, "crm_connector_changed", connection.id, "connection", now)
        await self._commit("The CRM connector kill switch could not be changed.")
        return await self.status(connection.id)

    async def list_owners(self, connection_id: UUID) -> CRMOwnerMappingListResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id, require_active=False)
        rows = list(
            (
                await self.session.scalars(
                    select(CRMOwnerMapping)
                    .where(
                        CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                        CRMOwnerMapping.connection_id == connection.id,
                    )
                    .order_by(CRMOwnerMapping.external_owner_name, CRMOwnerMapping.external_owner_id)
                )
            ).all()
        )
        return CRMOwnerMappingListResponse(items=[self._owner_response(item) for item in rows], total=len(rows))

    async def set_owner_mapping(
        self,
        connection_id: UUID,
        request: CRMOwnerMappingRequest,
    ) -> CRMOwnerMappingResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        owner = await self.session.scalar(
            select(CRMOwnerMapping)
            .where(
                CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                CRMOwnerMapping.connection_id == connection.id,
                CRMOwnerMapping.external_owner_id == request.external_owner_id,
            )
            .with_for_update()
        )
        if owner is None:
            raise PublicAPIError("crm_owner_not_found", "Refresh CRM owners and try again.", 404)
        if request.user_id is not None:
            membership = await self.session.scalar(
                select(OrganisationMembership).where(
                    OrganisationMembership.organisation_id == self.tenant.organisation_id,
                    OrganisationMembership.user_id == request.user_id,
                    OrganisationMembership.status == "active",
                )
            )
            if membership is None:
                raise PublicAPIError("crm_owner_user_invalid", "Select an active organisation member.", 422)
        owner.user_id = request.user_id
        owner.state = "mapped" if request.user_id is not None else "unmapped"
        owner.configured_by_user_id = self.tenant.user_id
        state = await self._state(connection.id, for_update=True)
        state.mapping_version += 1
        state.lifecycle = "mapping_required"
        state.writeback_enabled = False
        await self._commit("The CRM owner mapping could not be saved.")
        return self._owner_response(owner)

    async def list_conflicts(self, connection_id: UUID) -> CRMConflictListResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id, require_active=False)
        rows = list(
            (
                await self.session.scalars(
                    select(CRMConflict)
                    .where(
                        CRMConflict.organisation_id == self.tenant.organisation_id,
                        CRMConflict.connection_id == connection.id,
                    )
                    .order_by(CRMConflict.status, CRMConflict.created_at.desc())
                    .limit(200)
                )
            ).all()
        )
        return CRMConflictListResponse(items=[self._conflict_response(item) for item in rows], total=len(rows))

    async def resolve_conflict(
        self,
        conflict_id: UUID,
        request: CRMConflictResolutionRequest,
    ) -> CRMConflictResponse:
        self._require_admin()
        await self._require_entitlement()
        conflict = await self.session.scalar(
            select(CRMConflict)
            .where(
                CRMConflict.organisation_id == self.tenant.organisation_id,
                CRMConflict.id == conflict_id,
            )
            .with_for_update()
        )
        if conflict is None:
            raise PublicAPIError("crm_conflict_not_found", "The CRM conflict was not found.", 404)
        if conflict.status != "open":
            return self._conflict_response(conflict)
        connection = await self._connection(conflict.connection_id)
        if request.resolution == "provider":
            if conflict.revenueos_entity_id is None:
                raise PublicAPIError(
                    "crm_conflict_requires_mapping",
                    "Complete the owner, company or stage mapping before importing this record.",
                    409,
                )
            await self._apply_single_local_value(conflict, conflict.provider_value_json, connection.created_by_user_id)
        elif request.resolution in {"oryntela", "manual"}:
            state = await self._state(connection.id)
            if not state.writeback_enabled:
                raise PublicAPIError(
                    "crm_writeback_disabled",
                    "Enable reviewed CRM writeback before choosing the Oryntela value.",
                    409,
                )
            raise PublicAPIError(
                "crm_conflict_preview_required",
                "Create and confirm a writeback preview for this record before resolving it externally.",
                409,
            )
        conflict.status = "resolved"
        conflict.resolution = request.resolution
        conflict.resolved_by_user_id = self.tenant.user_id
        resolved_at = datetime.now(UTC)
        conflict.resolved_at = resolved_at
        conflict.updated_at = resolved_at
        state = await self._state(connection.id, for_update=True)
        await self.session.flush()
        state.conflict_count = await self._open_conflict_count(connection.id)
        self._audit(connection, "crm_conflict_resolved", conflict.id, "crm_conflict", resolved_at)
        await self._commit("The CRM conflict could not be resolved.")
        return self._conflict_response(conflict)

    async def preview_writeback(
        self,
        connection_id: UUID,
        request: CRMWritebackPreviewRequest,
    ) -> CRMWritebackPreviewResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id)
        if not state.connector_enabled or not state.writeback_enabled or state.lifecycle != "ready":
            raise PublicAPIError(
                "crm_writeback_disabled",
                "Approve mappings and enable CRM writeback before creating a preview.",
                409,
            )
        entity = await self._canonical_entity(request.entity_type, request.entity_id)
        mapping = await self._mapping_for_entity(connection.id, request.entity_type, request.entity_id)
        changes = await self._outbound_changes(connection, state, request.entity_type, entity)
        if not changes:
            raise PublicAPIError("crm_no_writeback_changes", "There are no governed CRM changes to review.", 409)
        external_version: str | None = None
        operation: Literal["create", "update"] = "create" if mapping is None else "update"
        if mapping is not None:
            try:
                external = await self._adapter(connection).get_record(
                    self._context(connection),
                    self._object_type(request.entity_type),
                    mapping.external_object_id,
                )
            except CRMProviderError as exc:
                self._raise_provider_error(connection.connector_key, exc)
            external_version = external.external_version
            changes = {
                key: value
                for key, value in changes.items()
                if self._json_value(external.fields.get(key)) != self._json_value(value)
            }
            if not changes:
                raise PublicAPIError("crm_no_writeback_changes", "The CRM already contains these values.", 409)
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=10)
        serialised_changes = {key: self._json_value(value) for key, value in sorted(changes.items())}
        fingerprint = self._fingerprint(
            {
                "connectionId": str(connection.id),
                "entityType": request.entity_type,
                "entityId": str(request.entity_id),
                "operation": operation,
                "externalObjectId": mapping.external_object_id if mapping else None,
                "externalVersion": external_version,
                "mappingVersion": state.mapping_version,
                "changes": serialised_changes,
            }
        )
        preview = CRMWritebackPreview(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            operation=operation,
            external_object_id=mapping.external_object_id if mapping else None,
            external_version=external_version,
            changes_json=serialised_changes,
            preview_fingerprint=fingerprint,
            mapping_version=state.mapping_version,
            expires_at=expires_at,
            confirmed_by_user_id=None,
            confirmed_at=None,
            receipt_id=None,
            invalidated_at=None,
            created_at=now,
        )
        self.session.add(preview)
        await self._commit("The CRM writeback preview could not be created.")
        return self._preview_response(preview)

    async def confirm_writeback(
        self,
        connection_id: UUID,
        request: CRMWritebackConfirmRequest,
    ) -> CRMWritebackResultResponse:
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id, for_update=True)
        if not state.connector_enabled or not state.writeback_enabled or state.lifecycle != "ready":
            raise PublicAPIError("crm_writeback_disabled", "CRM writeback is not enabled.", 409)
        preview = await self.session.scalar(
            select(CRMWritebackPreview)
            .where(
                CRMWritebackPreview.organisation_id == self.tenant.organisation_id,
                CRMWritebackPreview.connection_id == connection.id,
                CRMWritebackPreview.id == request.preview_id,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if preview is None:
            raise PublicAPIError("crm_preview_not_found", "The CRM writeback preview was not found.", 404)
        if preview.confirmed_at is not None:
            if preview.receipt_id is None:
                raise PublicAPIError("crm_writeback_state_invalid", "The confirmed writeback is unavailable.", 409)
            receipt = await self.session.scalar(
                select(CRMSyncReceipt).where(
                    CRMSyncReceipt.organisation_id == self.tenant.organisation_id,
                    CRMSyncReceipt.connection_id == connection.id,
                    CRMSyncReceipt.id == preview.receipt_id,
                )
            )
            if receipt is None:
                raise PublicAPIError("crm_writeback_state_invalid", "The confirmed writeback is unavailable.", 409)
            return self._writeback_result(receipt)
        if preview.invalidated_at is not None or self._aware(preview.expires_at) <= now:
            raise PublicAPIError("crm_preview_expired", "The CRM writeback preview has expired.", 409)
        if preview.preview_fingerprint != request.preview_fingerprint:
            raise PublicAPIError("crm_preview_changed", "The CRM writeback preview does not match.", 409)
        if preview.mapping_version != state.mapping_version:
            preview.invalidated_at = now
            await self._commit("The stale CRM preview could not be invalidated.")
            raise PublicAPIError("crm_mapping_stale", "CRM mappings changed; create a new preview.", 409)
        receipt_key = hashlib.sha256(
            f"{self.tenant.organisation_id}:{connection.id}:{request.idempotency_key}".encode()
        ).hexdigest()
        existing = await self.session.scalar(
            select(CRMSyncReceipt).where(
                CRMSyncReceipt.organisation_id == self.tenant.organisation_id,
                CRMSyncReceipt.connection_id == connection.id,
                CRMSyncReceipt.idempotency_key == receipt_key,
            )
        )
        if existing is not None:
            return self._writeback_result(existing)
        adapter = self._adapter(connection)
        object_type = self._object_type(preview.entity_type)
        mapping = await self._mapping_for_entity(connection.id, preview.entity_type, preview.entity_id)
        fields = cast(dict[str, CRMScalar], dict(preview.changes_json))
        try:
            if preview.operation == "create":
                if mapping is not None:
                    external = await adapter.get_record(
                        self._context(connection), object_type, mapping.external_object_id
                    )
                    status: Literal["applied", "reconciled", "unknown"] = "reconciled"
                else:
                    external = await adapter.create_record(self._context(connection), object_type, fields)
                    status = "applied"
            else:
                if mapping is None or preview.external_object_id != mapping.external_object_id:
                    raise PublicAPIError("crm_mapping_stale", "The CRM record link changed; create a new preview.", 409)
                current = await adapter.get_record(self._context(connection), object_type, mapping.external_object_id)
                if current.external_version != preview.external_version:
                    raise PublicAPIError(
                        "crm_external_state_changed", "The CRM record changed; create a new preview.", 409
                    )
                external = await adapter.update_record(self._context(connection), current, fields)
                status = "applied"
        except CRMProviderError as exc:
            if not exc.uncertain:
                self._raise_provider_error(connection.connector_key, exc)
            receipt = self._receipt(
                connection,
                direction="outbound",
                object_type=object_type,
                operation=preview.operation,
                status="unknown",
                idempotency_key=receipt_key,
                entity_id=preview.entity_id,
                external_object_id=preview.external_object_id,
                external_version=preview.external_version,
                fields=tuple(fields),
                safe_failure_code="unknown_external_state",
                now=now,
            )
            self.session.add(receipt)
            preview.confirmed_by_user_id = self.tenant.user_id
            preview.confirmed_at = now
            preview.receipt_id = receipt.id
            await self._commit("The uncertain CRM writeback state could not be recorded.")
            return self._writeback_result(receipt)
        if mapping is None:
            mapping = CRMEntityMapping(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                revenueos_entity_type=preview.entity_type,
                revenueos_entity_id=preview.entity_id,
                external_object_type=self._external_object_type(connection.connector_key, object_type),
                external_object_id=external.external_object_id,
                external_updated_at=external.modified_at,
                last_synced_at=now,
                sync_state="active",
                created_by_user_id=self.tenant.user_id,
                external_version=external.external_version,
                authority_version=state.mapping_version,
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
            self.session.add(mapping)
        else:
            mapping.external_updated_at = external.modified_at
            mapping.external_version = external.external_version
            mapping.last_synced_at = now
            mapping.authority_version = state.mapping_version
        receipt = self._receipt(
            connection,
            direction="outbound",
            object_type=object_type,
            operation=preview.operation,
            status=status,
            idempotency_key=receipt_key,
            entity_id=preview.entity_id,
            external_object_id=external.external_object_id,
            external_version=external.external_version,
            fields=tuple(fields),
            safe_failure_code=None,
            now=now,
        )
        self.session.add(receipt)
        preview.confirmed_by_user_id = self.tenant.user_id
        preview.confirmed_at = now
        preview.receipt_id = receipt.id
        await self._commit("The reviewed CRM writeback could not be recorded.")
        return self._writeback_result(receipt)

    async def reconcile_writeback(
        self,
        connection_id: UUID,
        receipt_id: UUID,
    ) -> CRMWritebackResultResponse:
        """Resolve an uncertain write with a provider read; never repeat the mutation."""
        self._require_admin()
        await self._require_entitlement()
        connection = await self._connection(connection_id)
        state = await self._state(connection.id)
        if not state.connector_enabled:
            raise PublicAPIError("crm_connector_disabled", "Enable the CRM connector before reconciling.", 409)
        receipt = await self.session.scalar(
            select(CRMSyncReceipt).where(
                CRMSyncReceipt.organisation_id == self.tenant.organisation_id,
                CRMSyncReceipt.connection_id == connection.id,
                CRMSyncReceipt.id == receipt_id,
                CRMSyncReceipt.direction == "outbound",
            )
        )
        if receipt is None:
            raise PublicAPIError("crm_receipt_not_found", "The CRM writeback receipt was not found.", 404)
        if receipt.status != "unknown":
            if receipt.status in {"applied", "reconciled"}:
                return self._writeback_result(receipt)
            raise PublicAPIError(
                "crm_reconciliation_not_available",
                "Only an unknown CRM writeback outcome can be reconciled.",
                409,
            )
        reconciliation_key = hashlib.sha256(
            f"{self.tenant.organisation_id}:{connection.id}:{receipt.id}:reconcile".encode()
        ).hexdigest()
        existing = await self.session.scalar(
            select(CRMSyncReceipt).where(
                CRMSyncReceipt.organisation_id == self.tenant.organisation_id,
                CRMSyncReceipt.connection_id == connection.id,
                CRMSyncReceipt.idempotency_key == reconciliation_key,
            )
        )
        if existing is not None:
            return self._writeback_result(existing)
        preview = await self.session.scalar(
            select(CRMWritebackPreview).where(
                CRMWritebackPreview.organisation_id == self.tenant.organisation_id,
                CRMWritebackPreview.connection_id == connection.id,
                CRMWritebackPreview.receipt_id == receipt.id,
            )
        )
        if preview is None:
            raise PublicAPIError(
                "crm_reconciliation_state_invalid",
                "The exact reviewed CRM change is unavailable.",
                409,
            )
        mapping = await self._mapping_for_entity(connection.id, preview.entity_type, preview.entity_id)
        external_object_id = receipt.external_object_id
        if mapping is not None:
            if external_object_id is not None and mapping.external_object_id != external_object_id:
                raise PublicAPIError(
                    "crm_mapping_stale",
                    "The CRM record link changed; the unknown outcome cannot be reconciled automatically.",
                    409,
                )
            external_object_id = mapping.external_object_id
        if external_object_id is None:
            raise PublicAPIError(
                "crm_reconciliation_lookup_required",
                "Run an inbound sync and link the exact CRM record before reconciling this create outcome.",
                409,
            )
        object_type = self._object_type(preview.entity_type)
        try:
            external = await self._adapter(connection).get_record(
                self._context(connection), object_type, external_object_id
            )
        except CRMProviderError as exc:
            self._raise_provider_error(connection.connector_key, exc)
        expected = {key: self._json_value(value) for key, value in preview.changes_json.items()}
        if any(self._json_value(external.fields.get(key)) != value for key, value in expected.items()):
            raise PublicAPIError(
                "crm_writeback_still_unknown",
                "The CRM record does not match the reviewed change. No write was retried.",
                409,
            )
        now = datetime.now(UTC)
        reconciled = self._receipt(
            connection,
            direction="outbound",
            object_type=object_type,
            operation="reconcile",
            status="reconciled",
            idempotency_key=reconciliation_key,
            entity_id=preview.entity_id,
            external_object_id=external.external_object_id,
            external_version=external.external_version,
            fields=tuple(sorted(expected)),
            safe_failure_code=None,
            now=now,
        )
        self.session.add(reconciled)
        if mapping is not None:
            mapping.external_updated_at = external.modified_at
            mapping.external_version = external.external_version
            mapping.last_synced_at = now
            mapping.authority_version = state.mapping_version
        self._audit(connection, "crm_writeback_reconciled", receipt.id, "crm_sync_receipt", now)
        await self._commit("The CRM writeback reconciliation could not be recorded.")
        return self._writeback_result(reconciled)

    async def process_next_page(self, worker_id: str) -> bool:
        """Process one bounded provider page for this tenant and yield fairly."""
        job = await self.session.scalar(
            select(CRMSyncJob)
            .where(
                CRMSyncJob.organisation_id == self.tenant.organisation_id,
                CRMSyncJob.status.in_(("queued", "running")),
                (CRMSyncJob.lease_expires_at.is_(None) | (CRMSyncJob.lease_expires_at <= datetime.now(UTC))),
            )
            .order_by(CRMSyncJob.created_at, CRMSyncJob.id)
            .with_for_update()
            .limit(1)
        )
        if job is None:
            return False
        await self._require_entitlement()
        connection = await self._connection(job.connection_id)
        state = await self._state(connection.id, for_update=True)
        if not state.connector_enabled:
            job.status = "cancelled"
            job.completed_at = datetime.now(UTC)
            await self._commit("The disabled CRM sync could not be cancelled.")
            return True
        now = datetime.now(UTC)
        job.status = "running"
        job.worker_id = worker_id
        job.lease_expires_at = now + timedelta(seconds=self.settings.worker_lease_duration_seconds)
        job.started_at = job.started_at or now
        job.attempt_count += 1
        await self._commit("The CRM sync job could not be claimed.")
        try:
            await self._process_claimed_page(connection, state, job)
        except CRMProviderError as exc:
            await self._record_job_failure(connection, state, job, exc)
        return True

    async def _process_claimed_page(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        job: CRMSyncJob,
    ) -> None:
        object_type, cursor = await self._next_cursor(connection, job)
        if object_type is None or cursor is None:
            await self._finish_job(connection, state, job)
            return
        adapter = self._adapter(connection)
        if object_type == "account" and cursor.page_count == 0 and cursor.cursor_token is None:
            owners = await adapter.owners(self._context(connection))
            await self._upsert_owners(connection, owners)
        provider_cursor, observed_high_watermark = self._decode_page_checkpoint(cursor.cursor_token)
        modified_after = cursor.high_watermark_at if cursor.strategy == "incremental" else None
        page = await adapter.list_records(
            self._context(connection),
            object_type,
            cursor=provider_cursor,
            modified_after=modified_after,
            limit=self.settings.crm_sync_page_size,
        )
        applied = 0
        for record in page.records:
            if await self._apply_inbound_record(connection, state, record):
                applied += 1
        now = datetime.now(UTC)
        observed_high_watermark = max(
            value for value in (observed_high_watermark, page.high_watermark_at) if value is not None
        )
        cursor.cursor_token = (
            self._encode_page_checkpoint(page.next_cursor, observed_high_watermark)
            if page.next_cursor is not None
            else None
        )
        cursor.page_count += 1
        cursor.record_count += len(page.records)
        if page.next_cursor is None:
            cursor.high_watermark_at = observed_high_watermark
            cursor.completed_at = now
        state.records_seen += len(page.records)
        state.records_applied += applied
        state.health_status = "healthy"
        state.last_health_checked_at = now
        state.last_safe_error_code = None
        job.attempt_count = 0
        job.worker_id = None
        job.lease_expires_at = None
        if object_type == _OBJECT_ORDER[-1] and page.next_cursor is None:
            await self._finish_job(connection, state, job)
            return
        await self._commit("The CRM sync checkpoint could not be saved.")

    @staticmethod
    def _encode_page_checkpoint(provider_cursor: str, high_watermark_at: datetime) -> str:
        value = "checkpoint:" + json.dumps(
            {
                "providerCursor": provider_cursor,
                "highWatermarkAt": high_watermark_at.astimezone(UTC).isoformat(),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(value) > 2048:
            raise CRMProviderError("provider_cursor_invalid")
        return value

    @staticmethod
    def _decode_page_checkpoint(value: str | None) -> tuple[str | None, datetime | None]:
        if value is None or not value.startswith("checkpoint:"):
            return value, None
        try:
            payload = json.loads(value.removeprefix("checkpoint:"))
            provider_cursor = payload["providerCursor"]
            high_watermark_at = datetime.fromisoformat(payload["highWatermarkAt"])
            if (
                not isinstance(provider_cursor, str)
                or not provider_cursor
                or len(provider_cursor) > 1900
                or high_watermark_at.tzinfo is None
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CRMProviderError("provider_cursor_invalid") from exc
        return provider_cursor, high_watermark_at.astimezone(UTC)

    async def _next_cursor(
        self,
        connection: IntegrationConnection,
        job: CRMSyncJob,
    ) -> tuple[CRMObjectType | None, CRMSyncCursor | None]:
        existing = {
            cast(CRMObjectType, item.object_type): item
            for item in (
                await self.session.scalars(
                    select(CRMSyncCursor).where(
                        CRMSyncCursor.organisation_id == self.tenant.organisation_id,
                        CRMSyncCursor.connection_id == connection.id,
                    )
                )
            ).all()
        }
        for object_type in _OBJECT_ORDER:
            cursor = existing.get(object_type)
            if cursor is None:
                cursor = CRMSyncCursor(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    connection_id=connection.id,
                    provider_key=connection.connector_key,
                    object_type=object_type,
                    strategy="full" if job.mode in {"initial", "reconcile"} else "incremental",
                    cursor_token=None,
                    high_watermark_at=None,
                    page_count=0,
                    record_count=0,
                    completed_at=None,
                )
                self.session.add(cursor)
                return object_type, cursor
            if cursor.completed_at is None:
                return object_type, cursor
        return None, None

    async def _finish_job(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        job: CRMSyncJob,
    ) -> None:
        now = datetime.now(UTC)
        conflicts = await self._open_conflict_count(connection.id)
        job.status = "degraded" if conflicts else "succeeded"
        job.completed_at = now
        job.worker_id = None
        job.lease_expires_at = None
        state.conflict_count = conflicts
        state.last_successful_sync_at = now
        state.last_health_checked_at = now
        state.health_status = "degraded" if conflicts else "healthy"
        if job.mode == "initial":
            state.initial_sync_completed_at = now
        if conflicts:
            state.lifecycle = "needs_attention"
            state.writeback_enabled = False
        elif state.lifecycle == "initial_sync":
            state.lifecycle = "mapping_required"
        self._audit(connection, "crm_sync_completed", job.id, "sync_job", now)
        await self._commit("The completed CRM sync could not be recorded.")

    async def _record_job_failure(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        job: CRMSyncJob,
        error: CRMProviderError,
    ) -> None:
        now = datetime.now(UTC)
        state.last_health_checked_at = now
        state.last_safe_error_code = error.code
        job.safe_failure_code = error.code
        job.worker_id = None
        if error.code in {
            "connection_reauthorisation_required",
            "provider_identity_mismatch",
        }:
            connection.connection_status = "reauthorisation_required"
            state.health_status = "needs_reauth"
            state.lifecycle = "needs_attention"
            state.writeback_enabled = False
            job.status = "paused"
            job.lease_expires_at = None
            self._audit(
                connection,
                "connection_reauthorisation_required",
                connection.id,
                "connection",
                now,
            )
        elif error.code == "provider_rate_limited":
            state.health_status = "rate_limited"
            job.status = "queued"
            job.lease_expires_at = now + timedelta(seconds=error.retry_after_seconds or 60)
        elif error.retryable and job.attempt_count < 3:
            state.health_status = "degraded"
            job.status = "queued"
            job.lease_expires_at = now + timedelta(seconds=min(300, 5 * 2**job.attempt_count))
        else:
            state.health_status = "degraded"
            state.lifecycle = "needs_attention"
            state.writeback_enabled = False
            job.status = "failed"
            job.completed_at = now
            job.lease_expires_at = None
        await self._commit("The CRM sync failure could not be recorded.")

    async def _upsert_owners(
        self,
        connection: IntegrationConnection,
        owners: tuple[CRMProviderOwner, ...],
    ) -> None:
        now = datetime.now(UTC)
        existing = {
            item.external_owner_id: item
            for item in (
                await self.session.scalars(
                    select(CRMOwnerMapping).where(
                        CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                        CRMOwnerMapping.connection_id == connection.id,
                    )
                )
            ).all()
        }
        for owner in owners:
            row = existing.get(owner.external_owner_id)
            if row is None:
                self.session.add(
                    CRMOwnerMapping(
                        id=uuid.uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        connection_id=connection.id,
                        provider_key=connection.connector_key,
                        external_owner_id=owner.external_owner_id,
                        external_owner_name=owner.display_name,
                        external_owner_email=owner.email,
                        user_id=None,
                        state="unmapped" if owner.active else "inactive",
                        configured_by_user_id=self.tenant.user_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                continue
            row.external_owner_name = owner.display_name
            row.external_owner_email = owner.email
            if not owner.active:
                row.user_id = None
                row.state = "inactive"

    async def _apply_inbound_record(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        record: CRMProviderRecord,
    ) -> bool:
        now = datetime.now(UTC)
        receipt_key = self._fingerprint(
            {
                "direction": "inbound",
                "connectionId": str(connection.id),
                "objectType": record.object_type,
                "externalObjectId": record.external_object_id,
                "externalVersion": record.external_version,
            }
        )
        if (
            await self.session.scalar(
                select(CRMSyncReceipt.id).where(
                    CRMSyncReceipt.organisation_id == self.tenant.organisation_id,
                    CRMSyncReceipt.connection_id == connection.id,
                    CRMSyncReceipt.idempotency_key == receipt_key,
                )
            )
            is not None
        ):
            return False
        mapping = await self._mapping_by_external(connection, record)
        created_entity = False
        if record.archived:
            if mapping is not None:
                mapping.sync_state = "external_missing"
                mapping.archived_at = now
                mapping.external_version = record.external_version
                mapping.external_updated_at = record.modified_at
            await self._create_conflict(
                connection,
                record,
                mapping.revenueos_entity_id if mapping else None,
                "external_deleted",
                "active" if mapping else None,
                "deleted",
            )
            self.session.add(
                self._receipt(
                    connection,
                    direction="inbound",
                    object_type=record.object_type,
                    operation="archive",
                    status="conflict",
                    idempotency_key=receipt_key,
                    entity_id=mapping.revenueos_entity_id if mapping else None,
                    external_object_id=record.external_object_id,
                    external_version=record.external_version,
                    fields=("external_deleted",),
                    safe_failure_code=None,
                    now=now,
                )
            )
            return False
        entity = await self._entity_for_mapping(mapping)
        if mapping is None:
            entity = await self._strong_match(record)
            if entity is not None:
                mapping = self._new_mapping(connection, state, record, entity.id, now)
                self.session.add(mapping)
        if mapping is not None and entity is None:
            await self._create_conflict(
                connection,
                record,
                mapping.revenueos_entity_id,
                "local_record_missing",
                None,
                record.external_object_id,
            )
            status: Literal["applied", "skipped", "conflict"] = "conflict"
            changed: tuple[str, ...] = ()
        elif entity is None:
            entity = await self._create_canonical_entity(connection, state, record)
            if entity is None:
                status = "conflict"
                changed = ()
            else:
                mapping = self._new_mapping(connection, state, record, entity.id, now)
                self.session.add(mapping)
                created_entity = True
                status = "applied"
                changed = tuple(record.fields)
        else:
            changed_fields, conflicts = await self._apply_provider_fields(connection, state, record, entity)
            status = "conflict" if conflicts else "applied" if changed_fields else "skipped"
            changed = tuple(changed_fields)
        if mapping is not None:
            mapping.external_updated_at = record.modified_at
            mapping.external_version = record.external_version
            mapping.last_synced_at = now
            mapping.sync_state = "active"
            mapping.archived_at = None
            mapping.authority_version = state.mapping_version
        self.session.add(
            self._receipt(
                connection,
                direction="inbound",
                object_type=record.object_type,
                operation="create" if created_entity else "update",
                status=status,
                idempotency_key=receipt_key,
                entity_id=entity.id if entity is not None else None,
                external_object_id=record.external_object_id,
                external_version=record.external_version,
                fields=changed,
                safe_failure_code=None,
                now=now,
            )
        )
        return status == "applied"

    async def _mapping_by_external(
        self,
        connection: IntegrationConnection,
        record: CRMProviderRecord,
    ) -> CRMEntityMapping | None:
        result = await self.session.scalar(
            select(CRMEntityMapping).where(
                CRMEntityMapping.organisation_id == self.tenant.organisation_id,
                CRMEntityMapping.connection_id == connection.id,
                CRMEntityMapping.external_object_type
                == self._external_object_type(connection.connector_key, record.object_type),
                CRMEntityMapping.external_object_id == record.external_object_id,
            )
        )
        return result

    async def _mapping_for_entity(
        self,
        connection_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> CRMEntityMapping | None:
        result = await self.session.scalar(
            select(CRMEntityMapping).where(
                CRMEntityMapping.organisation_id == self.tenant.organisation_id,
                CRMEntityMapping.connection_id == connection_id,
                CRMEntityMapping.revenueos_entity_type == entity_type,
                CRMEntityMapping.revenueos_entity_id == entity_id,
                CRMEntityMapping.sync_state == "active",
            )
        )
        return result

    async def _entity_for_mapping(
        self,
        mapping: CRMEntityMapping | None,
    ) -> Company | Contact | Opportunity | None:
        if mapping is None:
            return None
        return await self._canonical_entity(mapping.revenueos_entity_type, mapping.revenueos_entity_id)

    async def _canonical_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> Company | Contact | Opportunity:
        if entity_type == "company":
            company = await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == self.tenant.organisation_id,
                    Company.id == entity_id,
                )
            )
            entity: Company | Contact | Opportunity | None = company
        elif entity_type == "contact":
            contact = await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == self.tenant.organisation_id,
                    Contact.id == entity_id,
                )
            )
            entity = contact
        elif entity_type == "opportunity":
            opportunity = await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == entity_id,
                )
            )
            entity = opportunity
        else:
            raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)
        if entity is None:
            raise PublicAPIError("crm_entity_not_found", "The Oryntela record was not found.", 404)
        return entity

    async def _apply_provider_fields(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        record: CRMProviderRecord,
        entity: Company | Contact | Opportunity,
    ) -> tuple[list[str], bool]:
        entity_type = self._entity_type(record.object_type)
        rows = list(
            (
                await self.session.scalars(
                    select(CRMFieldMapping).where(
                        CRMFieldMapping.organisation_id == self.tenant.organisation_id,
                        CRMFieldMapping.connection_id == connection.id,
                        CRMFieldMapping.entity_type == entity_type,
                        CRMFieldMapping.enabled.is_(True),
                    )
                )
            ).all()
        )
        configured = {row.revenueos_field: row for row in rows}
        mapping = await self._mapping_for_entity(connection.id, entity_type, entity.id)
        changed: list[str] = []
        conflict_found = False
        for rule in rules_for(connection.connector_key, record.object_type):
            field = rule.canonical_field
            field_mapping = configured.get(field)
            if field_mapping is None or field not in record.fields:
                continue
            provider_value = await self._inbound_value(connection, record, field)
            local_value = await self._local_value(connection, entity, field)
            unresolved_reference = (
                (field == "owner" and record.owner_external_id is not None and provider_value is None)
                or (field == "account" and record.related_account_external_id is not None and provider_value is None)
                or (field == "stage" and record.fields.get("stage") is not None and provider_value is None)
            )
            if unresolved_reference:
                await self._create_conflict(
                    connection,
                    record,
                    entity.id,
                    field,
                    local_value,
                    (
                        record.owner_external_id
                        if field == "owner"
                        else record.related_account_external_id
                        if field == "account"
                        else record.fields.get("stage")
                    ),
                )
                conflict_found = True
                continue
            if self._json_value(local_value) == self._json_value(provider_value):
                continue
            local_changed = (
                mapping is not None
                and mapping.last_synced_at is not None
                and self._aware(entity.updated_at) > self._aware(mapping.last_synced_at)
            )
            requires_review = field_mapping.authority != "crm_authoritative" or local_changed
            if requires_review:
                await self._create_conflict(
                    connection,
                    record,
                    entity.id,
                    field,
                    local_value,
                    provider_value,
                )
                conflict_found = True
                continue
            if await self._set_local_value(connection, entity, field, provider_value, record.modified_at):
                self.session.add(
                    self._change(
                        record.object_type,
                        entity.id,
                        field,
                        local_value,
                        provider_value,
                        connection.created_by_user_id,
                    )
                )
                changed.append(field)
        if changed:
            entity.updated_at = datetime.now(UTC)
        return changed, conflict_found

    async def _apply_single_local_value(
        self,
        conflict: CRMConflict,
        value: object | None,
        actor_user_id: UUID,
    ) -> None:
        if conflict.revenueos_entity_id is None:
            raise PublicAPIError("crm_entity_not_found", "The Oryntela record was not found.", 404)
        connection = await self._connection(conflict.connection_id)
        entity_type = self._entity_type(cast(CRMObjectType, conflict.object_type))
        entity = await self._canonical_entity(entity_type, conflict.revenueos_entity_id)
        old_value = await self._local_value(connection, entity, conflict.field_key)
        if not await self._set_local_value(
            connection,
            entity,
            conflict.field_key,
            value,
            datetime.now(UTC),
        ):
            raise PublicAPIError(
                "crm_conflict_value_invalid",
                "The provider value cannot be applied to this Oryntela field.",
                422,
            )
        self.session.add(
            self._change(
                cast(CRMObjectType, conflict.object_type),
                entity.id,
                conflict.field_key,
                old_value,
                value,
                actor_user_id,
            )
        )

    async def _inbound_value(
        self,
        connection: IntegrationConnection,
        record: CRMProviderRecord,
        field: str,
    ) -> object | None:
        if field == "owner":
            return await self._owner_user_id(connection.id, record.owner_external_id)
        if field == "account":
            return await self._related_company_id(connection, record.related_account_external_id)
        if field == "stage":
            return await self._inbound_stage(connection.id, record.fields.get("stage"))
        return record.fields.get(field)

    async def _local_value(
        self,
        connection: IntegrationConnection,
        entity: Company | Contact | Opportunity,
        field: str,
    ) -> object | None:
        if field == "domain" and isinstance(entity, Company):
            return entity.normalized_domain
        if field == "owner":
            return entity.owner_user_id
        if field == "account" and isinstance(entity, (Contact, Opportunity)):
            return entity.company_id
        if field == "stage" and isinstance(entity, Opportunity):
            return entity.stage
        if field == "next_step":
            return None
        attribute = {
            "first_name": "first_name",
            "last_name": "last_name",
            "job_title": "job_title",
            "estimated_value": "estimated_value",
            "expected_close_date": "expected_close_date",
        }.get(field, field)
        return getattr(entity, attribute, None)

    async def _set_local_value(
        self,
        connection: IntegrationConnection,
        entity: Company | Contact | Opportunity,
        field: str,
        value: object | None,
        changed_at: datetime,
    ) -> bool:
        del connection
        if field == "owner":
            if not isinstance(value, UUID):
                return False
            entity.owner_user_id = value
            return True
        if field == "account" and isinstance(entity, (Contact, Opportunity)):
            if not isinstance(value, UUID) and value is not None:
                return False
            if isinstance(entity, Contact) and value is None:
                return False
            entity.company_id = value
            return True
        if field == "domain" and isinstance(entity, Company):
            parsed = self._domain(value)
            if value is not None and parsed is None:
                return False
            entity.website = parsed[0] if parsed is not None else None
            entity.normalized_domain = parsed[1] if parsed is not None else None
            return True
        if field == "stage" and isinstance(entity, Opportunity):
            if not isinstance(value, str):
                return False
            pipeline, stages = await ensure_default_pipeline(self.session, self.tenant.organisation_id)
            status = "won" if value == "closed_won" else "lost" if value == "closed_lost" else "open"
            target = initial_stage_for(stages, value, status)
            previous = next((item for item in stages if item.id == entity.pipeline_stage_id), None)
            previous_entered_at = entity.stage_entered_at
            entity.stage = value
            entity.status = status
            entity.pipeline_id = pipeline.id
            entity.pipeline_stage_id = target.id
            entity.stage_entered_at = changed_at
            entity.stage_tracking_started_at = entity.stage_tracking_started_at or changed_at
            if previous is None or previous.id != target.id:
                self.session.add(
                    OpportunityStageEvent(
                        id=uuid.uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        opportunity_id=entity.id,
                        from_pipeline_id=entity.pipeline_id if previous is not None else None,
                        to_pipeline_id=pipeline.id,
                        from_stage_id=previous.id if previous is not None else None,
                        to_stage_id=target.id,
                        from_stage_name=previous.name if previous is not None else None,
                        to_stage_name=target.name,
                        from_stage_type=previous.stage_type if previous is not None else None,
                        to_stage_type=target.stage_type,
                        changed_by_user_id=self.tenant.user_id,
                        changed_at=changed_at,
                        source="external_crm",
                        is_baseline=False,
                        previous_stage_entered_at=previous_entered_at,
                        outcome_reason=None,
                        outcome_note=None,
                        outcome_provenance=None,
                        actual_close_date=None,
                        final_amount=None,
                        final_currency=None,
                        idempotency_key=None,
                    )
                )
            return True
        if field == "estimated_value" and isinstance(entity, Opportunity):
            number, currency = self._money(value, entity.currency)
            entity.estimated_value = number
            entity.currency = currency
            return True
        if field == "currency" and isinstance(entity, Opportunity):
            currency = self._text(value, 3)
            if currency is None and entity.estimated_value is not None:
                return False
            entity.currency = currency.upper() if currency is not None else None
            return True
        if field == "expected_close_date" and isinstance(entity, Opportunity):
            entity.expected_close_date = self._date(value)
            return True
        limits = {
            "name": 200,
            "industry": 120,
            "first_name": 100,
            "last_name": 100,
            "email": 320,
            "phone": 50,
            "job_title": 150,
            "description": 2000,
        }
        if field not in limits or field == "next_step":
            return False
        if field == "name" and not isinstance(entity, (Company, Opportunity)):
            return False
        if field in {"first_name", "last_name", "email", "phone", "job_title"} and not isinstance(entity, Contact):
            return False
        if field == "industry" and not isinstance(entity, Company):
            return False
        if field == "description" and not isinstance(entity, Opportunity):
            return False
        text_value = self._text(value, limits[field])
        if field in {"name", "first_name", "last_name"} and text_value is None:
            return False
        setattr(entity, field, text_value)
        return True

    async def _outbound_changes(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        entity_type: str,
        entity: Company | Contact | Opportunity,
    ) -> dict[str, CRMScalar]:
        rows = list(
            (
                await self.session.scalars(
                    select(CRMFieldMapping).where(
                        CRMFieldMapping.organisation_id == self.tenant.organisation_id,
                        CRMFieldMapping.connection_id == connection.id,
                        CRMFieldMapping.entity_type == entity_type,
                        CRMFieldMapping.enabled.is_(True),
                        CRMFieldMapping.mapping_version <= state.mapping_version,
                        CRMFieldMapping.authority.in_(("revenueos_authoritative", "review_before_sync")),
                    )
                )
            ).all()
        )
        changes: dict[str, CRMScalar] = {}
        for row in rows:
            field = row.revenueos_field
            value: CRMScalar
            if field == "domain" and isinstance(entity, Company):
                value = entity.website
            elif field == "owner":
                owner = await self.session.scalar(
                    select(CRMOwnerMapping).where(
                        CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                        CRMOwnerMapping.connection_id == connection.id,
                        CRMOwnerMapping.user_id == entity.owner_user_id,
                        CRMOwnerMapping.state == "mapped",
                    )
                )
                if owner is None:
                    raise PublicAPIError(
                        "crm_owner_mapping_required",
                        "Map this record owner before creating a CRM writeback preview.",
                        409,
                    )
                value = owner.external_owner_id
            elif field == "account" and isinstance(entity, (Contact, Opportunity)):
                if entity.company_id is None:
                    value = None
                else:
                    account_mapping = await self._mapping_for_entity(connection.id, "company", entity.company_id)
                    if account_mapping is None:
                        raise PublicAPIError(
                            "crm_account_mapping_required",
                            "Link the related company before writing this record to the CRM.",
                            409,
                        )
                    value = account_mapping.external_object_id
            elif field == "stage" and isinstance(entity, Opportunity):
                stage = await self.session.scalar(
                    select(CRMStageMapping).where(
                        CRMStageMapping.organisation_id == self.tenant.organisation_id,
                        CRMStageMapping.connection_id == connection.id,
                        CRMStageMapping.revenueos_stage == entity.stage,
                    )
                )
                if stage is None:
                    raise PublicAPIError(
                        "crm_stage_mapping_required",
                        "Map this opportunity stage before creating a CRM writeback preview.",
                        409,
                    )
                value = stage.external_stage_id
            elif field == "next_step":
                continue
            else:
                raw = await self._local_value(connection, entity, field)
                if raw is not None and not isinstance(raw, (str, int, Decimal, date, datetime, bool)):
                    continue
                value = raw
            changes[field] = value
        return changes

    async def _owner_user_id(self, connection_id: UUID, external_owner_id: str | None) -> UUID | None:
        if external_owner_id is None:
            return None
        return await self.session.scalar(
            select(CRMOwnerMapping.user_id).where(
                CRMOwnerMapping.organisation_id == self.tenant.organisation_id,
                CRMOwnerMapping.connection_id == connection_id,
                CRMOwnerMapping.external_owner_id == external_owner_id,
                CRMOwnerMapping.state == "mapped",
            )
        )

    async def _related_company_id(
        self,
        connection: IntegrationConnection,
        external_account_id: str | None,
    ) -> UUID | None:
        if external_account_id is None:
            return None
        external_type = self._external_object_type(connection.connector_key, "account")
        result = await self.session.scalar(
            select(CRMEntityMapping.revenueos_entity_id).where(
                CRMEntityMapping.organisation_id == self.tenant.organisation_id,
                CRMEntityMapping.connection_id == connection.id,
                CRMEntityMapping.external_object_type == external_type,
                CRMEntityMapping.external_object_id == external_account_id,
                CRMEntityMapping.sync_state == "active",
            )
        )
        return result

    async def _inbound_stage(self, connection_id: UUID, external_stage: object | None) -> str | None:
        if not isinstance(external_stage, str) or not external_stage:
            return None
        result = await self.session.scalar(
            select(CRMStageMapping.revenueos_stage).where(
                CRMStageMapping.organisation_id == self.tenant.organisation_id,
                CRMStageMapping.connection_id == connection_id,
                CRMStageMapping.external_stage_id == external_stage,
            )
        )
        return result

    def _new_mapping(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        record: CRMProviderRecord,
        entity_id: UUID,
        now: datetime,
    ) -> CRMEntityMapping:
        return CRMEntityMapping(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            revenueos_entity_type=self._entity_type(record.object_type),
            revenueos_entity_id=entity_id,
            external_object_type=self._external_object_type(connection.connector_key, record.object_type),
            external_object_id=record.external_object_id,
            external_updated_at=record.modified_at,
            last_synced_at=now,
            sync_state="active",
            created_by_user_id=self.tenant.user_id,
            external_version=record.external_version,
            authority_version=state.mapping_version,
            archived_at=None,
            created_at=now,
            updated_at=now,
        )

    async def _create_conflict(
        self,
        connection: IntegrationConnection,
        record: CRMProviderRecord,
        entity_id: UUID | None,
        field: str,
        local_value: object | None,
        provider_value: object | None,
    ) -> CRMConflict:
        row = await self.session.scalar(
            select(CRMConflict).where(
                CRMConflict.organisation_id == self.tenant.organisation_id,
                CRMConflict.connection_id == connection.id,
                CRMConflict.object_type == record.object_type,
                CRMConflict.external_object_id == record.external_object_id,
                CRMConflict.field_key == field,
                CRMConflict.status == "open",
            )
        )
        local_json = self._json_value(local_value)
        provider_json = self._json_value(provider_value)
        if row is None:
            row = CRMConflict(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                provider_key=connection.connector_key,
                object_type=record.object_type,
                revenueos_entity_id=entity_id,
                external_object_id=record.external_object_id,
                field_key=field[:64],
                oryntela_value_json=local_json,
                provider_value_json=provider_json,
                oryntela_fingerprint=self._fingerprint(local_json),
                provider_fingerprint=self._fingerprint(provider_json),
                status="open",
                resolution=None,
                resolved_by_user_id=None,
                resolved_at=None,
            )
            self.session.add(row)
        else:
            row.revenueos_entity_id = entity_id
            row.oryntela_value_json = local_json
            row.provider_value_json = provider_json
            row.oryntela_fingerprint = self._fingerprint(local_json)
            row.provider_fingerprint = self._fingerprint(provider_json)
        return row

    def _change(
        self,
        object_type: CRMObjectType,
        entity_id: UUID,
        field: str,
        old_value: object | None,
        new_value: object | None,
        actor_user_id: UUID,
    ) -> CRMRecordChange:
        return CRMRecordChange(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            entity_type=object_type,
            entity_id=entity_id,
            field_key=field[:80],
            old_value_json=self._json_value(old_value),
            new_value_json=self._json_value(new_value),
            source="external_crm",
            changed_by_user_id=actor_user_id,
            changed_at=datetime.now(UTC),
        )

    def _receipt(
        self,
        connection: IntegrationConnection,
        *,
        direction: Literal["inbound", "outbound"],
        object_type: CRMObjectType,
        operation: str,
        status: str,
        idempotency_key: str,
        entity_id: UUID | None,
        external_object_id: str | None,
        external_version: str | None,
        fields: tuple[str, ...],
        safe_failure_code: str | None,
        now: datetime,
    ) -> CRMSyncReceipt:
        return CRMSyncReceipt(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            provider_key=connection.connector_key,
            direction=direction,
            object_type=object_type,
            operation=operation,
            status=status,
            idempotency_key=idempotency_key,
            revenueos_entity_id=entity_id,
            external_object_id=external_object_id,
            external_version=external_version,
            field_keys_json=list(fields),
            safe_failure_code=safe_failure_code,
            created_at=now,
        )

    async def _connection(
        self,
        connection_id: UUID,
        *,
        require_active: bool = True,
    ) -> IntegrationConnection:
        connection = await self.session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organisation_id == self.tenant.organisation_id,
                IntegrationConnection.id == connection_id,
                IntegrationConnection.connector_key.in_(("hubspot", "salesforce")),
            )
        )
        if connection is None or (require_active and connection.connection_status != "active"):
            raise PublicAPIError("connection_not_found", "The requested CRM connection was not found.", 404)
        return connection

    async def _state(self, connection_id: UUID, *, for_update: bool = False) -> CRMConnectionState:
        statement = select(CRMConnectionState).where(
            CRMConnectionState.organisation_id == self.tenant.organisation_id,
            CRMConnectionState.connection_id == connection_id,
        )
        if for_update:
            statement = statement.with_for_update()
        state = await self.session.scalar(statement)
        if state is None:
            raise PublicAPIError(
                "crm_connection_state_missing",
                "Reconnect the CRM before continuing.",
                409,
            )
        return state

    def _adapter(self, connection: IntegrationConnection) -> CRMProviderAdapter:
        adapter = self.adapters.get(connection.connector_key)
        if adapter is None:
            raise PublicAPIError(
                "provider_setup_required",
                "This CRM provider is not configured for this environment.",
                409,
            )
        return adapter

    def _context(self, connection: IntegrationConnection) -> ExecutorConnectionContext:
        return ExecutorConnectionContext(
            organisation_id=connection.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode="live",
            external_account_id=connection.external_account_id,
            external_account_email=connection.external_account_email,
            external_tenant_id=connection.external_tenant_id,
        )

    def _configured_adapters(self) -> dict[str, CRMProviderAdapter]:
        if self.settings.connector_credential_master_key is None:
            return {}
        store = EncryptedDatabaseCredentialStore(
            self.session,
            self.settings.connector_credential_master_key.get_secret_value(),
        )
        adapters: dict[str, CRMProviderAdapter] = {}
        if self.settings.feature_hubspot_crm_enabled:
            from revenueos.hubspot_connector import HubSpotClient, HubSpotSyncAdapter

            adapters["hubspot"] = cast(
                CRMProviderAdapter,
                HubSpotSyncAdapter(HubSpotClient(self.settings, store)),
            )
        if self.settings.feature_salesforce_crm_enabled:
            from revenueos.salesforce_connector import SalesforceClient

            adapters["salesforce"] = cast(
                CRMProviderAdapter,
                SalesforceClient(self.settings, store),
            )
        return adapters

    @staticmethod
    def _object_type(entity_type: str) -> CRMObjectType:
        if entity_type == "company":
            return "account"
        if entity_type == "contact":
            return "contact"
        if entity_type == "opportunity":
            return "opportunity"
        raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)

    @staticmethod
    def _entity_type(object_type: CRMObjectType) -> str:
        return "company" if object_type == "account" else object_type

    @staticmethod
    def _external_object_type(connector_key: str, object_type: CRMObjectType) -> str:
        if connector_key == "hubspot":
            return {"account": "company", "contact": "contact", "opportunity": "deal"}[object_type]
        if connector_key == "salesforce":
            return object_type
        raise PublicAPIError("connector_unavailable", "The selected CRM connector is unavailable.", 404)

    @staticmethod
    def _domain(value: object | None) -> tuple[str, str] | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            result = normalise_company_website(value)
        except PublicUrlSafetyError:
            return None
        return result.url, result.domain

    @staticmethod
    def _strong_email(value: str) -> bool:
        local, separator, domain = value.strip().casefold().partition("@")
        return bool(separator and "." in domain and local not in _GENERIC_EMAIL_LOCALS)

    @staticmethod
    def _text(value: object | None, limit: int) -> str | None:
        if not isinstance(value, str):
            return None
        return value.strip()[:limit] or None

    @staticmethod
    def _date(value: object | None) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _money(amount: object | None, currency: object | None) -> tuple[Decimal | None, str | None]:
        if amount in (None, ""):
            return None, None
        try:
            number = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return None, None
        if number < 0:
            return None, None
        code = currency.strip().upper() if isinstance(currency, str) else None
        if code is None or len(code) != 3 or not code.isalpha():
            return None, None
        return number, code

    @staticmethod
    def _json_value(value: object | None) -> object | None:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            return {
                str(key)[:256]: CRMConnectorService._json_value(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        if isinstance(value, (list, tuple)):
            return [CRMConnectorService._json_value(item) for item in value]
        return str(value)[:2048]

    @classmethod
    def _fingerprint(cls, value: object | None) -> str:
        payload = json.dumps(cls._json_value(value), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _status_response(
        self,
        state: CRMConnectionState,
        cursors: list[CRMSyncCursor],
        latest: CRMSyncJob | None,
    ) -> CRMConnectionStatusResponse:
        return CRMConnectionStatusResponse(
            connection_id=state.connection_id,
            provider_key=cast(Literal["hubspot", "salesforce"], state.provider_key),
            lifecycle=cast(
                Literal[
                    "connected_read_only",
                    "initial_sync",
                    "mapping_required",
                    "ready",
                    "needs_attention",
                    "disabled",
                ],
                state.lifecycle,
            ),
            health_status=cast(
                Literal["unknown", "healthy", "degraded", "needs_reauth", "rate_limited", "unavailable"],
                state.health_status,
            ),
            connector_enabled=state.connector_enabled,
            writeback_enabled=state.writeback_enabled,
            mapping_version=state.mapping_version,
            records_seen=state.records_seen,
            records_applied=state.records_applied,
            conflict_count=state.conflict_count,
            initial_sync_started_at=state.initial_sync_started_at,
            initial_sync_completed_at=state.initial_sync_completed_at,
            last_successful_sync_at=state.last_successful_sync_at,
            last_health_checked_at=state.last_health_checked_at,
            last_safe_error_code=state.last_safe_error_code,
            cursors=[
                CRMSyncCursorResponse(
                    object_type=cast(CRMObjectType, item.object_type),
                    strategy=cast(Literal["full", "incremental"], item.strategy),
                    page_count=item.page_count,
                    record_count=item.record_count,
                    high_watermark_at=item.high_watermark_at,
                    completed_at=item.completed_at,
                )
                for item in cursors
            ],
            latest_job=self._job_response(latest) if latest is not None else None,
        )

    @staticmethod
    def _job_response(job: CRMSyncJob) -> CRMSyncJobResponse:
        return CRMSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            provider_key=cast(Literal["hubspot", "salesforce"], job.provider_key),
            mode=cast(Literal["initial", "incremental", "reconcile"], job.mode),
            status=cast(
                Literal["queued", "running", "paused", "succeeded", "degraded", "cancelled", "failed"],
                job.status,
            ),
            attempt_count=job.attempt_count,
            safe_failure_code=job.safe_failure_code,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    @staticmethod
    def _owner_response(owner: CRMOwnerMapping) -> CRMOwnerMappingResponse:
        return CRMOwnerMappingResponse(
            id=owner.id,
            connection_id=owner.connection_id,
            provider_key=cast(Literal["hubspot", "salesforce"], owner.provider_key),
            external_owner_id=owner.external_owner_id,
            external_owner_name=owner.external_owner_name,
            external_owner_email=owner.external_owner_email,
            user_id=owner.user_id,
            state=cast(Literal["unmapped", "mapped", "inactive"], owner.state),
        )

    @staticmethod
    def _conflict_response(conflict: CRMConflict) -> CRMConflictResponse:
        return CRMConflictResponse(
            id=conflict.id,
            connection_id=conflict.connection_id,
            provider_key=cast(Literal["hubspot", "salesforce"], conflict.provider_key),
            object_type=cast(CRMObjectType, conflict.object_type),
            revenueos_entity_id=conflict.revenueos_entity_id,
            external_object_id=conflict.external_object_id,
            field_key=conflict.field_key,
            oryntela_value=conflict.oryntela_value_json,
            provider_value=conflict.provider_value_json,
            status=cast(Literal["open", "resolved", "ignored"], conflict.status),
            resolution=cast(Literal["provider", "oryntela", "manual"] | None, conflict.resolution),
            resolved_by_user_id=conflict.resolved_by_user_id,
            resolved_at=conflict.resolved_at,
            created_at=conflict.created_at,
            updated_at=conflict.updated_at,
        )

    @staticmethod
    def _preview_response(preview: CRMWritebackPreview) -> CRMWritebackPreviewResponse:
        return CRMWritebackPreviewResponse(
            id=preview.id,
            connection_id=preview.connection_id,
            entity_type=cast(Literal["company", "contact", "opportunity"], preview.entity_type),
            entity_id=preview.entity_id,
            operation=cast(Literal["create", "update"], preview.operation),
            external_object_id=preview.external_object_id,
            changes={key: value for key, value in preview.changes_json.items()},
            preview_fingerprint=preview.preview_fingerprint,
            expires_at=preview.expires_at,
        )

    @staticmethod
    def _writeback_result(receipt: CRMSyncReceipt) -> CRMWritebackResultResponse:
        status = cast(Literal["applied", "reconciled", "unknown"], receipt.status)
        message = {
            "applied": "The reviewed CRM writeback completed.",
            "reconciled": "The CRM writeback had already completed and was reconciled safely.",
            "unknown": "The CRM outcome is unknown. RevenueOS will not retry it automatically.",
        }[status]
        return CRMWritebackResultResponse(
            receipt_id=receipt.id,
            status=status,
            external_object_id=receipt.external_object_id,
            safe_message=message,
        )

    async def _open_conflict_count(self, connection_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count(CRMConflict.id)).where(
                    CRMConflict.organisation_id == self.tenant.organisation_id,
                    CRMConflict.connection_id == connection_id,
                    CRMConflict.status == "open",
                )
            )
            or 0
        )

    def _audit(
        self,
        connection: IntegrationConnection,
        event_type: str,
        subject_id: UUID,
        subject_type: str,
        now: datetime,
    ) -> None:
        self.session.add(
            IntegrationAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                connector_key=connection.connector_key,
                capability=None,
                risk_class=None,
                attempt_count=None,
                safe_failure_code=None,
                external_result_id=None,
                duration_ms=None,
                created_at=now,
            )
        )

    async def _commit(self, safe_message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("crm_state_conflict", safe_message, 409) from exc

    def _require_admin(self) -> None:
        if not self.settings.feature_integrations_enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)

    async def _require_entitlement(self) -> None:
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            "crm",
        )

    @staticmethod
    def _raise_provider_error(provider_key: str, error: CRMProviderError) -> NoReturn:
        display = "HubSpot" if provider_key == "hubspot" else "Salesforce"
        status = 429 if error.code == "provider_rate_limited" else 409
        messages = {
            "connection_reauthorisation_required": f"Reconnect {display} before continuing.",
            "provider_rate_limited": f"{display} is temporarily rate limited. Try again later.",
            "provider_not_found": f"The {display} record was not found.",
            "provider_stale_write": f"The {display} record changed. Create a new preview.",
            "provider_response_invalid": f"{display} returned an unusable response.",
        }
        raise PublicAPIError(
            error.code,
            messages.get(error.code, f"{display} could not complete the CRM request safely."),
            status,
        ) from error

    async def _strong_match(self, record: CRMProviderRecord) -> Company | Contact | None:
        if record.object_type == "account":
            canonical = self._domain(record.fields.get("domain"))
            if canonical is None:
                return None
            company_matches = list(
                (
                    await self.session.scalars(
                        select(Company).where(
                            Company.organisation_id == self.tenant.organisation_id,
                            Company.normalized_domain == canonical[1],
                            Company.archived_at.is_(None),
                        )
                    )
                ).all()
            )
            return company_matches[0] if len(company_matches) == 1 else None
        if record.object_type == "contact":
            email = record.fields.get("email")
            if not isinstance(email, str) or not self._strong_email(email):
                return None
            contact_matches = list(
                (
                    await self.session.scalars(
                        select(Contact).where(
                            Contact.organisation_id == self.tenant.organisation_id,
                            func.lower(Contact.email) == email.casefold(),
                            Contact.archived_at.is_(None),
                        )
                    )
                ).all()
            )
            return contact_matches[0] if len(contact_matches) == 1 else None
        return None

    async def _create_canonical_entity(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        record: CRMProviderRecord,
    ) -> Company | Contact | Opportunity | None:
        owner_id = await self._owner_user_id(connection.id, record.owner_external_id)
        if owner_id is None:
            await self._create_conflict(
                connection,
                record,
                None,
                "owner",
                None,
                record.owner_external_id,
            )
            return None
        now = datetime.now(UTC)
        if record.object_type == "account":
            name = self._text(record.fields.get("name"), 200)
            if name is None:
                await self._create_conflict(connection, record, None, "name", None, record.fields.get("name"))
                return None
            website, domain = self._domain(record.fields.get("domain")) or (None, None)
            entity: Company | Contact | Opportunity = Company(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                name=name,
                website=website,
                normalized_domain=domain,
                industry=self._text(record.fields.get("industry"), 120),
                location=None,
                employee_count=None,
                status="prospect",
                owner_user_id=owner_id,
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
        elif record.object_type == "contact":
            company_id = await self._related_company_id(connection, record.related_account_external_id)
            if company_id is None:
                await self._create_conflict(
                    connection,
                    record,
                    None,
                    "account",
                    None,
                    record.related_account_external_id,
                )
                return None
            first_name = self._text(record.fields.get("first_name"), 100)
            last_name = self._text(record.fields.get("last_name"), 100)
            if first_name is None or last_name is None:
                await self._create_conflict(connection, record, None, "name", None, "incomplete")
                return None
            entity = Contact(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                company_id=company_id,
                first_name=first_name,
                last_name=last_name,
                email=self._text(record.fields.get("email"), 320),
                phone=self._text(record.fields.get("phone"), 50),
                job_title=self._text(record.fields.get("job_title"), 150),
                linkedin_url=None,
                status="active",
                owner_user_id=owner_id,
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
        else:
            opportunity_company_id: UUID | None = None
            if record.related_account_external_id is not None:
                opportunity_company_id = await self._related_company_id(connection, record.related_account_external_id)
                if opportunity_company_id is None:
                    await self._create_conflict(
                        connection,
                        record,
                        None,
                        "account",
                        None,
                        record.related_account_external_id,
                    )
                    return None
            stage_key = await self._inbound_stage(connection.id, record.fields.get("stage"))
            if stage_key is None:
                await self._create_conflict(connection, record, None, "stage", None, record.fields.get("stage"))
                return None
            name = self._text(record.fields.get("name"), 200)
            if name is None:
                await self._create_conflict(connection, record, None, "name", None, record.fields.get("name"))
                return None
            pipeline, stages = await ensure_default_pipeline(self.session, self.tenant.organisation_id)
            status = "won" if stage_key == "closed_won" else "lost" if stage_key == "closed_lost" else "open"
            stage = initial_stage_for(stages, stage_key, status)
            amount, currency = self._money(record.fields.get("estimated_value"), record.fields.get("currency"))
            entity = Opportunity(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                company_id=opportunity_company_id,
                name=name,
                stage=stage_key,
                status=status,
                estimated_value=amount,
                currency=currency,
                expected_close_date=self._date(record.fields.get("expected_close_date")),
                owner_user_id=owner_id,
                description=self._text(record.fields.get("description"), 2000),
                archived_at=None,
                pipeline_id=pipeline.id,
                pipeline_stage_id=stage.id,
                stage_entered_at=record.modified_at,
                stage_tracking_started_at=record.modified_at,
                actual_close_date=None,
                outcome_reason=None,
                outcome_note=None,
                outcome_provenance=None,
                created_at=now,
                updated_at=now,
            )
            self.session.add(entity)
            await self.session.flush()
            self.session.add(
                OpportunityStageEvent(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    opportunity_id=entity.id,
                    from_pipeline_id=None,
                    to_pipeline_id=pipeline.id,
                    from_stage_id=None,
                    to_stage_id=stage.id,
                    from_stage_name=None,
                    to_stage_name=stage.name,
                    from_stage_type=None,
                    to_stage_type=stage.stage_type,
                    changed_by_user_id=connection.created_by_user_id,
                    changed_at=record.modified_at,
                    source="external_crm",
                    is_baseline=True,
                    previous_stage_entered_at=None,
                    outcome_reason=None,
                    outcome_note=None,
                    outcome_provenance=None,
                    actual_close_date=None,
                    final_amount=None,
                    final_currency=None,
                    idempotency_key=f"crm-sync:{record.external_object_id}:{record.external_version}"[:100],
                )
            )
        self.session.add(entity)
        await self.session.flush()
        for field, value in record.fields.items():
            if value is not None:
                self.session.add(
                    self._change(record.object_type, entity.id, field, None, value, connection.created_by_user_id)
                )
        return entity
