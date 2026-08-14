from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
    RevenueBrainInteractionSnapshot,
    VisualAsset,
    VisualCandidateEvidence,
)
from revenueos.tenant import TenantContext
from revenueos.visual_contracts import (
    VisualAnalysisCandidate,
    VisualCandidateRegion,
    VisualCandidateResponse,
    VisualDeleteResponse,
    VisualEvidenceCategory,
    VisualEvidenceResponse,
    VisualProcessingStatus,
    VisualProcessRequest,
    VisualReviewRequest,
    VisualReviewResponse,
    VisualSourceOwnership,
    VisualType,
    VisualUploadCompleteRequest,
    VisualUploadCreateRequest,
    VisualUploadCreateResponse,
)
from revenueos.visual_images import UnsafeVisualError, validate_and_sanitise_visual
from revenueos.visual_provider import (
    VisualAnalysisProvider,
    VisualProviderError,
    create_visual_provider,
    execute_visual_analysis,
)
from revenueos.visual_repositories import VisualAssetRecord, VisualEvidenceRepository
from revenueos.visual_storage import (
    VisualGrantSigner,
    VisualObjectMissingError,
    VisualStorage,
    VisualStorageError,
    create_visual_storage,
)

logger = logging.getLogger("revenueos.visual_evidence")

SELLER_SIGNAL_CATEGORIES = frozenset(
    {
        "customer_request",
        "decision",
        "action_item",
        "timeline",
        "procurement",
        "budget",
        "objection",
        "commercial_intent",
    }
)
SITE_PHOTO_CATEGORIES = frozenset({"technical_constraint", "implementation_requirement", "risk", "other"})


