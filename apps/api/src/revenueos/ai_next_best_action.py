from __future__ import annotations

from collections.abc import Iterable, Mapping

from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    NextBestActionArtifactContent,
    NextBestActionSource,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RecommendedAction,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)

NEXT_BEST_ACTION_SOURCE_ARTIFACT_TYPES = (
    "executive_summary",
    "buying_signals",
    "objections_competitive_signals",
    "stakeholder_intelligence",
    "decisions",
    "action_items",
    "open_questions",
    "risks_blockers",
)


def build_next_best_action_source(
    *,
    executive_summary: Mapping[str, object],
    buying_signals: Mapping[str, object],
    objections: Mapping[str, object],
    stakeholders: Mapping[str, object],
    decisions: Mapping[str, object],
    action_items: Mapping[str, object],
    open_questions: Mapping[str, object],
    risks: Mapping[str, object],
) -> NextBestActionSource:
    """Validate and compose only current intelligence artefacts."""

    return NextBestActionSource(
        executive_summary=ExecutiveSummaryArtifactContent.model_validate(
            executive_summary,
        ),
        buying_signals=BuyingSignalsArtifactContent.model_validate(
            buying_signals,
        ),
        objections=ObjectionsCompetitiveSignalsArtifactContent.model_validate(
            objections,
        ),
        stakeholders=StakeholderIntelligenceArtifactContent.model_validate(
            stakeholders,
        ),
        decisions=DecisionsArtifactContent.model_validate(decisions),
        action_items=ActionItemsArtifactContent.model_validate(action_items),
        open_questions=OpenQuestionsArtifactContent.model_validate(
            open_questions,
        ),
        risks=RisksBlockersArtifactContent.model_validate(risks),
    )


def output_is_grounded(
    content: NextBestActionArtifactContent,
    source: NextBestActionSource,
) -> bool:
    """Require every reason to cite exact values from validated artefacts."""

    references = _source_references(source)
    all_references = frozenset(reference for values in references.values() for reference in values)
    if any(not _contains_reference(reasoning, all_references) for reasoning in content.reasoning):
        return False
    return all(_action_is_grounded(action, references) for action in content.recommended_actions)


def _action_is_grounded(
    action: RecommendedAction,
    references: Mapping[str, frozenset[str]],
) -> bool:
    all_references = (reference for source_references in references.values() for reference in source_references)
    return _contains_reference(action.reason, all_references) and all(
        _contains_reference(action.reason, references[dependency]) for dependency in action.depends_on
    )


def _contains_reference(value: str, references: Iterable[str]) -> bool:
    lowered = value.casefold()
    return any(reference in lowered for reference in references)


def _source_references(
    source: NextBestActionSource,
) -> dict[str, frozenset[str]]:
    buying = {
        source.buying_signals.overall_momentum,
        source.buying_signals.momentum_summary,
        *(
            value
            for signal in source.buying_signals.signals
            for value in (
                signal.signal_type,
                signal.evidence,
            )
        ),
    }
    stakeholder_values = {
        source.stakeholders.stakeholder_summary,
        *(
            f"{field}:{getattr(source.stakeholders.role_coverage, field)}"
            for field in (
                "economic_buyer",
                "decision_maker",
                "champion",
                "technical_buyer",
                "procurement",
                "legal_security",
            )
        ),
        *(
            value
            for stakeholder in source.stakeholders.stakeholders
            for value in (
                stakeholder.name,
                stakeholder.role,
                stakeholder.evidence,
            )
        ),
    }
    risk_values = {
        value
        for risk in source.risks.risks
        for value in (
            risk.risk,
            risk.category,
            risk.evidence,
        )
    }
    question_values = {
        value
        for question in source.open_questions.open_questions
        for value in (
            question.question,
            question.evidence,
        )
    }
    action_values = {
        value
        for action in source.action_items.action_items
        for value in (
            action.task,
            action.evidence,
        )
    }
    shared = {
        source.executive_summary.executive_summary,
        source.objections.summary,
        *(
            value
            for objection in source.objections.objections
            for value in (
                objection.objection,
                objection.category,
                objection.evidence,
            )
        ),
        *(
            value
            for decision in source.decisions.decisions
            for value in (
                decision.decision,
                decision.evidence,
            )
        ),
    }
    return {
        "buying_signals": _normalise_references(buying),
        "stakeholders": _normalise_references(stakeholder_values),
        "risks": _normalise_references(risk_values),
        "open_questions": _normalise_references(question_values),
        "action_items": _normalise_references(action_values),
        "context": _normalise_references(shared),
    }


def _normalise_references(values: Iterable[str]) -> frozenset[str]:
    return frozenset(normalised for value in values if len(normalised := value.strip().casefold()) >= 5)
