from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from revenueos.debrief_contracts import (
    CandidateEvidenceCategory,
    CandidateEvidenceExtraction,
    CandidateEvidenceExtractionItem,
    DebriefCaptureType,
    DebriefQuestion,
    DebriefQuestionTarget,
)


@dataclass(frozen=True)
class QuestionTemplate:
    target: DebriefQuestionTarget
    question: str
    reason: str
    priority: Literal["high", "medium", "low"]
    answer_terms: tuple[str, ...]


GENERAL_QUESTIONS = (
    QuestionTemplate(
        "next_step",
        "What is the most important next step, and who owns it?",
        "A clear owner keeps the latest interaction actionable.",
        "high",
        ("next step", "follow up", "send", "owner", "will "),
    ),
    QuestionTemplate(
        "stakeholder",
        "Did anyone new become involved, or did a stakeholder’s role change?",
        "Stakeholder changes can materially alter the opportunity.",
        "high",
        ("stakeholder", "decision maker", "economic buyer", "procurement", "joined", "attended"),
    ),
    QuestionTemplate(
        "decision",
        "Was any decision or commitment made?",
        "Decisions and commitments are high-value changes worth confirming.",
        "high",
        ("decided", "agreed", "approved", "committed", "promised"),
    ),
    QuestionTemplate(
        "timeline",
        "Did the expected timeline change?",
        "Timeline changes affect preparation and follow-through.",
        "medium",
        ("timeline", "date", "month", "week", "october", "november", "december", "january"),
    ),
    QuestionTemplate(
        "objection",
        "Did the customer raise or resolve an important concern?",
        "Unresolved concerns may change the next interaction.",
        "medium",
        ("objection", "concern", "worried", "hesitant", "resolved", "blocker"),
    ),
    QuestionTemplate(
        "commercial_intent",
        "What was the most important thing you learned about their intent?",
        "Material commercial change is more useful than a complete conversation reconstruction.",
        "medium",
        ("budget", "commercial", "buy", "purchase", "proposal", "intent", "start"),
    ),
)

TYPE_QUESTIONS: dict[str, tuple[QuestionTemplate, ...]] = {
    "phone_call": (
        QuestionTemplate(
            "next_step",
            "What outcome or next step came from the call?",
            "Phone-call debriefs prioritise outcome and follow-through.",
            "high",
            ("outcome", "next step", "follow up", "will "),
        ),
        QuestionTemplate(
            "commitment",
            "Did either side make a commitment?",
            "Call commitments should be captured while fresh.",
            "high",
            ("committed", "promised", "agreed", "will "),
        ),
    ),
    "presentation": (
        QuestionTemplate(
            "other",
            "How did the audience react, and which parts generated discussion or fell flat?",
            "Audience reaction matters more than the seller’s prepared material.",
            "high",
            ("audience", "discussion", "reacted", "engaged", "questioned"),
        ),
        QuestionTemplate(
            "open_question",
            "What questions did the customer ask?",
            "Customer questions are source-aware evidence of what needs follow-up.",
            "high",
            ("asked", "question"),
        ),
        QuestionTemplate(
            "objection",
            "What objections, concerns or points of hesitation came up?",
            "Customer objections need to remain distinct from claims made in the presentation.",
            "high",
            ("objection", "concern", "hesitant", "pushback", "blocker"),
        ),
        QuestionTemplate(
            "action_item",
            "What material or follow-up did the customer request?",
            "A customer request can create a clear, reviewable follow-up.",
            "medium",
            ("requested", "asked for", "send", "material", "follow up"),
        ),
        QuestionTemplate(
            "decision",
            "What changed in the decision path, stakeholder group or commercial intent?",
            "Decision-path, stakeholder and commercial changes are useful only when explicitly reported.",
            "medium",
            ("decision", "approval", "stakeholder", "committee", "sign off"),
        ),
        QuestionTemplate(
            "commitment",
            "What commitments or next meeting did either side agree to?",
            "Agreed commitments and next meetings should be captured while fresh.",
            "high",
            ("committed", "agreed", "next meeting", "will ", "scheduled"),
        ),
    ),
    "site_visit": (
        QuestionTemplate(
            "implementation",
            "What implementation constraint or requirement became clear?",
            "Site observations often change implementation planning.",
            "high",
            ("implementation", "constraint", "requirement", "environment", "site"),
        ),
        QuestionTemplate(
            "security_legal",
            "Did you observe a technical, safety or security risk that needs validation?",
            "Reported observations must remain distinct from customer-confirmed facts.",
            "high",
            ("technical", "safety", "security", "risk", "validate"),
        ),
    ),
    "executive_lunch": (
        QuestionTemplate(
            "commercial_intent",
            "Did an executive priority or relationship signal change?",
            "Executive-lunch debriefs stay concise and strategic.",
            "high",
            ("priority", "relationship", "sponsor", "intent"),
        ),
    ),
    "conference_interaction": (
        QuestionTemplate(
            "stakeholder",
            "Who did you meet, and why do they matter?",
            "Short event debriefs start with identity and relevance.",
            "high",
            ("met", "role", "works", "stakeholder"),
        ),
    ),
    "trade_show_interaction": (
        QuestionTemplate(
            "stakeholder",
            "Who did you meet, and why do they matter?",
            "Short event debriefs start with identity and relevance.",
            "high",
            ("met", "role", "works", "stakeholder"),
        ),
    ),
}


