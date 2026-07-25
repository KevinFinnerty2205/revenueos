from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from revenueos.ai_contracts import (
    ActionItem,
    ActionItemsArtifactContent,
    BuyingSignal,
    BuyingSignalsArtifactContent,
    DecisionItem,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    NextBestActionArtifactContent,
    ObjectionItem,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionItem,
    OpenQuestionsArtifactContent,
    RiskItem,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
    StakeholderItem,
)
from revenueos.models import RevenueBrainSnapshot
from revenueos.revenue_brain_reasoning_contracts import (
    REVENUE_BRAIN_MAX_CHANGES,
    RevenueBrainChange,
    RevenueBrainChangeType,
    RevenueBrainDirection,
    RevenueBrainEvidence,
    RevenueBrainImportance,
    RevenueBrainInsightContent,
    RevenueBrainScope,
    RevenueBrainSourceCapability,
)

REVENUE_BRAIN_REASONING_VERSION = 1
REVENUE_BRAIN_RECENT_SNAPSHOT_LIMIT = 10

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)
_IMPORTANCE_ORDER = {"high": 0, "medium": 1, "low": 2}
_STRENGTH_ORDER = {"weak": 0, "moderate": 1, "strong": 2}
_PRESSURE_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "severe": 4}
_INFLUENCE_ORDER = {"unclear": 0, "low": 1, "medium": 2, "high": 3}
_STANCE_ORDER = {"resistant": 0, "mixed": 1, "unclear": 1, "neutral": 2, "supportive": 3}
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
_PRIORITY_ORDER = {"low": 0, "medium": 1, "high": 2}
_RESOLUTION_TERMS = (
    "resolved",
    "completed",
    "cleared",
    "no longer a risk",
    "no longer blocked",
)
_DEPARTURE_TERMS = (
    "withdrew",
    "withdrawn",
    "left the process",
    "no longer involved",
    "departed",
)


@dataclass(frozen=True)
class RevenueBrainArtifactPayloads:
    executive_summary: ExecutiveSummaryArtifactContent
    buying_signals: BuyingSignalsArtifactContent
    objections_competitive_signals: ObjectionsCompetitiveSignalsArtifactContent
    stakeholder_intelligence: StakeholderIntelligenceArtifactContent
    decisions: DecisionsArtifactContent
    action_items: ActionItemsArtifactContent
    risks_blockers: RisksBlockersArtifactContent
    open_questions: OpenQuestionsArtifactContent
    next_best_action: NextBestActionArtifactContent


@dataclass(frozen=True)
class RevenueBrainSnapshotBundle:
    snapshot: RevenueBrainSnapshot
    meeting_date: datetime
    payloads: RevenueBrainArtifactPayloads
    artifact_ids: dict[RevenueBrainSourceCapability, UUID]


