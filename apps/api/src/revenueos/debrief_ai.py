from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TypeVar, cast
from uuid import UUID

from pydantic import BaseModel, JsonValue

from revenueos.ai_output_schema_registry import (
    AI_DEBRIEF_EVIDENCE_SCHEMA_KEY,
    AI_DEBRIEF_QUESTION_SCHEMA_KEY,
    OutputSchemaRegistry,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_contracts import PromptVariables
from revenueos.ai_prompt_errors import StructuredOutputValidationError
from revenueos.ai_prompt_registry import (
    AI_DEBRIEF_EVIDENCE_PROMPT_KEY,
    AI_DEBRIEF_QUESTION_PROMPT_KEY,
    PromptRegistry,
    create_default_prompt_registry,
)
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider import AIProvider, execute_provider_request
from revenueos.ai_provider_contracts import (
    AIDebriefEvidenceProviderInput,
    AIDebriefQuestionProviderInput,
    ProviderOutputSchema,
    ProviderRequest,
)
from revenueos.ai_provider_errors import MalformedProviderOutputError
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.config import Settings
from revenueos.debrief_contracts import (
    AI_DEBRIEF_EVIDENCE_REQUEST_TYPE,
    AI_DEBRIEF_EVIDENCE_SCHEMA_VERSION,
    AI_DEBRIEF_QUESTION_REQUEST_TYPE,
    AI_DEBRIEF_QUESTION_SCHEMA_VERSION,
    CandidateEvidenceExtraction,
    DebriefCaptureType,
    DebriefQuestion,
)

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class StructuredDebriefReasoning:
    """Foreground, bounded use of the application-owned structured-output path."""

    def __init__(
        self,
        settings: Settings,
        organisation_id: UUID,
        provider: AIProvider | None = None,
        *,
        schemas: OutputSchemaRegistry | None = None,
        prompts: PromptRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.organisation_id = organisation_id
        self.schemas = schemas or create_default_output_schema_registry()
        self.prompts = prompts or create_default_prompt_registry(self.schemas)
        self.provider = provider or AIProviderRegistry(settings=settings).resolve(
            settings.ai_provider_name,
            settings.selected_ai_model_identifier,
        )

    @property
    def uses_external_provider(self) -> bool:
        return self.provider.provider_name == "openai"

    async def next_question(
        self,
        *,
        request_id: UUID,
        session_id: UUID,
        interaction_type: str,
        capture_type: DebriefCaptureType,
        context: dict[str, object],
        answers: tuple[str, ...],
        asked_targets: tuple[str, ...],
        question_count: int,
        max_questions: int,
        context_questions: tuple[str, ...],
    ) -> DebriefQuestion:
        payload = self._normalised_json(
            {
                "interaction_type": interaction_type,
                "capture_type": capture_type,
                "existing_context": context,
                "answers": list(answers),
                "latest_response": answers[-1],
                "asked_targets": list(asked_targets),
                "question_count": question_count,
                "max_questions": max_questions,
                "context_questions": list(context_questions),
                "direct_supported_targets": list(cast(list[object], context.get("directRecordingCoverage", []))),
                "marker_targets": list(cast(list[object], context.get("markerTargets", []))),
            }
        )
        return await self._execute(
            request_id=request_id,
            session_id=session_id,
            request_type=AI_DEBRIEF_QUESTION_REQUEST_TYPE,
            prompt_key=AI_DEBRIEF_QUESTION_PROMPT_KEY,
            schema_key=AI_DEBRIEF_QUESTION_SCHEMA_KEY,
            schema_version=AI_DEBRIEF_QUESTION_SCHEMA_VERSION,
            provider_input=AIDebriefQuestionProviderInput,
            payload=payload,
            result_model=DebriefQuestion,
        )

    async def extract_candidates(
        self,
        *,
        request_id: UUID,
        session_id: UUID,
        capture_type: DebriefCaptureType,
        context: dict[str, object],
        fragments: tuple[tuple[UUID, str], ...],
    ) -> CandidateEvidenceExtraction:
        payload = self._normalised_json(
            {
                "capture_type": capture_type,
                "existing_context": context,
                "fragments": [{"id": str(identifier), "text": text} for identifier, text in fragments],
            }
        )
        return await self._execute(
            request_id=request_id,
            session_id=session_id,
            request_type=AI_DEBRIEF_EVIDENCE_REQUEST_TYPE,
            prompt_key=AI_DEBRIEF_EVIDENCE_PROMPT_KEY,
            schema_key=AI_DEBRIEF_EVIDENCE_SCHEMA_KEY,
            schema_version=AI_DEBRIEF_EVIDENCE_SCHEMA_VERSION,
            provider_input=AIDebriefEvidenceProviderInput,
            payload=payload,
            result_model=CandidateEvidenceExtraction,
        )

    async def _execute(
        self,
        *,
        request_id: UUID,
        session_id: UUID,
        request_type: str,
        prompt_key: str,
        schema_key: str,
        schema_version: int,
        provider_input: type[AIDebriefQuestionProviderInput] | type[AIDebriefEvidenceProviderInput],
        payload: str,
        result_model: type[StructuredResult],
    ) -> StructuredResult:
        prompt = self.prompts.resolve(prompt_key, 1)
        rendered = render_prompt(prompt, PromptVariables(values={"debrief_input": payload}))
        schema = self.schemas.resolve(schema_key, schema_version)
        provider_schema = ProviderOutputSchema(
            schema_key=schema.schema_key,
            schema_version=schema.schema_version,
            json_schema=cast(
                dict[str, JsonValue],
                schema.validation_model.model_json_schema(mode="validation"),
            ),
        )
        request = ProviderRequest(
            request_id=request_id,
            organisation_id=self.organisation_id,
            job_id=session_id,
            job_type=request_type,
            model_identifier=self.provider.model_identifier,
            input_payload=provider_input(messages=rendered.messages),
            expected_schema_version=schema_version,
            output_schema=provider_schema,
            timeout_seconds=self.settings.selected_ai_timeout_seconds,
        )
        last_error: Exception | None = None
        for _ in range(self.settings.ai_structured_output_max_attempts):
            response = await execute_provider_request(self.provider, request)
            try:
                mapping = self._mapping(response.output_payload)
                validated = self.schemas.validate(schema, mapping)
                return result_model.model_validate(validated)
            except (MalformedProviderOutputError, StructuredOutputValidationError) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    @staticmethod
    def _mapping(payload: dict[str, JsonValue] | str) -> Mapping[str, object]:
        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise MalformedProviderOutputError from exc
        else:
            decoded = payload
        if not isinstance(decoded, dict):
            raise MalformedProviderOutputError
        return cast(Mapping[str, object], decoded)

    @staticmethod
    def _normalised_json(payload: dict[str, object]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
