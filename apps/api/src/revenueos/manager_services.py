from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.daily_repositories import DailyRepository
from revenueos.daily_services import NEGATIVE_REVENUE_BRAIN_CHANGES
from revenueos.errors import PublicAPIError
from revenueos.manager_contracts import (
    ManagerAttentionCode,
    ManagerAttentionReasonResponse,
    ManagerAttentionSummaryResponse,
    ManagerBaselineViewResponse,
    ManagerDealAttentionListResponse,
    ManagerDealAttentionResponse,
    ManagerDealChangeResponse,
    ManagerDealReviewResponse,
    ManagerDiscussionQuestionResponse,
    ManagerForecastViewResponse,
    ManagerInteractionResponse,
    ManagerMethodologyGapResponse,
    ManagerSourceResponse,
    ManagerSummaryResponse,
    ManagerTaskResponse,
)
from revenueos.manager_repositories import ManagerDealChanges, ManagerRepository
from revenueos.methodology_contracts import MethodologyProjectionContent
from revenueos.models import (
    Interaction,
    MethodologyProjection,
    Opportunity,
    RevenueBrainInsight,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastReviewerJudgment,
    SalesForecastReviewerRevision,
    Task,
)
from revenueos.pipeline_repositories import PipelineOpportunityRecord
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainInsightContent
from revenueos.sales_forecast_contracts import ForecastCategory
from revenueos.sales_forecast_repositories import (
    SalesForecastOpportunityRecord,
    SalesForecastOutcomeCount,
    SalesForecastRepository,
)
from revenueos.sales_forecast_services import FORECAST_MODEL_LOOKBACK_DAYS, SalesForecastService
from revenueos.tenant import TenantContext

ATTENTION_ORDER: dict[ManagerAttentionCode, int] = {
    "close_date_passed": 0,
    "overdue_high_priority_action": 1,
    "evidence_conflict": 2,
    "forecast_needs_review": 3,
    "forecast_not_reviewed": 4,
    "methodology_priority_gap": 5,
    "no_next_action": 6,
    "stale_evidence": 7,
    "customer_blocker": 8,
}
ATTENTION_LABELS: dict[ManagerAttentionCode, str] = {
    "close_date_passed": "Close date passed",
    "overdue_high_priority_action": "Overdue high-priority Action",
    "evidence_conflict": "Evidence needs clarification",
    "forecast_needs_review": "Seller forecast needs review",
    "forecast_not_reviewed": "Seller forecast not reviewed",
    "methodology_priority_gap": "Methodology gap",
    "no_next_action": "No next Action",
    "stale_evidence": "Evidence needs revalidation",
    "customer_blocker": "Customer blocker",
}

Judgment = tuple[SalesForecastJudgment, SalesForecastJudgmentRevision]
ReviewerJudgment = tuple[SalesForecastReviewerJudgment, SalesForecastReviewerRevision]


