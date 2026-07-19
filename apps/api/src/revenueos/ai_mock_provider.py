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
    DECISION_EVIDENCE_MAX_LENGTH,
    DECISION_MAX_LENGTH,
    DECISIONS_MAX_COUNT,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    FOLLOW_UP_EMAIL_SCHEMA_VERSION,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
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
    DecisionsProviderInput,
    ExecutiveSummaryProviderInput,
    FollowUpEmailProviderInput,
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