class RevenueBrainComparisonEngine:
    """Authoritative deterministic comparison over validated snapshot artefacts."""

    def compare(
        self,
        scope: RevenueBrainScope,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> RevenueBrainInsightContent:
        changes = [
            *self._compare_buying_signals(before, after),
            *self._compare_objections(before, after),
            *self._compare_stakeholders(before, after),
            *self._compare_risks(before, after),
            *self._compare_questions(before, after),
            *self._compare_decisions(before, after),
            *self._compare_actions(before, after),
            *self._compare_next_best_action(before, after),
        ]
        if len(changes) == 1 and changes[0].change_type == "next_best_action_unchanged":
            changes = []
        changes.sort(
            key=lambda item: (
                _IMPORTANCE_ORDER[item.importance],
                item.change_type,
                item.title,
            )
        )
        bounded = tuple(changes[:REVENUE_BRAIN_MAX_CHANGES])
        if bounded:
            top = bounded[0]
            summary = (
                f"The most important supported change was: {top.title}. "
                f"{len(bounded)} material supported "
                f"{'change was' if len(bounded) == 1 else 'changes were'} identified."
            )
            confidence = round(sum(item.confidence for item in bounded) / len(bounded), 4)
        else:
            summary = "No material supported changes were identified between the latest eligible meetings."
            confidence = round(
                min(
                    before.payloads.executive_summary.confidence,
                    after.payloads.executive_summary.confidence,
                    before.payloads.buying_signals.confidence,
                    after.payloads.buying_signals.confidence,
                    before.payloads.stakeholder_intelligence.confidence,
                    after.payloads.stakeholder_intelligence.confidence,
                    before.payloads.next_best_action.confidence,
                    after.payloads.next_best_action.confidence,
                ),
                4,
            )
        return RevenueBrainInsightContent(
            scope=scope,
            from_snapshot_id=before.snapshot.id,
            to_snapshot_id=after.snapshot.id,
            from_meeting_id=before.snapshot.meeting_id,
            to_meeting_id=after.snapshot.meeting_id,
            from_meeting_date=before.meeting_date.date(),
            to_meeting_date=after.meeting_date.date(),
            changes=bounded,
            summary=summary,
            confidence=confidence,
        )

    def _compare_buying_signals(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = self._signals_by_type(before.payloads.buying_signals)
        later = self._signals_by_type(after.payloads.buying_signals)
        changes: list[RevenueBrainChange] = []

        transitions = (
            (
                "budget_confirmed",
                "budget_unconfirmed",
                "budget_confirmed",
                "improved",
                "high",
                "Budget was confirmed",
                "Budget moved from absent or explicitly unconfirmed to confirmed.",
            ),
            (
                "timeline_confirmed",
                "timeline_unclear",
                "timeline_confirmed",
                "improved",
                "high",
                "Timeline was confirmed",
                "The timeline moved from absent or explicitly unclear to confirmed.",
            ),
            (
                "decision_maker_engaged",
                "decision_maker_missing",
                "decision_maker_entered",
                "improved",
                "high",
                "Decision-maker engagement appeared",
                "Decision-maker coverage moved from absent or explicitly missing to engaged.",
            ),
            (
                "procurement_active",
                "procurement_unclear",
                "procurement_entered",
                "improved",
                "high",
                "Procurement entered the process",
                "Procurement moved from absent or explicitly unclear to active.",
            ),
            (
                "urgency_present",
                "urgency_absent",
                "urgency_increased",
                "improved",
                "medium",
                "Urgency increased",
                "Urgency moved from absent or explicitly absent to present.",
            ),
            (
                "next_step_committed",
                "next_step_weak",
                "next_step_strengthened",
                "improved",
                "high",
                "The next step strengthened",
                "The next step moved from absent or weak to committed.",
            ),
            (
                "stakeholder_alignment",
                "stakeholder_misalignment",
                "stakeholder_alignment_improved",
                "improved",
                "high",
                "Stakeholder alignment improved",
                "Stakeholder alignment moved from absent or misaligned to aligned.",
            ),
            (
                "technical_fit_confirmed",
                "technical_fit_uncertain",
                "technical_fit_improved",
                "improved",
                "medium",
                "Technical fit improved",
                "Technical fit moved from absent or uncertain to confirmed.",
            ),
            (
                "security_or_legal_progress",
                "security_or_legal_blocker",
                "security_or_legal_progressed",
                "improved",
                "high",
                "Security or legal work progressed",
                "Security or legal evidence moved from absent or blocked to progress.",
            ),
        )
        for positive, negative, change_type, direction, importance, title, description in transitions:
            later_signal = later.get(positive)
            if later_signal is None or positive in earlier:
                continue
            earlier_signal = earlier.get(negative)
            changes.append(
                self._signal_change(
                    before,
                    after,
                    cast(RevenueBrainChangeType, change_type),
                    cast(RevenueBrainDirection, direction),
                    cast(RevenueBrainImportance, importance),
                    title,
                    description,
                    positive,
                    earlier_signal,
                    later_signal,
                )
            )

        reverse_transitions = (
            (
                "budget_confirmed",
                "budget_unconfirmed",
                "budget_became_unclear",
                "unclear",
                "high",
                "Budget became unclear",
                "Budget moved from confirmed to explicitly unconfirmed.",
            ),
            (
                "timeline_confirmed",
                "timeline_unclear",
                "timeline_became_unclear",
                "unclear",
                "high",
                "Timeline became unclear",
                "The timeline moved from confirmed to explicitly unclear.",
            ),
            (
                "decision_maker_engaged",
                "decision_maker_missing",
                "decision_maker_missing",
                "worsened",
                "high",
                "Decision-maker coverage deteriorated",
                "Decision-maker coverage moved from engaged to explicitly missing.",
            ),
            (
                "procurement_active",
                "procurement_unclear",
                "procurement_became_unclear",
                "unclear",
                "high",
                "Procurement became unclear",
                "Procurement moved from active to explicitly unclear.",
            ),
            (
                "urgency_present",
                "urgency_absent",
                "urgency_decreased",
                "worsened",
                "medium",
                "Urgency decreased",
                "Urgency moved from present to explicitly absent.",
            ),
            (
                "next_step_committed",
                "next_step_weak",
                "next_step_weakened",
                "worsened",
                "high",
                "The next step weakened",
                "The next step moved from committed to explicitly weak.",
            ),
            (
                "stakeholder_alignment",
                "stakeholder_misalignment",
                "stakeholder_alignment_worsened",
                "worsened",
                "high",
                "Stakeholder alignment worsened",
                "Stakeholder alignment moved from aligned to explicitly misaligned.",
            ),
            (
                "technical_fit_confirmed",
                "technical_fit_uncertain",
                "technical_fit_worsened",
                "worsened",
                "medium",
                "Technical fit became uncertain",
                "Technical fit moved from confirmed to explicitly uncertain.",
            ),
            (
                "security_or_legal_progress",
                "security_or_legal_blocker",
                "security_or_legal_blocker_introduced",
                "worsened",
                "high",
                "A security or legal blocker appeared",
                "Security or legal evidence moved from progress to an explicit blocker.",
            ),
        )
        for positive, negative, change_type, direction, importance, title, description in reverse_transitions:
            earlier_signal = earlier.get(positive)
            later_signal = later.get(negative)
            if earlier_signal is None or later_signal is None:
                continue
            changes.append(
                self._signal_change(
                    before,
                    after,
                    cast(RevenueBrainChangeType, change_type),
                    cast(RevenueBrainDirection, direction),
                    cast(RevenueBrainImportance, importance),
                    title,
                    description,
                    negative,
                    earlier_signal,
                    later_signal,
                )
            )

        commercial = later.get("commercial_intent")
        earlier_commercial = earlier.get("commercial_intent")
        if commercial is not None and (
            earlier_commercial is None
            or _STRENGTH_ORDER[commercial.strength] > _STRENGTH_ORDER[earlier_commercial.strength]
        ):
            changes.append(
                self._signal_change(
                    before,
                    after,
                    "commercial_intent_increased",
                    "improved",
                    "medium",
                    "Commercial intent increased",
                    "Commercial intent appeared or strengthened in the later snapshot.",
                    "commercial_intent",
                    earlier_commercial,
                    commercial,
                )
            )

        procurement = later.get("procurement_active")
        earlier_procurement = earlier.get("procurement_active")
        if (
            procurement is not None
            and earlier_procurement is not None
            and _STRENGTH_ORDER[procurement.strength] > _STRENGTH_ORDER[earlier_procurement.strength]
        ):
            changes.append(
                self._signal_change(
                    before,
                    after,
                    "procurement_progressed",
                    "improved",
                    "high",
                    "Procurement progressed",
                    "The explicit procurement signal strengthened.",
                    "procurement_active",
                    earlier_procurement,
                    procurement,
                )
            )
        return changes

    def _compare_objections(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.objections_competitive_signals
        later = after.payloads.objections_competitive_signals
        changes: list[RevenueBrainChange] = []
        matched_later: set[int] = set()
        for earlier_item in earlier.objections:
            match_index = self._find_objection(earlier_item, later.objections, matched_later)
            if match_index is None:
                continue
            matched_later.add(match_index)
            later_item = later.objections[match_index]
            entity_key = self._entity_key(
                "objection",
                f"{earlier_item.category}:{self._normalise(earlier_item.objection)}",
            )
            evidence = self._paired_evidence(
                before,
                after,
                "objections_competitive_signals",
                entity_key,
                "status",
                earlier_item.status,
                later_item.status,
            )
            confidence = min(earlier_item.confidence, later_item.confidence)
            if earlier_item.status != "resolved" and later_item.status == "resolved":
                changes.append(
                    self._change(
                        "objection_resolved",
                        "resolved",
                        "high",
                        "An objection was resolved",
                        f"The {later_item.category.replace('_', ' ')} objection moved to explicitly resolved.",
                        confidence,
                        "objections_competitive_signals",
                        evidence,
                    )
                )
            elif earlier_item.status == "resolved" and later_item.status != "resolved":
                changes.append(
                    self._change(
                        "objection_reopened",
                        "worsened",
                        "high",
                        "A resolved objection reopened",
                        f"The {later_item.category.replace('_', ' ')} objection became active again.",
                        confidence,
                        "objections_competitive_signals",
                        evidence,
                    )
                )
            elif _STRENGTH_ORDER[later_item.strength] > _STRENGTH_ORDER[earlier_item.strength]:
                changes.append(
                    self._change(
                        "objection_strengthened",
                        "worsened",
                        "high",
                        "An objection strengthened",
                        f"The {later_item.category.replace('_', ' ')} objection increased in strength.",
                        confidence,
                        "objections_competitive_signals",
                        self._paired_evidence(
                            before,
                            after,
                            "objections_competitive_signals",
                            entity_key,
                            "strength",
                            earlier_item.strength,
                            later_item.strength,
                        ),
                    )
                )
            elif _STRENGTH_ORDER[later_item.strength] < _STRENGTH_ORDER[earlier_item.strength]:
                changes.append(
                    self._change(
                        "objection_weakened",
                        "improved",
                        "medium",
                        "An objection weakened",
                        f"The {later_item.category.replace('_', ' ')} objection decreased in strength.",
                        confidence,
                        "objections_competitive_signals",
                        self._paired_evidence(
                            before,
                            after,
                            "objections_competitive_signals",
                            entity_key,
                            "strength",
                            earlier_item.strength,
                            later_item.strength,
                        ),
                    )
                )

        for index, item in enumerate(later.objections):
            if index in matched_later or item.status == "resolved":
                continue
            changes.append(
                self._change(
                    "objection_introduced",
                    "introduced",
                    "high",
                    "A new objection was introduced",
                    f"A supported {item.category.replace('_', ' ')} objection appeared.",
                    item.confidence,
                    "objections_competitive_signals",
                    (
                        self._evidence(
                            after,
                            "objections_competitive_signals",
                            self._entity_key(
                                "objection",
                                f"{item.category}:{self._normalise(item.objection)}",
                            ),
                            "status",
                            item.status,
                        ),
                    ),
                )
            )

        earlier_pressure = earlier.overall_objection_pressure
        later_pressure = later.overall_objection_pressure
        if earlier_pressure in _PRESSURE_ORDER and later_pressure in _PRESSURE_ORDER:
            if _PRESSURE_ORDER[later_pressure] > _PRESSURE_ORDER[earlier_pressure]:
                changes.append(
                    self._change(
                        "competitive_pressure_increased",
                        "worsened",
                        "medium",
                        "Overall objection pressure increased",
                        "Validated overall objection pressure increased.",
                        1.0,
                        "objections_competitive_signals",
                        self._paired_evidence(
                            before,
                            after,
                            "objections_competitive_signals",
                            "objection_pressure:overall",
                            "overall_objection_pressure",
                            earlier_pressure,
                            later_pressure,
                        ),
                    )
                )
            elif _PRESSURE_ORDER[later_pressure] < _PRESSURE_ORDER[earlier_pressure]:
                changes.append(
                    self._change(
                        "competitive_pressure_decreased",
                        "improved",
                        "medium",
                        "Overall objection pressure decreased",
                        "Validated overall objection pressure decreased.",
                        1.0,
                        "objections_competitive_signals",
                        self._paired_evidence(
                            before,
                            after,
                            "objections_competitive_signals",
                            "objection_pressure:overall",
                            "overall_objection_pressure",
                            earlier_pressure,
                            later_pressure,
                        ),
                    )
                )

        earlier_competitors = {self._normalise(item.name): item for item in earlier.competitors}
        for competitor in later.competitors:
            key = self._normalise(competitor.name)
            prior = earlier_competitors.get(key)
            entity_key = self._entity_key("competitor", key)
            if prior is None:
                changes.append(
                    self._change(
                        "competitor_introduced",
                        "introduced",
                        "high",
                        "A competitor entered the discussion",
                        "A named competitor appeared in the later validated snapshot.",
                        competitor.confidence,
                        "objections_competitive_signals",
                        (
                            self._evidence(
                                after,
                                "objections_competitive_signals",
                                entity_key,
                                "position",
                                competitor.position,
                            ),
                        ),
                    )
                )
            elif prior.position != competitor.position:
                earlier_rank = self._competitor_position_rank(prior.position)
                later_rank = self._competitor_position_rank(competitor.position)
                if later_rank > earlier_rank:
                    change_type: RevenueBrainChangeType = "competitor_position_strengthened"
                    direction: RevenueBrainDirection = "worsened"
                    title = "A competitor position strengthened"
                elif later_rank < earlier_rank:
                    change_type = "competitor_position_weakened"
                    direction = "improved"
                    title = "A competitor position weakened"
                else:
                    continue
                changes.append(
                    self._change(
                        change_type,
                        direction,
                        "high",
                        title,
                        "The named competitor's validated position changed.",
                        min(prior.confidence, competitor.confidence),
                        "objections_competitive_signals",
                        self._paired_evidence(
                            before,
                            after,
                            "objections_competitive_signals",
                            entity_key,
                            "position",
                            prior.position,
                            competitor.position,
                        ),
                    )
                )
        return changes

    def _compare_stakeholders(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = {self._normalise(item.name): item for item in before.payloads.stakeholder_intelligence.stakeholders}
        later = {self._normalise(item.name): item for item in after.payloads.stakeholder_intelligence.stakeholders}
        changes: list[RevenueBrainChange] = []
        for key, later_item in later.items():
            prior = earlier.get(key)
            entity_key = self._entity_key("stakeholder", key)
            if prior is None:
                changes.append(self._new_stakeholder_change(after, later_item, entity_key))
                continue
            confidence = min(prior.confidence, later_item.confidence)
            if prior.role != later_item.role:
                change_type, direction, importance, title = self._stakeholder_role_transition(
                    prior,
                    later_item,
                )
                changes.append(
                    self._change(
                        change_type,
                        direction,
                        importance,
                        title,
                        f"The matched stakeholder role changed from "
                        f"{prior.role.replace('_', ' ')} to {later_item.role.replace('_', ' ')}.",
                        confidence,
                        "stakeholder_intelligence",
                        self._paired_evidence(
                            before,
                            after,
                            "stakeholder_intelligence",
                            entity_key,
                            "role",
                            prior.role,
                            later_item.role,
                        ),
                    )
                )
            elif later_item.role == "champion" and (
                _INFLUENCE_ORDER[later_item.influence] != _INFLUENCE_ORDER[prior.influence]
            ):
                improved = _INFLUENCE_ORDER[later_item.influence] > _INFLUENCE_ORDER[prior.influence]
                changes.append(
                    self._change(
                        "champion_strengthened" if improved else "champion_weakened",
                        "improved" if improved else "worsened",
                        "high",
                        "Champion evidence strengthened" if improved else "Champion evidence weakened",
                        "The matched champion's explicit influence changed.",
                        confidence,
                        "stakeholder_intelligence",
                        self._paired_evidence(
                            before,
                            after,
                            "stakeholder_intelligence",
                            entity_key,
                            "influence",
                            prior.influence,
                            later_item.influence,
                        ),
                    )
                )
            elif _INFLUENCE_ORDER[later_item.influence] != _INFLUENCE_ORDER[prior.influence]:
                improved = _INFLUENCE_ORDER[later_item.influence] > _INFLUENCE_ORDER[prior.influence]
                changes.append(
                    self._change(
                        "stakeholder_influence_increased" if improved else "stakeholder_influence_decreased",
                        "improved" if improved else "worsened",
                        "medium",
                        "Stakeholder influence increased" if improved else "Stakeholder influence decreased",
                        "The matched stakeholder's explicit influence changed.",
                        confidence,
                        "stakeholder_intelligence",
                        self._paired_evidence(
                            before,
                            after,
                            "stakeholder_intelligence",
                            entity_key,
                            "influence",
                            prior.influence,
                            later_item.influence,
                        ),
                    )
                )
            if _STANCE_ORDER[later_item.stance] != _STANCE_ORDER[prior.stance]:
                improved = _STANCE_ORDER[later_item.stance] > _STANCE_ORDER[prior.stance]
                changes.append(
                    self._change(
                        "stakeholder_stance_improved" if improved else "stakeholder_stance_worsened",
                        "improved" if improved else "worsened",
                        "medium",
                        "Stakeholder stance improved" if improved else "Stakeholder stance worsened",
                        "The matched stakeholder's explicit stance changed.",
                        confidence,
                        "stakeholder_intelligence",
                        self._paired_evidence(
                            before,
                            after,
                            "stakeholder_intelligence",
                            entity_key,
                            "stance",
                            prior.stance,
                            later_item.stance,
                        ),
                    )
                )

        earlier_coverage = before.payloads.stakeholder_intelligence.role_coverage
        later_coverage = after.payloads.stakeholder_intelligence.role_coverage
        coverage_rules = (
            (
                "economic_buyer",
                "economic_buyer_identified",
                "economic_buyer_became_unclear",
                "Economic buyer coverage improved",
                "Economic buyer coverage became unclear",
            ),
            (
                "technical_buyer",
                "technical_buyer_identified",
                "technical_buyer_became_unclear",
                "Technical buyer coverage improved",
                "Technical buyer coverage became unclear",
            ),
            (
                "procurement",
                "procurement_entered",
                "procurement_became_unclear",
                "Procurement entered the process",
                "Procurement coverage became unclear",
            ),
            (
                "legal_security",
                "security_or_legal_progressed",
                "security_or_legal_blocker_introduced",
                "Legal or security entered the process",
                "Legal or security coverage became explicitly unclear",
            ),
        )
        existing_types = {change.change_type for change in changes}
        for field, improved_type, worsened_type, improved_title, worsened_title in coverage_rules:
            earlier_state = cast(str, getattr(earlier_coverage, field))
            later_state = cast(str, getattr(later_coverage, field))
            if later_state == "identified" and earlier_state != "identified":
                if improved_type in existing_types:
                    continue
                changes.append(
                    self._coverage_change(
                        before,
                        after,
                        cast(RevenueBrainChangeType, improved_type),
                        "improved",
                        improved_title,
                        field,
                        earlier_state,
                        later_state,
                    )
                )
            elif earlier_state == "identified" and later_state in {"not_identified", "unclear"}:
                if worsened_type in existing_types:
                    continue
                changes.append(
                    self._coverage_change(
                        before,
                        after,
                        cast(RevenueBrainChangeType, worsened_type),
                        "unclear",
                        worsened_title,
                        field,
                        earlier_state,
                        later_state,
                    )
                )
        return changes

    def _compare_risks(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.risks_blockers.risks
        later = after.payloads.risks_blockers.risks
        matched_later: set[int] = set()
        changes: list[RevenueBrainChange] = []
        for prior in earlier:
            index = self._find_risk(prior, later, matched_later)
            if index is None:
                continue
            matched_later.add(index)
            item = later[index]
            entity_key = self._entity_key(
                "risk",
                f"{prior.category}:{self._normalise(prior.risk)}",
            )
            confidence = min(prior.confidence, item.confidence)
            later_resolution_text = f"{item.risk} {item.evidence}".casefold()
            if any(term in later_resolution_text for term in _RESOLUTION_TERMS):
                changes.append(
                    self._change(
                        "risk_resolved",
                        "resolved",
                        "high",
                        "A risk was explicitly resolved",
                        f"The matched {item.category.replace('_', ' ')} risk included explicit resolution evidence.",
                        confidence,
                        "risks_blockers",
                        self._paired_evidence(
                            before,
                            after,
                            "risks_blockers",
                            entity_key,
                            "state",
                            "unresolved",
                            "resolved",
                        ),
                    )
                )
            elif _SEVERITY_ORDER[item.severity] > _SEVERITY_ORDER[prior.severity]:
                changes.append(self._risk_severity_change(before, after, prior, item, entity_key, increased=True))
            elif _SEVERITY_ORDER[item.severity] < _SEVERITY_ORDER[prior.severity]:
                changes.append(self._risk_severity_change(before, after, prior, item, entity_key, increased=False))
            else:
                changes.append(
                    self._change(
                        "risk_persisted",
                        "unchanged",
                        "low",
                        "A risk persisted",
                        f"The matched {item.category.replace('_', ' ')} risk remained at the same severity.",
                        confidence,
                        "risks_blockers",
                        self._paired_evidence(
                            before,
                            after,
                            "risks_blockers",
                            entity_key,
                            "severity",
                            prior.severity,
                            item.severity,
                        ),
                    )
                )
        for index, item in enumerate(later):
            if index in matched_later:
                continue
            changes.append(
                self._change(
                    "risk_introduced",
                    "introduced",
                    "high" if item.severity == "high" else "medium",
                    "A new risk was introduced",
                    f"A supported {item.category.replace('_', ' ')} risk appeared.",
                    item.confidence,
                    "risks_blockers",
                    (
                        self._evidence(
                            after,
                            "risks_blockers",
                            self._entity_key(
                                "risk",
                                f"{item.category}:{self._normalise(item.risk)}",
                            ),
                            "severity",
                            item.severity,
                        ),
                    ),
                )
            )
        return changes

    def _compare_questions(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.open_questions.open_questions
        later = after.payloads.open_questions.open_questions
        matched_later: set[int] = set()
        changes: list[RevenueBrainChange] = []
        for prior in earlier:
            index = self._find_question(prior, later, matched_later)
            if index is None:
                continue
            matched_later.add(index)
            item = later[index]
            entity_key = self._entity_key("question", self._normalise(prior.question))
            confidence = min(prior.confidence, item.confidence)
            if _PRIORITY_ORDER[item.importance] > _PRIORITY_ORDER[prior.importance]:
                change_type: RevenueBrainChangeType = "open_question_importance_increased"
                direction: RevenueBrainDirection = "worsened"
                title = "An open question became more important"
            elif _PRIORITY_ORDER[item.importance] < _PRIORITY_ORDER[prior.importance]:
                change_type = "open_question_importance_decreased"
                direction = "improved"
                title = "An open question became less important"
            else:
                change_type = "open_question_persisted"
                direction = "unchanged"
                title = "An open question persisted"
            changes.append(
                self._change(
                    change_type,
                    direction,
                    "medium" if change_type != "open_question_persisted" else "low",
                    title,
                    "The conservatively matched open question remained explicitly open.",
                    confidence,
                    "open_questions",
                    self._paired_evidence(
                        before,
                        after,
                        "open_questions",
                        entity_key,
                        "importance",
                        prior.importance,
                        item.importance,
                    ),
                )
            )
        for index, item in enumerate(later):
            if index in matched_later:
                continue
            changes.append(
                self._change(
                    "open_question_introduced",
                    "introduced",
                    item.importance,
                    "A new open question appeared",
                    "A supported unresolved question appeared in the later snapshot.",
                    item.confidence,
                    "open_questions",
                    (
                        self._evidence(
                            after,
                            "open_questions",
                            self._entity_key("question", self._normalise(item.question)),
                            "importance",
                            item.importance,
                        ),
                    ),
                )
            )
        return changes

    def _compare_decisions(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.decisions.decisions
        later = after.payloads.decisions.decisions
        matched_later: set[int] = set()
        changes: list[RevenueBrainChange] = []
        for prior in earlier:
            index = self._find_decision(prior, later, matched_later)
            if index is None:
                continue
            matched_later.add(index)
            item = later[index]
            if prior.status == item.status:
                continue
            reversed_decision = prior.status == "confirmed" and item.status == "rejected"
            changes.append(
                self._change(
                    "decision_reversed" if reversed_decision else "decision_changed",
                    "worsened" if reversed_decision else "changed",
                    "high",
                    "A confirmed decision was reversed" if reversed_decision else "A decision changed",
                    f"The matched decision status moved from {prior.status} to {item.status}.",
                    min(prior.confidence, item.confidence),
                    "decisions",
                    self._paired_evidence(
                        before,
                        after,
                        "decisions",
                        self._entity_key("decision", self._normalise(prior.decision)),
                        "status",
                        prior.status,
                        item.status,
                    ),
                )
            )
        for index, item in enumerate(later):
            if index in matched_later or item.status != "confirmed":
                continue
            changes.append(
                self._change(
                    "decision_added",
                    "introduced",
                    "medium",
                    "A confirmed decision was added",
                    "A new confirmed decision appeared in the later snapshot.",
                    item.confidence,
                    "decisions",
                    (
                        self._evidence(
                            after,
                            "decisions",
                            self._entity_key("decision", self._normalise(item.decision)),
                            "status",
                            item.status,
                        ),
                    ),
                )
            )
        return changes

    def _compare_actions(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.action_items.action_items
        later = after.payloads.action_items.action_items
        matched_later: set[int] = set()
        changes: list[RevenueBrainChange] = []
        for prior in earlier:
            index = self._find_action(prior, later, matched_later)
            if index is None:
                continue
            matched_later.add(index)
            item = later[index]
            entity_key = self._entity_key("action", self._normalise(prior.task))
            confidence = min(prior.confidence, item.confidence)
            if prior.owner != item.owner and item.owner is not None:
                changes.append(
                    self._change(
                        "action_item_owner_changed",
                        "changed",
                        "medium",
                        "An action item owner changed",
                        "The matched action item has an explicit different owner.",
                        confidence,
                        "action_items",
                        self._paired_evidence(
                            before,
                            after,
                            "action_items",
                            entity_key,
                            "owner_state",
                            "assigned" if prior.owner else "unassigned",
                            "assigned",
                        ),
                    )
                )
            if prior.due_date != item.due_date and item.due_date is not None:
                changes.append(
                    self._change(
                        "action_item_due_date_changed",
                        "changed",
                        "medium",
                        "An action item due date changed",
                        "The matched action item has an explicit different due date.",
                        confidence,
                        "action_items",
                        self._paired_evidence(
                            before,
                            after,
                            "action_items",
                            entity_key,
                            "due_date_state",
                            "set" if prior.due_date else "unset",
                            "set",
                        ),
                    )
                )
        for index, item in enumerate(later):
            if index in matched_later:
                continue
            changes.append(
                self._change(
                    "action_item_added",
                    "introduced",
                    item.priority,
                    "A new action item was added",
                    "A supported open action item appeared in the later snapshot.",
                    item.confidence,
                    "action_items",
                    (
                        self._evidence(
                            after,
                            "action_items",
                            self._entity_key("action", self._normalise(item.task)),
                            "priority",
                            item.priority,
                        ),
                    ),
                )
            )
        return changes

    def _compare_next_best_action(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
    ) -> list[RevenueBrainChange]:
        earlier = before.payloads.next_best_action
        later = after.payloads.next_best_action
        earlier_key = self._normalise(earlier.overall_recommendation)
        later_key = self._normalise(later.overall_recommendation)
        evidence = self._paired_evidence(
            before,
            after,
            "next_best_action",
            self._entity_key("recommendation", earlier_key),
            "priority",
            earlier.priority,
            later.priority,
        )
        confidence = min(earlier.confidence, later.confidence)
        changes: list[RevenueBrainChange] = []
        if earlier_key != later_key:
            changes.append(
                self._change(
                    "next_best_action_changed",
                    "changed",
                    "high",
                    "The Next Best Action changed",
                    "The normalised overall recommendation changed.",
                    confidence,
                    "next_best_action",
                    evidence,
                )
            )
        else:
            changes.append(
                self._change(
                    "next_best_action_unchanged",
                    "unchanged",
                    "low",
                    "The Next Best Action was unchanged",
                    "The normalised overall recommendation remained the same.",
                    confidence,
                    "next_best_action",
                    evidence,
                )
            )
        if _PRIORITY_ORDER[later.priority] > _PRIORITY_ORDER[earlier.priority]:
            changes.append(
                self._change(
                    "next_best_action_priority_increased",
                    "changed",
                    "medium",
                    "Next Best Action priority increased",
                    "The recommendation priority increased.",
                    confidence,
                    "next_best_action",
                    evidence,
                )
            )
        elif _PRIORITY_ORDER[later.priority] < _PRIORITY_ORDER[earlier.priority]:
            changes.append(
                self._change(
                    "next_best_action_priority_decreased",
                    "changed",
                    "medium",
                    "Next Best Action priority decreased",
                    "The recommendation priority decreased.",
                    confidence,
                    "next_best_action",
                    evidence,
                )
            )
        return changes

    def _new_stakeholder_change(
        self,
        after: RevenueBrainSnapshotBundle,
        item: StakeholderItem,
        entity_key: str,
    ) -> RevenueBrainChange:
        role_changes: dict[
            str,
            tuple[
                RevenueBrainChangeType,
                RevenueBrainDirection,
                RevenueBrainImportance,
                str,
            ],
        ] = {
            "champion": (
                "champion_emerged",
                "improved",
                "high",
                "A champion emerged",
            ),
            "economic_buyer": (
                "economic_buyer_identified",
                "improved",
                "high",
                "The economic buyer was identified",
            ),
            "technical_buyer": (
                "technical_buyer_identified",
                "improved",
                "high",
                "A technical buyer was identified",
            ),
            "blocker": (
                "blocker_emerged",
                "worsened",
                "high",
                "A stakeholder blocker emerged",
            ),
            "procurement": (
                "procurement_entered",
                "improved",
                "high",
                "Procurement entered the process",
            ),
            "legal": (
                "security_or_legal_progressed",
                "improved",
                "high",
                "Legal entered the process",
            ),
            "security": (
                "security_or_legal_progressed",
                "improved",
                "high",
                "Security entered the process",
            ),
        }
        change_type, direction, importance, title = role_changes.get(
            item.role,
            (
                "stakeholder_added",
                "introduced",
                "medium",
                "A stakeholder was added",
            ),
        )
        return self._change(
            change_type,
            direction,
            importance,
            title,
            f"A supported {item.role.replace('_', ' ')} stakeholder appeared.",
            item.confidence,
            "stakeholder_intelligence",
            (
                self._evidence(
                    after,
                    "stakeholder_intelligence",
                    entity_key,
                    "role",
                    item.role,
                ),
            ),
        )

    def _stakeholder_role_transition(
        self,
        prior: StakeholderItem,
        later: StakeholderItem,
    ) -> tuple[
        RevenueBrainChangeType,
        RevenueBrainDirection,
        RevenueBrainImportance,
        str,
    ]:
        if later.role == "champion":
            return "champion_emerged", "improved", "high", "A champion emerged"
        if prior.role == "champion":
            departure_text = f"{later.evidence} {later.engagement}".casefold()
            if any(term in departure_text for term in _DEPARTURE_TERMS):
                return (
                    "champion_disappeared",
                    "worsened",
                    "high",
                    "A champion explicitly left the process",
                )
            return "champion_weakened", "worsened", "high", "Champion evidence weakened"
        if later.role == "economic_buyer":
            return (
                "economic_buyer_identified",
                "improved",
                "high",
                "The economic buyer was identified",
            )
        if later.role == "technical_buyer":
            return (
                "technical_buyer_identified",
                "improved",
                "high",
                "A technical buyer was identified",
            )
        if later.role == "blocker":
            return "blocker_emerged", "worsened", "high", "A stakeholder blocker emerged"
        if prior.role == "blocker":
            return "blocker_resolved", "resolved", "high", "A stakeholder blocker was resolved"
        return "stakeholder_role_changed", "changed", "medium", "A stakeholder role changed"

    def _coverage_change(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
        change_type: RevenueBrainChangeType,
        direction: RevenueBrainDirection,
        title: str,
        field: str,
        earlier_state: str,
        later_state: str,
    ) -> RevenueBrainChange:
        return self._change(
            change_type,
            direction,
            "high",
            title,
            f"Explicit {field.replace('_', ' ')} coverage moved from "
            f"{earlier_state.replace('_', ' ')} to {later_state.replace('_', ' ')}.",
            min(
                before.payloads.stakeholder_intelligence.confidence,
                after.payloads.stakeholder_intelligence.confidence,
            ),
            "stakeholder_intelligence",
            self._paired_evidence(
                before,
                after,
                "stakeholder_intelligence",
                f"coverage:{field}",
                field,
                earlier_state,
                later_state,
            ),
        )

    def _risk_severity_change(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
        prior: RiskItem,
        later: RiskItem,
        entity_key: str,
        *,
        increased: bool,
    ) -> RevenueBrainChange:
        return self._change(
            "risk_severity_increased" if increased else "risk_severity_decreased",
            "worsened" if increased else "improved",
            "high" if increased else "medium",
            "Risk severity increased" if increased else "Risk severity decreased",
            f"The matched {later.category.replace('_', ' ')} risk severity changed.",
            min(prior.confidence, later.confidence),
            "risks_blockers",
            self._paired_evidence(
                before,
                after,
                "risks_blockers",
                entity_key,
                "severity",
                prior.severity,
                later.severity,
            ),
        )

    def _signal_change(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
        change_type: RevenueBrainChangeType,
        direction: RevenueBrainDirection,
        importance: RevenueBrainImportance,
        title: str,
        description: str,
        entity: str,
        earlier: BuyingSignal | None,
        later: BuyingSignal,
    ) -> RevenueBrainChange:
        entity_key = f"signal:{entity}"
        evidence: tuple[RevenueBrainEvidence, ...]
        if earlier is None:
            evidence = (
                self._evidence(
                    after,
                    "buying_signals",
                    entity_key,
                    "signal_type",
                    later.signal_type,
                ),
            )
            confidence = later.confidence
        else:
            evidence = self._paired_evidence(
                before,
                after,
                "buying_signals",
                entity_key,
                "signal_type",
                earlier.signal_type,
                later.signal_type,
            )
            confidence = min(earlier.confidence, later.confidence)
        return self._change(
            change_type,
            direction,
            importance,
            title,
            description,
            confidence,
            "buying_signals",
            evidence,
        )

    def _change(
        self,
        change_type: RevenueBrainChangeType,
        direction: RevenueBrainDirection,
        importance: RevenueBrainImportance,
        title: str,
        description: str,
        confidence: float,
        source: RevenueBrainSourceCapability,
        evidence: tuple[RevenueBrainEvidence, ...],
    ) -> RevenueBrainChange:
        return RevenueBrainChange(
            change_type=change_type,
            direction=direction,
            importance=importance,
            title=title,
            description=description,
            confidence=round(confidence, 4),
            source_capabilities=(source,),
            evidence=evidence,
        )

    def _paired_evidence(
        self,
        before: RevenueBrainSnapshotBundle,
        after: RevenueBrainSnapshotBundle,
        source: RevenueBrainSourceCapability,
        entity_key: str,
        field: str,
        earlier_value: str,
        later_value: str,
    ) -> tuple[RevenueBrainEvidence, RevenueBrainEvidence]:
        return (
            self._evidence(
                before,
                source,
                entity_key,
                field,
                earlier_value,
            ),
            self._evidence(
                after,
                source,
                entity_key,
                field,
                later_value,
            ),
        )

    @staticmethod
    def _evidence(
        bundle: RevenueBrainSnapshotBundle,
        source: RevenueBrainSourceCapability,
        entity_key: str,
        field: str,
        value: str,
    ) -> RevenueBrainEvidence:
        return RevenueBrainEvidence(
            snapshot_id=bundle.snapshot.id,
            artefact_id=bundle.artifact_ids[source],
            artefact_type=source,
            entity_key=entity_key,
            field=field,
            value=value,
        )

    @staticmethod
    def _signals_by_type(
        content: BuyingSignalsArtifactContent,
    ) -> dict[str, BuyingSignal]:
        result: dict[str, BuyingSignal] = {}
        for signal in content.signals:
            current = result.get(signal.signal_type)
            if current is None or _STRENGTH_ORDER[signal.strength] > _STRENGTH_ORDER[current.strength]:
                result[signal.signal_type] = signal
        return result

    def _find_objection(
        self,
        target: ObjectionItem,
        candidates: tuple[ObjectionItem, ...],
        used: set[int],
    ) -> int | None:
        return self._find_text_match(
            target.objection,
            target.category,
            tuple((item.objection, item.category) for item in candidates),
            used,
        )

    def _find_risk(
        self,
        target: RiskItem,
        candidates: tuple[RiskItem, ...],
        used: set[int],
    ) -> int | None:
        return self._find_text_match(
            target.risk,
            target.category,
            tuple((item.risk, item.category) for item in candidates),
            used,
        )

    def _find_question(
        self,
        target: OpenQuestionItem,
        candidates: tuple[OpenQuestionItem, ...],
        used: set[int],
    ) -> int | None:
        return self._find_text_match(
            target.question,
            "question",
            tuple((item.question, "question") for item in candidates),
            used,
        )

    def _find_decision(
        self,
        target: DecisionItem,
        candidates: tuple[DecisionItem, ...],
        used: set[int],
    ) -> int | None:
        return self._find_text_match(
            target.decision,
            "decision",
            tuple((item.decision, "decision") for item in candidates),
            used,
        )

    def _find_action(
        self,
        target: ActionItem,
        candidates: tuple[ActionItem, ...],
        used: set[int],
    ) -> int | None:
        return self._find_text_match(
            target.task,
            "action",
            tuple((item.task, "action") for item in candidates),
            used,
        )

    def _find_text_match(
        self,
        target_text: str,
        target_category: str,
        candidates: tuple[tuple[str, str], ...],
        used: set[int],
    ) -> int | None:
        target_normalised = self._normalise(target_text)
        target_terms = self._terms(target_text)
        best: tuple[float, int] | None = None
        for index, (candidate_text, category) in enumerate(candidates):
            if index in used or category != target_category:
                continue
            candidate_normalised = self._normalise(candidate_text)
            if candidate_normalised == target_normalised:
                return index
            candidate_terms = self._terms(candidate_text)
            intersection = target_terms & candidate_terms
            union = target_terms | candidate_terms
            if len(intersection) < 2 or not union:
                continue
            score = len(intersection) / len(union)
            if score >= 0.55 and (best is None or score > best[0]):
                best = (score, index)
        return best[1] if best is not None else None

    @staticmethod
    def _competitor_position_rank(position: str) -> int:
        return {
            "weaker": 0,
            "unclear": 1,
            "neutral": 1,
            "present": 2,
            "stronger": 3,
        }[position]

    @staticmethod
    def _normalise(value: str) -> str:
        return "-".join(_WORD_PATTERN.findall(value.casefold()))

    @staticmethod
    def _terms(value: str) -> frozenset[str]:
        return frozenset(
            term for term in _WORD_PATTERN.findall(value.casefold()) if term not in _STOP_WORDS and len(term) > 1
        )

    @staticmethod
    def _entity_key(kind: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
        return f"{kind}:{digest}"
