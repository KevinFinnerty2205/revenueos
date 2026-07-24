from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Literal, cast

from pydantic import JsonValue

from revenueos.ai_action_items_dates import normalise_action_item_due_date
from revenueos.ai_contracts import (
    ACTION_ITEM_EVIDENCE_MAX_LENGTH,
    ACTION_ITEM_TASK_MAX_LENGTH,
    ACTION_ITEMS_MAX_COUNT,
    ACTION_ITEMS_SCHEMA_VERSION,
    BUYING_SIGNALS_MAX_COUNT,
    BUYING_SIGNALS_SCHEMA_VERSION,
    COMPETITORS_MAX_COUNT,
    DECISION_EVIDENCE_MAX_LENGTH,
    DECISION_MAX_LENGTH,
    DECISIONS_MAX_COUNT,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    FOLLOW_UP_EMAIL_SCHEMA_VERSION,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
    NEXT_BEST_ACTION_SCHEMA_VERSION,
    OBJECTION_EVIDENCE_MAX_LENGTH,
    OBJECTION_MAX_LENGTH,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OBJECTIONS_MAX_COUNT,
    OPEN_QUESTION_EVIDENCE_MAX_LENGTH,
    OPEN_QUESTION_MAX_LENGTH,
    OPEN_QUESTIONS_MAX_COUNT,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    RISK_EVIDENCE_MAX_LENGTH,
    RISK_MAX_LENGTH,
    RISKS_BLOCKERS_MAX_COUNT,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    STAKEHOLDER_EVIDENCE_MAX_LENGTH,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
    STAKEHOLDERS_MAX_COUNT,
)
from revenueos.ai_provider_contracts import (
    ActionItemsProviderInput,
    BuyingSignalsProviderInput,
    DecisionsProviderInput,
    ExecutiveSummaryProviderInput,
    FollowUpEmailProviderInput,
    NextBestActionProviderInput,
    ObjectionsCompetitiveSignalsProviderInput,
    OpenQuestionsProviderInput,
    ProviderRequest,
    ProviderResponse,
    RisksBlockersProviderInput,
    StakeholderIntelligenceProviderInput,
)
from revenueos.ai_provider_errors import (
    InvalidProviderRequestError,
    UnsupportedModelError,
)
from revenueos.domain import AIJobType

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_IDENTIFIER = "mock-infrastructure-v1"
MockOutputKind = Literal[
    "valid_mapping",
    "valid_json",
    "malformed_json",
    "schema_invalid",
]


