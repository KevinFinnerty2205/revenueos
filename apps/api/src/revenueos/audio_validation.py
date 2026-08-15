from __future__ import annotations


class UnsafeAudioError(ValueError):
    code = "unsupported_audio_content"


def validate_audio_header(prefix: bytes, mime_type: str) -> None:
    """Validate the narrow container signature without trusting a filename or MIME alone."""

    if mime_type == "audio/webm":
        if len(prefix) < 4 or prefix[:4] != b"\x1aE\xdf\xa3":
            raise UnsafeAudioError("The recording does not contain a valid WebM header.")
        return
    if mime_type in {"audio/mp4", "audio/m4a"}:
        if len(prefix) < 12 or prefix[4:8] != b"ftyp":
            raise UnsafeAudioError("The recording does not contain a valid MP4 audio header.")
        return
    raise UnsafeAudioError("The recording format is not supported.")
