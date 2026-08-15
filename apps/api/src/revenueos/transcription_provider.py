from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol, cast

import openai
from openai import AsyncOpenAI

from revenueos.config import Settings
from revenueos.debrief_contracts import TranscriptionResult
from revenueos.recording_contracts import (
    RecordingTranscriptionResult,
    TranscriptionSegmentResult,
)

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
    max_audio_bytes: int | None

    async def transcribe(
        self,
        *,
        audio: bytes,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> TranscriptionResult: ...

    async def transcribe_file(
        self,
        *,
        audio_path: Path,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> RecordingTranscriptionResult: ...


class DeterministicMockTranscriptionProvider:
    """Zero-network fixture provider. It never retains or logs supplied bytes."""

    provider_name = "mock"
    max_audio_bytes: int | None = None

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

    async def transcribe_file(
        self,
        *,
        audio_path: Path,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> RecordingTranscriptionResult:
        del mime_type, language
        with audio_path.open("rb") as audio_file:
            content = audio_file.read(1_000_001)
        marker = b"MOCK_TRANSCRIPT:"
        marker_index = content.find(marker)
        if marker_index >= 0:
            text = content[marker_index + len(marker) :].decode("utf-8", errors="strict").strip()
        else:
            text = "Mock customer interaction transcript captured for deterministic testing."
        if not text or len(text) > 1_000_000:
            raise TranscriptionRejectedError
        sentences = [item.strip() for item in text.replace("\n", " ").split(".") if item.strip()]
        if not sentences:
            sentences = [text]
        duration_ms = duration_seconds * 1000
        segments = tuple(
            TranscriptionSegmentResult(
                sequence_number=index,
                start_ms=(duration_ms * index) // len(sentences),
                end_ms=(duration_ms * (index + 1)) // len(sentences),
                speaker_label=None,
                text=f"{sentence}." if not sentence.endswith(("!", "?", ".")) else sentence,
            )
            for index, sentence in enumerate(sentences)
        )
        request_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"revenueos-recording-transcription:{audio_path.stat().st_size}:{duration_seconds}",
        )
        return RecordingTranscriptionResult(
            text=text,
            segments=segments,
            provider_name=self.provider_name,
            provider_request_id=f"mock-{request_id}",
            duration_seconds=duration_seconds,
        )


class _OpenAITranscriptionResponse(Protocol):
    text: str
    segments: object
    _request_id: str | None


class _OpenAITranscriptionCreate(Protocol):
    def __call__(
        self,
        *,
        file: object,
        model: str,
        language: str | None,
        timeout: float,
        response_format: str | None = None,
        timestamp_granularities: list[str] | None = None,
        chunking_strategy: str | None = None,
    ) -> Awaitable[_OpenAITranscriptionResponse]: ...


class OpenAITranscriptionProvider:
    provider_name = "openai"
    max_audio_bytes: int | None = 25_000_000

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
        raw_text = getattr(response, "text", None)
        if not isinstance(raw_text, str):
            raise TranscriptionRejectedError
        text = raw_text.strip()
        if not text or len(text) > 12_000:
            raise TranscriptionRejectedError
        request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"openai-transcription:{duration_seconds}:{len(audio)}:{text}")
        return TranscriptionResult(
            text=text,
            provider_name=self.provider_name,
            provider_request_id=f"openai-{request_id}",
            duration_seconds=duration_seconds,
        )

    async def transcribe_file(
        self,
        *,
        audio_path: Path,
        mime_type: str,
        language: str | None,
        duration_seconds: int,
    ) -> RecordingTranscriptionResult:
        try:
            with audio_path.open("rb") as audio_file:
                if self._model == "gpt-4o-transcribe-diarize":
                    response = await self._create(
                        file=(f"recording.{_extension(mime_type)}", audio_file, mime_type),
                        model=self._model,
                        language=language,
                        timeout=self._timeout,
                        response_format="diarized_json",
                        chunking_strategy="auto",
                    )
                elif self._model == "whisper-1":
                    response = await self._create(
                        file=(f"recording.{_extension(mime_type)}", audio_file, mime_type),
                        model=self._model,
                        language=language,
                        timeout=self._timeout,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                    )
                else:
                    response = await self._create(
                        file=(f"recording.{_extension(mime_type)}", audio_file, mime_type),
                        model=self._model,
                        language=language,
                        timeout=self._timeout,
                        response_format="json",
                    )
        except openai.APITimeoutError as exc:
            raise TranscriptionTimeoutError from exc
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as exc:
            raise TranscriptionTransientError from exc
        except openai.APIError as exc:
            raise TranscriptionRejectedError from exc
        raw_text = getattr(response, "text", None)
        if not isinstance(raw_text, str):
            raise TranscriptionRejectedError
        text = raw_text.strip()
        if not text or len(text) > 1_000_000:
            raise TranscriptionRejectedError
        response_segments = getattr(response, "segments", None)
        raw_segments = response_segments if isinstance(response_segments, list) else []
        segments = tuple(_normalise_provider_segment(item, index) for index, item in enumerate(raw_segments))
        if not segments:
            segments = (
                TranscriptionSegmentResult(
                    sequence_number=0,
                    start_ms=0,
                    end_ms=duration_seconds * 1000,
                    text=text,
                ),
            )
        provider_request_id = getattr(response, "_request_id", None)
        request_id = provider_request_id if isinstance(provider_request_id, str) else f"openai-{uuid.uuid4()}"
        return RecordingTranscriptionResult(
            text=text,
            segments=segments,
            provider_name=self.provider_name,
            provider_request_id=request_id,
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


async def execute_recording_transcription(
    provider: TranscriptionProvider,
    *,
    audio_path: Path,
    mime_type: str,
    language: str | None,
    duration_seconds: int,
    timeout_seconds: float,
) -> RecordingTranscriptionResult:
    context = {
        "provider_name": provider.provider_name,
        "audio_byte_count": audio_path.stat().st_size,
        "duration_seconds": duration_seconds,
        "mime_type": mime_type,
    }
    logger.info("transcription_started", extra=context)
    try:
        result = await asyncio.wait_for(
            provider.transcribe_file(
                audio_path=audio_path,
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
            "segment_count": len(result.segments),
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


def _normalise_provider_segment(value: object, sequence_number: int) -> TranscriptionSegmentResult:
    if isinstance(value, dict):
        text = value.get("text")
        start = value.get("start")
        end = value.get("end")
        speaker = value.get("speaker")
    else:
        text = getattr(value, "text", None)
        start = getattr(value, "start", None)
        end = getattr(value, "end", None)
        speaker = getattr(value, "speaker", None)
    if not isinstance(text, str) or not text.strip():
        raise TranscriptionRejectedError
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end < start:
        raise TranscriptionRejectedError
    speaker_label = None
    if isinstance(speaker, str) and speaker.strip():
        normalised = speaker.strip()[:60]
        speaker_label = normalised if normalised.casefold().startswith("speaker") else f"Speaker {normalised}"
    return TranscriptionSegmentResult(
        sequence_number=sequence_number,
        start_ms=max(0, round(start * 1000)),
        end_ms=max(0, round(end * 1000)),
        speaker_label=speaker_label,
        text=text.strip(),
    )
