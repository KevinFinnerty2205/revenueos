from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.methodology_contracts import (
    MAX_CUSTOM_METHODOLOGIES,
    METHODOLOGY_SCHEMA_VERSION,
    PROJECTION_ENGINE_VERSION,
    CustomMethodologyCreateRequest,
    CustomMethodologyUpdateRequest,
    MethodologyCatalogueResponse,
    MethodologyDefinitionContent,
    MethodologyDefinitionSummary,
    MethodologyFieldDefinition,
    MethodologyGapContext,
    MethodologyGenerationResponse,
    MethodologyHistoryResponse,
    MethodologyProjectionContent,
    MethodologyProjectionItem,
    MethodologyProjectionSummary,
    MethodologyReviewMetadata,
    MethodologyReviewRequest,
    MethodologyReviewResponse,
    MethodologySelectionResponse,
    MethodologySelectionUpdate,
    MethodologySourceReference,
    MethodologyState,
    MethodologyStateCounts,
    OpportunityMethodologyResponse,
    StandardMethodologyKey,
)
from revenueos.methodology_registry import standard_methodologies, standard_methodology
from revenueos.methodology_repositories import CustomDefinitionRecord, MethodologyRepository
from revenueos.models import (
    AIArtifact,
    BetaSystemEvent,
    Evidence,
    InteractionIntelligenceSnapshot,
    MethodologyDefinition,
    MethodologyDefinitionVersion,
    MethodologyProjection,
    MethodologyReview,
    Opportunity,
    OrganisationMethodologySetting,
    RevenueBrainSourceSnapshot,
)
from revenueos.opportunity_repositories import MeetingSummaryRecord, OpportunityWorkspaceRepository
from revenueos.source_evidence_repositories import SourceEvidenceRepository
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.methodology")

SupportLevel = Literal["direct", "partial", "gap"]


@dataclass(frozen=True)
class EffectiveDefinition:
    content: MethodologyDefinitionContent
    definition_id: UUID | None
    definition_key: str
    kind: Literal["standard", "custom"]
    created_at: datetime | None
    status: Literal["active", "archived"] = "active"


@dataclass(frozen=True)
class FactCandidate:
    fact: str
    category: str
    conclusion: str | None
    source: MethodologySourceReference
    support: SupportLevel
    explicit_conflict: bool = False


@dataclass(frozen=True)
class SourceContext:
    candidates: tuple[FactCandidate, ...]
    reviews: tuple[MethodologyReview, ...]
    fingerprint: str


