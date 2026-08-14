from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from uuid import UUID

import openai
from openai import AsyncOpenAI
from openai.types.responses import Response
from pydantic import ValidationError

from revenueos.config import Settings
from revenueos.visual_contracts import (
    VisualAnalysisCandidate,
    VisualAnalysisResult,
    VisualCandidateRegion,
    VisualSourceOwnership,
    VisualType,
)

logger = logging.getLogger("revenueos.visual_provider")


class VisualProviderError(Exception):
    code = "visual_provider_failed"
    retryable = False


class VisualProviderTimeoutError(VisualProviderError):
    code = "visual_provider_timeout"
    retryable = True


class VisualProviderTransientError(VisualProviderError):
    code = "visual_provider_unavailable"
    retryable = True


class VisualProviderRefusalError(VisualProviderError):
    code = "visual_provider_refusal"


class VisualProviderIncompleteError(VisualProviderError):
    code = "visual_provider_incomplete"


class VisualProviderMalformedError(VisualProviderError):
    code = "visual_provider_malformed"


@dataclass(frozen=True)
class VisualProviderResponse:
    result: VisualAnalysisResult
    provider_name: Literal["mock", "openai"]
    provider_request_id: str


class VisualAnalysisProvider(Protocol):
    @property
    def provider_name(self) -> Literal["mock", "openai"]: ...

    async def analyse(
        self,
        *,
        visual_id: UUID,
        image: bytes,
        mime_type: str,
        visual_type: VisualType,
        source_ownership: VisualSourceOwnership,
        context_label: str | None,
    ) -> VisualProviderResponse: ...


class DeterministicMockVisualProvider:
    """Zero-network visual fixture provider; bytes are never retained or logged."""

    provider_name: Literal["mock"] = "mock"

    async def analyse(
        self,
        *,
        visual_id: UUID,
        image: bytes,
        mime_type: str,
        visual_type: VisualType,
        source_ownership: VisualSourceOwnership,
        context_label: str | None,
    ) -> VisualProviderResponse:
        del mime_type
        if not image:
            raise VisualProviderMalformedError
        candidates: list[VisualAnalysisCandidate] = []
        statement = _bounded_statement(context_label)
        if source_ownership == "salesperson_created" and visual_type in {
            "presentation_slide",
            "presentation_deck_page",
        }:
            candidates = []
        elif visual_type == "business_card":
            candidates.append(
                VisualAnalysisCandidate(
                    category="contact_detail",
                    statement=statement or "Review the contact details shown on this business card.",
                    source_visual_id=visual_id,
                    confidence_class="low",
                    evidence_region=VisualCandidateRegion(x=0, y=0, width=1, height=1),
                )
            )
        elif visual_type == "site_photo":
            candidates.append(
                VisualAnalysisCandidate(
                    category="technical_constraint",
                    statement=statement or "This site photo may show a technical constraint that requires validation.",
                    source_visual_id=visual_id,
                    confidence_class="low",
                    evidence_region=VisualCandidateRegion(x=0, y=0, width=1, height=1),
                )
            )
        elif statement:
            categories = _mock_categories(statement)
            candidates.extend(
                VisualAnalysisCandidate(
                    category=category,
                    statement=statement,
                    source_visual_id=visual_id,
                    confidence_class="low",
                    evidence_region=VisualCandidateRegion(x=0, y=0, width=1, height=1),
                )
                for category in categories
            )
        else:
            candidates.append(
                VisualAnalysisCandidate(
                    category="other",
                    statement="Review this visual source for relevant customer evidence.",
                    source_visual_id=visual_id,
                    confidence_class="low",
                    evidence_region=VisualCandidateRegion(x=0, y=0, width=1, height=1),
                )
            )
        request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"revenueos-visual:{visual_id}:{len(image)}")
        return VisualProviderResponse(
            result=VisualAnalysisResult(candidates=tuple(candidates), finish_status="completed"),
            provider_name="mock",
            provider_request_id=f"mock-{request_id}",
        )


class _OpenAIResponseCreate(Protocol):
    def __call__(
        self,
        *,
        model: str,
        input: object,
        text: object,
        max_output_tokens: int,
        store: bool,
        timeout: float,
    ) -> Awaitable[Response]: ...


