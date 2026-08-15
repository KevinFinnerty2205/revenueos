from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, time
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_prompt_errors import StructuredOutputValidationError
from revenueos.ai_provider import AIProvider
from revenueos.ai_provider_errors import MalformedProviderOutputError, ProviderError
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.debrief_ai import StructuredDebriefReasoning
from revenueos.debrief_contracts import (
    CandidateEvidenceCategory,
    CandidateEvidenceResponse,
    CandidateReviewState,
    CandidateValidationState,
    DebriefAnswerRequest,
    DebriefCancelRequest,
    DebriefCaptureType,
    DebriefFinishRequest,
    DebriefInputMode,
    DebriefLifecycleStatus,
    DebriefQuestion,
    DebriefReviewRequest,
    DebriefReviewResponse,
    DebriefSessionResponse,
    DebriefStartRequest,
    DebriefTurnResponse,
    DebriefVoiceAnswerRequest,
)
from revenueos.debrief_reasoning import DeterministicDebriefReasoning
from revenueos.debrief_repositories import DebriefRepository, DebriefSessionRecord
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    CandidateEvidence,
    CaptureSession,
    DebriefSession,
    DebriefTurn,
    Evidence,
    EvidenceFragment,
    Interaction,
    InteractionIntelligenceSnapshot,
    Opportunity,
    RevenueBrainInteractionSnapshot,
)
from revenueos.tenant import TenantContext
from revenueos.transcription_provider import (
    TranscriptionProvider,
    TranscriptionProviderError,
    create_transcription_provider,
    execute_transcription,
)

logger = logging.getLogger("revenueos.debrief")


