from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.daily_repositories import DailyRepository
from revenueos.models import (
    ActionProposal,
    ActionProposalVersion,
    AIArtifact,
    BetaSystemEvent,
    Company,
    Evidence,
    Meeting,
    MethodologyProjection,
    Opportunity,
    Organisation,
    OrganisationMembership,
    RevenueBrainInsight,
    RevenueBrainSnapshot,
    RevenueBrainSourceSnapshot,
)
from revenueos.source_evidence_contracts import OpportunityEvidenceItemResponse


@dataclass(frozen=True)
class AskBrainBundle:
    opportunity_id: UUID
    snapshot: RevenueBrainSnapshot
    meeting: Meeting
    artifacts: dict[str, AIArtifact]


@dataclass(frozen=True)
class AskActionRecord:
    proposal: ActionProposal
    version: ActionProposalVersion


class AskRepository:
    """Bounded tenant-scoped reads for Ask RevenueOS."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.daily = DailyRepository(session)

    async def active_membership(self, organisation_id: UUID, user_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                    OrganisationMembership.status == "active",
                )
            )
            is not None
        )

    async def opportunity(self, organisation_id: UUID, opportunity_id: UUID) -> Opportunity | None:
        return cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            ),
        )

    async def company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                )
            ),
        )

    async def opportunities_for_company(
        self,
        organisation_id: UUID,
        company_id: UUID,
        *,
        limit: int = 20,
    ) -> list[Opportunity]:
        values = await self.session.scalars(
            select(Opportunity)
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.company_id == company_id,
            )
            .order_by(
                case(
                    (Opportunity.status == "open", 0),
                    (Opportunity.status == "on_hold", 1),
                    else_=2,
                ),
                Opportunity.expected_close_date.is_(None),
                Opportunity.expected_close_date.asc(),
                Opportunity.updated_at.desc(),
                Opportunity.id.asc(),
            )
            .limit(limit)
        )
        return list(values.all())

    async def owned_open_opportunities(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Opportunity]:
        values = await self.session.scalars(
            select(Opportunity)
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.owner_user_id == user_id,
                Opportunity.status == "open",
            )
            .order_by(
                Opportunity.expected_close_date.is_(None),
                Opportunity.expected_close_date.asc(),
                Opportunity.updated_at.desc(),
                Opportunity.id.asc(),
            )
            .limit(limit)
        )
        return list(values.all())

    async def latest_methodology(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
    ) -> list[MethodologyProjection]:
        return await self.daily.methodology_projections(organisation_id, opportunity_ids)

    async def latest_brain_insights(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
    ) -> list[RevenueBrainInsight]:
        return await self.daily.revenue_brain_insights(organisation_id, opportunity_ids)

    async def latest_brain_bundles(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
        *,
        limit: int = 20,
    ) -> list[AskBrainBundle]:
        if not opportunity_ids:
            return []
        ranked = (
            select(
                RevenueBrainSnapshot.id.label("snapshot_id"),
                func.row_number()
                .over(
                    partition_by=RevenueBrainSnapshot.opportunity_id,
                    order_by=(
                        Meeting.meeting_date.desc(),
                        RevenueBrainSnapshot.created_at.desc(),
                        RevenueBrainSnapshot.id.desc(),
                    ),
                )
                .label("position"),
            )
            .join(
                Meeting,
                and_(
                    Meeting.organisation_id == RevenueBrainSnapshot.organisation_id,
                    Meeting.id == RevenueBrainSnapshot.meeting_id,
                ),
            )
            .where(
                RevenueBrainSnapshot.organisation_id == organisation_id,
                RevenueBrainSnapshot.opportunity_id.in_(opportunity_ids),
                Meeting.status == "completed",
                Meeting.deleted_at.is_(None),
            )
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(RevenueBrainSnapshot, Meeting)
                .join(ranked, ranked.c.snapshot_id == RevenueBrainSnapshot.id)
                .join(
                    Meeting,
                    and_(
                        Meeting.organisation_id == RevenueBrainSnapshot.organisation_id,
                        Meeting.id == RevenueBrainSnapshot.meeting_id,
                    ),
                )
                .where(ranked.c.position == 1)
                .order_by(Meeting.meeting_date.desc(), RevenueBrainSnapshot.id.desc())
                .limit(limit)
            )
        ).all()
        snapshots = [row[0] for row in rows]
        artifact_ids = {
            artifact_id
            for snapshot in snapshots
            for artifact_id in (
                snapshot.summary_reference,
                snapshot.buying_signals_reference,
                snapshot.objections_reference,
                snapshot.stakeholders_reference,
                snapshot.decisions_reference,
                snapshot.actions_reference,
                snapshot.risks_reference,
                snapshot.questions_reference,
                snapshot.next_best_action_reference,
            )
        }
        artifacts = {
            artifact.id: artifact
            for artifact in (
                await self.session.scalars(
                    select(AIArtifact).where(
                        AIArtifact.organisation_id == organisation_id,
                        AIArtifact.id.in_(artifact_ids),
                        AIArtifact.superseded_at.is_(None),
                    )
                )
            ).all()
        }
        bundles: list[AskBrainBundle] = []
        for snapshot, meeting in rows:
            references = {
                "executive_summary": snapshot.summary_reference,
                "buying_signals": snapshot.buying_signals_reference,
                "objections_competitive_signals": snapshot.objections_reference,
                "stakeholder_intelligence": snapshot.stakeholders_reference,
                "decisions": snapshot.decisions_reference,
                "action_items": snapshot.actions_reference,
                "risks_blockers": snapshot.risks_reference,
                "open_questions": snapshot.questions_reference,
                "next_best_action": snapshot.next_best_action_reference,
            }
            resolved = {key: artifacts[value] for key, value in references.items() if value in artifacts}
            if len(resolved) == len(references) and snapshot.opportunity_id is not None:
                bundles.append(AskBrainBundle(snapshot.opportunity_id, snapshot, meeting, resolved))
        return bundles

    async def accepted_source_snapshots(
        self,
        organisation_id: UUID,
        *,
        opportunity_ids: tuple[UUID, ...] = (),
        company_id: UUID | None = None,
        limit: int = 20,
    ) -> list[RevenueBrainSourceSnapshot]:
        if not opportunity_ids and company_id is None:
            return []
        scope = (
            RevenueBrainSourceSnapshot.opportunity_id.in_(opportunity_ids)
            if opportunity_ids
            else RevenueBrainSourceSnapshot.company_id == company_id
        )
        rows = list(
            (
                await self.session.scalars(
                    select(RevenueBrainSourceSnapshot)
                    .join(
                        Evidence,
                        and_(
                            Evidence.organisation_id == RevenueBrainSourceSnapshot.organisation_id,
                            Evidence.id == RevenueBrainSourceSnapshot.source_evidence_id,
                        ),
                    )
                    .where(
                        RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                        scope,
                        Evidence.lifecycle_status == "available",
                        Evidence.deleted_at.is_(None),
                    )
                    .order_by(
                        RevenueBrainSourceSnapshot.created_at.desc(),
                        RevenueBrainSourceSnapshot.id.desc(),
                    )
                    .limit(limit)
                )
            ).all()
        )
        evidence_ids: set[UUID] = set()
        parsed_ids: dict[UUID, set[UUID]] = {}
        for snapshot in rows:
            try:
                values = {UUID(value) for value in snapshot.source_evidence_ids}
            except (TypeError, ValueError):
                continue
            items = snapshot.content_json.get("items")
            occurred_at = snapshot.content_json.get("occurredAt")
            if not values or not isinstance(items, list) or not items or not isinstance(occurred_at, str):
                continue
            try:
                parsed_items = [
                    OpportunityEvidenceItemResponse.model_validate(
                        {
                            "snapshotId": snapshot.id,
                            "sourceKind": item.get("sourceKind"),
                            "sourceId": item.get("sourceId"),
                            "sourceType": item.get("sourceType"),
                            "sourceLabel": item.get("sourceLabel"),
                            "sourceOrigin": item.get("sourceOrigin"),
                            "occurredAt": occurred_at,
                            "category": item.get("category"),
                            "statement": item.get("statement"),
                            "evidenceId": item.get("evidenceId"),
                            "location": item.get("location"),
                            "originClass": item.get("originClass"),
                            "supportClass": item.get("supportClass"),
                            "conflictState": item.get("conflictState"),
                        }
                    )
                    for item in items
                    if isinstance(item, dict)
                ]
            except (TypeError, ValueError):
                continue
            expected_source_id = (
                snapshot.document_source_id if snapshot.source_kind == "document" else snapshot.email_source_id
            )
            content_ids = {item.evidence_id for item in parsed_items}
            if (
                len(parsed_items) != len(items)
                or len(content_ids) != len(items)
                or not content_ids <= values
                or expected_source_id is None
                or any(
                    item.source_kind != snapshot.source_kind or item.source_id != expected_source_id
                    for item in parsed_items
                )
            ):
                continue
            parsed_ids[snapshot.id] = values
            evidence_ids.update(values)
        if not evidence_ids:
            return []
        available_ids = set(
            (
                await self.session.scalars(
                    select(Evidence.id).where(
                        Evidence.organisation_id == organisation_id,
                        Evidence.id.in_(evidence_ids),
                        Evidence.validation_state == "verified",
                        Evidence.lifecycle_status == "available",
                        Evidence.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        return [snapshot for snapshot in rows if snapshot.id in parsed_ids and parsed_ids[snapshot.id] <= available_ids]

    async def current_actions(
        self,
        organisation_id: UUID,
        opportunity_ids: tuple[UUID, ...],
        *,
        limit: int = 20,
    ) -> list[AskActionRecord]:
        if not opportunity_ids:
            return []
        rows = (
            await self.session.execute(
                select(ActionProposal, ActionProposalVersion)
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .where(
                    ActionProposal.organisation_id == organisation_id,
                    ActionProposal.opportunity_id.in_(opportunity_ids),
                    ActionProposal.status.in_(("proposed", "edited", "approved")),
                )
                .order_by(
                    case(
                        (ActionProposal.priority == "high", 0),
                        (ActionProposal.priority == "medium", 1),
                        else_=2,
                    ),
                    ActionProposalVersion.proposed_due_at.is_(None),
                    ActionProposalVersion.proposed_due_at.asc(),
                    ActionProposal.generated_at.desc(),
                    ActionProposal.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [AskActionRecord(row[0], row[1]) for row in rows]

    async def reserve_quota_and_audit(
        self,
        organisation_id: UUID,
        user_id: UUID,
        event: BetaSystemEvent,
        *,
        user_limit: int,
        organisation_limit: int,
    ) -> Literal["ok", "user_limit", "organisation_limit"]:
        await self.session.scalar(select(Organisation.id).where(Organisation.id == organisation_id).with_for_update())
        start_at = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        organisation_count = int(
            await self.session.scalar(
                select(func.count(BetaSystemEvent.id)).where(
                    BetaSystemEvent.organisation_id == organisation_id,
                    BetaSystemEvent.event_type == "ask_answer_generated",
                    BetaSystemEvent.created_at >= start_at,
                )
            )
            or 0
        )
        if organisation_count >= organisation_limit:
            return "organisation_limit"
        user_count = int(
            await self.session.scalar(
                select(func.count(BetaSystemEvent.id)).where(
                    BetaSystemEvent.organisation_id == organisation_id,
                    BetaSystemEvent.actor_user_id == user_id,
                    BetaSystemEvent.event_type == "ask_answer_generated",
                    BetaSystemEvent.created_at >= start_at,
                )
            )
            or 0
        )
        if user_count >= user_limit:
            return "user_limit"
        self.session.add(event)
        return "ok"

    async def ask_event_exists(
        self,
        organisation_id: UUID,
        user_id: UUID,
        ask_request_id: UUID,
    ) -> bool:
        return (
            await self.session.scalar(
                select(BetaSystemEvent.id).where(
                    BetaSystemEvent.organisation_id == organisation_id,
                    BetaSystemEvent.actor_user_id == user_id,
                    BetaSystemEvent.event_type == "ask_answer_generated",
                    BetaSystemEvent.subject_id == ask_request_id,
                )
            )
            is not None
        )
