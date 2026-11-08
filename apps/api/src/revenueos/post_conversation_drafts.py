from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from revenueos.automatic_draft_authority import (
    automatic_draft_job_origin_audit_is_valid,
    automatic_draft_processing_authority_is_current,
    cancel_automatic_draft_generation,
)
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_private_user_database_context, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.intelligence_contracts import (
    ActionItemsContentResponse,
    DecisionsContentResponse,
    ExecutiveSummaryContentResponse,
    FollowUpEmailContentResponse,
    MeetingIntelligenceResponse,
    OpenQuestionsContentResponse,
)
from revenueos.intelligence_workspace import MeetingIntelligenceService
from revenueos.interaction_contracts import CONVERSATION_DRAFT_MAX_CHARACTERS
from revenueos.methodology_contracts import MethodologyProjectionContent
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.models import (
    CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT,
    AIJob,
    ConversationDraftGeneration,
    ConversationUserWorkspace,
    Evidence,
    Interaction,
    OrganisationMembership,
    RecordingSession,
    Transcript,
    TranscriptVersion,
    User,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.post_conversation_drafts")
DISCOVERY_LIMIT = 1000
EVENT_INTERACTION_TYPES = frozenset({"conference_interaction", "trade_show_interaction"})
PRIVATE_DRAFT_SCHEMA_VERSION = 1
SUPPORTED_PRIVATE_DRAFT_SCHEMA_VERSIONS = frozenset({1})
PRIVATE_PERSONAL_NOTES_SECTION_LABEL = "Personal notes (private, verbatim)"
PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS = 20_000


@dataclass(frozen=True, slots=True)
class DraftOwnerScope:
    organisation_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class DraftGenerationClaim:
    organisation_id: UUID
    user_id: UUID
    role: str
    generation_id: UUID
    interaction_id: UUID
    meeting_id: UUID
    transcript_version_id: UUID
    transcript_version: int
    opportunity_id: UUID | None
    interaction_type: str
    event_id: UUID | None
    worker_id: str
    attempt_count: int
    orchestrate: bool


def private_draft_fingerprint(enhanced_notes: str, follow_up_draft: str) -> str:
    digest = hashlib.sha256()
    digest.update(enhanced_notes.encode("utf-8"))
    digest.update(b"\0")
    digest.update(follow_up_draft.encode("utf-8"))
    return digest.hexdigest()


def personal_notes_fingerprint(live_notes: str | None) -> str | None:
    if live_notes is None or not live_notes.strip():
        return None
    return hashlib.sha256(live_notes.encode("utf-8")).hexdigest()


def eligible_personal_notes_snapshot(live_notes: str | None) -> str | None:
    if live_notes is None or not live_notes.strip() or len(live_notes) > PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS:
        return None
    return live_notes


def draft_input_fingerprint(
    source_fingerprint: str,
    source_live_notes_fingerprint: str | None,
    draft_schema_version: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_fingerprint.encode("ascii"))
    digest.update(b"\0")
    digest.update((source_live_notes_fingerprint or "none").encode("ascii"))
    digest.update(b"\0")
    digest.update(str(draft_schema_version).encode("ascii"))
    return digest.hexdigest()


class PostConversationDraftWorkerService:
    """Materialise final transcript intelligence into an owner-private draft.

    The service orchestrates the existing Meeting Intelligence jobs and stores a
    distinct generation row for every final transcript version. It never sends
    a follow-up and never replaces workspace content that a user has edited.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run_once(self, worker_id: str) -> bool:
        if not self._settings.feature_auto_generate_intelligence_after_transcription:
            return False
        processed = False
        for scope in await self.discover_eligible_scopes():
            created = await self.ensure_final_generations(scope)
            claim = await self.claim_next(scope, worker_id)
            processed = processed or created > 0 or claim is not None
            if claim is not None:
                await self.process(claim)
        return processed

    async def discover_eligible_scopes(self) -> list[DraftOwnerScope]:
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                rows = await session.execute(
                    text(
                        "SELECT organisation_id, user_id "
                        "FROM public.revenueos_post_conversation_draft_worker_scopes(:result_limit)"
                    ),
                    {"result_limit": DISCOVERY_LIMIT},
                )
                return [DraftOwnerScope(UUID(str(row.organisation_id)), UUID(str(row.user_id))) for row in rows]

            final_rows = await session.execute(self._final_source_scope_statement())
            active_rows = await session.execute(
                select(
                    ConversationDraftGeneration.organisation_id,
                    ConversationDraftGeneration.user_id,
                ).where(ConversationDraftGeneration.status.in_(("pending", "processing")))
            )
            unique = {
                (UUID(str(organisation_id)), UUID(str(user_id)))
                for organisation_id, user_id in (*final_rows.all(), *active_rows.all())
            }
            return [
                DraftOwnerScope(*values) for values in sorted(unique, key=lambda item: (str(item[0]), str(item[1])))
            ][:DISCOVERY_LIMIT]

    async def ensure_final_generations(self, scope: DraftOwnerScope) -> int:
        created = 0
        async with self._session_factory() as session, session.begin():
            await self._set_private_context(session, scope)
            recording_lineage_id = self._recording_lineage_id_expression()
            evidence_lineage_id = self._evidence_lineage_id_expression()
            owner = self._owner_expression()
            statement = (
                select(
                    TranscriptVersion,
                    recording_lineage_id.label("source_recording_session_id"),
                    evidence_lineage_id.label("source_evidence_id"),
                )
                .join(
                    Transcript,
                    (Transcript.organisation_id == TranscriptVersion.organisation_id)
                    & (Transcript.id == TranscriptVersion.transcript_id)
                    & (Transcript.version == TranscriptVersion.version),
                )
                .join(
                    Interaction,
                    (Interaction.organisation_id == TranscriptVersion.organisation_id)
                    & (Interaction.id == TranscriptVersion.interaction_id),
                )
                .outerjoin(
                    RecordingSession,
                    (RecordingSession.organisation_id == TranscriptVersion.organisation_id)
                    & (RecordingSession.id == recording_lineage_id),
                )
                .outerjoin(
                    Evidence,
                    (Evidence.organisation_id == TranscriptVersion.organisation_id)
                    & (Evidence.id == evidence_lineage_id),
                )
                .where(
                    TranscriptVersion.organisation_id == scope.organisation_id,
                    owner == scope.user_id,
                    TranscriptVersion.status == "final",
                    TranscriptVersion.deleted_at.is_(None),
                    TranscriptVersion.meeting_id.is_not(None),
                    Transcript.deleted_at.is_(None),
                    Interaction.lifecycle_status == "completed",
                    Interaction.deleted_at.is_(None),
                    ~select(ConversationDraftGeneration.id)
                    .where(
                        ConversationDraftGeneration.organisation_id == scope.organisation_id,
                        ConversationDraftGeneration.user_id == scope.user_id,
                        ConversationDraftGeneration.transcript_version_id == TranscriptVersion.id,
                    )
                    .exists(),
                )
                .order_by(TranscriptVersion.created_at, TranscriptVersion.id)
                .limit(100)
            )
            versions = (await session.execute(statement)).all()
            for version, source_recording_session_id, source_evidence_id in versions:
                assert version.meeting_id is not None
                source_fingerprint = self._source_fingerprint(version)
                workspace = await session.scalar(
                    select(ConversationUserWorkspace)
                    .where(
                        ConversationUserWorkspace.organisation_id == scope.organisation_id,
                        ConversationUserWorkspace.interaction_id == version.interaction_id,
                        ConversationUserWorkspace.user_id == scope.user_id,
                    )
                    .with_for_update()
                )
                source_live_notes = eligible_personal_notes_snapshot(
                    workspace.live_notes if workspace is not None else None
                )
                source_live_notes_fingerprint = personal_notes_fingerprint(source_live_notes)
                source_workspace_lock_version = (
                    workspace.lock_version if workspace is not None and source_live_notes is not None else None
                )
                input_fingerprint = draft_input_fingerprint(
                    source_fingerprint,
                    source_live_notes_fingerprint,
                    PRIVATE_DRAFT_SCHEMA_VERSION,
                )
                try:
                    async with session.begin_nested():
                        session.add(
                            ConversationDraftGeneration(
                                id=uuid.uuid4(),
                                organisation_id=scope.organisation_id,
                                interaction_id=version.interaction_id,
                                meeting_id=version.meeting_id,
                                transcript_version_id=version.id,
                                transcript_version=version.version,
                                source_recording_session_id=source_recording_session_id,
                                source_evidence_id=source_evidence_id,
                                user_id=scope.user_id,
                                status="pending",
                                source_fingerprint=source_fingerprint,
                                source_live_notes=source_live_notes,
                                source_live_notes_fingerprint=source_live_notes_fingerprint,
                                source_workspace_lock_version=source_workspace_lock_version,
                                input_fingerprint=input_fingerprint,
                                draft_schema_version=PRIVATE_DRAFT_SCHEMA_VERSION,
                                max_attempts=self._settings.worker_default_max_attempts,
                                next_attempt_at=(
                                    CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT
                                    if source_live_notes is not None
                                    else None
                                ),
                            )
                        )
                        await session.flush()
                    created += 1
                except IntegrityError:
                    # Another worker created the same immutable source version.
                    continue
        return created

    async def claim_next(self, scope: DraftOwnerScope, worker_id: str) -> DraftGenerationClaim | None:
        clean_worker_id = worker_id.strip()
        if not clean_worker_id or len(clean_worker_id) > 200:
            raise ValueError("Worker identity must contain 1 to 200 characters.")
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            await self._set_private_context(session, scope)
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == scope.organisation_id,
                    ConversationDraftGeneration.user_id == scope.user_id,
                    or_(
                        and_(
                            ConversationDraftGeneration.status == "pending",
                            or_(
                                ConversationDraftGeneration.source_live_notes.is_not(None),
                                ConversationDraftGeneration.next_attempt_at.is_(None),
                                ConversationDraftGeneration.next_attempt_at <= now,
                            ),
                        ),
                        and_(
                            ConversationDraftGeneration.status == "processing",
                            or_(
                                ConversationDraftGeneration.source_live_notes.is_not(None),
                                ConversationDraftGeneration.next_attempt_at.is_(None),
                                ConversationDraftGeneration.next_attempt_at <= now,
                            ),
                            or_(
                                ConversationDraftGeneration.lease_expires_at.is_(None),
                                ConversationDraftGeneration.lease_expires_at <= now,
                            ),
                        ),
                    ),
                )
                .order_by(
                    ConversationDraftGeneration.transcript_version,
                    ConversationDraftGeneration.created_at,
                    ConversationDraftGeneration.id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if generation is None:
                return None
            interaction = await session.scalar(
                select(Interaction)
                .where(
                    Interaction.organisation_id == scope.organisation_id,
                    Interaction.id == generation.interaction_id,
                    Interaction.deleted_at.is_(None),
                )
                .with_for_update()
            )
            membership = await session.scalar(
                select(OrganisationMembership).where(
                    OrganisationMembership.organisation_id == scope.organisation_id,
                    OrganisationMembership.user_id == scope.user_id,
                )
            )
            user = await session.scalar(select(User).where(User.id == scope.user_id))
            if membership is None or membership.status != "active" or user is None or user.status != "active":
                self._cancel(generation, "draft_authority_revoked")
                return None
            if interaction is None or interaction.lifecycle_status != "completed":
                self._cancel(generation, "draft_source_unavailable")
                return None
            source = await session.scalar(
                select(TranscriptVersion).where(
                    TranscriptVersion.organisation_id == scope.organisation_id,
                    TranscriptVersion.id == generation.transcript_version_id,
                )
            )
            current = (
                await session.scalar(
                    select(Transcript).where(
                        Transcript.organisation_id == scope.organisation_id,
                        Transcript.id == source.transcript_id,
                        Transcript.deleted_at.is_(None),
                    )
                )
                if source is not None and source.transcript_id is not None
                else None
            )
            if (
                source is None
                or source.status != "final"
                or source.deleted_at is not None
                or current is None
                or current.version != generation.transcript_version
                or self._source_fingerprint(source) != generation.source_fingerprint
            ):
                self._cancel(generation, "draft_transcript_superseded")
                return None
            if not self._generation_input_trace_is_valid(generation):
                self._cancel(generation, "draft_input_trace_invalid")
                return None
            if not await self._processing_authority_is_current(session, generation, source):
                self._cancel(generation, "draft_processing_consent_withdrawn")
                return None
            abandoned_claim = generation.status == "processing" and generation.worker_id is not None
            abandoned_orchestration = abandoned_claim and generation.lease_mode == "orchestrate"
            orchestrate = False
            if generation.status == "pending" or abandoned_orchestration:
                if generation.attempt_count >= generation.max_attempts:
                    self._fail(generation, "draft_retry_exhausted")
                    return None
                generation.attempt_count += 1
                generation.orchestration_attempt_count = generation.attempt_count
                generation.started_at = generation.started_at or datetime.now(UTC)
                generation.failure_code = None
                orchestrate = True
            generation.status = "processing"
            generation.worker_id = clean_worker_id
            generation.lease_mode = "orchestrate" if orchestrate else "poll"
            generation.lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            generation.next_attempt_at = self._worker_fence(generation)
            return DraftGenerationClaim(
                organisation_id=scope.organisation_id,
                user_id=scope.user_id,
                role=membership.role,
                generation_id=generation.id,
                interaction_id=generation.interaction_id,
                meeting_id=generation.meeting_id,
                transcript_version_id=generation.transcript_version_id,
                transcript_version=generation.transcript_version,
                opportunity_id=interaction.opportunity_id,
                interaction_type=interaction.interaction_type,
                event_id=interaction.event_id,
                worker_id=clean_worker_id,
                attempt_count=generation.attempt_count,
                orchestrate=orchestrate,
            )

    async def process(self, claim: DraftGenerationClaim) -> None:
        tenant = TenantContext(
            organisation_id=claim.organisation_id,
            user_id=claim.user_id,
            role=cast(Literal["admin", "member"], claim.role),
        )
        try:
            if not await self._validate_generation_job_origins(claim):
                return
            async with self._session_factory() as session:
                await self._set_private_context(
                    session,
                    DraftOwnerScope(claim.organisation_id, claim.user_id),
                )
                beta = BetaService(session, tenant, self._settings)
                intelligence = MeetingIntelligenceService(
                    session,
                    tenant,
                    generation_limiter=beta.reserve_generation,
                    default_max_attempts=self._settings.worker_default_max_attempts,
                    automatic_draft_generation_id=claim.generation_id,
                )
                if claim.orchestrate:
                    # A pending or genuinely abandoned lease owns one durable
                    # orchestration attempt. Released polling is deliberately
                    # read-only so failed capabilities cannot create billable
                    # replacement jobs without an explicit draft retry.
                    response: MeetingIntelligenceResponse = (
                        await intelligence.generate_post_conversation_draft(claim.meeting_id)
                    ).response
                else:
                    response = await intelligence.get_workspace(claim.meeting_id)
            if not await self._validate_generation_job_origins(claim):
                return
            if claim.orchestrate and not await self._mark_orchestration_returned(claim):
                return
        except PublicAPIError as exc:
            await self._record_failure(claim, exc.code)
            return
        except SQLAlchemyError:
            await self._record_failure(claim, "draft_persistence_unavailable")
            return

        required = (
            response.executive_summary,
            response.decisions,
            response.action_items,
            response.open_questions,
            response.follow_up_email,
        )
        if any(item.state in {"failed", "cancelled"} for item in required):
            await self._record_failure(claim, "draft_intelligence_generation_failed")
            return
        if not all(item.state == "completed" for item in required):
            prerequisites = (
                response.executive_summary,
                response.decisions,
                response.action_items,
                response.open_questions,
            )
            if (
                not claim.orchestrate
                and response.follow_up_email.state == "not_generated"
                and all(item.state == "completed" for item in prerequisites)
            ):
                await self._stage_orchestration_attempt(claim)
                return
            await self._release_for_poll(claim)
            return
        try:
            await self._materialise(claim, response)
        except IntegrityError:
            # A user can create their private workspace after the locked read
            # but before this transaction inserts the initial generated draft.
            # The failed transaction is rolled back by the session context; a
            # fresh materialisation then locks the winning workspace row and
            # preserves its content under the normal edit rules.
            try:
                await self._materialise(claim, response)
            except SQLAlchemyError:
                await self._record_failure(claim, "draft_persistence_unavailable")
        except SQLAlchemyError:
            await self._record_failure(claim, "draft_persistence_unavailable")

    async def _materialise(
        self,
        claim: DraftGenerationClaim,
        response: MeetingIntelligenceResponse,
    ) -> None:
        summary = response.executive_summary.content
        decisions = response.decisions.content
        actions = response.action_items.content
        questions = response.open_questions.content
        follow_up = response.follow_up_email.content
        if summary is None or decisions is None or actions is None or questions is None or follow_up is None:
            await self._record_failure(claim, "draft_intelligence_content_invalid")
            return

        methodology: MethodologyProjectionContent | None = None
        async with self._session_factory() as session, session.begin():
            scope = DraftOwnerScope(claim.organisation_id, claim.user_id)
            await self._set_private_context(session, scope)
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                    ConversationDraftGeneration.worker_id == claim.worker_id,
                )
                .with_for_update()
            )
            if generation is None or not self._claim_is_owned(generation, claim):
                return
            if not await self._generation_job_origins_are_valid(session, claim):
                self._cancel(generation, "draft_job_origin_audit_invalid")
                return
            source = await session.scalar(
                select(TranscriptVersion).where(
                    TranscriptVersion.organisation_id == claim.organisation_id,
                    TranscriptVersion.id == generation.transcript_version_id,
                )
            )
            membership = await session.scalar(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == claim.organisation_id,
                    OrganisationMembership.user_id == claim.user_id,
                    OrganisationMembership.status == "active",
                )
            )
            user = await session.scalar(
                select(User.id).where(
                    User.id == claim.user_id,
                    User.status == "active",
                )
            )
            if membership is None or user is None:
                self._cancel(generation, "draft_authority_revoked")
                return
            interaction = await session.scalar(
                select(Interaction)
                .where(
                    Interaction.organisation_id == claim.organisation_id,
                    Interaction.id == generation.interaction_id,
                    Interaction.lifecycle_status == "completed",
                    Interaction.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if interaction is None:
                self._cancel(generation, "draft_source_unavailable")
                return
            if (
                interaction.opportunity_id != claim.opportunity_id
                or interaction.interaction_type != claim.interaction_type
                or interaction.event_id != claim.event_id
            ):
                # The optional framework is scoped to the interaction state
                # captured by the lease. Never combine a completed intelligence
                # response with a newly associated opportunity or event scope.
                self._cancel(generation, "draft_interaction_scope_changed")
                return
            current = (
                await session.scalar(
                    select(Transcript).where(
                        Transcript.organisation_id == claim.organisation_id,
                        Transcript.id == source.transcript_id,
                        Transcript.deleted_at.is_(None),
                    )
                )
                if source is not None and source.transcript_id is not None
                else None
            )
            if (
                source is None
                or source.status != "final"
                or source.deleted_at is not None
                or source.interaction_id != generation.interaction_id
                or source.meeting_id != generation.meeting_id
                or source.version != generation.transcript_version
                or current is None
                or current.version != generation.transcript_version
                or self._source_fingerprint(source) != generation.source_fingerprint
            ):
                self._cancel(generation, "draft_transcript_superseded")
                return
            if not self._generation_input_trace_is_valid(generation):
                self._cancel(generation, "draft_input_trace_invalid")
                return
            if not await self._processing_authority_is_current(session, generation, source):
                self._cancel(generation, "draft_processing_consent_withdrawn")
                return
            if self._settings.feature_sales_methodology_enabled and self._methodology_is_in_scope(
                interaction_type=interaction.interaction_type,
                event_id=interaction.event_id,
                opportunity_id=interaction.opportunity_id,
            ):
                assert interaction.opportunity_id is not None
                try:
                    # Keep the interaction row locked while resolving the
                    # optional projection so a reassociation cannot make the
                    # framework stale before the generated draft is stored.
                    async with session.begin_nested():
                        result = await SalesMethodologyProjectionService(
                            session,
                            TenantContext(
                                organisation_id=claim.organisation_id,
                                user_id=claim.user_id,
                                role=cast(Literal["admin", "member"], claim.role),
                            ),
                            self._settings,
                        ).read(interaction.opportunity_id)
                        if result.state == "current":
                            methodology = result.projection
                except (PublicAPIError, SQLAlchemyError):
                    # Framework assessment is optional and must never block a
                    # general private draft or substitute unsupported conclusions.
                    methodology = None

            enhanced_notes = self._render_enhanced_notes(
                summary,
                decisions,
                actions,
                questions,
                methodology,
                generation.source_live_notes,
                generation.draft_schema_version,
            )
            if len(enhanced_notes) > CONVERSATION_DRAFT_MAX_CHARACTERS:
                # Do not silently cut the verbatim personal-note section or
                # partial evidence out of transcript-derived sections. Keep
                # the pinned inputs and fail with safe metadata instead.
                # The completed immutable inputs cannot become smaller on a
                # retry, so this is terminal rather than retryable failure.
                self._cancel(generation, "draft_enhanced_notes_too_large")
                return
            follow_up_draft = self._render_follow_up(follow_up)
            content_fingerprint = private_draft_fingerprint(enhanced_notes, follow_up_draft)
            now = datetime.now(UTC)
            generation.enhanced_notes = enhanced_notes
            generation.follow_up_draft = follow_up_draft
            generation.content_fingerprint = content_fingerprint
            generation.framework_included = methodology is not None
            generation.status = "ready"
            generation.failure_code = None
            generation.completed_at = now
            generation.worker_id = None
            generation.lease_mode = None
            generation.lease_expires_at = None
            generation.next_attempt_at = None

            workspace = await session.scalar(
                select(ConversationUserWorkspace)
                .where(
                    ConversationUserWorkspace.organisation_id == claim.organisation_id,
                    ConversationUserWorkspace.interaction_id == claim.interaction_id,
                    ConversationUserWorkspace.user_id == claim.user_id,
                )
                .with_for_update()
            )
            if workspace is None and generation.source_live_notes_fingerprint is None:
                workspace = ConversationUserWorkspace(
                    id=uuid.uuid4(),
                    organisation_id=claim.organisation_id,
                    interaction_id=claim.interaction_id,
                    user_id=claim.user_id,
                    enhanced_notes=enhanced_notes,
                    follow_up_draft=follow_up_draft,
                    follow_up_reviewed=False,
                    generation_fingerprint=content_fingerprint,
                    lock_version=1,
                )
                session.add(workspace)
                generation.workspace_applied_at = now
            elif workspace is not None and self._workspace_accepts_initial_generation(workspace, generation):
                workspace.enhanced_notes = enhanced_notes
                workspace.follow_up_draft = follow_up_draft
                workspace.follow_up_reviewed = False
                workspace.generation_fingerprint = content_fingerprint
                workspace.lock_version += 1
                generation.workspace_applied_at = now

        logger.info(
            "post_conversation_draft_ready",
            extra={
                "organisation_id": str(claim.organisation_id),
                "interaction_id": str(claim.interaction_id),
                "generation_id": str(claim.generation_id),
                "transcript_version": claim.transcript_version,
                "framework_included": methodology is not None,
            },
        )

    async def _record_failure(self, claim: DraftGenerationClaim, code: str) -> None:
        async with self._session_factory() as session, session.begin():
            await self._set_private_context(
                session,
                DraftOwnerScope(claim.organisation_id, claim.user_id),
            )
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                    ConversationDraftGeneration.worker_id == claim.worker_id,
                )
                .with_for_update()
            )
            if generation is not None and self._claim_is_owned(generation, claim):
                self._fail(generation, code)
        logger.warning(
            "post_conversation_draft_failed",
            extra={
                "organisation_id": str(claim.organisation_id),
                "interaction_id": str(claim.interaction_id),
                "generation_id": str(claim.generation_id),
                "error_code": code,
            },
        )

    async def _release_for_poll(self, claim: DraftGenerationClaim) -> None:
        async with self._session_factory() as session, session.begin():
            await self._set_private_context(
                session,
                DraftOwnerScope(claim.organisation_id, claim.user_id),
            )
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                    ConversationDraftGeneration.worker_id == claim.worker_id,
                )
                .with_for_update()
            )
            if generation is None or not self._claim_is_owned(generation, claim):
                return
            generation.worker_id = None
            generation.lease_mode = None
            if generation.source_live_notes_fingerprint is not None:
                generation.lease_expires_at = datetime.now(UTC) + timedelta(
                    seconds=self._settings.worker_poll_interval_seconds
                )
                generation.next_attempt_at = CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT
            else:
                generation.lease_expires_at = None
                generation.next_attempt_at = datetime.now(UTC) + timedelta(
                    seconds=self._settings.worker_poll_interval_seconds
                )

    async def _stage_orchestration_attempt(self, claim: DraftGenerationClaim) -> None:
        """Move a completed prerequisite phase to one new bounded attempt."""

        async with self._session_factory() as session, session.begin():
            await self._set_private_context(
                session,
                DraftOwnerScope(claim.organisation_id, claim.user_id),
            )
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                    ConversationDraftGeneration.worker_id == claim.worker_id,
                )
                .with_for_update()
            )
            if generation is None or not self._claim_is_owned(generation, claim):
                return
            if generation.attempt_count >= generation.max_attempts:
                self._fail(generation, "draft_retry_exhausted")
                return
            generation.status = "pending"
            generation.worker_id = None
            generation.lease_mode = None
            generation.lease_expires_at = None
            generation.next_attempt_at = self._worker_fence(generation)

    async def _mark_orchestration_returned(self, claim: DraftGenerationClaim) -> bool:
        """Fence a returned orchestrator call from abandoned-poll recovery."""

        async with self._session_factory() as session, session.begin():
            await self._set_private_context(
                session,
                DraftOwnerScope(claim.organisation_id, claim.user_id),
            )
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                    ConversationDraftGeneration.worker_id == claim.worker_id,
                    ConversationDraftGeneration.lease_mode == "orchestrate",
                )
                .with_for_update()
            )
            if generation is None or not self._claim_is_owned(generation, claim):
                return False
            generation.lease_mode = "poll"
            return True

    async def _validate_generation_job_origins(
        self,
        claim: DraftGenerationClaim,
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            await self._set_private_context(
                session,
                DraftOwnerScope(claim.organisation_id, claim.user_id),
            )
            generation = await session.scalar(
                select(ConversationDraftGeneration)
                .where(
                    ConversationDraftGeneration.organisation_id == claim.organisation_id,
                    ConversationDraftGeneration.user_id == claim.user_id,
                    ConversationDraftGeneration.id == claim.generation_id,
                )
                .with_for_update()
            )
            if generation is None or not self._claim_is_owned(generation, claim):
                return False
            if await self._generation_job_origins_are_valid(session, claim):
                return True
            self._cancel(generation, "draft_job_origin_audit_invalid")
            return False

    @staticmethod
    async def _generation_job_origins_are_valid(
        session: AsyncSession,
        claim: DraftGenerationClaim,
    ) -> bool:
        jobs = list(
            await session.scalars(
                select(AIJob)
                .where(
                    AIJob.organisation_id == claim.organisation_id,
                    AIJob.automatic_draft_generation_id == claim.generation_id,
                )
                .with_for_update()
            )
        )
        for job in jobs:
            if (
                job.requested_by_user_id != claim.user_id
                or job.meeting_id != claim.meeting_id
                or job.transcript_version != claim.transcript_version
                or not await automatic_draft_job_origin_audit_is_valid(
                    session,
                    organisation_id=job.organisation_id,
                    meeting_id=job.meeting_id,
                    job_id=job.id,
                    generation_id=claim.generation_id,
                    requested_by_user_id=job.requested_by_user_id,
                    transcript_version=job.transcript_version,
                )
            ):
                return False
        return True

    async def _processing_authority_is_current(
        self,
        session: AsyncSession,
        generation: ConversationDraftGeneration,
        source: TranscriptVersion,
    ) -> bool:
        return await automatic_draft_processing_authority_is_current(
            session,
            self._settings,
            generation,
            source,
        )

    @staticmethod
    def _methodology_is_in_scope(
        *,
        interaction_type: str,
        event_id: UUID | None,
        opportunity_id: UUID | None,
    ) -> bool:
        return opportunity_id is not None and event_id is None and interaction_type not in EVENT_INTERACTION_TYPES

    @staticmethod
    def _workspace_accepts_initial_generation(
        workspace: ConversationUserWorkspace,
        generation: ConversationDraftGeneration,
    ) -> bool:
        return (
            workspace.user_edited_at is None
            and workspace.generation_fingerprint is None
            and not (workspace.enhanced_notes or "").strip()
            and not (workspace.follow_up_draft or "").strip()
            and personal_notes_fingerprint(workspace.live_notes) == generation.source_live_notes_fingerprint
        )

    @staticmethod
    def _generation_input_trace_is_valid(generation: ConversationDraftGeneration) -> bool:
        if generation.draft_schema_version not in SUPPORTED_PRIVATE_DRAFT_SCHEMA_VERSIONS:
            return False
        if generation.input_fingerprint is None:
            return False
        if (
            generation.source_live_notes is not None
            and len(generation.source_live_notes) > PRIVATE_PERSONAL_NOTES_SNAPSHOT_MAX_CHARACTERS
        ):
            return False
        notes_fingerprint = personal_notes_fingerprint(generation.source_live_notes)
        if notes_fingerprint != generation.source_live_notes_fingerprint:
            return False
        if (generation.source_workspace_lock_version is None) != (notes_fingerprint is None):
            return False
        return generation.input_fingerprint == draft_input_fingerprint(
            generation.source_fingerprint,
            notes_fingerprint,
            generation.draft_schema_version,
        )

    @staticmethod
    def _worker_fence(generation: ConversationDraftGeneration) -> datetime | None:
        return (
            CONVERSATION_DRAFT_PRIVATE_NOTES_WORKER_FENCE_AT
            if generation.source_live_notes_fingerprint is not None
            else None
        )

    @staticmethod
    def _render_enhanced_notes(
        summary: ExecutiveSummaryContentResponse,
        decisions: DecisionsContentResponse,
        actions: ActionItemsContentResponse,
        questions: OpenQuestionsContentResponse,
        methodology: MethodologyProjectionContent | None,
        source_live_notes: str | None,
        draft_schema_version: int,
    ) -> str:
        if draft_schema_version == 1:
            return PostConversationDraftWorkerService._render_enhanced_notes_v1(
                summary,
                decisions,
                actions,
                questions,
                methodology,
                source_live_notes,
            )
        raise ValueError("Unsupported private draft schema version.")

    @staticmethod
    def _render_enhanced_notes_v1(
        summary: ExecutiveSummaryContentResponse,
        decisions: DecisionsContentResponse,
        actions: ActionItemsContentResponse,
        questions: OpenQuestionsContentResponse,
        methodology: MethodologyProjectionContent | None,
        source_live_notes: str | None,
    ) -> str:
        sections = ["Enhanced notes"]
        if source_live_notes is not None:
            sections.extend((PRIVATE_PERSONAL_NOTES_SECTION_LABEL, source_live_notes))
        sections.extend(("Summary", summary.executive_summary))
        sections.extend(
            (
                "Decisions",
                (
                    "\n".join(f"- {item.decision} (Evidence: {item.evidence})" for item in decisions.decisions)
                    if decisions.decisions
                    else "No evidence-backed decisions were identified."
                ),
            )
        )
        if methodology is not None:
            supported = [
                item
                for item in methodology.items
                if item.state in {"confirmed", "partially_supported", "conflicting", "stale"}
                and (item.sources or item.conflicts)
            ]
            if supported:
                sections.extend(
                    (
                        f"{methodology.methodology_name} framework assessment",
                        "\n".join(
                            f"- {item.display_name}: {item.conclusion or item.state.replace('_', ' ')} "
                            f"[{item.state.replace('_', ' ')}; Evidence: "
                            f"{', '.join(source.label for source in (*item.sources, *item.conflicts))}]"
                            for item in supported
                        ),
                    )
                )
        sections.extend(
            (
                "Suggested actions",
                (
                    "\n".join(
                        "- "
                        + item.task
                        + (f" — owner: {item.owner}" if item.owner else "")
                        + (f" — due: {item.due_date}" if item.due_date else "")
                        + f" (Evidence: {item.evidence})"
                        for item in actions.action_items
                    )
                    if actions.action_items
                    else "No evidence-backed actions were identified."
                ),
            )
        )
        if questions.open_questions:
            sections.extend(
                (
                    "Open questions",
                    "\n".join(f"- {item.question} (Evidence: {item.evidence})" for item in questions.open_questions),
                )
            )
        return "\n\n".join(sections)

    @staticmethod
    def _render_follow_up(content: FollowUpEmailContentResponse) -> str:
        sections = [
            f"Subject: {content.subject}",
            content.greeting,
            content.summary,
            PostConversationDraftWorkerService._plain_list("Decisions", content.decisions),
            PostConversationDraftWorkerService._plain_list("Action Items", content.action_items),
            PostConversationDraftWorkerService._plain_list("Open Questions", content.open_questions),
            content.closing,
        ]
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _plain_list(title: str, values: list[str]) -> str:
        return f"{title}:\n" + "\n".join(f"- {item}" for item in values) if values else ""

    @staticmethod
    def _source_fingerprint(version: TranscriptVersion) -> str:
        digest = hashlib.sha256()
        digest.update(str(version.id).encode("ascii"))
        digest.update(b":")
        digest.update(str(version.version).encode("ascii"))
        digest.update(b":")
        digest.update(version.raw_text.encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _owner_expression() -> ColumnElement[UUID]:
        return func.coalesce(
            RecordingSession.created_by_user_id,
            Evidence.captured_by_user_id,
            Interaction.created_by_user_id,
        )

    @staticmethod
    def _recording_lineage_id_expression() -> ColumnElement[UUID]:
        lineage = aliased(TranscriptVersion)
        inherited = (
            select(lineage.recording_session_id)
            .where(
                lineage.organisation_id == TranscriptVersion.organisation_id,
                lineage.transcript_id == TranscriptVersion.transcript_id,
                lineage.version <= TranscriptVersion.version,
                lineage.recording_session_id.is_not(None),
            )
            .order_by(lineage.version.desc(), lineage.id.desc())
            .limit(1)
            .correlate(TranscriptVersion)
            .scalar_subquery()
        )
        return func.coalesce(TranscriptVersion.recording_session_id, inherited)

    @staticmethod
    def _evidence_lineage_id_expression() -> ColumnElement[UUID]:
        lineage = aliased(TranscriptVersion)
        inherited = (
            select(lineage.evidence_id)
            .where(
                lineage.organisation_id == TranscriptVersion.organisation_id,
                lineage.transcript_id == TranscriptVersion.transcript_id,
                lineage.version <= TranscriptVersion.version,
                lineage.evidence_id.is_not(None),
            )
            .order_by(lineage.version.desc(), lineage.id.desc())
            .limit(1)
            .correlate(TranscriptVersion)
            .scalar_subquery()
        )
        return func.coalesce(TranscriptVersion.evidence_id, inherited)

    @classmethod
    def _final_source_scope_statement(cls) -> Select[tuple[UUID, UUID]]:
        recording_lineage_id = cls._recording_lineage_id_expression()
        evidence_lineage_id = cls._evidence_lineage_id_expression()
        owner = cls._owner_expression()
        return (
            select(TranscriptVersion.organisation_id, owner.label("user_id"))
            .join(
                Transcript,
                (Transcript.organisation_id == TranscriptVersion.organisation_id)
                & (Transcript.id == TranscriptVersion.transcript_id)
                & (Transcript.version == TranscriptVersion.version),
            )
            .join(
                Interaction,
                (Interaction.organisation_id == TranscriptVersion.organisation_id)
                & (Interaction.id == TranscriptVersion.interaction_id),
            )
            .outerjoin(
                RecordingSession,
                (RecordingSession.organisation_id == TranscriptVersion.organisation_id)
                & (RecordingSession.id == recording_lineage_id),
            )
            .outerjoin(
                Evidence,
                (Evidence.organisation_id == TranscriptVersion.organisation_id) & (Evidence.id == evidence_lineage_id),
            )
            .join(
                OrganisationMembership,
                (OrganisationMembership.organisation_id == TranscriptVersion.organisation_id)
                & (OrganisationMembership.user_id == owner)
                & (OrganisationMembership.status == "active"),
            )
            .join(User, (User.id == owner) & (User.status == "active"))
            .where(
                TranscriptVersion.status == "final",
                TranscriptVersion.deleted_at.is_(None),
                TranscriptVersion.meeting_id.is_not(None),
                Transcript.deleted_at.is_(None),
                Interaction.lifecycle_status == "completed",
                Interaction.deleted_at.is_(None),
                ~select(ConversationDraftGeneration.id)
                .where(
                    ConversationDraftGeneration.organisation_id == TranscriptVersion.organisation_id,
                    ConversationDraftGeneration.user_id == owner,
                    ConversationDraftGeneration.transcript_version_id == TranscriptVersion.id,
                )
                .exists(),
            )
            .distinct()
        )

    @staticmethod
    async def _set_private_context(session: AsyncSession, scope: DraftOwnerScope) -> None:
        await set_tenant_database_context(session, scope.organisation_id)
        await set_private_user_database_context(session, scope.user_id)

    @staticmethod
    def _cancel(generation: ConversationDraftGeneration, code: str) -> None:
        cancel_automatic_draft_generation(generation, code, datetime.now(UTC))

    @staticmethod
    def _fail(generation: ConversationDraftGeneration, code: str) -> None:
        generation.status = "failed"
        generation.failure_code = code
        generation.completed_at = datetime.now(UTC)
        generation.worker_id = None
        generation.lease_mode = None
        generation.lease_expires_at = None
        generation.next_attempt_at = None

    @staticmethod
    def _claim_is_owned(
        generation: ConversationDraftGeneration,
        claim: DraftGenerationClaim,
    ) -> bool:
        if (
            generation.status != "processing"
            or generation.worker_id != claim.worker_id
            or generation.attempt_count != claim.attempt_count
        ):
            return False
        if generation.lease_expires_at is None:
            return False
        lease_expires_at = generation.lease_expires_at
        if lease_expires_at.tzinfo is None:
            lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
        return lease_expires_at > datetime.now(UTC)
