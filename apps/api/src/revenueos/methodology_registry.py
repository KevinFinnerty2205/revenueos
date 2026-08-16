from __future__ import annotations

from revenueos.methodology_contracts import (
    MethodologyDefinitionContent,
    MethodologyFieldDefinition,
    StandardMethodologyKey,
)


def _field(
    key: str,
    name: str,
    explanation: str,
    order: int,
    facts: tuple[str, ...],
    categories: tuple[str, ...],
    question: str,
    *,
    freshness_days: int | None = None,
    stage: str | None = None,
) -> MethodologyFieldDefinition:
    return MethodologyFieldDefinition.model_validate(
        {
            "key": key,
            "displayName": name,
            "explanation": explanation,
            "order": order,
            "required": True,
            "evidenceExpectations": (
                "Current customer-direct or accepted evidence",
                "Salesperson-reported information remains clearly labelled",
            ),
            "canonicalFacts": facts,
            "evidenceCategories": categories,
            "freshnessDays": freshness_days,
            "suggestedQuestions": (question,),
            "stageExpectation": stage,
        }
    )


_MEDDIC = MethodologyDefinitionContent(
    key="meddic",
    name="MEDDIC",
    description="Understand measurable impact, buying authority, decision path, pain and internal support.",
    version=1,
    standard=True,
    fields=(
        _field(
            "metrics",
            "Metrics",
            "The measurable business result the customer needs.",
            1,
            ("quantified_business_impact", "impact"),
            ("buying_signal", "commercial_intent", "other"),
            "What measurable result would make this project worthwhile?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "economic_buyer",
            "Economic Buyer",
            "The person who owns final commercial approval.",
            2,
            ("economic_buyer", "authority"),
            ("stakeholder", "budget"),
            "Who ultimately owns commercial approval for this project?",
            freshness_days=90,
            stage="evaluation",
        ),
        _field(
            "decision_criteria",
            "Decision Criteria",
            "The outcomes and requirements used to compare options.",
            3,
            ("decision_criteria",),
            ("decision", "technical_requirement", "customer_request", "other"),
            "What will matter most when you compare the available options?",
            freshness_days=120,
            stage="evaluation",
        ),
        _field(
            "decision_process",
            "Decision Process",
            "The steps, people and timing used to reach a decision.",
            4,
            ("decision_process", "decision", "timing"),
            ("decision", "timeline", "stakeholder", "open_question"),
            "What steps remain before the team can make a final decision?",
            freshness_days=60,
            stage="evaluation",
        ),
        _field(
            "identify_pain",
            "Identify Pain",
            "The material customer problem that makes change necessary.",
            5,
            ("business_pain", "pain", "need"),
            ("commercial_intent", "objection", "risk", "other"),
            "What is the cost or consequence of leaving this problem unresolved?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "champion",
            "Champion",
            "A credible internal supporter who can help the change progress.",
            6,
            ("champion",),
            ("stakeholder",),
            "Who is most motivated to help this succeed internally?",
            freshness_days=90,
            stage="evaluation",
        ),
    ),
)

_BANT = MethodologyDefinitionContent(
    key="bant",
    name="BANT",
    description="Understand budget, authority, need and timing from current evidence.",
    version=1,
    standard=True,
    fields=(
        _field(
            "budget",
            "Budget",
            "The customer’s available or approved commercial capacity.",
            1,
            ("budget",),
            ("budget", "buying_signal"),
            "What budget or funding path is available for this work?",
            freshness_days=60,
            stage="evaluation",
        ),
        _field(
            "authority",
            "Authority",
            "The people who can approve or stop the purchase.",
            2,
            ("authority", "economic_buyer"),
            ("stakeholder", "decision"),
            "Who needs to approve this before it can proceed?",
            freshness_days=90,
            stage="evaluation",
        ),
        _field(
            "need",
            "Need",
            "The customer problem and desired outcome that justify action.",
            3,
            ("need", "business_pain", "pain"),
            ("commercial_intent", "risk", "objection", "other"),
            "What needs to change, and why does it matter now?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "timing",
            "Timing",
            "The target date, urgency and events shaping the buying window.",
            4,
            ("timing", "critical_event"),
            ("timeline", "buying_signal", "decision"),
            "What date or event is driving the timing for this decision?",
            freshness_days=60,
            stage="evaluation",
        ),
    ),
)

