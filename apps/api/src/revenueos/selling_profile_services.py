from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import cast, overload
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CompanyKnowledgeIngestionJob,
    CompanyKnowledgeSource,
    SellingProfile,
    SellingProfileRevision,
)
from revenueos.prospect_url_security import PublicUrlSafetyError, canonicalize_public_https_url
from revenueos.selling_profile_contracts import (
    CompanyKnowledgeSourceCreate,
    CompanyKnowledgeSourceResponse,
    KnowledgeSourceKind,
    KnowledgeSourceStatus,
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

    async def knowledge_sources(self) -> tuple[CompanyKnowledgeSourceResponse, ...]:
        await self._require_admin()
        return tuple(
            self._knowledge_source_response(item)
            for item in await self.repository.knowledge_sources(self.tenant.organisation_id)
        )

    async def create_knowledge_source(
        self,
        request: CompanyKnowledgeSourceCreate,
    ) -> CompanyKnowledgeSourceResponse:
        await self._require_admin()
        website_url = self._normalise_website(request.website_url) if request.website_url else None
        source_text = request.source_text
        source_document = self._decode_knowledge_document(request.source_document_base64)
        fingerprint_input = (
            website_url.encode("utf-8")
            if website_url is not None
            else source_text.encode("utf-8")
            if source_text is not None
            else source_document
        )
        if fingerprint_input is None:  # The request contract already prevents this.
            raise PublicAPIError("knowledge_source_invalid", "The knowledge source is incomplete.", 422)
        fingerprint = hashlib.sha256(fingerprint_input).hexdigest()
        existing = await self.repository.knowledge_source_by_idempotency(
            self.tenant.organisation_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if (
                existing.source_kind != request.source_kind
                or existing.label != request.label
                or existing.website_url != website_url
                or existing.source_text != source_text
                or existing.source_filename != request.source_filename
                or existing.source_mime_type != request.source_mime_type
                or existing.content_fingerprint != fingerprint
            ):
                raise PublicAPIError(
                    "knowledge_source_idempotency_conflict",
                    "This retry key was already used for different company knowledge.",
                    409,
                )
            return self._knowledge_source_response(existing)

        status: KnowledgeSourceStatus = "queued"
        source = CompanyKnowledgeSource(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            source_kind=request.source_kind,
            label=request.label,
            website_url=website_url,
            source_text=source_text,
            source_document=source_document,
            source_filename=request.source_filename,
            source_mime_type=request.source_mime_type,
            extracted_text=None,
            summary_text=None,
            content_fingerprint=fingerprint,
            processing_status=status,
            failure_code=None,
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
        )
        self.repository.add_knowledge_source(source)
        try:
            await self.session.flush()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "persistence_failure",
                "The company knowledge source could not be saved.",
                500,
            ) from exc
        self._queue_knowledge_job(source, "initial")
        self._event(
            "company_knowledge_source_added",
            source.id,
            {
                "source_kind": request.source_kind,
                "processing_status": status,
                "character_count": len(source_text or ""),
            },
        )
        await self._commit("The company knowledge source could not be saved.")
        await self.session.refresh(source)
        self._log_knowledge_source(source)
        return self._knowledge_source_response(source)

    async def approve_knowledge_source(self, source_id: UUID) -> CompanyKnowledgeSourceResponse:
        await self._require_admin()
        source = await self.repository.knowledge_source(
            self.tenant.organisation_id,
            source_id,
            for_update=True,
        )
        if source is None:
            raise self._knowledge_not_found()
        if source.processing_status != "ready_for_review":
            raise PublicAPIError(
                "knowledge_source_not_reviewable",
                "Only successfully prepared knowledge can be approved.",
                409,
            )
        now = datetime.now(UTC)
        source.processing_status = "approved"
        source.approved_at = now
        source.approved_by_user_id = self.tenant.user_id
        source.stale_at = None
        self._event("company_knowledge_source_approved", source.id, {"source_kind": source.source_kind})
        await self._commit("The company knowledge source could not be approved.")
        await self.session.refresh(source)
        return self._knowledge_source_response(source)

    async def retry_knowledge_source(self, source_id: UUID) -> CompanyKnowledgeSourceResponse:
        return await self._requeue_knowledge_source(source_id, action="retry", required_status="failed")

    async def refresh_knowledge_source(self, source_id: UUID) -> CompanyKnowledgeSourceResponse:
        return await self._requeue_knowledge_source(source_id, action="refresh", required_status=None)

    async def cancel_knowledge_source(self, source_id: UUID) -> CompanyKnowledgeSourceResponse:
        await self._require_admin()
        source = await self.repository.knowledge_source(
            self.tenant.organisation_id,
            source_id,
            for_update=True,
        )
        if source is None:
            raise self._knowledge_not_found()
        job = await self.repository.active_knowledge_job(
            self.tenant.organisation_id,
            source.id,
            for_update=True,
        )
        if job is None:
            raise PublicAPIError("knowledge_job_not_active", "No knowledge ingestion job is active.", 409)
        now = datetime.now(UTC)
        job.cancellation_requested_at = now
        if job.status == "pending":
            job.status = "cancelled"
            job.completed_at = now
            source.processing_status = "failed"
            source.failure_code = "ingestion_cancelled"
        self._event("company_knowledge_ingestion_cancelled", source.id, {"source_kind": source.source_kind})
        await self._commit("The knowledge ingestion job could not be cancelled.")
        await self.session.refresh(source)
        return self._knowledge_source_response(source)

    async def _requeue_knowledge_source(
        self,
        source_id: UUID,
        *,
        action: str,
        required_status: str | None,
    ) -> CompanyKnowledgeSourceResponse:
        await self._require_admin()
        source = await self.repository.knowledge_source(
            self.tenant.organisation_id,
            source_id,
            for_update=True,
        )
        if source is None:
            raise self._knowledge_not_found()
        if required_status is not None and source.processing_status != required_status:
            raise PublicAPIError(
                "knowledge_source_not_retryable",
                "Only failed knowledge ingestion can be retried.",
                409,
            )
        if await self.repository.active_knowledge_job(self.tenant.organisation_id, source.id) is not None:
            raise PublicAPIError("knowledge_job_active", "This knowledge source is already being prepared.", 409)
        source.processing_status = "stale" if action == "refresh" else "queued"
        source.failure_code = None
        source.approved_at = None
        source.approved_by_user_id = None
        source.stale_at = datetime.now(UTC) if action == "refresh" else source.stale_at
        self._queue_knowledge_job(source, action)
        self._event(
            "company_knowledge_ingestion_queued",
            source.id,
            {"source_kind": source.source_kind, "action": action},
        )
        await self._commit("The knowledge ingestion job could not be queued.")
        await self.session.refresh(source)
        return self._knowledge_source_response(source)

    async def delete_knowledge_source(self, source_id: UUID) -> None:
        await self._require_admin()
        source = await self.repository.knowledge_source(self.tenant.organisation_id, source_id)
        if source is None:
            raise PublicAPIError(
                "knowledge_source_not_found",
                "The company knowledge source was not found.",
                404,
            )
        await self.repository.delete_knowledge_source(source)
        self._event(
            "company_knowledge_source_deleted",
            source.id,
            {"source_kind": source.source_kind},
        )
        await self._commit("The company knowledge source could not be deleted.")

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
    def _normalise_website(value: str) -> str:
        try:
            canonical = canonicalize_public_https_url(value).url
            parsed = urlsplit(canonical)
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        except PublicUrlSafetyError as exc:
            raise PublicAPIError(
                "knowledge_website_invalid",
                "Enter a public HTTPS website address without credentials or an internal host.",
                422,
            ) from exc

    @staticmethod
    def _decode_knowledge_document(value: str | None) -> bytes | None:
        if value is None:
            return None
        try:
            content = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PublicAPIError(
                "knowledge_document_invalid",
                "The uploaded knowledge document is not valid base64 content.",
                422,
            ) from exc
        if not content or len(content) > 15_000_000:
            raise PublicAPIError(
                "knowledge_document_limit",
                "Knowledge documents must be non-empty and no larger than 15 MB.",
                422,
            )
        return content

    def _queue_knowledge_job(self, source: CompanyKnowledgeSource, action: str) -> None:
        request_fingerprint = hashlib.sha256(
            f"{source.id}:{action}:{datetime.now(UTC).isoformat()}:{uuid.uuid4()}".encode()
        ).hexdigest()
        self.repository.add_knowledge_job(
            CompanyKnowledgeIngestionJob(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                source_id=source.id,
                requested_by_user_id=self.tenant.user_id,
                status="pending",
                request_fingerprint=request_fingerprint,
                attempt_count=0,
                max_attempts=3,
            )
        )

    @staticmethod
    def _knowledge_not_found() -> PublicAPIError:
        return PublicAPIError(
            "knowledge_source_not_found",
            "The company knowledge source was not found.",
            404,
        )

    def _knowledge_source_response(
        self,
        source: CompanyKnowledgeSource,
    ) -> CompanyKnowledgeSourceResponse:
        status = cast(KnowledgeSourceStatus, source.processing_status)
        safe_message = {
            "queued": "This source is queued for bounded extraction. It is not used until an administrator approves it.",
            "fetching": "The public website is being fetched within the configured safety limits.",
            "extracting": "Text is being extracted. Embedded instructions are treated as untrusted source text.",
            "ready_for_review": "Extraction completed. Review the summary and source text before approving it.",
            "approved": "This source is approved organisation context, not customer Evidence.",
            "stale": "This source changed or was queued for refresh and is excluded until it is reviewed again.",
            "failed": "This source could not be prepared. Approved company knowledge is unchanged.",
        }[status]
        if source.source_kind == "website" and status in {"queued", "stale"}:
            safe_message = (
                "This website is stored and excluded from use. If bounded website fetching is disabled in this "
                "environment it will remain queued until an operator enables it; administrator review is still required."
            )
        return CompanyKnowledgeSourceResponse(
            id=source.id,
            source_kind=cast(KnowledgeSourceKind, source.source_kind),
            label=source.label,
            website_url=source.website_url,
            source_text=source.source_text,
            source_filename=source.source_filename,
            source_mime_type=source.source_mime_type,
            extracted_text=source.extracted_text,
            summary_text=source.summary_text,
            character_count=len(source.extracted_text or source.source_text or ""),
            content_fingerprint=source.content_fingerprint,
            processing_status=status,
            failure_code=source.failure_code,
            processing_attempts=source.processing_attempts,
            processed_at=self._as_utc(source.processed_at),
            approved_at=self._as_utc(source.approved_at),
            approved_by_user_id=source.approved_by_user_id,
            stale_at=self._as_utc(source.stale_at),
            created_by_user_id=source.created_by_user_id,
            created_at=self._as_utc(source.created_at),
            updated_at=self._as_utc(source.updated_at),
            safe_message=safe_message,
        )

    def _log_knowledge_source(self, source: CompanyKnowledgeSource) -> None:
        logger.info(
            "company_knowledge_source_added",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "user_id": str(self.tenant.user_id),
                "source_id": str(source.id),
                "source_kind": source.source_kind,
                "processing_status": source.processing_status,
            },
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
