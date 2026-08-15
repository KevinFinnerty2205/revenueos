from __future__ import annotations

import base64
import binascii
import html
import re
from dataclasses import dataclass


class UnsafeTranscript(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedTranscriptSegment:
    sequence_number: int
    start_ms: int
    end_ms: int
    speaker_label: str | None
    text: str


@dataclass(frozen=True)
class ParsedTranscript:
    text: str
    source_format: str
    segments: tuple[ParsedTranscriptSegment, ...]
    timestamps_present: bool
    speaker_labels_present: bool


_TIMING = re.compile(
    r"^(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$"
)
_VOICE_TAG = re.compile(r"^\s*<v(?:\.[^ >]+)*\s+([^>]{1,80})>(.*?)(?:</v>)?\s*$", re.DOTALL)
_SPEAKER_PREFIX = re.compile(r"^([\w][\w .'-]{0,79}):\s+(.+)$", re.DOTALL)
_MARKUP = re.compile(r"<[^>]{1,256}>")


def decode_and_parse_transcript(
    content_base64: str,
    file_name: str,
    *,
    max_bytes: int,
    max_characters: int,
) -> ParsedTranscript:
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UnsafeTranscript("invalid_transcript_encoding", "The transcript upload is not valid base64.") from exc
    if not content or len(content) > max_bytes:
        raise UnsafeTranscript(
            "transcript_size_limit_exceeded",
            f"The transcript must be non-empty and no larger than {max_bytes:,} bytes.",
        )
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise UnsafeTranscript(
            "invalid_transcript_encoding",
            "The transcript must use valid UTF-8 text encoding.",
        ) from exc
    if any(ord(character) < 32 and character not in "\t\n\r" for character in decoded):
        raise UnsafeTranscript(
            "invalid_transcript_content",
            "The transcript contains unsupported control characters.",
        )
    normalised = decoded.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalised:
        raise UnsafeTranscript("empty_transcript", "The transcript contains no text.")
    if len(normalised) > max_characters:
        raise UnsafeTranscript(
            "transcript_character_limit_exceeded",
            f"The transcript exceeds the {max_characters:,}-character limit.",
        )
    source_format = file_name.rsplit(".", 1)[-1].lower()
    if source_format == "txt":
        return _parse_plain_text(normalised)
    return _parse_timed_text(normalised, source_format)


def _parse_plain_text(value: str) -> ParsedTranscript:
    segments: list[ParsedTranscriptSegment] = []
    normalised_lines: list[str] = []
    for line in (candidate.strip() for candidate in value.splitlines()):
        if not line:
            continue
        speaker, text = _speaker_and_text(line)
        _validate_cue_text(text)
        segments.append(
            ParsedTranscriptSegment(
                sequence_number=len(segments),
                start_ms=0,
                end_ms=0,
                speaker_label=speaker,
                text=text,
            )
        )
        normalised_lines.append(f"{speaker}: {text}" if speaker else text)
    if not segments:
        raise UnsafeTranscript("empty_transcript", "The transcript contains no text.")
    return ParsedTranscript(
        text="\n".join(normalised_lines),
        source_format="txt",
        segments=tuple(segments),
        timestamps_present=False,
        speaker_labels_present=any(item.speaker_label is not None for item in segments),
    )


def _parse_timed_text(value: str, source_format: str) -> ParsedTranscript:
    if source_format == "vtt":
        lines = value.splitlines()
        if not lines or not lines[0].strip().startswith("WEBVTT"):
            raise UnsafeTranscript("malformed_transcript", "A VTT transcript must begin with WEBVTT.")
        value = "\n".join(lines[1:]).strip()
    blocks = re.split(r"\n\s*\n", value)
    segments: list[ParsedTranscriptSegment] = []
    normalised_lines: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper().startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing_index = next((index for index, line in enumerate(lines[:2]) if "-->" in line), None)
        if timing_index is None or timing_index + 1 >= len(lines):
            raise UnsafeTranscript(
                "malformed_transcript", f"The {source_format.upper()} transcript has an invalid cue."
            )
        match = _TIMING.fullmatch(lines[timing_index])
        if match is None:
            raise UnsafeTranscript(
                "malformed_transcript", f"The {source_format.upper()} transcript has an invalid timestamp."
            )
        start_ms = _timestamp_ms(match.group("start"))
        end_ms = _timestamp_ms(match.group("end"))
        if end_ms < start_ms:
            raise UnsafeTranscript("malformed_transcript", "A transcript cue ends before it starts.")
        cue = "\n".join(lines[timing_index + 1 :])
        speaker, text = _speaker_and_text(cue)
        _validate_cue_text(text)
        segments.append(
            ParsedTranscriptSegment(
                sequence_number=len(segments),
                start_ms=start_ms,
                end_ms=end_ms,
                speaker_label=speaker,
                text=text,
            )
        )
        normalised_lines.append(f"{speaker}: {text}" if speaker else text)
        if len(segments) > 100_000:
            raise UnsafeTranscript("transcript_segment_limit_exceeded", "The transcript has too many cues.")
    if not segments:
        raise UnsafeTranscript("empty_transcript", "The transcript contains no usable cues.")
    return ParsedTranscript(
        text="\n".join(normalised_lines),
        source_format=source_format,
        segments=tuple(segments),
        timestamps_present=True,
        speaker_labels_present=any(item.speaker_label is not None for item in segments),
    )


def _speaker_and_text(value: str) -> tuple[str | None, str]:
    voice = _VOICE_TAG.fullmatch(value)
    if voice is not None:
        label = _normalise_label(voice.group(1))
        return label, _plain_text(voice.group(2))
    plain = _plain_text(value)
    prefixed = _SPEAKER_PREFIX.fullmatch(plain)
    if prefixed is not None and "://" not in prefixed.group(1):
        return _normalise_label(prefixed.group(1)), prefixed.group(2).strip()
    return None, plain


def _plain_text(value: str) -> str:
    return html.unescape(_MARKUP.sub("", value)).strip()


def _normalise_label(value: str) -> str:
    label = " ".join(value.split())
    if not label or len(label) > 80:
        raise UnsafeTranscript("malformed_transcript", "A transcript speaker label is invalid.")
    return label


def _validate_cue_text(value: str) -> None:
    if not value:
        raise UnsafeTranscript("malformed_transcript", "A transcript cue contains no text.")
    if len(value) > 12_000:
        raise UnsafeTranscript("transcript_segment_too_large", "A transcript cue exceeds 12,000 characters.")


def _timestamp_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    hours = int(parts[0]) if len(parts) == 3 else 0
    minutes = int(parts[-2])
    seconds, milliseconds = (int(part) for part in parts[-1].split("."))
    if minutes > 59 or seconds > 59:
        raise UnsafeTranscript("malformed_transcript", "A transcript timestamp is outside its valid range.")
    return ((hours * 60 + minutes) * 60 + seconds) * 1_000 + milliseconds
