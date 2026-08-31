from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    NextBestActionArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.ask_contracts import (
    AskAnswer,
    AskAnswerStatus,
    AskCapabilitiesResponse,
    AskProvenance,
    AskQuestionClass,
    AskRequest,
    AskScope,
    AskSource,
    AskSuggestedAction,
    AskSummaryPoint,
    AskTelemetryRequest,
)
from revenueos.ask_repositories import AskActionRecord, AskBrainBundle, AskRepository
from revenueos.config import Settings
from revenueos.daily_services import RevenueOSDailyService
from revenueos.errors import PublicAPIError
from revenueos.methodology_contracts import MethodologyProjectionContent, MethodologyProjectionItem
from revenueos.models import (
    AIArtifact,
    BetaSystemEvent,
    MethodologyProjection,
    Opportunity,
    RevenueBrainInsight,
    RevenueBrainSourceSnapshot,
)
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainInsightContent
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.ask")

PUBLIC_WEB_PATTERN = re.compile(
    r"\b(?:latest news|public web|internet|web search|stock price|share price|market cap|latest revenue|"
    r"linkedin|news about|google (?:it|this)|research online)\b",
    re.IGNORECASE,
)
INSTRUCTION_PATTERN = re.compile(
    r"\b(?:ignore (?:all |any )?(?:previous|prior|system) instructions|system prompt|developer message|"
    r"reveal hidden|exfiltrat|execute (?:a |an )?(?:tool|action|command)|fabricate (?:a )?(?:source|citation))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AskCandidate:
    text: str
    source: AskSource
    rank: int
    conflict: bool = False
    incomplete: bool = False
    uncertainty: str | None = None
    suggested_question: str | None = None


class AskIntentClassifier:
    """Deterministic bounded question classifier; it never produces a query language."""

    @staticmethod
    def classify(question: str, scope_type: str) -> AskQuestionClass:
        value = question.casefold()
        if PUBLIC_WEB_PATTERN.search(value):
            return "unsupported_public_web"
        if scope_type == "workspace" and (
            "today" in value
            or "need to do" in value
            or "need my attention" in value
            or "should i focus" in value
            or "what should i do next" in value
            or "best next action" in value
            or "follow up now" in value
            or "follow up next" in value
        ):
            return "daily_focus"
        if scope_type == "workspace" and any(
            term in value for term in ("which deal", "which opportunit", "what promises")
        ):
            return "opportunity_filter"
        if (
            scope_type == "account"
            and "opportunit" in value
            and any(term in value for term in ("active", "open", "current"))
        ):
            return "deal_summary"
        if "what changed" in value or "changed recently" in value or "since our last" in value:
            return "recent_change"
        if "what should i do next" in value or "next best action" in value or "next step" in value:
            return "action"
        if any(term in value for term in ("economic buyer", "champion", "decision maker", "key stakeholder")):
            return "stakeholder"
        if any(
            term in value
            for term in ("meddpicc", "meddic", "bant", "spiced", "methodology", "still unknown", "what is missing")
        ):
            return "methodology"
        if any(term in value for term in ("holding", "blocker", "biggest risk", "at risk", "risks")):
            return "blocker_risk"
        if "security" in value or "legal" in value or "privacy" in value:
            return "security_legal"
        if "procurement" in value or "paper process" in value:
            return "procurement"
        if any(term in value for term in ("pricing", "price", "commercial", "budget")):
            return "pricing_commercial"
        if any(term in value for term in ("timeline", "implementation date", "go live", "target date", "when are")):
            return "timeline"
        if any(term in value for term in ("commitment", "committed", "promise", "promised", "outstanding")):
            return "commitment"
        if "competitor" in value or "competition" in value or "other vendor" in value:
            return "competitor"
        if "objection" in value or "pushback" in value or "concern" in value:
            return "objection"
        if "buying signal" in value or "momentum" in value or "intent" in value:
            return "buying_signal"
        if "decision" in value or "agreed" in value or "approve" in value:
            return "decision"
        if "customer request" in value or "asked for" in value or "requested" in value:
            return "customer_request"
        if any(term in value for term in ("evidence", "source", "what did they say", "customer say", "customer said")):
            return "evidence_lookup"
        if any(term in value for term in ("summary", "summarise", "everything we know", "what is happening")):
            return "deal_summary"
        return "general_sales_question"


class AskRevenueOSService:
    """Evidence-first, deterministic Ask v1 with no retained conversation content."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = AskRepository(session)

    async def capabilities(self, scope_type: str, scope_id: UUID | None) -> AskCapabilitiesResponse:
        self._require_enabled()
        scope, _ = await self._resolve_scope(scope_type, scope_id)
        return AskCapabilitiesResponse(
            enabled=True,
            scope=scope,
            supported_scopes=("opportunity", "account", "workspace"),
            max_sources=self.settings.private_beta_ask_max_sources,
            safe_message=(
                "Ask answers from authorised RevenueOS evidence. It does not search the public web or perform actions."
            ),
        )

    async def answer(self, request: AskRequest) -> AskAnswer:
        self._require_enabled()
        started_at = time.perf_counter()
        request_id = uuid.uuid4()
        generated_at = datetime.now(UTC)
        scope, opportunities = await self._resolve_scope(request.scope_type, request.scope_id)
        question_class = AskIntentClassifier.classify(request.question, request.scope_type)

        if INSTRUCTION_PATTERN.search(request.question):
            answer = self._unknown_answer(
                request_id,
                generated_at,
                scope,
                question_class,
                "RevenueOS can only answer bounded sales questions from authorised evidence. Instructions to change its rules, reveal hidden data or execute actions are ignored.",
            )
        elif question_class == "unsupported_public_web":
            answer = self._unknown_answer(
                request_id,
                generated_at,
                scope,
                question_class,
                "I don’t have that information in RevenueOS. Ask RevenueOS does not research the public web yet.",
            )
        elif question_class == "daily_focus":
            answer = await self._daily_answer(request_id, generated_at, scope, request.timezone)
        elif request.scope_type == "workspace":
            answer = await self._portfolio_answer(
                request_id,
                generated_at,
                scope,
                opportunities,
                request.question,
                question_class,
            )
        else:
            answer = await self._scoped_answer(
                request_id,
                generated_at,
                scope,
                opportunities,
                request.question,
                question_class,
            )

        latency_ms = max(0, round((time.perf_counter() - started_at) * 1_000))
        await self._reserve_and_audit(answer, latency_ms)
        logger.info(
            "ask_answer_generated",
            extra={
                "ask_request_id": str(answer.ask_request_id),
                "organisation_id": str(self.tenant.organisation_id),
                "user_id": str(self.tenant.user_id),
                "scope_type": answer.scope.type,
                "question_class": answer.question_class,
                "answer_status": answer.answer_status,
                "source_count": len(answer.sources),
                "latency_ms": latency_ms,
            },
        )
        return answer

    async def record_telemetry(self, request: AskTelemetryRequest) -> None:
        self._require_enabled()
        if not await self.repository.active_membership(self.tenant.organisation_id, self.tenant.user_id):
            raise PublicAPIError("forbidden", "You do not have permission to use Ask RevenueOS.", 403)
        if not await self.repository.ask_event_exists(
            self.tenant.organisation_id,
            self.tenant.user_id,
            request.ask_request_id,
        ):
            raise PublicAPIError("ask_request_not_found", "The Ask RevenueOS request was not found.", 404)
        event_type = "ask_source_opened" if request.event_type == "source_opened" else "ask_follow_up_selected"
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=request.ask_request_id,
                metadata_json=(
                    {"sourceId": str(request.source_id)}
                    if request.source_id is not None
                    else {"selection": "bounded_follow_up"}
                ),
            )
        )
        await self.session.commit()

    def _require_enabled(self) -> None:
        if not self.settings.feature_ask_revenueos_enabled:
            raise PublicAPIError(
                "feature_unavailable",
                "Ask RevenueOS is not enabled for this private-beta workspace.",
                404,
            )

    async def _resolve_scope(
        self,
        scope_type: str,
        scope_id: UUID | None,
    ) -> tuple[AskScope, list[Opportunity]]:
        if not await self.repository.active_membership(self.tenant.organisation_id, self.tenant.user_id):
            raise PublicAPIError("forbidden", "You do not have permission to use Ask RevenueOS.", 403)
        if scope_type == "opportunity":
            if scope_id is None:
                raise PublicAPIError("invalid_ask_scope", "Opportunity scope requires an opportunity ID.", 422)
            opportunity = await self.repository.opportunity(self.tenant.organisation_id, scope_id)
            if opportunity is None:
                raise PublicAPIError("opportunity_not_found", "The opportunity was not found.", 404)
            return AskScope(type="opportunity", id=opportunity.id, label=opportunity.name), [opportunity]
        if scope_type == "account":
            if scope_id is None:
                raise PublicAPIError("invalid_ask_scope", "Account scope requires an account ID.", 422)
            company = await self.repository.company(self.tenant.organisation_id, scope_id)
            if company is None:
                raise PublicAPIError("account_not_found", "The account was not found.", 404)
            opportunities = await self.repository.opportunities_for_company(
                self.tenant.organisation_id,
                company.id,
            )
            return AskScope(type="account", id=company.id, label=company.name), opportunities
        if scope_id is not None:
            raise PublicAPIError("invalid_ask_scope", "Workspace scope cannot include an entity ID.", 422)
        opportunities = await self.repository.owned_open_opportunities(
            self.tenant.organisation_id,
            self.tenant.user_id,
        )
        return AskScope(type="workspace", id=None, label="Your accessible sales work"), opportunities

    async def _scoped_answer(
        self,
        request_id: UUID,
        generated_at: datetime,
        scope: AskScope,
        opportunities: list[Opportunity],
        question: str,
        question_class: AskQuestionClass,
    ) -> AskAnswer:
        opportunity_ids = tuple(item.id for item in opportunities)
        bundles = await self.repository.latest_brain_bundles(
            self.tenant.organisation_id,
            opportunity_ids,
            limit=min(20, max(1, len(opportunity_ids))),
        )
        methodologies = (
            await self.repository.latest_methodology(self.tenant.organisation_id, opportunity_ids)
            if self.settings.feature_sales_methodology_enabled
            else []
        )
        insights = (
            await self.repository.latest_brain_insights(self.tenant.organisation_id, opportunity_ids)
            if self.settings.feature_revenue_brain_enabled
            else []
        )
        evidence = await self.repository.accepted_source_snapshots(
            self.tenant.organisation_id,
            opportunity_ids=opportunity_ids if scope.type == "opportunity" else (),
            company_id=scope.id if scope.type == "account" else None,
            limit=20,
        )
        actions = (
            await self.repository.current_actions(self.tenant.organisation_id, opportunity_ids)
            if self.settings.feature_action_layer_enabled
            else []
        )
        names = {item.id: item.name for item in opportunities}
        candidates: list[AskCandidate] = []
        if scope.type == "account" and question_class == "deal_summary":
            candidates.extend(self._opportunity_candidates(opportunities))
        candidates.extend(self._methodology_candidates(methodologies, names, question, question_class))
        candidates.extend(self._insight_candidates(insights, names, question_class))
        candidates.extend(self._evidence_candidates(evidence, names, question, question_class, scope))
        candidates.extend(self._artifact_candidates(bundles, names, question, question_class))
        candidates.extend(self._action_candidates(actions, names, question_class))
        candidates = self._bound_candidates(candidates)
        return self._compose(request_id, generated_at, scope, question_class, candidates)

    async def _portfolio_answer(
        self,
        request_id: UUID,
        generated_at: datetime,
        scope: AskScope,
        opportunities: list[Opportunity],
        question: str,
        question_class: AskQuestionClass,
    ) -> AskAnswer:
        if not opportunities:
            return self._unknown_answer(
                request_id,
                generated_at,
                scope,
                question_class,
                "I don’t have any open opportunities assigned to you to answer that from.",
            )
        lowered = question.casefold()
        if "need" in lowered and "attention" in lowered:
            return await self._daily_answer(request_id, generated_at, scope, None)
        opportunity_ids = tuple(item.id for item in opportunities)
        names = {item.id: item.name for item in opportunities}
        candidates: list[AskCandidate] = []
        if any(term in lowered for term in ("economic buyer", "methodology", "meddpicc", "meddic")):
            methodologies = await self.repository.latest_methodology(self.tenant.organisation_id, opportunity_ids)
            candidates = self._portfolio_methodology_gaps(methodologies, names, lowered)
        elif any(term in lowered for term in ("security", "competitor", "timeline", "risk")):
            bundles = await self.repository.latest_brain_bundles(
                self.tenant.organisation_id,
                opportunity_ids,
                limit=20,
            )
            evidence = await self.repository.accepted_source_snapshots(
                self.tenant.organisation_id,
                opportunity_ids=opportunity_ids,
                limit=20,
            )
            mapped_class: AskQuestionClass
            if "security" in lowered:
                mapped_class = "security_legal"
            elif "competitor" in lowered:
                mapped_class = "competitor"
            elif "timeline" in lowered:
                mapped_class = "timeline"
            else:
                mapped_class = "blocker_risk"
            candidates.extend(self._evidence_candidates(evidence, names, question, mapped_class, scope))
            candidates.extend(self._artifact_candidates(bundles, names, question, mapped_class))
        elif any(term in lowered for term in ("commitment", "promise", "overdue")):
            actions = await self.repository.current_actions(self.tenant.organisation_id, opportunity_ids)
            candidates = self._action_candidates(actions, names, "commitment")
            candidates = [
                item
                for item in candidates
                if item.source.occurred_at is None or item.source.occurred_at <= datetime.now(UTC)
            ]
        elif question_class == "opportunity_filter":
            candidates = self._opportunity_candidates(opportunities)
        else:
            return self._unknown_answer(
                request_id,
                generated_at,
                scope,
                question_class,
                "I can answer bounded portfolio questions about methodology gaps, risks, security, competitors, commitments and today’s priorities. I can’t run arbitrary business-intelligence queries.",
            )
        candidates = self._bound_candidates(candidates, self.settings.private_beta_ask_max_portfolio_results)
        return self._compose(request_id, generated_at, scope, "opportunity_filter", candidates)

    async def _daily_answer(
        self,
        request_id: UUID,
        generated_at: datetime,
        scope: AskScope,
        timezone: str | None,
    ) -> AskAnswer:
        daily = await RevenueOSDailyService(self.session, self.tenant, self.settings).read(timezone)
        if daily.top_priority is None:
            return self._unknown_answer(
                request_id,
                generated_at,
                scope,
                "daily_focus",
                "You’re caught up based on the current RevenueOS Daily view. No supported priority needs your attention right now.",
            )
        priority = daily.top_priority
        source = AskSource(
            id=priority.source_id,
            source_type="daily",
            label=f"RevenueOS Daily · {daily.local_date.isoformat()}",
            occurred_at=priority.starts_at or priority.due_at or daily.generated_at,
            excerpt=self._short(priority.reason),
            provenance="validated_intelligence",
            href=priority.href,
        )
        point = AskSummaryPoint(
            text=self._short(f"{priority.title}: {priority.reason}"),
            source_ids=(source.id,),
        )
        return AskAnswer(
            ask_request_id=request_id,
            answer=f"Start with {priority.title}. {priority.reason}",
            answer_status="supported",
            question_class="daily_focus",
            summary_points=(point,),
            sources=(source,),
            uncertainties=(),
            suggested_action=AskSuggestedAction(
                label=priority.cta_label,
                href=priority.href,
                source_id=source.id,
            ),
            follow_up_questions=("Which deals need my attention?",),
            scope=scope,
            generated_at=generated_at,
        )

    def _methodology_candidates(
        self,
        projections: list[MethodologyProjection],
        names: dict[UUID, str],
        question: str,
        question_class: AskQuestionClass,
    ) -> list[AskCandidate]:
        candidates: list[AskCandidate] = []
        lowered = question.casefold()
        for projection in projections:
            try:
                content = MethodologyProjectionContent.model_validate(projection.content_json)
            except ValidationError:
                continue
            items = list(content.items)
            selected = self._select_methodology_items(items, lowered, question_class)
            for item in selected[:6]:
                state_label = item.state.replace("_", " ")
                conclusion = item.conclusion or "RevenueOS does not have a reliable conclusion."
                prefix = f"{names.get(projection.opportunity_id, 'Opportunity')} · " if len(names) > 1 else ""
                text = self._short(f"{prefix}{item.display_name}: {conclusion} ({state_label}).")
                excerpt = self._short(item.conclusion or f"{item.display_name} is {state_label}.")
                source = AskSource(
                    id=projection.id,
                    source_type="methodology",
                    label=f"{content.methodology_name} · {item.display_name}",
                    occurred_at=content.generated_at,
                    excerpt=excerpt,
                    provenance="validated_intelligence",
                    href=f"/opportunities/{projection.opportunity_id}#deal-methodology",
                )
                candidates.append(
                    AskCandidate(
                        text=text,
                        source=source,
                        rank=0 if item.state == "conflicting" else 2,
                        conflict=item.state == "conflicting",
                        incomplete=item.state in {"unknown", "partially_supported", "stale"},
                        uncertainty=(
                            f"{item.display_name} is {state_label}; RevenueOS has not treated it as confirmed."
                            if item.state != "confirmed"
                            else None
                        ),
                        suggested_question=item.suggested_question,
                    )
                )
        return candidates

    def _opportunity_candidates(self, opportunities: list[Opportunity]) -> list[AskCandidate]:
        candidates: list[AskCandidate] = []
        for opportunity in opportunities:
            if opportunity.status not in {"open", "on_hold"}:
                continue
            close = (
                f" Expected close {opportunity.expected_close_date.isoformat()}."
                if opportunity.expected_close_date
                else " No expected close date is recorded."
            )
            source = AskSource(
                id=opportunity.id,
                source_type="opportunity",
                label=f"Opportunity · {opportunity.name}",
                occurred_at=opportunity.updated_at,
                excerpt=self._short(f"{opportunity.stage.replace('_', ' ')} · {opportunity.status.replace('_', ' ')}."),
                provenance="system_metadata",
                href=f"/opportunities/{opportunity.id}",
            )
            candidates.append(
                AskCandidate(
                    text=self._short(
                        f"{opportunity.name} is {opportunity.status.replace('_', ' ')} in "
                        f"{opportunity.stage.replace('_', ' ')}.{close}"
                    ),
                    source=source,
                    rank=1 if opportunity.status == "open" else 4,
                    incomplete=opportunity.status == "on_hold",
                )
            )
        return candidates

    @staticmethod
    def _select_methodology_items(
        items: list[MethodologyProjectionItem],
        lowered: str,
        question_class: AskQuestionClass,
    ) -> list[MethodologyProjectionItem]:
        terms: tuple[str, ...] = ()
        if "economic buyer" in lowered:
            terms = ("economic_buyer",)
        elif "champion" in lowered:
            terms = ("champion",)
        elif question_class == "timeline":
            terms = ("timing", "critical_event")
        elif question_class == "procurement":
            terms = ("paper_process", "decision_process")
        elif question_class == "pricing_commercial":
            terms = ("budget", "quantified_business_impact")
        elif question_class == "competitor":
            terms = ("competition",)
        if terms:
            return [item for item in items if item.field_key in terms]
        if question_class in {"methodology", "stakeholder"}:
            unresolved = [item for item in items if item.state != "confirmed"]
            return sorted(
                unresolved,
                key=lambda item: (
                    {"conflicting": 0, "stale": 1, "unknown": 2, "partially_supported": 3}.get(item.state, 4),
                    not item.required,
                    item.field_key,
                ),
            )
        return []

    def _portfolio_methodology_gaps(
        self,
        projections: list[MethodologyProjection],
        names: dict[UUID, str],
        lowered: str,
    ) -> list[AskCandidate]:
        candidates = self._methodology_candidates(projections, names, lowered, "methodology")
        if "economic buyer" in lowered:
            candidates = [item for item in candidates if "economic buyer" in item.source.label.casefold()]
        return [item for item in candidates if item.incomplete or item.conflict]

    def _insight_candidates(
        self,
        insights: list[RevenueBrainInsight],
        names: dict[UUID, str],
        question_class: AskQuestionClass,
    ) -> list[AskCandidate]:
        if question_class not in {"recent_change", "deal_summary", "blocker_risk", "security_legal", "timeline"}:
            return []
        candidates: list[AskCandidate] = []
        for insight in insights:
            try:
                content = RevenueBrainInsightContent.model_validate(insight.content_json)
            except ValidationError:
                continue
            source = AskSource(
                id=insight.id,
                source_type="revenue_brain",
                label=f"Revenue Brain changes · {content.to_meeting_date.isoformat()}",
                occurred_at=insight.created_at,
                excerpt=self._short(content.summary),
                provenance="validated_intelligence",
                href=f"/opportunities/{insight.opportunity_id}#longitudinal-changes",
            )
            for change in content.changes[:6]:
                if question_class == "security_legal" and "security" not in change.change_type:
                    continue
                if question_class == "timeline" and "timeline" not in change.change_type:
                    continue
                if question_class == "blocker_risk" and not any(
                    term in change.change_type for term in ("risk", "blocker", "objection", "security", "unclear")
                ):
                    continue
                insight_name = names.get(insight.opportunity_id) if insight.opportunity_id is not None else None
                prefix = f"{insight_name or 'Opportunity'} · " if len(names) > 1 else ""
                candidates.append(
                    AskCandidate(
                        text=self._short(f"{prefix}{change.title}: {change.description}"),
                        source=source,
                        rank=1 if change.importance == "high" else 4,
                        conflict=change.direction == "unclear",
                        incomplete=change.direction == "unclear",
                    )
                )
        return candidates

    def _evidence_candidates(
        self,
        snapshots: list[RevenueBrainSourceSnapshot],
        names: dict[UUID, str],
        question: str,
        question_class: AskQuestionClass,
        scope: AskScope,
    ) -> list[AskCandidate]:
        category_map: dict[AskQuestionClass, set[str]] = {
            "blocker_risk": {"risk", "objection", "open_question"},
            "timeline": {"timeline", "implementation"},
            "commitment": {"commitment", "action_item"},
            "buying_signal": {"buying_signal", "commercial_intent", "expansion_signal", "renewal_signal"},
            "objection": {"objection"},
            "competitor": {"competitor"},
            "decision": {"decision"},
            "customer_request": {"customer_request", "technical_requirement", "contractual_requirement"},
            "security_legal": {"security_legal", "technical_requirement", "risk"},
            "procurement": {"procurement", "contractual_requirement"},
            "pricing_commercial": {"pricing_requirement", "budget", "commercial_intent"},
            "evidence_lookup": set(),
            "deal_summary": set(),
        }
        allowed = category_map.get(question_class)
        if allowed is None:
            return []
        lowered = question.casefold()
        customer_specific = "customer say" in lowered or "they say" in lowered or "customer said" in lowered
        candidates: list[AskCandidate] = []
        for snapshot in snapshots:
            content = snapshot.content_json
            if not isinstance(content, dict):
                continue
            source_label = content.get("sourceLabel")
            source_type = content.get("sourceType")
            occurred_at = self._datetime(content.get("occurredAt")) or snapshot.created_at
            items = content.get("items")
            if not isinstance(source_label, str) or not isinstance(source_type, str) or not isinstance(items, list):
                continue
            opportunity_id = snapshot.opportunity_id
            for item in items:
                if not isinstance(item, dict):
                    continue
                category = item.get("category")
                statement = item.get("statement")
                evidence_id = self._uuid(item.get("evidenceId"))
                origin = item.get("originClass")
                conflict_state = item.get("conflictState", "not_assessed")
                if not isinstance(category, str) or not isinstance(statement, str) or evidence_id is None:
                    continue
                if allowed and category not in allowed:
                    continue
                if customer_specific and origin != "customer_direct":
                    continue
                if question_class == "competitor":
                    target = self._competitor_target(lowered)
                    if target and target not in statement.casefold():
                        continue
                provenance = self._provenance(origin)
                href = (
                    f"/opportunities/{opportunity_id}#customer-evidence"
                    if opportunity_id is not None
                    else f"/companies/{scope.id}"
                )
                source = AskSource(
                    id=evidence_id,
                    source_type="accepted_evidence",
                    label=self._short(source_label),
                    occurred_at=occurred_at,
                    excerpt=self._short(statement),
                    provenance=provenance,
                    href=href,
                )
                opportunity_name = names.get(opportunity_id) if opportunity_id is not None else None
                prefix = f"{opportunity_name or 'Account'} · " if len(names) > 1 else ""
                provenance_label = {
                    "salesperson_reported": "Reported by the salesperson",
                    "seller_prepared": "Seller-prepared context",
                    "customer_direct": "Customer-direct evidence",
                    "imported_external": "Imported evidence",
                }.get(provenance, "Evidence")
                candidates.append(
                    AskCandidate(
                        text=self._short(f"{prefix}{statement} — {provenance_label}."),
                        source=source,
                        rank=0 if provenance == "customer_direct" else 3,
                        conflict=conflict_state == "conflicting",
                        incomplete=provenance in {"salesperson_reported", "seller_prepared"},
                        uncertainty=(
                            "This is seller-side or reported context, not customer-direct confirmation."
                            if provenance in {"salesperson_reported", "seller_prepared"}
                            else None
                        ),
                    )
                )
        return candidates

    def _artifact_candidates(
        self,
        bundles: list[AskBrainBundle],
        names: dict[UUID, str],
        question: str,
        question_class: AskQuestionClass,
    ) -> list[AskCandidate]:
        candidates: list[AskCandidate] = []
        lowered = question.casefold()
        for bundle in bundles:
            prefix = f"{names.get(bundle.opportunity_id, 'Opportunity')} · " if len(names) > 1 else ""
            if question_class in {"deal_summary"}:
                artifact = bundle.artifacts["executive_summary"]
                try:
                    summary_content = ExecutiveSummaryArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    candidates.append(
                        self._artifact_candidate(bundle, artifact, prefix + summary_content.executive_summary, 2)
                    )
            if question_class in {
                "blocker_risk",
                "security_legal",
                "procurement",
                "pricing_commercial",
                "deal_summary",
            }:
                artifact = bundle.artifacts["risks_blockers"]
                try:
                    risk_content = RisksBlockersArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    for risk in risk_content.risks:
                        if not self._category_matches(risk.category, question_class):
                            continue
                        candidates.append(
                            self._artifact_candidate(
                                bundle,
                                artifact,
                                f"{prefix}{risk.risk} ({risk.severity} risk).",
                                0 if risk.severity == "high" else 3,
                                excerpt=risk.evidence,
                            )
                        )
            if question_class in {
                "objection",
                "competitor",
                "security_legal",
                "procurement",
                "pricing_commercial",
                "deal_summary",
            }:
                artifact = bundle.artifacts["objections_competitive_signals"]
                try:
                    objection_content = ObjectionsCompetitiveSignalsArtifactContent.model_validate(
                        artifact.content_json
                    )
                except ValidationError:
                    pass
                else:
                    if question_class == "competitor":
                        target = self._competitor_target(lowered)
                        for competitor in objection_content.competitors:
                            if target and target not in competitor.name.casefold():
                                continue
                            candidates.append(
                                self._artifact_candidate(
                                    bundle,
                                    artifact,
                                    f"{prefix}{competitor.name} was mentioned; its position is {competitor.position}.",
                                    1,
                                    excerpt=competitor.evidence,
                                )
                            )
                    else:
                        for objection in objection_content.objections:
                            if not self._category_matches(objection.category, question_class):
                                continue
                            candidates.append(
                                self._artifact_candidate(
                                    bundle,
                                    artifact,
                                    f"{prefix}{objection.objection} ({objection.status}).",
                                    1 if objection.status == "unresolved" else 4,
                                    excerpt=objection.evidence,
                                )
                            )
            if question_class in {"stakeholder", "deal_summary"}:
                artifact = bundle.artifacts["stakeholder_intelligence"]
                try:
                    stakeholder_content = StakeholderIntelligenceArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    role_target = (
                        "economic_buyer"
                        if "economic buyer" in lowered
                        else "champion"
                        if "champion" in lowered
                        else None
                    )
                    for stakeholder in stakeholder_content.stakeholders:
                        if role_target and stakeholder.role != role_target:
                            continue
                        candidates.append(
                            self._artifact_candidate(
                                bundle,
                                artifact,
                                f"{prefix}{stakeholder.name} is currently classified as {stakeholder.role.replace('_', ' ')} with {stakeholder.influence} influence.",
                                1,
                                excerpt=stakeholder.evidence,
                            )
                        )
                    if role_target and not any(
                        stakeholder.role == role_target for stakeholder in stakeholder_content.stakeholders
                    ):
                        coverage = getattr(stakeholder_content.role_coverage, role_target)
                        candidates.append(
                            AskCandidate(
                                text=self._short(
                                    f"{prefix}{role_target.replace('_', ' ').title()} is {coverage.replace('_', ' ')}."
                                ),
                                source=self._artifact_source(
                                    bundle,
                                    artifact,
                                    stakeholder_content.stakeholder_summary,
                                ),
                                rank=1,
                                incomplete=True,
                                uncertainty=f"The {role_target.replace('_', ' ')} is not reliably identified.",
                            )
                        )
            if question_class in {"commitment"}:
                artifact = bundle.artifacts["action_items"]
                try:
                    action_content = ActionItemsArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    for action_item in action_content.action_items:
                        due = f" due {action_item.due_date}" if action_item.due_date else ""
                        owner = f" owned by {action_item.owner}" if action_item.owner else " with no confirmed owner"
                        candidates.append(
                            self._artifact_candidate(
                                bundle,
                                artifact,
                                f"{prefix}{action_item.task}{owner}{due}.",
                                2,
                                excerpt=action_item.evidence,
                            )
                        )
            if question_class == "decision":
                artifact = bundle.artifacts["decisions"]
                try:
                    decision_content = DecisionsArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    for decision in decision_content.decisions:
                        candidates.append(
                            self._artifact_candidate(
                                bundle,
                                artifact,
                                f"{prefix}{decision.decision} ({decision.status}).",
                                2,
                                excerpt=decision.evidence,
                            )
                        )
            if question_class == "buying_signal":
                artifact = bundle.artifacts["buying_signals"]
                try:
                    signal_content = BuyingSignalsArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    for signal in signal_content.signals:
                        candidates.append(
                            self._artifact_candidate(
                                bundle,
                                artifact,
                                f"{prefix}{signal.signal_type.replace('_', ' ')} is a {signal.strength} {signal.polarity} signal.",
                                2,
                                excerpt=signal.evidence,
                            )
                        )
            if question_class == "action":
                artifact = bundle.artifacts["next_best_action"]
                try:
                    next_action_content = NextBestActionArtifactContent.model_validate(artifact.content_json)
                except ValidationError:
                    pass
                else:
                    candidates.append(
                        self._artifact_candidate(
                            bundle,
                            artifact,
                            prefix + next_action_content.overall_recommendation,
                            0,
                            excerpt=next_action_content.reasoning[0],
                        )
                    )
            if question_class == "evidence_lookup":
                for artifact_type in ("risks_blockers", "stakeholder_intelligence", "decisions"):
                    artifact = bundle.artifacts[artifact_type]
                    candidates.append(
                        self._artifact_candidate(
                            bundle,
                            artifact,
                            f"{prefix}{artifact_type.replace('_', ' ').title()} is available from the latest completed interaction.",
                            5,
                        )
                    )
        return candidates

    def _artifact_candidate(
        self,
        bundle: AskBrainBundle,
        artifact: AIArtifact,
        text: str,
        rank: int,
        *,
        excerpt: str | None = None,
    ) -> AskCandidate:
        return AskCandidate(
            text=self._short(text),
            source=self._artifact_source(bundle, artifact, excerpt or text),
            rank=rank,
        )

    def _artifact_source(self, bundle: AskBrainBundle, artifact: AIArtifact, excerpt: str) -> AskSource:
        artifact_id = artifact.id
        artifact_type = artifact.artifact_type
        return AskSource(
            id=artifact_id,
            source_type="interaction",
            label=f"{bundle.meeting.title} · {artifact_type.replace('_', ' ').title()}",
            occurred_at=bundle.meeting.meeting_date,
            excerpt=self._short(excerpt),
            provenance="validated_intelligence",
            href=f"/meetings/{bundle.meeting.id}",
        )

    def _action_candidates(
        self,
        actions: list[AskActionRecord],
        names: dict[UUID, str],
        question_class: AskQuestionClass,
    ) -> list[AskCandidate]:
        if question_class not in {"action", "commitment", "deal_summary"}:
            return []
        candidates: list[AskCandidate] = []
        for item in actions:
            if item.proposal.opportunity_id is None:
                continue
            prefix = f"{names.get(item.proposal.opportunity_id, 'Opportunity')} · " if len(names) > 1 else ""
            due = f" Due {item.version.proposed_due_at.date().isoformat()}." if item.version.proposed_due_at else ""
            source = AskSource(
                id=item.proposal.id,
                source_type="action",
                label=f"Action · {item.version.title}",
                occurred_at=item.version.proposed_due_at or item.proposal.generated_at,
                excerpt=self._short(item.version.provenance_summary),
                provenance="validated_intelligence",
                href=f"/opportunities/{item.proposal.opportunity_id}#recommended-actions",
            )
            candidates.append(
                AskCandidate(
                    text=self._short(
                        f"{prefix}{item.version.title}.{due} Status: {item.proposal.status.replace('_', ' ')}."
                    ),
                    source=source,
                    rank=1 if item.proposal.priority == "high" else 4,
                    incomplete=item.proposal.status != "approved",
                )
            )
        return candidates

    def _compose(
        self,
        request_id: UUID,
        generated_at: datetime,
        scope: AskScope,
        question_class: AskQuestionClass,
        candidates: list[AskCandidate],
    ) -> AskAnswer:
        if not candidates:
            return self._unknown_answer(
                request_id,
                generated_at,
                scope,
                question_class,
                self._unknown_message(question_class),
            )
        selected = candidates[: min(6, self.settings.private_beta_ask_max_sources)]
        source_map: dict[UUID, AskSource] = {}
        points: list[AskSummaryPoint] = []
        uncertainties: list[str] = []
        follow_ups: list[str] = []
        for candidate in selected:
            source_map[candidate.source.id] = candidate.source
            points.append(AskSummaryPoint(text=candidate.text, source_ids=(candidate.source.id,)))
            if candidate.uncertainty and candidate.uncertainty not in uncertainties:
                uncertainties.append(candidate.uncertainty)
            if candidate.suggested_question and candidate.suggested_question not in follow_ups:
                follow_ups.append(candidate.suggested_question)
        status: AskAnswerStatus
        if any(item.conflict for item in selected):
            status = "conflicting"
        elif all(item.incomplete for item in selected):
            status = "partially_supported"
        elif any(item.incomplete for item in selected):
            status = "partially_supported"
        else:
            status = "supported"
        answer = self._answer_lead(question_class, status, selected)
        suggested = self._suggested_action(question_class, selected)
        if not follow_ups:
            follow_ups = self._default_follow_ups(question_class)
        return AskAnswer(
            ask_request_id=request_id,
            answer=answer,
            answer_status=status,
            question_class=question_class,
            summary_points=tuple(points),
            sources=tuple(source_map.values()),
            uncertainties=tuple(uncertainties[:6]),
            suggested_action=suggested,
            follow_up_questions=tuple(follow_ups[:4]),
            scope=scope,
            generated_at=generated_at,
        )

    def _unknown_answer(
        self,
        request_id: UUID,
        generated_at: datetime,
        scope: AskScope,
        question_class: AskQuestionClass,
        message: str,
    ) -> AskAnswer:
        return AskAnswer(
            ask_request_id=request_id,
            answer=message,
            answer_status="unknown",
            question_class=question_class,
            summary_points=(),
            sources=(),
            uncertainties=("RevenueOS will not fill evidence gaps with assumptions.",),
            suggested_action=None,
            follow_up_questions=tuple(self._default_follow_ups(question_class)[:4]),
            scope=scope,
            generated_at=generated_at,
        )

    async def _reserve_and_audit(self, answer: AskAnswer, latency_ms: int) -> None:
        context_characters = sum(len(point.text) for point in answer.summary_points) + sum(
            len(source.excerpt or "") for source in answer.sources
        )
        event = BetaSystemEvent(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            actor_user_id=self.tenant.user_id,
            event_type="ask_answer_generated",
            subject_id=answer.ask_request_id,
            metadata_json={
                "scopeType": answer.scope.type,
                "scopeId": str(answer.scope.id) if answer.scope.id else None,
                "questionClass": answer.question_class,
                "sourceCount": len(answer.sources),
                "answerStatus": answer.answer_status,
                "retrievalStrategy": "bounded_structured_v1",
                "composer": "deterministic_v1",
                "contextCharacters": context_characters,
                "latencyMs": latency_ms,
            },
        )
        quota = await self.repository.reserve_quota_and_audit(
            self.tenant.organisation_id,
            self.tenant.user_id,
            event,
            user_limit=self.settings.private_beta_max_ask_questions_per_user_per_day,
            organisation_limit=self.settings.private_beta_max_ask_questions_per_organisation_per_day,
        )
        if quota != "ok":
            await self.session.rollback()
            if quota == "user_limit":
                raise PublicAPIError(
                    "ask_user_daily_limit_exceeded",
                    "You have reached today’s Ask RevenueOS limit. Try again tomorrow.",
                    429,
                )
            raise PublicAPIError(
                "ask_organisation_daily_limit_exceeded",
                "This workspace has reached today’s Ask RevenueOS limit. Try again tomorrow or contact an administrator.",
                429,
            )
        await self.session.commit()

    def _bound_candidates(self, candidates: list[AskCandidate], limit: int | None = None) -> list[AskCandidate]:
        candidates.sort(
            key=lambda item: (
                item.rank,
                -(item.source.occurred_at or datetime(1970, 1, 1, tzinfo=UTC)).timestamp(),
                str(item.source.id),
            )
        )
        result: list[AskCandidate] = []
        characters = 0
        seen: set[tuple[str, UUID]] = set()
        maximum = min(limit or self.settings.private_beta_ask_max_sources, self.settings.private_beta_ask_max_sources)
        for item in candidates:
            if INSTRUCTION_PATTERN.search(item.text) or (
                item.source.excerpt is not None and INSTRUCTION_PATTERN.search(item.source.excerpt)
            ):
                continue
            key = (item.text.casefold(), item.source.id)
            next_characters = characters + len(item.text) + len(item.source.excerpt or "")
            if key in seen or next_characters > self.settings.private_beta_ask_max_context_characters:
                continue
            result.append(item)
            seen.add(key)
            characters = next_characters
            if len(result) >= maximum:
                break
        return result

    @staticmethod
    def _category_matches(category: str, question_class: AskQuestionClass) -> bool:
        if question_class in {"deal_summary", "blocker_risk", "objection"}:
            return True
        if question_class == "security_legal":
            return category in {"security", "legal", "privacy", "technical"}
        if question_class == "procurement":
            return category in {"procurement", "legal", "commercial"}
        if question_class == "pricing_commercial":
            return category in {"pricing", "budget", "commercial"}
        return False

    @staticmethod
    def _answer_lead(
        question_class: AskQuestionClass,
        status: AskAnswerStatus,
        candidates: list[AskCandidate],
    ) -> str:
        first = candidates[0].text
        if status == "conflicting":
            return f"RevenueOS found material disagreement in the current evidence. {first} Review the cited sources before relying on this conclusion."
        if question_class == "opportunity_filter":
            return f"RevenueOS found {len(candidates)} relevant {'opportunity' if len(candidates) == 1 else 'opportunities'} in your accessible work. {first}"
        if status == "partially_supported":
            return f"The available evidence gives a partial answer. {first}"
        return first

    @staticmethod
    def _suggested_action(
        question_class: AskQuestionClass,
        candidates: list[AskCandidate],
    ) -> AskSuggestedAction | None:
        if not candidates:
            return None
        source = candidates[0].source
        if question_class == "action" and source.source_type in {"interaction", "action"}:
            return AskSuggestedAction(label="Review the current next action", href=source.href, source_id=source.id)
        return AskSuggestedAction(label="View the supporting evidence", href=source.href, source_id=source.id)

    @staticmethod
    def _unknown_message(question_class: AskQuestionClass) -> str:
        if question_class == "action":
            return "I don’t have a current Next Best Action or supported fallback for this scope."
        if question_class == "stakeholder":
            return "I don’t have enough reliable evidence to identify that stakeholder yet."
        if question_class == "recent_change":
            return "I don’t have enough eligible Revenue Brain history to explain what changed yet."
        if question_class == "general_sales_question":
            return "I can answer bounded questions about deals, stakeholders, methodology, risks, commitments, actions and accepted customer evidence. I don’t have enough reliable evidence to answer that question as asked."
        return "I don’t have enough reliable evidence to answer that yet."

    @staticmethod
    def _default_follow_ups(question_class: AskQuestionClass) -> list[str]:
        if question_class in {"stakeholder", "methodology"}:
            return ["What is still unknown?", "Show me the evidence."]
        if question_class == "recent_change":
            return ["What are the biggest risks?", "What should I do next?"]
        if question_class == "action":
            return ["Why is that the next action?", "What is still unknown?"]
        return ["Show me the evidence.", "What changed recently?", "What should I do next?"]

    @staticmethod
    def _competitor_target(question: str) -> str | None:
        match = re.search(r"competitor\s+([a-z0-9][a-z0-9._-]*)", question, re.IGNORECASE)
        return match.group(1).casefold() if match else None

    @staticmethod
    def _short(value: str, limit: int = 480) -> str:
        normalised = " ".join(value.split())
        return normalised if len(normalised) <= limit else normalised[: limit - 1].rstrip() + "…"

    @staticmethod
    def _uuid(value: object) -> UUID | None:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.utcoffset() is not None else None
        return None

    @staticmethod
    def _provenance(value: object) -> AskProvenance:
        if value in {
            "customer_direct",
            "salesperson_reported",
            "seller_prepared",
            "imported_external",
        }:
            return cast(AskProvenance, value)
        return "validated_intelligence"
