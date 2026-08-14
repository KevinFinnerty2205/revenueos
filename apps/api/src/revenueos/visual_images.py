from __future__ import annotations

import binascii
import hashlib
import struct
import zlib
from dataclasses import dataclass

MAX_PNG_DECODED_BYTES = 64_000_000


class UnsafeVisualError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedVisual:
    content: bytes
    mime_type: str
    width: int
    height: int
    checksum_sha256: str
    metadata_stripped: bool


def validate_and_sanitise_visual(
    content: bytes,
    *,
    declared_mime_type: str,
    declared_byte_size: int,
    declared_checksum: str,
    max_bytes: int,
    max_dimension: int,
    max_pixels: int,
) -> ValidatedVisual:
    if not content:
        raise UnsafeVisualError("empty_image", "The uploaded image is empty.")
    if len(content) > max_bytes or declared_byte_size > max_bytes:
        raise UnsafeVisualError("image_too_large", "The uploaded image exceeds the configured size limit.")
    if len(content) != declared_byte_size:
        raise UnsafeVisualError("upload_size_mismatch", "The uploaded image size did not match the upload request.")
    actual_checksum = hashlib.sha256(content).hexdigest()
    if actual_checksum != declared_checksum:
        raise UnsafeVisualError("upload_checksum_mismatch", "The uploaded image checksum did not match.")

    if content.startswith(b"\xff\xd8"):
        actual_mime = "image/jpeg"
        cleaned, width, height, stripped = _sanitise_jpeg(content)
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        actual_mime = "image/png"
        cleaned, width, height, stripped = _sanitise_png(content)
    else:
        raise UnsafeVisualError("malformed_image", "The uploaded file is not a supported image.")
    if actual_mime != declared_mime_type:
        raise UnsafeVisualError("mime_mismatch", "The uploaded image content does not match its MIME type.")
    if width > max_dimension or height > max_dimension or width * height > max_pixels:
        raise UnsafeVisualError("image_dimensions_exceeded", "The uploaded image dimensions are not allowed.")
    return ValidatedVisual(
        content=cleaned,
        mime_type=actual_mime,
        width=width,
        height=height,
        checksum_sha256=hashlib.sha256(cleaned).hexdigest(),
        metadata_stripped=stripped,
    )