class ManagerIntelligenceService:
    """Compose explainable deal conditions without people scoring or persistent coaching profiles."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ManagerRepository(session)
        self.daily_repository = DailyRepository(session)
        self.forecast_repository = SalesForecastRepository(session)
        self.forecasts = SalesForecastService(session, tenant, settings)

    def require_enabled(self) -> None:
        if not self.settings.feature_manager_intelligence_enabled:
            raise PublicAPIError("feature_unavailable", "Manager Intelligence is not enabled.", 404)
        if not self.tenant.can_manage():
            raise PublicAPIError(
                "forbidden",
                "Organisation administrator access is required for this private-beta manager view.",
                403,
            )

    async def attention(
        self,
        *,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        reason: ManagerAttentionCode | None,
        page: int,
        page_size: int,
        now: datetime | None = None,
    ) -> ManagerDealAttentionListResponse:
        self.require_enabled()
        generated_at = self._utc(now or datetime.now(UTC))
        records = await self.repository.open_opportunities(
            self.tenant.organisation_id,
            pipeline_id=pipeline_id,
            owner_user_id=owner_user_id,
        )
        await self._validate_filters(records, pipeline_id=pipeline_id, owner_user_id=owner_user_id)
        items, _ = await self._compose(records, generated_at)
        summaries = self._summaries(items)
        if reason is not None:
            items = [item for item in items if any(value.code == reason for value in item.reasons)]
        start = (page - 1) * page_size
        return ManagerDealAttentionListResponse(
            total=len(items),
            summaries=summaries,
            items=items[start : start + page_size],
            page=page,
            page_size=page_size,
            generated_at=generated_at,
        )

    async def deal_review(
        self,
        opportunity_id: UUID,
        *,
        now: datetime | None = None,
    ) -> ManagerDealReviewResponse:
        self.require_enabled()
        generated_at = self._utc(now or datetime.now(UTC))
        record = await self.repository.opportunity(self.tenant.organisation_id, opportunity_id)
        if record is None:
            raise PublicAPIError("opportunity_not_found", "The open Opportunity was not found.", 404)
        items, context = await self._compose([record], generated_at, include_without_attention=True)
        item = items[0]
        projections = context.projections.get(opportunity_id)
        gaps = self._methodology_gaps(projections, opportunity_id)
        tasks = context.tasks.get(opportunity_id, [])
        latest_interaction = context.interactions.get(opportunity_id)
        changes = await self.repository.deal_changes(
            self.tenant.organisation_id,
            opportunity_id,
            since=generated_at - timedelta(days=90),
        )
        recent_changes = self._recent_changes(changes)
        baseline = SalesForecastService._baseline_response(
            self._forecast_record(record),
            context.outcome_counts,
            lookback_start=generated_at.date() - timedelta(days=FORECAST_MODEL_LOOKBACK_DAYS),
            lookback_end=generated_at.date(),
        )
        return ManagerDealReviewResponse(
            deal=item,
            historical_baseline=ManagerBaselineViewResponse(
                state=baseline.status,
                expected_contribution=baseline.expected_contribution,
                won_count=baseline.won_count,
                lost_count=baseline.lost_count,
                explanation=baseline.explanation,
            ),
            methodology_gaps=gaps,
            current_actions=[self._task(task, opportunity_id) for task in tasks[:20]],
            latest_interaction=self._interaction(latest_interaction, opportunity_id),
            recent_changes=recent_changes,
            questions=self._questions(item.reasons, gaps),
            generated_at=generated_at,
        )

    async def summary(
        self,
        *,
        period_anchor: date,
        currency: str,
        now: datetime | None = None,
    ) -> ManagerSummaryResponse:
        self.require_enabled()
        generated_at = self._utc(now or datetime.now(UTC))
        forecast = await self.forecasts.forecast(
            period_type="quarter",
            period_anchor=period_anchor,
            currency=currency,
            pipeline_id=None,
            owner_user_id=None,
            page=1,
            page_size=1,
            now=generated_at,
        )
        attention = await self.attention(
            pipeline_id=None,
            owner_user_id=None,
            reason=None,
            page=1,
            page_size=1,
            now=generated_at,
        )
        assert forecast.manager_forecast is not None
        return ManagerSummaryResponse(
            period_label=forecast.period.period_label,
            currency=forecast.currency,
            actual=forecast.actual,
            organisation_targets=[target for target in forecast.targets if target.scope == "organisation"],
            seller_forecast=forecast.seller_forecast,
            manager_forecast=forecast.manager_forecast,
            revenueos_baseline=forecast.revenueos_baseline,
            deals_needing_attention=attention.total,
            top_attention_reasons=attention.summaries[:5],
            generated_at=generated_at,
        )

    async def _compose(
        self,
        records: list[PipelineOpportunityRecord],
        now: datetime,
        *,
        include_without_attention: bool = False,
    ) -> tuple[list[ManagerDealAttentionResponse], _ManagerContext]:
        opportunity_ids = {record.opportunity.id for record in records}
        tasks = await self.repository.current_tasks(self.tenant.organisation_id, opportunity_ids)
        interactions = await self.repository.latest_completed_interactions(self.tenant.organisation_id, opportunity_ids)
        projection_rows = (
            await self.daily_repository.methodology_projections(
                self.tenant.organisation_id,
                tuple(opportunity_ids),
            )
            if self.settings.feature_sales_methodology_enabled
            else []
        )
        insight_rows = await self.daily_repository.revenue_brain_insights(
            self.tenant.organisation_id,
            tuple(opportunity_ids),
        )
        projections = {row.opportunity_id: row for row in projection_rows}
        insights = {row.opportunity_id: row for row in insight_rows if row.opportunity_id is not None}
        period_start, period_end = SalesForecastService._period("quarter", now.date())
        period = await self.forecast_repository.period(
            self.tenant.organisation_id,
            period_type="quarter",
            period_start=period_start,
            period_end=period_end,
        )
        seller = await self.forecast_repository.judgments_for_period(
            self.tenant.organisation_id,
            period.id if period is not None else None,
            opportunity_ids,
        )
        manager = await self.forecast_repository.reviewer_judgments_for_period(
            self.tenant.organisation_id,
            period.id if period is not None else None,
            opportunity_ids,
        )
        outcome_counts = await self.forecast_repository.historical_outcome_counts(
            self.tenant.organisation_id,
            lookback_start=now.date() - timedelta(days=FORECAST_MODEL_LOOKBACK_DAYS),
            as_of=now,
        )
        context = _ManagerContext(tasks, interactions, projections, insights, seller, manager, outcome_counts)
        values: list[tuple[int, date, str, ManagerDealAttentionResponse]] = []
        for record in records:
            opportunity = record.opportunity
            reasons = self._reasons(record, context, now, period_start, period_end)
            if not reasons and not include_without_attention:
                continue
            primary_order = ATTENTION_ORDER[reasons[0].code] if reasons else len(ATTENTION_ORDER)
            values.append(
                (
                    primary_order,
                    opportunity.expected_close_date or date.max,
                    opportunity.name.casefold(),
                    ManagerDealAttentionResponse(
                        opportunity_id=opportunity.id,
                        opportunity_name=opportunity.name,
                        company_name=record.company_name,
                        owner_user_id=opportunity.owner_user_id,
                        owner_display_name=record.owner_name,
                        pipeline_id=record.pipeline.id,
                        pipeline_name=record.pipeline.name,
                        stage_id=record.stage.id,
                        stage_name=record.stage.name,
                        amount=opportunity.estimated_value,
                        currency=opportunity.currency,
                        expected_close_date=opportunity.expected_close_date,
                        seller_forecast=self._forecast_view(opportunity, seller.get(opportunity.id)),
                        manager_forecast=self._manager_forecast_view(opportunity, manager.get(opportunity.id)),
                        reasons=reasons[:5],
                        href=f"/opportunities/{opportunity.id}",
                    ),
                )
            )
        values.sort(key=lambda value: value[:3])
        return [value[3] for value in values], context

    def _reasons(
        self,
        record: PipelineOpportunityRecord,
        context: _ManagerContext,
        now: datetime,
        period_start: date,
        period_end: date,
    ) -> list[ManagerAttentionReasonResponse]:
        opportunity = record.opportunity
        reasons: list[ManagerAttentionReasonResponse] = []
        opportunity_source = self._source(
            "opportunity", opportunity.id, "Current Opportunity state", f"/opportunities/{opportunity.id}"
        )
        if opportunity.expected_close_date is not None and opportunity.expected_close_date < now.date():
            reasons.append(
                self._reason(
                    "close_date_passed",
                    "The canonical expected close date is in the past while the Opportunity remains open.",
                    [opportunity_source],
                    detected_at=now,
                )
            )
        tasks = context.tasks.get(opportunity.id, [])
        overdue = next(
            (
                task
                for task in tasks
                if task.due_at is not None and self._utc(task.due_at) < now and task.priority in {"high", "urgent"}
            ),
            None,
        )
        if overdue is not None:
            reasons.append(
                self._reason(
                    "overdue_high_priority_action",
                    "A current high-priority Action is overdue.",
                    [self._source("task", overdue.id, overdue.title, f"/opportunities/{opportunity.id}#actions")],
                    detected_at=now,
                )
            )
        projection = context.projections.get(opportunity.id)
        for gap in self._methodology_gaps(projection, opportunity.id)[:2]:
            code: ManagerAttentionCode = (
                "evidence_conflict"
                if gap.state == "conflicting"
                else "stale_evidence"
                if gap.state == "stale"
                else "methodology_priority_gap"
            )
            reasons.append(
                self._reason(
                    code,
                    gap.explanation,
                    gap.sources or [opportunity_source],
                    gap.field_key,
                    detected_at=now,
                )
            )
        seller = context.seller.get(opportunity.id)
        if seller is not None and SalesForecastService._stale_reasons(opportunity, seller[1]):
            reasons.append(
                self._reason(
                    "forecast_needs_review",
                    "The seller forecast was reviewed before the current Opportunity context changed.",
                    [
                        self._source(
                            "forecast_revision",
                            seller[1].id,
                            "Seller forecast revision",
                            "/insights?tab=forecast",
                        )
                    ],
                    detected_at=now,
                )
            )
        elif (
            seller is None
            and opportunity.expected_close_date is not None
            and period_start <= opportunity.expected_close_date <= period_end
        ):
            reasons.append(
                self._reason(
                    "forecast_not_reviewed",
                    "This Opportunity closes in the current quarter and has no seller forecast view.",
                    [opportunity_source],
                    detected_at=now,
                )
            )
        if not tasks:
            reasons.append(
                self._reason(
                    "no_next_action",
                    "There is no current open or in-progress Action linked to this Opportunity.",
                    [opportunity_source],
                    detected_at=now,
                )
            )
        insight = context.insights.get(opportunity.id)
        brain_reason = self._brain_reason(insight, opportunity.id)
        if brain_reason is not None:
            reasons.append(brain_reason)
        deduplicated: dict[tuple[ManagerAttentionCode, str], ManagerAttentionReasonResponse] = {}
        for reason in reasons:
            key = (reason.code, reason.id.split(":", maxsplit=2)[-1])
            deduplicated.setdefault(key, reason)
        return sorted(deduplicated.values(), key=lambda value: (ATTENTION_ORDER[value.code], value.id))

    def _methodology_gaps(
        self,
        projection: MethodologyProjection | None,
        opportunity_id: UUID,
    ) -> list[ManagerMethodologyGapResponse]:
        if projection is None:
            return []
        try:
            content = MethodologyProjectionContent.model_validate(projection.content_json)
        except ValidationError:
            return []
        rank = {"conflicting": 0, "stale": 1, "unknown": 2, "partially_supported": 3}
        candidates = [value for value in content.items if value.state != "confirmed"]
        candidates.sort(key=lambda value: (rank[value.state], not value.required, value.field_key))
        result: list[ManagerMethodologyGapResponse] = []
        for item in candidates:
            explanation = (
                f"{item.display_name} needs clarification."
                if item.state == "conflicting"
                else f"{item.display_name} needs revalidation."
                if item.state == "stale"
                else f"{item.display_name} is still unknown."
                if item.state == "unknown"
                else f"{item.display_name} needs more customer evidence."
            )
            sources = [
                self._source(
                    "methodology_projection",
                    projection.id,
                    f"{content.methodology_name}: {item.display_name}",
                    f"/opportunities/{opportunity_id}#methodology",
                )
            ]
            sources.extend(
                self._source(
                    "evidence",
                    value.source_id,
                    value.label,
                    f"/opportunities/{opportunity_id}#evidence",
                )
                for value in (*item.sources, *item.conflicts)
            )
            result.append(
                ManagerMethodologyGapResponse(
                    field_key=item.field_key,
                    display_name=item.display_name,
                    state=cast(Literal["partially_supported", "unknown", "conflicting", "stale"], item.state),
                    explanation=explanation,
                    suggested_question=item.suggested_question,
                    sources=self._unique_sources(sources),
                )
            )
        return result

    def _brain_reason(
        self,
        insight: RevenueBrainInsight | None,
        opportunity_id: UUID,
    ) -> ManagerAttentionReasonResponse | None:
        if insight is None:
            return None
        try:
            content = RevenueBrainInsightContent.model_validate_json(json.dumps(insight.content_json))
        except ValidationError:
            return None
        changes = sorted(
            content.changes,
            key=lambda value: ({"high": 0, "medium": 1, "low": 2}[value.importance], value.change_type),
        )
        for change in changes:
            if change.change_type not in NEGATIVE_REVENUE_BRAIN_CHANGES or change.direction in {
                "improved",
                "resolved",
            }:
                continue
            return self._reason(
                "customer_blocker",
                NEGATIVE_REVENUE_BRAIN_CHANGES[change.change_type][1],
                [
                    self._source(
                        "revenue_brain_insight",
                        insight.id,
                        change.title,
                        f"/opportunities/{opportunity_id}#revenue-brain",
                    )
                ],
                change.change_type,
                detected_at=self._utc(insight.created_at),
            )
        return None

    def _questions(
        self,
        reasons: list[ManagerAttentionReasonResponse],
        gaps: list[ManagerMethodologyGapResponse],
    ) -> list[ManagerDiscussionQuestionResponse]:
        gap_by_reason = {gap.field_key: gap for gap in gaps if gap.suggested_question is not None}
        templates: dict[ManagerAttentionCode, str] = {
            "close_date_passed": "What is the current expected close date, and what customer evidence supports it?",
            "overdue_high_priority_action": "What is blocking the current high-priority Action, and what should happen next?",
            "evidence_conflict": "Which customer evidence is current, and what would resolve the conflict?",
            "forecast_needs_review": "Does the seller forecast still reflect the current deal context?",
            "forecast_not_reviewed": "What is the seller's current view for this forecast period?",
            "methodology_priority_gap": "What customer evidence would clarify this methodology gap?",
            "no_next_action": "What is the next agreed customer-facing step?",
            "stale_evidence": "What current customer evidence would revalidate this deal condition?",
            "customer_blocker": "What must happen to resolve the current customer blocker?",
        }
        result: list[ManagerDiscussionQuestionResponse] = []
        seen: set[str] = set()
        for reason in reasons:
            field_key = reason.id.split(":", maxsplit=2)[-1]
            gap = gap_by_reason.get(field_key)
            question = (
                gap.suggested_question
                if gap is not None and gap.suggested_question is not None
                else templates[reason.code]
            )
            if question in seen:
                continue
            seen.add(question)
            result.append(
                ManagerDiscussionQuestionResponse(
                    id=f"question:{reason.id}",
                    question=question,
                    why_shown=reason.explanation,
                    source_reason_ids=[reason.id],
                    sources=reason.sources,
                )
            )
            if len(result) == 5:
                break
        return result

    def _recent_changes(self, changes: ManagerDealChanges) -> list[ManagerDealChangeResponse]:
        values: list[ManagerDealChangeResponse] = []
        for event in changes.stage_events:
            values.append(
                ManagerDealChangeResponse(
                    id=f"stage:{event.id}",
                    change_type="stage_changed",
                    label=f"Stage changed to {event.to_stage_name}",
                    changed_at=self._utc(event.changed_at),
                    source=self._source("pipeline_stage_event", event.id, "Pipeline stage history"),
                )
            )
        crm_labels: dict[str, tuple[str, Literal["amount_changed", "expected_close_changed", "owner_changed"]]] = {
            "estimated_value": ("Opportunity amount changed", "amount_changed"),
            "expected_close_date": ("Expected close date changed", "expected_close_changed"),
            "owner_user_id": ("Opportunity owner changed", "owner_changed"),
        }
        for change in changes.crm_changes:
            label, change_type = crm_labels[change.field_key]
            values.append(
                ManagerDealChangeResponse(
                    id=f"crm:{change.id}",
                    change_type=change_type,
                    label=label,
                    changed_at=self._utc(change.changed_at),
                    source=self._source("crm_change", change.id, "Opportunity field history"),
                )
            )
        for revision in changes.seller_revisions:
            values.append(
                ManagerDealChangeResponse(
                    id=f"seller-forecast:{revision.id}",
                    change_type="seller_forecast_changed",
                    label=f"Seller forecast reviewed as {self._category_label(revision.category)}",
                    changed_at=self._utc(revision.created_at),
                    source=self._source("forecast_revision", revision.id, "Seller forecast revision"),
                )
            )
        for manager_revision in changes.manager_revisions:
            values.append(
                ManagerDealChangeResponse(
                    id=f"manager-forecast:{manager_revision.id}",
                    change_type="manager_forecast_changed",
                    label=f"Manager forecast reviewed as {self._category_label(manager_revision.category)}",
                    changed_at=self._utc(manager_revision.created_at),
                    source=self._source("forecast_revision", manager_revision.id, "Manager forecast revision"),
                )
            )
        for task in changes.completed_tasks:
            values.append(
                ManagerDealChangeResponse(
                    id=f"task:{task.id}",
                    change_type="action_completed",
                    label="Action completed",
                    changed_at=self._utc(task.updated_at),
                    source=self._source("task", task.id, task.title),
                )
            )
        for interaction in changes.completed_interactions:
            occurred_at = interaction.actual_end_at or interaction.actual_start_at or interaction.updated_at
            values.append(
                ManagerDealChangeResponse(
                    id=f"interaction:{interaction.id}",
                    change_type="interaction_completed",
                    label="Customer interaction completed",
                    changed_at=self._utc(occurred_at),
                    source=self._source("interaction", interaction.id, interaction.title),
                )
            )
        for insight in changes.revenue_brain_insights:
            reason = self._brain_reason(insight, cast(UUID, insight.opportunity_id))
            if reason is not None:
                values.append(
                    ManagerDealChangeResponse(
                        id=f"customer-context:{insight.id}",
                        change_type="customer_context_changed",
                        label=reason.explanation,
                        changed_at=self._utc(insight.created_at),
                        source=reason.sources[0],
                    )
                )
        values.sort(key=lambda value: (value.changed_at, value.id), reverse=True)
        return values[:20]

    @staticmethod
    def _task(task: Task, opportunity_id: UUID) -> ManagerTaskResponse:
        return ManagerTaskResponse(
            id=task.id,
            title=task.title,
            status=cast(Literal["open", "in_progress"], task.status),
            priority=cast(Literal["low", "medium", "high", "urgent"], task.priority),
            due_at=ManagerIntelligenceService._utc(task.due_at) if task.due_at is not None else None,
            href=f"/opportunities/{opportunity_id}#actions",
        )

    @staticmethod
    def _interaction(value: Interaction | None, opportunity_id: UUID) -> ManagerInteractionResponse | None:
        if value is None:
            return None
        occurred_at = value.actual_end_at or value.actual_start_at or value.updated_at
        return ManagerInteractionResponse(
            id=value.id,
            title=value.title,
            interaction_type=value.interaction_type,
            occurred_at=ManagerIntelligenceService._utc(occurred_at),
            href=f"/opportunities/{opportunity_id}#interactions",
        )

    @staticmethod
    def _forecast_record(record: PipelineOpportunityRecord) -> SalesForecastOpportunityRecord:
        return SalesForecastOpportunityRecord(
            opportunity=record.opportunity,
            company_name=record.company_name,
            owner_display_name=record.owner_name,
            pipeline_name=record.pipeline.name,
            stage_name=record.stage.name,
        )

    @staticmethod
    def _forecast_view(opportunity: Opportunity, value: Judgment | None) -> ManagerForecastViewResponse | None:
        if value is None:
            return None
        revision = value[1]
        return ManagerForecastViewResponse(
            category=cast(ForecastCategory, revision.category),
            revision_number=revision.revision_number,
            reviewed_at=ManagerIntelligenceService._utc(revision.created_at),
            stale_reasons=SalesForecastService._stale_reasons(opportunity, revision),
        )

    @staticmethod
    def _manager_forecast_view(
        opportunity: Opportunity,
        value: ReviewerJudgment | None,
    ) -> ManagerForecastViewResponse | None:
        if value is None:
            return None
        revision = value[1]
        return ManagerForecastViewResponse(
            category=cast(ForecastCategory, revision.category),
            revision_number=revision.revision_number,
            reviewed_at=ManagerIntelligenceService._utc(revision.created_at),
            stale_reasons=SalesForecastService._stale_reasons(opportunity, revision),
        )

    @staticmethod
    def _summaries(items: list[ManagerDealAttentionResponse]) -> list[ManagerAttentionSummaryResponse]:
        counts: Counter[ManagerAttentionCode] = Counter(reason.code for item in items for reason in item.reasons)
        return [
            ManagerAttentionSummaryResponse(code=code, label=ATTENTION_LABELS[code], deal_count=counts[code])
            for code in sorted(counts, key=lambda value: ATTENTION_ORDER[value])
        ]

    @staticmethod
    def _reason(
        code: ManagerAttentionCode,
        explanation: str,
        sources: list[ManagerSourceResponse],
        discriminator: str | None = None,
        *,
        detected_at: datetime,
    ) -> ManagerAttentionReasonResponse:
        suffix = discriminator or str(sources[0].source_id)
        return ManagerAttentionReasonResponse(
            id=f"{code}:{suffix}",
            code=code,
            label=ATTENTION_LABELS[code],
            explanation=explanation,
            detected_at=detected_at,
            sources=ManagerIntelligenceService._unique_sources(sources),
        )

    @staticmethod
    def _source(
        source_type: Literal[
            "opportunity",
            "task",
            "methodology_projection",
            "evidence",
            "forecast_revision",
            "revenue_brain_insight",
            "interaction",
            "pipeline_stage_event",
            "crm_change",
        ],
        source_id: UUID,
        label: str,
        href: str | None = None,
    ) -> ManagerSourceResponse:
        return ManagerSourceResponse(source_type=source_type, source_id=source_id, label=label, href=href)

    @staticmethod
    def _unique_sources(values: list[ManagerSourceResponse]) -> list[ManagerSourceResponse]:
        result: list[ManagerSourceResponse] = []
        seen: set[tuple[str, UUID]] = set()
        for value in values:
            key = (value.source_type, value.source_id)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result[:12]

    async def _validate_filters(
        self,
        records: list[PipelineOpportunityRecord],
        *,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
    ) -> None:
        if pipeline_id is not None and not any(record.pipeline.id == pipeline_id for record in records):
            pipeline = await self.forecast_repository.pipeline(self.tenant.organisation_id, pipeline_id)
            if pipeline is None:
                raise PublicAPIError("pipeline_not_found", "The selected Pipeline was not found.", 404)
        if owner_user_id is not None:
            members = await self.forecast_repository.members(self.tenant.organisation_id)
            if not any(member.user_id == owner_user_id for member in members):
                raise PublicAPIError("owner_not_found", "The selected owner was not found.", 404)

    @staticmethod
    def _category_label(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class _ManagerContext:
    def __init__(
        self,
        tasks: dict[UUID, list[Task]],
        interactions: dict[UUID, Interaction],
        projections: dict[UUID, MethodologyProjection],
        insights: dict[UUID, RevenueBrainInsight],
        seller: dict[UUID, Judgment],
        manager: dict[UUID, ReviewerJudgment],
        outcome_counts: dict[tuple[UUID, UUID], SalesForecastOutcomeCount],
    ) -> None:
        self.tasks = tasks
        self.interactions = interactions
        self.projections = projections
        self.insights = insights
        self.seller = seller
        self.manager = manager
        self.outcome_counts = outcome_counts
