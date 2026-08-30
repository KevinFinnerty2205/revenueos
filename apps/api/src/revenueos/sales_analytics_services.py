from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import Interaction, Opportunity, OpportunityStageEvent, SalesPipelineStage
from revenueos.sales_analytics_contracts import (
    CurrencyAmountResponse,
    FollowOnRateResponse,
    FunnelStageResponse,
    LossStageResponse,
    OutcomeCurrencyResponse,
    OutcomeCycleResponse,
    OutcomeReasonResponse,
    SalesActivityResponse,
    SalesFunnelResponse,
    SalesInsightsMetadataResponse,
    SalesInsightsOwnerResponse,
    SalesInsightsPipelineResponse,
    SalesInsightsScopeResponse,
    SalesInsightsStageResponse,
    SalesMetricObservationResponse,
    SalesOverviewResponse,
    SalesWinLossResponse,
    StageDurationResponse,
    StageHistoryCoverageResponse,
)
from revenueos.sales_analytics_repositories import LiveOutreachSendRecord, SalesAnalyticsRepository
from revenueos.sales_metric_registry import SALES_METRIC_REGISTRY, sales_metric_definitions
from revenueos.tenant import TenantContext

OUTCOME_WINDOW_DAYS = 30
MAXIMUM_RANGE_DAYS = 1_827
MEETING_TYPES = frozenset(
    (
        "online_meeting",
        "face_to_face_meeting",
        "presentation",
        "workshop",
        "site_visit",
        "executive_lunch",
        "conference_interaction",
        "trade_show_interaction",
    )
)
REASON_LABELS: dict[str, str] = {
    "solution_fit": "Solution fit",
    "commercial": "Commercial",
    "relationship": "Relationship",
    "implementation": "Implementation",
    "existing_customer": "Existing customer",
    "price": "Price",
    "competitor": "Competitor",
    "no_decision": "No decision",
    "budget": "Budget",
    "timing": "Timing",
    "requirements_fit": "Requirements fit",
    "procurement": "Procurement",
    "other": "Other",
    "unknown": "Unknown",
}