class SalesMethodologyProjectionService:
    """Deterministic projection over current validated RevenueOS evidence."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = MethodologyRepository(session)
        self.workspace = OpportunityWorkspaceRepository(session)
        self.source_repository = SourceEvidenceRepository(session)

    async def catalogue(self) -> MethodologyCatalogueResponse:
        custom_records = await self.repository.custom_definitions(self.tenant.organisation_id)
        return MethodologyCatalogueResponse(
            standards=[self._standard_summary(item) for item in standard_methodologies()],
            custom=[self._custom_summary(item) for item in custom_records],
            current=await self.current_selection(),
        )

    async def current_selection(self) -> MethodologySelectionResponse:
        setting = await self.repository.setting(self.tenant.organisation_id)
        if setting is None or setting.selection == "none":
            return MethodologySelectionResponse(
                selection="none",
                custom_definition_id=None,
                effective_definition=None,
                updated_at=setting.updated_at if setting is not None else None,
            )
        effective = await self._effective_definition(setting)
        return MethodologySelectionResponse(
            selection=cast(
                Literal["none", "meddic", "meddpicc", "bant", "spiced", "custom"],
                setting.selection,
            ),
            custom_definition_id=setting.custom_definition_id,
            effective_definition=self._definition_summary(effective),
            updated_at=setting.updated_at,
        )

    async def select_methodology(self, request: MethodologySelectionUpdate) -> MethodologySelectionResponse:
        self._require_admin()
        setting = await self.repository.setting(self.tenant.organisation_id, for_update=True)
        if request.selection == "custom":
            assert request.custom_definition_id is not None
            custom = await self.repository.custom_definition(
                self.tenant.organisation_id,
                request.custom_definition_id,
            )
            if custom is None or custom.definition.status != "active":
                raise PublicAPIError(
                    "methodology_not_found",
                    "The selected custom methodology is unavailable.",
                    404,
                )
        if setting is None:
            setting = OrganisationMethodologySetting(
                organisation_id=self.tenant.organisation_id,
                selection=request.selection,
                custom_definition_id=request.custom_definition_id,
                updated_by_user_id=self.tenant.user_id,
            )
            self.repository.add(setting)
        else:
            setting.selection = request.selection
            setting.custom_definition_id = request.custom_definition_id
            setting.updated_by_user_id = self.tenant.user_id
            setting.updated_at = datetime.now(UTC)
        self._event(
            "methodology_selected",
            setting.custom_definition_id,
            {"methodology_type": request.selection},
        )
        await self._commit("The organisation sales methodology could not be saved.")
        return await self.current_selection()

    async def create_custom(
        self,
        request: CustomMethodologyCreateRequest,
    ) -> MethodologyDefinitionSummary:
        self._require_admin()
        if await self.repository.custom_definition_count(self.tenant.organisation_id) >= MAX_CUSTOM_METHODOLOGIES:
            raise PublicAPIError(
                "custom_methodology_limit_reached",
                f"An organisation can keep up to {MAX_CUSTOM_METHODOLOGIES} custom methodologies.",
                409,
            )
        definition_id = uuid.uuid4()
        content = MethodologyDefinitionContent(
            key=f"custom_{definition_id.hex[:12]}",
            name=request.name,
            description=request.description,
            version=1,
            standard=False,
            fields=tuple(request.fields),
        )
        now = datetime.now(UTC)
        definition = MethodologyDefinition(
            id=definition_id,
            organisation_id=self.tenant.organisation_id,
            status="active",
            current_version=1,
            created_by_user_id=self.tenant.user_id,
            created_at=now,
            updated_at=now,
        )
        version = self._definition_version(definition_id, content, now)
        self.repository.add(definition)
        self.repository.add(version)
        self._event(
            "custom_methodology_created",
            definition_id,
            {"version": 1, "field_count": len(content.fields)},
        )
        await self._commit("The custom methodology could not be created.")
        saved = await self.repository.custom_definition(self.tenant.organisation_id, definition_id)
        assert saved is not None
        return self._custom_summary(saved)

    async def update_custom(
        self,
        definition_id: UUID,
        request: CustomMethodologyUpdateRequest,
    ) -> MethodologyDefinitionSummary:
        self._require_admin()
        record = await self.repository.custom_definition(
            self.tenant.organisation_id,
            definition_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError("methodology_not_found", "The custom methodology was not found.", 404)
        if record.definition.status != "active":
            raise PublicAPIError(
                "methodology_archived",
                "Archived methodologies cannot be edited. Create a new methodology instead.",
                409,
            )
        if record.definition.current_version != request.expected_version:
            raise PublicAPIError(
                "stale_methodology_version",
                "This methodology changed after it was loaded. Refresh and try again.",
                409,
            )
        next_version = record.definition.current_version + 1
        previous = self._parse_definition(record.version)
        content = MethodologyDefinitionContent(
            key=previous.key,
            name=request.name,
            description=request.description,
            version=next_version,
            standard=False,
            fields=tuple(request.fields),
        )
        now = datetime.now(UTC)
        record.definition.current_version = next_version
        record.definition.updated_at = now
        self.repository.add(self._definition_version(definition_id, content, now))
        self._event(
            "custom_methodology_versioned",
            definition_id,
            {"version": next_version, "field_count": len(content.fields)},
        )
        await self._commit("The custom methodology version could not be saved.")
        saved = await self.repository.custom_definition(self.tenant.organisation_id, definition_id)
        assert saved is not None
        return self._custom_summary(saved)

    async def archive_custom(self, definition_id: UUID) -> MethodologyDefinitionSummary:
        self._require_admin()
        record = await self.repository.custom_definition(
            self.tenant.organisation_id,
            definition_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError("methodology_not_found", "The custom methodology was not found.", 404)
        if record.definition.status == "archived":
            return self._custom_summary(record)
        now = datetime.now(UTC)
        record.definition.status = "archived"
        record.definition.archived_at = now
        record.definition.updated_at = now
        setting = await self.repository.setting(self.tenant.organisation_id, for_update=True)
        if setting is not None and setting.custom_definition_id == definition_id:
            setting.selection = "none"
            setting.custom_definition_id = None
            setting.updated_by_user_id = self.tenant.user_id
            setting.updated_at = now
        self._event(
            "custom_methodology_archived",
            definition_id,
            {"version": record.definition.current_version},
        )
        await self._commit("The custom methodology could not be archived.")
        saved = await self.repository.custom_definition(self.tenant.organisation_id, definition_id)
        assert saved is not None
        return self._custom_summary(saved)

    async def generate(self, opportunity_id: UUID) -> MethodologyGenerationResponse:
        self._require_feature()
        opportunity = await self._opportunity(opportunity_id, for_update=True)
        effective = await self._require_effective_definition()
        context = await self._source_context(opportunity, effective)
        existing = await self.repository.projection_by_fingerprint(
            self.tenant.organisation_id,
            opportunity_id,
            effective.definition_key,
            effective.content.version,
            context.fingerprint,
        )
        if existing is not None:
            response = self._projection_response(existing, effective, needs_refresh=False)
            logger.info(
                "methodology_projection_reused",
                extra=self._projection_log(existing, response.projection),
            )
            return MethodologyGenerationResponse(**response.model_dump(), created=False, reused=True)

        now = datetime.now(UTC)
        projection_version = await self.repository.next_projection_version(
            self.tenant.organisation_id,
            opportunity_id,
        )
        content = self._compose(
            opportunity,
            effective,
            context,
            projection_version=projection_version,
            generated_at=now,
        )
        projection = MethodologyProjection(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            methodology_kind=effective.kind,
            definition_key=effective.definition_key,
            definition_id=effective.definition_id,
            definition_version=effective.content.version,
            projection_version=projection_version,
            engine_version=PROJECTION_ENGINE_VERSION,
            schema_version=METHODOLOGY_SCHEMA_VERSION,
            source_fingerprint=context.fingerprint,
            content_json=content.as_json(),
            generated_by_user_id=self.tenant.user_id,
            generated_at=now,
        )
        self.repository.add(projection)
        self._event(
            "methodology_projection_generated",
            projection.id,
            {
                "methodology_type": effective.kind,
                "definition_version": effective.content.version,
                "projection_version": projection_version,
                "state_counts": content.state_counts.model_dump(mode="json"),
            },
        )
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.repository.projection_by_fingerprint(
                self.tenant.organisation_id,
                opportunity_id,
                effective.definition_key,
                effective.content.version,
                context.fingerprint,
            )
            if concurrent is None:
                raise PublicAPIError(
                    "methodology_generation_conflict",
                    "The methodology changed while it was being generated. Refresh and try again.",
                    409,
                ) from exc
            response = self._projection_response(concurrent, effective, needs_refresh=False)
            return MethodologyGenerationResponse(**response.model_dump(), created=False, reused=True)
        response = self._projection_response(projection, effective, needs_refresh=False)
        logger.info("methodology_projection_generated", extra=self._projection_log(projection, content))
        return MethodologyGenerationResponse(**response.model_dump(), created=True, reused=False)

    async def read(self, opportunity_id: UUID) -> OpportunityMethodologyResponse:
        if not self.settings.feature_sales_methodology_enabled:
            return OpportunityMethodologyResponse(
                state="disabled",
                generation_available=False,
                needs_refresh=False,
                safe_message="Sales Methodology is not enabled for this private-beta environment.",
                definition=None,
                projection_id=None,
                projection=None,
                generated_at=None,
            )
        opportunity = await self._opportunity(opportunity_id)
        setting = await self.repository.setting(self.tenant.organisation_id)
        if setting is None or setting.selection == "none":
            return OpportunityMethodologyResponse(
                state="not_configured",
                generation_available=False,
                needs_refresh=False,
                safe_message=(
                    "Your organisation has not selected a sales methodology. RevenueOS continues to work normally."
                ),
                definition=None,
                projection_id=None,
                projection=None,
                generated_at=None,
            )
        effective = await self._effective_definition(setting)
        latest = await self.repository.latest_projection(
            self.tenant.organisation_id,
            opportunity_id,
            definition_key=effective.definition_key,
            definition_version=effective.content.version,
        )
        if latest is None:
            return OpportunityMethodologyResponse(
                state="not_generated",
                generation_available=True,
                needs_refresh=False,
                safe_message="Generate this view from the opportunity’s current validated evidence.",
                definition=self._definition_summary(effective),
                projection_id=None,
                projection=None,
                generated_at=None,
            )
        context = await self._source_context(opportunity, effective)
        needs_refresh = context.fingerprint != latest.source_fingerprint
        if needs_refresh:
            return OpportunityMethodologyResponse(
                state="needs_refresh",
                generation_available=True,
                needs_refresh=True,
                safe_message=("The supporting evidence changed. Refresh this view before relying on its conclusions."),
                definition=self._definition_summary(effective),
                projection_id=latest.id,
                projection=None,
                generated_at=latest.generated_at,
            )
        return self._projection_response(latest, effective, needs_refresh=needs_refresh)

    async def history(self, opportunity_id: UUID) -> MethodologyHistoryResponse:
        await self._opportunity(opportunity_id)
        current = await self.read(opportunity_id)
        history = await self.repository.projection_history(
            self.tenant.organisation_id,
            opportunity_id,
        )
        items: list[MethodologyProjectionSummary] = []
        for projection in history:
            try:
                content = MethodologyProjectionContent.model_validate(projection.content_json)
            except ValidationError:
                continue
            items.append(
                MethodologyProjectionSummary(
                    id=projection.id,
                    methodology_key=content.methodology_key,
                    methodology_name=content.methodology_name,
                    definition_version=projection.definition_version,
                    projection_version=projection.projection_version,
                    state_counts=content.state_counts,
                    generated_at=projection.generated_at,
                    projection=content,
                )
            )
        return MethodologyHistoryResponse(
            current_projection_id=current.projection_id,
            items=items,
        )

    async def review(
        self,
        opportunity_id: UUID,
        field_key: str,
        request: MethodologyReviewRequest,
    ) -> MethodologyReviewResponse:
        self._require_feature()
        duplicate = await self.repository.review_by_idempotency(
            self.tenant.organisation_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if duplicate is not None:
            if duplicate.opportunity_id != opportunity_id or duplicate.field_key != field_key:
                raise PublicAPIError(
                    "methodology_review_idempotency_conflict",
                    "This review key has already been used for another methodology field.",
                    409,
                )
            return MethodologyReviewResponse(
                review_id=duplicate.id,
                clarification_evidence_id=duplicate.clarification_evidence_id,
                methodology=await self.read(opportunity_id),
            )
        await self._opportunity(opportunity_id, for_update=True)
        setting = await self.repository.setting(self.tenant.organisation_id)
        if setting is None or setting.selection == "none":
            raise PublicAPIError(
                "methodology_not_configured",
                "Select an organisation sales methodology before reviewing this view.",
                409,
            )
        effective = await self._effective_definition(setting)
        current = await self.repository.latest_projection(
            self.tenant.organisation_id,
            opportunity_id,
            definition_key=effective.definition_key,
            definition_version=effective.content.version,
        )
        if current is None:
            raise PublicAPIError(
                "methodology_not_generated",
                "Generate the current methodology view before reviewing it.",
                409,
            )
        if current.id != request.expected_projection_id:
            raise PublicAPIError(
                "stale_methodology_projection",
                "This methodology view changed after it was loaded. Refresh and try again.",
                409,
            )
        content = self._parse_projection(current)
        if field_key not in {item.field_key for item in content.items}:
            raise PublicAPIError("methodology_field_not_found", "The methodology field was not found.", 404)
        now = datetime.now(UTC)
        evidence_id: UUID | None = None
        if request.action == "clarify":
            assert request.clarification is not None
            evidence_id = uuid.uuid4()
            self.repository.add(
                Evidence(
                    id=evidence_id,
                    organisation_id=self.tenant.organisation_id,
                    interaction_id=None,
                    capture_session_id=None,
                    evidence_type="user_observation",
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="verified",
                    captured_by_user_id=self.tenant.user_id,
                    captured_at=now,
                    effective_start_at=now,
                    lifecycle_status="available",
                    retention_class="inherited",
                )
            )
        review = MethodologyReview(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            projection_id=current.id,
            opportunity_id=opportunity_id,
            field_key=field_key,
            action=request.action,
            clarification_text=request.clarification,
            clarification_evidence_id=evidence_id,
            reviewed_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
        )
        self.repository.add(review)
        self._event(
            "methodology_field_reviewed",
            review.id,
            {"action": request.action, "factual_clarification": evidence_id is not None},
        )
        if evidence_id is not None:
            self._event(
                "methodology_clarification_added",
                review.id,
                {"origin_class": "salesperson_reported"},
            )
        await self._commit("The methodology review could not be saved.")
        # Reviews change the source fingerprint; generation remains explicit so the
        # previous immutable view is still explainable and the UI can show refresh.
        return MethodologyReviewResponse(
            review_id=review.id,
            clarification_evidence_id=evidence_id,
            methodology=await self.read(opportunity_id),
        )

    async def gap_context(
        self,
        opportunity_id: UUID,
        *,
        limit: int = 3,
    ) -> tuple[MethodologyGapContext, ...]:
        response = await self.read(opportunity_id)
        if response.state not in {"current", "needs_refresh"} or response.projection is None:
            return ()
        if response.needs_refresh:
            return ()
        ranked = sorted(
            (item for item in response.projection.items if item.state != "confirmed"),
            key=lambda item: (
                {"conflicting": 0, "stale": 1, "unknown": 2, "partially_supported": 3}[item.state],
                not item.required,
                next(
                    field.order
                    for field in cast(MethodologyDefinitionSummary, response.definition).fields
                    if field.key == item.field_key
                ),
            ),
        )
        assert response.projection_id is not None
        return tuple(
            MethodologyGapContext(
                projection_id=response.projection_id,
                methodology_key=response.projection.methodology_key,
                field_key=item.field_key,
                display_name=item.display_name,
                state=cast(
                    Literal["partially_supported", "unknown", "conflicting", "stale"],
                    item.state,
                ),
                conclusion=item.conclusion,
                suggested_question=item.suggested_question
                or f"What should we confirm about {item.display_name.lower()}?",
                sources=item.sources[:6],
            )
            for item in ranked[:limit]
        )

    async def _source_context(
        self,
        opportunity: Opportunity,
        effective: EffectiveDefinition,
    ) -> SourceContext:
        meetings = await self.workspace.recent_meetings(
            self.tenant.organisation_id,
            opportunity.id,
            limit=10,
        )
        artifacts = await self.workspace.current_completed_artifacts(
            self.tenant.organisation_id,
            meetings,
            artifact_types={
                "buying_signals",
                "objections_competitive_signals",
                "stakeholder_intelligence",
                "decisions",
                "risks_blockers",
                "open_questions",
            },
        )
        source_snapshots = await self.source_repository.list_snapshots_for_opportunity(
            self.tenant.organisation_id,
            opportunity.id,
            limit=20,
        )
        interaction_snapshots = await self.repository.eligible_interaction_snapshots(
            self.tenant.organisation_id,
            opportunity.id,
            limit=20,
        )
        reviews = await self.repository.reviews(
            self.tenant.organisation_id,
            opportunity.id,
            limit=100,
        )
        candidates: list[FactCandidate] = []
        candidates.extend(self._artifact_candidates(artifacts, meetings))
        candidates.extend(self._source_snapshot_candidates(source_snapshots))
        candidates.extend(self._interaction_snapshot_candidates(interaction_snapshots))
        candidates.extend(self._opportunity_candidates(opportunity))
        candidates.extend(self._review_candidates(reviews, effective))
        fingerprint = self._sha256(
            {
                "engineVersion": PROJECTION_ENGINE_VERSION,
                "definitionKey": effective.definition_key,
                "definitionVersion": effective.content.version,
                "definitionFingerprint": self._sha256(effective.content.as_json()),
                "opportunity": {
                    "id": str(opportunity.id),
                    "stage": opportunity.stage,
                    "expectedCloseDate": (
                        opportunity.expected_close_date.isoformat() if opportunity.expected_close_date else None
                    ),
                    "descriptionFingerprint": (
                        hashlib.sha256(opportunity.description.encode()).hexdigest()
                        if opportunity.description
                        else None
                    ),
                },
                "candidates": [
                    {
                        "fact": item.fact,
                        "category": item.category,
                        "conclusionFingerprint": (
                            hashlib.sha256(item.conclusion.encode()).hexdigest() if item.conclusion else None
                        ),
                        "sourceType": item.source.source_type,
                        "sourceId": str(item.source.source_id),
                        "itemKey": item.source.item_key,
                        "origin": item.source.origin,
                        "classification": item.source.source_classification,
                        "supportedAt": self._as_utc(item.source.supported_at).isoformat(),
                        "support": item.support,
                        "conflict": item.explicit_conflict,
                    }
                    for item in candidates
                ],
                "reviews": [
                    {
                        "id": str(item.id),
                        "projectionId": str(item.projection_id),
                        "fieldKey": item.field_key,
                        "action": item.action,
                        "clarificationEvidenceId": (
                            str(item.clarification_evidence_id) if item.clarification_evidence_id else None
                        ),
                        "createdAt": self._as_utc(item.created_at).isoformat(),
                    }
                    for item in reviews
                ],
            }
        )
        return SourceContext(
            candidates=tuple(candidates),
            reviews=tuple(reviews),
            fingerprint=fingerprint,
        )

    def _artifact_candidates(
        self,
        artifacts: list[AIArtifact],
        meetings: list[MeetingSummaryRecord],
    ) -> list[FactCandidate]:
        meeting_dates = {item.meeting.id: self._as_utc(item.meeting.meeting_date) for item in meetings}
        validators: dict[str, type[BaseModel]] = {
            "buying_signals": BuyingSignalsArtifactContent,
            "objections_competitive_signals": ObjectionsCompetitiveSignalsArtifactContent,
            "stakeholder_intelligence": StakeholderIntelligenceArtifactContent,
            "decisions": DecisionsArtifactContent,
            "risks_blockers": RisksBlockersArtifactContent,
            "open_questions": OpenQuestionsArtifactContent,
        }
        selected: set[tuple[UUID, str]] = set()
        values: list[FactCandidate] = []
        for artifact in artifacts:
            key = (artifact.meeting_id, artifact.artifact_type)
            validator = validators.get(artifact.artifact_type)
            if key in selected or validator is None or artifact.superseded_at is not None:
                continue
            selected.add(key)
            try:
                content = validator.model_validate(artifact.content_json)
            except ValidationError:
                continue
            supported_at = meeting_dates.get(artifact.meeting_id, self._as_utc(artifact.created_at))
            if isinstance(content, BuyingSignalsArtifactContent):
                values.extend(self._buying_signal_candidates(artifact, content, supported_at))
            elif isinstance(content, StakeholderIntelligenceArtifactContent):
                values.extend(self._stakeholder_candidates(artifact, content, supported_at))
            elif isinstance(content, ObjectionsCompetitiveSignalsArtifactContent):
                for index, competitor in enumerate(content.competitors):
                    values.append(
                        self._artifact_candidate(
                            artifact,
                            "competition",
                            "competitor",
                            f"{competitor.name} is an active alternative ({competitor.position}).",
                            f"competitor:{index}",
                            competitor.evidence,
                            supported_at,
                            support="direct",
                        )
                    )
            elif isinstance(content, DecisionsArtifactContent):
                for index, decision in enumerate(content.decisions):
                    support: SupportLevel = "direct" if decision.status == "confirmed" else "partial"
                    facts = ["decision"]
                    lowered = f"{decision.decision} {decision.evidence}".casefold()
                    if any(term in lowered for term in ("criteria", "requirement", "evaluate", "compare")):
                        facts.append("decision_criteria")
                    if any(term in lowered for term in ("process", "approval", "step", "committee")):
                        facts.append("decision_process")
                    for fact in facts:
                        values.append(
                            self._artifact_candidate(
                                artifact,
                                fact,
                                "decision",
                                decision.decision,
                                f"decision:{index}:{fact}",
                                decision.evidence,
                                supported_at,
                                support=support,
                            )
                        )
            elif isinstance(content, RisksBlockersArtifactContent):
                risk_facts = {
                    "budget": ("budget",),
                    "procurement": ("paper_process", "decision_process"),
                    "legal": ("paper_process",),
                    "security": ("paper_process", "decision_criteria"),
                    "timeline": ("timing", "critical_event"),
                    "stakeholder": ("authority",),
                    "competitor": ("competition",),
                    "implementation": ("situation",),
                    "technical": ("decision_criteria", "situation"),
                }
                for index, risk in enumerate(content.risks):
                    for fact in risk_facts.get(risk.category, ()):
                        values.append(
                            self._artifact_candidate(
                                artifact,
                                fact,
                                "risk",
                                risk.risk,
                                f"risk:{index}:{fact}",
                                risk.evidence,
                                supported_at,
                                support="partial",
                            )
                        )
            elif isinstance(content, OpenQuestionsArtifactContent):
                for index, question in enumerate(content.open_questions):
                    for fact in self._facts_for_text(question.question):
                        values.append(
                            self._artifact_candidate(
                                artifact,
                                fact,
                                "open_question",
                                None,
                                f"open_question:{index}:{fact}",
                                question.evidence,
                                supported_at,
                                support="gap",
                            )
                        )
        return values

    def _buying_signal_candidates(
        self,
        artifact: AIArtifact,
        content: BuyingSignalsArtifactContent,
        supported_at: datetime,
    ) -> list[FactCandidate]:
        positive: dict[str, tuple[str, ...]] = {
            "budget_confirmed": ("budget",),
            "timeline_confirmed": ("timing", "critical_event"),
            "decision_maker_engaged": ("authority", "economic_buyer"),
            "champion_identified": ("champion",),
            "procurement_active": ("paper_process", "decision_process"),
            "competitor_present": ("competition",),
            "urgency_present": ("timing", "critical_event"),
            "commercial_intent": ("need", "pain", "business_pain"),
            "implementation_commitment": ("decision", "situation"),
            "technical_fit_confirmed": ("decision_criteria",),
        }
        gaps: dict[str, tuple[str, ...]] = {
            "budget_unconfirmed": ("budget",),
            "timeline_unclear": ("timing",),
            "decision_maker_missing": ("authority", "economic_buyer"),
            "champion_not_evident": ("champion",),
            "procurement_unclear": ("paper_process", "decision_process"),
            "technical_fit_uncertain": ("decision_criteria",),
        }
        values: list[FactCandidate] = []
        for index, signal in enumerate(content.signals):
            facts = positive.get(signal.signal_type, ())
            support: SupportLevel = "direct"
            if not facts:
                facts = gaps.get(signal.signal_type, ())
                support = "gap"
            for fact in facts:
                values.append(
                    self._artifact_candidate(
                        artifact,
                        fact,
                        "buying_signal",
                        signal.evidence if support != "gap" else None,
                        f"signal:{index}:{fact}",
                        signal.evidence,
                        supported_at,
                        support=support,
                    )
                )
        return values

    def _stakeholder_candidates(
        self,
        artifact: AIArtifact,
        content: StakeholderIntelligenceArtifactContent,
        supported_at: datetime,
    ) -> list[FactCandidate]:
        role_facts: dict[str, tuple[str, ...]] = {
            "economic_buyer": ("economic_buyer", "authority"),
            "decision_maker": ("authority", "decision_process"),
            "champion": ("champion",),
            "procurement": ("paper_process", "decision_process"),
            "finance": ("economic_buyer", "authority", "budget"),
            "executive_sponsor": ("authority",),
        }
        values: list[FactCandidate] = []
        for index, stakeholder in enumerate(content.stakeholders):
            for fact in role_facts.get(stakeholder.role, ()):
                values.append(
                    self._artifact_candidate(
                        artifact,
                        fact,
                        "stakeholder",
                        f"{stakeholder.name} is identified as {stakeholder.role.replace('_', ' ')}.",
                        f"stakeholder:{index}:{fact}",
                        stakeholder.evidence,
                        supported_at,
                        support="direct",
                    )
                )
        coverage_facts = {
            "economic_buyer": ("economic_buyer", "authority"),
            "decision_maker": ("authority", "decision_process"),
            "champion": ("champion",),
            "procurement": ("paper_process",),
        }
        coverage = content.role_coverage.model_dump(mode="python")
        for coverage_key, facts in coverage_facts.items():
            if coverage.get(coverage_key) not in {"not_identified", "unclear"}:
                continue
            for fact in facts:
                values.append(
                    self._artifact_candidate(
                        artifact,
                        fact,
                        "stakeholder",
                        None,
                        f"coverage:{coverage_key}:{fact}",
                        content.stakeholder_summary,
                        supported_at,
                        support="gap",
                    )
                )
        return values

    def _artifact_candidate(
        self,
        artifact: AIArtifact,
        fact: str,
        category: str,
        conclusion: str | None,
        item_key: str,
        label_detail: str,
        supported_at: datetime,
        *,
        support: SupportLevel,
    ) -> FactCandidate:
        lowered_detail = label_detail.casefold()
        if fact in {"authority", "economic_buyer", "champion"} and any(
            marker in lowered_detail
            for marker in ("unknown speaker", "unidentified speaker", "seller:", "salesperson says")
        ):
            support = "partial"
        return FactCandidate(
            fact=fact,
            category=category,
            conclusion=conclusion,
            source=MethodologySourceReference(
                source_type="ai_artifact",
                source_id=artifact.id,
                item_key=item_key,
                label=self._bounded_label(f"Final {artifact.artifact_type.replace('_', ' ')}: {label_detail}"),
                origin="validated_intelligence",
                supported_at=supported_at,
                source_classification="Final validated Interaction Intelligence",
            ),
            support=support,
        )

    def _source_snapshot_candidates(
        self,
        snapshots: list[RevenueBrainSourceSnapshot],
    ) -> list[FactCandidate]:
        values: list[FactCandidate] = []
        for snapshot in snapshots:
            raw_items = snapshot.content_json.get("items")
            occurred_at = self._parse_datetime(snapshot.content_json.get("occurredAt")) or self._as_utc(
                snapshot.created_at
            )
            if not isinstance(raw_items, list):
                continue
            for index, raw in enumerate(raw_items):
                if not isinstance(raw, dict):
                    continue
                category = raw.get("category")
                statement = raw.get("statement")
                evidence_id = raw.get("evidenceId")
                origin = raw.get("originClass")
                support_class = raw.get("supportClass")
                source_label = raw.get("sourceLabel")
                if (
                    not isinstance(category, str)
                    or not isinstance(statement, str)
                    or not isinstance(evidence_id, str)
                    or not isinstance(source_label, str)
                    or origin not in {"customer_direct", "salesperson_reported", "imported_external", "seller_prepared"}
                ):
                    continue
                try:
                    source_id = UUID(evidence_id)
                except ValueError:
                    continue
                facts = self._facts_for_category(category, statement)
                direct = origin == "customer_direct" and support_class == "direct"
                candidate_support: SupportLevel = "direct" if direct else "partial"
                if origin == "seller_prepared":
                    facts = tuple(fact for fact in facts if fact in {"situation", "decision_criteria", "paper_process"})
                for fact in facts:
                    values.append(
                        FactCandidate(
                            fact=fact,
                            category=category,
                            conclusion=statement,
                            source=MethodologySourceReference(
                                source_type="accepted_evidence",
                                source_id=source_id,
                                item_key=f"item:{index}:{fact}",
                                label=self._bounded_label(source_label),
                                origin=cast(
                                    Literal[
                                        "customer_direct",
                                        "salesperson_reported",
                                        "imported_external",
                                        "seller_prepared",
                                    ],
                                    origin,
                                ),
                                supported_at=occurred_at,
                                source_classification=f"Accepted {snapshot.source_kind} evidence",
                            ),
                            support=candidate_support,
                            explicit_conflict=raw.get("conflictState") == "conflicting",
                        )
                    )
        return values

    def _interaction_snapshot_candidates(
        self,
        snapshots: list[InteractionIntelligenceSnapshot],
    ) -> list[FactCandidate]:
        values: list[FactCandidate] = []
        for snapshot in snapshots:
            raw_items = snapshot.content_json.get("items")
            if not isinstance(raw_items, list):
                continue
            for index, raw in enumerate(raw_items):
                if not isinstance(raw, dict):
                    continue
                category = raw.get("category")
                statement = raw.get("statement")
                if not isinstance(category, str) or not isinstance(statement, str):
                    continue
                source_id = snapshot.id
                if snapshot.schema_version == 1:
                    origin: Literal["salesperson_reported", "validated_intelligence"] = "salesperson_reported"
                    support: SupportLevel = "partial"
                    label = "Reported by you"
                else:
                    origin = "validated_intelligence"
                    ownership = raw.get("sourceOwnership")
                    classification = raw.get("supportClassification")
                    support = (
                        "direct"
                        if ownership in {"customer_created", "jointly_created"} and classification == "direct"
                        else "partial"
                    )
                    raw_label = raw.get("sourceLabel")
                    label = raw_label if isinstance(raw_label, str) else "Reviewed visual"
                    if ownership == "salesperson_created" and category in {
                        "budget",
                        "commercial_intent",
                        "objection",
                    }:
                        continue
                for fact in self._facts_for_category(category, statement):
                    values.append(
                        FactCandidate(
                            fact=fact,
                            category=category,
                            conclusion=statement,
                            source=MethodologySourceReference(
                                source_type="interaction_intelligence",
                                source_id=source_id,
                                item_key=f"item:{index}:{fact}",
                                label=self._bounded_label(label),
                                origin=origin,
                                supported_at=self._as_utc(snapshot.created_at),
                                source_classification=(
                                    "Reviewed salesperson report"
                                    if snapshot.schema_version == 1
                                    else "Reviewed visual evidence"
                                ),
                            ),
                            support=support,
                            explicit_conflict=raw.get("conflictState") == "conflicting",
                        )
                    )
        return values

    def _opportunity_candidates(self, opportunity: Opportunity) -> list[FactCandidate]:
        values: list[FactCandidate] = []
        supported_at = self._as_utc(opportunity.updated_at)
        if opportunity.expected_close_date is not None:
            values.extend(
                self._opportunity_candidate(
                    opportunity,
                    fact,
                    "timeline",
                    f"The salesperson’s current opportunity close date is {opportunity.expected_close_date.isoformat()}.",
                    supported_at,
                )
                for fact in ("timing", "critical_event")
            )
        if opportunity.description:
            values.append(
                self._opportunity_candidate(
                    opportunity,
                    "situation",
                    "other",
                    opportunity.description[:1000],
                    supported_at,
                )
            )
        return values

    @staticmethod
    def _opportunity_candidate(
        opportunity: Opportunity,
        fact: str,
        category: str,
        conclusion: str,
        supported_at: datetime,
    ) -> FactCandidate:
        return FactCandidate(
            fact=fact,
            category=category,
            conclusion=conclusion,
            source=MethodologySourceReference(
                source_type="opportunity_state",
                source_id=opportunity.id,
                item_key=f"opportunity:{fact}",
                label="Opportunity information",
                origin="salesperson_reported",
                supported_at=supported_at,
                source_classification="Salesperson-owned opportunity information",
            ),
            support="partial",
        )

    def _review_candidates(
        self,
        reviews: list[MethodologyReview],
        effective: EffectiveDefinition,
    ) -> list[FactCandidate]:
        fields = {field.key: field for field in effective.content.fields}
        values: list[FactCandidate] = []
        for review in reviews:
            field = fields.get(review.field_key)
            if (
                field is None
                or review.action != "clarify"
                or review.clarification_evidence_id is None
                or review.clarification_text is None
            ):
                continue
            for fact in field.canonical_facts:
                values.append(
                    FactCandidate(
                        fact=fact,
                        category=field.evidence_categories[0],
                        conclusion=review.clarification_text,
                        source=MethodologySourceReference(
                            source_type="methodology_review",
                            source_id=review.id,
                            item_key=f"clarification:{fact}",
                            label="Clarified by you",
                            origin="salesperson_reported",
                            supported_at=self._as_utc(review.created_at),
                            source_classification="Salesperson-reported clarification",
                        ),
                        support="partial",
                    )
                )
        return values

    def _compose(
        self,
        opportunity: Opportunity,
        effective: EffectiveDefinition,
        context: SourceContext,
        *,
        projection_version: int,
        generated_at: datetime,
    ) -> MethodologyProjectionContent:
        items = tuple(self._project_field(field, context, generated_at) for field in effective.content.fields)
        counts = MethodologyStateCounts(
            confirmed=sum(item.state == "confirmed" for item in items),
            partially_supported=sum(item.state == "partially_supported" for item in items),
            unknown=sum(item.state == "unknown" for item in items),
            conflicting=sum(item.state == "conflicting" for item in items),
            stale=sum(item.state == "stale" for item in items),
        )
        return MethodologyProjectionContent(
            opportunity_id=opportunity.id,
            methodology_key=effective.content.key,
            methodology_name=effective.content.name,
            definition_version=effective.content.version,
            projection_version=projection_version,
            engine_version=PROJECTION_ENGINE_VERSION,
            state_counts=counts,
            items=items,
            generated_at=generated_at,
        )

    def _project_field(
        self,
        field: MethodologyFieldDefinition,
        context: SourceContext,
        now: datetime,
    ) -> MethodologyProjectionItem:
        candidates = [
            item
            for item in context.candidates
            if item.fact in field.canonical_facts and item.category in field.evidence_categories
        ]
        candidates.sort(
            key=lambda item: (self._as_utc(item.source.supported_at), str(item.source.source_id)), reverse=True
        )
        support = [item for item in candidates if item.support in {"direct", "partial"}]
        gap_sources = [item.source for item in candidates if item.support == "gap"]
        explicit_conflicts = [item for item in support if item.explicit_conflict]
        if not explicit_conflicts and self._conclusions_conflict(support):
            explicit_conflicts = support
        latest_review_by_action = [item for item in context.reviews if item.field_key == field.key]
        latest_override = next(
            (item for item in reversed(latest_review_by_action) if item.action in {"mark_not_known", "mark_incorrect"}),
            None,
        )
        latest_clarification = next(
            (item for item in reversed(latest_review_by_action) if item.action == "clarify"),
            None,
        )
        if latest_override is not None and (
            latest_clarification is None or latest_override.created_at >= latest_clarification.created_at
        ):
            state: MethodologyState = "unknown"
            conclusion = None
            support = []
            explicit_conflicts = []
        elif explicit_conflicts:
            state = "conflicting"
            conclusion = "Current valid sources disagree. RevenueOS has not selected either interpretation."
        elif any(item.support == "direct" for item in support):
            state = "confirmed"
            conclusion = next(item.conclusion for item in support if item.support == "direct" and item.conclusion)
        elif support:
            state = "partially_supported"
            conclusion = next((item.conclusion for item in support if item.conclusion), None)
        else:
            state = "unknown"
            conclusion = None
        last_supported_at = max(
            (self._as_utc(item.source.supported_at) for item in support),
            default=None,
        )
        freshness: Literal["current", "stale", "not_applicable"]
        if last_supported_at is None or field.freshness_days is None:
            freshness = "not_applicable" if field.freshness_days is None else "current"
        elif last_supported_at < now - timedelta(days=field.freshness_days):
            freshness = "stale"
            if state in {"confirmed", "partially_supported"}:
                state = "stale"
        else:
            freshness = "current"
        sources = self._unique_sources([item.source for item in support] + gap_sources)[:12]
        conflicts = self._unique_sources([item.source for item in explicit_conflicts])[:12]
        reviews = tuple(
            MethodologyReviewMetadata(
                action=cast(
                    Literal[
                        "confirm_interpretation",
                        "clarify",
                        "mark_not_known",
                        "mark_incorrect",
                    ],
                    review.action,
                ),
                reviewed_at=review.created_at,
                reviewed_by_user_id=review.reviewed_by_user_id,
                clarification_evidence_id=review.clarification_evidence_id,
            )
            for review in latest_review_by_action[-10:]
        )
        return MethodologyProjectionItem(
            field_key=field.key,
            display_name=field.display_name,
            explanation=field.explanation,
            required=field.required,
            state=state,
            conclusion=conclusion,
            sources=tuple(sources),
            conflicts=tuple(conflicts),
            last_supported_at=last_supported_at,
            freshness=freshness,
            suggested_question=(field.suggested_questions[0] if state != "confirmed" else None),
            stage_expectation=field.stage_expectation,
            reviews=reviews,
        )

    @staticmethod
    def _conclusions_conflict(candidates: list[FactCandidate]) -> bool:
        conclusions = [item.conclusion.casefold() for item in candidates if item.conclusion]
        if len(conclusions) < 2:
            return False
        date_sets = [
            set(
                re.findall(
                    r"\b(?:20\d{2}-\d{2}-\d{2}|january|february|march|april|may|june|july|"
                    r"august|september|october|november|december)\b",
                    value,
                )
            )
            for value in conclusions
        ]
        material_dates = [value for value in date_sets if value]
        if len(material_dates) >= 2 and len({tuple(sorted(value)) for value in material_dates}) > 1:
            return True
        opposing_pairs = (
            ("approved", "not approved"),
            ("confirmed", "not confirmed"),
            ("has budget", "no budget"),
            ("will proceed", "will not proceed"),
        )
        return any(
            any(positive in value and negative not in value for value in conclusions)
            and any(negative in value for value in conclusions)
            for positive, negative in opposing_pairs
        )

    @staticmethod
    def _unique_sources(sources: list[MethodologySourceReference]) -> list[MethodologySourceReference]:
        values: list[MethodologySourceReference] = []
        seen: set[tuple[str, UUID, str]] = set()
        for source in sources:
            key = (source.source_type, source.source_id, source.item_key)
            if key in seen:
                continue
            seen.add(key)
            values.append(source)
        return values

    @staticmethod
    def _facts_for_category(category: str, statement: str) -> tuple[str, ...]:
        mapping: dict[str, tuple[str, ...]] = {
            "budget": ("budget",),
            "timeline": ("timing", "critical_event"),
            "procurement": ("paper_process", "decision_process"),
            "security_legal": ("paper_process", "decision_criteria"),
            "competitor": ("competition",),
            "commercial_intent": ("need", "pain", "business_pain"),
            "technical_requirement": ("decision_criteria", "situation"),
            "contractual_requirement": ("paper_process", "decision_criteria"),
            "pricing_requirement": ("budget", "decision_criteria"),
            "implementation": ("situation", "decision"),
            "implementation_requirement": ("situation", "decision_criteria"),
            "technical_constraint": ("situation", "decision_criteria"),
            "decision": ("decision",),
            "stakeholder": (),
            "risk": ("pain", "situation"),
            "objection": ("pain",),
            "buying_signal": ("need",),
            "customer_request": ("decision_criteria", "need"),
            "other": ("situation",),
        }
        facts = list(mapping.get(category, ()))
        lowered = statement.casefold()
        if category == "stakeholder":
            if "economic buyer" in lowered or "commercial approv" in lowered:
                facts.extend(("economic_buyer", "authority"))
            if "champion" in lowered:
                facts.append("champion")
        if category == "decision":
            if any(term in lowered for term in ("criteria", "requirement", "evaluate", "compare")):
                facts.append("decision_criteria")
            if any(term in lowered for term in ("process", "approval", "step", "committee")):
                facts.append("decision_process")
        facts.extend(SalesMethodologyProjectionService._facts_for_text(statement))
        return tuple(dict.fromkeys(facts))

    @staticmethod
    def _facts_for_text(value: str) -> tuple[str, ...]:
        lowered = value.casefold()
        terms: tuple[tuple[tuple[str, ...], str], ...] = (
            (("budget", "funding"), "budget"),
            (("economic buyer", "commercial approval", "final approver"), "economic_buyer"),
            (("champion", "internal sponsor"), "champion"),
            (("criteria", "requirements"), "decision_criteria"),
            (("decision process", "approval process", "decision steps"), "decision_process"),
            (("procurement", "contract", "legal process"), "paper_process"),
            (("competitor", "alternative", "status quo"), "competition"),
            (("timeline", "target date", "when"), "timing"),
            (("pain", "problem", "challenge"), "pain"),
            (("impact", "metric", "measurable"), "impact"),
            (("deadline", "critical event"), "critical_event"),
        )
        return tuple(fact for words, fact in terms if any(word in lowered for word in words))

    async def _effective_definition(
        self,
        setting: OrganisationMethodologySetting,
    ) -> EffectiveDefinition:
        if setting.selection in {"meddic", "meddpicc", "bant", "spiced"}:
            content = standard_methodology(cast(StandardMethodologyKey, setting.selection))
            return EffectiveDefinition(
                content=content,
                definition_id=None,
                definition_key=content.key,
                kind="standard",
                created_at=None,
            )
        if setting.selection != "custom" or setting.custom_definition_id is None:
            raise PublicAPIError(
                "methodology_not_configured",
                "The organisation sales methodology is not configured.",
                409,
            )
        record = await self.repository.custom_definition(
            self.tenant.organisation_id,
            setting.custom_definition_id,
        )
        if record is None or record.definition.status != "active":
            raise PublicAPIError(
                "methodology_unavailable",
                "The selected custom methodology is unavailable. Ask an administrator to choose another.",
                409,
            )
        content = self._parse_definition(record.version)
        return EffectiveDefinition(
            content=content,
            definition_id=record.definition.id,
            definition_key=content.key,
            kind="custom",
            created_at=record.definition.created_at,
        )

    async def _require_effective_definition(self) -> EffectiveDefinition:
        setting = await self.repository.setting(self.tenant.organisation_id)
        if setting is None or setting.selection == "none":
            raise PublicAPIError(
                "methodology_not_configured",
                "Select an organisation sales methodology before generating this view.",
                409,
            )
        return await self._effective_definition(setting)

    async def _opportunity(self, opportunity_id: UUID, *, for_update: bool = False) -> Opportunity:
        opportunity = await self.repository.opportunity(
            self.tenant.organisation_id,
            opportunity_id,
            for_update=for_update,
        )
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        return opportunity

    def _projection_response(
        self,
        projection: MethodologyProjection,
        effective: EffectiveDefinition,
        *,
        needs_refresh: bool,
    ) -> OpportunityMethodologyResponse:
        content = self._parse_projection(projection)
        return OpportunityMethodologyResponse(
            state="needs_refresh" if needs_refresh else "current",
            generation_available=True,
            needs_refresh=needs_refresh,
            safe_message=(
                "New or changed evidence is available. Refresh this methodology view before relying on it."
                if needs_refresh
                else "This view uses the current validated evidence available to RevenueOS."
            ),
            definition=self._definition_summary(effective),
            projection_id=projection.id,
            projection=content,
            generated_at=projection.generated_at,
        )

    @staticmethod
    def _parse_projection(projection: MethodologyProjection) -> MethodologyProjectionContent:
        try:
            return MethodologyProjectionContent.model_validate(projection.content_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "methodology_projection_invalid",
                "This methodology view is unavailable. Generate it again from current evidence.",
                409,
            ) from exc

    @staticmethod
    def _parse_definition(version: MethodologyDefinitionVersion) -> MethodologyDefinitionContent:
        try:
            content = MethodologyDefinitionContent.model_validate(version.content_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "methodology_definition_invalid",
                "The custom methodology definition is unavailable.",
                409,
            ) from exc
        if content.standard or content.version != version.version:
            raise PublicAPIError(
                "methodology_definition_invalid",
                "The custom methodology definition is unavailable.",
                409,
            )
        return content

    def _definition_version(
        self,
        definition_id: UUID,
        content: MethodologyDefinitionContent,
        created_at: datetime,
    ) -> MethodologyDefinitionVersion:
        return MethodologyDefinitionVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            definition_id=definition_id,
            version=content.version,
            schema_version=METHODOLOGY_SCHEMA_VERSION,
            content_json=content.as_json(),
            content_fingerprint=self._sha256(content.as_json()),
            created_by_user_id=self.tenant.user_id,
            created_at=created_at,
        )

    @staticmethod
    def _standard_summary(content: MethodologyDefinitionContent) -> MethodologyDefinitionSummary:
        return MethodologyDefinitionSummary(
            id=None,
            key=content.key,
            name=content.name,
            description=content.description,
            version=content.version,
            standard=True,
            status="active",
            field_count=len(content.fields),
            fields=list(content.fields),
            created_at=None,
        )

    def _custom_summary(self, record: CustomDefinitionRecord) -> MethodologyDefinitionSummary:
        content = self._parse_definition(record.version)
        return MethodologyDefinitionSummary(
            id=record.definition.id,
            key=content.key,
            name=content.name,
            description=content.description,
            version=content.version,
            standard=False,
            status=cast(Literal["active", "archived"], record.definition.status),
            field_count=len(content.fields),
            fields=list(content.fields),
            created_at=record.definition.created_at,
        )

    def _definition_summary(self, effective: EffectiveDefinition) -> MethodologyDefinitionSummary:
        if effective.kind == "standard":
            return self._standard_summary(effective.content)
        return MethodologyDefinitionSummary(
            id=effective.definition_id,
            key=effective.content.key,
            name=effective.content.name,
            description=effective.content.description,
            version=effective.content.version,
            standard=False,
            status=effective.status,
            field_count=len(effective.content.fields),
            fields=list(effective.content.fields),
            created_at=effective.created_at,
        )

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)

    def _require_feature(self) -> None:
        if not self.settings.feature_sales_methodology_enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.repository.rollback()
            raise PublicAPIError("persistence_failure", message, 500) from exc

    def _event(
        self,
        event_type: str,
        subject_id: UUID | None,
        metadata: dict[str, object],
    ) -> None:
        self.repository.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=subject_id,
                metadata_json=metadata,
            )
        )

    def _projection_log(
        self,
        projection: MethodologyProjection,
        content: MethodologyProjectionContent | None,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(self.tenant.organisation_id),
            "opportunity_id": str(projection.opportunity_id),
            "projection_id": str(projection.id),
            "methodology_type": projection.methodology_kind,
            "definition_version": projection.definition_version,
            "projection_version": projection.projection_version,
            "state_counts": content.state_counts.model_dump(mode="json") if content is not None else {},
            "provider_used": False,
        }

    @staticmethod
    def _sha256(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @classmethod
    def _parse_datetime(cls, value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return cls._as_utc(parsed)

    @staticmethod
    def _bounded_label(value: str) -> str:
        normalised = " ".join(value.split())
        return normalised[:160] or "Validated evidence"
