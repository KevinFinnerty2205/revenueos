from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    NextBestActionArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, PreInteractionBrief
from revenueos.pre_interaction_contracts import (
    BriefCommitment,
    BriefInteractionType,
    BriefObjective,
    BriefParticipant,
    BriefPriority,
    BriefQuestion,
    BriefRecentChange,
    BriefRisk,
    BriefSection,
    BriefSourceCapability,
    BriefStakeholder,
    BriefState,
    BriefVersionSummary,
    PreInteractionBriefContent,
    PreInteractionBriefRequestResponse,
    PreInteractionBriefResponse,
    PreInteractionSourceReference,
)
from revenueos.pre_interaction_repositories import (
    PreInteractionBriefRepository,
    PreInteractionSourceRecords,
)
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainInsightContent
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.pre_interaction_briefs")
PRE_INTERACTION_BRIEF_SCHEMA_VERSION = 2
PRE_INTERACTION_BRIEF_HISTORY_LIMIT = 6
ValidatedModel = TypeVar("ValidatedModel", bound=BaseModel)


@dataclass(frozen=True)
class ValidatedBriefContext:
    records: PreInteractionSourceRecords
    executive_summary: ExecutiveSummaryArtifactContent | None
    buying_signals: BuyingSignalsArtifactContent | None
    objections: ObjectionsCompetitiveSignalsArtifactContent | None
    stakeholders: StakeholderIntelligenceArtifactContent | None
    decisions: DecisionsArtifactContent | None
    action_items: ActionItemsArtifactContent | None
    risks: RisksBlockersArtifactContent | None
    open_questions: OpenQuestionsArtifactContent | None
    next_best_action: NextBestActionArtifactContent | None
    revenue_brain: RevenueBrainInsightContent | None
    source_references: tuple[PreInteractionSourceReference, ...]
    fingerprint: str