_SPICED = MethodologyDefinitionContent(
    key="spiced",
    name="SPICED",
    description="Connect the customer situation and pain to impact, urgency and decision path.",
    version=1,
    standard=True,
    fields=(
        _field(
            "situation",
            "Situation",
            "The customer’s relevant current environment and constraints.",
            1,
            ("situation",),
            ("implementation", "technical_requirement", "other"),
            "What does the current environment look like today?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "pain",
            "Pain",
            "The customer problem creating friction or risk.",
            2,
            ("pain", "business_pain", "need"),
            ("risk", "objection", "commercial_intent", "other"),
            "Where is the current approach causing the most difficulty?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "impact",
            "Impact",
            "The measurable consequence of the pain or value of change.",
            3,
            ("impact", "quantified_business_impact"),
            ("commercial_intent", "buying_signal", "other"),
            "What measurable impact does this problem have on the business?",
            freshness_days=180,
            stage="discovery",
        ),
        _field(
            "critical_event",
            "Critical Event",
            "The deadline or event that makes action time-sensitive.",
            4,
            ("critical_event", "timing"),
            ("timeline", "buying_signal", "decision"),
            "What event or deadline makes this important now?",
            freshness_days=60,
            stage="evaluation",
        ),
        _field(
            "decision",
            "Decision",
            "The people, criteria and steps that determine the choice.",
            5,
            ("decision", "decision_criteria", "decision_process", "authority"),
            ("decision", "stakeholder", "open_question"),
            "How will the final decision be made, and who will be involved?",
            freshness_days=60,
            stage="evaluation",
        ),
    ),
)

_MEDDPICC = MethodologyDefinitionContent(
    key="meddpicc",
    name="MEDDPICC",
    description="Extend MEDDIC with the contracting path and competitive position.",
    version=1,
    standard=True,
    fields=(
        *_MEDDIC.fields[:4],
        _field(
            "paper_process",
            "Paper Process",
            "The procurement, legal and contracting path required to buy.",
            5,
            ("paper_process",),
            ("procurement", "security_legal", "timeline", "open_question"),
            "What procurement, legal or contracting steps remain?",
            freshness_days=60,
            stage="procurement",
        ),
        _MEDDIC.fields[4].model_copy(update={"order": 6}),
        _MEDDIC.fields[5].model_copy(update={"order": 7}),
        _field(
            "competition",
            "Competition",
            "The named alternatives, internal options and status quo under consideration.",
            8,
            ("competition",),
            ("competitor", "objection", "buying_signal"),
            "What other options, including the status quo, are being considered?",
            freshness_days=60,
            stage="evaluation",
        ),
    ),
)

STANDARD_METHODOLOGIES: dict[StandardMethodologyKey, MethodologyDefinitionContent] = {
    "meddic": _MEDDIC,
    "meddpicc": _MEDDPICC,
    "bant": _BANT,
    "spiced": _SPICED,
}
STANDARD_METHODOLOGY_ORDER: tuple[StandardMethodologyKey, ...] = (
    "meddic",
    "meddpicc",
    "bant",
    "spiced",
)


def standard_methodology(key: StandardMethodologyKey) -> MethodologyDefinitionContent:
    return STANDARD_METHODOLOGIES[key]


def standard_methodologies() -> tuple[MethodologyDefinitionContent, ...]:
    return tuple(STANDARD_METHODOLOGIES[key] for key in STANDARD_METHODOLOGY_ORDER)
