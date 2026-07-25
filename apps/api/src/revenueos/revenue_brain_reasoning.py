from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping
from typing import Literal, NamedTuple, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    BUYING_SIGNALS_SCHEMA_VERSION,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    NEXT_BEST_ACTION_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
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
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, MeetingAuditEvent, RevenueBrainInsight
from revenueos.revenue_brain import transcript_version_identifier
from revenueos.revenue_brain_comparison import (
    REVENUE_BRAIN_REASONING_VERSION,
    REVENUE_BRAIN_RECENT_SNAPSHOT_LIMIT,
    RevenueBrainArtifactPayloads,
    RevenueBrainComparisonEngine,
    RevenueBrainSnapshotBundle,
)
from revenueos.revenue_brain_reasoning_contracts import (
    REVENUE_BRAIN_RECENT_INSIGHT_LIMIT,
    RevenueBrainInsightContent,
    RevenueBrainInsightResponse,
    RevenueBrainReasoningRequestResponse,
    RevenueBrainReasoningResponse,
    RevenueBrainScope,
    RevenueBrainSourceCapability,
)
from revenueos.revenue_brain_reasoning_repositories import (
    RevenueBrainReasoningRepository,
    RevenueBrainSnapshotCandidate,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.revenue_brain_reasoning")
RevenueBrainComparisonMode = Literal["latest_change", "recent_history"]


class ArtifactReferenceSpec(NamedTuple):
    source: RevenueBrainSourceCapability
    reference_attribute: str
    artifact_type: str
    schema_version: int
    validation_model: type[BaseModel]


ARTIFACT_REFERENCE_SPECS = (
    ArtifactReferenceSpec(
        "executive_summary",
        "summary_reference",
        "executive_summary",
        EXECUTIVE_SUMMARY_SCHEMA_VERSION,
        ExecutiveSummaryArtifactContent,
    ),
    ArtifactReferenceSpec(
        "buying_signals",
        "buying_signals_reference",
        "buying_signals",
        BUYING_SIGNALS_SCHEMA_VERSION,
        BuyingSignalsArtifactContent,
    ),
    ArtifactReferenceSpec(
        "objections_competitive_signals",
        "objections_reference",
        "objections_competitive_signals",
        OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
        ObjectionsCompetitiveSignalsArtifactContent,
    ),
    ArtifactReferenceSpec(
        "stakeholder_intelligence",
        "stakeholders_reference",
        "stakeholder_intelligence",
        STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
        StakeholderIntelligenceArtifactContent,
    ),
    ArtifactReferenceSpec(
        "decisions",
        "decisions_reference",
        "decisions",
        DECISIONS_SCHEMA_VERSION,
        DecisionsArtifactContent,
    ),
    ArtifactReferenceSpec(
        "action_items",
        "actions_reference",
        "action_items",
        ACTION_ITEMS_SCHEMA_VERSION,
        ActionItemsArtifactContent,
    ),
    ArtifactReferenceSpec(
        "risks_blockers",
        "risks_reference",
        "risks_blockers",
        RISKS_BLOCKERS_SCHEMA_VERSION,
        RisksBlockersArtifactContent,
    ),
    ArtifactReferenceSpec(
        "open_questions",
        "questions_reference",
        "open_questions",
        OPEN_QUESTIONS_SCHEMA_VERSION,
        OpenQuestionsArtifactContent,
    ),
    ArtifactReferenceSpec(
        "next_best_action",
        "next_best_action_reference",
        "next_best_action",
        NEXT_BEST_ACTION_SCHEMA_VERSION,
        NextBestActionArtifactContent,
    ),
)


class RevenueBrainReasoningService:
    """On-demand deterministic longitudinal reasoning over immutable snapshots."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        *,
        repository: RevenueBrainReasoningRepository | None = None,
        engine: RevenueBrainComparisonEngine | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repository = repository or RevenueBrainReasoningRepository(session)
        self.engine = engine or RevenueBrainComparisonEngine()

    async def generate_for_account(
        self,
        account_id: UUID,
        *,
        mode: RevenueBrainComparisonMode,
    ) -> RevenueBrainReasoningRequestResponse:
        if not await self.repository.company_exists(
            self.tenant.organisation_id,
            account_id,
        ):
            raise PublicAPIError(
                "not_found",
                "The requested account was not found.",
                404,
            )
        return await self._generate(
            scope="account",
            company_id=account_id,
            opportunity_id=None,
            scope_target_id=account_id,
            mode=mode,
        )

    async def generate_for_opportunity(
        self,
        opportunity_id: UUID,
        *,
        mode: RevenueBrainComparisonMode,
    ) -> RevenueBrainReasoningRequestResponse:
        company_id = await self.repository.opportunity_company_id(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if company_id is None:
            raise PublicAPIError(
                "opportunity_not_found",
                "The requested opportunity was not found or is not associated with an account.",
                404,
            )
        return await self._generate(
            scope="opportunity",
            company_id=company_id,
            opportunity_id=opportunity_id,
            scope_target_id=opportunity_id,
            mode=mode,
        )

    async def read_for_account(
        self,
        account_id: UUID,
    ) -> RevenueBrainReasoningResponse:
        if not await self.repository.company_exists(
            self.tenant.organisation_id,
            account_id,
        ):
            raise PublicAPIError(
                "not_found",
                "The requested account was not found.",
                404,
            )
        return await self._read(
            scope="account",
            company_id=account_id,
            opportunity_id=None,
            scope_target_id=account_id,
        )

    async def read_for_opportunity(
        self,
        opportunity_id: UUID,
    ) -> RevenueBrainReasoningResponse:
        company_id = await self.repository.opportunity_company_id(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if company_id is None:
            raise PublicAPIError(
                "opportunity_not_found",
                "The requested opportunity was not found or is not associated with an account.",
                404,
            )
        return await self._read(
            scope="opportunity",
            company_id=company_id,
            opportunity_id=opportunity_id,
            scope_target_id=opportunity_id,
        )

    async def _generate(
        self,
        *,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
        scope_target_id: UUID,
        mode: RevenueBrainComparisonMode,
    ) -> RevenueBrainReasoningRequestResponse:
        bundles = await self._eligible_bundles(
            scope=scope,
            company_id=company_id,
            opportunity_id=opportunity_id,
        )
        logger.info(
            "revenue_brain_reasoning_requested",
            extra=self._telemetry(
                scope,
                company_id,
                opportunity_id,
                eligible_snapshot_count=len(bundles),
                mode=mode,
            ),
        )
        if len(bundles) < 2:
            logger.info(
                "revenue_brain_reasoning_insufficient_history",
                extra=self._telemetry(
                    scope,
                    company_id,
                    opportunity_id,
                    eligible_snapshot_count=len(bundles),
                ),
            )
            return RevenueBrainReasoningRequestResponse(
                state="insufficient_history",
                message=(
                    "Revenue Brain needs at least two completed meeting snapshots before it can identify changes."
                ),
                latest=None,
                history=[],
                created=False,
            )

        pairs = [(bundles[1], bundles[0])]
        if mode == "recent_history":
            pairs = [(bundles[index + 1], bundles[index]) for index in range(len(bundles) - 1)]
            pairs.reverse()

        created = False
        for before, after in pairs:
            pair_created = await self._create_or_reuse(
                scope=scope,
                company_id=company_id,
                opportunity_id=opportunity_id,
                scope_target_id=scope_target_id,
                before=before,
                after=after,
            )
            created = created or pair_created

        response = await self._read(
            scope=scope,
            company_id=company_id,
            opportunity_id=opportunity_id,
            scope_target_id=scope_target_id,
        )
        return RevenueBrainReasoningRequestResponse(
            **response.model_dump(),
            created=created,
        )

    async def _read(
        self,
        *,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
        scope_target_id: UUID,
    ) -> RevenueBrainReasoningResponse:
        records = await self.repository.list_insights(
            self.tenant.organisation_id,
            scope=scope,
            scope_target_id=scope_target_id,
            reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
            limit=REVENUE_BRAIN_RECENT_INSIGHT_LIMIT,
        )
        history = [
            response
            for record in records
            if (response := self._insight_response(record, scope, company_id, opportunity_id)) is not None
        ]
        bundles = await self._eligible_bundles(
            scope=scope,
            company_id=company_id,
            opportunity_id=opportunity_id,
        )
        if len(bundles) >= 2:
            latest = next(
                (
                    insight
                    for insight in history
                    if insight.content.from_snapshot_id == bundles[1].snapshot.id
                    and insight.content.to_snapshot_id == bundles[0].snapshot.id
                ),
                None,
            )
        else:
            latest = None
        if latest is not None:
            logger.info(
                "revenue_brain_reasoning_viewed",
                extra=self._telemetry(
                    scope,
                    company_id,
                    opportunity_id,
                    insight_count=len(history),
                ),
            )
            return RevenueBrainReasoningResponse(
                state="completed",
                message="Longitudinal reasoning is available.",
                latest=latest,
                history=history,
            )

        if len(bundles) < 2:
            return RevenueBrainReasoningResponse(
                state="insufficient_history",
                message=(
                    "Revenue Brain needs at least two completed meeting snapshots before it can identify changes."
                ),
                latest=None,
                history=history,
            )
        return RevenueBrainReasoningResponse(
            state="not_generated",
            message="Longitudinal reasoning has not been generated for the latest snapshots.",
            latest=None,
            history=history,
        )

    async def _create_or_reuse(
        self,
        *,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
        scope_target_id: UUID,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> bool:
        existing = await self.repository.get_insight(
            self.tenant.organisation_id,
            scope=scope,
            scope_target_id=scope_target_id,
            from_snapshot_id=before.snapshot.id,
            to_snapshot_id=after.snapshot.id,
            reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
        )
        self.repository.add(
            self._audit(
                "revenue_brain_reasoning_requested",
                scope,
                after,
                insight_id=existing.id if existing is not None else None,
            )
        )
        if existing is not None:
            await self.repository.commit()
            logger.info(
                "revenue_brain_reasoning_reused",
                extra=self._telemetry(scope, company_id, opportunity_id),
            )
            return False

        logger.info(
            "revenue_brain_comparison_started",
            extra=self._telemetry(scope, company_id, opportunity_id),
        )
        content = self.engine.compare(scope, before, after)
        self._validate_evidence(content, before, after)
        insight = RevenueBrainInsight(
            organisation_id=self.tenant.organisation_id,
            company_id=company_id,
            opportunity_id=opportunity_id,
            scope=scope,
            scope_target_id=scope_target_id,
            from_snapshot_id=before.snapshot.id,
            to_snapshot_id=after.snapshot.id,
            reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
            status="completed",
            content_json=content.as_json(),
        )
        try:
            async with self.session.begin_nested():
                self.repository.add(insight)
                await self.repository.flush()
                self.repository.add(
                    self._audit(
                        "revenue_brain_insight_created",
                        scope,
                        after,
                        insight_id=insight.id,
                        change_count=len(content.changes),
                    )
                )
                await self.repository.flush()
        except IntegrityError:
            concurrent = await self.repository.get_insight(
                self.tenant.organisation_id,
                scope=scope,
                scope_target_id=scope_target_id,
                from_snapshot_id=before.snapshot.id,
                to_snapshot_id=after.snapshot.id,
                reasoning_version=REVENUE_BRAIN_REASONING_VERSION,
            )
            if concurrent is None:
                raise
            await self.repository.commit()
            logger.info(
                "revenue_brain_reasoning_reused",
                extra=self._telemetry(scope, company_id, opportunity_id),
            )
            return False

        await self.repository.commit()
        change_types = Counter(item.change_type for item in content.changes)
        directions = Counter(item.direction for item in content.changes)
        importance = Counter(item.importance for item in content.changes)
        logger.info(
            "revenue_brain_reasoning_completed",
            extra=self._telemetry(
                scope,
                company_id,
                opportunity_id,
                change_count=len(content.changes),
                change_type_counts=dict(change_types),
                direction_counts=dict(directions),
                importance_counts=dict(importance),
                no_material_change=not content.changes,
            ),
        )
        return True

    async def _eligible_bundles(
        self,
        *,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> list[RevenueBrainSnapshotBundle]:
        candidates = await self.repository.list_snapshot_candidates(
            self.tenant.organisation_id,
            scope=scope,
            company_id=company_id,
            opportunity_id=opportunity_id,
        )
        referenced_ids = {
            cast(UUID, getattr(candidate.snapshot, spec.reference_attribute))
            for candidate in candidates
            for spec in ARTIFACT_REFERENCE_SPECS
        }
        artifacts = await self.repository.load_referenced_artifacts(
            self.tenant.organisation_id,
            referenced_ids,
        )
        eligible: list[RevenueBrainSnapshotBundle] = []
        for candidate in candidates:
            bundle = self._validated_bundle(candidate, artifacts)
            if bundle is not None:
                eligible.append(bundle)
            if len(eligible) == REVENUE_BRAIN_RECENT_SNAPSHOT_LIMIT:
                break
        logger.info(
            "revenue_brain_snapshots_selected",
            extra=self._telemetry(
                scope,
                company_id,
                opportunity_id,
                candidate_count=len(candidates),
                eligible_snapshot_count=len(eligible),
            ),
        )
        return eligible

    def _validated_bundle(
        self,
        candidate: RevenueBrainSnapshotCandidate,
        artifacts: Mapping[UUID, AIArtifact],
    ) -> RevenueBrainSnapshotBundle | None:
        snapshot = candidate.snapshot
        if snapshot.version != 1:
            return None
        validated: dict[RevenueBrainSourceCapability, BaseModel] = {}
        artifact_ids: dict[RevenueBrainSourceCapability, UUID] = {}
        transcript_traces: set[tuple[UUID, int]] = set()
        for spec in ARTIFACT_REFERENCE_SPECS:
            artifact_id = cast(UUID, getattr(snapshot, spec.reference_attribute))
            untyped_artifact = artifacts.get(artifact_id)
            if untyped_artifact is None:
                return None
            artifact = untyped_artifact
            if (
                artifact.organisation_id != self.tenant.organisation_id
                or artifact.meeting_id != snapshot.meeting_id
                or artifact.artifact_type != spec.artifact_type
                or artifact.schema_version != spec.schema_version
            ):
                return None
            try:
                validated[spec.source] = spec.validation_model.model_validate(artifact.content_json)
            except ValidationError:
                return None
            artifact_ids[spec.source] = artifact.id
            transcript_traces.add((artifact.transcript_id, artifact.transcript_version))
        if len(transcript_traces) != 1:
            return None
        transcript_id, transcript_version = next(iter(transcript_traces))
        if snapshot.transcript_version_id != transcript_version_identifier(
            transcript_id,
            transcript_version,
        ):
            return None
        return RevenueBrainSnapshotBundle(
            snapshot=snapshot,
            meeting_date=candidate.meeting_date,
            payloads=RevenueBrainArtifactPayloads(
                executive_summary=cast(
                    ExecutiveSummaryArtifactContent,
                    validated["executive_summary"],
                ),
                buying_signals=cast(
                    BuyingSignalsArtifactContent,
                    validated["buying_signals"],
                ),
                objections_competitive_signals=cast(
                    ObjectionsCompetitiveSignalsArtifactContent,
                    validated["objections_competitive_signals"],
                ),
                stakeholder_intelligence=cast(
                    StakeholderIntelligenceArtifactContent,
                    validated["stakeholder_intelligence"],
                ),
                decisions=cast(DecisionsArtifactContent, validated["decisions"]),
                action_items=cast(
                    ActionItemsArtifactContent,
                    validated["action_items"],
                ),
                risks_blockers=cast(
                    RisksBlockersArtifactContent,
                    validated["risks_blockers"],
                ),
                open_questions=cast(
                    OpenQuestionsArtifactContent,
                    validated["open_questions"],
                ),
                next_best_action=cast(
                    NextBestActionArtifactContent,
                    validated["next_best_action"],
                ),
            ),
            artifact_ids=artifact_ids,
        )

    @staticmethod
    def _validate_evidence(
        content: RevenueBrainInsightContent,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> None:
        allowed = {
            (
                bundle.snapshot.id,
                artifact_id,
                source,
            )
            for bundle in (before, after)
            for source, artifact_id in bundle.artifact_ids.items()
        }
        if any(
            (
                evidence.snapshot_id,
                evidence.artefact_id,
                evidence.artefact_type,
            )
            not in allowed
            for change in content.changes
            for evidence in change.evidence
        ):
            raise ValueError("Reasoning evidence does not belong to the selected snapshots.")

    @staticmethod
    def _insight_response(
        insight: RevenueBrainInsight,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> RevenueBrainInsightResponse | None:
        try:
            content = RevenueBrainInsightContent.model_validate_json(json.dumps(insight.content_json))
        except ValidationError:
            return None
        if (
            insight.scope != scope
            or insight.company_id != company_id
            or insight.opportunity_id != opportunity_id
            or content.scope != scope
            or content.from_snapshot_id != insight.from_snapshot_id
            or content.to_snapshot_id != insight.to_snapshot_id
        ):
            return None
        return RevenueBrainInsightResponse(
            id=insight.id,
            company_id=insight.company_id,
            opportunity_id=insight.opportunity_id,
            reasoning_version=insight.reasoning_version,
            created_at=insight.created_at,
            content=content,
        )

    def _audit(
        self,
        event: str,
        scope: RevenueBrainScope,
        after: RevenueBrainSnapshotBundle,
        *,
        insight_id: UUID | None,
        change_count: int | None = None,
    ) -> MeetingAuditEvent:
        metadata: dict[str, object] = {
            "event": event,
            "scope": scope,
            "reasoning_version": REVENUE_BRAIN_REASONING_VERSION,
        }
        if insight_id is not None:
            metadata["insight_id"] = str(insight_id)
        if change_count is not None:
            metadata["change_count"] = change_count
        return MeetingAuditEvent(
            organisation_id=self.tenant.organisation_id,
            meeting_id=after.snapshot.meeting_id,
            actor_user_id=self.tenant.user_id,
            action="updated",
            entity_type="meeting",
            entity_id=after.snapshot.meeting_id,
            changed_fields=["revenue_brain_reasoning"],
            metadata_json=metadata,
            version=REVENUE_BRAIN_REASONING_VERSION,
        )

    def _telemetry(
        self,
        scope: RevenueBrainScope,
        company_id: UUID,
        opportunity_id: UUID | None,
        **metadata: object,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(self.tenant.organisation_id),
            "scope": scope,
            "company_id": str(company_id),
            "opportunity_id": str(opportunity_id) if opportunity_id else None,
            "reasoning_version": REVENUE_BRAIN_REASONING_VERSION,
            **metadata,
        }
