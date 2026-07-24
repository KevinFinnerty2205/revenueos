from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH,
    BUYING_SIGNALS_SCHEMA_VERSION,
    BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    DECISIONS_SCHEMA_VERSION,
    DECISIONS_TRANSCRIPT_MAX_LENGTH,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH,
    FOLLOW_UP_EMAIL_SCHEMA_VERSION,
    NEXT_BEST_ACTION_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
    STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH,
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    FollowUpEmailArtifactContent,
    NextBestActionArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.ai_prompt_registry import (
    ACTION_ITEMS_PROMPT_KEY,
    ACTION_ITEMS_PROMPT_VERSION,
    BUYING_SIGNALS_PROMPT_KEY,
    BUYING_SIGNALS_PROMPT_VERSION,
    DECISIONS_PROMPT_KEY,
    DECISIONS_PROMPT_VERSION,
    EXECUTIVE_SUMMARY_PROMPT_KEY,
    EXECUTIVE_SUMMARY_PROMPT_VERSION,
    FOLLOW_UP_EMAIL_PROMPT_KEY,
    FOLLOW_UP_EMAIL_PROMPT_VERSION,
    NEXT_BEST_ACTION_PROMPT_KEY,
    NEXT_BEST_ACTION_PROMPT_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
    OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
    OPEN_QUESTIONS_PROMPT_KEY,
    OPEN_QUESTIONS_PROMPT_VERSION,
    RISKS_BLOCKERS_PROMPT_KEY,
    RISKS_BLOCKERS_PROMPT_VERSION,
    STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
    STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
)
from revenueos.ai_repositories import AIArtifactRepository, AIJobRepository
from revenueos.ai_services import AIJobRequestResult, AIJobService
from revenueos.database import set_tenant_database_context
from revenueos.domain import AIArtifactType, AIJobStatus, AIJobType, FollowUpEmailTone
from revenueos.errors import PublicAPIError
from revenueos.intelligence_contracts import (
    ActionItemsContentResponse,
    BuyingSignalsContentResponse,
    DecisionsContentResponse,
    ExecutiveSummaryContentResponse,
    FollowUpEmailContentResponse,
    MeetingIntelligenceActionItemsResponse,
    MeetingIntelligenceBuyingSignalsResponse,
    MeetingIntelligenceDecisionsResponse,
    MeetingIntelligenceExecutiveSummaryResponse,
    MeetingIntelligenceFollowUpEmailResponse,
    MeetingIntelligenceGenerationResponse,
    MeetingIntelligenceNextBestActionResponse,
    MeetingIntelligenceObjectionsCompetitiveSignalsResponse,
    MeetingIntelligenceOpenQuestionsResponse,
    MeetingIntelligenceOverallState,
    MeetingIntelligenceProgressResponse,
    MeetingIntelligenceResponse,
    MeetingIntelligenceRisksBlockersResponse,
    MeetingIntelligenceStakeholderIntelligenceResponse,
    NextBestActionContentResponse,
    ObjectionsCompetitiveSignalsContentResponse,
    OpenQuestionsContentResponse,
    RisksBlockersContentResponse,
    StakeholderIntelligenceContentResponse,
)
from revenueos.models import AIArtifact, AIJob, Transcript
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.intelligence_workspace")

CapabilityName = Literal[
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "next_best_action",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
    "follow_up_email",
]
CapabilityState = Literal[
    "unavailable",
    "not_generated",
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
]


@dataclass(frozen=True)
class CapabilityConfiguration:
    name: CapabilityName
    job_type: str
    artifact_type: str
    prompt_key: str
    prompt_version: int
    schema_version: int
    label: str
    transcript_max_length: int | None


@dataclass(frozen=True)
class CapabilitySnapshot:
    state: CapabilityState
    generation_available: bool
    message: str | None
    generated_at: datetime | None
    empty_result: bool
    content: BaseModel | None
    tone: FollowUpEmailTone | None
    job: AIJob | None


@dataclass(frozen=True)
class GenerationResult:
    response: MeetingIntelligenceGenerationResponse
    created_count: int


