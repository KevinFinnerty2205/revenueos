from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import BetaSystemEvent, SalesTarget, SalesTargetRevision
from revenueos.sales_analytics_services import SalesAnalyticsService, SalesMetricService
from revenueos.sales_target_contracts import (
    SalesTargetArchiveRequest,
    SalesTargetCreateRequest,
    SalesTargetListResponse,
    SalesTargetMetadataResponse,
    SalesTargetMetricPolicyResponse,
    SalesTargetOwnerResponse,
    SalesTargetPipelineResponse,
    SalesTargetProgressResponse,
    SalesTargetResponse,
    SalesTargetRevisionCreateRequest,
    SalesTargetRevisionResponse,
    TargetListView,
    TargetPeriodType,
    TargetStatus,
)
from revenueos.sales_target_policy import SALES_TARGET_METRIC_POLICIES, SALES_TARGET_METRIC_POLICY
from revenueos.sales_target_repositories import SalesTargetRepository
from revenueos.tenant import TenantContext

MAXIMUM_VISIBLE_TARGETS = 200
MAXIMUM_PERSONAL_CURRENT_TARGETS = 10
MAXIMUM_ORGANISATION_CURRENT_TARGETS = 20
MAXIMUM_GOAL = Decimal("1000000000000000")
OPPORTUNITY_METRICS = frozenset(("won_value", "opportunities_closed_won_count", "opportunities_created_count"))
ACTIVITY_METRICS = frozenset(("meetings_completed_count", "phone_calls_completed_count"))


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SalesTargetService:
    """Human-defined goals whose live actuals come only from SalesMetricService."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = SalesTargetRepository(session)
        self.analytics = SalesAnalyticsService(session, tenant, settings)
        self.metrics = SalesMetricService(self.analytics)

    def require_enabled(self) -> None:
        if not self.settings.feature_sales_targets_enabled or not self.settings.feature_sales_analytics_enabled:
            raise PublicAPIError("feature_unavailable", "Sales Targets are not enabled in this environment.", 404)

    async def metadata(self) -> SalesTargetMetadataResponse:
        self.require_enabled()
        timezone = await self._organisation_timezone()
        members = await self.repository.members(self.tenant.organisation_id)
        pipelines = await self.repository.pipelines(self.tenant.organisation_id)
        return SalesTargetMetadataResponse(
            current_user_id=self.tenant.user_id,
            current_user_role=self.tenant.role,
            organisation_timezone=timezone.key,
            metrics=[self._metric_policy_response(policy.metric_id) for policy in SALES_TARGET_METRIC_POLICIES],
            owners=[
                SalesTargetOwnerResponse(user_id=member.user_id, display_name=member.display_name)
                for member in members
                if member.active
            ],
            pipelines=[
                SalesTargetPipelineResponse(id=pipeline.id, name=pipeline.name, active=pipeline.active)
                for pipeline in pipelines
            ],
            can_assign_personal_targets=self.tenant.can_manage(),
            can_create_organisation_targets=self.tenant.can_manage(),
        )

    async def list_targets(
        self,
        view: TargetListView = "current",
        *,
        now: datetime | None = None,
    ) -> SalesTargetListResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        targets = await self.repository.visible_targets(
            self.tenant.organisation_id,
            self.tenant.user_id,
            is_admin=self.tenant.can_manage(),
            limit=MAXIMUM_VISIBLE_TARGETS,
        )
        filtered = [target for target in targets if self._in_view(target, view, generated_at)]
        latest = await self.repository.latest_revisions(
            self.tenant.organisation_id,
            {target.id for target in filtered},
        )
        pipelines = {
            pipeline.id: pipeline.name for pipeline in await self.repository.pipelines(self.tenant.organisation_id)
        }
        user_ids = {
            user_id
            for target in filtered
            for user_id in (target.owner_user_id, target.created_by_user_id)
            if user_id is not None
        }
        user_ids.update(revision.created_by_user_id for revision in latest.values())
        names = await self.repository.user_names(self.tenant.organisation_id, user_ids)
        items = [
            await self._target_response(
                target,
                latest[target.id],
                revisions=[latest[target.id]],
                names=names,
                pipeline_name=pipelines.get(target.pipeline_id) if target.pipeline_id is not None else None,
                now=generated_at,
            )
            for target in filtered
            if target.id in latest
        ]
        return SalesTargetListResponse(
            items=items,
            can_assign_personal_targets=self.tenant.can_manage(),
            can_create_organisation_targets=self.tenant.can_manage(),
        )

    async def matching_forecast_targets(
        self,
        *,
        period_start: date,
        period_end: date,
        currency: str,
        pipeline_id: UUID | None,
        owner_user_id: UUID | None,
        organisation_scope: bool,
    ) -> list[tuple[SalesTarget, SalesTargetRevision]]:
        """Return matching won-value goals without recalculating unrelated target actuals."""

        self.require_enabled()
        targets = await self.repository.visible_targets(
            self.tenant.organisation_id,
            self.tenant.user_id,
            is_admin=self.tenant.can_manage(),
            limit=MAXIMUM_VISIBLE_TARGETS,
        )
        matched = [
            target
            for target in targets
            if target.archived_at is None
            and target.metric_id == "won_value"
            and target.metric_definition_version == "1"
            and target.period_start == period_start
            and target.period_end == period_end
            and target.currency == currency
            and target.pipeline_id == pipeline_id
            and (
                target.scope == "organisation"
                if organisation_scope
                else target.scope == "personal" and target.owner_user_id == owner_user_id
            )
        ]
        latest = await self.repository.latest_revisions(
            self.tenant.organisation_id,
            {target.id for target in matched},
        )
        return [(target, latest[target.id]) for target in matched if target.id in latest]

    async def get_target(self, target_id: UUID, *, now: datetime | None = None) -> SalesTargetResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        target = await self._visible_target(target_id)
        revisions = await self.repository.revisions(self.tenant.organisation_id, target.id)
        if not revisions:
            raise PublicAPIError("target_unavailable", "The target could not be loaded.", 409)
        names = await self.repository.user_names(
            self.tenant.organisation_id,
            {
                target.created_by_user_id,
                *(revision.created_by_user_id for revision in revisions),
                *((target.owner_user_id,) if target.owner_user_id is not None else ()),
            },
        )
        pipeline_name: str | None = None
        if target.pipeline_id is not None:
            pipeline = await self.repository.pipeline(self.tenant.organisation_id, target.pipeline_id)
            pipeline_name = pipeline.name if pipeline is not None else "Unavailable pipeline"
        return await self._target_response(
            target,
            revisions[0],
            revisions=revisions,
            names=names,
            pipeline_name=pipeline_name,
            now=generated_at,
        )

    async def create_target(
        self,
        request: SalesTargetCreateRequest,
        *,
        now: datetime | None = None,
    ) -> SalesTargetResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        policy = SALES_TARGET_METRIC_POLICY.get(request.metric_id)
        if policy is None:
            raise PublicAPIError("metric_not_targetable", "Choose a supported target metric.", 422)
        definition = policy.definition
        if request.metric_definition_version != definition.definition_version:
            raise PublicAPIError("metric_version_not_found", "The selected metric definition is unavailable.", 422)
        if request.scope not in policy.allowed_scopes:
            raise PublicAPIError("target_scope_not_supported", "The selected metric does not support that scope.", 422)
        owner_user_id = await self._creation_owner(request)
        currency = request.currency if policy.requires_currency else None
        if policy.requires_currency and currency is None:
            raise PublicAPIError("currency_required", "Choose one ISO currency for this target.", 422)
        if not policy.requires_currency and request.currency is not None:
            raise PublicAPIError("currency_not_supported", "This count target does not use a currency.", 422)
        goal_value = self._goal_value(request.goal_value, unit=definition.unit)
        timezone = await self._organisation_timezone()
        period_start, period_end = self._period(request.period_type, request.period_anchor)
        local_today = generated_at.astimezone(timezone).date()
        if period_end < local_today:
            raise PublicAPIError("past_target_not_allowed", "Choose the current period or a future period.", 422)
        if period_start > local_today + timedelta(days=366 * 5):
            raise PublicAPIError("target_period_too_far", "Choose a period within the next five years.", 422)
        pipeline_name: str | None = None
        if request.pipeline_id is not None:
            if definition.id not in OPPORTUNITY_METRICS:
                raise PublicAPIError(
                    "pipeline_not_supported",
                    "Pipeline selection is available only for Opportunity targets.",
                    422,
                )
            pipeline = await self.repository.pipeline(self.tenant.organisation_id, request.pipeline_id)
            if pipeline is None:
                raise PublicAPIError("pipeline_not_found", "The selected pipeline was not found.", 404)
            if not pipeline.active:
                raise PublicAPIError("pipeline_archived", "Choose an active pipeline for a new target.", 409)
            pipeline_name = pipeline.name
        duplicate = await self.repository.duplicate_target(
            self.tenant.organisation_id,
            metric_id=definition.id,
            metric_definition_version=definition.definition_version,
            scope=request.scope,
            origin=request.origin,
            owner_user_id=owner_user_id,
            pipeline_id=request.pipeline_id,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
        )
        if duplicate is not None:
            raise PublicAPIError(
                "target_conflict",
                f"A {definition.label} target already exists for {self._period_label(request.period_type, period_start)}.",
                409,
            )
        count = await self.repository.current_target_count(
            self.tenant.organisation_id,
            scope=request.scope,
            owner_user_id=owner_user_id,
            today=local_today,
        )
        maximum = (
            MAXIMUM_PERSONAL_CURRENT_TARGETS if request.scope == "personal" else MAXIMUM_ORGANISATION_CURRENT_TARGETS
        )
        if count >= maximum:
            raise PublicAPIError(
                "target_limit", "Archive an existing current or future target before adding another.", 429
            )
        target = SalesTarget(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            metric_id=definition.id,
            metric_definition_version=definition.definition_version,
            scope=request.scope,
            origin=request.origin,
            owner_user_id=owner_user_id,
            pipeline_id=request.pipeline_id,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            timezone=timezone.key,
            currency=currency,
            created_by_user_id=self.tenant.user_id,
        )
        revision = SalesTargetRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            target_id=target.id,
            revision_number=1,
            goal_value=goal_value,
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(target)
        self.repository.add(revision)
        self._audit("sales_target_created", target)
        await self._commit("The target could not be created.", conflict_message="That target already exists.")
        names = await self.repository.user_names(
            self.tenant.organisation_id,
            {self.tenant.user_id, *((owner_user_id,) if owner_user_id is not None else ())},
        )
        return await self._target_response(
            target,
            revision,
            revisions=[revision],
            names=names,
            pipeline_name=pipeline_name,
            now=generated_at,
        )

    async def revise_target(
        self,
        target_id: UUID,
        request: SalesTargetRevisionCreateRequest,
        *,
        now: datetime | None = None,
    ) -> SalesTargetResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        target = await self.repository.visible_target(
            self.tenant.organisation_id,
            self.tenant.user_id,
            target_id,
            is_admin=self.tenant.can_manage(),
            for_update=True,
        )
        if target is None:
            raise PublicAPIError("target_not_found", "The target was not found.", 404)
        self._require_target_manager(target)
        if target.archived_at is not None:
            raise PublicAPIError("target_archived", "An archived target cannot be changed.", 409)
        local_today = generated_at.astimezone(self._target_timezone(target)).date()
        if target.period_end < local_today:
            raise PublicAPIError("past_target_locked", "Past target periods are locked.", 409)
        latest = (await self.repository.latest_revisions(self.tenant.organisation_id, {target.id})).get(target.id)
        if latest is None:
            raise PublicAPIError("target_unavailable", "The target could not be loaded.", 409)
        if request.expected_revision_number != latest.revision_number:
            raise PublicAPIError("target_revision_conflict", "This target changed since you opened it.", 409)
        definition = SALES_TARGET_METRIC_POLICY[target.metric_id].definition
        goal_value = self._goal_value(request.goal_value, unit=definition.unit)
        revision = SalesTargetRevision(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            target_id=target.id,
            revision_number=latest.revision_number + 1,
            goal_value=goal_value,
            created_by_user_id=self.tenant.user_id,
        )
        self.repository.add(revision)
        self._audit("sales_target_revised", target, revision_number=revision.revision_number)
        await self._commit(
            "The target could not be changed.", conflict_message="This target changed since you opened it."
        )
        return await self.get_target(target.id, now=generated_at)

    async def archive_target(
        self,
        target_id: UUID,
        _: SalesTargetArchiveRequest,
        *,
        now: datetime | None = None,
    ) -> SalesTargetResponse:
        self.require_enabled()
        generated_at = _utc(now or datetime.now(UTC))
        target = await self.repository.visible_target(
            self.tenant.organisation_id,
            self.tenant.user_id,
            target_id,
            is_admin=self.tenant.can_manage(),
            for_update=True,
        )
        if target is None:
            raise PublicAPIError("target_not_found", "The target was not found.", 404)
        self._require_target_manager(target)
        if target.archived_at is not None:
            return await self.get_target(target.id, now=generated_at)
        local_today = generated_at.astimezone(self._target_timezone(target)).date()
        if target.period_end < local_today:
            raise PublicAPIError(
                "past_target_locked", "Past target periods remain in history and cannot be archived.", 409
            )
        target.archived_at = generated_at
        self._audit("sales_target_archived", target)
        await self._commit("The target could not be archived.")
        return await self.get_target(target.id, now=generated_at)

    async def _creation_owner(self, request: SalesTargetCreateRequest) -> UUID | None:
        if request.origin == "self_set":
            if request.scope != "personal":
                raise PublicAPIError("invalid_target_origin", "A personal goal must be for one person.", 422)
            if request.owner_user_id is not None and request.owner_user_id != self.tenant.user_id:
                raise PublicAPIError("forbidden", "You cannot set another person's personal goal.", 403)
            owner_user_id: UUID | None = self.tenant.user_id
        else:
            if not self.tenant.can_manage():
                raise PublicAPIError("forbidden", "Only administrators can assign targets.", 403)
            if request.scope == "organisation":
                if request.owner_user_id is not None:
                    raise PublicAPIError("invalid_target_owner", "Organisation targets do not have one owner.", 422)
                owner_user_id = None
            else:
                if request.owner_user_id is None:
                    raise PublicAPIError("target_owner_required", "Choose an active organisation member.", 422)
                owner_user_id = request.owner_user_id
        if owner_user_id is not None:
            owner = await self.repository.active_member(self.tenant.organisation_id, owner_user_id)
            if owner is None:
                raise PublicAPIError("target_owner_not_found", "The selected active member was not found.", 404)
        return owner_user_id

    def _require_target_manager(self, target: SalesTarget) -> None:
        if target.origin == "self_set":
            if target.owner_user_id != self.tenant.user_id:
                raise PublicAPIError("forbidden", "Only the owner can change this personal goal.", 403)
            return
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Only administrators can change an assigned target.", 403)

    async def _visible_target(self, target_id: UUID) -> SalesTarget:
        target = await self.repository.visible_target(
            self.tenant.organisation_id,
            self.tenant.user_id,
            target_id,
            is_admin=self.tenant.can_manage(),
        )
        if target is None:
            raise PublicAPIError("target_not_found", "The target was not found.", 404)
        return target

    async def _organisation_timezone(self) -> ZoneInfo:
        timezone_name = await self.repository.organisation_timezone(self.tenant.organisation_id)
        if timezone_name is None:
            raise PublicAPIError("target_timezone_unavailable", "The organisation timezone is unavailable.", 409)
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError(
                "target_timezone_unavailable",
                "The organisation timezone must be configured before setting a target.",
                409,
            ) from exc

    @staticmethod
    def _target_timezone(target: SalesTarget) -> ZoneInfo:
        try:
            return ZoneInfo(target.timezone)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError("target_timezone_unavailable", "The target timezone is unavailable.", 409) from exc

    @staticmethod
    def _period(period_type: TargetPeriodType, anchor: date) -> tuple[date, date]:
        if period_type == "month":
            start = date(anchor.year, anchor.month, 1)
            end = date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])
        elif period_type == "quarter":
            start_month = ((anchor.month - 1) // 3) * 3 + 1
            start = date(anchor.year, start_month, 1)
            end_month = start_month + 2
            end = date(anchor.year, end_month, calendar.monthrange(anchor.year, end_month)[1])
        else:
            start = date(anchor.year, 1, 1)
            end = date(anchor.year, 12, 31)
        return start, end

    @staticmethod
    def _period_label(period_type: str, period_start: date) -> str:
        if period_type == "month":
            return period_start.strftime("%B %Y")
        if period_type == "quarter":
            return f"Q{((period_start.month - 1) // 3) + 1} {period_start.year}"
        return str(period_start.year)

    @staticmethod
    def _goal_value(value: str, *, unit: str) -> Decimal:
        goal = Decimal(value)
        if goal <= 0 or goal > MAXIMUM_GOAL:
            raise PublicAPIError(
                "invalid_target_value", "Enter a target greater than zero within the supported limit.", 422
            )
        if unit == "count" and goal != goal.to_integral_value():
            raise PublicAPIError("invalid_target_value", "Count targets must be whole numbers.", 422)
        return goal.quantize(Decimal("1") if unit == "count" else Decimal("0.01"))

    @staticmethod
    def _status(target: SalesTarget, now: datetime) -> TargetStatus:
        if target.archived_at is not None:
            return "archived"
        local_today = now.astimezone(SalesTargetService._target_timezone(target)).date()
        if local_today < target.period_start:
            return "upcoming"
        if local_today <= target.period_end:
            return "active"
        return "past"

    @classmethod
    def _in_view(cls, target: SalesTarget, view: TargetListView, now: datetime) -> bool:
        status = cls._status(target, now)
        return view == "all" or view == "current" and status in {"active", "upcoming"} or view == status

    @staticmethod
    def _metric_policy_response(metric_id: str) -> SalesTargetMetricPolicyResponse:
        policy = SALES_TARGET_METRIC_POLICY[metric_id]
        definition = policy.definition
        return SalesTargetMetricPolicyResponse(
            metric_id=definition.id,
            definition_version=definition.definition_version,
            label=definition.label,
            description=definition.description,
            unit=definition.unit,
            category=policy.category,
            allowed_scopes=list(policy.allowed_scopes),
            requires_currency=policy.requires_currency,
            display_order=policy.display_order,
            date_semantics=definition.date_semantics,
            exclusions=list(definition.exclusions),
        )

    async def _progress(
        self,
        target: SalesTarget,
        revision: SalesTargetRevision,
        *,
        now: datetime,
    ) -> SalesTargetProgressResponse:
        status = self._status(target, now)
        disclosures = [
            "Actual performance is calculated live from the same canonical Sales Analytics metric used in Insights.",
            "This is an operational sales goal, not a forecast or compensation record.",
        ]
        if target.metric_id in OPPORTUNITY_METRICS and target.scope == "personal":
            disclosures.append(
                "Personal Opportunity targets use the Opportunity's current owner; reassignment can change historical progress."
            )
        if target.metric_id in ACTIVITY_METRICS and target.scope == "personal":
            disclosures.append("Personal activity targets use the Interaction creator.")
        if target.metric_id == "won_value":
            disclosures.append(
                f"Only valued Won Opportunities in {target.currency} are included; other currencies are not converted."
            )
        created_local_date = _utc(target.created_at).astimezone(self._target_timezone(target)).date()
        if created_local_date > target.period_start:
            disclosures.append(
                "Progress includes the full selected period, including records before this target was created."
            )
        if status == "upcoming":
            return SalesTargetProgressResponse(
                state="upcoming",
                target_value=revision.goal_value,
                target_reached=None,
                calculated_through=None,
                generated_at=now,
                disclosures=disclosures,
            )
        policy = SALES_TARGET_METRIC_POLICY.get(target.metric_id)
        if policy is None or policy.definition.definition_version != target.metric_definition_version:
            return SalesTargetProgressResponse(
                state="unavailable",
                target_value=revision.goal_value,
                target_reached=None,
                calculated_through=None,
                generated_at=now,
                disclosures=[*disclosures, "The stored canonical metric version is not available in this release."],
            )
        timezone = self._target_timezone(target)
        local_today = now.astimezone(timezone).date()
        calculated_through = min(target.period_end, local_today)
        try:
            filters = await self.analytics.filters(
                start_date=target.period_start,
                end_date=calculated_through,
                timezone_name=target.timezone,
                pipeline_id=target.pipeline_id,
                owner_user_id=target.owner_user_id if target.scope == "personal" else None,
                now=now,
            )
            observation = await self.metrics.observe(
                target.metric_id,
                filters,
                currency=target.currency,
                now=now,
            )
        except PublicAPIError:
            return SalesTargetProgressResponse(
                state="unavailable",
                target_value=revision.goal_value,
                target_reached=None,
                calculated_through=calculated_through,
                generated_at=now,
                disclosures=[*disclosures, "Canonical metric progress is temporarily unavailable."],
            )
        if observation.value is None:
            return SalesTargetProgressResponse(
                state="unavailable",
                target_value=revision.goal_value,
                target_reached=None,
                calculated_through=calculated_through,
                generated_at=now,
                disclosures=[*disclosures, "The canonical metric does not have enough data for this period."],
            )
        actual = Decimal(str(observation.value))
        remaining = max(revision.goal_value - actual, Decimal(0))
        above = max(actual - revision.goal_value, Decimal(0))
        percentage = (actual * Decimal(100) / revision.goal_value).quantize(
            Decimal("0.1"),
            rounding=ROUND_HALF_UP,
        )
        return SalesTargetProgressResponse(
            state="available",
            actual_value=actual,
            target_value=revision.goal_value,
            remaining_value=remaining,
            above_target_value=above,
            percentage_complete=percentage,
            target_reached=actual >= revision.goal_value,
            calculated_through=calculated_through,
            generated_at=now,
            disclosures=disclosures,
        )

    async def _target_response(
        self,
        target: SalesTarget,
        latest: SalesTargetRevision,
        *,
        revisions: list[SalesTargetRevision],
        names: dict[UUID, str],
        pipeline_name: str | None,
        now: datetime,
    ) -> SalesTargetResponse:
        status = self._status(target, now)
        can_manage = self._can_manage(target)
        can_change = can_manage and status in {"active", "upcoming"}
        revision_responses = [
            SalesTargetRevisionResponse(
                id=revision.id,
                revision_number=revision.revision_number,
                goal_value=revision.goal_value,
                created_by_user_id=revision.created_by_user_id,
                created_by_display_name=names.get(revision.created_by_user_id, "Former member"),
                created_at=_utc(revision.created_at),
            )
            for revision in revisions
        ]
        return SalesTargetResponse(
            id=target.id,
            metric=self._metric_policy_response(target.metric_id),
            scope=cast(Literal["personal", "organisation"], target.scope),
            origin=cast(Literal["self_set", "admin_assigned"], target.origin),
            owner_user_id=target.owner_user_id,
            owner_display_name=names.get(target.owner_user_id) if target.owner_user_id is not None else None,
            pipeline_id=target.pipeline_id,
            pipeline_name=pipeline_name,
            period_type=cast(TargetPeriodType, target.period_type),
            period_start=target.period_start,
            period_end=target.period_end,
            period_label=self._period_label(target.period_type, target.period_start),
            timezone=target.timezone,
            currency=target.currency,
            status=status,
            latest_revision=next(
                response for response in revision_responses if response.revision_number == latest.revision_number
            ),
            revisions=revision_responses,
            progress=await self._progress(target, latest, now=now),
            created_by_user_id=target.created_by_user_id,
            created_by_display_name=names.get(target.created_by_user_id, "Former member"),
            archived_at=_utc(target.archived_at) if target.archived_at is not None else None,
            created_at=_utc(target.created_at),
            updated_at=_utc(target.updated_at),
            can_revise=can_change,
            can_archive=can_change,
        )

    def _can_manage(self, target: SalesTarget) -> bool:
        if target.origin == "self_set":
            return target.owner_user_id == self.tenant.user_id
        return self.tenant.can_manage()

    def _audit(self, event_type: str, target: SalesTarget, *, revision_number: int | None = None) -> None:
        metadata: dict[str, object] = {
            "metric_id": target.metric_id,
            "metric_definition_version": target.metric_definition_version,
            "scope": target.scope,
            "origin": target.origin,
            "period_type": target.period_type,
        }
        if revision_number is not None:
            metadata["revision_number"] = revision_number
        self.repository.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=target.id,
                metadata_json=metadata,
            )
        )

    async def _commit(
        self,
        message: str,
        *,
        conflict_message: str | None = None,
    ) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("target_conflict", conflict_message or message, 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failed", message, 503) from exc