@dataclass(frozen=True)
class SalesAnalyticsFilters:
    start_date: date
    end_date: date
    timezone_name: str
    timezone: ZoneInfo
    start_at: datetime
    end_at: datetime
    pipeline_id: UUID | None
    owner_user_id: UUID | None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _decimal_median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return Decimal(statistics.median(values)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _rate(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    return (Decimal(numerator) * Decimal(100) / Decimal(denominator)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class SalesAnalyticsService:
    """Deterministic Core sales analytics over canonical tenant-owned records."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = SalesAnalyticsRepository(session)

    async def filters(
        self,
        *,
        start_date: date,
        end_date: date,
        timezone_name: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        now: datetime | None = None,
    ) -> SalesAnalyticsFilters:
        self.require_enabled()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError("invalid_timezone", "Choose a valid IANA timezone.", 422) from exc
        generated_at = _utc(now or datetime.now(UTC))
        local_today = generated_at.astimezone(timezone).date()
        if end_date < start_date:
            raise PublicAPIError("invalid_date_range", "The end date must be on or after the start date.", 422)
        if end_date > local_today:
            raise PublicAPIError("future_date_range", "The date range cannot end in the future.", 422)
        if (end_date - start_date).days + 1 > MAXIMUM_RANGE_DAYS:
            raise PublicAPIError("date_range_too_large", "Choose a date range of five years or less.", 422)
        if pipeline_id is not None and await self.repository.pipeline(self.tenant.organisation_id, pipeline_id) is None:
            raise PublicAPIError("pipeline_not_found", "The selected pipeline was not found.", 404)
        if owner_user_id is not None and not await self.repository.owner_exists(
            self.tenant.organisation_id, owner_user_id
        ):
            raise PublicAPIError("owner_not_found", "The selected owner was not found.", 404)
        start_at = datetime.combine(start_date, time.min, timezone).astimezone(UTC)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, timezone).astimezone(UTC)
        return SalesAnalyticsFilters(
            start_date=start_date,
            end_date=end_date,
            timezone_name=timezone.key,
            timezone=timezone,
            start_at=start_at,
            end_at=end_at,
            pipeline_id=pipeline_id,
            owner_user_id=owner_user_id,
        )

    async def metadata(self, *, now: datetime | None = None) -> SalesInsightsMetadataResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        pipeline_records = await self.repository.pipelines(self.tenant.organisation_id, include_archived=True)
        owners = await self.repository.owners(self.tenant.organisation_id)
        return SalesInsightsMetadataResponse(
            current_user_id=self.tenant.user_id,
            pipelines=[
                SalesInsightsPipelineResponse(
                    id=pipeline.id,
                    name=pipeline.name,
                    is_default=pipeline.is_default,
                    active=pipeline.active,
                    stages=[
                        SalesInsightsStageResponse(
                            id=stage.id,
                            name=stage.name,
                            position=stage.position,
                            stage_type=cast(Literal["open", "won", "lost"], stage.stage_type),
                            active=stage.active,
                        )
                        for stage in stages
                    ],
                )
                for pipeline, stages in pipeline_records
            ],
            owners=[
                SalesInsightsOwnerResponse(
                    user_id=owner.user_id,
                    display_name=owner.display_name,
                    active=owner.active,
                )
                for owner in owners
            ],
            metrics=sales_metric_definitions(),
            maximum_range_days=MAXIMUM_RANGE_DAYS,
            generated_at=generated_at,
        )

    async def overview(
        self,
        filters: SalesAnalyticsFilters,
        *,
        now: datetime | None = None,
    ) -> SalesOverviewResponse:
        generated_at = _utc(now or datetime.now(UTC))
        opportunities = await self.repository.opportunities(
            self.tenant.organisation_id,
            pipeline_id=filters.pipeline_id,
            owner_user_id=filters.owner_user_id,
        )
        closed = self._closed_in_range(opportunities, filters)
        won = [opportunity for opportunity in closed if opportunity.status == "won"]
        lost = [opportunity for opportunity in closed if opportunity.status == "lost"]
        created = [
            opportunity
            for opportunity in opportunities
            if filters.start_at <= _utc(opportunity.created_at) < filters.end_at
        ]
        cycles = self._cycle_days(closed, filters.timezone)
        won_values, unvalued_won_count = self._currency_totals(won)
        return SalesOverviewResponse(
            scope=self._scope(filters, generated_at),
            open_opportunity_count=sum(opportunity.status in {"open", "on_hold"} for opportunity in opportunities),
            opportunities_created_count=len(created),
            won_count=len(won),
            lost_count=len(lost),
            closed_count=len(closed),
            win_rate=_rate(len(won), len(closed)),
            median_sales_cycle_days=_decimal_median(cycles),
            won_values=won_values,
            unvalued_won_count=unvalued_won_count,
            has_opportunities=bool(opportunities),
        )

    async def funnel(
        self,
        filters: SalesAnalyticsFilters,
        *,
        now: datetime | None = None,
    ) -> SalesFunnelResponse:
        if filters.pipeline_id is None:
            raise PublicAPIError("pipeline_required", "Choose one pipeline to view its funnel.", 422)
        generated_at = _utc(now or datetime.now(UTC))
        pipeline_record = await self.repository.pipeline(self.tenant.organisation_id, filters.pipeline_id)
        if pipeline_record is None:
            raise PublicAPIError("pipeline_not_found", "The selected pipeline was not found.", 404)
        pipeline, all_stages = pipeline_record
        opportunities = await self.repository.opportunities(
            self.tenant.organisation_id,
            owner_user_id=filters.owner_user_id,
        )
        opportunities_by_id = {opportunity.id: opportunity for opportunity in opportunities}
        events = await self.repository.stage_events(
            self.tenant.organisation_id,
            set(opportunities_by_id),
            pipeline_id=pipeline.id,
        )
        events_by_opportunity = self._events_by_opportunity(events)
        first_reliable_entries: dict[UUID, OpportunityStageEvent] = {}
        reliable_opportunity_ids: set[UUID] = set()
        baseline_opportunity_ids: set[UUID] = set()
        earliest_reliable: datetime | None = None
        for opportunity_id, opportunity_events in events_by_opportunity.items():
            entries = [event for event in opportunity_events if event.to_pipeline_id == pipeline.id]
            reliable = [event for event in entries if not event.is_baseline and event.source != "migration_baseline"]
            if reliable:
                first = reliable[0]
                first_reliable_entries[opportunity_id] = first
                reliable_opportunity_ids.add(opportunity_id)
                changed_at = _utc(first.changed_at)
                earliest_reliable = changed_at if earliest_reliable is None else min(earliest_reliable, changed_at)
            elif entries and all(event.is_baseline or event.source == "migration_baseline" for event in entries):
                baseline_opportunity_ids.add(opportunity_id)

        cohort_ids = {
            opportunity_id
            for opportunity_id, event in first_reliable_entries.items()
            if filters.start_at <= _utc(event.changed_at) < filters.end_at
        }
        cohort = [opportunities_by_id[opportunity_id] for opportunity_id in sorted(cohort_ids, key=str)]
        stage_positions = {stage.id: stage.position for stage in all_stages}
        open_stages = sorted(
            (stage for stage in all_stages if stage.stage_type == "open"), key=lambda item: item.position
        )
        stage_results = [
            self._funnel_stage(
                stage,
                cohort_ids,
                opportunities_by_id,
                events_by_opportunity,
                stage_positions,
                pipeline.id,
            )
            for stage in open_stages
        ]
        duration_values: dict[UUID, list[Decimal]] = defaultdict(list)
        for event in events:
            if (
                event.from_pipeline_id != pipeline.id
                or event.from_stage_id is None
                or event.from_stage_type != "open"
                or event.previous_stage_entered_at is None
                or not (filters.start_at <= _utc(event.changed_at) < filters.end_at)
            ):
                continue
            previous_entry_was_reliable = any(
                prior.to_pipeline_id == pipeline.id
                and prior.to_stage_id == event.from_stage_id
                and not prior.is_baseline
                and prior.source != "migration_baseline"
                and _utc(prior.changed_at) == _utc(event.previous_stage_entered_at)
                for prior in events_by_opportunity.get(event.opportunity_id, [])
            )
            if not previous_entry_was_reliable:
                continue
            seconds = (_utc(event.changed_at) - _utc(event.previous_stage_entered_at)).total_seconds()
            if seconds >= 0:
                duration_values[event.from_stage_id].append(Decimal(str(seconds)) / Decimal(86_400))
        stage_durations = [
            StageDurationResponse(
                stage_id=stage.id,
                stage_name=stage.name,
                median_completed_days=_decimal_median(duration_values[stage.id]),
                completed_interval_count=len(duration_values[stage.id]),
            )
            for stage in open_stages
        ]
        baseline_in_period = {
            event.opportunity_id
            for event in events
            if event.to_pipeline_id == pipeline.id
            and (event.is_baseline or event.source == "migration_baseline")
            and filters.start_at <= _utc(event.changed_at) < filters.end_at
            and event.opportunity_id not in reliable_opportunity_ids
        }
        disclosure = (
            f"Stage conversion excludes {len(baseline_in_period)} baseline-only Opportunities in this period. "
            "Earlier stage entry and duration were not reconstructed."
            if baseline_in_period
            else "Stage conversion uses only Opportunities with a real non-baseline entry; no earlier history is reconstructed."
        )
        return SalesFunnelResponse(
            scope=self._scope(filters, generated_at),
            pipeline_id=pipeline.id,
            pipeline_name=pipeline.name,
            cohort_definition="Opportunities first entering this pipeline during the selected period; progression measured through today.",
            cohort_count=len(cohort),
            current_open_count=sum(opportunity.status in {"open", "on_hold"} for opportunity in cohort),
            current_won_count=sum(opportunity.status == "won" for opportunity in cohort),
            current_lost_count=sum(opportunity.status == "lost" for opportunity in cohort),
            stages=stage_results,
            stage_durations=stage_durations,
            coverage=StageHistoryCoverageResponse(
                reliable_opportunity_count=len(reliable_opportunity_ids),
                baseline_only_opportunity_count=len(baseline_opportunity_ids),
                earliest_reliable_event_at=earliest_reliable,
                disclosure=disclosure,
            ),
        )

    async def activity(
        self,
        filters: SalesAnalyticsFilters,
        *,
        now: datetime | None = None,
    ) -> SalesActivityResponse:
        generated_at = _utc(now or datetime.now(UTC))
        window = timedelta(days=OUTCOME_WINDOW_DAYS)
        interactions = await self.repository.completed_interactions(
            self.tenant.organisation_id,
            start_at=filters.start_at,
            end_at=filters.end_at + window,
        )
        all_opportunities = await self.repository.opportunities(self.tenant.organisation_id)
        pipeline_opportunity_ids = {
            opportunity.id
            for opportunity in all_opportunities
            if filters.pipeline_id is None or opportunity.pipeline_id == filters.pipeline_id
        }

        def in_scope(interaction: Interaction) -> bool:
            ended_at = interaction.actual_end_at
            if ended_at is None or not (filters.start_at <= _utc(ended_at) < filters.end_at):
                return False
            if filters.owner_user_id is not None and interaction.created_by_user_id != filters.owner_user_id:
                return False
            if filters.pipeline_id is not None and interaction.opportunity_id not in pipeline_opportunity_ids:
                return False
            return True

        calls = [
            interaction
            for interaction in interactions
            if interaction.interaction_type == "phone_call" and in_scope(interaction)
        ]
        meetings = [
            interaction
            for interaction in interactions
            if interaction.interaction_type in MEETING_TYPES and in_scope(interaction)
        ]
        all_meetings = [interaction for interaction in interactions if interaction.interaction_type in MEETING_TYPES]
        participant_contacts = await self.repository.meeting_participant_contacts(
            self.tenant.organisation_id,
            {interaction.id for interaction in all_meetings},
        )
        opportunity_ids = {
            interaction.opportunity_id for interaction in meetings if interaction.opportunity_id is not None
        }
        events = await self.repository.stage_events(self.tenant.organisation_id, opportunity_ids)
        events_by_opportunity = self._events_by_opportunity(events)
        pipeline_records = await self.repository.pipelines(self.tenant.organisation_id, include_archived=True)
        stage_positions = {stage.id: stage.position for _, stages in pipeline_records for stage in stages}
        call_follow_on = self._call_follow_on(calls, all_meetings, participant_contacts, generated_at)
        meeting_progression = self._meeting_progression(
            meetings,
            events_by_opportunity,
            stage_positions,
            generated_at,
        )
        outreach_available = self.settings.feature_engage_enabled and await self.repository.module_enabled(
            self.tenant.organisation_id, "engage"
        )
        outreach_follow_on: FollowOnRateResponse | None = None
        live_sends: list[LiveOutreachSendRecord] = []
        if outreach_available:
            live_sends = await self.repository.live_outreach_sends(
                self.tenant.organisation_id,
                start_at=filters.start_at,
                end_at=filters.end_at,
            )
            live_sends = [
                send
                for send in live_sends
                if (filters.owner_user_id is None or send.sender_user_id == filters.owner_user_id)
                and (
                    filters.pipeline_id is None
                    or (send.opportunity_id is not None and send.opportunity_id in pipeline_opportunity_ids)
                )
            ]
            outreach_follow_on = self._outreach_follow_on(
                live_sends,
                all_meetings,
                participant_contacts,
                generated_at,
            )
        return SalesActivityResponse(
            scope=self._scope(filters, generated_at),
            phone_calls_completed_count=len(calls),
            meetings_completed_count=len(meetings),
            calls_followed_by_meeting=call_follow_on,
            meetings_followed_by_progression=meeting_progression,
            outreach_available=outreach_available,
            live_outreach_sent_count=len(live_sends),
            outreach_followed_by_meeting=outreach_follow_on,
            association_disclosure=(
                "These are RevenueOS-recorded activities followed by a later recorded outcome within 30 days. "
                "They are associations, not attribution or proof of causation. Only fully matured outcome windows enter rates."
            ),
        )

    async def win_loss(
        self,
        filters: SalesAnalyticsFilters,
        *,
        now: datetime | None = None,
    ) -> SalesWinLossResponse:
        generated_at = _utc(now or datetime.now(UTC))
        opportunities = await self.repository.opportunities(
            self.tenant.organisation_id,
            pipeline_id=filters.pipeline_id,
            owner_user_id=filters.owner_user_id,
        )
        closed = self._closed_in_range(opportunities, filters)
        won = [opportunity for opportunity in closed if opportunity.status == "won"]
        lost = [opportunity for opportunity in closed if opportunity.status == "lost"]
        events = await self.repository.stage_events(
            self.tenant.organisation_id,
            {opportunity.id for opportunity in closed},
        )
        events_by_opportunity = self._events_by_opportunity(events)
        won_cycles = self._cycle_days(won, filters.timezone)
        lost_cycles = self._cycle_days(lost, filters.timezone)
        values, unvalued_won_count, unvalued_lost_count = self._outcome_values(won, lost)
        return SalesWinLossResponse(
            scope=self._scope(filters, generated_at),
            won_count=len(won),
            lost_count=len(lost),
            win_rate=_rate(len(won), len(closed)),
            won_reasons=self._reason_counts(won),
            lost_reasons=self._reason_counts(lost),
            loss_stages=self._loss_stages(lost, events_by_opportunity),
            sales_cycles=[
                OutcomeCycleResponse(
                    outcome="won", median_days=_decimal_median(won_cycles), sample_size=len(won_cycles)
                ),
                OutcomeCycleResponse(
                    outcome="lost", median_days=_decimal_median(lost_cycles), sample_size=len(lost_cycles)
                ),
            ],
            values=values,
            unvalued_won_count=unvalued_won_count,
            unvalued_lost_count=unvalued_lost_count,
        )

    def require_enabled(self) -> None:
        if not self.settings.feature_sales_analytics_enabled:
            raise PublicAPIError("feature_unavailable", "Sales Insights is not enabled in this environment.", 404)

    @staticmethod
    def _scope(filters: SalesAnalyticsFilters, generated_at: datetime) -> SalesInsightsScopeResponse:
        return SalesInsightsScopeResponse(
            start_date=filters.start_date,
            end_date=filters.end_date,
            timezone=filters.timezone_name,
            pipeline_id=filters.pipeline_id,
            owner_user_id=filters.owner_user_id,
            generated_at=generated_at,
        )

    @staticmethod
    def _closed_in_range(opportunities: list[Opportunity], filters: SalesAnalyticsFilters) -> list[Opportunity]:
        return [
            opportunity
            for opportunity in opportunities
            if opportunity.status in {"won", "lost"}
            and opportunity.actual_close_date is not None
            and filters.start_date <= opportunity.actual_close_date <= filters.end_date
        ]

    @staticmethod
    def _cycle_days(opportunities: list[Opportunity], timezone: ZoneInfo) -> list[Decimal]:
        values: list[Decimal] = []
        for opportunity in opportunities:
            if opportunity.actual_close_date is None:
                continue
            created_date = _utc(opportunity.created_at).astimezone(timezone).date()
            duration = (opportunity.actual_close_date - created_date).days
            if duration >= 0:
                values.append(Decimal(duration))
        return values

    @staticmethod
    def _currency_totals(opportunities: list[Opportunity]) -> tuple[list[CurrencyAmountResponse], int]:
        totals: dict[str, tuple[Decimal, int]] = {}
        unvalued = 0
        for opportunity in opportunities:
            if opportunity.estimated_value is None or opportunity.currency is None:
                unvalued += 1
                continue
            amount, count = totals.get(opportunity.currency, (Decimal(0), 0))
            totals[opportunity.currency] = (amount + opportunity.estimated_value, count + 1)
        return (
            [
                CurrencyAmountResponse(currency=currency, amount=amount, opportunity_count=count)
                for currency, (amount, count) in sorted(totals.items())
            ],
            unvalued,
        )

    @staticmethod
    def _events_by_opportunity(
        events: list[OpportunityStageEvent],
    ) -> dict[UUID, list[OpportunityStageEvent]]:
        result: dict[UUID, list[OpportunityStageEvent]] = defaultdict(list)
        for event in events:
            result[event.opportunity_id].append(event)
        for opportunity_events in result.values():
            opportunity_events.sort(key=lambda item: (_utc(item.changed_at), str(item.id)))
        return result

    @staticmethod
    def _funnel_stage(
        stage: SalesPipelineStage,
        cohort_ids: set[UUID],
        opportunities_by_id: dict[UUID, Opportunity],
        events_by_opportunity: dict[UUID, list[OpportunityStageEvent]],
        stage_positions: dict[UUID, int],
        pipeline_id: UUID,
    ) -> FunnelStageResponse:
        entered = advanced = still_open = closed_lost = other = 0
        for opportunity_id in cohort_ids:
            stage_entries = [
                event
                for event in events_by_opportunity.get(opportunity_id, [])
                if event.to_pipeline_id == pipeline_id
                and event.to_stage_id == stage.id
                and not event.is_baseline
                and event.source != "migration_baseline"
            ]
            if not stage_entries:
                continue
            entered += 1
            first_entry = stage_entries[0]
            later_events = [
                event
                for event in events_by_opportunity.get(opportunity_id, [])
                if (_utc(event.changed_at), str(event.id)) > (_utc(first_entry.changed_at), str(first_entry.id))
            ]
            progressed = any(
                (event.to_pipeline_id == pipeline_id and event.to_stage_type == "won")
                or (
                    event.to_pipeline_id == pipeline_id
                    and stage_positions.get(event.to_stage_id, -1) > stage.position
                    and event.to_stage_type == "open"
                )
                for event in later_events
            )
            if progressed:
                advanced += 1
                continue
            status = opportunities_by_id[opportunity_id].status
            if status in {"open", "on_hold"}:
                still_open += 1
            elif status == "lost":
                closed_lost += 1
            else:
                other += 1
        return FunnelStageResponse(
            stage_id=stage.id,
            stage_name=stage.name,
            position=stage.position,
            entered_count=entered,
            advanced_count=advanced,
            still_open_count=still_open,
            closed_lost_count=closed_lost,
            other_not_advanced_count=other,
            advance_rate=_rate(advanced, entered),
        )

    @staticmethod
    def _same_relationship(
        *,
        source_company_id: UUID | None,
        source_contact_id: UUID | None,
        meeting: Interaction,
        participant_contacts: dict[UUID, set[UUID]],
    ) -> bool:
        return bool(
            source_company_id is not None
            and meeting.company_id == source_company_id
            or source_contact_id is not None
            and source_contact_id in participant_contacts.get(meeting.id, set())
        )

    def _call_follow_on(
        self,
        calls: list[Interaction],
        meetings: list[Interaction],
        participant_contacts: dict[UUID, set[UUID]],
        generated_at: datetime,
    ) -> FollowOnRateResponse:
        mature_before = generated_at - timedelta(days=OUTCOME_WINDOW_DAYS)
        mature = [
            call for call in calls if call.actual_end_at is not None and _utc(call.actual_end_at) <= mature_before
        ]
        immature = len(calls) - len(mature)
        associated = [call for call in mature if call.company_id is not None or call.contact_id is not None]
        outcome_count = 0
        for call in associated:
            actual_end_at = call.actual_end_at
            assert actual_end_at is not None
            ended_at = _utc(actual_end_at)
            deadline = ended_at + timedelta(days=OUTCOME_WINDOW_DAYS)
            if any(
                meeting.actual_end_at is not None
                and ended_at < _utc(meeting.actual_end_at) <= deadline
                and self._same_relationship(
                    source_company_id=call.company_id,
                    source_contact_id=call.contact_id,
                    meeting=meeting,
                    participant_contacts=participant_contacts,
                )
                for meeting in meetings
            ):
                outcome_count += 1
        return FollowOnRateResponse(
            cohort_count=len(calls),
            eligible_mature_count=len(associated),
            followed_by_outcome_count=outcome_count,
            rate=_rate(outcome_count, len(associated)),
            immature_count=immature,
            excluded_unassociated_count=len(mature) - len(associated),
            excluded_untracked_count=0,
        )

    @staticmethod
    def _is_forward_event(event: OpportunityStageEvent, stage_positions: dict[UUID, int]) -> bool:
        if event.to_stage_type == "won":
            return True
        return bool(
            event.from_pipeline_id is not None
            and event.from_pipeline_id == event.to_pipeline_id
            and event.from_stage_id is not None
            and event.from_stage_type == "open"
            and event.to_stage_type == "open"
            and stage_positions.get(event.to_stage_id, -1) > stage_positions.get(event.from_stage_id, -1)
        )

    def _meeting_progression(
        self,
        meetings: list[Interaction],
        events_by_opportunity: dict[UUID, list[OpportunityStageEvent]],
        stage_positions: dict[UUID, int],
        generated_at: datetime,
    ) -> FollowOnRateResponse:
        mature_before = generated_at - timedelta(days=OUTCOME_WINDOW_DAYS)
        mature = [
            meeting
            for meeting in meetings
            if meeting.actual_end_at is not None and _utc(meeting.actual_end_at) <= mature_before
        ]
        immature = len(meetings) - len(mature)
        associated = [meeting for meeting in mature if meeting.opportunity_id is not None]
        tracked: list[Interaction] = []
        for meeting in associated:
            actual_end_at = meeting.actual_end_at
            opportunity_id = meeting.opportunity_id
            assert actual_end_at is not None
            assert opportunity_id is not None
            ended_at = _utc(actual_end_at)
            history = events_by_opportunity.get(opportunity_id, [])
            if any(
                not event.is_baseline and event.source != "migration_baseline" and _utc(event.changed_at) <= ended_at
                for event in history
            ):
                tracked.append(meeting)
        outcome_count = 0
        for meeting in tracked:
            actual_end_at = meeting.actual_end_at
            opportunity_id = meeting.opportunity_id
            assert actual_end_at is not None
            assert opportunity_id is not None
            ended_at = _utc(actual_end_at)
            deadline = ended_at + timedelta(days=OUTCOME_WINDOW_DAYS)
            history = events_by_opportunity.get(opportunity_id, [])
            if any(
                ended_at < _utc(event.changed_at) <= deadline and self._is_forward_event(event, stage_positions)
                for event in history
            ):
                outcome_count += 1
        return FollowOnRateResponse(
            cohort_count=len(meetings),
            eligible_mature_count=len(tracked),
            followed_by_outcome_count=outcome_count,
            rate=_rate(outcome_count, len(tracked)),
            immature_count=immature,
            excluded_unassociated_count=len(mature) - len(associated),
            excluded_untracked_count=len(associated) - len(tracked),
        )

    def _outreach_follow_on(
        self,
        sends: list[LiveOutreachSendRecord],
        meetings: list[Interaction],
        participant_contacts: dict[UUID, set[UUID]],
        generated_at: datetime,
    ) -> FollowOnRateResponse:
        mature_before = generated_at - timedelta(days=OUTCOME_WINDOW_DAYS)
        mature = [send for send in sends if _utc(send.completed_at) <= mature_before]
        associated = [send for send in mature if send.company_id is not None or send.contact_id is not None]
        outcome_count = 0
        for send in associated:
            sent_at = _utc(send.completed_at)
            deadline = sent_at + timedelta(days=OUTCOME_WINDOW_DAYS)
            if any(
                meeting.actual_end_at is not None
                and sent_at < _utc(meeting.actual_end_at) <= deadline
                and self._same_relationship(
                    source_company_id=send.company_id,
                    source_contact_id=send.contact_id,
                    meeting=meeting,
                    participant_contacts=participant_contacts,
                )
                for meeting in meetings
            ):
                outcome_count += 1
        return FollowOnRateResponse(
            cohort_count=len(sends),
            eligible_mature_count=len(associated),
            followed_by_outcome_count=outcome_count,
            rate=_rate(outcome_count, len(associated)),
            immature_count=len(sends) - len(mature),
            excluded_unassociated_count=len(mature) - len(associated),
            excluded_untracked_count=0,
        )

    @staticmethod
    def _reason_counts(opportunities: list[Opportunity]) -> list[OutcomeReasonResponse]:
        counts: dict[str, int] = defaultdict(int)
        for opportunity in opportunities:
            counts[opportunity.outcome_reason or "unknown"] += 1
        total = len(opportunities)
        return [
            OutcomeReasonResponse(
                reason=reason,
                label=REASON_LABELS.get(reason, reason.replace("_", " ").title()),
                count=count,
                percentage=_rate(count, total),
            )
            for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    @staticmethod
    def _loss_stages(
        opportunities: list[Opportunity],
        events_by_opportunity: dict[UUID, list[OpportunityStageEvent]],
    ) -> list[LossStageResponse]:
        counts: dict[tuple[UUID | None, str], int] = defaultdict(int)
        for opportunity in opportunities:
            lost_events = [
                event for event in events_by_opportunity.get(opportunity.id, []) if event.to_stage_type == "lost"
            ]
            if not lost_events:
                counts[(None, "Unknown stage")] += 1
                continue
            final = lost_events[-1]
            stage_name = final.from_stage_name if final.from_stage_type == "open" else None
            counts[(final.from_stage_id if stage_name else None, stage_name or "Unknown stage")] += 1
        return [
            LossStageResponse(stage_id=stage_id, stage_name=stage_name, count=count)
            for (stage_id, stage_name), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][1]))
        ]

    @staticmethod
    def _outcome_values(
        won: list[Opportunity],
        lost: list[Opportunity],
    ) -> tuple[list[OutcomeCurrencyResponse], int, int]:
        responses: list[OutcomeCurrencyResponse] = []
        unvalued: dict[str, int] = {"won": 0, "lost": 0}
        for outcome, opportunities in (("won", won), ("lost", lost)):
            by_currency: dict[str, list[Decimal]] = defaultdict(list)
            for opportunity in opportunities:
                if opportunity.estimated_value is None or opportunity.currency is None:
                    unvalued[outcome] += 1
                else:
                    by_currency[opportunity.currency].append(opportunity.estimated_value)
            for currency, amounts in sorted(by_currency.items()):
                median_amount = Decimal(statistics.median(amounts)).quantize(Decimal("0.01"))
                responses.append(
                    OutcomeCurrencyResponse(
                        outcome=cast(Literal["won", "lost"], outcome),
                        currency=currency,
                        amount=sum(amounts, Decimal(0)),
                        median_amount=median_amount,
                        opportunity_count=len(amounts),
                    )
                )
        return responses, unvalued["won"], unvalued["lost"]


class SalesMetricService:
    """WO-037 handoff: observe only registered canonical metrics."""

    def __init__(self, analytics: SalesAnalyticsService) -> None:
        self.analytics = analytics

    async def observe(
        self,
        metric_id: str,
        filters: SalesAnalyticsFilters,
        *,
        currency: str | None,
        now: datetime | None = None,
    ) -> SalesMetricObservationResponse:
        definition = SALES_METRIC_REGISTRY.get(metric_id)
        if definition is None:
            raise PublicAPIError("metric_not_found", "The selected canonical metric was not found.", 404)
        generated_at = _utc(now or datetime.now(UTC))
        value: Decimal | int | None
        numerator: int | None = None
        denominator: int | None = None
        sample_size = 0
        normalised_currency: str | None = None
        if metric_id in {
            "opportunities_created_count",
            "opportunities_closed_won_count",
            "opportunities_closed_lost_count",
            "closed_win_rate",
            "median_sales_cycle_days",
            "won_value",
        }:
            overview = await self.analytics.overview(filters, now=generated_at)
            if metric_id == "opportunities_created_count":
                value = overview.opportunities_created_count
                sample_size = overview.opportunities_created_count
            elif metric_id == "opportunities_closed_won_count":
                value = overview.won_count
                sample_size = overview.won_count
            elif metric_id == "opportunities_closed_lost_count":
                value = overview.lost_count
                sample_size = overview.lost_count
            elif metric_id == "closed_win_rate":
                value = overview.win_rate
                numerator = overview.won_count
                denominator = overview.closed_count
                sample_size = overview.closed_count
            elif metric_id == "median_sales_cycle_days":
                value = overview.median_sales_cycle_days
                sample_size = overview.closed_count
            else:
                if currency is None or len(currency.strip()) != 3:
                    raise PublicAPIError("currency_required", "Choose one three-letter currency for Won value.", 422)
                normalised_currency = currency.strip().upper()
                matching = next((item for item in overview.won_values if item.currency == normalised_currency), None)
                value = matching.amount if matching is not None else Decimal(0)
                sample_size = matching.opportunity_count if matching is not None else 0
        else:
            activity = await self.analytics.activity(filters, now=generated_at)
            if metric_id == "meetings_completed_count":
                value = activity.meetings_completed_count
                sample_size = activity.meetings_completed_count
            elif metric_id == "phone_calls_completed_count":
                value = activity.phone_calls_completed_count
                sample_size = activity.phone_calls_completed_count
            elif metric_id == "calls_followed_by_meeting_rate_30d":
                value = activity.calls_followed_by_meeting.rate
                numerator = activity.calls_followed_by_meeting.followed_by_outcome_count
                denominator = activity.calls_followed_by_meeting.eligible_mature_count
                sample_size = activity.calls_followed_by_meeting.eligible_mature_count
            elif metric_id == "meetings_followed_by_progression_rate_30d":
                value = activity.meetings_followed_by_progression.rate
                numerator = activity.meetings_followed_by_progression.followed_by_outcome_count
                denominator = activity.meetings_followed_by_progression.eligible_mature_count
                sample_size = activity.meetings_followed_by_progression.eligible_mature_count
            else:
                value = activity.live_outreach_sent_count
                sample_size = activity.live_outreach_sent_count
        return SalesMetricObservationResponse(
            metric_id=definition.id,
            definition_version=definition.definition_version,
            start_date=filters.start_date,
            end_date=filters.end_date,
            timezone=filters.timezone_name,
            pipeline_id=filters.pipeline_id,
            owner_user_id=filters.owner_user_id,
            currency=normalised_currency,
            value=value,
            numerator=numerator,
            denominator=denominator,
            sample_size=sample_size,
            generated_at=generated_at,
        )
