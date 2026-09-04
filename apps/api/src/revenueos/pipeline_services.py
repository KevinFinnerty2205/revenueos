from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import (
    CRMRecordChange,
    IntegrationConnection,
    Opportunity,
    OpportunityAuditEvent,
    OpportunityStageEvent,
    OrganisationCRMSetting,
    SalesPipeline,
    SalesPipelineStage,
    Task,
)
from revenueos.pipeline_contracts import (
    OpportunityCloseLostRequest,
    OpportunityCloseWonRequest,
    OpportunityPipelineResponse,
    OpportunityReopenRequest,
    OpportunityStageEventResponse,
    OpportunityStageTransitionRequest,
    PipelineBoardResponse,
    PipelineCardResponse,
    PipelineCreate,
    PipelineOpenStageCreate,
    PipelineResponse,
    PipelineStageResponse,
    PipelineStageType,
    PipelineStageUpdate,
    PipelineSummaryResponse,
    PipelineUpdate,
    PipelineValueSummary,
)
from revenueos.pipeline_repositories import (
    PipelineOpportunityRecord,
    PipelineRepository,
    ensure_default_pipeline,
    initial_stage_for,
    legacy_stage_for,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.pipeline")


class PipelineService:
    """Server-authoritative workflow state; it never writes Evidence, Brain or Methodology."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.repository = PipelineRepository(session)
        self.tenant = tenant
        self.settings = settings

    async def list_pipelines(self, *, include_archived: bool = False) -> list[PipelineResponse]:
        await ensure_default_pipeline(self.repository.session, self.tenant.organisation_id)
        await self.repository.session.commit()
        pipelines = await self.repository.pipelines(
            self.tenant.organisation_id,
            include_archived=include_archived,
        )
        return [await self._pipeline_response(pipeline, include_archived=include_archived) for pipeline in pipelines]

    async def create_pipeline(self, request: PipelineCreate) -> PipelineResponse:
        await self._require_admin_configuration()
        if await self.repository.active_pipeline_count(self.tenant.organisation_id) >= 5:
            raise PublicAPIError("pipeline_limit_reached", "An organisation can have up to five active pipelines.", 409)
        existing = await self.repository.pipelines(self.tenant.organisation_id)
        if any(item.name.casefold() == request.name.casefold() for item in existing):
            raise PublicAPIError("pipeline_name_exists", "Choose a different pipeline name.", 409)
        pipeline = SalesPipeline(
            organisation_id=self.tenant.organisation_id,
            name=request.name,
            is_default=request.is_default,
        )
        if request.is_default:
            for item in existing:
                item.is_default = False
            await self.repository.flush()
        self.repository.add(pipeline)
        await self.repository.flush()
        for position, draft in enumerate(request.stages):
            self.repository.add(
                SalesPipelineStage(
                    organisation_id=self.tenant.organisation_id,
                    pipeline_id=pipeline.id,
                    stage_key=self.repository.new_stage_key(),
                    name=draft.name,
                    position=position,
                    stage_type=draft.stage_type,
                    guidance=draft.guidance,
                )
            )
        await self._commit("The pipeline could not be created.")
        await self.repository.refresh(pipeline)
        self._log("pipeline_created", pipeline_id=pipeline.id)
        return await self._pipeline_response(pipeline)

    async def update_pipeline(self, pipeline_id: UUID, request: PipelineUpdate) -> PipelineResponse:
        await self._require_admin_configuration()
        pipeline = await self._pipeline_or_404(pipeline_id, for_update=True)
        if not pipeline.active:
            raise PublicAPIError("pipeline_archived", "Archived pipelines cannot be changed.", 409)
        if request.name is not None:
            others = await self.repository.pipelines(self.tenant.organisation_id)
            if any(item.id != pipeline.id and item.name.casefold() == request.name.casefold() for item in others):
                raise PublicAPIError("pipeline_name_exists", "Choose a different pipeline name.", 409)
            pipeline.name = request.name
        if request.is_default is True and not pipeline.is_default:
            for item in await self.repository.pipelines(self.tenant.organisation_id, for_update=True):
                item.is_default = False
            # The database enforces one active default with an immediate unique
            # index, so retire the previous default before promoting this one.
            await self.repository.flush()
            pipeline.is_default = True
        elif request.is_default is False and pipeline.is_default:
            raise PublicAPIError("default_pipeline_required", "Choose another default pipeline first.", 409)
        pipeline.updated_at = datetime.now(UTC)
        await self._commit("The pipeline could not be updated.")
        await self.repository.refresh(pipeline)
        return await self._pipeline_response(pipeline)

    async def add_open_stage(
        self,
        pipeline_id: UUID,
        request: PipelineOpenStageCreate,
    ) -> PipelineResponse:
        await self._require_admin_configuration()
        pipeline = await self._pipeline_or_404(pipeline_id, for_update=True)
        if not pipeline.active:
            raise PublicAPIError("pipeline_archived", "Archived pipelines cannot be changed.", 409)
        stages = await self.repository.stages(
            self.tenant.organisation_id,
            pipeline.id,
            for_update=True,
        )
        if len(stages) >= 12:
            raise PublicAPIError("pipeline_stage_limit_reached", "A pipeline can have up to 12 stages.", 409)
        self._require_unique_stage_name(stages, request.name)
        open_count = sum(stage.stage_type == "open" for stage in stages)
        insertion = min(request.position, open_count)
        stage = SalesPipelineStage(
            organisation_id=self.tenant.organisation_id,
            pipeline_id=pipeline.id,
            stage_key=self.repository.new_stage_key(),
            name=request.name,
            position=insertion,
            stage_type="open",
            guidance=request.guidance,
        )
        stages.insert(insertion, stage)
        self.repository.add(stage)
        self._renumber(stages)
        pipeline.updated_at = datetime.now(UTC)
        await self._commit("The stage could not be added.")
        await self.repository.refresh(pipeline)
        return await self._pipeline_response(pipeline)

    async def update_stage(
        self,
        pipeline_id: UUID,
        stage_id: UUID,
        request: PipelineStageUpdate,
    ) -> PipelineResponse:
        await self._require_admin_configuration()
        pipeline = await self._pipeline_or_404(pipeline_id, for_update=True)
        stage = await self._stage_or_404(stage_id, for_update=True)
        if stage.pipeline_id != pipeline.id:
            raise PublicAPIError("pipeline_stage_not_found", "The pipeline stage was not found.", 404)
        if not pipeline.active or not stage.active:
            raise PublicAPIError("pipeline_stage_archived", "Archived pipeline stages cannot be changed.", 409)
        stages = await self.repository.stages(
            self.tenant.organisation_id,
            pipeline.id,
            for_update=True,
        )
        if request.name is not None:
            self._require_unique_stage_name(stages, request.name, exclude_id=stage.id)
            stage.name = request.name
        if "guidance" in request.model_fields_set:
            stage.guidance = request.guidance
        if request.position is not None:
            stages.remove(stage)
            if stage.stage_type == "open":
                open_count = sum(item.stage_type == "open" for item in stages)
                insertion = min(request.position, open_count)
            else:
                first_final = sum(item.stage_type == "open" for item in stages)
                insertion = max(first_final, min(request.position, len(stages)))
            stages.insert(insertion, stage)
        self._renumber(stages)
        pipeline.updated_at = datetime.now(UTC)
        await self._commit("The stage could not be updated.")
        await self.repository.refresh(pipeline)
        return await self._pipeline_response(pipeline)

    async def archive_stage(self, pipeline_id: UUID, stage_id: UUID) -> PipelineResponse:
        await self._require_admin_configuration()
        pipeline = await self._pipeline_or_404(pipeline_id, for_update=True)
        stage = await self._stage_or_404(stage_id, for_update=True)
        if stage.pipeline_id != pipeline.id:
            raise PublicAPIError("pipeline_stage_not_found", "The pipeline stage was not found.", 404)
        if stage.stage_type != "open":
            raise PublicAPIError("final_stage_required", "Won and Lost stages cannot be archived.", 409)
        stages = await self.repository.stages(
            self.tenant.organisation_id,
            pipeline.id,
            for_update=True,
        )
        counts = await self.repository.stage_counts(self.tenant.organisation_id, pipeline.id)
        if counts.get(stage.id, 0):
            raise PublicAPIError(
                "pipeline_stage_in_use",
                "Move current opportunities out of this stage before archiving it.",
                409,
            )
        if sum(item.stage_type == "open" for item in stages) <= 1:
            raise PublicAPIError("open_stage_required", "A pipeline needs at least one open stage.", 409)
        stage.active = False
        stage.archived_at = datetime.now(UTC)
        self._renumber([item for item in stages if item.id != stage.id])
        pipeline.updated_at = datetime.now(UTC)
        await self._commit("The stage could not be archived.")
        await self.repository.refresh(pipeline)
        return await self._pipeline_response(pipeline, include_archived=True)

    async def archive_pipeline(self, pipeline_id: UUID) -> PipelineResponse:
        await self._require_admin_configuration()
        pipeline = await self._pipeline_or_404(pipeline_id, for_update=True)
        if pipeline.is_default:
            raise PublicAPIError("default_pipeline_required", "Choose another default pipeline first.", 409)
        open_count = await self.repository.session.scalar(
            select(func.count())
            .select_from(Opportunity)
            .where(
                Opportunity.organisation_id == self.tenant.organisation_id,
                Opportunity.pipeline_id == pipeline.id,
                Opportunity.status.in_(("open", "on_hold")),
                Opportunity.archived_at.is_(None),
            )
        )
        if open_count:
            raise PublicAPIError(
                "pipeline_in_use",
                "Move or close current opportunities before archiving this pipeline.",
                409,
            )
        pipeline.active = False
        pipeline.archived_at = datetime.now(UTC)
        pipeline.updated_at = datetime.now(UTC)
        await self._commit("The pipeline could not be archived.")
        await self.repository.refresh(pipeline)
        return await self._pipeline_response(pipeline, include_archived=True)

    async def board(
        self,
        *,
        pipeline_id: UUID | None,
        closed: bool,
        owner_user_id: UUID | None,
        stage_id: UUID | None,
        company_id: UUID | None,
        search: str | None,
        attention_only: bool,
        close_date_filter: str | None,
    ) -> PipelineBoardResponse:
        default, _ = await ensure_default_pipeline(self.repository.session, self.tenant.organisation_id)
        await self.repository.session.commit()
        selected = default if pipeline_id is None else await self._pipeline_or_404(pipeline_id)
        if not selected.active:
            raise PublicAPIError("pipeline_archived", "Choose an active pipeline.", 409)
        records = await self.repository.board_records(
            self.tenant.organisation_id,
            selected.id,
            closed=closed,
            owner_user_id=owner_user_id,
            stage_id=stage_id,
            company_id=company_id,
            search=search,
        )
        task_map = await self._tasks_for([record.opportunity.id for record in records])
        cards = [self._card(record, task_map.get(record.opportunity.id, [])) for record in records]
        today = datetime.now(UTC).date()
        if close_date_filter == "overdue":
            cards = [
                card for card in cards if card.expected_close_date is not None and card.expected_close_date < today
            ]
        elif close_date_filter == "this_month":
            cards = [card for card in cards if self._is_this_month(card.expected_close_date, today)]
        elif close_date_filter == "next_30_days":
            cards = [
                card
                for card in cards
                if card.expected_close_date is not None
                and today <= card.expected_close_date <= today + timedelta(days=30)
            ]
        if attention_only:
            cards = [card for card in cards if card.attention_reasons]
        cards.sort(
            key=lambda card: (
                not bool(card.attention_reasons),
                card.expected_close_date is None,
                card.expected_close_date or date.max,
                card.opportunity_name.casefold(),
            )
        )
        pipelines = await self.repository.pipelines(self.tenant.organisation_id)
        allowed, external, message = await self._authority()
        return PipelineBoardResponse(
            pipeline=await self._pipeline_response(selected),
            pipelines=[await self._pipeline_response(item) for item in pipelines],
            view="closed" if closed else "open",
            summary=self._summary(cards),
            cards=cards,
            stage_changes_allowed=allowed,
            managed_externally=external,
            authority_message=message,
            manager_intelligence_available=(
                self.settings.feature_manager_intelligence_enabled and self.tenant.can_manage()
            ),
            generated_at=datetime.now(UTC),
        )

    async def opportunity_pipeline(self, opportunity_id: UUID) -> OpportunityPipelineResponse:
        opportunity = await self._opportunity_or_404(opportunity_id, for_update=True)
        await self._ensure_assignment(opportunity)
        await self.repository.session.commit()
        record = await self.repository.opportunity_record(self.tenant.organisation_id, opportunity.id)
        if record is None:
            raise PublicAPIError("pipeline_state_unavailable", "Pipeline state is unavailable.", 409)
        pipelines = await self.repository.pipelines(self.tenant.organisation_id)
        allowed, external, message = await self._authority()
        return OpportunityPipelineResponse(
            opportunity_id=opportunity.id,
            status=cast(Literal["open", "won", "lost", "on_hold"], opportunity.status),
            pipeline=await self._pipeline_response(record.pipeline),
            stage=self._stage_response(record.stage),
            stage_entered_at=opportunity.stage_entered_at,
            stage_tracking_started_at=opportunity.stage_tracking_started_at,
            days_in_stage=self._days_in_stage(opportunity.stage_entered_at),
            actual_close_date=opportunity.actual_close_date,
            outcome_reason=opportunity.outcome_reason,
            outcome_note=opportunity.outcome_note,
            outcome_provenance=cast(Literal["seller_reported"] | None, opportunity.outcome_provenance),
            available_pipelines=[await self._pipeline_response(item) for item in pipelines],
            history=[
                self._event_response(item.event, item.actor_name)
                for item in await self.repository.events(self.tenant.organisation_id, opportunity.id)
            ],
            stage_changes_allowed=allowed,
            managed_externally=external,
            authority_message=message,
        )

    async def move_stage(
        self,
        opportunity_id: UUID,
        request: OpportunityStageTransitionRequest,
    ) -> OpportunityPipelineResponse:
        await self._require_stage_change_authority()
        opportunity = await self._opportunity_or_404(opportunity_id, for_update=True)
        await self._ensure_assignment(opportunity)
        if (
            await self.repository.event_for_idempotency(
                self.tenant.organisation_id, opportunity.id, request.idempotency_key
            )
            is not None
        ):
            await self.repository.session.commit()
            return await self.opportunity_pipeline(opportunity.id)
        self._check_current_stage(opportunity, request.expected_current_stage_id)
        if opportunity.status not in ("open", "on_hold"):
            raise PublicAPIError("opportunity_closed", "Reopen this opportunity before moving it.", 409)
        target = await self._stage_or_404(request.target_stage_id)
        target_pipeline = await self._pipeline_or_404(target.pipeline_id)
        if not target.active or not target_pipeline.active:
            raise PublicAPIError("pipeline_stage_archived", "Choose an active stage.", 409)
        if target.stage_type != "open":
            raise PublicAPIError("closure_flow_required", "Use Mark Won or Mark Lost for a final stage.", 409)
        if opportunity.pipeline_stage_id == target.id:
            await self.repository.session.commit()
            return await self.opportunity_pipeline(opportunity.id)
        current = await self._stage_or_404(cast(UUID, opportunity.pipeline_stage_id))
        self._append_event(opportunity, current, target, request.idempotency_key, source="manual")
        old_values = self._workflow_values(opportunity)
        now = datetime.now(UTC)
        opportunity.pipeline_id = target.pipeline_id
        opportunity.pipeline_stage_id = target.id
        opportunity.stage = legacy_stage_for(target)
        opportunity.status = "open"
        opportunity.stage_entered_at = now
        opportunity.stage_tracking_started_at = opportunity.stage_tracking_started_at or now
        opportunity.updated_at = now
        self._record_domain_changes(opportunity, old_values, "stage_changed")
        await self._commit("The opportunity stage could not be changed.")
        self._log("opportunity_stage_changed", opportunity_id=opportunity.id, stage_id=target.id)
        return await self.opportunity_pipeline(opportunity.id)

    async def close_won(
        self,
        opportunity_id: UUID,
        request: OpportunityCloseWonRequest,
    ) -> OpportunityPipelineResponse:
        return await self._close(opportunity_id, request, outcome="won")

    async def close_lost(
        self,
        opportunity_id: UUID,
        request: OpportunityCloseLostRequest,
    ) -> OpportunityPipelineResponse:
        return await self._close(opportunity_id, request, outcome="lost")

    async def reopen(
        self,
        opportunity_id: UUID,
        request: OpportunityReopenRequest,
    ) -> OpportunityPipelineResponse:
        await self._require_stage_change_authority()
        opportunity = await self._opportunity_or_404(opportunity_id, for_update=True)
        await self._ensure_assignment(opportunity)
        if (
            await self.repository.event_for_idempotency(
                self.tenant.organisation_id, opportunity.id, request.idempotency_key
            )
            is not None
        ):
            await self.repository.session.commit()
            return await self.opportunity_pipeline(opportunity.id)
        self._check_current_stage(opportunity, request.expected_current_stage_id)
        if opportunity.status not in ("won", "lost"):
            raise PublicAPIError("opportunity_not_closed", "This opportunity is already open.", 409)
        target = await self._stage_or_404(request.target_stage_id)
        target_pipeline = await self._pipeline_or_404(target.pipeline_id)
        if target.stage_type != "open" or not target.active or not target_pipeline.active:
            raise PublicAPIError("pipeline_stage_invalid", "Choose an active open stage.", 422)
        current = await self._stage_or_404(cast(UUID, opportunity.pipeline_stage_id))
        self._append_event(opportunity, current, target, request.idempotency_key, source="manual")
        old_values = self._workflow_values(opportunity)
        now = datetime.now(UTC)
        opportunity.pipeline_id = target.pipeline_id
        opportunity.pipeline_stage_id = target.id
        opportunity.stage = legacy_stage_for(target)
        opportunity.status = "open"
        opportunity.stage_entered_at = now
        opportunity.actual_close_date = None
        opportunity.outcome_reason = None
        opportunity.outcome_note = None
        opportunity.outcome_provenance = None
        opportunity.updated_at = now
        self._record_domain_changes(opportunity, old_values, "reopened")
        await self._commit("The opportunity could not be reopened.")
        self._log("opportunity_reopened", opportunity_id=opportunity.id, stage_id=target.id)
        return await self.opportunity_pipeline(opportunity.id)

    async def _close(
        self,
        opportunity_id: UUID,
        request: OpportunityCloseWonRequest | OpportunityCloseLostRequest,
        *,
        outcome: str,
    ) -> OpportunityPipelineResponse:
        await self._require_stage_change_authority()
        if request.actual_close_date > datetime.now(UTC).date():
            raise PublicAPIError("actual_close_date_future", "Actual close date cannot be in the future.", 422)
        opportunity = await self._opportunity_or_404(opportunity_id, for_update=True)
        await self._ensure_assignment(opportunity)
        if (
            await self.repository.event_for_idempotency(
                self.tenant.organisation_id, opportunity.id, request.idempotency_key
            )
            is not None
        ):
            await self.repository.session.commit()
            return await self.opportunity_pipeline(opportunity.id)
        self._check_current_stage(opportunity, request.expected_current_stage_id)
        if opportunity.status not in ("open", "on_hold"):
            raise PublicAPIError("opportunity_closed", "This opportunity is already closed.", 409)
        stages = await self.repository.stages(
            self.tenant.organisation_id,
            cast(UUID, opportunity.pipeline_id),
        )
        target = next((stage for stage in stages if stage.stage_type == outcome), None)
        if target is None:
            raise PublicAPIError("pipeline_final_stage_missing", "The pipeline final stage is unavailable.", 409)
        current = await self._stage_or_404(cast(UUID, opportunity.pipeline_stage_id))
        self._append_event(
            opportunity,
            current,
            target,
            request.idempotency_key,
            source="manual",
            outcome_reason=request.outcome_reason,
            outcome_note=request.outcome_note,
            outcome_provenance="seller_reported",
            actual_close_date=request.actual_close_date,
            final_amount=request.final_amount if request.final_amount is not None else opportunity.estimated_value,
            final_currency=opportunity.currency,
        )
        old_values = self._workflow_values(opportunity)
        now = datetime.now(UTC)
        opportunity.pipeline_stage_id = target.id
        opportunity.stage = legacy_stage_for(target)
        opportunity.status = outcome
        opportunity.stage_entered_at = now
        opportunity.actual_close_date = request.actual_close_date
        opportunity.outcome_reason = request.outcome_reason or "unknown"
        opportunity.outcome_note = request.outcome_note
        opportunity.outcome_provenance = "seller_reported"
        if request.final_amount is not None:
            if opportunity.currency is None:
                raise PublicAPIError(
                    "opportunity_currency_required",
                    "Set a currency before changing the final value.",
                    422,
                )
            opportunity.estimated_value = request.final_amount
        opportunity.updated_at = now
        self._record_domain_changes(opportunity, old_values, f"closed_{outcome}")
        await self._commit("The opportunity could not be closed.")
        self._log(f"opportunity_closed_{outcome}", opportunity_id=opportunity.id, stage_id=target.id)
        return await self.opportunity_pipeline(opportunity.id)

    async def _ensure_assignment(self, opportunity: Opportunity) -> None:
        if opportunity.pipeline_id is not None and opportunity.pipeline_stage_id is not None:
            return
        pipeline, stages = await ensure_default_pipeline(self.repository.session, self.tenant.organisation_id)
        stage = initial_stage_for(stages, opportunity.stage, opportunity.status)
        now = datetime.now(UTC)
        opportunity.pipeline_id = pipeline.id
        opportunity.pipeline_stage_id = stage.id
        opportunity.stage_tracking_started_at = now
        self.repository.add(
            OpportunityStageEvent(
                organisation_id=self.tenant.organisation_id,
                opportunity_id=opportunity.id,
                to_pipeline_id=pipeline.id,
                to_stage_id=stage.id,
                to_stage_name=stage.name,
                to_stage_type=stage.stage_type,
                changed_by_user_id=None,
                changed_at=now,
                source="migration_baseline",
                is_baseline=True,
            )
        )
        await self.repository.flush()

    def _append_event(
        self,
        opportunity: Opportunity,
        current: SalesPipelineStage,
        target: SalesPipelineStage,
        idempotency_key: str,
        *,
        source: str,
        outcome_reason: str | None = None,
        outcome_note: str | None = None,
        outcome_provenance: str | None = None,
        actual_close_date: date | None = None,
        final_amount: Decimal | None = None,
        final_currency: str | None = None,
    ) -> None:
        self.repository.add(
            OpportunityStageEvent(
                organisation_id=self.tenant.organisation_id,
                opportunity_id=opportunity.id,
                from_pipeline_id=current.pipeline_id,
                to_pipeline_id=target.pipeline_id,
                from_stage_id=current.id,
                to_stage_id=target.id,
                from_stage_name=current.name,
                to_stage_name=target.name,
                from_stage_type=current.stage_type,
                to_stage_type=target.stage_type,
                changed_by_user_id=self.tenant.user_id,
                changed_at=datetime.now(UTC),
                source=source,
                is_baseline=False,
                previous_stage_entered_at=opportunity.stage_entered_at,
                outcome_reason=outcome_reason,
                outcome_note=outcome_note,
                outcome_provenance=outcome_provenance,
                actual_close_date=actual_close_date,
                final_amount=final_amount,
                final_currency=final_currency,
                idempotency_key=idempotency_key,
            )
        )

    def _record_domain_changes(
        self,
        opportunity: Opportunity,
        old_values: dict[str, object | None],
        action: str,
    ) -> None:
        now = datetime.now(UTC)
        new_values = self._workflow_values(opportunity)
        changed_fields: list[str] = ["pipeline_id", "pipeline_stage_id"]
        for field_key, old_value in old_values.items():
            new_value = new_values[field_key]
            if old_value == new_value:
                continue
            changed_fields.append(field_key)
            self.repository.add(
                CRMRecordChange(
                    organisation_id=self.tenant.organisation_id,
                    entity_type="opportunity",
                    entity_id=opportunity.id,
                    field_key=field_key,
                    old_value_json=self._json_value(old_value),
                    new_value_json=self._json_value(new_value),
                    source="manual_user_entry",
                    changed_by_user_id=self.tenant.user_id,
                    changed_at=now,
                )
            )
        self.repository.add(
            OpportunityAuditEvent(
                organisation_id=self.tenant.organisation_id,
                opportunity_id=opportunity.id,
                actor_user_id=self.tenant.user_id,
                action=action,
                changed_fields=changed_fields,
                metadata_json={},
            )
        )

    @staticmethod
    def _workflow_values(opportunity: Opportunity) -> dict[str, object | None]:
        return {
            "stage": opportunity.stage,
            "status": opportunity.status,
            "actual_close_date": opportunity.actual_close_date,
            "outcome_reason": opportunity.outcome_reason,
            "outcome_note": opportunity.outcome_note,
            "outcome_provenance": opportunity.outcome_provenance,
            "estimated_value": opportunity.estimated_value,
        }

    @staticmethod
    def _json_value(value: object | None) -> object | None:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value

    async def _pipeline_response(
        self,
        pipeline: SalesPipeline,
        *,
        include_archived: bool = False,
    ) -> PipelineResponse:
        stages = await self.repository.stages(
            self.tenant.organisation_id,
            pipeline.id,
            include_archived=include_archived,
        )
        counts = await self.repository.stage_counts(self.tenant.organisation_id, pipeline.id)
        return PipelineResponse(
            id=pipeline.id,
            name=pipeline.name,
            is_default=pipeline.is_default,
            active=pipeline.active,
            archived_at=pipeline.archived_at,
            stages=[self._stage_response(stage, counts.get(stage.id, 0)) for stage in stages],
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    @staticmethod
    def _stage_response(stage: SalesPipelineStage, count: int = 0) -> PipelineStageResponse:
        return PipelineStageResponse(
            id=stage.id,
            pipeline_id=stage.pipeline_id,
            key=stage.stage_key,
            name=stage.name,
            position=stage.position,
            stage_type=cast(PipelineStageType, stage.stage_type),
            guidance=stage.guidance,
            active=stage.active,
            archived_at=stage.archived_at,
            current_opportunity_count=count,
        )

    async def _tasks_for(self, opportunity_ids: list[UUID]) -> dict[UUID, list[Task]]:
        if not opportunity_ids:
            return {}
        tasks = list(
            (
                await self.repository.session.scalars(
                    select(Task)
                    .where(
                        Task.organisation_id == self.tenant.organisation_id,
                        Task.opportunity_id.in_(opportunity_ids),
                        Task.status.in_(("open", "in_progress")),
                    )
                    .order_by(Task.due_at.asc().nulls_last(), Task.created_at, Task.id)
                )
            ).all()
        )
        grouped: dict[UUID, list[Task]] = defaultdict(list)
        for task in tasks:
            if task.opportunity_id is not None:
                grouped[task.opportunity_id].append(task)
        return dict(grouped)

    def _card(self, record: PipelineOpportunityRecord, tasks: list[Task]) -> PipelineCardResponse:
        opportunity = record.opportunity
        now = datetime.now(UTC)
        reasons: list[str] = []
        if any(
            task.due_at is not None and self._as_utc(task.due_at) < now and task.priority in ("high", "urgent")
            for task in tasks
        ):
            reasons.append("Overdue high-priority Action")
        if opportunity.expected_close_date is not None and opportunity.expected_close_date < now.date():
            reasons.append("Close date passed")
        if not tasks:
            reasons.append("No next Action")
        return PipelineCardResponse(
            opportunity_id=opportunity.id,
            opportunity_name=opportunity.name,
            company_id=opportunity.company_id,
            company_name=record.company_name,
            pipeline_id=record.pipeline.id,
            pipeline_name=record.pipeline.name,
            stage_id=record.stage.id,
            stage_name=record.stage.name,
            stage_type=cast(PipelineStageType, record.stage.stage_type),
            status=cast(Literal["open", "won", "lost", "on_hold"], opportunity.status),
            estimated_value=opportunity.estimated_value,
            currency=opportunity.currency,
            expected_close_date=opportunity.expected_close_date,
            actual_close_date=opportunity.actual_close_date,
            owner_user_id=opportunity.owner_user_id,
            owner_name=record.owner_name,
            stage_entered_at=opportunity.stage_entered_at,
            stage_tracking_started_at=opportunity.stage_tracking_started_at,
            days_in_stage=self._days_in_stage(opportunity.stage_entered_at),
            next_action=tasks[0].title if tasks else None,
            attention_reasons=reasons[:2],
            outcome_reason=opportunity.outcome_reason,
            outcome_provenance=cast(Literal["seller_reported"] | None, opportunity.outcome_provenance),
        )

    @staticmethod
    def _summary(cards: list[PipelineCardResponse]) -> PipelineSummaryResponse:
        grouped: dict[str, tuple[Decimal, int]] = {}
        for card in cards:
            if card.estimated_value is None or card.currency is None:
                continue
            amount, count = grouped.get(card.currency, (Decimal("0"), 0))
            grouped[card.currency] = (amount + card.estimated_value, count + 1)
        today = datetime.now(UTC).date()
        return PipelineSummaryResponse(
            open_opportunity_count=len(cards),
            needs_attention_count=sum(bool(card.attention_reasons) for card in cards),
            close_dates_this_month_count=sum(
                PipelineService._is_this_month(card.expected_close_date, today) for card in cards
            ),
            unvalued_opportunity_count=sum(card.estimated_value is None for card in cards),
            values=[
                PipelineValueSummary(currency=currency, amount=value[0], opportunity_count=value[1])
                for currency, value in sorted(grouped.items())
            ],
        )

    @staticmethod
    def _event_response(event: OpportunityStageEvent, actor_name: str | None) -> OpportunityStageEventResponse:
        return OpportunityStageEventResponse(
            id=event.id,
            from_pipeline_id=event.from_pipeline_id,
            to_pipeline_id=event.to_pipeline_id,
            from_stage_id=event.from_stage_id,
            to_stage_id=event.to_stage_id,
            from_stage_name=event.from_stage_name,
            to_stage_name=event.to_stage_name,
            from_stage_type=cast(PipelineStageType | None, event.from_stage_type),
            to_stage_type=cast(PipelineStageType, event.to_stage_type),
            changed_by_user_id=event.changed_by_user_id,
            changed_by_name=actor_name,
            changed_at=event.changed_at,
            source=cast(
                Literal["system_initial", "migration_baseline", "manual", "external_crm"],
                event.source,
            ),
            is_baseline=event.is_baseline,
            previous_stage_entered_at=event.previous_stage_entered_at,
            outcome_reason=event.outcome_reason,
            outcome_note=event.outcome_note,
            outcome_provenance=cast(Literal["seller_reported"] | None, event.outcome_provenance),
            actual_close_date=event.actual_close_date,
            final_amount=event.final_amount,
            final_currency=event.final_currency,
        )

    async def _authority(self) -> tuple[bool, bool, str | None]:
        if not self.settings.feature_native_pipeline_enabled:
            return False, False, "Pipeline changes are temporarily unavailable."
        setting = await self.repository.session.scalar(
            select(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == self.tenant.organisation_id)
        )
        connected_hubspot = None
        if setting is None:
            connected_hubspot = await self.repository.session.scalar(
                select(IntegrationConnection.id)
                .where(
                    IntegrationConnection.organisation_id == self.tenant.organisation_id,
                    IntegrationConnection.connector_key == "hubspot",
                    IntegrationConnection.connection_status.in_(("active", "reauthorisation_required")),
                )
                .limit(1)
            )
        if (setting is not None and setting.mode == "external") or connected_hubspot is not None:
            return False, True, "Stages are managed in HubSpot. Use the reviewed CRM update flow."
        return True, False, None

    async def _require_stage_change_authority(self) -> None:
        allowed, external, _ = await self._authority()
        if not allowed:
            if external:
                raise PublicAPIError(
                    "external_stage_authority",
                    "This stage is managed in HubSpot. Use the reviewed CRM update flow.",
                    409,
                )
            raise PublicAPIError("native_pipeline_unavailable", "Pipeline changes are unavailable.", 503)

    async def _require_admin_configuration(self) -> None:
        if self.tenant.role != "admin":
            raise PublicAPIError("admin_required", "An organisation administrator must manage pipelines.", 403)
        if not self.settings.feature_native_pipeline_enabled or not self.settings.feature_native_crm_enabled:
            raise PublicAPIError("native_pipeline_unavailable", "Native pipeline administration is unavailable.", 503)
        await CommercialService(self.repository.session, self.settings).require_module_write(
            self.tenant.organisation_id, "core"
        )
        setting = await self.repository.session.scalar(
            select(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == self.tenant.organisation_id)
        )
        if setting is None or setting.mode != "native":
            raise PublicAPIError(
                "native_crm_required",
                "Select RevenueOS as the CRM before configuring native pipelines.",
                409,
            )

    async def _pipeline_or_404(self, pipeline_id: UUID, *, for_update: bool = False) -> SalesPipeline:
        pipeline = await self.repository.pipeline(
            self.tenant.organisation_id,
            pipeline_id,
            for_update=for_update,
        )
        if pipeline is None:
            raise PublicAPIError("pipeline_not_found", "The pipeline was not found.", 404)
        return pipeline

    async def _stage_or_404(self, stage_id: UUID, *, for_update: bool = False) -> SalesPipelineStage:
        stage = await self.repository.stage(
            self.tenant.organisation_id,
            stage_id,
            for_update=for_update,
        )
        if stage is None:
            raise PublicAPIError("pipeline_stage_not_found", "The pipeline stage was not found.", 404)
        return stage

    async def _opportunity_or_404(self, opportunity_id: UUID, *, for_update: bool = False) -> Opportunity:
        opportunity = await self.repository.opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=for_update,
        )
        if opportunity is None or opportunity.archived_at is not None:
            raise PublicAPIError("opportunity_not_found", "The opportunity was not found.", 404)
        return opportunity

    @staticmethod
    def _check_current_stage(opportunity: Opportunity, expected_stage_id: UUID) -> None:
        if opportunity.pipeline_stage_id != expected_stage_id:
            raise PublicAPIError(
                "stale_pipeline_state",
                "This opportunity changed since you opened the pipeline. Refresh to continue.",
                409,
            )

    @staticmethod
    def _require_unique_stage_name(
        stages: list[SalesPipelineStage],
        name: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        if any(
            stage.id != exclude_id and stage.active and stage.name.casefold() == name.casefold() for stage in stages
        ):
            raise PublicAPIError("pipeline_stage_name_exists", "Choose a different stage name.", 409)

    @staticmethod
    def _renumber(stages: list[SalesPipelineStage]) -> None:
        for position, stage in enumerate(stages):
            stage.position = position
            stage.updated_at = datetime.now(UTC)

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("pipeline_conflict", message, 409) from exc
        except SQLAlchemyError as exc:
            await self.repository.rollback()
            raise PublicAPIError("pipeline_unavailable", message, 503) from exc

    @staticmethod
    def _days_in_stage(value: datetime | None) -> int | None:
        if value is None:
            return None
        return max(0, (datetime.now(UTC) - PipelineService._as_utc(value)).days)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.utcoffset() is None else value.astimezone(UTC)

    @staticmethod
    def _is_this_month(value: date | None, today: date) -> bool:
        return value is not None and value.year == today.year and value.month == today.month

    def _log(self, event: str, **identifiers: UUID) -> None:
        logger.info(
            event,
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                **{key: str(value) for key, value in identifiers.items()},
            },
        )