class DeterministicDebriefReasoning:
    """Application-owned v1 question and extraction policy with strict output contracts."""

    @staticmethod
    def opening_question() -> DebriefQuestion:
        return DebriefQuestion(
            status="ask",
            question="How did it go?",
            reason="Start naturally so you can report what changed in your own words.",
            target="other",
            priority="high",
        )

    def next_question(
        self,
        *,
        interaction_type: str,
        capture_type: DebriefCaptureType,
        answers: tuple[str, ...],
        asked_targets: tuple[str, ...],
        question_count: int,
        max_questions: int,
        brief_questions: tuple[str, ...],
    ) -> DebriefQuestion:
        if question_count >= max_questions or self._user_finished(answers[-1]):
            return self.complete_question("The configured question limit or the user’s finish signal was reached.")
        reported = " ".join(answers).lower()
        templates = (*TYPE_QUESTIONS.get(interaction_type, ()), *GENERAL_QUESTIONS)
        for template in templates:
            if template.target in asked_targets:
                continue
            if any(term in reported for term in template.answer_terms):
                continue
            return DebriefQuestion(
                status="ask",
                question=template.question,
                reason=template.reason,
                target=template.target,
                priority=template.priority,
            )
        for prepared in brief_questions:
            if self._normalise(prepared) in self._normalise(reported):
                continue
            if "other" in asked_targets:
                break
            return DebriefQuestion(
                status="ask",
                question=prepared,
                reason="This was an unresolved question in the pre-interaction brief.",
                target="other",
                priority="medium",
            )
        if capture_type == "voice_journal" or question_count >= max_questions:
            return self.complete_question("No material unanswered gap remains for this bounded capture.")
        return self.complete_question("The reported evidence is sufficient for review.")

    def extract_candidates(
        self,
        fragments: tuple[tuple[UUID, str], ...],
    ) -> CandidateEvidenceExtraction:
        items: list[CandidateEvidenceExtractionItem] = []
        seen: set[tuple[str, str]] = set()
        for fragment_id, answer in fragments:
            sentences = [self._statement(value) for value in re.split(r"[.!?\n]+", answer) if value.strip()]
            for sentence in sentences:
                categories = self._categories(sentence)
                for category in categories:
                    identity = (category, self._normalise(sentence))
                    if identity in seen:
                        continue
                    seen.add(identity)
                    items.append(
                        CandidateEvidenceExtractionItem(
                            evidence_category=cast(CandidateEvidenceCategory, category),
                            statement=sentence,
                            source_fragment_id=fragment_id,
                        )
                    )
                    if len(items) >= 100:
                        return CandidateEvidenceExtraction(items=tuple(items))
        return CandidateEvidenceExtraction(items=tuple(items))

    @staticmethod
    def complete_question(reason: str) -> DebriefQuestion:
        return DebriefQuestion(status="complete", reason=reason)

    @staticmethod
    def _user_finished(value: str) -> bool:
        normalised = " ".join(value.lower().split()).strip(" .!")
        return normalised in {
            "nothing else",
            "no",
            "nope",
            "that's all",
            "that is all",
            "finished",
            "finish",
        }

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value.lower()).split())

    @staticmethod
    def _statement(value: str) -> str:
        statement = " ".join(value.split()).strip(" ,;:-")[:999]
        if statement and statement[-1] not in ".!":
            statement += "."
        return statement[0].upper() + statement[1:]

    @staticmethod
    def _categories(statement: str) -> tuple[str, ...]:
        value = statement.lower()
        rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("procurement", ("procurement", "purchasing")),
            ("budget", ("budget", "funding", "price approved")),
            ("security_legal", ("security", "legal", "soc 2", "contract", "privacy")),
            ("competitor", ("competitor", "competing", "alternative vendor")),
            ("objection", ("objection", "concern", "hesitant", "pushback", "unacceptable")),
            ("risk", ("risk", "blocker", "delay", "may prevent", "constraint")),
            ("decision", ("decided", "decision", "approved", "agreed to proceed", "rejected")),
            ("action_item", ("i need to", "i will", "we need to", "send ", "follow up", "schedule ")),
            ("commitment", ("committed", "promised", "agreed to", "will provide", "will send")),
            ("open_question", ("unanswered", "still need to know", "unclear", "open question")),
            ("timeline", ("timeline", "start in", "deadline", "by october", "by november", "by december")),
            ("implementation", ("implementation", "integration", "deployment", "rollout")),
            ("customer_request", ("asked for", "requested", "they want", "customer wants", "need our")),
            ("commercial_intent", ("commercial", "purchase", "buy", "proposal", "pricing", "intent")),
            ("buying_signal", ("ready to", "want to start", "approved budget", "move forward", "go ahead")),
            (
                "stakeholder",
                ("stakeholder", "decision maker", "economic buyer", "champion", "procurement owner", "joined"),
            ),
        )
        categories = tuple(category for category, terms in rules if any(term in value for term in terms))
        return categories or ("other",)