class DebriefService:
    """Bounded source-aware post-interaction capture and review workflow."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        transcription_provider: TranscriptionProvider | None = None,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = DebriefRepository(session)
        self.beta = BetaService(session, tenant, settings)
        self.reasoning = DeterministicDebriefReasoning()
        self.structured_reasoning = StructuredDebriefReasoning(
            settings,
            tenant.organisation_id,
            ai_provider,
        )
        self.transcription_provider = transcription_provider or create_transcription_provider(settings)

    async def start(
        self,
        interaction_id: UUID,
        request: DebriefStartRequest,
    ) -> DebriefSessionResponse:
        await self.beta.require_notice_acknowledgement()
        feature = "aiDebrief" if request.capture_type == "ai_debrief" else "voiceJournal"
        self.beta.require_feature(feature)
        existing = await self.repository.find_idempotent_session(
            self.tenant.organisation_id,
            interaction_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            if existing.capture_session.capture_type != request.capture_type:
                raise PublicAPIError(
                    "idempotency_conflict",
                    "That request key was already used for a different capture type.",
                    409,
                )
            return await self._response(existing)
        interaction = await self._require_completed_interaction(interaction_id)
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        count = await self.repository.count_sessions_since(self.tenant.organisation_id, today)
        if count >= self.settings.private_beta_max_debrief_sessions_per_day:
            raise PublicAPIError(
                "daily_debrief_limit_exceeded",
                "This organisation has reached today’s debrief session limit.",
                429,
            )
        now = datetime.now(UTC)
        session_id = uuid.uuid4()
        capture = CaptureSession(
            id=session_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            capture_type=request.capture_type,
            status="capturing",
            started_by_user_id=self.tenant.user_id,
            started_at=now,
        )
        max_questions = (
            min(2, self.settings.private_beta_debrief_question_cap)
            if request.capture_type == "voice_journal"
            else self.settings.private_beta_debrief_question_cap
        )
        debrief = DebriefSession(
            id=session_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            started_by_user_id=self.tenant.user_id,
            lifecycle_status="collecting",
            idempotency_key=request.idempotency_key,
            question_count=0,
            max_questions=max_questions,
            current_question_json=self.reasoning.opening_question().model_dump(mode="json", by_alias=False),
            safety_confirmed_at=now,
            voice_processing_acknowledged_at=now if request.voice_processing_acknowledged else None,
        )
        self.session.add_all([capture, debrief])
        self._event(
            "debrief_started" if request.capture_type == "ai_debrief" else "voice_journal_started",
            session_id,
            {"interaction_type": interaction.interaction_type},
        )
        await self._commit("The debrief session could not be started.")
        return await self._response(DebriefSessionRecord(capture, debrief))

    async def get(self, interaction_id: UUID, session_id: UUID) -> DebriefSessionResponse:
        return await self._response(await self._require_session(interaction_id, session_id))

    async def answer(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: DebriefAnswerRequest,
    ) -> DebriefSessionResponse:
        return await self._store_answer(
            interaction_id,
            session_id,
            answer_text=request.answer_text,
            input_mode="text",
            idempotency_key=request.idempotency_key,
            audio_duration_seconds=None,
            transcription_provider=None,
            transcription_request_id=None,
        )

    async def voice_answer(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: DebriefVoiceAnswerRequest,
    ) -> DebriefSessionResponse:
        await self.beta.require_notice_acknowledgement()
        self.beta.require_feature("voiceJournal")
        record = await self._require_session(interaction_id, session_id)
        if record.debrief_session.voice_processing_acknowledged_at is None:
            raise PublicAPIError(
                "voice_processing_acknowledgement_required",
                "Confirm the post-interaction voice-processing notice before using the microphone.",
                428,
            )
        existing = await self.repository.find_turn_by_idempotency(
            self.tenant.organisation_id,
            session_id,
            request.idempotency_key,
        )
        if existing is not None:
            return await self._response(record)
        if request.duration_seconds > self.settings.private_beta_max_debrief_audio_seconds:
            raise PublicAPIError(
                "voice_segment_too_long",
                f"Voice segments must be {self.settings.private_beta_max_debrief_audio_seconds} seconds or shorter.",
                413,
            )
        try:
            audio = request.audio_bytes()
        except ValueError as exc:
            raise PublicAPIError("invalid_audio", "The voice segment could not be read.", 422) from exc
        if not audio or len(audio) > self.settings.private_beta_max_debrief_audio_bytes:
            raise PublicAPIError(
                "voice_segment_too_large",
                "The voice segment is empty or exceeds the private-beta upload limit.",
                413,
            )
        if self.settings.transcription_provider_name == "openai":
            await self.beta.reserve_provider_request(self.settings.transcription_provider_name)
        await self.session.commit()
        try:
            transcription = await execute_transcription(
                self.transcription_provider,
                audio=audio,
                mime_type=request.mime_type,
                language=request.language,
                duration_seconds=request.duration_seconds,
                timeout_seconds=self.settings.transcription_timeout_seconds,
            )
        except TranscriptionProviderError as exc:
            raise PublicAPIError(
                exc.code, "The voice answer could not be transcribed. You can type it instead.", 503
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        return await self._store_answer(
            interaction_id,
            session_id,
            answer_text=transcription.text,
            input_mode="voice",
            idempotency_key=request.idempotency_key,
            audio_duration_seconds=transcription.duration_seconds,
            transcription_provider=transcription.provider_name,
            transcription_request_id=transcription.provider_request_id,
        )

    async def finish(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: DebriefFinishRequest,
    ) -> DebriefSessionResponse:
        record = await self._require_session(interaction_id, session_id, for_update=True)
        debrief = record.debrief_session
        if debrief.lifecycle_status in {"review", "completed"}:
            return await self._response(record)
        if debrief.lifecycle_status == "processing":
            return await self._response(record)
        if debrief.lifecycle_status != "collecting":
            raise self._invalid_state("finish", debrief.lifecycle_status)
        fragments = await self.repository.list_fragments(self.tenant.organisation_id, session_id)
        if not fragments:
            raise PublicAPIError(
                "debrief_answer_required",
                "Add at least one answer before finishing the debrief.",
                409,
            )
        interaction = await self._require_completed_interaction(interaction_id)
        context = await self.repository.normalised_start_context(self.tenant.organisation_id, interaction)
        await self.beta.reserve_generation()
        if self.structured_reasoning.uses_external_provider:
            await self.beta.reserve_provider_request()
        debrief.lifecycle_status = "processing"
        debrief.current_question_json = None
        await self._commit_before_provider("The captured evidence could not be prepared for review.")
        try:
            extraction = await self.structured_reasoning.extract_candidates(
                request_id=uuid.uuid5(session_id, f"finish:{request.idempotency_key}"),
                session_id=session_id,
                capture_type=cast(DebriefCaptureType, record.capture_session.capture_type),
                context=context,
                fragments=tuple((fragment.id, fragment.content_text) for fragment in fragments),
            )
        except (ProviderError, MalformedProviderOutputError, StructuredOutputValidationError) as exc:
            await self._fail_provider_processing(
                interaction_id,
                session_id,
                getattr(exc, "code", "invalid_structured_output"),
            )
            raise PublicAPIError(
                "debrief_processing_failed",
                "The captured evidence could not be prepared. Please start a new debrief.",
                503,
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_session(interaction_id, session_id, for_update=True)
        debrief = record.debrief_session
        if debrief.lifecycle_status != "processing":
            return await self._response(record)
        eligible_items = [
            item
            for item in extraction.items
            if interaction.interaction_type != "presentation"
            or self._presentation_candidate_allowed(item.statement, item.evidence_category)
        ]
        for item in eligible_items:
            fingerprint = self._fingerprint(item.statement)
            self.session.add(
                CandidateEvidence(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    interaction_id=interaction_id,
                    session_id=session_id,
                    source_fragment_id=item.source_fragment_id,
                    evidence_category=item.evidence_category,
                    statement=item.statement,
                    original_statement=item.statement,
                    statement_fingerprint=fingerprint,
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="unreviewed",
                    entity_reference=item.entity_reference,
                    explicitly_reported_at=item.explicitly_reported_at,
                    review_state="pending",
                )
            )
        debrief.lifecycle_status = "review"
        debrief.finished_early = request.finish_early
        self._event(
            "debrief_finished",
            session_id,
            {
                "candidate_count": len(extraction.items),
                "eligible_candidate_count": len(eligible_items),
                "question_count": debrief.question_count,
                "interaction_type": interaction.interaction_type,
            },
        )
        await self._commit("The captured evidence could not be prepared for review.")
        return await self._response(record)

    @staticmethod
    def _presentation_candidate_allowed(statement: str, category: str) -> bool:
        """Keep seller-authored presentation claims out of customer-signal evidence."""

        normalised = " ".join(statement.casefold().split())
        seller_material_markers = (
            "our deck",
            "our slide",
            "our presentation",
            "we presented",
            "we showed",
            "we explained",
            "the slide says",
            "the deck says",
        )
        signal_categories = {
            "buying_signal",
            "commercial_intent",
            "decision",
            "commitment",
            "timeline",
            "procurement",
            "budget",
        }
        return not (category in signal_categories and any(marker in normalised for marker in seller_material_markers))

    async def review(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: DebriefReviewRequest,
    ) -> DebriefReviewResponse:
        _ = request.idempotency_key
        record = await self._require_session(interaction_id, session_id, for_update=True)
        debrief = record.debrief_session
        if debrief.lifecycle_status == "completed":
            return await self._review_response(record)
        if debrief.lifecycle_status != "review":
            raise self._invalid_state("review", debrief.lifecycle_status)
        candidates = await self.repository.list_candidates(
            self.tenant.organisation_id,
            session_id,
            for_update=True,
        )
        pending = {item.id: item for item in candidates if item.review_state == "pending"}
        decisions = {item.candidate_id: item for item in request.decisions}
        if set(decisions) != set(pending):
            raise PublicAPIError(
                "incomplete_review",
                "Review every captured item before updating the interaction.",
                422,
            )
        now = datetime.now(UTC)
        accepted: list[CandidateEvidence] = []
        for candidate_id, candidate in pending.items():
            decision = decisions[candidate_id]
            if decision.decision == "reject":
                candidate.review_state = "rejected"
                candidate.validation_state = "rejected"
            else:
                accepted_evidence_id = uuid.uuid4()
                accepted_evidence = Evidence(
                    id=accepted_evidence_id,
                    organisation_id=self.tenant.organisation_id,
                    interaction_id=interaction_id,
                    capture_session_id=session_id,
                    evidence_type="user_observation",
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="verified",
                    captured_by_user_id=self.tenant.user_id,
                    captured_at=now,
                    lifecycle_status="available",
                    retention_class="inherited",
                )
                self.session.add(accepted_evidence)
                await self.session.flush([accepted_evidence])
                if decision.statement is not None:
                    candidate.statement = decision.statement
                candidate.accepted_evidence_id = accepted_evidence_id
                candidate.review_state = "accepted"
                candidate.validation_state = "verified"
                accepted.append(candidate)
            candidate.reviewed_by_user_id = self.tenant.user_id
            candidate.reviewed_at = now
        interaction = await self._require_completed_interaction(interaction_id)
        intelligence_id: UUID | None = None
        brain_id: UUID | None = None
        if accepted:
            intelligence_id, brain_id = await self._create_snapshots(interaction, session_id, accepted)
        debrief.lifecycle_status = "completed"
        debrief.completed_at = now
        record.capture_session.status = "completed"
        record.capture_session.completed_at = now
        self._event(
            "evidence_confirmed",
            session_id,
            {
                "accepted_count": len(accepted),
                "rejected_count": len(candidates) - len(accepted),
                "interaction_updated": intelligence_id is not None,
                "revenue_brain_updated": brain_id is not None,
                "interaction_type": interaction.interaction_type,
            },
        )
        await self._commit("The reviewed evidence could not be applied.")
        return await self._review_response(record)

    async def cancel(
        self,
        interaction_id: UUID,
        session_id: UUID,
        request: DebriefCancelRequest,
    ) -> DebriefSessionResponse:
        _ = request.idempotency_key
        record = await self._require_session(interaction_id, session_id, for_update=True)
        if record.debrief_session.lifecycle_status == "completed":
            raise self._invalid_state("cancel", "completed")
        if record.debrief_session.lifecycle_status != "cancelled":
            now = datetime.now(UTC)
            record.debrief_session.lifecycle_status = "cancelled"
            record.debrief_session.completed_at = now
            record.capture_session.status = "abandoned"
            record.capture_session.completed_at = now
            self._event("debrief_cancelled", session_id, {})
            await self._commit("The debrief session could not be cancelled.")
        return await self._response(record)

    async def _store_answer(
        self,
        interaction_id: UUID,
        session_id: UUID,
        *,
        answer_text: str,
        input_mode: str,
        idempotency_key: str,
        audio_duration_seconds: int | None,
        transcription_provider: str | None,
        transcription_request_id: str | None,
    ) -> DebriefSessionResponse:
        record = await self._require_session(interaction_id, session_id, for_update=True)
        existing = await self.repository.find_turn_by_idempotency(
            self.tenant.organisation_id,
            session_id,
            idempotency_key,
        )
        if existing is not None:
            return await self._response(record)
        debrief = record.debrief_session
        if debrief.lifecycle_status != "collecting":
            raise self._invalid_state("answer", debrief.lifecycle_status)
        if debrief.current_question_json is None:
            raise PublicAPIError("question_unavailable", "Finish the debrief to review what was captured.", 409)
        current_question = DebriefQuestion.model_validate(debrief.current_question_json)
        if current_question.status != "ask":
            raise PublicAPIError("question_unavailable", "Finish the debrief to review what was captured.", 409)
        turns = await self.repository.list_turns(self.tenant.organisation_id, session_id)
        turn_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        fragment_id = uuid.uuid4()
        now = datetime.now(UTC)
        self.session.add(
            Evidence(
                id=evidence_id,
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction_id,
                capture_session_id=session_id,
                evidence_type="user_observation",
                origin_class="salesperson_reported",
                support_class="reported",
                validation_state="unreviewed",
                captured_by_user_id=self.tenant.user_id,
                captured_at=now,
                lifecycle_status="available",
                retention_class="inherited",
            )
        )
        await self.session.flush()
        self.session.add(
            DebriefTurn(
                id=turn_id,
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction_id,
                session_id=session_id,
                evidence_id=evidence_id,
                turn_number=len(turns) + 1,
                question_json=current_question.model_dump(mode="json", by_alias=False),
                answer_text=answer_text,
                input_mode=input_mode,
                idempotency_key=idempotency_key,
                audio_duration_seconds=audio_duration_seconds,
                transcription_provider=transcription_provider,
                transcription_request_id=transcription_request_id,
            )
        )
        await self.session.flush()
        self.session.add(
            EvidenceFragment(
                id=fragment_id,
                organisation_id=self.tenant.organisation_id,
                evidence_id=evidence_id,
                session_id=session_id,
                turn_id=turn_id,
                locator_type="debrief_turn",
                content_text=answer_text,
            )
        )
        answers = tuple([*(item.answer_text for item in turns), answer_text])
        asked: list[str] = []
        for item in turns:
            prior_question = DebriefQuestion.model_validate(item.question_json)
            if prior_question.question != "How did it go?" and prior_question.target is not None:
                asked.append(prior_question.target)
        asked_targets = tuple(asked)
        if current_question.question != "How did it go?" and current_question.target is not None:
            asked_targets = (*asked_targets, current_question.target)
        brief_questions = await self.repository.latest_brief_questions(
            self.tenant.organisation_id,
            interaction_id,
        )
        interaction = await self._require_completed_interaction(interaction_id)
        context = await self.repository.normalised_start_context(self.tenant.organisation_id, interaction)
        capture_type = cast(DebriefCaptureType, record.capture_session.capture_type)
        question_count = debrief.question_count
        max_questions = debrief.max_questions
        if self.structured_reasoning.uses_external_provider:
            await self.beta.reserve_provider_request()
        debrief.lifecycle_status = "processing"
        debrief.current_question_json = None
        await self._commit_before_provider("The debrief answer could not be saved.")
        try:
            next_question = await self.structured_reasoning.next_question(
                request_id=uuid.uuid5(session_id, f"answer:{idempotency_key}"),
                session_id=session_id,
                interaction_type=interaction.interaction_type,
                capture_type=capture_type,
                context=context,
                answers=answers,
                asked_targets=asked_targets,
                question_count=question_count,
                max_questions=max_questions,
                context_questions=brief_questions,
            )
        except (ProviderError, MalformedProviderOutputError, StructuredOutputValidationError) as exc:
            await self._fail_provider_processing(
                interaction_id,
                session_id,
                getattr(exc, "code", "invalid_structured_output"),
            )
            raise PublicAPIError(
                "debrief_processing_failed",
                "The next debrief question could not be prepared. Please start a new debrief.",
                503,
            ) from exc
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_session(interaction_id, session_id, for_update=True)
        debrief = record.debrief_session
        if debrief.lifecycle_status != "processing":
            return await self._response(record)
        if next_question.status == "ask":
            debrief.question_count += 1
        debrief.lifecycle_status = "collecting"
        debrief.current_question_json = next_question.model_dump(mode="json", by_alias=False)
        self._event(
            "voice_answer_submitted" if input_mode == "voice" else "answer_submitted",
            session_id,
            {
                "question_count": debrief.question_count,
                "input_mode": input_mode,
            },
        )
        await self._commit("The debrief answer could not be saved.")
        return await self._response(record)

    async def _create_snapshots(
        self,
        interaction: Interaction,
        session_id: UUID,
        accepted: list[CandidateEvidence],
    ) -> tuple[UUID, UUID | None]:
        source_ids = [str(item.accepted_evidence_id) for item in accepted if item.accepted_evidence_id is not None]
        content: dict[str, object] = {
            "schemaVersion": 1,
            "origin": "salesperson_reported",
            "sourceLabel": "Reported by you",
            "items": [
                {
                    "candidateId": str(item.id),
                    "evidenceId": str(item.accepted_evidence_id),
                    "category": item.evidence_category,
                    "statement": item.statement,
                    "origin": "salesperson_reported",
                    "validationState": "verified",
                }
                for item in accepted
            ],
        }
        intelligence_id = uuid.uuid4()
        intelligence = InteractionIntelligenceSnapshot(
            id=intelligence_id,
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction.id,
            opportunity_id=interaction.opportunity_id,
            session_id=session_id,
            schema_version=1,
            version=await self.repository.next_intelligence_version(
                self.tenant.organisation_id,
                interaction.id,
            ),
            validation_state="validated",
            content_json=content,
            source_evidence_ids=source_ids,
        )
        self.session.add(intelligence)
        company_id = interaction.company_id
        if company_id is None and interaction.opportunity_id is not None:
            opportunity = await self.repository.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == interaction.opportunity_id,
                )
            )
            company_id = opportunity.company_id if opportunity is not None else None
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
                schema_version=1,
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

    async def _response(self, record: DebriefSessionRecord) -> DebriefSessionResponse:
        await self.session.refresh(record.capture_session)
        await self.session.refresh(record.debrief_session)
        turns = await self.repository.list_turns(self.tenant.organisation_id, record.debrief_session.id)
        candidates = await self.repository.list_candidates(self.tenant.organisation_id, record.debrief_session.id)
        intelligence = await self.repository.intelligence_for_session(
            self.tenant.organisation_id,
            record.debrief_session.id,
        )
        brain = (
            await self.repository.brain_for_intelligence(self.tenant.organisation_id, intelligence.id)
            if intelligence is not None
            else None
        )
        current = (
            DebriefQuestion.model_validate(record.debrief_session.current_question_json)
            if record.debrief_session.current_question_json is not None
            else None
        )
        return DebriefSessionResponse(
            id=record.debrief_session.id,
            interaction_id=record.debrief_session.interaction_id,
            capture_type=cast(DebriefCaptureType, record.capture_session.capture_type),
            lifecycle_status=cast(DebriefLifecycleStatus, record.debrief_session.lifecycle_status),
            question_count=record.debrief_session.question_count,
            max_questions=record.debrief_session.max_questions,
            current_question=current,
            can_finish=bool(turns) and record.debrief_session.lifecycle_status == "collecting",
            finished_early=record.debrief_session.finished_early,
            turns=[
                DebriefTurnResponse(
                    id=item.id,
                    turn_number=item.turn_number,
                    question=DebriefQuestion.model_validate(item.question_json),
                    answer_text=item.answer_text,
                    input_mode=cast(DebriefInputMode, item.input_mode),
                    created_at=item.created_at,
                )
                for item in turns
            ],
            candidates=[self._candidate_response(item) for item in candidates],
            interaction_intelligence_id=intelligence.id if intelligence is not None else None,
            revenue_brain_snapshot_id=brain.id if brain is not None else None,
            started_at=record.capture_session.started_at or record.debrief_session.created_at,
            updated_at=record.debrief_session.updated_at,
            completed_at=record.debrief_session.completed_at,
        )

    async def _review_response(self, record: DebriefSessionRecord) -> DebriefReviewResponse:
        base = await self._response(record)
        accepted = sum(item.user_review_state == "accepted" for item in base.candidates)
        rejected = sum(item.user_review_state == "rejected" for item in base.candidates)
        return DebriefReviewResponse(
            **base.model_dump(),
            accepted_count=accepted,
            rejected_count=rejected,
            interaction_updated=base.interaction_intelligence_id is not None,
            revenue_brain_updated=base.revenue_brain_snapshot_id is not None,
        )

    async def _require_completed_interaction(self, interaction_id: UUID) -> Interaction:
        interaction = await self.repository.get_interaction(self.tenant.organisation_id, interaction_id)
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        if interaction.lifecycle_status != "completed":
            raise PublicAPIError(
                "interaction_not_completed",
                "Complete the customer interaction before starting a post-interaction debrief.",
                409,
            )
        return interaction

    async def _require_session(
        self,
        interaction_id: UUID,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> DebriefSessionRecord:
        record = await self.repository.get_session(
            self.tenant.organisation_id,
            interaction_id,
            session_id,
            for_update=for_update,
        )
        if record is None or record.debrief_session.started_by_user_id != self.tenant.user_id:
            raise PublicAPIError("debrief_not_found", "The requested debrief session was not found.", 404)
        return record

    def _candidate_response(self, item: CandidateEvidence) -> CandidateEvidenceResponse:
        return CandidateEvidenceResponse(
            id=item.id,
            evidence_category=cast(CandidateEvidenceCategory, item.evidence_category),
            statement=item.statement,
            original_statement=item.original_statement,
            origin="salesperson_reported",
            support_classification="reported",
            validation_state=cast(CandidateValidationState, item.validation_state),
            user_review_state=cast(CandidateReviewState, item.review_state),
            source_capture_session_id=item.session_id,
            evidence_fragment_id=item.source_fragment_id,
            accepted_evidence_id=item.accepted_evidence_id,
            entity_reference=item.entity_reference,
            explicitly_reported_at=item.explicitly_reported_at,
            edited=item.statement != item.original_statement,
        )

    def _event(self, event_type: str, session_id: UUID, metadata: dict[str, object]) -> None:
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=session_id,
                metadata_json=metadata,
            )
        )

    async def _commit_before_provider(self, message: str) -> None:
        """Commit persisted input before a provider call, leaving no open transaction."""

        try:
            await self.session.flush()
            await self.session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            logger.warning(
                "debrief_persistence_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "error_code": "debrief_persistence_failed",
                },
            )
            raise PublicAPIError("persistence_failure", message, 500) from exc

    async def _fail_provider_processing(
        self,
        interaction_id: UUID,
        session_id: UUID,
        error_code: str,
    ) -> None:
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        record = await self._require_session(interaction_id, session_id, for_update=True)
        if record.debrief_session.lifecycle_status != "processing":
            return
        now = datetime.now(UTC)
        record.debrief_session.lifecycle_status = "failed"
        record.debrief_session.failure_code = error_code[:100]
        record.debrief_session.completed_at = now
        record.capture_session.status = "failed"
        record.capture_session.completed_at = now
        self._event("debrief_processing_failed", session_id, {"error_code": error_code[:100]})
        await self._commit("The debrief failure state could not be saved.")

    async def _commit(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            logger.warning(
                "debrief_persistence_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "error_code": "debrief_persistence_failed",
                },
            )
            raise PublicAPIError("persistence_failure", message, 500) from exc

    @staticmethod
    def _fingerprint(statement: str) -> str:
        normalised = " ".join(statement.lower().split())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    @staticmethod
    def _invalid_state(action: str, state: str) -> PublicAPIError:
        return PublicAPIError(
            "invalid_debrief_transition",
            f"A debrief in {state} cannot {action}.",
            409,
        )