class DeterministicMockAIProvider:
    """Deterministic, zero-network provider for supported mock AI jobs."""

    provider_name = MOCK_PROVIDER_NAME
    model_identifier = MOCK_MODEL_IDENTIFIER

    def __init__(
        self,
        output_sequence: tuple[MockOutputKind, ...] | None = None,
    ) -> None:
        if output_sequence is not None and not output_sequence:
            raise ValueError("Mock output sequence must not be empty.")
        self._output_sequence = output_sequence or ("valid_mapping",)
        self._execution_count = 0

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        if request.model_identifier != self.model_identifier:
            raise UnsupportedModelError
        if not self._valid_request(request):
            raise InvalidProviderRequestError
        output_kind = self._output_sequence[min(self._execution_count, len(self._output_sequence) - 1)]
        self._execution_count += 1

        deterministic_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"revenueos:{request.request_id}:{request.job_id}:{self.model_identifier}",
        )
        valid_output = self._valid_output(request)
        if output_kind == "valid_mapping":
            output_payload: dict[str, JsonValue] | str = valid_output
        elif output_kind == "valid_json":
            output_payload = json.dumps(valid_output, separators=(",", ":"))
        elif output_kind == "malformed_json":
            output_payload = '{"result":'
        else:
            output_payload = self._schema_invalid_output(request)

        return ProviderResponse(
            provider_name=self.provider_name,
            model_identifier=self.model_identifier,
            provider_request_id=f"mock-{deterministic_request_id}",
            output_payload=output_payload,
            input_token_count=0,
            output_token_count=0,
            total_token_count=0,
            estimated_cost_minor_units=0,
            currency="AUD",
            provider_latency_ms=0,
            finish_reason="completed",
        )

    @staticmethod
    def _valid_request(request: ProviderRequest) -> bool:
        if request.job_type == AIJobType.INFRASTRUCTURE_TEST.value:
            return (
                request.expected_schema_version == INFRASTRUCTURE_TEST_SCHEMA_VERSION
                and request.input_payload.operation == AIJobType.INFRASTRUCTURE_TEST.value
            )
        if request.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
            return request.expected_schema_version == EXECUTIVE_SUMMARY_SCHEMA_VERSION and isinstance(
                request.input_payload, ExecutiveSummaryProviderInput
            )
        if request.job_type == AIJobType.DECISIONS.value:
            return request.expected_schema_version == DECISIONS_SCHEMA_VERSION and isinstance(
                request.input_payload, DecisionsProviderInput
            )
        if request.job_type == AIJobType.ACTION_ITEMS.value:
            return request.expected_schema_version == ACTION_ITEMS_SCHEMA_VERSION and isinstance(
                request.input_payload, ActionItemsProviderInput
            )
        if request.job_type == AIJobType.RISKS_BLOCKERS.value:
            return request.expected_schema_version == RISKS_BLOCKERS_SCHEMA_VERSION and isinstance(
                request.input_payload, RisksBlockersProviderInput
            )
        if request.job_type == AIJobType.OPEN_QUESTIONS.value:
            return request.expected_schema_version == OPEN_QUESTIONS_SCHEMA_VERSION and isinstance(
                request.input_payload, OpenQuestionsProviderInput
            )
        if request.job_type == AIJobType.BUYING_SIGNALS.value:
            return request.expected_schema_version == BUYING_SIGNALS_SCHEMA_VERSION and isinstance(
                request.input_payload, BuyingSignalsProviderInput
            )
        if request.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
            return request.expected_schema_version == OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION and isinstance(
                request.input_payload,
                ObjectionsCompetitiveSignalsProviderInput,
            )
        if request.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
            return request.expected_schema_version == STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION and isinstance(
                request.input_payload,
                StakeholderIntelligenceProviderInput,
            )
        if request.job_type == AIJobType.NEXT_BEST_ACTION.value:
            return request.expected_schema_version == NEXT_BEST_ACTION_SCHEMA_VERSION and isinstance(
                request.input_payload,
                NextBestActionProviderInput,
            )
        if request.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
            return request.expected_schema_version == FOLLOW_UP_EMAIL_SCHEMA_VERSION and isinstance(
                request.input_payload, FollowUpEmailProviderInput
            )
        return False

    @classmethod
    def _valid_output(cls, request: ProviderRequest) -> dict[str, JsonValue]:
        if request.job_type == AIJobType.INFRASTRUCTURE_TEST.value:
            return {
                "status": "ok",
                "message": "AI processing infrastructure is operational.",
            }
        if isinstance(request.input_payload, ExecutiveSummaryProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            meeting_context = request.input_payload.messages[1].content.lower()
            return {
                "executive_summary": cls._summarise_transcript(transcript),
                "meeting_type": cls._meeting_type(meeting_context, transcript),
                "sentiment": cls._sentiment(transcript),
                "confidence": 0.82 if len(transcript) >= 100 else 0.72,
            }
        if isinstance(request.input_payload, DecisionsProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return {"decisions": cast(JsonValue, cls._extract_decisions(transcript))}
        if isinstance(request.input_payload, ActionItemsProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            meeting_date = cls._extract_meeting_date(request.input_payload)
            return {
                "action_items": cast(
                    JsonValue,
                    cls._extract_action_items(transcript, meeting_date),
                )
            }
        if isinstance(request.input_payload, RisksBlockersProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return {"risks": cast(JsonValue, cls._extract_risks_blockers(transcript))}
        if isinstance(request.input_payload, OpenQuestionsProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return {
                "open_questions": cast(
                    JsonValue,
                    cls._extract_open_questions(transcript),
                )
            }
        if isinstance(request.input_payload, BuyingSignalsProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return cls._extract_buying_signals(transcript)
        if isinstance(request.input_payload, ObjectionsCompetitiveSignalsProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return cls._extract_objections_competitive_signals(transcript)
        if isinstance(request.input_payload, StakeholderIntelligenceProviderInput):
            transcript = cls._extract_transcript(request.input_payload)
            return cls._extract_stakeholder_intelligence(transcript)
        if isinstance(request.input_payload, NextBestActionProviderInput):
            sources = {
                field: cls._extract_composition_value(
                    request.input_payload,
                    f"Validated {label} JSON: ",
                )
                for field, label in (
                    ("executive_summary", "Executive Summary"),
                    ("buying_signals", "Buying Signals"),
                    ("objections", "Objections"),
                    ("stakeholders", "Stakeholders"),
                    ("decisions", "Decisions"),
                    ("action_items", "Action Items"),
                    ("open_questions", "Open Questions"),
                    ("risks", "Risks"),
                )
            }
            if not all(isinstance(value, dict) for value in sources.values()):
                raise InvalidProviderRequestError
            return cls._recommend_next_best_actions(
                cast(dict[str, dict[str, JsonValue]], sources),
            )
        if isinstance(request.input_payload, FollowUpEmailProviderInput):
            summary = cls._extract_composition_value(
                request.input_payload,
                "Validated Executive Summary as a JSON string: ",
            )
            decisions = cls._extract_composition_value(
                request.input_payload,
                "Validated Decisions as a JSON array: ",
            )
            action_items = cls._extract_composition_value(
                request.input_payload,
                "Validated Action Items as a JSON array: ",
            )
            open_questions = cls._extract_composition_value(
                request.input_payload,
                "Validated Open Questions as a JSON array: ",
            )
            tone = cls._extract_composition_value(
                request.input_payload,
                "Requested Tone as a JSON string: ",
            )
            if (
                not isinstance(summary, str)
                or not isinstance(decisions, list)
                or not all(isinstance(item, str) for item in decisions)
                or not isinstance(action_items, list)
                or not all(isinstance(item, str) for item in action_items)
                or not isinstance(open_questions, list)
                or not all(isinstance(item, str) for item in open_questions)
                or not isinstance(tone, str)
                or tone not in {"professional", "friendly", "executive"}
            ):
                raise InvalidProviderRequestError
            greeting, closing = {
                "professional": ("Hello,", "Kind regards,"),
                "friendly": ("Hi,", "Thanks,"),
                "executive": ("Hello,", "Regards,"),
            }[tone]
            return {
                "subject": "Meeting follow-up",
                "greeting": greeting,
                "summary": summary,
                "decisions": cast(JsonValue, decisions),
                "action_items": cast(JsonValue, action_items),
                "open_questions": cast(JsonValue, open_questions),
                "closing": closing,
                "tone": tone,
                "confidence": 0.95,
            }
        raise InvalidProviderRequestError

    @staticmethod
    def _extract_composition_value(
        input_payload: FollowUpEmailProviderInput | NextBestActionProviderInput,
        prefix: str,
    ) -> JsonValue:
        for line in input_payload.messages[1].content.splitlines():
            if not line.startswith(prefix):
                continue
            try:
                return cast(JsonValue, json.loads(line[len(prefix) :]))
            except (TypeError, ValueError) as exc:
                raise InvalidProviderRequestError from exc
        raise InvalidProviderRequestError

    @staticmethod
    def _recommend_next_best_actions(
        sources: dict[str, dict[str, JsonValue]],
    ) -> dict[str, JsonValue]:
        """Return deterministic recommendations from validated artefact JSON."""

        buying = sources["buying_signals"]
        stakeholders = sources["stakeholders"]
        risks_source = sources["risks"]
        questions_source = sources["open_questions"]
        signal_values = buying.get("signals")
        signals = signal_values if isinstance(signal_values, list) else []
        signal_types = {
            value for item in signals if isinstance(item, dict) and isinstance((value := item.get("signal_type")), str)
        }
        coverage_value = stakeholders.get("role_coverage")
        coverage = coverage_value if isinstance(coverage_value, dict) else {}
        risk_values = risks_source.get("risks")
        risks = risk_values if isinstance(risk_values, list) else []
        question_values = questions_source.get("open_questions")
        questions = question_values if isinstance(question_values, list) else []
        recommendations: list[dict[str, JsonValue]] = []

        missing_references: list[str] = []
        missing_dependencies: list[str] = []
        if "decision_maker_missing" in signal_types:
            missing_references.append(
                "Buying Signals: decision_maker_missing.",
            )
            missing_dependencies.append("buying_signals")
        if coverage.get("economic_buyer") == "not_identified":
            missing_references.append(
                "Stakeholders: economic_buyer:not_identified.",
            )
            missing_dependencies.append("stakeholders")
        elif coverage.get("decision_maker") == "not_identified":
            missing_references.append(
                "Stakeholders: decision_maker:not_identified.",
            )
            missing_dependencies.append("stakeholders")
        if missing_references:
            recommendations.append(
                {
                    "action": "Identify the economic buyer.",
                    "reason": " ".join(missing_references),
                    "priority": "high",
                    "confidence": 0.94,
                    "depends_on": cast(JsonValue, missing_dependencies),
                }
            )

        technical_risk = next(
            (
                item
                for item in risks
                if isinstance(item, dict) and item.get("category") == "technical" and isinstance(item.get("risk"), str)
            ),
            None,
        )
        if technical_risk is not None:
            risk_text = cast(str, technical_risk["risk"])
            priority = "high" if technical_risk.get("severity") == "high" else "medium"
            recommendations.append(
                {
                    "action": "Book a technical workshop.",
                    "reason": f"Risks: {risk_text}",
                    "priority": priority,
                    "confidence": 0.92,
                    "depends_on": ["risks"],
                }
            )

        if "next_step_weak" in signal_types:
            recommendations.append(
                {
                    "action": "Schedule a follow-up meeting.",
                    "reason": "Buying Signals: next_step_weak.",
                    "priority": "high",
                    "confidence": 0.91,
                    "depends_on": ["buying_signals"],
                }
            )

        high_question = next(
            (
                item
                for item in questions
                if isinstance(item, dict) and item.get("importance") == "high" and isinstance(item.get("question"), str)
            ),
            None,
        )
        if high_question is not None:
            question = cast(str, high_question["question"])
            recommendations.append(
                {
                    "action": "Resolve the highest-priority open question.",
                    "reason": f"Open Questions: {question}",
                    "priority": "high",
                    "confidence": 0.9,
                    "depends_on": ["open_questions"],
                }
            )

        material_risk = next(
            (
                item
                for item in risks
                if isinstance(item, dict)
                and item is not technical_risk
                and item.get("severity") in {"high", "medium"}
                and isinstance(item.get("risk"), str)
            ),
            None,
        )
        if material_risk is not None:
            risk_text = cast(str, material_risk["risk"])
            recommendations.append(
                {
                    "action": "Address the highest-priority blocker.",
                    "reason": f"Risks: {risk_text}",
                    "priority": ("high" if material_risk.get("severity") == "high" else "medium"),
                    "confidence": 0.89,
                    "depends_on": ["risks"],
                }
            )

        if not recommendations:
            momentum = buying.get("overall_momentum")
            reference = momentum if isinstance(momentum, str) else "insufficient_evidence"
            recommendations.append(
                {
                    "action": "Schedule a follow-up meeting.",
                    "reason": f"Buying Signals: {reference}.",
                    "priority": "medium",
                    "confidence": 0.78,
                    "depends_on": ["buying_signals"],
                }
            )

        bounded = recommendations[:5]
        primary = bounded[0]
        reasoning = [cast(str, recommendation["reason"]) for recommendation in bounded]
        return {
            "overall_recommendation": primary["action"],
            "priority": primary["priority"],
            "confidence": primary["confidence"],
            "reasoning": cast(JsonValue, reasoning),
            "recommended_actions": cast(JsonValue, bounded),
        }

    @staticmethod
    def _extract_transcript(
        input_payload: (
            ExecutiveSummaryProviderInput
            | DecisionsProviderInput
            | ActionItemsProviderInput
            | RisksBlockersProviderInput
            | OpenQuestionsProviderInput
            | BuyingSignalsProviderInput
            | ObjectionsCompetitiveSignalsProviderInput
            | StakeholderIntelligenceProviderInput
        ),
    ) -> str:
        marker = "Untrusted transcript as a JSON string:\n"
        user_content = input_payload.messages[1].content
        marker_index = user_content.find(marker)
        if marker_index < 0:
            raise InvalidProviderRequestError
        encoded = user_content[marker_index + len(marker) :]
        try:
            transcript, _ = json.JSONDecoder().raw_decode(encoded)
        except (TypeError, ValueError) as exc:
            raise InvalidProviderRequestError from exc
        if not isinstance(transcript, str) or not transcript.strip():
            raise InvalidProviderRequestError
        return transcript.strip()

    @staticmethod
    def _extract_meeting_date(input_payload: ActionItemsProviderInput) -> datetime:
        prefix = "Meeting date as an ISO-8601 JSON string: "
        user_content = input_payload.messages[1].content
        marker_index = user_content.find(prefix)
        if marker_index < 0:
            raise InvalidProviderRequestError
        encoded = user_content[marker_index + len(prefix) :]
        try:
            value, _ = json.JSONDecoder().raw_decode(encoded)
            meeting_date = datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise InvalidProviderRequestError from exc
        if not isinstance(value, str):
            raise InvalidProviderRequestError
        return meeting_date

    @staticmethod
    def _summarise_transcript(transcript: str) -> str:
        normalised = " ".join(transcript.split())
        sentences = re.split(r"(?<=[.!?])\s+", normalised)
        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
        )
        grounded = [
            sentence
            for sentence in sentences
            if sentence and not any(marker in sentence.lower() for marker in injection_markers)
        ]
        excerpt = " ".join(grounded[:3]).strip()
        if not excerpt:
            return "The supplied transcript was reviewed, but it did not contain summarisable business discussion."
        if len(excerpt) > 600:
            excerpt = excerpt[:597].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
        return f"The meeting covered the following transcript-grounded points: {excerpt}"

    @staticmethod
    def _meeting_type(meeting_context: str, transcript: str) -> str:
        content = f"{meeting_context} {transcript}".lower()
        if any(term in content for term in ("demo", "walkthrough", "product tour")):
            return "sales_demo"
        if any(term in content for term in ("discovery", "requirements", "budget", "pain point")):
            return "sales_discovery"
        if any(term in content for term in ("customer success", "adoption", "renewal", "onboarding")):
            return "customer_success"
        if any(term in content for term in ("candidate", "interview", "recruitment", "role vacancy")):
            return "recruitment"
        if any(term in content for term in ("internal", "team meeting", "stand-up", "standup")):
            return "internal"
        return "other"

    @staticmethod
    def _sentiment(transcript: str) -> str:
        content = transcript.lower()
        positive = sum(
            content.count(term) for term in ("positive", "great", "happy", "agreed", "excited", "successful")
        )
        negative = sum(content.count(term) for term in ("negative", "concern", "blocked", "unhappy", "risk", "failed"))
        if positive and negative:
            return "mixed"
        if positive:
            return "positive"
        if negative:
            return "negative"
        return "neutral"

    @classmethod
    def _extract_decisions(cls, transcript: str) -> list[dict[str, JsonValue]]:
        normalised = " ".join(transcript.split())
        sentences = re.split(r"(?<=[.!?])\s+", normalised)
        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
        )
        decision_markers = (
            " decided ",
            " agreed ",
            " approved ",
            " committed ",
            " rejected ",
            " declined ",
            " deferred ",
            " postponed ",
            " will proceed ",
            " go ahead ",
        )
        decisions: list[dict[str, JsonValue]] = []
        for sentence in sentences:
            stripped = sentence.strip(" \t\r\n-•")
            lowered = f" {stripped.lower()} "
            if not stripped or any(marker in lowered for marker in injection_markers):
                continue
            if not any(marker in lowered for marker in decision_markers):
                continue
            status = cls._decision_status(lowered)
            owner = cls._decision_owner(stripped)
            decision = cls._bounded_plain_text(stripped, DECISION_MAX_LENGTH)
            evidence = cls._bounded_plain_text(
                f"The transcript records this as a {status} decision: {stripped}",
                DECISION_EVIDENCE_MAX_LENGTH,
            )
            decisions.append(
                {
                    "decision": decision,
                    "owner": owner,
                    "status": status,
                    "confidence": 0.9 if status in {"confirmed", "rejected"} else 0.78,
                    "evidence": evidence,
                }
            )
            if len(decisions) == DECISIONS_MAX_COUNT:
                break
        return decisions

    @staticmethod
    def _decision_status(content: str) -> str:
        if any(term in content for term in (" rejected ", " declined ")):
            return "rejected"
        if any(term in content for term in (" deferred ", " postponed ")):
            return "deferred"
        if any(term in content for term in (" tentatively ", " subject to ")):
            return "tentative"
        return "confirmed"

    @staticmethod
    def _decision_owner(sentence: str) -> str | None:
        match = re.match(
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+"
            r"(?:decided|agreed|approved|committed|rejected|declined|deferred|postponed)\b",
            sentence,
        )
        return match.group(1) if match is not None else None

    @classmethod
    def _extract_action_items(
        cls,
        transcript: str,
        meeting_date: datetime,
    ) -> list[dict[str, JsonValue]]:
        normalised = " ".join(transcript.split())
        sentences = re.split(r"(?<=[.!?])\s+", normalised)
        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
        )
        vague_markers = (
            "should consider",
            "maybe ",
            "it would be good",
            "can someone",
            "could someone",
            "pricing remains a concern",
        )
        action_items: list[dict[str, JsonValue]] = []
        for sentence in sentences:
            clauses = re.split(r"(?:;\s*|,?\s+and\s+)", sentence)
            for clause in clauses:
                stripped = clause.strip(" \t\r\n-•,.")
                lowered = stripped.lower()
                if (
                    not stripped
                    or any(marker in lowered for marker in injection_markers)
                    or any(marker in lowered for marker in vague_markers)
                ):
                    continue
                commitment = cls._action_commitment(stripped)
                if commitment is None:
                    continue
                owner, task_text = commitment
                due_expression = cls._action_due_expression(stripped)
                due_date = normalise_action_item_due_date(
                    due_expression,
                    meeting_date,
                )
                task = cls._normalise_action_task(task_text, due_expression)
                if len(task) < 5:
                    continue
                priority = cls._action_priority(lowered)
                evidence_parts = [f"The transcript supports the commitment to {task.rstrip('.').lower()}"]
                if owner is not None:
                    evidence_parts.append(f"by {owner}")
                if due_date is not None:
                    evidence_parts.append(f"due {due_date}")
                evidence = cls._bounded_plain_text(
                    " ".join(evidence_parts) + ".",
                    ACTION_ITEM_EVIDENCE_MAX_LENGTH,
                )
                action_items.append(
                    {
                        "task": task,
                        "owner": owner,
                        "due_date": due_date,
                        "priority": priority,
                        "status": "open",
                        "confidence": 0.92 if owner is not None and due_date is not None else 0.86,
                        "evidence": evidence,
                    }
                )
                if len(action_items) == ACTION_ITEMS_MAX_COUNT:
                    return action_items
        return action_items

    @staticmethod
    def _action_commitment(sentence: str) -> tuple[str | None, str] | None:
        name = r"[A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*){0,3}"
        patterns = (
            rf"^(?P<owner>{name}):\s+I\s+(?:will|shall|agreed to|committed to)\s+(?P<task>.+)$",
            rf"^(?:We\s+agreed\s+)?(?P<owner>{name})\s+(?:will|shall|would|agreed to|committed to|promised to|volunteered to)\s+(?P<task>.+)$",
            rf"^(?:Action item:\s*)?(?P<owner>{name})\s+to\s+(?P<task>.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, sentence)
            if match is None:
                continue
            owner = match.group("owner")
            if owner.lower() in {"we", "the", "someone", "somebody", "team"}:
                owner = None
            return owner, match.group("task")

        ownerless_patterns = (
            r"^(?:It was agreed|We agreed|The team agreed)(?: that)? (?:we |the team )?(?:will|would|to) (?P<task>.+)$",
            r"^An action was agreed(?: to)? (?P<task>.+)$",
        )
        for pattern in ownerless_patterns:
            match = re.match(pattern, sentence, flags=re.IGNORECASE)
            if match is not None:
                return None, match.group("task")
        return None

    @staticmethod
    def _action_due_expression(sentence: str) -> str | None:
        match = re.search(
            r"\b(?:by\s+)?(\d{4}-\d{2}-\d{2}|(?:the\s+)?end of (?:this|next) week|(?:this|next) (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|today|tomorrow)\b",
            sentence,
            flags=re.IGNORECASE,
        )
        return match.group(1) if match is not None else None

    @classmethod
    def _normalise_action_task(
        cls,
        value: str,
        due_expression: str | None,
    ) -> str:
        task = value.strip(" \t\r\n-•,.")
        if due_expression is not None:
            task = re.sub(
                rf"\s+by\s+(?:the\s+)?{re.escape(due_expression)}\s*$",
                "",
                task,
                flags=re.IGNORECASE,
            ).strip(" ,.")
        if task:
            task = task[0].upper() + task[1:]
        if task and task[-1] not in ".!?":
            task += "."
        return cls._bounded_plain_text(task, ACTION_ITEM_TASK_MAX_LENGTH)

    @staticmethod
    def _action_priority(content: str) -> str:
        if any(
            marker in content
            for marker in (
                "urgent",
                "asap",
                "blocking",
                "time-critical",
                "high priority",
            )
        ):
            return "high"
        if any(marker in content for marker in ("low priority", "not urgent", "when convenient")):
            return "low"
        return "medium"

    @classmethod
    def _extract_risks_blockers(
        cls,
        transcript: str,
    ) -> list[dict[str, JsonValue]]:
        normalised = " ".join(transcript.split())
        sentences = re.split(r"(?<=[.!?])\s+", normalised)
        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
        )
        risk_markers = (
            " risk",
            " blocker",
            " blocked",
            " may delay",
            " might delay",
            " could delay",
            " will delay",
            " prevent ",
            " cannot proceed",
            " unable to proceed",
            " not approved",
            " pending",
            " outstanding",
            " concern",
            " uncertainty",
            " uncertain",
            " objection",
            " resistance",
            " pressure",
            " dependency",
            " depends on",
            " lack of ",
            " missing ",
            " takes six weeks",
        )
        decision_or_action_markers = (
            " decided ",
            " agreed ",
            " approved ",
            " rejected ",
            " will send ",
            " will arrange ",
            " will provide ",
            " action item",
        )
        risks: list[dict[str, JsonValue]] = []
        for sentence in sentences:
            stripped = sentence.strip(" \t\r\n-•")
            lowered = f" {stripped.lower()} "
            if not stripped or any(marker in lowered for marker in injection_markers):
                continue
            has_consequence = any(marker in lowered for marker in risk_markers)
            if stripped.endswith("?") and not any(
                marker in lowered for marker in ("may delay", "could delay", "risk", "block")
            ):
                continue
            if any(marker in lowered for marker in decision_or_action_markers) and not has_consequence:
                continue
            if not has_consequence:
                continue

            category = cls._risk_category(lowered)
            severity = cls._risk_severity(lowered)
            owner = cls._risk_owner(stripped)
            risk = cls._bounded_plain_text(stripped, RISK_MAX_LENGTH)
            evidence = cls._bounded_plain_text(
                f"The transcript indicates this {category} concern could affect progress: {stripped}",
                RISK_EVIDENCE_MAX_LENGTH,
            )
            risks.append(
                {
                    "risk": risk,
                    "category": category,
                    "severity": severity,
                    "owner": owner,
                    "confidence": 0.92 if "block" in lowered or "will delay" in lowered else 0.84,
                    "evidence": evidence,
                }
            )
            if len(risks) == RISKS_BLOCKERS_MAX_COUNT:
                break
        return risks

    @staticmethod
    def _risk_category(content: str) -> str:
        categories = (
            ("budget", ("budget", "funding")),
            ("procurement", ("procurement", "purchasing")),
            ("legal", ("legal", "contract", "counsel")),
            ("security", ("security", "infosec", "privacy review")),
            ("integration", ("integration", "api", "connector")),
            ("technical", ("technical", "feasibility", "architecture")),
            ("timeline", ("timeline", "deadline", "delay", "six weeks")),
            ("implementation", ("implementation", "deployment", "rollout")),
            ("stakeholder", ("stakeholder", "decision maker", "resistance")),
            ("competitor", ("competitor", "competitive")),
            ("commercial", ("commercial", "pricing", "price", "terms")),
            ("resourcing", ("resource", "capacity", "staff")),
            ("dependency", ("dependency", "depends on")),
        )
        for category, markers in categories:
            if any(marker in content for marker in markers):
                return category
        return "other"

    @staticmethod
    def _risk_severity(content: str) -> str:
        if any(
            marker in content
            for marker in (
                " blocker",
                " blocked",
                " cannot proceed",
                " unable to proceed",
                " will delay",
                " materially delay",
                "critical",
                "six weeks",
            )
        ):
            return "high"
        if any(marker in content for marker in ("early warning", "limited concern", "minor risk", "low risk")):
            return "low"
        return "medium"

    @staticmethod
    def _risk_owner(sentence: str) -> str | None:
        patterns = (
            r"\bowner(?: is|:)?\s+(?P<owner>[A-Z][A-Za-z&' -]{1,80})(?:[.,;]|$)",
            r"\bowned by\s+(?P<owner>[A-Z][A-Za-z&' -]{1,80})(?:[.,;]|$)",
            r"\b(?P<owner>[A-Z][A-Za-z&' -]{1,80})\s+is responsible for resolving\b",
        )
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match is not None:
                return " ".join(match.group("owner").split())
        return None

    @classmethod
    def _extract_open_questions(
        cls,
        transcript: str,
    ) -> list[dict[str, JsonValue]]:
        normalised = " ".join(transcript.split())
        sentences = [
            sentence.strip(" \t\r\n-•\"'") for sentence in re.split(r"(?<=[.!?])\s+", normalised) if sentence.strip()
        ]
        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
            "prompt injection",
        )
        conversational_markers = (
            "how are you?",
            "how is everyone?",
            "how's everyone?",
            "how is it going?",
            "how's it going?",
            "can you hear me?",
            "can everyone see",
            "did you have a good weekend?",
            "do you have any questions?",
            "does anyone have any questions?",
            "any questions?",
        )
        rhetorical_markers = (
            "who knows?",
            "why bother?",
            "isn't it obvious?",
            "isn’t it obvious?",
            "what could possibly go wrong?",
            "do we really need to ask?",
        )
        questions: list[dict[str, JsonValue]] = []
        seen: set[str] = set()

        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            if any(marker in lowered for marker in injection_markers):
                continue

            question: str | None = None
            if sentence.endswith("?"):
                if any(marker in lowered for marker in conversational_markers):
                    continue
                if any(marker in lowered for marker in rhetorical_markers):
                    continue
                if cls._is_action_request_question(lowered):
                    continue
                if cls._is_ai_directed_question(lowered):
                    continue
                surrounding_sentences = sentences[:index] + sentences[index + 1 :]
                if cls._question_answered_elsewhere(sentence, surrounding_sentences):
                    continue
                question = cls._normalise_question(sentence)
            else:
                question = cls._question_from_unresolved_statement(sentence)

            if question is None:
                continue
            deduplication_key = question.casefold()
            if deduplication_key in seen:
                continue
            seen.add(deduplication_key)
            importance = cls._question_importance(lowered)
            questions.append(
                {
                    "question": question,
                    "owner": cls._question_owner(sentence),
                    "importance": importance,
                    "confidence": 0.91 if sentence.endswith("?") else 0.84,
                    "evidence": cls._bounded_plain_text(
                        (
                            "The transcript raises this question without a later answer."
                            if sentence.endswith("?")
                            else f"The transcript leaves this information unresolved: {sentence}"
                        ),
                        OPEN_QUESTION_EVIDENCE_MAX_LENGTH,
                    ),
                }
            )
            if len(questions) == OPEN_QUESTIONS_MAX_COUNT:
                break
        return questions

    @classmethod
    def _extract_buying_signals(cls, transcript: str) -> dict[str, JsonValue]:
        """Return deterministic demonstration fixtures, not production reasoning."""

        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
            "prompt injection",
        )
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(transcript.split()))
        content = " ".join(
            sentence.lower()
            for sentence in sentences
            if not any(marker in sentence.lower() for marker in injection_markers)
        )
        if any(
            marker in content
            for marker in (
                "polite interest only",
                "this looks good",
                "thanks for the demo",
                "interesting product",
                "no buying signals",
            )
        ) and not any(
            marker in content for marker in ("approved budget", "budget is approved", "next meeting is", "will proceed")
        ):
            return cls._insufficient_buying_signals()

        signals: list[dict[str, JsonValue]] = []

        def add(
            signal_type: str,
            polarity: str,
            strength: str,
            evidence: str,
            confidence: float,
        ) -> None:
            if any(item["signal_type"] == signal_type for item in signals):
                return
            if len(signals) < BUYING_SIGNALS_MAX_COUNT:
                signals.append(
                    {
                        "signal_type": signal_type,
                        "polarity": polarity,
                        "strength": strength,
                        "confidence": confidence,
                        "evidence": evidence,
                    }
                )

        if any(marker in content for marker in ("approved budget", "budget is approved", "budget confirmed")):
            add("budget_confirmed", "positive", "strong", "The customer confirmed that budget is approved.", 0.96)
        if any(
            marker in content
            for marker in (
                "budget is not approved",
                "budget remains unconfirmed",
                "no budget owner",
                "budget unconfirmed",
            )
        ):
            add("budget_unconfirmed", "negative", "moderate", "The budget or approval path remains unconfirmed.", 0.91)
        if any(
            marker in content
            for marker in (
                "timeline confirmed",
                "implementation date confirmed",
                "september pilot",
                "start in september",
            )
        ):
            add("timeline_confirmed", "positive", "strong", "The customer confirmed a target delivery timeline.", 0.94)
        if any(
            marker in content
            for marker in ("timeline is unclear", "timeline remains vague", "no target date", "unclear timeline")
        ):
            add(
                "timeline_unclear",
                "negative",
                "moderate",
                "The meeting did not establish a reliable target timeline.",
                0.9,
            )
        if any(
            marker in content
            for marker in (
                "decision-maker confirmed",
                "decision maker confirmed",
                "economic buyer approved",
                "final decision-maker agreed",
            )
        ):
            add(
                "decision_maker_engaged",
                "positive",
                "strong",
                "The final decision-maker actively confirmed the proposed direction.",
                0.95,
            )
        if any(
            marker in content
            for marker in (
                "decision-maker was absent",
                "decision maker was absent",
                "no access to the decision-maker",
                "decision maker missing",
            )
        ):
            add(
                "decision_maker_missing",
                "negative",
                "moderate",
                "The decision-maker was absent and no access path was established.",
                0.91,
            )
        if any(
            marker in content
            for marker in ("champion identified", "advocate internally", "will champion", "internal champion")
        ):
            add(
                "champion_identified",
                "positive",
                "moderate",
                "A participant committed to advocate internally for the solution.",
                0.9,
            )
        if any(marker in content for marker in ("no internal champion", "champion not evident")):
            add(
                "champion_not_evident",
                "negative",
                "moderate",
                "The discussion established that no internal champion is currently evident.",
                0.87,
            )
        if any(
            marker in content for marker in ("procurement has started", "procurement is active", "entered procurement")
        ):
            add(
                "procurement_active",
                "positive",
                "strong",
                "The customer confirmed that the formal procurement process has started.",
                0.95,
            )
        if any(
            marker in content
            for marker in ("procurement is unclear", "procurement process is unknown", "procurement unclear")
        ):
            add("procurement_unclear", "negative", "moderate", "The procurement process and path remain unclear.", 0.88)
        if any(
            marker in content
            for marker in (
                "prefer the competitor",
                "competitor is preferred",
                "evaluating a competitor",
                "competitor present",
            )
        ):
            add(
                "competitor_present",
                "negative",
                "moderate",
                "The customer is actively considering or prefers a competing option.",
                0.9,
            )
        if any(marker in content for marker in ("no competitors under consideration", "competitor absent")):
            add(
                "competitor_absent",
                "positive",
                "weak",
                "The customer confirmed that no competing option is under consideration.",
                0.82,
            )
        if any(
            marker in content for marker in ("urgent requirement", "must launch", "time-critical", "urgency present")
        ):
            add(
                "urgency_present",
                "positive",
                "moderate",
                "The customer described a time-bound need to make progress.",
                0.88,
            )
        if any(marker in content for marker in ("no urgency", "urgency absent")):
            add(
                "urgency_absent",
                "neutral",
                "weak",
                "The customer explicitly indicated that the initiative is not urgent.",
                0.82,
            )
        if any(
            marker in content
            for marker in ("intent to proceed", "ready to purchase", "will proceed", "commercial intent")
        ):
            add(
                "commercial_intent",
                "positive",
                "strong",
                "The customer stated a clear intention to proceed commercially.",
                0.95,
            )
        if any(
            marker in content
            for marker in (
                "implementation team committed",
                "implementation resources committed",
                "resources are committed",
            )
        ):
            add(
                "implementation_commitment",
                "positive",
                "strong",
                "The customer committed resources for implementation.",
                0.93,
            )
        if any(
            marker in content
            for marker in (
                "next meeting is booked",
                "next meeting is scheduled",
                "committed next step",
                "next step committed",
            )
        ):
            add(
                "next_step_committed",
                "positive",
                "strong",
                "The customer committed to a defined next meeting or deliverable.",
                0.96,
            )
        if any(
            marker in content
            for marker in ("maybe meet again", "no committed next step", "next step is vague", "weak next step")
        ):
            add(
                "next_step_weak", "negative", "moderate", "The meeting ended without a firm next-step commitment.", 0.89
            )
        if any(marker in content for marker in ("stakeholders aligned", "stakeholder alignment")):
            add(
                "stakeholder_alignment",
                "positive",
                "moderate",
                "The relevant stakeholders expressed an aligned direction.",
                0.89,
            )
        if any(marker in content for marker in ("stakeholders disagree", "stakeholder misalignment")):
            add(
                "stakeholder_misalignment",
                "negative",
                "strong",
                "Material stakeholder disagreement remains unresolved.",
                0.93,
            )
        if any(
            marker in content
            for marker in ("technical fit confirmed", "technical requirements are met", "feasibility confirmed")
        ):
            add(
                "technical_fit_confirmed",
                "positive",
                "strong",
                "The customer confirmed that the solution meets the technical requirements.",
                0.94,
            )
        if any(
            marker in content
            for marker in ("technical uncertainty", "technical fit uncertain", "feasibility remains unresolved")
        ):
            add("technical_fit_uncertain", "negative", "moderate", "Technical feasibility remains unresolved.", 0.91)
        if any(
            marker in content
            for marker in (
                "security review is progressing",
                "legal review is progressing",
                "security approved",
                "legal approved",
            )
        ):
            add(
                "security_or_legal_progress",
                "positive",
                "moderate",
                "Security or legal review is demonstrably progressing.",
                0.91,
            )
        if any(
            marker in content
            for marker in (
                "legal approval blocks",
                "security review blocks",
                "legal blocker",
                "security blocker",
                "cannot sign until legal",
            )
        ):
            add(
                "security_or_legal_blocker",
                "negative",
                "strong",
                "Outstanding security or legal approval materially blocks progress.",
                0.95,
            )
        if "neutral meeting" in content and not signals:
            add(
                "other",
                "neutral",
                "weak",
                "The discussion contained a neutral deal-context observation without a commitment.",
                0.72,
            )

        if not signals:
            return cls._insufficient_buying_signals()

        polarities = {str(item["polarity"]) for item in signals}
        has_strong_positive = any(item["polarity"] == "positive" and item["strength"] == "strong" for item in signals)
        has_strong_negative = any(item["polarity"] == "negative" and item["strength"] == "strong" for item in signals)
        if polarities <= {"neutral"}:
            momentum = "neutral"
            summary = "The current meeting contains neutral evidence without a clear direction of deal momentum."
            confidence = 0.72
        elif "positive" in polarities and "negative" in polarities:
            momentum = "neutral"
            summary = "The current meeting contains mixed positive and negative signals, so momentum is neutral."
            confidence = 0.82
        elif "positive" in polarities:
            momentum = "strong_positive" if has_strong_positive else "positive"
            summary = (
                "The current meeting shows strong positive momentum based on the extracted positive signals."
                if has_strong_positive
                else "The current meeting shows positive momentum based on the extracted positive signals."
            )
            confidence = 0.91
        else:
            momentum = "strong_negative" if has_strong_negative else "negative"
            summary = (
                "The current meeting shows strong negative momentum based on the extracted negative signals."
                if has_strong_negative
                else "The current meeting shows negative momentum based on the extracted negative signals."
            )
            confidence = 0.9
        return {
            "signals": cast(JsonValue, signals),
            "overall_momentum": momentum,
            "momentum_summary": summary,
            "confidence": confidence,
        }

    @staticmethod
    def _insufficient_buying_signals() -> dict[str, JsonValue]:
        return {
            "signals": [],
            "overall_momentum": "insufficient_evidence",
            "momentum_summary": "There was not enough transcript evidence to assess deal momentum reliably.",
            "confidence": 0.35,
        }

    @classmethod
    def _extract_objections_competitive_signals(
        cls,
        transcript: str,
    ) -> dict[str, JsonValue]:
        """Return bounded deterministic fixtures, not production reasoning."""

        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
            "prompt injection",
        )
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", " ".join(transcript.split()))
            if sentence.strip() and not any(marker in sentence.casefold() for marker in injection_markers)
        ]
        lowered_transcript = " ".join(sentences).casefold()
        objections: list[dict[str, JsonValue]] = []
        competitors: list[dict[str, JsonValue]] = []
        seen_objections: set[str] = set()
        seen_competitors: set[str] = set()

        resistance_markers = (
            "too expensive",
            "price is too high",
            "pricing is too high",
            "cannot afford",
            "can't afford",
            "unacceptable",
            "would prevent",
            "will prevent",
            "blocks adoption",
            "block adoption",
            "cannot proceed",
            "can't proceed",
            "will not proceed",
            "deal-breaker",
            "deal breaker",
            "concerned that",
            "concern about",
            "security concern",
            "privacy concern",
            "hesitant",
            "hesitation",
            "objected",
            "objection",
            "too many internal resources",
            "could not support a six-month rollout",
            "could not support the rollout",
            "prefer the competitor",
            "competitor is preferred",
            "lack of sso",
            "missing sso",
        )
        for sentence in sentences:
            lowered = sentence.casefold()
            if any(
                marker in lowered
                for marker in (
                    "no objections were raised",
                    "no objections or competitors",
                    "no objections and no competitors",
                    "no competitive signals",
                )
            ):
                continue
            competitor_name = cls._mock_competitor_name(sentence)
            if (
                competitor_name is not None
                and competitor_name.casefold() not in seen_competitors
                and len(competitors) < COMPETITORS_MAX_COUNT
            ):
                position = cls._mock_competitor_position(lowered)
                competitors.append(
                    {
                        "name": competitor_name,
                        "position": position,
                        "confidence": 0.9 if position in {"stronger", "weaker"} else 0.82,
                        "evidence": cls._bounded_plain_text(
                            f"The transcript identifies {competitor_name} in the customer's evaluation context.",
                            OBJECTION_EVIDENCE_MAX_LENGTH,
                        ),
                    }
                )
                seen_competitors.add(competitor_name.casefold())

            if not any(marker in lowered for marker in resistance_markers):
                continue
            if sentence.endswith("?") and not any(
                marker in lowered for marker in ("would prevent", "will prevent", "cannot proceed", "can't proceed")
            ):
                continue
            category = cls._mock_objection_category(lowered)
            status = cls._mock_objection_status(lowered)
            strength = cls._mock_objection_strength(lowered)
            category_label = category.replace("_", " ")
            objection_text = cls._bounded_plain_text(
                f"The customer raised a {category_label} objection.",
                OBJECTION_MAX_LENGTH,
            )
            key = objection_text.casefold()
            if key in seen_objections:
                continue
            objections.append(
                {
                    "objection": objection_text,
                    "category": category,
                    "status": status,
                    "strength": strength,
                    "owner": cls._mock_objection_owner(lowered),
                    "confidence": 0.94 if strength == "strong" else 0.86 if strength == "moderate" else 0.76,
                    "evidence": cls._bounded_plain_text(
                        f"The transcript records expressed buyer resistance about {category_label}.",
                        OBJECTION_EVIDENCE_MAX_LENGTH,
                    ),
                }
            )
            seen_objections.add(key)
            if len(objections) == OBJECTIONS_MAX_COUNT:
                break

        if not objections and not competitors:
            explicit_none = any(
                marker in lowered_transcript
                for marker in (
                    "no objections or competitors",
                    "no objections and no competitors",
                    "no objections were raised",
                    "no competitive signals",
                )
            )
            return {
                "objections": [],
                "competitors": [],
                "overall_objection_pressure": "none" if explicit_none else "insufficient_evidence",
                "summary": (
                    "No objections or competitive signals were identified in the current meeting."
                    if explicit_none
                    else "There was not enough transcript evidence to identify objection pressure reliably."
                ),
            }

        strong_unresolved_count = sum(
            item["strength"] == "strong" and item["status"] == "unresolved" for item in objections
        )
        if strong_unresolved_count >= 2:
            pressure = "severe"
        elif strong_unresolved_count == 1 or any(item["position"] == "stronger" for item in competitors):
            pressure = "high"
        elif any(
            item["status"] in {"unresolved", "partially_addressed"} and item["strength"] == "moderate"
            for item in objections
        ):
            pressure = "medium"
        else:
            pressure = "low"
        return {
            "objections": cast(JsonValue, objections),
            "competitors": cast(JsonValue, competitors),
            "overall_objection_pressure": pressure,
            "summary": (f"Validated extracted items indicate {pressure} current meeting objection pressure."),
        }

    @staticmethod
    def _mock_objection_category(content: str) -> str:
        category_markers: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("pricing", ("price", "pricing", "expensive")),
            ("budget", ("budget", "afford")),
            ("legal", ("legal", "contract terms")),
            ("security", ("security", "sso")),
            ("privacy", ("privacy", "data residency")),
            ("integration", ("integration", "integrate")),
            ("implementation", ("implementation", "rollout")),
            ("resourcing", ("resources", "resourcing", "capacity")),
            ("procurement", ("procurement",)),
            ("timeline", ("timeline", "timing", "deadline")),
            ("product_fit", ("product fit", "feature gap")),
            ("stakeholder", ("stakeholder", "executive sponsor")),
            ("change_management", ("change management", "adoption")),
            ("competitor", ("competitor", "another vendor", "alternative vendor")),
            ("trust", ("trust", "credibility")),
            ("technical", ("technical",)),
            ("commercial", ("commercial", "terms")),
        )
        for category, markers in category_markers:
            if any(marker in content for marker in markers):
                return category
        return "other"

    @staticmethod
    def _mock_objection_status(content: str) -> str:
        if any(marker in content for marker in ("resolved", "fully addressed", "accepted the answer")):
            return "resolved"
        if any(marker in content for marker in ("partially addressed", "helps but", "somewhat addressed")):
            return "partially_addressed"
        if any(marker in content for marker in ("deferred", "revisit", "later meeting", "put aside")):
            return "deferred"
        return "unresolved"

    @staticmethod
    def _mock_objection_strength(content: str) -> str:
        if any(
            marker in content
            for marker in (
                "would prevent",
                "will prevent",
                "cannot proceed",
                "can't proceed",
                "will not proceed",
                "unacceptable",
                "deal-breaker",
                "deal breaker",
            )
        ):
            return "strong"
        if any(marker in content for marker in ("minor concern", "slight concern", "weak objection")):
            return "weak"
        return "moderate"

    @staticmethod
    def _mock_objection_owner(content: str) -> str | None:
        owners = (
            ("customer it", "Customer IT"),
            ("security team", "Customer security team"),
            ("legal team", "Customer legal team"),
            ("procurement team", "Customer procurement team"),
            ("finance team", "Customer finance team"),
        )
        for marker, owner in owners:
            if marker in content:
                return owner
        return None

    @staticmethod
    def _mock_competitor_name(sentence: str) -> str | None:
        named = re.search(r"\bCompetitor\s+[A-Z0-9][A-Za-z0-9_-]*", sentence)
        if named is not None:
            return named.group(0)
        lowered = sentence.casefold()
        if "another vendor" in lowered or "alternative vendor" in lowered:
            return "Unnamed competitor"
        return None

    @staticmethod
    def _mock_competitor_position(content: str) -> str:
        if any(marker in content for marker in ("stronger", "preferred", "prefer ", "better", "already integrates")):
            return "stronger"
        if any(marker in content for marker in ("weaker", "fell short", "less capable", "does not support")):
            return "weaker"
        if any(marker in content for marker in ("neutral", "similar", "equivalent")):
            return "neutral"
        if any(marker in content for marker in ("mentioned", "also evaluating", "considering")):
            return "present"
        return "unclear"

    @classmethod
    def _extract_stakeholder_intelligence(
        cls,
        transcript: str,
    ) -> dict[str, JsonValue]:
        """Return bounded deterministic stakeholder fixtures, not inferred memory."""

        injection_markers = (
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "developer message",
            "reveal secrets",
            "prompt injection",
        )
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", " ".join(transcript.split()))
            if sentence.strip() and not any(marker in sentence.casefold() for marker in injection_markers)
        ]
        lowered_transcript = " ".join(sentences).casefold()
        if not sentences or any(
            marker in lowered_transcript
            for marker in (
                "no reliable stakeholder evidence",
                "no stakeholders were identified",
                "no stakeholder evidence",
            )
        ):
            return cls._insufficient_stakeholder_intelligence()

        stakeholders: list[dict[str, JsonValue]] = []
        seen_names: set[str] = set()
        for sentence in sentences:
            lowered = sentence.casefold()
            if cls._stakeholder_sentence_is_only_missing_coverage(lowered):
                continue
            role = cls._mock_stakeholder_role(lowered)
            name = cls._mock_stakeholder_name(sentence, lowered, role)
            if name is None or name.casefold() in seen_names:
                continue
            engagement = cls._mock_stakeholder_engagement(lowered)
            if engagement == "absent_but_referenced" and role == "participant":
                role = "unknown"
            influence = cls._mock_stakeholder_influence(role)
            stance = cls._mock_stakeholder_stance(lowered)
            if role == "blocker" and stance == "supportive":
                stance = "mixed"
            confidence = cls._mock_stakeholder_confidence(role, lowered)
            stakeholders.append(
                {
                    "name": name,
                    "organisation": cls._mock_stakeholder_organisation(lowered),
                    "role": role,
                    "influence": influence,
                    "stance": stance,
                    "engagement": engagement,
                    "confidence": confidence,
                    "evidence": cls._bounded_plain_text(
                        cls._mock_stakeholder_evidence(role, engagement),
                        STAKEHOLDER_EVIDENCE_MAX_LENGTH,
                    ),
                }
            )
            seen_names.add(name.casefold())
            if len(stakeholders) == STAKEHOLDERS_MAX_COUNT:
                break

        if not stakeholders:
            return cls._insufficient_stakeholder_intelligence()

        roles = {str(item["role"]) for item in stakeholders}
        role_coverage = {
            "economic_buyer": cls._mock_role_coverage(
                roles,
                {"economic_buyer"},
                lowered_transcript,
                ("economic buyer", "budget approval", "final budget", "cfo", "finance"),
            ),
            "decision_maker": cls._mock_role_coverage(
                roles,
                {"decision_maker"},
                lowered_transcript,
                ("decision maker", "final decision", "final selection", "approve or reject"),
            ),
            "champion": cls._mock_role_coverage(
                roles,
                {"champion"},
                lowered_transcript,
                ("champion", "advocate", "internal support", "present internally"),
            ),
            "technical_buyer": cls._mock_role_coverage(
                roles,
                {"technical_buyer"},
                lowered_transcript,
                ("technical buyer", "technical approval", "architecture approval", "cto"),
            ),
            "procurement": cls._mock_role_coverage(
                roles,
                {"procurement"},
                lowered_transcript,
                ("procurement",),
            ),
            "legal_security": cls._mock_role_coverage(
                roles,
                {"legal", "security"},
                lowered_transcript,
                ("legal", "security"),
            ),
        }
        identified = [key.replace("_", " ") for key, value in role_coverage.items() if value == "identified"]
        unresolved = [
            key.replace("_", " ") for key, value in role_coverage.items() if value in {"not_identified", "unclear"}
        ]
        if identified:
            summary = f"Current meeting evidence identifies {', '.join(identified)} involvement."
        else:
            summary = "Current meeting evidence identifies relevant participants without a stronger buying role."
        if unresolved:
            summary += f" The {', '.join(unresolved)} coverage remains unclear or not identified."
        confidence_values = [cast(float, item["confidence"]) for item in stakeholders]
        confidence = round(sum(confidence_values) / len(confidence_values), 2)
        return {
            "stakeholders": cast(JsonValue, stakeholders),
            "role_coverage": cast(JsonValue, role_coverage),
            "stakeholder_summary": summary,
            "confidence": confidence,
        }

    @staticmethod
    def _stakeholder_sentence_is_only_missing_coverage(content: str) -> bool:
        missing_markers = (
            "not identified",
            "not yet identified",
            "still need to identify",
            "do not know who",
            "don't know who",
            "unknown who",
            "unclear who",
            "not discussed",
        )
        if any(marker in content for marker in missing_markers):
            return True
        coverage_subjects = (
            "economic buyer",
            "decision maker",
            "champion",
            "technical buyer",
            "procurement path",
            "legal path",
            "security path",
        )
        return any(subject in content for subject in coverage_subjects) and any(
            marker in content for marker in ("is unclear", "remains unclear", "was unclear")
        )

    @staticmethod
    def _mock_stakeholder_role(content: str) -> str:
        role_markers: tuple[tuple[str, tuple[str, ...]], ...] = (
            (
                "economic_buyer",
                (
                    "controls final budget",
                    "controls the final budget",
                    "final budget approval",
                    "financial approval authority",
                    "owns final financial approval",
                ),
            ),
            (
                "decision_maker",
                (
                    "make the final selection",
                    "makes the final selection",
                    "will make the final decision",
                    "has final decision authority",
                    "can approve or reject",
                ),
            ),
            (
                "champion",
                (
                    "present the proposal internally",
                    "present it internally",
                    "secure internal support",
                    "build internal support",
                    "advocate internally",
                    "advocated for the solution",
                    "acting as champion",
                ),
            ),
            (
                "blocker",
                (
                    "cannot proceed",
                    "can't proceed",
                    "could not proceed",
                    "would prevent",
                    "will prevent",
                    "actively blocked",
                    "deal-breaker",
                    "deal breaker",
                ),
            ),
            (
                "technical_buyer",
                (
                    "must approve the technical",
                    "controls technical approval",
                    "technical architecture approval",
                    "approve the technical architecture",
                ),
            ),
            (
                "technical_evaluator",
                (
                    "reviewing compatibility",
                    "review compatibility",
                    "assess technical fit",
                    "assessing technical fit",
                    "technical evaluation",
                ),
            ),
            ("procurement", ("procurement",)),
            ("legal", ("legal counsel", "legal representative", "legal team")),
            ("security", ("security director", "security representative", "security team")),
            ("finance", ("finance representative", "finance team")),
            ("executive_sponsor", ("executive sponsor",)),
            ("implementation_owner", ("implementation owner", "owns implementation")),
            ("vendor_representative", ("vendor representative", "our account executive")),
            ("end_user", ("end user", "daily user")),
            (
                "influencer",
                (
                    "provided evaluation feedback",
                    "shapes the evaluation",
                    "influences the evaluation",
                    "influencer",
                ),
            ),
            (
                "participant",
                (
                    "attended",
                    "asked a feature question",
                    "asked whether",
                    "thanked us",
                    "praised the feature",
                    "receive a proposal",
                    "joined the meeting",
                ),
            ),
        )
        for role, markers in role_markers:
            if any(marker in content for marker in markers):
                return role
        return "unknown"

    @staticmethod
    def _mock_stakeholder_name(sentence: str, content: str, role: str) -> str | None:
        named = re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", sentence)
        if named is not None:
            candidate = named.group(0)
            if candidate.casefold() not in {
                "current meeting",
                "customer procurement",
                "customer security",
                "customer legal",
            }:
                return candidate
        role_labels = (
            ("chief financial officer", "Customer CFO"),
            ("cfo", "Customer CFO"),
            ("chief operating officer", "Customer COO"),
            ("coo", "Customer COO"),
            ("chief technology officer", "Customer CTO"),
            ("cto", "Customer CTO"),
            ("security director", "Customer security director"),
            ("architect", "Customer architect"),
            ("procurement", "Customer procurement representative"),
            ("legal", "Customer legal representative"),
            ("security", "Customer security representative"),
            ("finance", "Customer finance representative"),
            ("unnamed it", "Unnamed IT stakeholder"),
            ("it stakeholder", "Unnamed IT stakeholder"),
        )
        for marker, label in role_labels:
            if marker in content:
                return label
        if role != "unknown" and any(marker in content for marker in ("customer", "stakeholder", "representative")):
            return f"Customer {role.replace('_', ' ')}"
        return None

    @staticmethod
    def _mock_stakeholder_organisation(content: str) -> str | None:
        if any(marker in content for marker in ("our account executive", "our vendor", "vendor representative")):
            return "RevenueOS"
        if any(marker in content for marker in ("customer", "their ", "cfo", "coo", "cto", "procurement")):
            return "Customer"
        return None

    @staticmethod
    def _mock_stakeholder_engagement(content: str) -> str:
        if any(
            marker in content
            for marker in (
                "not present",
                "wasn't present",
                "was not present",
                "not in the meeting",
                "could not attend",
                "couldn't attend",
                "absent",
                "will review later",
            )
        ):
            return "absent_but_referenced"
        if any(marker in content for marker in ("listened", "observed", "attended quietly", "passive")):
            return "passive"
        if any(
            marker in content
            for marker in (
                "said",
                "stated",
                "confirmed",
                "asked",
                "advocated",
                "committed",
                "objected",
                "presented",
                "provided",
            )
        ):
            return "active"
        return "unclear"

    @staticmethod
    def _mock_stakeholder_stance(content: str) -> str:
        if any(marker in content for marker in ("mixed stance", "mixed view", "both supported and opposed")):
            return "mixed"
        if any(
            marker in content
            for marker in (
                "cannot proceed",
                "can't proceed",
                "would prevent",
                "will prevent",
                "opposed",
                "resistant",
                "rejected",
                "deal-breaker",
            )
        ):
            return "resistant"
        if any(
            marker in content
            for marker in (
                "advocated",
                "secure internal support",
                "build internal support",
                "supported the solution",
                "recommended the solution",
            )
        ):
            return "supportive"
        if any(marker in content for marker in ("neutral", "provided evaluation feedback", "reviewing")):
            return "neutral"
        return "unclear"

    @staticmethod
    def _mock_stakeholder_influence(role: str) -> str:
        if role in {"economic_buyer", "decision_maker", "champion", "blocker", "technical_buyer"}:
            return "high"
        if role in {
            "influencer",
            "technical_evaluator",
            "procurement",
            "legal",
            "security",
            "finance",
            "executive_sponsor",
            "implementation_owner",
        }:
            return "medium"
        if role in {"end_user", "vendor_representative", "participant"}:
            return "low"
        return "unclear"

    @staticmethod
    def _mock_stakeholder_confidence(role: str, content: str) -> float:
        if role == "unknown":
            return 0.5
        if any(marker in content for marker in ("may be", "might be", "possibly", "ambiguous")):
            return 0.6
        if role == "participant":
            return 0.72
        return 0.9

    @staticmethod
    def _mock_stakeholder_evidence(role: str, engagement: str) -> str:
        role_label = role.replace("_", " ")
        if engagement == "absent_but_referenced":
            return f"The transcript explicitly references an absent stakeholder with {role_label} evidence."
        if role == "participant":
            return "The person participated, but the transcript does not support a stronger buying role."
        if role == "unknown":
            return "The person was explicitly referenced, but the transcript does not establish a reliable role."
        return f"The transcript contains explicit current-meeting evidence supporting the {role_label} classification."

    @staticmethod
    def _mock_role_coverage(
        roles: set[str],
        supported_roles: set[str],
        transcript: str,
        markers: tuple[str, ...],
    ) -> str:
        if not roles.isdisjoint(supported_roles):
            return "identified"
        relevant_fragments = tuple(
            fragment
            for fragment in re.split(r"(?<=[.!?])\s+", transcript)
            if any(marker in fragment for marker in markers)
        )
        if not relevant_fragments:
            return "not_discussed"
        if any(
            missing_marker in fragment
            for fragment in relevant_fragments
            for missing_marker in (
                "not identified",
                "not yet identified",
                "still need to identify",
                "do not know who",
                "don't know who",
                "unknown who",
                "missing",
            )
        ):
            return "not_identified"
        return "unclear"

    @staticmethod
    def _insufficient_stakeholder_intelligence() -> dict[str, JsonValue]:
        return {
            "stakeholders": [],
            "role_coverage": {
                "economic_buyer": "not_discussed",
                "decision_maker": "not_discussed",
                "champion": "not_discussed",
                "technical_buyer": "not_discussed",
                "procurement": "not_discussed",
                "legal_security": "not_discussed",
            },
            "stakeholder_summary": "There was not enough evidence to identify stakeholder roles reliably.",
            "confidence": 0.3,
        }

    @staticmethod
    def _is_action_request_question(content: str) -> bool:
        if re.match(r"^(?:can|could|would|will)\s+(?:you|we|they)\b", content) is None:
            return False
        return any(
            marker in content
            for marker in (
                " send ",
                " share ",
                " provide ",
                " arrange ",
                " schedule ",
                " book ",
                " email ",
                " call ",
                " follow up",
                " update ",
                " create ",
            )
        )

    @staticmethod
    def _is_ai_directed_question(content: str) -> bool:
        return any(
            marker in content
            for marker in (
                "ai,",
                "assistant,",
                "chatgpt",
                "language model",
                "system prompt",
                "what are your instructions",
            )
        )

    @classmethod
    def _question_answered_elsewhere(
        cls,
        question: str,
        surrounding_sentences: list[str],
    ) -> bool:
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "been",
            "by",
            "did",
            "do",
            "does",
            "for",
            "has",
            "have",
            "how",
            "is",
            "it",
            "of",
            "on",
            "or",
            "our",
            "the",
            "their",
            "this",
            "to",
            "was",
            "were",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "will",
        }
        keywords = {
            token for token in re.findall(r"[a-z0-9]+", question.lower()) if len(token) >= 3 and token not in stop_words
        }
        if not keywords:
            return False
        answer_markers = (
            " yes",
            " no",
            "approved",
            "confirmed",
            "decided",
            "resolved",
            "completed",
            "rejected",
            "owns",
            "responsible",
            "the answer",
            " is ",
            " are ",
            " will ",
            " has ",
            " have ",
        )
        for context_sentence in surrounding_sentences:
            lowered = f" {context_sentence.lower()} "
            overlap = sum(1 for keyword in keywords if keyword in lowered)
            if overlap >= min(2, len(keywords)) and any(marker in lowered for marker in answer_markers):
                return True
        return False

    @classmethod
    def _normalise_question(cls, value: str) -> str:
        question = " ".join(value.split()).strip(" \"'")
        if question:
            question = question[0].upper() + question[1:]
        if len(question) <= OPEN_QUESTION_MAX_LENGTH:
            return question
        shortened = question[: OPEN_QUESTION_MAX_LENGTH - 1].rsplit(" ", 1)[0].rstrip(" ,;:.!?")
        return f"{shortened}?"

    @classmethod
    def _question_from_unresolved_statement(cls, sentence: str) -> str | None:
        lowered = sentence.lower()
        unresolved_markers = (
            " unclear",
            " unknown",
            " unresolved",
            " outstanding",
            " pending",
            " not confirmed",
            " unconfirmed",
            " to be determined",
            " yet to be decided",
            " still need to know",
            " don't know",
            " do not know",
        )
        if not any(marker in lowered for marker in unresolved_markers):
            return None
        if any(
            marker in lowered
            for marker in (
                " risk",
                " may delay",
                " might delay",
                " could delay",
                " will delay",
            )
        ):
            return None

        unknown_match = re.search(
            r"\b(?:we\s+)?(?:still\s+)?(?:do not|don't)\s+know\s+(?P<subject>.+?)[.!]?$",
            sentence,
            flags=re.IGNORECASE,
        )
        if unknown_match is not None:
            subject = unknown_match.group("subject").strip(" .")
            return cls._normalise_question(f"What is {subject}?")

        subject_match = re.search(
            r"(?P<subject>.+?)\s+(?:is|remains|was)\s+(?:still\s+)?"
            r"(?:unclear|unknown|unresolved|outstanding|pending|unconfirmed|not confirmed)"
            r"[.!]?$",
            sentence,
            flags=re.IGNORECASE,
        )
        if subject_match is None:
            return None
        subject = subject_match.group("subject").strip(" .")
        if "approval" in subject.lower():
            return cls._normalise_question(f"When will {subject} be completed?")
        if any(marker in subject.lower() for marker in ("owner", "responsibility", "responsible")):
            return cls._normalise_question(f"Who is responsible for {subject}?")
        return cls._normalise_question(f"What is the confirmed position on {subject}?")

    @staticmethod
    def _question_owner(sentence: str) -> str | None:
        patterns = (
            r"\bowner(?: is|:)?\s+(?P<owner>[A-Z][A-Za-z&' -]{1,80})(?:[.,;:?]|$)",
            r"\banswer expected from\s+(?P<owner>[A-Z][A-Za-z&' -]{1,80})(?:[.,;:?]|$)",
            r"\b(?P<owner>[A-Z][A-Za-z&' -]{1,80})\s+(?:must|needs to)\s+(?:answer|confirm|clarify)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match is not None:
                return " ".join(match.group("owner").split())
        return None

    @staticmethod
    def _question_importance(content: str) -> str:
        if any(
            marker in content
            for marker in (
                "block",
                "cannot proceed",
                "can't proceed",
                "legal approval",
                "contract signature",
                "budget approval",
                "security approval",
                "commercial outcome",
                "implementation depends",
                "deadline",
                "critical timeline",
            )
        ):
            return "high"
        if any(
            marker in content
            for marker in (
                "nice to know",
                "when convenient",
                "limited impact",
                "optional",
                "low priority",
            )
        ):
            return "low"
        return "medium"

    @staticmethod
    def _bounded_plain_text(value: str, maximum_length: int) -> str:
        normalised = " ".join(value.split()).strip()
        if len(normalised) <= maximum_length:
            return normalised
        shortened = normalised[: maximum_length - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
        return f"{shortened}…"

    @staticmethod
    def _schema_invalid_output(request: ProviderRequest) -> dict[str, JsonValue]:
        if request.job_type == AIJobType.INFRASTRUCTURE_TEST.value:
            return {
                "status": "invalid",
                "message": "This output is deterministically schema-invalid.",
            }
        if request.job_type == AIJobType.EXECUTIVE_SUMMARY.value:
            return {
                "executive_summary": "Too short.",
                "meeting_type": "unsupported",
                "sentiment": "neutral",
                "confidence": 2,
            }
        if request.job_type == AIJobType.ACTION_ITEMS.value:
            return {
                "action_items": [
                    {
                        "task": "",
                        "owner": "",
                        "due_date": "2026-02-30",
                        "priority": "urgent",
                        "status": "completed",
                        "confidence": 2,
                        "evidence": "",
                    }
                ]
            }
        if request.job_type == AIJobType.RISKS_BLOCKERS.value:
            return {
                "risks": [
                    {
                        "risk": "",
                        "category": "unsupported",
                        "severity": "critical",
                        "owner": "",
                        "confidence": 2,
                        "evidence": "",
                        "probability": 90,
                    }
                ]
            }
        if request.job_type == AIJobType.OPEN_QUESTIONS.value:
            return {
                "open_questions": [
                    {
                        "question": "This is not a question",
                        "owner": "",
                        "importance": "critical",
                        "confidence": 2,
                        "evidence": "",
                        "answer": "Invented",
                    }
                ]
            }
        if request.job_type == AIJobType.BUYING_SIGNALS.value:
            return {
                "signals": [
                    {
                        "signal_type": "unsupported",
                        "polarity": "optimistic",
                        "strength": "certain",
                        "confidence": 2,
                        "evidence": "",
                        "win_probability": 90,
                    }
                ],
                "overall_momentum": "will_close",
                "momentum_summary": "Too short.",
                "confidence": 2,
                "deal_score": 99,
            }
        if request.job_type == AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value:
            return {
                "objections": [
                    {
                        "objection": "",
                        "category": "unsupported",
                        "status": "ignored",
                        "strength": "critical",
                        "owner": "",
                        "confidence": 2,
                        "evidence": "",
                        "close_probability": 0.9,
                    }
                ],
                "competitors": [
                    {
                        "name": "",
                        "position": "winning",
                        "confidence": 2,
                        "evidence": "",
                        "market_share": 90,
                    }
                ],
                "overall_objection_pressure": "certain_loss",
                "summary": "Too short.",
                "deal_score": 99,
            }
        if request.job_type == AIJobType.STAKEHOLDER_INTELLIGENCE.value:
            return {
                "stakeholders": [
                    {
                        "name": "",
                        "organisation": "",
                        "role": "guru",
                        "influence": "certain",
                        "stance": "winning",
                        "engagement": "always",
                        "confidence": 2,
                        "evidence": "",
                        "deal_score": 99,
                    }
                ],
                "role_coverage": {
                    "economic_buyer": "certain",
                    "decision_maker": "identified",
                    "champion": "identified",
                    "technical_buyer": "identified",
                    "procurement": "identified",
                    "legal_security": "identified",
                    "forecast": "commit",
                },
                "stakeholder_summary": "Too short.",
                "confidence": 2,
                "close_probability": 0.9,
            }
        if request.job_type == AIJobType.NEXT_BEST_ACTION.value:
            return {
                "overall_recommendation": "Update the CRM.",
                "priority": "urgent",
                "confidence": 2,
                "reasoning": [],
                "recommended_actions": [
                    {
                        "action": "Send an email.",
                        "reason": "Invented unsupported reason.",
                        "priority": "critical",
                        "confidence": 2,
                        "depends_on": ["transcript"],
                    }
                ],
                "automation": True,
            }
        if request.job_type == AIJobType.FOLLOW_UP_EMAIL.value:
            return {
                "subject": "",
                "greeting": "",
                "summary": "Too short.",
                "decisions": [1],
                "action_items": [],
                "open_questions": [],
                "closing": "",
                "tone": "casual",
                "confidence": 2,
                "body": "Unexpected field",
            }
        return {
            "decisions": [
                {
                    "decision": "",
                    "owner": None,
                    "status": "unsupported",
                    "confidence": 2,
                    "evidence": "",
                }
            ]
        }