def _sanitise_jpeg(content: bytes) -> tuple[bytes, int, int, bool]:
    if len(content) < 4 or not content.endswith(b"\xff\xd9"):
        raise UnsafeVisualError("malformed_image", "The JPEG image is incomplete or contains trailing content.")
    output = bytearray(b"\xff\xd8")
    offset = 2
    width = 0
    height = 0
    stripped = False
    saw_scan = False
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset < len(content) - 2:
        if content[offset] != 0xFF:
            raise UnsafeVisualError("malformed_image", "The JPEG marker stream is malformed.")
        marker_start = offset
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            raise UnsafeVisualError("malformed_image", "The JPEG marker stream is incomplete.")
        marker = content[offset]
        offset += 1
        if marker in {0x00, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            raise UnsafeVisualError("malformed_image", "The JPEG header contains an invalid marker.")
        if offset + 2 > len(content):
            raise UnsafeVisualError("malformed_image", "The JPEG segment is incomplete.")
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            raise UnsafeVisualError("malformed_image", "The JPEG segment length is invalid.")
        segment_end = offset + segment_length
        segment = content[marker_start:segment_end]
        if marker in sof_markers:
            if segment_length < 7:
                raise UnsafeVisualError("malformed_image", "The JPEG dimensions are missing.")
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
        if marker == 0xDA:
            output.extend(segment)
            output.extend(content[segment_end:])
            saw_scan = True
            break
        if marker in {0xE1, 0xED, 0xFE}:
            stripped = True
        else:
            output.extend(segment)
        offset = segment_end
    if not saw_scan or width <= 0 or height <= 0:
        raise UnsafeVisualError("malformed_image", "The JPEG image has no valid frame or scan.")
    return bytes(output), width, height, stripped


def _sanitise_png(content: bytes) -> tuple[bytes, int, int, bool]:
    output = bytearray(content[:8])
    offset = 8
    width = 0
    height = 0
    stripped = False
    saw_header = False
    saw_data = False
    saw_end = False
    saw_palette = False
    data_ended = False
    bit_depth = 0
    colour_type = 0
    compressed_data = bytearray()
    allowed_critical = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
    safe_ancillary = {b"tRNS"}
    while offset < len(content):
        if offset + 12 > len(content):
            raise UnsafeVisualError("malformed_image", "The PNG chunk is incomplete.")
        length = int.from_bytes(content[offset : offset + 4], "big")
        if length > len(content) or offset + 12 + length > len(content):
            raise UnsafeVisualError("malformed_image", "The PNG chunk length is invalid.")
        chunk_type = content[offset + 4 : offset + 8]
        chunk_data = content[offset + 8 : offset + 8 + length]
        expected_crc = int.from_bytes(content[offset + 8 + length : offset + 12 + length], "big")
        actual_crc = binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise UnsafeVisualError("malformed_image", "The PNG checksum is invalid.")
        chunk = content[offset : offset + 12 + length]
        if not saw_header:
            if chunk_type != b"IHDR" or length != 13:
                raise UnsafeVisualError("malformed_image", "The PNG header is invalid.")
            width, height, bit_depth, colour_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if (
                width <= 0
                or height <= 0
                or compression != 0
                or filtering != 0
                or interlace != 0
                or colour_type not in {0, 2, 3, 4, 6}
                or bit_depth not in _valid_png_bit_depths(colour_type)
            ):
                raise UnsafeVisualError("malformed_image", "The PNG image parameters are invalid.")
            saw_header = True
        elif chunk_type == b"IHDR":
            raise UnsafeVisualError("malformed_image", "The PNG contains more than one header.")
        if chunk_type == b"PLTE":
            if saw_data or length < 3 or length > 768 or length % 3 != 0:
                raise UnsafeVisualError("malformed_image", "The PNG palette is invalid.")
            saw_palette = True
        if chunk_type == b"IDAT":
            if data_ended:
                raise UnsafeVisualError("malformed_image", "The PNG image data is not contiguous.")
            saw_data = True
            compressed_data.extend(chunk_data)
        elif saw_data and chunk_type != b"IEND":
            data_ended = True
        if chunk_type == b"IEND":
            if length != 0 or not saw_data:
                raise UnsafeVisualError("malformed_image", "The PNG end marker is invalid.")
            saw_end = True
        is_critical = 65 <= chunk_type[0] <= 90
        if is_critical and chunk_type not in allowed_critical:
            raise UnsafeVisualError("unsupported_image", "The PNG contains an unsupported critical chunk.")
        if is_critical or chunk_type in safe_ancillary:
            output.extend(chunk)
        else:
            stripped = True
        offset += 12 + length
        if saw_end:
            if offset != len(content):
                raise UnsafeVisualError("image_polyglot", "The PNG contains content after its end marker.")
            break
    if not saw_header or not saw_data or not saw_end:
        raise UnsafeVisualError("malformed_image", "The PNG image is incomplete.")
    if colour_type == 3 and not saw_palette:
        raise UnsafeVisualError("malformed_image", "The indexed PNG image has no palette.")
    _validate_png_data(bytes(compressed_data), width, height, bit_depth, colour_type)
    return bytes(output), width, height, stripped


def _valid_png_bit_depths(colour_type: int) -> frozenset[int]:
    return {
        0: frozenset({1, 2, 4, 8, 16}),
        2: frozenset({8, 16}),
        3: frozenset({1, 2, 4, 8}),
        4: frozenset({8, 16}),
        6: frozenset({8, 16}),
    }.get(colour_type, frozenset())


def _validate_png_data(
    compressed: bytes,
    width: int,
    height: int,
    bit_depth: int,
    colour_type: int,
) -> None:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour_type]
    row_bytes = ((width * channels * bit_depth + 7) // 8) + 1
    expected_bytes = row_bytes * height
    if expected_bytes > MAX_PNG_DECODED_BYTES:
        raise UnsafeVisualError("image_dimensions_exceeded", "The decoded PNG image is too large.")
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(compressed, expected_bytes + 1)
        if len(decoded) <= expected_bytes:
            decoded += decompressor.flush(expected_bytes + 1 - len(decoded))
    except zlib.error as exc:
        raise UnsafeVisualError("malformed_image", "The PNG image data is invalid.") from exc
    if (
        len(decoded) != expected_bytes
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise UnsafeVisualError("malformed_image", "The PNG image data does not match its dimensions.")
    if any(decoded[offset] > 4 for offset in range(0, expected_bytes, row_bytes)):
        raise UnsafeVisualError("malformed_image", "The PNG contains an invalid row filter.")
