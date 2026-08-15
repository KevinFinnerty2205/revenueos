from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.document_parsing import (
    BoundedDocumentParser,
    DocumentParsingError,
    ParsedDocumentFragment,
)
from revenueos.email_normalization import normalize_plain_text_email
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    Evidence,
    RevenueBrainSourceSnapshot,
    SourceCandidateEvidence,
)
from revenueos.source_evidence_contracts import (
    DocumentCreateRequest,
    DocumentEmailCapabilitiesResponse,
    DocumentSourceOwnership,
    DocumentSourceResponse,
    DocumentType,
    EmailCreateRequest,
    EmailDirection,
    EmailSourceResponse,
    EmailSourceType,
    OpportunityEvidenceItemResponse,
    RevenueBrainSourceSnapshotResponse,
    SourceAnalysisCandidate,
    SourceCandidateLocation,
    SourceCandidateResponse,
    SourceDeleteResponse,
    SourceEvidenceCategory,
    SourceProcessRequest,
    SourceReviewRequest,
    SourceReviewResponse,
)
from revenueos.source_evidence_provider import (
    SourceEvidenceExtractionProvider,
    SourceEvidenceProviderError,
    create_source_evidence_provider,
    execute_source_analysis,
)
from revenueos.source_evidence_repositories import (
    DocumentSourceRecord,
    EmailSourceRecord,
    SourceEvidenceRepository,
)
from revenueos.tenant import TenantContext
from revenueos.visual_storage import (
    VisualGrantSigner,
    VisualStorage,
    VisualStorageError,
    create_visual_storage,
)

logger = logging.getLogger("revenueos.source_evidence")


