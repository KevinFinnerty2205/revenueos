from __future__ import annotations

import json
import re
import uuid
from typing import Literal, cast

from pydantic import JsonValue

from revenueos.ai_contracts import (
    DECISION_EVIDENCE_MAX_LENGTH,
    DECISION_MAX_LENGTH,
    DECISIONS_MAX_COUNT,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
)
from revenueos.ai_provider_contracts import (
    DecisionsProviderInput,
    ExecutiveSummaryProviderInput,
    ProviderRequest,
    ProviderResponse,
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
        raise InvalidProviderRequestError

    @staticmethod
    def _extract_transcript(
        input_payload: ExecutiveSummaryProviderInput | DecisionsProviderInput,
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