CAPABILITIES = (
    CapabilityConfiguration(
        "executive_summary",
        AIJobType.EXECUTIVE_SUMMARY.value,
        AIArtifactType.EXECUTIVE_SUMMARY.value,
        EXECUTIVE_SUMMARY_PROMPT_KEY,
        EXECUTIVE_SUMMARY_PROMPT_VERSION,
        EXECUTIVE_SUMMARY_SCHEMA_VERSION,
        "Executive Summary",
        EXECUTIVE_SUMMARY_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "buying_signals",
        AIJobType.BUYING_SIGNALS.value,
        AIArtifactType.BUYING_SIGNALS.value,
        BUYING_SIGNALS_PROMPT_KEY,
        BUYING_SIGNALS_PROMPT_VERSION,
        BUYING_SIGNALS_SCHEMA_VERSION,
        "Buying Signals",
        BUYING_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "objections_competitive_signals",
        AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
        AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
        OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_KEY,
        OBJECTIONS_COMPETITIVE_SIGNALS_PROMPT_VERSION,
        OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
        "Objections & Competitive Signals",
        OBJECTIONS_COMPETITIVE_SIGNALS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "stakeholder_intelligence",
        AIJobType.STAKEHOLDER_INTELLIGENCE.value,
        AIArtifactType.STAKEHOLDER_INTELLIGENCE.value,
        STAKEHOLDER_INTELLIGENCE_PROMPT_KEY,
        STAKEHOLDER_INTELLIGENCE_PROMPT_VERSION,
        STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
        "Stakeholder Intelligence",
        STAKEHOLDER_INTELLIGENCE_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "decisions",
        AIJobType.DECISIONS.value,
        AIArtifactType.DECISIONS.value,
        DECISIONS_PROMPT_KEY,
        DECISIONS_PROMPT_VERSION,
        DECISIONS_SCHEMA_VERSION,
        "Decisions",
        DECISIONS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "action_items",
        AIJobType.ACTION_ITEMS.value,
        AIArtifactType.ACTION_ITEMS.value,
        ACTION_ITEMS_PROMPT_KEY,
        ACTION_ITEMS_PROMPT_VERSION,
        ACTION_ITEMS_SCHEMA_VERSION,
        "Action Items",
        ACTION_ITEMS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "risks_blockers",
        AIJobType.RISKS_BLOCKERS.value,
        AIArtifactType.RISKS_BLOCKERS.value,
        RISKS_BLOCKERS_PROMPT_KEY,
        RISKS_BLOCKERS_PROMPT_VERSION,
        RISKS_BLOCKERS_SCHEMA_VERSION,
        "Risks & Blockers",
        RISKS_BLOCKERS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "open_questions",
        AIJobType.OPEN_QUESTIONS.value,
        AIArtifactType.OPEN_QUESTIONS.value,
        OPEN_QUESTIONS_PROMPT_KEY,
        OPEN_QUESTIONS_PROMPT_VERSION,
        OPEN_QUESTIONS_SCHEMA_VERSION,
        "Open Questions",
        OPEN_QUESTIONS_TRANSCRIPT_MAX_LENGTH,
    ),
    CapabilityConfiguration(
        "next_best_action",
        AIJobType.NEXT_BEST_ACTION.value,
        AIArtifactType.NEXT_BEST_ACTION.value,
        NEXT_BEST_ACTION_PROMPT_KEY,
        NEXT_BEST_ACTION_PROMPT_VERSION,
        NEXT_BEST_ACTION_SCHEMA_VERSION,
        "Next Best Action",
        None,
    ),
    CapabilityConfiguration(
        "follow_up_email",
        AIJobType.FOLLOW_UP_EMAIL.value,
        AIArtifactType.FOLLOW_UP_EMAIL.value,
        FOLLOW_UP_EMAIL_PROMPT_KEY,
        FOLLOW_UP_EMAIL_PROMPT_VERSION,
        FOLLOW_UP_EMAIL_SCHEMA_VERSION,
        "Follow-up Email",
        None,
    ),
)
CONFIG_BY_NAME = {configuration.name: configuration for configuration in CAPABILITIES}
EXTRACTION_NAMES: tuple[CapabilityName, ...] = (
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
)
FOLLOW_UP_EMAIL_PREREQUISITES: tuple[CapabilityName, ...] = (
    "executive_summary",
    "decisions",
    "action_items",
    "open_questions",
)
NEXT_BEST_ACTION_PREREQUISITES: tuple[CapabilityName, ...] = (
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "decisions",
    "action_items",
    "risks_blockers",
    "open_questions",
)


