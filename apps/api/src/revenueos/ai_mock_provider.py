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
)
from revenueos.ai_provider_contracts import (
    ActionItemsProviderInput,
    BuyingSignalsProviderInput,
    DecisionsProviderInput,
    ExecutiveSummaryProviderInput,
    FollowUpEmailProviderInput,
    ObjectionsCompetitiveSignalsProviderInput,
    OpenQuestionsProviderInput,
    ProviderRequest,
    ProviderResponse,
    RisksBlockersProviderInput,
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
        input_payload: FollowUpEmailProviderInput,
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
    def _extract_transcript(
        input_payload: (
            ExecutiveSummaryProviderInput
            | DecisionsProviderInput
            | ActionItemsProviderInput
            | RisksBlockersProviderInput
            | OpenQuestionsProviderInput
            | BuyingSignalsProviderInput
            | ObjectionsCompetitiveSignalsProviderInput
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