class PreInteractionBriefService:
    """Build and persist deterministic briefs from current validated structured data."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = PreInteractionBriefRepository(session)
        self.beta = BetaService(session, tenant, settings)

    async def get_brief(self, interaction_id: UUID) -> PreInteractionBriefResponse:
        self.beta.require_feature("aiCompanion")
        records = await self._require_interaction(interaction_id)
        latest = await self.repository.get_latest_brief(self.tenant.organisation_id, interaction_id)
        if latest is None:
            return self._empty_response(records)
        if latest.status != "completed":
            logger.warning(
                "brief_failed_safe_code",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(interaction_id),
                    "interaction_type": records.interaction.interaction_type,
                    "brief_version": latest.brief_version,
                    "safe_code": f"brief_{latest.status}",
                },
            )
            return PreInteractionBriefResponse(
                state=cast(BriefState, latest.status),
                generation_available=True,
                unavailable_reason=None,
                safe_message=(
                    "The previous preparation attempt was cancelled. You can prepare a new version."
                    if latest.status == "cancelled"
                    else "The previous preparation attempt did not complete safely. You can try again."
                ),
                brief=None,
                generated_at=latest.created_at,
                reviewed=False,
                reviewed_at=None,
                prior_versions=[],
                source_labels=[],
            )
        response = await self._completed_response(latest)
        logger.info(
            "brief_viewed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": records.interaction.interaction_type,
                "brief_version": latest.brief_version,
            },
        )
        return response

    async def generate_brief(self, interaction_id: UUID) -> PreInteractionBriefRequestResponse:
        self.beta.require_feature("aiCompanion")
        records = await self._require_interaction(interaction_id, for_update=True)
        logger.info(
            "brief_requested",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": records.interaction.interaction_type,
            },
        )
        if records.company is None and records.opportunity is None:
            logger.info(
                "insufficient_context",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(interaction_id),
                    "interaction_type": records.interaction.interaction_type,
                },
            )
            return PreInteractionBriefRequestResponse(
                **self._empty_response(records).model_dump(),
                created=False,
            )
        context = self._build_context(records)
        existing = await self.repository.get_equivalent_brief(
            self.tenant.organisation_id,
            interaction_id,
            context.fingerprint,
            PRE_INTERACTION_BRIEF_SCHEMA_VERSION,
        )
        if existing is not None:
            logger.info(
                "existing_brief_reused",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(interaction_id),
                    "interaction_type": records.interaction.interaction_type,
                    "brief_version": existing.brief_version,
                },
            )
            return PreInteractionBriefRequestResponse(
                **(await self._completed_response(existing)).model_dump(),
                created=False,
            )

        await self.beta.require_notice_acknowledgement()
        await self.beta.reserve_generation()
        brief_version = await self.repository.next_version(self.tenant.organisation_id, interaction_id)
        logger.info(
            "brief_generation_started",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": records.interaction.interaction_type,
                "brief_version": brief_version,
            },
        )
        content = self._compose(context, brief_version)
        record = PreInteractionBrief(
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            company_id=records.company.id if records.company is not None else None,
            opportunity_id=records.opportunity.id if records.opportunity is not None else None,
            source_context_fingerprint=context.fingerprint,
            brief_version=brief_version,
            schema_version=PRE_INTERACTION_BRIEF_SCHEMA_VERSION,
            status="completed",
            content_json=content.as_json(),
            source_references_json=[reference.model_dump(mode="json") for reference in context.source_references],
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(record)
        try:
            await self.repository.flush()
            await self.repository.refresh(record)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.repository.get_equivalent_brief(
                self.tenant.organisation_id,
                interaction_id,
                context.fingerprint,
                PRE_INTERACTION_BRIEF_SCHEMA_VERSION,
            )
            if concurrent is None:
                self._log_persistence_failure(interaction_id, records, brief_version)
                raise PublicAPIError(
                    "brief_persistence_failed",
                    "The preparation brief could not be saved safely.",
                    500,
                ) from exc
            return PreInteractionBriefRequestResponse(
                **(await self._completed_response(concurrent)).model_dump(),
                created=False,
            )
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            self._log_persistence_failure(interaction_id, records, brief_version)
            raise PublicAPIError(
                "brief_persistence_failed",
                "The preparation brief could not be saved safely.",
                500,
            ) from exc

        logger.info(
            "brief_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": records.interaction.interaction_type,
                "brief_version": brief_version,
                "objective_count": len(content.objectives),
                "question_count": len(content.questions_to_ask),
                "risk_count": len(content.risks_to_watch),
            },
        )
        return PreInteractionBriefRequestResponse(
            **(await self._completed_response(record)).model_dump(),
            created=True,
        )

    async def review_brief(self, interaction_id: UUID) -> PreInteractionBriefResponse:
        self.beta.require_feature("aiCompanion")
        records = await self._require_interaction(interaction_id)
        record = await self.repository.get_latest_brief(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError(
                "brief_not_generated",
                "Prepare the interaction brief before marking it as reviewed.",
                409,
            )
        if record.status != "completed":
            raise PublicAPIError(
                "brief_not_ready",
                "The preparation brief is not ready to review.",
                409,
            )
        if record.reviewed_at is None:
            record.reviewed_at = datetime.now(UTC)
            record.reviewed_by_user_id = self.tenant.user_id
            try:
                await self.repository.commit()
            except SQLAlchemyError as exc:
                await self.repository.rollback()
                logger.error(
                    "brief_failed_safe_code",
                    extra={
                        "organisation_id": str(self.tenant.organisation_id),
                        "interaction_id": str(interaction_id),
                        "interaction_type": records.interaction.interaction_type,
                        "brief_version": record.brief_version,
                        "safe_code": "brief_review_failed",
                    },
                )
                raise PublicAPIError(
                    "brief_review_failed",
                    "The brief review state could not be saved.",
                    500,
                ) from exc
            logger.info(
                "brief_reviewed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(interaction_id),
                    "interaction_type": records.interaction.interaction_type,
                    "brief_version": record.brief_version,
                },
            )
        return await self._completed_response(record)

    def _log_persistence_failure(
        self,
        interaction_id: UUID,
        records: PreInteractionSourceRecords,
        brief_version: int,
    ) -> None:
        logger.error(
            "brief_failed_safe_code",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": records.interaction.interaction_type,
                "brief_version": brief_version,
                "safe_code": "brief_persistence_failed",
            },
        )

    async def _require_interaction(
        self,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> PreInteractionSourceRecords:
        records = await self.repository.load_source_records(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if records is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        return records

    def _build_context(self, records: PreInteractionSourceRecords) -> ValidatedBriefContext:
        artifacts = records.artifacts
        executive_summary = self._validated_artifact(
            artifacts.get("executive_summary"), ExecutiveSummaryArtifactContent
        )
        buying_signals = self._validated_artifact(artifacts.get("buying_signals"), BuyingSignalsArtifactContent)
        objections = self._validated_artifact(
            artifacts.get("objections_competitive_signals"),
            ObjectionsCompetitiveSignalsArtifactContent,
        )
        stakeholders = self._validated_artifact(
            artifacts.get("stakeholder_intelligence"), StakeholderIntelligenceArtifactContent
        )
        decisions = self._validated_artifact(artifacts.get("decisions"), DecisionsArtifactContent)
        action_items = self._validated_artifact(artifacts.get("action_items"), ActionItemsArtifactContent)
        risks = self._validated_artifact(artifacts.get("risks_blockers"), RisksBlockersArtifactContent)
        open_questions = self._validated_artifact(artifacts.get("open_questions"), OpenQuestionsArtifactContent)
        next_best_action = self._validated_artifact(artifacts.get("next_best_action"), NextBestActionArtifactContent)
        revenue_brain: RevenueBrainInsightContent | None = None
        if records.revenue_brain_insight is not None:
            try:
                revenue_brain = RevenueBrainInsightContent.model_validate_json(
                    json.dumps(records.revenue_brain_insight.content_json)
                )
            except ValidationError:
                logger.warning(
                    "brief_source_skipped",
                    extra={
                        "organisation_id": str(self.tenant.organisation_id),
                        "interaction_id": str(records.interaction.id),
                        "source_type": "revenue_brain",
                        "source_id": str(records.revenue_brain_insight.id),
                    },
                )

        validated_values = {
            "executive_summary": executive_summary,
            "buying_signals": buying_signals,
            "objections_competitive_signals": objections,
            "stakeholder_intelligence": stakeholders,
            "decisions": decisions,
            "action_items": action_items,
            "risks_blockers": risks,
            "open_questions": open_questions,
            "next_best_action": next_best_action,
        }
        validated_artifacts = {
            capability: artifacts[capability]
            for capability, value in validated_values.items()
            if value is not None and capability in artifacts
        }
        references = self._source_references(records, validated_artifacts, revenue_brain is not None)
        canonical = {
            "schema_version": PRE_INTERACTION_BRIEF_SCHEMA_VERSION,
            "interaction": {
                "id": str(records.interaction.id),
                "type": records.interaction.interaction_type,
                "title": records.interaction.title,
                "scheduled_start_at": self._iso(records.interaction.scheduled_start_at),
                "scheduled_end_at": self._iso(records.interaction.scheduled_end_at),
                "company_id": str(records.interaction.company_id) if records.interaction.company_id else None,
                "opportunity_id": (
                    str(records.interaction.opportunity_id) if records.interaction.opportunity_id else None
                ),
            },
            "company": (
                {
                    "id": str(records.company.id),
                    "name": records.company.name,
                    "industry": records.company.industry,
                    "status": records.company.status,
                }
                if records.company is not None
                else None
            ),
            "opportunity": (
                {
                    "id": str(records.opportunity.id),
                    "name": records.opportunity.name,
                    "stage": records.opportunity.stage,
                    "status": records.opportunity.status,
                    "description": records.opportunity.description,
                    "expected_close_date": (
                        records.opportunity.expected_close_date.isoformat()
                        if records.opportunity.expected_close_date is not None
                        else None
                    ),
                }
                if records.opportunity is not None
                else None
            ),
            "participants": [
                {
                    "id": str(item.participant_id),
                    "name": item.name,
                    "role": item.role,
                    "job_title": item.job_title,
                }
                for item in records.participants
            ],
            "validated_artifacts": {
                "executive_summary": self._json(executive_summary),
                "buying_signals": self._json(buying_signals),
                "objections": self._json(objections),
                "stakeholders": self._json(stakeholders),
                "decisions": self._json(decisions),
                "action_items": self._json(action_items),
                "risks": self._json(risks),
                "open_questions": self._json(open_questions),
                "next_best_action": self._json(next_best_action),
            },
            "revenue_brain": self._json(revenue_brain),
            "source_trace": {
                capability: {
                    "id": str(artifact.id),
                    "artifact_version": artifact.artifact_version,
                    "schema_version": artifact.schema_version,
                    "transcript_version": artifact.transcript_version,
                }
                for capability, artifact in sorted(validated_artifacts.items())
            },
            "revenue_brain_source_id": (
                str(records.revenue_brain_insight.id)
                if revenue_brain is not None and records.revenue_brain_insight is not None
                else None
            ),
        }
        fingerprint = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        logger.info(
            "context_built",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(records.interaction.id),
                "interaction_type": records.interaction.interaction_type,
                "source_count": len(references),
            },
        )
        return ValidatedBriefContext(
            records=records,
            executive_summary=executive_summary,
            buying_signals=buying_signals,
            objections=objections,
            stakeholders=stakeholders,
            decisions=decisions,
            action_items=action_items,
            risks=risks,
            open_questions=open_questions,
            next_best_action=next_best_action,
            revenue_brain=revenue_brain,
            source_references=references,
            fingerprint=fingerprint,
        )

    def _compose(self, context: ValidatedBriefContext, brief_version: int) -> PreInteractionBriefContent:
        objectives = self._objectives(context)
        questions = self._questions(context)
        commitments = self._commitments(context)
        risks = self._risks(context)
        stakeholders = self._stakeholders(context)
        interaction_type = context.records.interaction.interaction_type
        success_criteria = self._success_criteria(interaction_type, commitments, risks)
        return PreInteractionBriefContent(
            interaction_id=context.records.interaction.id,
            interaction_type=cast(BriefInteractionType, interaction_type),
            brief_version=brief_version,
            headline=objectives[0].objective,
            account_context=self._account_context(context),
            recent_changes=self._recent_changes(context),
            objectives=objectives,
            questions_to_ask=questions,
            stakeholder_focus=stakeholders,
            open_commitments=commitments,
            risks_to_watch=risks,
            success_criteria=success_criteria,
            interaction_guidance=self._guidance(interaction_type),
            confidence=self._confidence(context),
            company_name=(context.records.company.name if context.records.company is not None else None),
            opportunity_name=(context.records.opportunity.name if context.records.opportunity is not None else None),
            participants=tuple(
                BriefParticipant(name=item.name, role=item.role) for item in context.records.participants[:20]
            ),
            next_best_action=(
                context.next_best_action.overall_recommendation if context.next_best_action is not None else None
            ),
        )

    def _account_context(self, context: ValidatedBriefContext) -> str:
        records = context.records
        if records.opportunity is not None:
            company_name = records.company.name if records.company is not None else "The linked account"
            value = (
                f"{company_name} has the {records.opportunity.name} opportunity at the "
                f"{self._humanise(records.opportunity.stage)} stage with "
                f"{self._humanise(records.opportunity.status)} status."
            )
            if context.executive_summary is not None:
                value = f"{value} Latest validated context: {context.executive_summary.executive_summary}"
            elif not context.records.artifacts:
                value = f"{value} Limited validated interaction intelligence is currently available."
            return self._bounded(value, 1_000)
        assert records.company is not None
        return (
            f"Preparation is based on company metadata for {records.company.name}. "
            "No linked opportunity or prior validated opportunity intelligence is available."
        )

    @staticmethod
    def _recent_changes(context: ValidatedBriefContext) -> tuple[BriefRecentChange, ...]:
        if context.revenue_brain is None:
            return ()
        return tuple(
            BriefRecentChange(
                change=PreInteractionBriefService._bounded(f"{change.title}: {change.description}", 500),
                importance=change.importance,
            )
            for change in context.revenue_brain.changes
            if change.change_type != "no_material_change"
        )[:5]

    def _objectives(self, context: ValidatedBriefContext) -> tuple[BriefObjective, ...]:
        interaction_type = context.records.interaction.interaction_type
        defaults: dict[str, tuple[str, str]] = {
            "phone_call": (
                "Agree the next concrete step for this call.",
                "A short call is most useful when it closes with clear ownership and timing.",
            ),
            "presentation": (
                "Validate the audience's priorities and agree a useful next step.",
                "Seller-prepared material is context; customer response and requested evidence are what matter.",
            ),
            "workshop": (
                "Agree the workshop output, decisions and ownership.",
                "A workshop should finish with observable outputs and accountable follow-up.",
            ),
            "site_visit": (
                "Validate the operational and technical constraints relevant to the visit.",
                "Site preparation should focus on authorised observations and implementation constraints.",
            ),
            "executive_lunch": (
                "Clarify strategic priorities and an appropriate relationship next step.",
                "An executive lunch benefits from a concise strategic focus without operational overload.",
            ),
            "conference_interaction": (
                "Establish whether a focused follow-up is worthwhile.",
                "Conference conversations are short and should end with a clear follow-up criterion.",
            ),
            "trade_show_interaction": (
                "Establish whether a focused follow-up is worthwhile.",
                "Trade-show conversations are short and should end with a clear follow-up criterion.",
            ),
            "face_to_face_meeting": (
                "Clarify the most important outcome and agree the next step.",
                "Face-to-face preparation should keep priorities, stakeholders and commitments easy to scan.",
            ),
            "online_meeting": (
                "Clarify the most important outcome and agree the next step.",
                "A focused objective keeps the meeting grounded in the current opportunity context.",
            ),
            "manual_interaction": (
                "Clarify the purpose and desired outcome of this interaction.",
                "Limited interaction metadata makes an explicit outcome the safest preparation focus.",
            ),
        }
        objective, reason = defaults[interaction_type]
        values = [BriefObjective(objective=objective, priority="high", reason=reason)]
        if context.next_best_action is not None:
            for recommendation in context.next_best_action.recommended_actions:
                self._append_unique_objective(
                    values,
                    BriefObjective(
                        objective=recommendation.action,
                        priority=recommendation.priority,
                        reason=self._bounded(recommendation.reason, 500),
                    ),
                )
                if len(values) == 5:
                    break
        if context.open_questions is not None:
            for item in context.open_questions.open_questions:
                self._append_unique_objective(
                    values,
                    BriefObjective(
                        objective=self._bounded(f"Clarify {item.question.rstrip('?').lower()}.", 500),
                        priority=item.importance,
                        reason="This remains an unresolved validated question.",
                    ),
                )
                if len(values) == 5:
                    break
        if context.buying_signals is not None:
            objective_by_signal = {
                "budget_unconfirmed": "Clarify the current budget position and validation path.",
                "timeline_unclear": "Clarify the decision and implementation timeline.",
                "decision_maker_missing": "Clarify who needs to participate in the decision.",
                "champion_not_evident": "Clarify who could coordinate the next step internally.",
                "procurement_unclear": "Clarify the relevant procurement process and timing.",
                "next_step_weak": "Agree a specific next step with an owner and timing.",
                "stakeholder_misalignment": "Clarify stakeholder priorities and points of alignment.",
                "technical_fit_uncertain": "Clarify the remaining technical fit questions.",
                "security_or_legal_blocker": "Clarify the current security or legal blocker and follow-up path.",
            }
            priority_by_strength: dict[str, BriefPriority] = {
                "strong": "high",
                "moderate": "medium",
                "weak": "low",
            }
            for signal in context.buying_signals.signals:
                objective_text = objective_by_signal.get(signal.signal_type)
                if objective_text is None:
                    continue
                self._append_unique_objective(
                    values,
                    BriefObjective(
                        objective=objective_text,
                        priority=priority_by_strength[signal.strength],
                        reason="Prior validated intelligence marks this area as unresolved.",
                    ),
                )
                if len(values) == 5:
                    break
        return tuple(values[:5])

    def _questions(self, context: ValidatedBriefContext) -> tuple[BriefQuestion, ...]:
        values: list[BriefQuestion] = []
        if context.open_questions is not None:
            for open_question in context.open_questions.open_questions:
                self._append_unique_question(
                    values,
                    BriefQuestion(
                        question=open_question.question,
                        purpose="Resolve a validated open question from prior intelligence.",
                        priority=open_question.importance,
                    ),
                )
        if context.risks is not None:
            for risk_item in context.risks.risks:
                risk_text = self._bounded(risk_item.risk.rstrip(".?"), 440).rstrip("…")
                self._append_unique_question(
                    values,
                    BriefQuestion(
                        question=f"What would help address {risk_text.lower()}?",
                        purpose="Clarify a current validated risk without assuming it is resolved.",
                        priority=risk_item.severity,
                    ),
                )
        if context.buying_signals is not None:
            question_by_signal = {
                "budget_unconfirmed": "What budget position and approval path should we plan around?",
                "timeline_unclear": "What timeline and decision points should we plan around?",
                "decision_maker_missing": "Who else needs to be involved in the decision?",
                "champion_not_evident": "Who could help coordinate the next step internally?",
                "procurement_unclear": "What procurement steps and timing should we account for?",
                "next_step_weak": "What specific next step, owner and timing can we agree?",
                "stakeholder_misalignment": "Where do stakeholder priorities differ today?",
                "technical_fit_uncertain": "Which technical fit questions remain unresolved?",
                "security_or_legal_blocker": "What would help progress the current security or legal blocker?",
            }
            priority_by_strength: dict[str, BriefPriority] = {
                "strong": "high",
                "moderate": "medium",
                "weak": "low",
            }
            for signal in context.buying_signals.signals:
                question = question_by_signal.get(signal.signal_type)
                if question is None:
                    continue
                self._append_unique_question(
                    values,
                    BriefQuestion(
                        question=question,
                        purpose="Validate an unresolved area from prior intelligence.",
                        priority=priority_by_strength[signal.strength],
                    ),
                )
        type_questions: dict[str, tuple[tuple[str, str], ...]] = {
            "phone_call": (
                ("What is the most useful next step we can agree on this call?", "Close the call clearly."),
                ("What remains unresolved from our previous discussion?", "Surface the highest-value unknown."),
            ),
            "presentation": (
                ("Which questions or evidence would be most useful to the audience today?", "Focus on customer needs."),
                (
                    "What would a useful next validation step look like?",
                    "Avoid treating presentation content as customer evidence.",
                ),
            ),
            "workshop": (
                ("Which decisions need to be made in this workshop?", "Clarify the required output."),
                ("Who will own each agreed follow-up?", "Make workshop ownership observable."),
            ),
            "site_visit": (
                ("Which operational or technical constraints should we validate today?", "Focus the site visit."),
                ("What evidence may be captured with authorisation?", "Respect site and privacy restrictions."),
            ),
            "executive_lunch": (
                (
                    "Which strategic priority matters most over the next period?",
                    "Keep the conversation executive-level.",
                ),
                ("What would be a useful next step after today?", "Close without operational overload."),
            ),
            "conference_interaction": (
                ("What business outcome is most important to you right now?", "Use limited time for discovery."),
                ("Would a focused follow-up be useful, and on what topic?", "Set a clear follow-up criterion."),
            ),
            "trade_show_interaction": (
                ("What business outcome is most important to you right now?", "Use limited time for discovery."),
                ("Would a focused follow-up be useful, and on what topic?", "Set a clear follow-up criterion."),
            ),
            "face_to_face_meeting": (
                (
                    "What would make this meeting useful from your perspective?",
                    "Confirm the customer's desired outcome.",
                ),
                ("What should we agree before we finish?", "Create an observable success condition."),
            ),
            "online_meeting": (
                (
                    "What would make this meeting useful from your perspective?",
                    "Confirm the customer's desired outcome.",
                ),
                ("What should we agree before we finish?", "Create an observable success condition."),
            ),
            "manual_interaction": (
                ("What outcome would make this interaction useful?", "Clarify the purpose safely."),
                ("What is the most important unknown to resolve?", "Focus limited context on discovery."),
            ),
        }
        for question, purpose in type_questions[context.records.interaction.interaction_type]:
            self._append_unique_question(
                values,
                BriefQuestion(question=question, purpose=purpose, priority="medium"),
            )
        maximum = 5 if context.records.interaction.interaction_type == "phone_call" else 8
        return tuple(values[:maximum])

    @staticmethod
    def _stakeholders(context: ValidatedBriefContext) -> tuple[BriefStakeholder, ...]:
        if context.stakeholders is not None and context.stakeholders.stakeholders:
            return tuple(
                BriefStakeholder(
                    name=item.name,
                    role=item.role.replace("_", " "),
                    focus=PreInteractionBriefService._bounded(
                        f"Confirm {item.name}'s priorities and current {item.role.replace('_', ' ')} role.",
                        500,
                    ),
                )
                for item in context.stakeholders.stakeholders
            )[:8]
        return tuple(
            BriefStakeholder(
                name=item.name,
                role=item.job_title or item.role.replace("_", " "),
                focus=PreInteractionBriefService._bounded(
                    f"Confirm {item.name}'s priorities and role in this interaction.", 500
                ),
            )
            for item in context.records.participants
        )[:8]

    @staticmethod
    def _commitments(context: ValidatedBriefContext) -> tuple[BriefCommitment, ...]:
        values: list[BriefCommitment] = []
        if context.action_items is not None:
            values.extend(
                BriefCommitment(commitment=item.task, owner=item.owner, due_date=item.due_date)
                for item in context.action_items.action_items
                if item.status == "open"
            )
        if context.decisions is not None:
            values.extend(
                BriefCommitment(
                    commitment=PreInteractionBriefService._bounded(
                        f"Revisit {item.status} decision: {item.decision}",
                        500,
                    ),
                    owner=item.owner,
                    due_date=None,
                )
                for item in context.decisions.decisions
                if item.status in {"tentative", "deferred"}
            )
        return tuple(values[:8])

    @staticmethod
    def _risks(context: ValidatedBriefContext) -> tuple[BriefRisk, ...]:
        values: list[BriefRisk] = []
        if context.risks is not None:
            values.extend(BriefRisk(risk=item.risk, severity=item.severity) for item in context.risks.risks)
        if context.objections is not None:
            for objection_item in context.objections.objections:
                if objection_item.status == "resolved":
                    continue
                severity = cast(
                    BriefPriority,
                    {"strong": "high", "moderate": "medium", "weak": "low"}[objection_item.strength],
                )
                values.append(BriefRisk(risk=f"Objection: {objection_item.objection}", severity=severity))
            for competitor in context.objections.competitors:
                values.append(
                    BriefRisk(
                        risk=f"Competitive context: {competitor.name} is {competitor.position}.",
                        severity="medium" if competitor.position == "stronger" else "low",
                    )
                )
        return tuple(values[:8])

    @staticmethod
    def _success_criteria(
        interaction_type: str,
        commitments: tuple[BriefCommitment, ...],
        risks: tuple[BriefRisk, ...],
    ) -> tuple[str, ...]:
        primary = {
            "phone_call": "A clear next step, owner and timing are agreed.",
            "presentation": "Audience questions, requested evidence and a next validation step are clarified.",
            "workshop": "Required decisions, outputs and owners are clear.",
            "site_visit": "Relevant constraints and authorised follow-up evidence needs are clear.",
            "executive_lunch": "Strategic priorities and an appropriate next step are clear.",
            "conference_interaction": "Follow-up value, topic and ownership are clear.",
            "trade_show_interaction": "Follow-up value, topic and ownership are clear.",
            "face_to_face_meeting": "The highest-value outcome and next step are agreed.",
            "online_meeting": "The highest-value outcome and next step are agreed.",
            "manual_interaction": "The interaction's intended outcome and next step are clear.",
        }[interaction_type]
        values = [primary]
        if commitments:
            values.append("Open commitments have confirmed status and ownership.")
        if risks:
            values.append("Material risks have a clear validation or follow-up path.")
        return tuple(values[:5])

    @staticmethod
    def _guidance(interaction_type: str) -> str:
        return {
            "phone_call": "Keep the call concise, lead with the objective and close with a confirmed next step.",
            "presentation": (
                "Keep the audience and objective in view; treat seller-prepared material as context, "
                "not customer evidence, and close with a validation step."
            ),
            "workshop": "Keep the group focused on decisions, intended outputs, dependencies and follow-up ownership.",
            "site_visit": "Prioritise safety, operational questions and authorised evidence; do not assume capture is permitted.",
            "executive_lunch": "Keep the brief discreet and strategic, and avoid overloading the conversation with operational detail.",
            "conference_interaction": "Use the short interaction for focused discovery and agree follow-up only when it is valuable.",
            "trade_show_interaction": "Use the short interaction for focused discovery and agree follow-up only when it is valuable.",
            "face_to_face_meeting": "Keep high-value questions, stakeholder priorities and success criteria easy to scan before the meeting.",
            "online_meeting": "Keep the meeting focused on current priorities, unresolved questions and an observable next step.",
            "manual_interaction": "Confirm the interaction purpose early and use the available context conservatively.",
        }[interaction_type]

    @staticmethod
    def _confidence(context: ValidatedBriefContext) -> float:
        score = 0.25
        score += 0.15 if context.records.company is not None else 0
        score += 0.15 if context.records.opportunity is not None else 0
        score += 0.05 if context.records.participants else 0
        validated_count = sum(
            item is not None
            for item in (
                context.executive_summary,
                context.buying_signals,
                context.objections,
                context.stakeholders,
                context.decisions,
                context.action_items,
                context.risks,
                context.open_questions,
                context.next_best_action,
            )
        )
        score += min(validated_count * 0.04, 0.25)
        score += 0.1 if context.revenue_brain is not None else 0
        return round(min(score, 0.95), 2)

    def _source_references(
        self,
        records: PreInteractionSourceRecords,
        artifacts: dict[str, AIArtifact],
        valid_revenue_brain: bool,
    ) -> tuple[PreInteractionSourceReference, ...]:
        values: list[PreInteractionSourceReference] = []
        for section in (
            "account_context",
            "objectives",
            "questions_to_ask",
            "success_criteria",
            "interaction_guidance",
        ):
            values.append(
                PreInteractionSourceReference(
                    section=section,
                    capability="interaction_metadata",
                    source_id=records.interaction.id,
                    scope="interaction",
                    source_classification=("recommendation" if section != "account_context" else "system_metadata"),
                    validation_status="not_applicable",
                )
            )
        if records.company is not None:
            values.append(
                PreInteractionSourceReference(
                    section="account_context",
                    capability="company_metadata",
                    source_id=records.company.id,
                    scope="account",
                    source_classification="system_metadata",
                    validation_status="not_applicable",
                )
            )
        if records.opportunity is not None:
            values.append(
                PreInteractionSourceReference(
                    section="account_context",
                    capability="opportunity_metadata",
                    source_id=records.opportunity.id,
                    scope="opportunity",
                    source_classification="system_metadata",
                    validation_status="not_applicable",
                )
            )
        for participant in records.participants:
            values.append(
                PreInteractionSourceReference(
                    section="stakeholder_focus",
                    capability="meeting_participants",
                    source_id=participant.participant_id,
                    scope="interaction",
                    source_classification="system_metadata",
                    validation_status="not_applicable",
                )
            )
        sections_by_capability: dict[str, tuple[str, ...]] = {
            "executive_summary": ("account_context",),
            "buying_signals": ("objectives", "questions_to_ask"),
            "objections_competitive_signals": ("risks_to_watch", "questions_to_ask"),
            "stakeholder_intelligence": ("stakeholder_focus", "questions_to_ask"),
            "decisions": ("open_commitments",),
            "action_items": ("open_commitments", "objectives"),
            "risks_blockers": ("risks_to_watch", "questions_to_ask"),
            "open_questions": ("questions_to_ask", "objectives"),
            "next_best_action": ("objectives", "success_criteria"),
        }
        for capability, artifact in artifacts.items():
            for section in sections_by_capability.get(capability, ()):
                values.append(
                    PreInteractionSourceReference(
                        section=cast(BriefSection, section),
                        capability=cast(BriefSourceCapability, capability),
                        source_id=artifact.id,
                        scope="meeting",
                        source_classification="inferred_from_prior_intelligence",
                        validation_status="completed",
                    )
                )
        if valid_revenue_brain and records.revenue_brain_insight is not None:
            values.append(
                PreInteractionSourceReference(
                    section="recent_changes",
                    capability="revenue_brain",
                    source_id=records.revenue_brain_insight.id,
                    scope=("opportunity" if records.revenue_brain_insight.scope == "opportunity" else "account"),
                    source_classification="revenue_brain_change",
                    validation_status="completed",
                )
            )
        unique: dict[tuple[str, str, UUID], PreInteractionSourceReference] = {}
        for reference in values:
            unique[(reference.section, reference.capability, reference.source_id)] = reference
        return tuple(unique.values())

    @staticmethod
    def _validated_artifact(
        artifact: AIArtifact | None,
        model: type[ValidatedModel],
    ) -> ValidatedModel | None:
        if artifact is None:
            return None
        try:
            return model.model_validate(artifact.content_json)
        except ValidationError:
            logger.warning(
                "brief_source_skipped",
                extra={
                    "organisation_id": str(artifact.organisation_id),
                    "meeting_id": str(artifact.meeting_id),
                    "source_type": artifact.artifact_type,
                    "source_id": str(artifact.id),
                },
            )
            return None

    async def _completed_response(self, record: PreInteractionBrief) -> PreInteractionBriefResponse:
        try:
            content = PreInteractionBriefContent.model_validate_json(json.dumps(record.content_json))
            references = tuple(
                PreInteractionSourceReference.model_validate_json(json.dumps(item))
                for item in record.source_references_json
            )
            if (
                content.interaction_id != record.interaction_id
                or content.brief_version != record.brief_version
                or not references
            ):
                raise ValueError("Persisted brief trace does not match its immutable content.")
        except (ValidationError, ValueError):
            logger.error(
                "brief_failed_safe_code",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(record.interaction_id),
                    "brief_version": record.brief_version,
                    "safe_code": "invalid_persisted_brief",
                },
            )
            return PreInteractionBriefResponse(
                state="failed",
                generation_available=True,
                unavailable_reason=None,
                safe_message="The preparation brief could not be loaded safely. Generate a new version.",
                brief=None,
                generated_at=record.created_at,
                reviewed=False,
                reviewed_at=None,
                prior_versions=[],
                source_labels=[],
            )
        history = await self.repository.list_briefs(
            self.tenant.organisation_id,
            record.interaction_id,
            limit=PRE_INTERACTION_BRIEF_HISTORY_LIMIT,
        )
        prior = [
            BriefVersionSummary(
                brief_version=item.brief_version,
                generated_at=item.created_at,
                reviewed=item.reviewed_at is not None,
                reviewed_at=item.reviewed_at,
            )
            for item in history
            if item.id != record.id
        ][:5]
        return PreInteractionBriefResponse(
            state="completed",
            generation_available=True,
            unavailable_reason=None,
            safe_message=None,
            brief=content,
            generated_at=record.created_at,
            reviewed=record.reviewed_at is not None,
            reviewed_at=record.reviewed_at,
            prior_versions=prior,
            source_labels=self._source_labels(references),
        )

    @staticmethod
    def _empty_response(records: PreInteractionSourceRecords) -> PreInteractionBriefResponse:
        if records.company is None and records.opportunity is None:
            return PreInteractionBriefResponse(
                state="unavailable",
                generation_available=False,
                unavailable_reason="Link a company or opportunity to prepare a grounded brief.",
                safe_message=None,
                brief=None,
                generated_at=None,
                reviewed=False,
                reviewed_at=None,
                prior_versions=[],
                source_labels=[],
            )
        return PreInteractionBriefResponse(
            state="not_generated",
            generation_available=True,
            unavailable_reason=None,
            safe_message=None,
            brief=None,
            generated_at=None,
            reviewed=False,
            reviewed_at=None,
            prior_versions=[],
            source_labels=[],
        )

    @staticmethod
    def _source_labels(references: tuple[PreInteractionSourceReference, ...]) -> list[str]:
        capabilities = {reference.capability for reference in references}
        labels: list[str] = ["Interaction details"]
        if "company_metadata" in capabilities:
            labels.append("Company record")
        if "opportunity_metadata" in capabilities:
            labels.append("Opportunity record")
        if "meeting_participants" in capabilities:
            labels.append("Participant details")
        if capabilities & {
            "executive_summary",
            "buying_signals",
            "objections_competitive_signals",
            "stakeholder_intelligence",
            "decisions",
            "action_items",
            "risks_blockers",
            "open_questions",
            "next_best_action",
        }:
            labels.append("Prior validated Meeting Intelligence")
        if "revenue_brain" in capabilities:
            labels.append("Revenue Brain changes")
        return labels[:5]

    @staticmethod
    def _append_unique_objective(values: list[BriefObjective], candidate: BriefObjective) -> None:
        if candidate.objective.casefold() not in {item.objective.casefold() for item in values}:
            values.append(candidate)

    @staticmethod
    def _append_unique_question(values: list[BriefQuestion], candidate: BriefQuestion) -> None:
        if candidate.question.casefold() not in {item.question.casefold() for item in values}:
            values.append(candidate)

    @staticmethod
    def _humanise(value: str) -> str:
        return value.replace("_", " ")

    @staticmethod
    def _bounded(value: str, maximum: int) -> str:
        stripped = " ".join(value.split())
        if len(stripped) <= maximum:
            return stripped
        return f"{stripped[: maximum - 1].rstrip()}…"

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return (value if value.tzinfo is not None else value.replace(tzinfo=UTC)).isoformat()

    @staticmethod
    def _json(value: BaseModel | None) -> dict[str, object] | None:
        return value.model_dump(mode="json") if value is not None else None