class VisualEvidenceService:
    """Private visual upload, conservative extraction and complete human review."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        storage: VisualStorage | None = None,
        provider: VisualAnalysisProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = VisualEvidenceRepository(session)
        self.beta = BetaService(session, tenant, settings)
        self.storage = storage or create_visual_storage(settings)
        self.provider = provider or create_visual_provider(settings)
        self.grants = VisualGrantSigner(settings.visual_storage_signing_secret.get_secret_value())

    async def create_upload(
        self,
        interaction_id: UUID,
        request: VisualUploadCreateRequest,
    ) -> VisualUploadCreateResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("visualEvidence")
        if request.byte_size > self.settings.private_beta_max_visual_bytes:
            raise PublicAPIError(
                "image_too_large",
                f"Images must be {self.settings.private_beta_max_visual_bytes:,} bytes or fewer.",
                413,
            )
        existing = await self.repository.find_idempotent_upload(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if not self._same_upload(existing.visual, request):
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That request key was already used for a different visual upload.",
                    409,
                )
            existing.visual.upload_expires_at = datetime.now(UTC) + timedelta(
                seconds=self.settings.visual_signed_url_ttl_seconds
            )
            await self._commit("The upload grant could not be renewed.")
            return await self._upload_response(existing)
        interaction = await self._require_interaction(interaction_id)
        if interaction.interaction_type == "presentation":
            self.beta.require_feature("presentationMode")
        count, total_bytes = await self.repository.visual_usage(self.tenant.organisation_id, interaction_id)
        if count >= self.settings.private_beta_max_visuals_per_interaction:
            raise PublicAPIError(
                "visual_count_limit_exceeded",
                "This interaction has reached its visual evidence limit.",
                429,
            )
        if total_bytes + request.byte_size > self.settings.private_beta_max_visual_bytes_per_interaction:
            raise PublicAPIError(
                "visual_storage_limit_exceeded",
                "This interaction has reached its visual storage limit.",
                429,
            )
        visual_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.visual_signed_url_ttl_seconds)
        extension = ".jpg" if request.mime_type == "image/jpeg" else ".png"
        storage_key = f"{self.tenant.organisation_id}/{interaction_id}/{uuid.uuid4().hex}{extension}"
        origin, support = self._source_evidence_provenance(request.source_ownership)
        capture = CaptureSession(
            id=visual_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_type="visual_capture",
            status="created",
            started_by_user_id=self.tenant.user_id,
            started_at=now,
        )
        evidence = Evidence(
            id=evidence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=visual_id,
            evidence_type="visual",
            origin_class=origin,
            support_class=support,
            validation_state="unreviewed",
            captured_by_user_id=self.tenant.user_id,
            captured_at=request.captured_at,
            lifecycle_status="received",
            retention_class="inherited",
        )
        visual = VisualAsset(
            id=visual_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=visual_id,
            source_evidence_id=evidence_id,
            captured_by_user_id=self.tenant.user_id,
            visual_type=request.visual_type,
            source_ownership=request.source_ownership,
            context_label=request.context_label,
            display_filename=self._safe_filename(request.filename, extension),
            storage_key=storage_key,
            mime_type=request.mime_type,
            byte_size=request.byte_size,
            upload_byte_size=request.byte_size,
            checksum_sha256=request.checksum_sha256,
            upload_checksum_sha256=request.checksum_sha256,
            captured_at=request.captured_at,
            upload_idempotency_key=request.idempotency_key,
            processing_status="uploading",
            storage_status="pending",
            upload_expires_at=expires_at,
        )
        self.session.add_all((capture, evidence, visual))
        self._event(
            "visual_capture_started",
            visual_id,
            {
                "visual_type": request.visual_type,
                "source_ownership": request.source_ownership,
                "byte_size": request.byte_size,
                "storage_backend": self.storage.backend_name,
            },
        )
        await self._commit("The visual upload could not be started.")
        return await self._upload_response(VisualAssetRecord(capture, evidence, visual))

    async def upload_content(
        self,
        interaction_id: UUID,
        visual_id: UUID,
        *,
        token: str,
        content: bytes,
        content_type: str | None,
    ) -> None:
        self.beta.require_feature("visualEvidence")
        if self.storage.direct_upload:
            raise PublicAPIError("upload_route_unavailable", "Use the supplied private object-storage upload URL.", 409)
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        if visual.captured_by_user_id != self.tenant.user_id or not self.grants.verify(
            token,
            self.tenant.organisation_id,
            self.tenant.user_id,
            visual_id,
            "upload",
        ):
            raise PublicAPIError("upload_grant_invalid", "The visual upload grant is invalid or expired.", 403)
        if visual.processing_status != "uploading":
            raise PublicAPIError("invalid_visual_transition", "This visual is not waiting for an upload.", 409)
        if content_type is None or content_type.split(";", 1)[0].strip().lower() != visual.mime_type:
            raise PublicAPIError("mime_mismatch", "The upload Content-Type does not match the request.", 415)
        if len(content) > self.settings.private_beta_max_visual_bytes:
            raise PublicAPIError("image_too_large", "The uploaded image exceeds the configured size limit.", 413)
        try:
            await self.storage.write(visual.storage_key, content, visual.mime_type)
        except VisualStorageError as exc:
            raise PublicAPIError("visual_upload_failed", "The visual upload could not be stored.", 503) from exc

    async def complete_upload(
        self,
        interaction_id: UUID,
        visual_id: UUID,
        request: VisualUploadCompleteRequest,
    ) -> VisualEvidenceResponse:
        self.beta.require_feature("visualEvidence")
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        if visual.captured_by_user_id != self.tenant.user_id:
            raise PublicAPIError("visual_not_found", "The requested visual evidence was not found.", 404)
        if visual.processing_status != "uploading":
            if visual.completion_idempotency_key == request.idempotency_key:
                return await self._response(record)
            raise PublicAPIError("invalid_visual_transition", "This visual upload has already been finalised.", 409)
        if request.checksum_sha256 != visual.upload_checksum_sha256:
            raise PublicAPIError("upload_checksum_mismatch", "The upload checksum does not match the request.", 422)
        try:
            raw = await self.storage.read(visual.storage_key)
            validated = validate_and_sanitise_visual(
                raw,
                declared_mime_type=visual.mime_type,
                declared_byte_size=visual.upload_byte_size,
                declared_checksum=visual.upload_checksum_sha256,
                max_bytes=self.settings.private_beta_max_visual_bytes,
                max_dimension=self.settings.private_beta_max_visual_dimension,
                max_pixels=self.settings.private_beta_max_visual_pixels,
            )
            await self.storage.write(visual.storage_key, validated.content, validated.mime_type)
        except VisualObjectMissingError as exc:
            raise PublicAPIError(
                "visual_upload_incomplete", "Finish uploading the image before finalising it.", 409
            ) from exc
        except UnsafeVisualError as exc:
            await self._reject_unsafe_upload(record, exc.code)
            raise PublicAPIError(exc.code, str(exc), 422) from exc
        except VisualStorageError as exc:
            raise PublicAPIError("visual_storage_failure", "The visual upload could not be verified.", 503) from exc
        now = datetime.now(UTC)
        visual.byte_size = len(validated.content)
        visual.checksum_sha256 = validated.checksum_sha256
        visual.width = validated.width
        visual.height = validated.height
        visual.completion_idempotency_key = request.idempotency_key
        visual.processing_status = "uploaded"
        visual.storage_status = "available"
        visual.upload_completed_at = now
        record.source_evidence.lifecycle_status = "available"
        record.capture_session.status = "capturing"
        self._event(
            "upload_completed",
            visual_id,
            {
                "visual_type": visual.visual_type,
                "byte_size": visual.byte_size,
                "width": visual.width,
                "height": visual.height,
                "metadata_stripped": validated.metadata_stripped,
            },
        )
        await self._commit("The visual upload could not be finalised.")
        return await self._response(record)

    async def list_visuals(self, interaction_id: UUID) -> list[VisualEvidenceResponse]:
        self.beta.require_feature("visualEvidence")
        await self._require_interaction(interaction_id)
        records = await self.repository.list_visuals(self.tenant.organisation_id, interaction_id)
        return [await self._response(record) for record in records]

    async def get_visual(self, interaction_id: UUID, visual_id: UUID) -> VisualEvidenceResponse:
        self.beta.require_feature("visualEvidence")
        return await self._response(await self._require_visual(interaction_id, visual_id))

    async def get_content(self, interaction_id: UUID, visual_id: UUID, token: str) -> tuple[bytes, str, str]:
        self.beta.require_feature("visualEvidence")
        record = await self._require_visual(interaction_id, visual_id)
        if not self.grants.verify(
            token,
            self.tenant.organisation_id,
            self.tenant.user_id,
            visual_id,
            "download",
        ):
            raise PublicAPIError("download_grant_invalid", "The visual download grant is invalid or expired.", 403)
        if record.visual.storage_status != "available":
            raise PublicAPIError("visual_unavailable", "The visual evidence is not available.", 410)
        try:
            content = await self.storage.read(record.visual.storage_key)
        except VisualStorageError as exc:
            raise PublicAPIError("visual_storage_failure", "The visual evidence could not be retrieved.", 503) from exc
        return content, record.visual.mime_type, record.visual.display_filename

    async def process(
        self,
        interaction_id: UUID,
        visual_id: UUID,
        request: VisualProcessRequest,
    ) -> VisualEvidenceResponse:
        self.beta.require_feature("visualEvidence")
        del request.idempotency_key
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        if visual.processing_status in {"review", "completed"}:
            return await self._response(record)
        if visual.processing_status not in {"uploaded", "failed"}:
            raise PublicAPIError("invalid_visual_transition", "This visual is not ready for processing.", 409)
        if visual.processing_attempts >= self.settings.private_beta_visual_processing_retries:
            raise PublicAPIError(
                "visual_processing_retry_limit",
                "This visual has reached its processing retry limit.",
                429,
            )
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        if (
            await self.repository.count_processing_since(self.tenant.organisation_id, today)
            >= self.settings.private_beta_max_visual_ai_requests_per_day
        ):
            raise PublicAPIError(
                "daily_visual_processing_limit_exceeded",
                "This organisation has reached today’s visual processing limit.",
                429,
            )
        if self.provider.provider_name == "openai":
            await self.beta.reserve_provider_request()
        visual.processing_status = "processing"
        visual.processing_attempts += 1
        visual.failure_code = None
        record.capture_session.status = "capturing"
        self._event(
            "processing_started",
            visual_id,
            {"visual_type": visual.visual_type, "processing_attempt": visual.processing_attempts},
        )
        await self._commit_before_provider("The visual processing state could not be saved.")
        try:
            image = await self.storage.read(visual.storage_key)
            provider_response = await execute_visual_analysis(
                self.provider,
                visual_id=visual_id,
                image=image,
                mime_type=visual.mime_type,
                visual_type=cast(VisualType, visual.visual_type),
                source_ownership=cast(VisualSourceOwnership, visual.source_ownership),
                context_label=visual.context_label,
                timeout_seconds=self.settings.visual_provider_timeout_seconds,
            )
        except (VisualProviderError, VisualStorageError) as exc:
            await self._mark_processing_failed(
                interaction_id, visual_id, getattr(exc, "code", "visual_processing_failed")
            )
            raise PublicAPIError(
                "visual_processing_failed",
                "The visual evidence could not be processed. You can retry within the configured limit.",
                503,
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        if visual.processing_status != "processing":
            return await self._response(record)
        if provider_response.result.finish_status != "completed":
            await self._mark_processing_failed(
                interaction_id,
                visual_id,
                f"visual_provider_{provider_response.result.finish_status}",
            )
            raise PublicAPIError(
                "visual_processing_failed",
                "The visual provider did not return a complete result.",
                503,
            )
        accepted_provider_candidates = self._eligible_provider_candidates(
            visual,
            list(provider_response.result.candidates),
        )
        for item in accepted_provider_candidates:
            statement = item.statement.strip()
            self.session.add(
                VisualCandidateEvidence(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    interaction_id=interaction_id,
                    source_visual_id=visual_id,
                    evidence_category=item.category,
                    statement=statement,
                    original_statement=statement,
                    statement_fingerprint=self._fingerprint(statement),
                    source_ownership=visual.source_ownership,
                    origin_class="ai_inferred",
                    support_classification=self._support_classification(visual),
                    validation_state="unreviewed",
                    review_state="pending",
                    conflict_state="not_assessed",
                    confidence_class=item.confidence_class,
                    evidence_region_json=(
                        item.evidence_region.model_dump(mode="json", by_alias=False)
                        if item.evidence_region is not None
                        else None
                    ),
                    entity_reference=item.related_entity,
                    extracted_text_snippet=item.extracted_text_snippet,
                )
            )
        now = datetime.now(UTC)
        visual.provider_name = provider_response.provider_name
        visual.provider_request_id = provider_response.provider_request_id
        visual.processed_at = now
        visual.processing_status = "review" if accepted_provider_candidates else "completed"
        if not accepted_provider_candidates:
            record.capture_session.status = "completed"
            record.capture_session.completed_at = now
        self._event(
            "processing_completed",
            visual_id,
            {
                "visual_type": visual.visual_type,
                "candidate_count": len(accepted_provider_candidates),
                "provider_name": provider_response.provider_name,
            },
        )
        await self._commit("The visual candidates could not be saved.")
        return await self._response(record)

    async def review(
        self,
        interaction_id: UUID,
        visual_id: UUID,
        request: VisualReviewRequest,
    ) -> VisualReviewResponse:
        self.beta.require_feature("visualEvidence")
        del request.idempotency_key
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        candidates = await self.repository.list_candidates(
            self.tenant.organisation_id,
            visual_id,
            for_update=True,
        )
        if visual.processing_status == "completed":
            return await self._review_response(record)
        if visual.processing_status != "review":
            raise PublicAPIError("invalid_visual_transition", "This visual is not awaiting review.", 409)
        by_id = {item.id: item for item in candidates}
        decision_ids = {item.candidate_id for item in request.decisions}
        if decision_ids != set(by_id):
            raise PublicAPIError("incomplete_review", "Review every visual candidate before finishing.", 422)
        now = datetime.now(UTC)
        accepted: list[VisualCandidateEvidence] = []
        for decision in request.decisions:
            candidate = by_id[decision.candidate_id]
            if candidate.review_state != "pending":
                continue
            candidate.reviewed_by_user_id = self.tenant.user_id
            candidate.reviewed_at = now
            if decision.decision == "reject":
                candidate.review_state = "rejected"
                candidate.validation_state = "rejected"
                continue
            statement = decision.statement or candidate.statement
            accepted_evidence_id = uuid.uuid4()
            candidate.statement = statement
            candidate.review_state = "accepted"
            candidate.validation_state = "verified"
            candidate.accepted_evidence_id = accepted_evidence_id
            self.session.add(
                Evidence(
                    id=accepted_evidence_id,
                    organisation_id=self.tenant.organisation_id,
                    interaction_id=interaction_id,
                    capture_session_id=visual.capture_session_id,
                    evidence_type="visual",
                    origin_class="ai_inferred",
                    support_class=("observed" if candidate.support_classification == "observed" else "inferred"),
                    validation_state="verified",
                    captured_by_user_id=self.tenant.user_id,
                    captured_at=visual.captured_at,
                    lifecycle_status="available",
                    retention_class="inherited",
                )
            )
            accepted.append(candidate)
        eligible = [item for item in accepted if self._eligible_downstream(visual, item)]
        intelligence_id: UUID | None = None
        brain_id: UUID | None = None
        if eligible:
            interaction = await self._require_interaction(interaction_id)
            intelligence_id, brain_id = await self._create_snapshots(interaction, visual, eligible)
        visual.processing_status = "completed"
        record.capture_session.status = "completed"
        record.capture_session.completed_at = now
        self._event(
            "visual_evidence_reviewed",
            visual_id,
            {
                "visual_type": visual.visual_type,
                "accepted_count": len(accepted),
                "rejected_count": len(candidates) - len(accepted),
                "downstream_count": len(eligible),
                "interaction_updated": intelligence_id is not None,
                "revenue_brain_updated": brain_id is not None,
            },
        )
        await self._commit("The visual evidence review could not be saved.")
        return await self._review_response(record)

    async def delete_visual(self, interaction_id: UUID, visual_id: UUID) -> VisualDeleteResponse:
        self.beta.require_feature("visualEvidence")
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        visual = record.visual
        visual.processing_status = "deletion_pending"
        visual.storage_status = "deletion_pending"
        await self._commit_before_provider("The visual deletion state could not be saved.")
        try:
            await self.storage.delete(visual.storage_key)
        except VisualStorageError:
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            record = await self._require_visual(interaction_id, visual_id, for_update=True)
            record.visual.storage_status = "delete_failed"
            record.visual.failure_code = "visual_storage_delete_failed"
            self._event(
                "visual_deletion_failed",
                visual_id,
                {"error_code": "visual_storage_delete_failed"},
            )
            await self._commit("The retryable visual deletion state could not be saved.")
            return VisualDeleteResponse(id=visual_id, deleted=False, retry_required=True)
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        candidates = await self.repository.list_candidates(self.tenant.organisation_id, visual_id)
        accepted_evidence = [item.accepted_evidence_id for item in candidates if item.accepted_evidence_id is not None]
        for evidence_id in accepted_evidence:
            evidence = await self.session.scalar(
                select(Evidence).where(
                    Evidence.organisation_id == self.tenant.organisation_id,
                    Evidence.id == evidence_id,
                )
            )
            if evidence is not None:
                evidence.lifecycle_status = "deleted"
                evidence.deleted_at = datetime.now(UTC)
        record.source_evidence.lifecycle_status = "deleted"
        record.source_evidence.deleted_at = datetime.now(UTC)
        await self.session.execute(
            delete(VisualCandidateEvidence).where(
                VisualCandidateEvidence.organisation_id == self.tenant.organisation_id,
                VisualCandidateEvidence.source_visual_id == visual_id,
            )
        )
        now = datetime.now(UTC)
        record.visual.processing_status = "deleted"
        record.visual.storage_status = "deleted"
        record.visual.context_label = None
        record.visual.provider_request_id = None
        record.visual.failure_code = None
        record.visual.deleted_at = now
        record.capture_session.deleted_at = now
        self._event("visual_evidence_deleted", visual_id, {"visual_type": record.visual.visual_type})
        await self._commit("The visual deletion could not be completed.")
        return VisualDeleteResponse(id=visual_id, deleted=True, retry_required=False)

    async def _create_snapshots(
        self,
        interaction: Interaction,
        visual: VisualAsset,
        candidates: list[VisualCandidateEvidence],
    ) -> tuple[UUID, UUID | None]:
        source_ids = [str(item.accepted_evidence_id) for item in candidates if item.accepted_evidence_id is not None]
        source_label = self._source_label(visual)
        content: dict[str, object] = {
            "schemaVersion": 2,
            "origin": "ai_inferred",
            "sourceLabel": source_label,
            "sourceOwnership": visual.source_ownership,
            "sourceVisualId": str(visual.id),
            "visualType": visual.visual_type,
            "items": [
                {
                    "candidateId": str(item.id),
                    "evidenceId": str(item.accepted_evidence_id),
                    "category": item.evidence_category,
                    "statement": item.statement,
                    "origin": "ai_inferred",
                    "sourceOwnership": item.source_ownership,
                    "supportClassification": item.support_classification,
                    "sourceLabel": source_label,
                    "validationState": "verified",
                    "conflictState": item.conflict_state,
                }
                for item in candidates
            ],
        }
        intelligence_id = uuid.uuid4()
        intelligence = InteractionIntelligenceSnapshot(
            id=intelligence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            opportunity_id=interaction.opportunity_id,
            session_id=visual.capture_session_id,
            schema_version=2,
            version=await self.repository.next_intelligence_version(
                self.tenant.organisation_id,
                interaction.id,
            ),
            validation_state="validated",
            content_json=content,
            source_evidence_ids=source_ids,
        )
        self.session.add(intelligence)
        company_id = await self.repository.company_for_interaction(self.tenant.organisation_id, interaction)
        if company_id is None:
            return intelligence_id, None
        brain_id = uuid.uuid4()
        self.session.add(
            RevenueBrainInteractionSnapshot(
                id=brain_id,
                organisation_id=self.tenant.organisation_id,
                company_id=company_id,
                opportunity_id=interaction.opportunity_id,
                interaction_id=interaction.id,
                interaction_intelligence_id=intelligence_id,
                schema_version=2,
                version=await self.repository.next_brain_version(
                    self.tenant.organisation_id,
                    company_id,
                    interaction.opportunity_id,
                ),
                content_json=content,
                source_evidence_ids=source_ids,
            )
        )
        return intelligence_id, brain_id

    async def _upload_response(self, record: VisualAssetRecord) -> VisualUploadCreateResponse:
        base = await self._response(record)
        upload_url = self.storage.upload_url(
            record.visual.storage_key,
            record.visual.mime_type,
            record.visual.upload_expires_at,
        )
        if upload_url is None:
            token = self.grants.issue(
                self.tenant.organisation_id,
                self.tenant.user_id,
                record.visual.id,
                "upload",
                record.visual.upload_expires_at,
            )
            upload_url = (
                f"/api/v1/interactions/{record.visual.interaction_id}/visual-evidence/"
                f"{record.visual.id}/content?token={token}"
            )
        return VisualUploadCreateResponse(
            **base.model_dump(),
            upload_url=upload_url,
            upload_expires_at=self._as_utc(record.visual.upload_expires_at),
        )

    async def _response(self, record: VisualAssetRecord) -> VisualEvidenceResponse:
        visual = record.visual
        # Database-managed timestamps are expired after writes; refresh inside the
        # async context before serialising so attribute access never performs
        # implicit I/O.
        await self.session.refresh(visual)
        candidates = await self.repository.list_candidates(self.tenant.organisation_id, visual.id)
        intelligence = await self.repository.intelligence_for_session(
            self.tenant.organisation_id,
            visual.capture_session_id,
        )
        brain = (
            await self.repository.brain_for_intelligence(self.tenant.organisation_id, intelligence.id)
            if intelligence is not None
            else None
        )
        download_url: str | None = None
        if visual.storage_status == "available" and visual.deleted_at is None:
            expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.visual_signed_url_ttl_seconds)
            download_url = self.storage.download_url(visual.storage_key, expires_at)
            if download_url is None:
                token = self.grants.issue(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    visual.id,
                    "download",
                    expires_at,
                )
                download_url = (
                    f"/api/v1/interactions/{visual.interaction_id}/visual-evidence/{visual.id}/content?token={token}"
                )
        return VisualEvidenceResponse(
            id=visual.id,
            interaction_id=visual.interaction_id,
            capture_session_id=visual.capture_session_id,
            visual_type=cast(VisualType, visual.visual_type),
            source_ownership=cast(VisualSourceOwnership, visual.source_ownership),
            context_label=visual.context_label,
            filename=visual.display_filename,
            mime_type=cast(Literal["image/jpeg", "image/png"], visual.mime_type),
            byte_size=visual.byte_size,
            width=visual.width,
            height=visual.height,
            checksum_sha256=visual.checksum_sha256,
            captured_at=self._as_utc(visual.captured_at),
            processing_status=cast(VisualProcessingStatus, visual.processing_status),
            processing_attempts=visual.processing_attempts,
            failure_code=visual.failure_code,
            provider_mode=self.provider.provider_name,
            external_processing=self.provider.provider_name == "openai",
            candidates=[self._candidate_response(item) for item in candidates],
            download_url=download_url,
            interaction_intelligence_id=intelligence.id if intelligence is not None else None,
            revenue_brain_snapshot_id=brain.id if brain is not None else None,
            created_at=self._as_utc(visual.created_at),
            updated_at=self._as_utc(visual.updated_at),
        )

    async def _review_response(self, record: VisualAssetRecord) -> VisualReviewResponse:
        base = await self._response(record)
        accepted = sum(item.review_state == "accepted" for item in base.candidates)
        rejected = sum(item.review_state == "rejected" for item in base.candidates)
        return VisualReviewResponse(
            **base.model_dump(),
            accepted_count=accepted,
            rejected_count=rejected,
            interaction_updated=base.interaction_intelligence_id is not None,
            revenue_brain_updated=base.revenue_brain_snapshot_id is not None,
        )

    async def _require_interaction(self, interaction_id: UUID) -> Interaction:
        interaction = await self.repository.get_interaction(self.tenant.organisation_id, interaction_id)
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        if interaction.lifecycle_status == "cancelled":
            raise PublicAPIError(
                "interaction_cancelled",
                "Visual evidence cannot be added to a cancelled interaction.",
                409,
            )
        return interaction

    async def _require_visual(
        self,
        interaction_id: UUID,
        visual_id: UUID,
        *,
        for_update: bool = False,
    ) -> VisualAssetRecord:
        record = await self.repository.get_visual(
            self.tenant.organisation_id,
            interaction_id,
            visual_id,
            for_update=for_update,
        )
        if record is None:
            raise PublicAPIError("visual_not_found", "The requested visual evidence was not found.", 404)
        return record

    async def _reject_unsafe_upload(self, record: VisualAssetRecord, error_code: str) -> None:
        try:
            await self.storage.delete(record.visual.storage_key)
            record.visual.storage_status = "deleted"
        except VisualStorageError:
            record.visual.storage_status = "delete_failed"
        now = datetime.now(UTC)
        record.visual.processing_status = "failed"
        record.visual.failure_code = error_code[:100]
        record.capture_session.status = "failed"
        record.capture_session.completed_at = now
        record.source_evidence.lifecycle_status = "excluded"
        self._event("visual_upload_rejected", record.visual.id, {"error_code": error_code[:100]})
        await self._commit("The rejected upload state could not be saved.")

    async def _mark_processing_failed(self, interaction_id: UUID, visual_id: UUID, error_code: str) -> None:
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_visual(interaction_id, visual_id, for_update=True)
        if record.visual.processing_status != "processing":
            return
        record.visual.processing_status = "failed"
        record.visual.failure_code = error_code[:100]
        record.capture_session.status = "failed"
        self._event("visual_processing_failed", visual_id, {"error_code": error_code[:100]})
        await self._commit("The visual failure state could not be saved.")

    def _eligible_provider_candidates(
        self,
        visual: VisualAsset,
        candidates: list[VisualAnalysisCandidate],
    ) -> list[VisualAnalysisCandidate]:
        eligible: list[VisualAnalysisCandidate] = []
        seen: set[tuple[str, str]] = set()
        for item in candidates:
            if item.source_visual_id != visual.id:
                continue
            if visual.visual_type == "business_card" and item.category != "contact_detail":
                continue
            if visual.visual_type == "site_photo" and item.category not in SITE_PHOTO_CATEGORIES:
                continue
            if visual.source_ownership == "salesperson_created" and item.category in SELLER_SIGNAL_CATEGORIES:
                continue
            identity = (item.category, self._fingerprint(item.statement))
            if identity in seen:
                continue
            seen.add(identity)
            eligible.append(item)
        return eligible[:100]

    @staticmethod
    def _eligible_downstream(visual: VisualAsset, candidate: VisualCandidateEvidence) -> bool:
        if visual.visual_type == "business_card":
            return False
        if visual.source_ownership == "salesperson_created":
            return False
        if visual.visual_type == "site_photo":
            return candidate.evidence_category in SITE_PHOTO_CATEGORIES
        return True

    @staticmethod
    def _support_classification(visual: VisualAsset) -> str:
        if visual.visual_type == "site_photo":
            return "observed"
        if visual.source_ownership in {"salesperson_created", "unknown_origin"}:
            return "context"
        return "direct"

    @staticmethod
    def _source_evidence_provenance(source_ownership: VisualSourceOwnership) -> tuple[str, str]:
        if source_ownership == "salesperson_created":
            return "seller_prepared", "direct"
        if source_ownership in {"customer_created", "jointly_created"}:
            return "customer_direct", "direct"
        return "ai_inferred", "inferred"

    @staticmethod
    def _source_label(visual: VisualAsset) -> str:
        labels = {
            "whiteboard": "customer whiteboard",
            "workshop_output": "workshop output",
            "architecture_diagram": "architecture diagram",
            "site_photo": "site photo (observed)",
            "customer_document_photo": "customer document photo",
            "screenshot": "reviewed screenshot",
        }
        if visual.source_ownership == "salesperson_created":
            return "seller material (context only)"
        return labels.get(visual.visual_type, "reviewed visual evidence")

    def _candidate_response(self, item: VisualCandidateEvidence) -> VisualCandidateResponse:
        region = (
            VisualCandidateRegion.model_validate(item.evidence_region_json)
            if item.evidence_region_json is not None
            else None
        )
        return VisualCandidateResponse(
            id=item.id,
            category=cast(VisualEvidenceCategory, item.evidence_category),
            statement=item.statement,
            original_statement=item.original_statement,
            source_visual_id=item.source_visual_id,
            source_ownership=cast(VisualSourceOwnership, item.source_ownership),
            origin="ai_inferred",
            support_classification=cast(Literal["direct", "observed", "context"], item.support_classification),
            validation_state=cast(Literal["unreviewed", "verified", "rejected"], item.validation_state),
            review_state=cast(Literal["pending", "accepted", "rejected"], item.review_state),
            conflict_state=cast(Literal["not_assessed", "conflicting"], item.conflict_state),
            confidence_class=cast(Literal["low", "medium", "high"] | None, item.confidence_class),
            evidence_region=region,
            related_entity=item.entity_reference,
            extracted_text_snippet=item.extracted_text_snippet,
            accepted_evidence_id=item.accepted_evidence_id,
            edited=item.statement != item.original_statement,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

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

    async def _commit_before_provider(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            logger.warning(
                "visual_persistence_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "error_code": "visual_persistence_failed",
                },
            )
            raise PublicAPIError("persistence_failure", message, 500) from exc

    async def _commit(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            logger.warning(
                "visual_persistence_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "error_code": "visual_persistence_failed",
                },
            )
            raise PublicAPIError("persistence_failure", message, 500) from exc

    @staticmethod
    def _same_upload(visual: VisualAsset, request: VisualUploadCreateRequest) -> bool:
        return (
            visual.visual_type == request.visual_type
            and visual.source_ownership == request.source_ownership
            and visual.context_label == request.context_label
            and visual.mime_type == request.mime_type
            and visual.upload_byte_size == request.byte_size
            and visual.upload_checksum_sha256 == request.checksum_sha256
        )

    @staticmethod
    def _safe_filename(value: str, extension: str) -> str:
        basename = Path(value.replace("\\", "/")).name
        stem = Path(basename).stem
        safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem).strip(" .-_")[:120] or "visual-evidence"
        return f"{safe_stem}{extension}"

    @staticmethod
    def _fingerprint(statement: str) -> str:
        normalised = " ".join(statement.casefold().split())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