class SourceEvidenceService:
    """Deliberate document/email ingestion with source-aware, complete human review."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        storage: VisualStorage | None = None,
        provider: SourceEvidenceExtractionProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = SourceEvidenceRepository(session)
        self.beta = BetaService(session, tenant, settings)
        self.storage = storage or create_visual_storage(settings)
        self.provider = provider or create_source_evidence_provider(settings)
        self.grants = VisualGrantSigner(settings.visual_storage_signing_secret.get_secret_value())
        self.parser = BoundedDocumentParser(
            max_pages=settings.private_beta_max_document_pages,
            max_characters=settings.private_beta_max_document_text_characters,
        )

    def capabilities(self) -> DocumentEmailCapabilitiesResponse:
        return DocumentEmailCapabilitiesResponse(
            document_evidence=self.settings.feature_document_evidence_enabled,
            email_evidence=self.settings.feature_email_evidence_enabled,
            supported_document_mime_types=("application/pdf", "text/plain"),
            email_provider_import=False,
            document_provider_import=False,
            safe_message=(
                "Select only evidence you are authorised to process. Gmail, Outlook and drive synchronisation are not connected."
            ),
        )

    async def create_document(self, request: DocumentCreateRequest) -> DocumentSourceResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("documentEvidence")
        content = self._decode_document(request.content_base64)
        if len(content) > self.settings.private_beta_max_document_bytes:
            raise PublicAPIError(
                "document_too_large",
                f"Documents must be {self.settings.private_beta_max_document_bytes:,} bytes or fewer.",
                413,
            )
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != request.checksum_sha256:
            raise PublicAPIError("document_checksum_mismatch", "The document checksum did not match.", 422)
        self._validate_filename_and_mime(request.filename, request.mime_type)
        company_id, opportunity_id, interaction_id = await self._validate_association(
            request.company_id, request.opportunity_id, request.interaction_id
        )
        existing = await self.repository.document_by_idempotency(
            self.tenant.organisation_id, self.tenant.user_id, request.idempotency_key
        )
        if existing is not None:
            if existing.deleted_at is not None:
                raise PublicAPIError(
                    "document_already_deleted",
                    "This document was deleted and cannot be recreated.",
                    409,
                )
            if not self._same_document_request(existing, request, company_id, opportunity_id, interaction_id):
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That document retry key was already used for different metadata.",
                    409,
                )
            return await self._document_response(
                cast(DocumentSourceRecord, await self.repository.get_document(self.tenant.organisation_id, existing.id))
            )
        try:
            self.parser.parse(content, request.mime_type)
        except DocumentParsingError as exc:
            raise PublicAPIError(exc.code, self._safe_parse_message(exc.code), 422) from exc
        duplicate = await self.repository.document_by_checksum(self.tenant.organisation_id, checksum)
        if duplicate is not None:
            raise PublicAPIError(
                "duplicate_document",
                "This document has already been added to the organisation.",
                409,
            )
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        if (
            await self.repository.count_documents_since(self.tenant.organisation_id, today)
            >= self.settings.private_beta_max_document_uploads_per_day
        ):
            raise PublicAPIError(
                "daily_document_upload_limit_exceeded",
                "This organisation has reached today’s document upload limit.",
                429,
            )
        if (
            await self.repository.stored_document_bytes(self.tenant.organisation_id) + len(content)
            > self.settings.private_beta_max_document_bytes_per_organisation
        ):
            raise PublicAPIError(
                "document_storage_limit_exceeded",
                "This organisation has reached its document storage limit.",
                429,
            )
        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        capture_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        extension = ".pdf" if request.mime_type == "application/pdf" else ".txt"
        storage_key = f"{self.tenant.organisation_id}/documents/{document_id.hex}{extension}"
        origin_class, support_class = self._document_provenance(request.source_ownership)
        capture = CaptureSession(
            id=capture_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_type="document_import",
            status="completed",
            started_by_user_id=self.tenant.user_id,
            started_at=now,
            completed_at=now,
        )
        evidence = Evidence(
            id=evidence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=capture_id,
            evidence_type="document",
            origin_class=origin_class,
            support_class=support_class,
            validation_state="unreviewed",
            captured_by_user_id=self.tenant.user_id,
            captured_at=self._as_utc(request.document_at),
            lifecycle_status="received",
            retention_class="inherited",
        )
        document = DocumentSource(
            id=document_id,
            organisation_id=self.tenant.organisation_id,
            company_id=company_id,
            opportunity_id=opportunity_id,
            interaction_id=interaction_id,
            capture_session_id=capture_id,
            source_evidence_id=evidence_id,
            uploaded_by_user_id=self.tenant.user_id,
            document_type=request.document_type,
            source_ownership=request.source_ownership,
            display_filename=self._safe_filename(request.filename, extension),
            storage_key=storage_key,
            mime_type=request.mime_type,
            byte_size=len(content),
            checksum_sha256=checksum,
            document_at=self._as_utc(request.document_at),
            idempotency_key=request.idempotency_key,
            processing_status="received",
            storage_status="available",
            authority_confirmed_at=now,
            external_processing_acknowledged_at=now,
        )
        try:
            await self.storage.write(storage_key, content, request.mime_type)
        except VisualStorageError as exc:
            raise PublicAPIError("document_storage_failure", "The document could not be stored securely.", 503) from exc
        self.session.add_all((capture, evidence))
        try:
            await self.session.flush()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            try:
                await self.storage.delete(storage_key)
            except VisualStorageError:
                logger.warning(
                    "document_orphan_cleanup_failed",
                    extra={"organisation_id": str(self.tenant.organisation_id), "document_id": str(document_id)},
                )
            raise PublicAPIError("persistence_failure", "The document metadata could not be saved.", 500) from exc
        self.session.add(document)
        self._event(
            "document_uploaded",
            document_id,
            {"document_type": request.document_type, "byte_size": len(content)},
        )
        try:
            await self._commit("The document metadata could not be saved.")
        except PublicAPIError:
            try:
                await self.storage.delete(storage_key)
            except VisualStorageError:
                logger.warning(
                    "document_orphan_cleanup_failed",
                    extra={"organisation_id": str(self.tenant.organisation_id), "document_id": str(document_id)},
                )
            raise
        record = await self.repository.get_document(self.tenant.organisation_id, document_id)
        assert record is not None
        return await self._document_response(record)

    async def create_email(self, request: EmailCreateRequest) -> EmailSourceResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("emailEvidence")
        try:
            normalised = normalize_plain_text_email(request.body)
        except ValueError as exc:
            raise PublicAPIError("unsafe_email_content", "The email body contains unsupported content.", 422) from exc
        checksum = self._email_checksum(request)
        company_id, opportunity_id, interaction_id = await self._validate_association(
            request.company_id, request.opportunity_id, request.interaction_id
        )
        existing = await self.repository.email_by_idempotency(
            self.tenant.organisation_id, self.tenant.user_id, request.idempotency_key
        )
        if existing is not None:
            if existing.deleted_at is not None:
                raise PublicAPIError(
                    "email_already_deleted",
                    "This email was deleted and cannot be recreated.",
                    409,
                )
            if not self._same_email_request(existing, request, checksum, company_id, opportunity_id, interaction_id):
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That email retry key was already used for different metadata.",
                    409,
                )
            record = await self.repository.get_email(self.tenant.organisation_id, existing.id)
            assert record is not None
            return await self._email_response(record)
        sender_identity_state = "unknown"
        if request.sender_contact_id is not None:
            contact = await self.repository.get_contact(self.tenant.organisation_id, request.sender_contact_id)
            if contact is None:
                raise PublicAPIError("contact_not_found", "The selected sender Contact was not found.", 404)
            if company_id is not None and contact.company_id != company_id:
                raise PublicAPIError(
                    "contact_company_mismatch",
                    "The selected sender Contact does not belong to the associated account.",
                    422,
                )
            sender_identity_state = "verified_contact"
        origin_class, support_class = self._email_provenance(
            request.source_type, request.direction, sender_identity_state
        )
        duplicate = await self.repository.email_by_checksum(self.tenant.organisation_id, checksum)
        if duplicate is not None:
            raise PublicAPIError("duplicate_email", "This email has already been added.", 409)
        now = datetime.now(UTC)
        email_id = uuid.uuid4()
        capture_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        capture = CaptureSession(
            id=capture_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_type="email_import",
            status="completed",
            started_by_user_id=self.tenant.user_id,
            started_at=now,
            completed_at=now,
        )
        evidence = Evidence(
            id=evidence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            capture_session_id=capture_id,
            evidence_type="email",
            origin_class=origin_class,
            support_class=support_class,
            validation_state="unreviewed",
            captured_by_user_id=self.tenant.user_id,
            captured_at=self._as_utc(request.message_at),
            lifecycle_status="received",
            retention_class="inherited",
        )
        self.session.add_all((capture, evidence))
        try:
            await self.session.flush()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failure", "The email evidence could not be saved.", 500) from exc
        self.session.add(
            EmailSource(
                id=email_id,
                organisation_id=self.tenant.organisation_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                interaction_id=interaction_id,
                capture_session_id=capture_id,
                source_evidence_id=evidence_id,
                submitted_by_user_id=self.tenant.user_id,
                sender_contact_id=request.sender_contact_id,
                source_type=request.source_type,
                direction=request.direction,
                sender_identity_state=sender_identity_state,
                origin_class=origin_class,
                support_class=support_class,
                subject=request.subject,
                body_text=request.body,
                normalized_body_text=normalised.body,
                quote_handling=normalised.quote_handling,
                message_at=self._as_utc(request.message_at),
                content_sha256=checksum,
                idempotency_key=request.idempotency_key,
                processing_status="received",
                authority_confirmed_at=now,
                external_processing_acknowledged_at=now,
            )
        )
        self._event("email_submitted", email_id, {"email_direction": request.direction})
        await self._commit("The email evidence could not be saved.")
        record = await self.repository.get_email(self.tenant.organisation_id, email_id)
        assert record is not None
        return await self._email_response(record)

    async def get_document(self, document_id: UUID) -> DocumentSourceResponse:
        self.beta.require_feature("documentEvidence")
        return await self._document_response(await self._require_document(document_id))

    async def get_email(self, email_id: UUID) -> EmailSourceResponse:
        self.beta.require_feature("emailEvidence")
        return await self._email_response(await self._require_email(email_id))

    async def get_document_content(self, document_id: UUID, token: str) -> tuple[bytes, str, str]:
        self.beta.require_feature("documentEvidence")
        record = await self._require_document(document_id)
        if not self.grants.verify(token, self.tenant.organisation_id, self.tenant.user_id, document_id, "download"):
            raise PublicAPIError("download_grant_invalid", "The document download grant is invalid or expired.", 403)
        if record.document.storage_status != "available":
            raise PublicAPIError("document_unavailable", "The document is not available.", 410)
        try:
            content = await self.storage.read(record.document.storage_key)
        except VisualStorageError as exc:
            raise PublicAPIError("document_storage_failure", "The document could not be retrieved.", 503) from exc
        return content, record.document.mime_type, record.document.display_filename

    async def process_document(self, document_id: UUID, request: SourceProcessRequest) -> DocumentSourceResponse:
        del request.idempotency_key
        self.beta.require_feature("documentEvidence")
        record = await self._require_document(document_id, for_update=True)
        document = record.document
        if document.processing_status in {"review", "completed"}:
            return await self._document_response(record)
        if document.processing_status not in {"received", "failed"}:
            raise PublicAPIError("invalid_document_transition", "This document is not ready for processing.", 409)
        if document.processing_attempts >= self.settings.private_beta_document_processing_retries:
            raise PublicAPIError(
                "document_processing_retry_limit", "This document has reached its processing retry limit.", 429
            )
        await self.beta.reserve_generation()
        if self.provider.provider_name == "openai":
            await self.beta.reserve_provider_request(self.provider.provider_name)
        document.processing_status = "processing"
        document.processing_attempts += 1
        document.failure_code = None
        self._event(
            "document_parsing_started",
            document_id,
            {"document_type": document.document_type, "processing_attempt": document.processing_attempts},
        )
        await self._commit("The document processing state could not be saved.")
        try:
            content = await self.storage.read(document.storage_key)
            parsed = self.parser.parse(content, document.mime_type)
            provider_response = await execute_source_analysis(
                self.provider.analyse_document(
                    source_id=document.id,
                    document_type=document.document_type,
                    source_ownership=document.source_ownership,
                    fragments=parsed.fragments,
                ),
                timeout_seconds=self.settings.evidence_extraction_timeout_seconds,
            )
        except (DocumentParsingError, SourceEvidenceProviderError, VisualStorageError) as exc:
            await self._mark_document_failed(document_id, getattr(exc, "code", "document_processing_failed"))
            raise PublicAPIError(
                "document_processing_failed",
                "The document could not be processed safely. You can retry within the configured limit.",
                503,
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_document(document_id, for_update=True)
        document = record.document
        if document.processing_status != "processing":
            return await self._document_response(record)
        await self.session.execute(
            delete(DocumentFragment).where(
                DocumentFragment.organisation_id == self.tenant.organisation_id,
                DocumentFragment.document_source_id == document_id,
            )
        )
        fragments = self._persist_document_fragments(document, parsed.fragments)
        try:
            self._persist_candidates(
                source_kind="document",
                source=document,
                candidates=list(provider_response.result.candidates),
                fragments=fragments,
            )
        except PublicAPIError as exc:
            await self.session.rollback()
            await self._mark_document_failed(document_id, exc.code)
            raise
        document.page_count = parsed.page_count
        document.extracted_character_count = parsed.character_count
        document.provider_name = provider_response.provider_name
        document.provider_request_id = provider_response.provider_request_id
        document.processing_status = "review"
        document.processed_at = datetime.now(UTC)
        evidence = await self._source_evidence(document.source_evidence_id)
        evidence.lifecycle_status = "available"
        self._event(
            "document_parsing_completed",
            document_id,
            {
                "document_type": document.document_type,
                "page_count": parsed.page_count,
                "candidate_count": len(provider_response.result.candidates),
            },
        )
        await self._commit("The document findings could not be saved.")
        updated = await self.repository.get_document(self.tenant.organisation_id, document_id)
        assert updated is not None
        return await self._document_response(updated)

    async def process_email(self, email_id: UUID, request: SourceProcessRequest) -> EmailSourceResponse:
        del request.idempotency_key
        self.beta.require_feature("emailEvidence")
        record = await self._require_email(email_id, for_update=True)
        email = record.email
        if email.processing_status in {"review", "completed"}:
            return await self._email_response(record)
        if email.processing_status not in {"received", "failed"}:
            raise PublicAPIError("invalid_email_transition", "This email is not ready for processing.", 409)
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        if (
            await self.repository.count_email_analyses_since(self.tenant.organisation_id, today)
            >= self.settings.private_beta_max_email_analyses_per_day
        ):
            raise PublicAPIError(
                "daily_email_analysis_limit_exceeded",
                "This organisation has reached today’s email analysis limit.",
                429,
            )
        if email.processing_attempts >= self.settings.private_beta_email_processing_retries:
            raise PublicAPIError(
                "email_processing_retry_limit", "This email has reached its processing retry limit.", 429
            )
        await self.beta.reserve_generation()
        if self.provider.provider_name == "openai":
            await self.beta.reserve_provider_request(self.provider.provider_name)
        email.processing_status = "processing"
        email.processing_attempts += 1
        email.failure_code = None
        await self._commit("The email processing state could not be saved.")
        try:
            provider_response = await execute_source_analysis(
                self.provider.analyse_email(
                    source_id=email.id,
                    source_type=email.source_type,
                    direction=email.direction,
                    sender_identity_state=email.sender_identity_state,
                    body=email.normalized_body_text,
                ),
                timeout_seconds=self.settings.evidence_extraction_timeout_seconds,
            )
        except SourceEvidenceProviderError as exc:
            await self._mark_email_failed(email_id, exc.code)
            raise PublicAPIError(
                "email_processing_failed",
                "The email could not be processed safely. You can retry within the configured limit.",
                503,
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_email(email_id, for_update=True)
        email = record.email
        if email.processing_status != "processing":
            return await self._email_response(record)
        try:
            self._persist_candidates(
                source_kind="email",
                source=email,
                candidates=list(provider_response.result.candidates),
                fragments=None,
                email_paragraph_count=len(re.split(r"\n\s*\n+", email.normalized_body_text)),
            )
        except PublicAPIError as exc:
            await self.session.rollback()
            await self._mark_email_failed(email_id, exc.code)
            raise
        email.provider_name = provider_response.provider_name
        email.provider_request_id = provider_response.provider_request_id
        email.processing_status = "review"
        email.processed_at = datetime.now(UTC)
        evidence = await self._source_evidence(email.source_evidence_id)
        evidence.lifecycle_status = "available"
        self._event(
            "email_analysis_completed",
            email_id,
            {"email_direction": email.direction, "candidate_count": len(provider_response.result.candidates)},
        )
        await self._commit("The email findings could not be saved.")
        updated = await self.repository.get_email(self.tenant.organisation_id, email_id)
        assert updated is not None
        return await self._email_response(updated)

    async def review_document(self, document_id: UUID, request: SourceReviewRequest) -> SourceReviewResponse:
        self.beta.require_feature("documentEvidence")
        record = await self._require_document(document_id, for_update=True)
        return await self._review_source("document", record.document, request)

    async def review_email(self, email_id: UUID, request: SourceReviewRequest) -> SourceReviewResponse:
        self.beta.require_feature("emailEvidence")
        record = await self._require_email(email_id, for_update=True)
        return await self._review_source("email", record.email, request)

    async def delete_document(self, document_id: UUID) -> SourceDeleteResponse:
        self.beta.require_feature("documentEvidence")
        record = await self._require_document(document_id, include_deleted=True, for_update=True)
        document = record.document
        if document.deleted_at is not None and document.storage_status == "deleted":
            return SourceDeleteResponse(
                source_kind="document", source_id=document_id, deleted=True, retry_required=False
            )
        document.processing_status = "deletion_pending"
        document.storage_status = "deletion_pending"
        await self._commit("The document deletion state could not be saved.")
        try:
            await self.storage.delete(document.storage_key)
        except VisualStorageError:
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            record = await self._require_document(document_id, include_deleted=True, for_update=True)
            record.document.storage_status = "delete_failed"
            record.document.failure_code = "document_storage_delete_failed"
            await self._commit("The document deletion failure could not be saved.")
            return SourceDeleteResponse(
                source_kind="document", source_id=document_id, deleted=False, retry_required=True
            )
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_document(document_id, include_deleted=True, for_update=True)
        await self._remove_source_lineage("document", record.document)
        now = datetime.now(UTC)
        record.document.processing_status = "deleted"
        record.document.storage_status = "deleted"
        record.document.provider_request_id = None
        record.document.failure_code = None
        record.document.deleted_at = now
        self._event("document_deleted", document_id, {"document_type": record.document.document_type})
        await self._commit("The document deletion could not be completed.")
        return SourceDeleteResponse(source_kind="document", source_id=document_id, deleted=True, retry_required=False)

    async def delete_email(self, email_id: UUID) -> SourceDeleteResponse:
        self.beta.require_feature("emailEvidence")
        record = await self._require_email(email_id, include_deleted=True, for_update=True)
        if record.email.deleted_at is not None:
            return SourceDeleteResponse(source_kind="email", source_id=email_id, deleted=True, retry_required=False)
        await self._remove_source_lineage("email", record.email)
        record.email.subject = None
        record.email.body_text = "[deleted]"
        record.email.normalized_body_text = "[deleted]"
        record.email.provider_request_id = None
        record.email.failure_code = None
        record.email.processing_status = "deleted"
        record.email.deleted_at = datetime.now(UTC)
        self._event("email_deleted", email_id, {"email_direction": record.email.direction})
        await self._commit("The email deletion could not be completed.")
        return SourceDeleteResponse(source_kind="email", source_id=email_id, deleted=True, retry_required=False)

    async def list_opportunity_evidence(self, opportunity_id: UUID) -> list[OpportunityEvidenceItemResponse]:
        if await self.repository.get_opportunity(self.tenant.organisation_id, opportunity_id) is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        snapshots = await self.repository.list_snapshots_for_opportunity(self.tenant.organisation_id, opportunity_id)
        return [item for snapshot in snapshots for item in self._snapshot_items(snapshot)]

    async def list_company_brain(self, company_id: UUID) -> list[RevenueBrainSourceSnapshotResponse]:
        if await self.repository.get_company(self.tenant.organisation_id, company_id) is None:
            raise PublicAPIError("company_not_found", "The requested account was not found.", 404)
        snapshots = await self.repository.list_snapshots_for_company(self.tenant.organisation_id, company_id)
        return [self._brain_response(snapshot) for snapshot in snapshots]

    async def _review_source(
        self,
        source_kind: Literal["document", "email"],
        source: DocumentSource | EmailSource,
        request: SourceReviewRequest,
    ) -> SourceReviewResponse:
        if source.processing_status == "completed":
            candidates = await self.repository.get_candidates_for_review(
                self.tenant.organisation_id,
                document_id=source.id if source_kind == "document" else None,
                email_id=source.id if source_kind == "email" else None,
            )
            existing_snapshot_id = await self._snapshot_id(source_kind, source.id)
            return self._review_response(source_kind, source, candidates, existing_snapshot_id)
        if source.processing_status != "review":
            raise PublicAPIError("review_not_ready", "Process this source before reviewing its findings.", 409)
        candidates = await self.repository.get_candidates_for_review(
            self.tenant.organisation_id,
            document_id=source.id if source_kind == "document" else None,
            email_id=source.id if source_kind == "email" else None,
        )
        pending = [candidate for candidate in candidates if candidate.review_state == "pending"]
        decisions = {decision.candidate_id: decision for decision in request.decisions}
        if set(decisions) != {candidate.id for candidate in pending}:
            raise PublicAPIError(
                "incomplete_review",
                "Review every finding before finishing this source.",
                422,
            )
        accepted: list[SourceCandidateEvidence] = []
        now = datetime.now(UTC)
        for candidate in pending:
            decision = decisions[candidate.id]
            if decision.decision == "reject":
                candidate.review_state = "rejected"
                candidate.validation_state = "rejected"
                candidate.reviewed_by_user_id = self.tenant.user_id
                candidate.reviewed_at = now
                continue
            if decision.supersedes_candidate_id is not None:
                prior = await self.repository.accepted_candidate(
                    self.tenant.organisation_id, decision.supersedes_candidate_id
                )
                if prior is None or prior.evidence_category != candidate.evidence_category:
                    raise PublicAPIError(
                        "invalid_supersession",
                        "Superseded evidence must be an accepted item in the same category.",
                        422,
                    )
                candidate.supersedes_candidate_id = prior.id
                candidate.conflict_state = "supersedes"
            candidate.statement = decision.statement or candidate.statement
            candidate.review_state = "accepted"
            candidate.validation_state = "verified"
            candidate.reviewed_by_user_id = self.tenant.user_id
            candidate.reviewed_at = now
            accepted_evidence = Evidence(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=source.interaction_id,
                capture_session_id=source.capture_session_id,
                evidence_type=source_kind,
                origin_class=candidate.origin_class,
                support_class=candidate.support_class,
                validation_state="verified",
                captured_by_user_id=self.tenant.user_id,
                captured_at=source.document_at if isinstance(source, DocumentSource) else source.message_at,
                lifecycle_status="available",
                retention_class="inherited",
            )
            self.session.add(accepted_evidence)
            candidate.accepted_evidence_id = accepted_evidence.id
            accepted.append(candidate)
        source.processing_status = "completed"
        source_evidence = await self._source_evidence(source.source_evidence_id)
        source_evidence.validation_state = "verified"
        source_evidence.lifecycle_status = "available"
        snapshot_id: UUID | None = None
        if accepted:
            snapshot_id = await self._create_snapshot(source_kind, source, accepted)
        self._event(
            "source_evidence_review_completed",
            source.id,
            {
                "source_kind": source_kind,
                "evidence_accepted_count": len(accepted),
                "evidence_rejected_count": len(pending) - len(accepted),
            },
        )
        await self._commit("The evidence review could not be saved.")
        reviewed = await self.repository.get_candidates_for_review(
            self.tenant.organisation_id,
            document_id=source.id if source_kind == "document" else None,
            email_id=source.id if source_kind == "email" else None,
        )
        return self._review_response(source_kind, source, reviewed, snapshot_id)

    async def _create_snapshot(
        self,
        source_kind: Literal["document", "email"],
        source: DocumentSource | EmailSource,
        accepted: list[SourceCandidateEvidence],
    ) -> UUID:
        snapshot_id = uuid.uuid4()
        source_label = self._source_label(source_kind, source)
        source_origin = source.source_ownership if isinstance(source, DocumentSource) else source.source_type
        source_type = source.document_type if isinstance(source, DocumentSource) else source.source_type
        occurred_at = source.document_at if isinstance(source, DocumentSource) else source.message_at
        items: list[dict[str, object]] = []
        accepted_ids: list[str] = []
        for candidate in accepted:
            assert candidate.accepted_evidence_id is not None
            accepted_ids.append(str(candidate.accepted_evidence_id))
            items.append(
                {
                    "candidateId": str(candidate.id),
                    "evidenceId": str(candidate.accepted_evidence_id),
                    "category": candidate.evidence_category,
                    "statement": candidate.statement,
                    "sourceKind": source_kind,
                    "sourceId": str(source.id),
                    "sourceType": source_type,
                    "sourceLabel": source_label,
                    "sourceOrigin": source_origin,
                    "originClass": candidate.origin_class,
                    "supportClass": candidate.support_class,
                    "conflictState": candidate.conflict_state,
                    "location": candidate.source_location_json,
                }
            )
        content: dict[str, object] = {
            "schemaVersion": 1,
            "sourceKind": source_kind,
            "sourceId": str(source.id),
            "sourceType": source_type,
            "sourceLabel": source_label,
            "sourceOrigin": source_origin,
            "occurredAt": self._as_utc(occurred_at).isoformat(),
            "items": items,
        }
        self.session.add(
            RevenueBrainSourceSnapshot(
                id=snapshot_id,
                organisation_id=self.tenant.organisation_id,
                company_id=source.company_id,
                opportunity_id=source.opportunity_id,
                interaction_id=source.interaction_id,
                source_kind=source_kind,
                document_source_id=source.id if source_kind == "document" else None,
                email_source_id=source.id if source_kind == "email" else None,
                source_evidence_id=source.source_evidence_id,
                source_evidence_ids=accepted_ids,
                content_json=content,
                schema_version=1,
                version=await self.repository.next_snapshot_version(
                    self.tenant.organisation_id, source.source_evidence_id
                ),
            )
        )
        return snapshot_id

    def _persist_document_fragments(
        self, document: DocumentSource, parsed: tuple[ParsedDocumentFragment, ...]
    ) -> dict[int, DocumentFragment]:
        persisted: dict[int, DocumentFragment] = {}
        for fragment in parsed:
            record = DocumentFragment(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                document_source_id=document.id,
                source_evidence_id=document.source_evidence_id,
                page_number=fragment.page_number,
                section=fragment.section,
                paragraph_index=fragment.paragraph_index,
                content_text=fragment.text,
            )
            self.session.add(record)
            persisted[fragment.paragraph_index] = record
        return persisted

    def _persist_candidates(
        self,
        *,
        source_kind: Literal["document", "email"],
        source: DocumentSource | EmailSource,
        candidates: list[SourceAnalysisCandidate],
        fragments: dict[int, DocumentFragment] | None,
        email_paragraph_count: int | None = None,
    ) -> None:
        origin_class, support_class = (
            self._document_provenance(source.source_ownership)
            if isinstance(source, DocumentSource)
            else (source.origin_class, source.support_class)
        )
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            fingerprint = self._fingerprint(candidate.statement)
            key = (candidate.category, fingerprint)
            if key in seen:
                continue
            seen.add(key)
            fragment_id: UUID | None = None
            if source_kind == "document":
                assert fragments is not None
                paragraph_index = candidate.source_location.paragraph_index
                fragment = fragments.get(paragraph_index) if paragraph_index is not None else None
                if fragment is None:
                    raise PublicAPIError(
                        "source_location_invalid", "A document finding did not cite a valid paragraph.", 502
                    )
                if candidate.source_location.page_number != fragment.page_number:
                    raise PublicAPIError(
                        "source_location_invalid", "A document finding did not cite a valid page.", 502
                    )
                fragment_id = fragment.id
            else:
                paragraph_index = candidate.source_location.paragraph_index
                if (
                    email_paragraph_count is None
                    or paragraph_index is None
                    or not 0 <= paragraph_index < email_paragraph_count
                    or candidate.source_location.page_number is not None
                ):
                    raise PublicAPIError(
                        "source_location_invalid", "An email finding did not cite a valid message paragraph.", 502
                    )
            self.session.add(
                SourceCandidateEvidence(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    source_kind=source_kind,
                    document_source_id=source.id if source_kind == "document" else None,
                    email_source_id=source.id if source_kind == "email" else None,
                    source_evidence_id=source.source_evidence_id,
                    document_fragment_id=fragment_id,
                    evidence_category=candidate.category,
                    statement=candidate.statement,
                    original_statement=candidate.statement,
                    statement_fingerprint=fingerprint,
                    interpretation_origin="ai_inferred",
                    origin_class=origin_class,
                    support_class=support_class,
                    source_location_json=candidate.source_location.model_dump(mode="json", by_alias=True),
                    validation_state="unreviewed",
                    review_state="pending",
                    conflict_state="not_assessed",
                )
            )

    async def _validate_association(
        self, company_id: UUID | None, opportunity_id: UUID | None, interaction_id: UUID | None
    ) -> tuple[UUID | None, UUID | None, UUID | None]:
        opportunity = None
        interaction = None
        if (
            company_id is not None
            and await self.repository.get_company(self.tenant.organisation_id, company_id) is None
        ):
            raise PublicAPIError("company_not_found", "The associated account was not found.", 404)
        if opportunity_id is not None:
            opportunity = await self.repository.get_opportunity(self.tenant.organisation_id, opportunity_id)
            if opportunity is None:
                raise PublicAPIError("opportunity_not_found", "The associated opportunity was not found.", 404)
            if company_id is not None and opportunity.company_id != company_id:
                raise PublicAPIError(
                    "association_mismatch", "The opportunity does not belong to the selected account.", 422
                )
            company_id = company_id or opportunity.company_id
        if interaction_id is not None:
            interaction = await self.repository.get_interaction(self.tenant.organisation_id, interaction_id)
            if interaction is None:
                raise PublicAPIError("interaction_not_found", "The associated interaction was not found.", 404)
            if opportunity_id is not None and interaction.opportunity_id != opportunity_id:
                raise PublicAPIError(
                    "association_mismatch", "The interaction does not belong to the selected opportunity.", 422
                )
            if company_id is not None and interaction.company_id not in {None, company_id}:
                raise PublicAPIError(
                    "association_mismatch", "The interaction does not belong to the selected account.", 422
                )
            opportunity_id = opportunity_id or interaction.opportunity_id
            company_id = company_id or interaction.company_id
            if company_id is None and opportunity_id is not None:
                linked = await self.repository.get_opportunity(self.tenant.organisation_id, opportunity_id)
                company_id = linked.company_id if linked is not None else None
        return company_id, opportunity_id, interaction_id

    async def _remove_source_lineage(
        self, source_kind: Literal["document", "email"], source: DocumentSource | EmailSource
    ) -> None:
        candidates = await self.repository.get_candidates_for_review(
            self.tenant.organisation_id,
            document_id=source.id if source_kind == "document" else None,
            email_id=source.id if source_kind == "email" else None,
        )
        accepted_ids = [candidate.accepted_evidence_id for candidate in candidates if candidate.accepted_evidence_id]
        candidate_ids = [candidate.id for candidate in candidates]
        if candidate_ids:
            await self.session.execute(
                update(SourceCandidateEvidence)
                .where(
                    SourceCandidateEvidence.organisation_id == self.tenant.organisation_id,
                    SourceCandidateEvidence.supersedes_candidate_id.in_(candidate_ids),
                )
                .values(supersedes_candidate_id=None)
            )
        await self.session.execute(
            delete(RevenueBrainSourceSnapshot).where(
                RevenueBrainSourceSnapshot.organisation_id == self.tenant.organisation_id,
                (
                    RevenueBrainSourceSnapshot.document_source_id == source.id
                    if source_kind == "document"
                    else RevenueBrainSourceSnapshot.email_source_id == source.id
                ),
            )
        )
        await self.session.execute(
            delete(SourceCandidateEvidence).where(
                SourceCandidateEvidence.organisation_id == self.tenant.organisation_id,
                (
                    SourceCandidateEvidence.document_source_id == source.id
                    if source_kind == "document"
                    else SourceCandidateEvidence.email_source_id == source.id
                ),
            )
        )
        if source_kind == "document":
            await self.session.execute(
                delete(DocumentFragment).where(
                    DocumentFragment.organisation_id == self.tenant.organisation_id,
                    DocumentFragment.document_source_id == source.id,
                )
            )
        for evidence_id in accepted_ids:
            evidence = await self._source_evidence(evidence_id)
            evidence.lifecycle_status = "deleted"
            evidence.deleted_at = datetime.now(UTC)
        source_evidence = await self._source_evidence(source.source_evidence_id)
        source_evidence.lifecycle_status = "deleted"
        source_evidence.deleted_at = datetime.now(UTC)

    async def _mark_document_failed(self, document_id: UUID, code: str) -> None:
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_document(document_id, for_update=True)
        record.document.processing_status = "failed"
        record.document.failure_code = code
        self._event("document_processing_failed", document_id, {"safe_error_code": code})
        await self._commit("The document failure state could not be saved.")

    async def _mark_email_failed(self, email_id: UUID, code: str) -> None:
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_email(email_id, for_update=True)
        record.email.processing_status = "failed"
        record.email.failure_code = code
        self._event("email_processing_failed", email_id, {"safe_error_code": code})
        await self._commit("The email failure state could not be saved.")

    async def _require_document(
        self, document_id: UUID, *, include_deleted: bool = False, for_update: bool = False
    ) -> DocumentSourceRecord:
        record = await self.repository.get_document(
            self.tenant.organisation_id,
            document_id,
            include_deleted=include_deleted,
            for_update=for_update,
        )
        if record is None:
            raise PublicAPIError("document_not_found", "The requested document was not found.", 404)
        return record

    async def _require_email(
        self, email_id: UUID, *, include_deleted: bool = False, for_update: bool = False
    ) -> EmailSourceRecord:
        record = await self.repository.get_email(
            self.tenant.organisation_id,
            email_id,
            include_deleted=include_deleted,
            for_update=for_update,
        )
        if record is None:
            raise PublicAPIError("email_not_found", "The requested email was not found.", 404)
        return record

    async def _source_evidence(self, evidence_id: UUID) -> Evidence:
        evidence = await self.session.scalar(
            select(Evidence).where(
                Evidence.organisation_id == self.tenant.organisation_id,
                Evidence.id == evidence_id,
            )
        )
        assert evidence is not None
        return evidence

    async def _snapshot_id(self, source_kind: str, source_id: UUID) -> UUID | None:
        statement = select(RevenueBrainSourceSnapshot.id).where(
            RevenueBrainSourceSnapshot.organisation_id == self.tenant.organisation_id,
            (
                RevenueBrainSourceSnapshot.document_source_id == source_id
                if source_kind == "document"
                else RevenueBrainSourceSnapshot.email_source_id == source_id
            ),
        )
        return cast(
            UUID | None,
            await self.session.scalar(statement.order_by(RevenueBrainSourceSnapshot.version.desc()).limit(1)),
        )

    async def _document_response(self, record: DocumentSourceRecord) -> DocumentSourceResponse:
        document = record.document
        await self.session.refresh(document)
        download_url: str | None = None
        if document.storage_status == "available" and document.deleted_at is None:
            expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.visual_signed_url_ttl_seconds)
            download_url = self.storage.download_url(document.storage_key, expires_at)
            if download_url is None:
                token = self.grants.issue(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    document.id,
                    "download",
                    expires_at,
                )
                download_url = f"/api/v1/evidence/documents/{document.id}/content?token={token}"
        return DocumentSourceResponse(
            id=document.id,
            source_evidence_id=document.source_evidence_id,
            company_id=document.company_id,
            opportunity_id=document.opportunity_id,
            interaction_id=document.interaction_id,
            document_type=cast(DocumentType, document.document_type),
            source_ownership=cast(DocumentSourceOwnership, document.source_ownership),
            filename=document.display_filename,
            mime_type=cast(Literal["application/pdf", "text/plain"], document.mime_type),
            byte_size=document.byte_size,
            checksum_sha256=document.checksum_sha256,
            document_at=self._as_utc(document.document_at),
            processing_status=cast(
                Literal["received", "processing", "review", "completed", "failed", "deletion_pending", "deleted"],
                document.processing_status,
            ),
            storage_status=cast(
                Literal["available", "missing", "deletion_pending", "delete_failed", "deleted"],
                document.storage_status,
            ),
            page_count=document.page_count,
            extracted_character_count=document.extracted_character_count,
            failure_code=document.failure_code,
            candidates=[self._candidate_response(candidate, document) for candidate in record.candidates],
            download_url=download_url,
            revenue_brain_snapshot_id=record.snapshot_id,
            created_at=self._as_utc(document.created_at),
            updated_at=self._as_utc(document.updated_at),
        )

    async def _email_response(self, record: EmailSourceRecord) -> EmailSourceResponse:
        email = record.email
        await self.session.refresh(email)
        return EmailSourceResponse(
            id=email.id,
            source_evidence_id=email.source_evidence_id,
            company_id=email.company_id,
            opportunity_id=email.opportunity_id,
            interaction_id=email.interaction_id,
            source_type=cast(EmailSourceType, email.source_type),
            direction=cast(EmailDirection, email.direction),
            sender_contact_id=email.sender_contact_id,
            sender_identity_state=cast(Literal["verified_contact", "unknown"], email.sender_identity_state),
            subject_present=email.subject is not None,
            message_at=self._as_utc(email.message_at),
            quote_handling=cast(Literal["none", "stripped", "ambiguous"], email.quote_handling),
            processing_status=cast(
                Literal["received", "processing", "review", "completed", "failed", "deleted"],
                email.processing_status,
            ),
            failure_code=email.failure_code,
            candidates=[self._candidate_response(candidate, email) for candidate in record.candidates],
            revenue_brain_snapshot_id=record.snapshot_id,
            created_at=self._as_utc(email.created_at),
            updated_at=self._as_utc(email.updated_at),
        )

    def _candidate_response(
        self, candidate: SourceCandidateEvidence, source: DocumentSource | EmailSource
    ) -> SourceCandidateResponse:
        source_kind = cast(Literal["document", "email"], candidate.source_kind)
        return SourceCandidateResponse(
            id=candidate.id,
            category=cast(SourceEvidenceCategory, candidate.evidence_category),
            statement=candidate.statement,
            original_statement=candidate.original_statement,
            source_kind=source_kind,
            source_id=source.id,
            source_evidence_id=candidate.source_evidence_id,
            source_label=self._source_label(source_kind, source),
            source_origin=source.source_ownership if isinstance(source, DocumentSource) else source.source_type,
            interpretation_origin="ai_inferred",
            origin_class=cast(
                Literal["customer_direct", "seller_prepared", "salesperson_reported", "imported_external"],
                candidate.origin_class,
            ),
            support_class=cast(Literal["direct", "reported", "context"], candidate.support_class),
            source_location=SourceCandidateLocation.model_validate(candidate.source_location_json),
            validation_state=cast(Literal["unreviewed", "verified", "rejected"], candidate.validation_state),
            review_state=cast(Literal["pending", "accepted", "rejected"], candidate.review_state),
            conflict_state=cast(
                Literal["not_assessed", "conflicting", "supersedes", "superseded"], candidate.conflict_state
            ),
            supersedes_candidate_id=candidate.supersedes_candidate_id,
            accepted_evidence_id=candidate.accepted_evidence_id,
            edited=candidate.statement != candidate.original_statement,
        )

    def _review_response(
        self,
        source_kind: Literal["document", "email"],
        source: DocumentSource | EmailSource,
        candidates: list[SourceCandidateEvidence],
        snapshot_id: UUID | None,
    ) -> SourceReviewResponse:
        return SourceReviewResponse(
            source_kind=source_kind,
            source_id=source.id,
            accepted_count=sum(item.review_state == "accepted" for item in candidates),
            rejected_count=sum(item.review_state == "rejected" for item in candidates),
            opportunity_updated=any(item.review_state == "accepted" for item in candidates),
            revenue_brain_updated=snapshot_id is not None,
            revenue_brain_snapshot_id=snapshot_id,
            candidates=[self._candidate_response(item, source) for item in candidates],
        )

    def _snapshot_items(self, snapshot: RevenueBrainSourceSnapshot) -> list[OpportunityEvidenceItemResponse]:
        raw_items = snapshot.content_json.get("items")
        occurred_at = snapshot.content_json.get("occurredAt")
        if not isinstance(raw_items, list) or not isinstance(occurred_at, str):
            return []
        parsed: list[OpportunityEvidenceItemResponse] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                parsed.append(
                    OpportunityEvidenceItemResponse.model_validate(
                        {
                            "snapshotId": snapshot.id,
                            "sourceKind": raw.get("sourceKind"),
                            "sourceId": raw.get("sourceId"),
                            "sourceType": raw.get("sourceType"),
                            "sourceLabel": raw.get("sourceLabel"),
                            "sourceOrigin": raw.get("sourceOrigin"),
                            "occurredAt": occurred_at,
                            "category": raw.get("category"),
                            "statement": raw.get("statement"),
                            "evidenceId": raw.get("evidenceId"),
                            "location": raw.get("location"),
                            "originClass": raw.get("originClass"),
                            "supportClass": raw.get("supportClass"),
                            "conflictState": raw.get("conflictState"),
                        }
                    )
                )
            except (ValueError, TypeError):
                continue
        return parsed

    def _brain_response(self, snapshot: RevenueBrainSourceSnapshot) -> RevenueBrainSourceSnapshotResponse:
        content = snapshot.content_json
        occurred_at = content.get("occurredAt")
        if not isinstance(occurred_at, str):
            occurred_at = snapshot.created_at.isoformat()
        return RevenueBrainSourceSnapshotResponse(
            id=snapshot.id,
            source_kind=cast(Literal["document", "email"], snapshot.source_kind),
            source_id=UUID(str(content["sourceId"])),
            opportunity_id=snapshot.opportunity_id,
            interaction_id=snapshot.interaction_id,
            source_type=str(content["sourceType"]),
            source_label=str(content["sourceLabel"]),
            source_origin=str(content["sourceOrigin"]),
            occurred_at=datetime.fromisoformat(occurred_at),
            created_at=self._as_utc(snapshot.created_at),
            items=self._snapshot_items(snapshot),
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            logger.warning(
                "source_evidence_persistence_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "error_code": "source_evidence_persistence_failed",
                },
            )
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
    def _document_provenance(source_ownership: str) -> tuple[str, str]:
        if source_ownership == "customer_provided":
            return "customer_direct", "direct"
        if source_ownership == "salesperson_provided":
            return "seller_prepared", "context"
        if source_ownership == "jointly_created":
            return "imported_external", "reported"
        return "imported_external", "context"

    @staticmethod
    def _email_provenance(source_type: str, direction: str, sender_identity_state: str) -> tuple[str, str]:
        if source_type == "customer_sent" and direction == "inbound" and sender_identity_state == "verified_contact":
            return "customer_direct", "direct"
        if direction in {"outbound", "internal"} or source_type in {"salesperson_sent", "internal_forward"}:
            return "salesperson_reported", "context"
        return "imported_external", "reported"

    @staticmethod
    def _source_label(source_kind: str, source: DocumentSource | EmailSource) -> str:
        if source_kind == "document":
            ownership = cast(DocumentSource, source).source_ownership
            return {
                "customer_provided": "Customer-provided document",
                "salesperson_provided": "Seller-provided document",
                "jointly_created": "Jointly created document",
                "externally_generated": "Externally generated document",
                "system_imported": "System-imported document",
                "unknown": "Document with unknown origin",
            }.get(ownership, "Document evidence")
        email = cast(EmailSource, source)
        if email.origin_class == "customer_direct":
            return "Verified inbound customer email"
        if email.direction == "outbound":
            return "Outbound salesperson email"
        if email.direction == "internal":
            return "Internal email observation"
        return "Manually supplied email"

    @staticmethod
    def _safe_filename(value: str, extension: str) -> str:
        basename = Path(value.replace("\\", "/")).name
        stem = Path(basename).stem
        safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem).strip(" .-_")[:120] or "document-evidence"
        return f"{safe_stem}{extension}"

    @staticmethod
    def _validate_filename_and_mime(filename: str, mime_type: str) -> None:
        extension = Path(filename.replace("\\", "/")).suffix.casefold()
        expected = {"application/pdf": ".pdf", "text/plain": ".txt"}[mime_type]
        if extension != expected:
            raise PublicAPIError(
                "document_type_mismatch", "The file extension does not match the selected document type.", 422
            )

    def _decode_document(self, content_base64: str) -> bytes:
        max_encoded = ((self.settings.private_beta_max_document_bytes + 2) // 3) * 4 + 8
        if len(content_base64) > max_encoded:
            raise PublicAPIError("document_too_large", "The encoded document exceeds the upload limit.", 413)
        try:
            return base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PublicAPIError("invalid_document_encoding", "The document encoding was invalid.", 422) from exc

    @staticmethod
    def _safe_parse_message(code: str) -> str:
        return {
            "unsafe_document": "The document contains unsupported active or unsafe content.",
            "password_protected_document": "Password-protected documents are not supported.",
            "document_limit_exceeded": "The document exceeds the configured page or text limit.",
            "unsupported_document": "Only PDF and UTF-8 TXT documents are supported.",
        }.get(code, "The document was malformed or could not be parsed safely.")

    @staticmethod
    def _fingerprint(statement: str) -> str:
        return hashlib.sha256(" ".join(statement.casefold().split()).encode("utf-8")).hexdigest()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _same_document_request(
        document: DocumentSource,
        request: DocumentCreateRequest,
        company_id: UUID | None,
        opportunity_id: UUID | None,
        interaction_id: UUID | None,
    ) -> bool:
        extension = ".pdf" if request.mime_type == "application/pdf" else ".txt"
        return (
            document.document_type == request.document_type
            and document.source_ownership == request.source_ownership
            and document.checksum_sha256 == request.checksum_sha256
            and document.display_filename == SourceEvidenceService._safe_filename(request.filename, extension)
            and document.mime_type == request.mime_type
            and SourceEvidenceService._as_utc(document.document_at)
            == SourceEvidenceService._as_utc(request.document_at)
            and document.company_id == company_id
            and document.opportunity_id == opportunity_id
            and document.interaction_id == interaction_id
        )

    @classmethod
    def _same_email_request(
        cls,
        email: EmailSource,
        request: EmailCreateRequest,
        checksum: str,
        company_id: UUID | None,
        opportunity_id: UUID | None,
        interaction_id: UUID | None,
    ) -> bool:
        return (
            email.source_type == request.source_type
            and email.direction == request.direction
            and email.content_sha256 == checksum
            and cls._as_utc(email.message_at) == cls._as_utc(request.message_at)
            and email.company_id == company_id
            and email.opportunity_id == opportunity_id
            and email.interaction_id == interaction_id
            and email.sender_contact_id == request.sender_contact_id
        )

    @classmethod
    def _email_checksum(cls, request: EmailCreateRequest) -> str:
        fingerprint_payload = "\n".join(
            (
                request.source_type,
                request.direction,
                request.subject or "",
                cls._as_utc(request.message_at).isoformat(),
                request.body,
            )
        )
        return hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