class MeetingIntelligenceService:
    """Tenant-scoped aggregate read model and small generation orchestrator."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant
        self.jobs = AIJobRepository(session)
        self.artifacts = AIArtifactRepository(session)
        self.capabilities = AIJobService(session, tenant, job_repository=self.jobs)

    async def get_workspace(
        self,
        meeting_id: UUID,
        *,
        previous_overall_state: MeetingIntelligenceOverallState | None = None,
        polling_event: Literal["started", "continued"] | None = None,
    ) -> MeetingIntelligenceResponse:
        response, _ = await self._read_workspace(meeting_id)
        context = self._log_context(meeting_id, response)
        if previous_overall_state is None and polling_event is None:
            logger.info("unified_intelligence_page_viewed", extra=context)
        logger.info("meeting_intelligence_capability_state_count", extra=context)
        if previous_overall_state is not None and previous_overall_state != response.overall_state:
            logger.info(
                "meeting_intelligence_overall_state_transition",
                extra={
                    **context,
                    "previous_overall_state": previous_overall_state,
                },
            )
        if polling_event == "started":
            logger.info(
                "unified_intelligence_polling_started",
                extra={**context, "polling_event": polling_event},
            )
        if polling_event is not None and response.progress.queued == 0 and response.progress.processing == 0:
            logger.info(
                "unified_intelligence_polling_stopped",
                extra={**context, "polling_event": polling_event},
            )
        if response.overall_state == "partially_failed" and previous_overall_state != response.overall_state:
            logger.info("meeting_intelligence_partial_failure", extra=context)
        if response.overall_state in {"completed", "completed_with_empty_results"} and (
            previous_overall_state != response.overall_state
        ):
            logger.info("meeting_intelligence_all_completed", extra=context)
        return response

    async def generate(self, meeting_id: UUID) -> GenerationResult:
        logger.info(
            "meeting_intelligence_generation_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
            },
        )
        created: list[CapabilityName] = []
        reused: list[CapabilityName] = []
        requesters = {
            "executive_summary": self.capabilities.request_executive_summary,
            "buying_signals": self.capabilities.request_buying_signals,
            "objections_competitive_signals": self.capabilities.request_objections_competitive_signals,
            "stakeholder_intelligence": self.capabilities.request_stakeholder_intelligence,
            "decisions": self.capabilities.request_decisions,
            "action_items": self.capabilities.request_action_items,
            "risks_blockers": self.capabilities.request_risks_blockers,
            "open_questions": self.capabilities.request_open_questions,
        }
        for name in EXTRACTION_NAMES:
            await self._reset_tenant_context()
            result = await requesters[name](meeting_id)
            self._record_orchestration_result(meeting_id, name, result, created, reused)

        await self._reset_tenant_context()
        intermediate, snapshots = await self._read_workspace(meeting_id)
        next_best_action_ready = all(snapshots[name].state == "completed" for name in NEXT_BEST_ACTION_PREREQUISITES)
        next_best_action_state = snapshots["next_best_action"].state
        if next_best_action_ready and next_best_action_state in {
            "not_generated",
            "failed",
            "cancelled",
        }:
            logger.info(
                "next_best_action_prerequisites_satisfied",
                extra=self._log_context(meeting_id, intermediate),
            )
            await self._reset_tenant_context()
            next_best_action_result = await self.capabilities.request_next_best_action(meeting_id)
            self._record_orchestration_result(
                meeting_id,
                "next_best_action",
                next_best_action_result,
                created,
                reused,
            )
        elif next_best_action_state in {
            "queued",
            "processing",
            "completed",
        }:
            reused.append("next_best_action")
            logger.info(
                "meeting_intelligence_orchestration_reused_job",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "meeting_id": str(meeting_id),
                    "job_type": AIJobType.NEXT_BEST_ACTION.value,
                    "reused_count": 1,
                },
            )

        prerequisites_ready = all(snapshots[name].state == "completed" for name in FOLLOW_UP_EMAIL_PREREQUISITES)
        email_state = snapshots["follow_up_email"].state
        if prerequisites_ready and email_state in {
            "not_generated",
            "failed",
            "cancelled",
        }:
            logger.info(
                "meeting_intelligence_composer_prerequisites_satisfied",
                extra=self._log_context(meeting_id, intermediate),
            )
            await self._reset_tenant_context()
            email_result = await self.capabilities.request_follow_up_email(
                meeting_id,
                FollowUpEmailTone.PROFESSIONAL,
            )
            self._record_orchestration_result(
                meeting_id,
                "follow_up_email",
                email_result,
                created,
                reused,
            )
        elif email_state in {"queued", "processing", "completed"}:
            reused.append("follow_up_email")
            logger.info(
                "meeting_intelligence_orchestration_reused_job",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "meeting_id": str(meeting_id),
                    "job_type": AIJobType.FOLLOW_UP_EMAIL.value,
                    "reused_count": 1,
                },
            )

        await self._reset_tenant_context()
        final, _ = await self._read_workspace(meeting_id)
        response = MeetingIntelligenceGenerationResponse(
            **final.model_dump(),
            created_capabilities=created,
            reused_capabilities=reused,
        )
        logger.info(
            "meeting_intelligence_orchestration_completed",
            extra={
                **self._log_context(meeting_id, final),
                "created_count": len(created),
                "reused_count": len(reused),
            },
        )
        return GenerationResult(response=response, created_count=len(created))

    async def _read_workspace(
        self,
        meeting_id: UUID,
    ) -> tuple[MeetingIntelligenceResponse, dict[CapabilityName, CapabilitySnapshot]]:
        meeting = await self.jobs.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        transcript = await self.jobs.get_transcript_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if transcript is None:
            unavailable = self._unavailable_snapshots(None)
            return self._response(unavailable, transcript_usable=False), unavailable

        jobs = await self.jobs.list_intelligence_jobs_for_meeting(
            self.tenant.organisation_id,
            meeting_id,
            transcript.version,
            [configuration.job_type for configuration in CAPABILITIES],
        )
        selected_jobs = {
            configuration.name: self._latest_equivalent_job(jobs, configuration) for configuration in CAPABILITIES
        }
        artifacts = await self.artifacts.list_intelligence_artifacts_for_jobs(
            self.tenant.organisation_id,
            meeting_id,
            transcript.version,
            [job.id for job in selected_jobs.values() if job is not None],
        )
        artifacts_by_job = self._latest_artifacts_by_job(artifacts)
        transcript_usable = all(
            self._unavailable_reason(configuration, transcript) is None
            for configuration in CAPABILITIES
            if configuration.transcript_max_length is not None
        )
        if not transcript_usable:
            unavailable = self._unavailable_snapshots(transcript)
            return self._response(unavailable, transcript_usable=False), unavailable

        snapshots: dict[CapabilityName, CapabilitySnapshot] = {}
        for name in EXTRACTION_NAMES:
            configuration = CONFIG_BY_NAME[name]
            snapshots[configuration.name] = self._snapshot(
                configuration,
                selected_jobs[configuration.name],
                artifacts_by_job,
                generation_available_when_empty=True,
            )
        next_best_action_prerequisites_ready = all(
            snapshots[name].state == "completed" for name in NEXT_BEST_ACTION_PREREQUISITES
        )
        next_best_action_configuration = CONFIG_BY_NAME["next_best_action"]
        next_best_action_job = selected_jobs["next_best_action"]
        if next_best_action_job is None and not next_best_action_prerequisites_ready:
            snapshots["next_best_action"] = CapabilitySnapshot(
                state="unavailable",
                generation_available=False,
                message=("This section will be recommended after all validated Meeting Intelligence inputs are ready."),
                generated_at=None,
                empty_result=False,
                content=None,
                tone=None,
                job=None,
            )
        else:
            snapshots["next_best_action"] = self._snapshot(
                next_best_action_configuration,
                next_best_action_job,
                artifacts_by_job,
                generation_available_when_empty=(next_best_action_prerequisites_ready),
            )
        prerequisites_ready = all(snapshots[name].state == "completed" for name in FOLLOW_UP_EMAIL_PREREQUISITES)
        email_configuration = CONFIG_BY_NAME["follow_up_email"]
        email_job = selected_jobs["follow_up_email"]
        if email_job is None and not prerequisites_ready:
            snapshots["follow_up_email"] = CapabilitySnapshot(
                state="unavailable",
                generation_available=False,
                message=(
                    "This section will be drafted after Executive Summary, Decisions, "
                    "Action Items and Open Questions are ready."
                ),
                generated_at=None,
                empty_result=False,
                content=None,
                tone=None,
                job=None,
            )
        else:
            snapshots["follow_up_email"] = self._snapshot(
                email_configuration,
                email_job,
                artifacts_by_job,
                generation_available_when_empty=prerequisites_ready,
            )
        return self._response(snapshots, transcript_usable=True), snapshots

    def _snapshot(
        self,
        configuration: CapabilityConfiguration,
        job: AIJob | None,
        artifacts_by_job: dict[tuple[UUID, str], AIArtifact],
        *,
        generation_available_when_empty: bool,
    ) -> CapabilitySnapshot:
        if job is None:
            return CapabilitySnapshot(
                state="not_generated",
                generation_available=generation_available_when_empty,
                message=None,
                generated_at=None,
                empty_result=False,
                content=None,
                tone=None,
                job=None,
            )
        state = cast(
            CapabilityState,
            {
                AIJobStatus.PENDING.value: "queued",
                AIJobStatus.RUNNING.value: "processing",
                AIJobStatus.COMPLETED.value: "completed",
                AIJobStatus.FAILED.value: "failed",
                AIJobStatus.CANCELLED.value: "cancelled",
            }[job.status],
        )
        artifact = artifacts_by_job.get((job.id, configuration.artifact_type))
        content: BaseModel | None = None
        empty_result = False
        if state == "completed" and artifact is not None:
            if (
                artifact.prompt_key != configuration.prompt_key
                or artifact.prompt_version != configuration.prompt_version
                or artifact.schema_version != configuration.schema_version
            ):
                state = "failed"
            else:
                try:
                    content, empty_result = self._validated_content(
                        configuration.name,
                        artifact,
                    )
                except ValidationError:
                    state = "failed"
        elif state == "completed":
            state = "failed"

        message = None
        if state == "failed":
            message = job.last_error_message_safe or f"{configuration.label} could not be completed."
        elif state == "cancelled":
            message = job.last_error_message_safe or f"{configuration.label} generation was cancelled."
        generation_available = state in {"failed", "cancelled"} or (
            state == "completed" and configuration.name == "follow_up_email"
        )
        tone = (
            FollowUpEmailTone(job.composition_tone)
            if configuration.name == "follow_up_email" and job.composition_tone is not None
            else None
        )
        return CapabilitySnapshot(
            state=state,
            generation_available=generation_available,
            message=message,
            generated_at=artifact.created_at if state == "completed" and artifact is not None else None,
            empty_result=empty_result,
            content=content,
            tone=tone,
            job=job,
        )

    @staticmethod
    def _validated_content(
        name: CapabilityName,
        artifact: AIArtifact,
    ) -> tuple[BaseModel, bool]:
        if name == "executive_summary":
            summary = ExecutiveSummaryArtifactContent.model_validate(artifact.content_json)
            return ExecutiveSummaryContentResponse.model_validate(summary), False
        if name == "buying_signals":
            signals = BuyingSignalsArtifactContent.model_validate(artifact.content_json)
            return (
                BuyingSignalsContentResponse.model_validate(signals),
                len(signals.signals) == 0 or signals.overall_momentum == "insufficient_evidence",
            )
        if name == "objections_competitive_signals":
            objection_signals = ObjectionsCompetitiveSignalsArtifactContent.model_validate(artifact.content_json)
            return (
                ObjectionsCompetitiveSignalsContentResponse.model_validate(objection_signals),
                len(objection_signals.objections) == 0 and len(objection_signals.competitors) == 0,
            )
        if name == "stakeholder_intelligence":
            stakeholders = StakeholderIntelligenceArtifactContent.model_validate(artifact.content_json)
            return (
                StakeholderIntelligenceContentResponse.model_validate(stakeholders),
                len(stakeholders.stakeholders) == 0,
            )
        if name == "next_best_action":
            recommendation = NextBestActionArtifactContent.model_validate(artifact.content_json)
            return (
                NextBestActionContentResponse.model_validate(recommendation),
                False,
            )
        if name == "decisions":
            decisions = DecisionsArtifactContent.model_validate(artifact.content_json)
            return DecisionsContentResponse.model_validate(decisions), len(decisions.decisions) == 0
        if name == "action_items":
            action_items = ActionItemsArtifactContent.model_validate(artifact.content_json)
            return (
                ActionItemsContentResponse.model_validate(action_items),
                len(action_items.action_items) == 0,
            )
        if name == "risks_blockers":
            risks = RisksBlockersArtifactContent.model_validate(artifact.content_json)
            return RisksBlockersContentResponse.model_validate(risks), len(risks.risks) == 0
        if name == "open_questions":
            questions = OpenQuestionsArtifactContent.model_validate(artifact.content_json)
            return (
                OpenQuestionsContentResponse.model_validate(questions),
                len(questions.open_questions) == 0,
            )
        email = FollowUpEmailArtifactContent.model_validate(artifact.content_json)
        return FollowUpEmailContentResponse.model_validate(email), False

    def _response(
        self,
        snapshots: dict[CapabilityName, CapabilitySnapshot],
        *,
        transcript_usable: bool,
    ) -> MeetingIntelligenceResponse:
        states = [snapshot.state for snapshot in snapshots.values()]
        ready = states.count("completed")
        queued = states.count("queued")
        processing = states.count("processing")
        failed = states.count("failed") + states.count("cancelled")
        not_generated = states.count("not_generated") + states.count("unavailable")
        overall_state = self._overall_state(
            transcript_usable=transcript_usable,
            ready=ready,
            queued=queued,
            processing=processing,
            failed=failed,
            any_empty_result=any(snapshot.empty_result for snapshot in snapshots.values()),
        )
        progress = MeetingIntelligenceProgressResponse(
            ready=ready,
            queued=queued,
            processing=processing,
            failed=failed,
            not_generated=not_generated,
            summary=self._progress_summary(
                ready=ready,
                queued=queued,
                processing=processing,
                failed=failed,
            ),
        )
        updated_values = [
            value
            for snapshot in snapshots.values()
            for value in (
                snapshot.generated_at,
                snapshot.job.completed_at if snapshot.job is not None else None,
                snapshot.job.started_at if snapshot.job is not None else None,
                snapshot.job.created_at if snapshot.job is not None else None,
            )
            if value is not None
        ]
        generation_available = (
            transcript_usable
            and queued == 0
            and processing == 0
            and overall_state not in {"completed", "completed_with_empty_results"}
        )
        return MeetingIntelligenceResponse(
            overall_state=overall_state,
            generation_available=generation_available,
            retry_available=failed > 0 and queued == 0 and processing == 0,
            last_updated_at=max(updated_values) if updated_values else None,
            progress=progress,
            executive_summary=MeetingIntelligenceExecutiveSummaryResponse.model_validate(
                {
                    **self._capability_fields(snapshots["executive_summary"]),
                    "content": snapshots["executive_summary"].content,
                }
            ),
            buying_signals=MeetingIntelligenceBuyingSignalsResponse.model_validate(
                {
                    **self._capability_fields(snapshots["buying_signals"]),
                    "content": snapshots["buying_signals"].content,
                }
            ),
            objections_competitive_signals=(
                MeetingIntelligenceObjectionsCompetitiveSignalsResponse.model_validate(
                    {
                        **self._capability_fields(snapshots["objections_competitive_signals"]),
                        "content": snapshots["objections_competitive_signals"].content,
                    }
                )
            ),
            stakeholder_intelligence=MeetingIntelligenceStakeholderIntelligenceResponse.model_validate(
                {
                    **self._capability_fields(snapshots["stakeholder_intelligence"]),
                    "content": snapshots["stakeholder_intelligence"].content,
                }
            ),
            next_best_action=MeetingIntelligenceNextBestActionResponse.model_validate(
                {
                    **self._capability_fields(snapshots["next_best_action"]),
                    "content": snapshots["next_best_action"].content,
                }
            ),
            decisions=MeetingIntelligenceDecisionsResponse.model_validate(
                {
                    **self._capability_fields(snapshots["decisions"]),
                    "content": snapshots["decisions"].content,
                }
            ),
            action_items=MeetingIntelligenceActionItemsResponse.model_validate(
                {
                    **self._capability_fields(snapshots["action_items"]),
                    "content": snapshots["action_items"].content,
                }
            ),
            risks_blockers=MeetingIntelligenceRisksBlockersResponse.model_validate(
                {
                    **self._capability_fields(snapshots["risks_blockers"]),
                    "content": snapshots["risks_blockers"].content,
                }
            ),
            open_questions=MeetingIntelligenceOpenQuestionsResponse.model_validate(
                {
                    **self._capability_fields(snapshots["open_questions"]),
                    "content": snapshots["open_questions"].content,
                }
            ),
            follow_up_email=MeetingIntelligenceFollowUpEmailResponse.model_validate(
                {
                    **self._capability_fields(snapshots["follow_up_email"]),
                    "tone": snapshots["follow_up_email"].tone,
                    "content": snapshots["follow_up_email"].content,
                }
            ),
        )

    @staticmethod
    def _capability_fields(snapshot: CapabilitySnapshot) -> dict[str, object]:
        return {
            "state": snapshot.state,
            "generation_available": snapshot.generation_available,
            "message": snapshot.message,
            "generated_at": snapshot.generated_at,
            "empty_result": snapshot.empty_result,
        }

    @staticmethod
    def _overall_state(
        *,
        transcript_usable: bool,
        ready: int,
        queued: int,
        processing: int,
        failed: int,
        any_empty_result: bool,
    ) -> MeetingIntelligenceOverallState:
        if not transcript_usable:
            return "unavailable"
        if processing > 0:
            return "processing"
        if failed > 0 and ready > 0:
            return "partially_failed"
        if failed > 0:
            return "failed"
        if queued > 0:
            return "queued"
        if ready == len(CAPABILITIES):
            return "completed_with_empty_results" if any_empty_result else "completed"
        if ready > 0:
            return "partially_generated"
        return "not_started"

    @staticmethod
    def _progress_summary(
        *,
        ready: int,
        queued: int,
        processing: int,
        failed: int,
    ) -> str:
        if processing > 0:
            active = processing + queued
            return f"Generating {active} section{'s' if active != 1 else ''}"
        if failed > 0 and ready > 0:
            return f"{ready} ready · {failed} failed"
        if failed > 0:
            return f"{failed} section{'s' if failed != 1 else ''} failed"
        if queued > 0:
            return f"{queued} section{'s' if queued != 1 else ''} queued"
        return f"{ready} of {len(CAPABILITIES)} ready"

    def _unavailable_snapshots(
        self,
        transcript: Transcript | None,
    ) -> dict[CapabilityName, CapabilitySnapshot]:
        snapshots: dict[CapabilityName, CapabilitySnapshot] = {}
        for name in EXTRACTION_NAMES:
            configuration = CONFIG_BY_NAME[name]
            snapshots[configuration.name] = CapabilitySnapshot(
                state="unavailable",
                generation_available=False,
                message=self._unavailable_reason(configuration, transcript),
                generated_at=None,
                empty_result=False,
                content=None,
                tone=None,
                job=None,
            )
        snapshots["next_best_action"] = CapabilitySnapshot(
            state="unavailable",
            generation_available=False,
            message=(
                "Add a usable transcript and generate all validated Meeting "
                "Intelligence inputs before requesting Next Best Action."
            ),
            generated_at=None,
            empty_result=False,
            content=None,
            tone=None,
            job=None,
        )
        snapshots["follow_up_email"] = CapabilitySnapshot(
            state="unavailable",
            generation_available=False,
            message=(
                "Add a usable transcript and generate the required Meeting Intelligence "
                "before drafting a follow-up email."
            ),
            generated_at=None,
            empty_result=False,
            content=None,
            tone=None,
            job=None,
        )
        return snapshots

    @staticmethod
    def _unavailable_reason(
        configuration: CapabilityConfiguration,
        transcript: Transcript | None,
    ) -> str | None:
        if configuration.transcript_max_length is None:
            return None
        if transcript is None or not transcript.raw_text.strip():
            return f"Add a usable transcript before generating {configuration.label}."
        if len(transcript.raw_text.strip()) > configuration.transcript_max_length:
            return (
                f"This transcript exceeds the {configuration.transcript_max_length:,}-character "
                f"{configuration.label} processing limit."
            )
        return None

    @staticmethod
    def _latest_equivalent_job(
        jobs: list[AIJob],
        configuration: CapabilityConfiguration,
    ) -> AIJob | None:
        candidates = [
            job
            for job in jobs
            if job.job_type == configuration.job_type
            and job.prompt_key == configuration.prompt_key
            and job.prompt_version == configuration.prompt_version
            and job.schema_version == configuration.schema_version
        ]
        if not candidates:
            return None
        if configuration.name == "follow_up_email":
            return max(
                candidates,
                key=lambda job: (job.created_at, str(job.id)),
            )
        return max(
            candidates,
            key=lambda job: (
                job.created_at,
                len(job.idempotency_key or ""),
                job.idempotency_key or "",
                str(job.id),
            ),
        )

    @staticmethod
    def _latest_artifacts_by_job(
        artifacts: list[AIArtifact],
    ) -> dict[tuple[UUID, str], AIArtifact]:
        selected: dict[tuple[UUID, str], AIArtifact] = {}
        for artifact in artifacts:
            key = (artifact.job_id, artifact.artifact_type)
            current = selected.get(key)
            if current is None or (artifact.artifact_version, str(artifact.id)) > (
                current.artifact_version,
                str(current.id),
            ):
                selected[key] = artifact
        return selected

    def _record_orchestration_result(
        self,
        meeting_id: UUID,
        name: CapabilityName,
        result: AIJobRequestResult,
        created: list[CapabilityName],
        reused: list[CapabilityName],
    ) -> None:
        target = created if result.created else reused
        target.append(name)
        logger.info(
            (
                "meeting_intelligence_orchestration_created_job"
                if result.created
                else "meeting_intelligence_orchestration_reused_job"
            ),
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "meeting_id": str(meeting_id),
                "job_type": result.job.job_type,
                "created_count": int(result.created),
                "reused_count": int(not result.created),
            },
        )

    async def _reset_tenant_context(self) -> None:
        await set_tenant_database_context(
            self.session,
            self.tenant.organisation_id,
        )

    def _log_context(
        self,
        meeting_id: UUID,
        response: MeetingIntelligenceResponse,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(self.tenant.organisation_id),
            "meeting_id": str(meeting_id),
            "overall_state": response.overall_state,
            "ready_count": response.progress.ready,
            "queued_count": response.progress.queued,
            "processing_count": response.progress.processing,
            "failed_count": response.progress.failed,
            "not_generated_count": response.progress.not_generated,
        }