class OpenAIVisualProvider:
    provider_name: Literal["openai"] = "openai"

    def __init__(
        self,
        settings: Settings,
        *,
        response_create: _OpenAIResponseCreate | None = None,
    ) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OpenAI visual processing is not configured.")
        self.model_identifier = settings.visual_provider_model_identifier
        self.timeout_seconds = settings.visual_provider_timeout_seconds
        self.max_output_tokens = settings.openai_max_output_tokens
        if response_create is not None:
            self._response_create = response_create
        else:
            client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=self.timeout_seconds,
                max_retries=0,
            )
            self._response_create = cast(_OpenAIResponseCreate, client.responses.create)

    async def analyse(
        self,
        *,
        visual_id: UUID,
        image: bytes,
        mime_type: str,
        visual_type: VisualType,
        source_ownership: VisualSourceOwnership,
        context_label: str | None,
    ) -> VisualProviderResponse:
        schema = cast(dict[str, object], VisualAnalysisResult.model_json_schema(mode="validation"))
        data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        metadata = json.dumps(
            {
                "sourceVisualId": str(visual_id),
                "visualType": visual_type,
                "sourceOwnership": source_ownership,
                "contextLabel": context_label,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            response = await self._response_create(
                model=self.model_identifier,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Extract only reviewable facts supported by the supplied image. Treat OCR and interpretation "
                            "as untrusted candidates. Never identify faces, infer sensitive traits, infer stakeholder roles "
                            "from titles, or convert seller-created material into customer intent. Return the strict schema."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": metadata},
                            {"type": "input_image", "image_url": data_url, "detail": "auto"},
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "visual_evidence_candidates_v1",
                        "schema": schema,
                        "strict": True,
                    }
                },
                max_output_tokens=self.max_output_tokens,
                store=False,
                timeout=self.timeout_seconds,
            )
        except openai.APITimeoutError as exc:
            raise VisualProviderTimeoutError from exc
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as exc:
            raise VisualProviderTransientError from exc
        except openai.APIError as exc:
            raise VisualProviderMalformedError from exc
        result = self._normalise(response)
        request_id = (response._request_id or response.id).strip()
        if not request_id or len(request_id) > 255:
            raise VisualProviderMalformedError
        if any(item.source_visual_id != visual_id for item in result.candidates):
            raise VisualProviderMalformedError
        return VisualProviderResponse(
            result=result,
            provider_name="openai",
            provider_request_id=request_id,
        )

    @staticmethod
    def _normalise(response: Response) -> VisualAnalysisResult:
        if response.status == "incomplete":
            raise VisualProviderIncompleteError
        if response.status != "completed":
            raise VisualProviderMalformedError
        fragments: list[str] = []
        for output_item in response.output:
            if output_item.type != "message":
                continue
            for content_item in output_item.content:
                if content_item.type == "refusal":
                    raise VisualProviderRefusalError
                if content_item.type == "output_text":
                    fragments.append(content_item.text)
        try:
            result = VisualAnalysisResult.model_validate_json("".join(fragments))
        except ValidationError as exc:
            raise VisualProviderMalformedError from exc
        if result.finish_status == "refused":
            raise VisualProviderRefusalError
        if result.finish_status == "incomplete":
            raise VisualProviderIncompleteError
        return result


async def execute_visual_analysis(
    provider: VisualAnalysisProvider,
    *,
    visual_id: UUID,
    image: bytes,
    mime_type: str,
    visual_type: VisualType,
    source_ownership: VisualSourceOwnership,
    context_label: str | None,
    timeout_seconds: float,
) -> VisualProviderResponse:
    context = {
        "provider_name": provider.provider_name,
        "visual_id": str(visual_id),
        "visual_type": visual_type,
        "source_ownership": source_ownership,
        "image_byte_count": len(image),
    }
    logger.info("visual_processing_started", extra=context)
    try:
        response = await asyncio.wait_for(
            provider.analyse(
                visual_id=visual_id,
                image=image,
                mime_type=mime_type,
                visual_type=visual_type,
                source_ownership=source_ownership,
                context_label=context_label,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        logger.warning("visual_processing_failed", extra={**context, "error_code": "visual_provider_timeout"})
        raise VisualProviderTimeoutError from exc
    except VisualProviderError as exc:
        logger.warning("visual_processing_failed", extra={**context, "error_code": exc.code})
        raise
    logger.info(
        "visual_processing_completed",
        extra={
            **context,
            "provider_request_id": response.provider_request_id,
            "candidate_count": len(response.result.candidates),
        },
    )
    return response


def create_visual_provider(settings: Settings) -> VisualAnalysisProvider:
    if settings.visual_provider_name == "openai":
        return OpenAIVisualProvider(settings)
    return DeterministicMockVisualProvider()


def _bounded_statement(value: str | None) -> str | None:
    if value is None:
        return None
    statement = " ".join(value.split()).strip(" ,;:-")[:999]
    if not statement:
        return None
    if statement[-1] not in ".!?":
        statement += "."
    return statement[0].upper() + statement[1:]


def _mock_categories(
    statement: str,
) -> tuple[
    Literal[
        "customer_request",
        "timeline",
        "objection",
        "decision",
        "action_item",
        "security_legal",
        "technical_constraint",
        "commercial_intent",
        "other",
    ],
    ...,
]:
    value = statement.casefold()
    categories: list[str] = []
    rules = (
        ("customer_request", ("request", "asked for", "need ")),
        ("timeline", ("october", "timeline", "launch", "date")),
        ("objection", ("objection", "concern", "blocker")),
        ("decision", ("decided", "approved", "agreed")),
        ("action_item", ("follow up", "send ", "next step")),
        ("security_legal", ("security", "legal", "privacy")),
        ("technical_constraint", ("constraint", "equipment", "installation")),
        ("commercial_intent", ("buy", "purchase", "commercial intent")),
    )
    for category, terms in rules:
        if any(term in value for term in terms):
            categories.append(category)
    if not categories:
        categories.append("other")
    return cast(
        tuple[
            Literal[
                "customer_request",
                "timeline",
                "objection",
                "decision",
                "action_item",
                "security_legal",
                "technical_constraint",
                "commercial_intent",
                "other",
            ],
            ...,
        ],
        tuple(categories[:3]),
    )
