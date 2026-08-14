from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from typing import Protocol, cast

import openai
from openai import AsyncOpenAI

from revenueos.config import Settings
from revenueos.debrief_contracts import TranscriptionResult

logger = logging.getLogger("revenueos.transcription_provider")


class TranscriptionProviderError(Exception):
    code = "transcription_failed"
    retryable = False


class TranscriptionTimeoutError(TranscriptionProviderError):
    code = "transcription_timeout"
    retryable = True


class TranscriptionTransientError(TranscriptionProviderError):
    code = "transcription_unavailable"
    retryable = True


class TranscriptionRejectedError(TranscriptionProviderError):
    code = "transcription_rejected"


class TranscriptionProvider(Protocol):
    provider_name: str

    async def transcribe(
        self,
        *,
        audio: bytes,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> TranscriptionResult: ...


class DeterministicMockTranscriptionProvider:
    """Zero-network fixture provider. It never retains or logs supplied bytes."""

    provider_name = "mock"

    async def transcribe(
        self,
        *,
        audio: bytes,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> TranscriptionResult:
        del mime_type, language
        marker = b"MOCK_TRANSCRIPT:"
        if audio.startswith(marker):
            text = audio[len(marker) :].decode("utf-8", errors="strict").strip()
        else:
            text = "Mock voice answer captured for deterministic testing."
        if not text:
            raise TranscriptionRejectedError
        request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"revenueos-transcription:{len(audio)}:{duration_seconds}")
        return TranscriptionResult(
            text=text[:12_000],
            provider_name=self.provider_name,
            provider_request_id=f"mock-{request_id}",
            duration_seconds=duration_seconds,
        )


class _OpenAITranscriptionResponse(Protocol):
    text: str


class _OpenAITranscriptionCreate(Protocol):
    def __call__(
        self,
        *,
        file: tuple[str, bytes, str],
        model: str,
        language: str | None,
        timeout: float,
    ) -> Awaitable[_OpenAITranscriptionResponse]: ...


class OpenAITranscriptionProvider:
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OpenAI transcription requires a server-side API key.")
        self._model = settings.transcription_model_identifier
        self._timeout = settings.transcription_timeout_seconds
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=self._timeout,
            max_retries=0,
        )
        self._create = cast(_OpenAITranscriptionCreate, client.audio.transcriptions.create)

    async def transcribe(
        self,
        *,
        audio: bytes,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> TranscriptionResult:
        try:
            response = await self._create(
                file=(f"debrief.{_extension(mime_type)}", audio, mime_type),
                model=self._model,
                language=language,
                timeout=self._timeout,
            )
        except openai.APITimeoutError as exc:
            raise TranscriptionTimeoutError from exc
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as exc:
            raise TranscriptionTransientError from exc
        except openai.APIError as exc:
            raise TranscriptionRejectedError from exc
        text = response.text.strip()
        if not text or len(text) > 12_000:
            raise TranscriptionRejectedError
        request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"openai-transcription:{duration_seconds}:{len(audio)}:{text}")
        return TranscriptionResult(
            text=text,
            provider_name=self.provider_name,
            provider_request_id=f"openai-{request_id}",
            duration_seconds=duration_seconds,
        )


async def execute_transcription(
    provider: TranscriptionProvider,
    *,
    audio: bytes,
    mime_type: str,
    language: str | None,
    duration_seconds: int,
    timeout_seconds: float,
) -> TranscriptionResult:
    context = {
        "provider_name": provider.provider_name,
        "audio_byte_count": len(audio),
        "duration_seconds": duration_seconds,
        "mime_type": mime_type,
    }
    logger.info("transcription_started", extra=context)
    try:
        result = await asyncio.wait_for(
            provider.transcribe(
                audio=audio,
                mime_type=mime_type,
                language=language,
                duration_seconds=duration_seconds,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        logger.warning("transcription_failed", extra={**context, "error_code": "transcription_timeout"})
        raise TranscriptionTimeoutError from exc
    except TranscriptionProviderError as exc:
        logger.warning("transcription_failed", extra={**context, "error_code": exc.code})
        raise
    logger.info(
        "transcription_completed",
        extra={
            **context,
            "provider_request_id": result.provider_request_id,
        },
    )
    return result


def create_transcription_provider(settings: Settings) -> TranscriptionProvider:
    if settings.transcription_provider_name == "mock":
        return DeterministicMockTranscriptionProvider()
    return OpenAITranscriptionProvider(settings)


def _extension(mime_type: str) -> str:
    if "ogg" in mime_type:
        return "ogg"
    if "mp4" in mime_type:
        return "m4a"
    return "webm"
