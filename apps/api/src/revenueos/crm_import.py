from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import PurePath

MAX_CRM_IMPORT_BYTES = 5 * 1024 * 1024
MAX_CRM_IMPORT_ROWS = 5_000
MAX_CRM_IMPORT_COLUMNS = 100
MAX_CRM_IMPORT_CELL_CHARACTERS = 2_048


class CRMImportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedCRMImportRow:
    source_row: int
    values: dict[str, str]
    formula_like: bool


@dataclass(frozen=True)
class ParsedCRMImport:
    file_size_bytes: int
    file_fingerprint: str
    headers: tuple[str, ...]
    rows: tuple[ParsedCRMImportRow, ...]


def decode_crm_csv(file_name: str, content_base64: str) -> bytes:
    name = PurePath(file_name.replace("\\", "/")).name.strip()
    if not name or len(name) > 255 or not name.casefold().endswith(".csv"):
        raise CRMImportError("unsupported_file", "Choose a CSV file with a .csv extension.")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise CRMImportError("unsafe_filename", "The CSV filename contains unsupported characters.")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CRMImportError("invalid_file_encoding", "The selected CSV could not be decoded.") from exc
    if not content:
        raise CRMImportError("empty_file", "The selected CSV is empty.")
    if len(content) > MAX_CRM_IMPORT_BYTES:
        raise CRMImportError("file_too_large", "CRM CSV files may be at most 5 MB.")
    if b"\x00" in content:
        raise CRMImportError("invalid_csv", "The selected CSV contains null bytes and was rejected.")
    return content


def parse_crm_csv(content: bytes, column_mapping: dict[str, str | None]) -> ParsedCRMImport:
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise CRMImportError("invalid_file_encoding", "CSV files must use UTF-8 encoding.") from exc
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), delimiter=",", strict=True)
        raw_rows = list(reader)
    except csv.Error as exc:
        raise CRMImportError("malformed_csv", "The selected file is not a well-formed comma-separated CSV.") from exc
    if not raw_rows:
        raise CRMImportError("empty_file", "The selected CSV is empty.")
    headers = tuple(value.strip() for value in raw_rows[0])
    if not headers or not any(headers):
        raise CRMImportError("missing_headers", "The CSV must contain a header row.")
    if len(headers) > MAX_CRM_IMPORT_COLUMNS:
        raise CRMImportError("too_many_columns", "CRM CSV files may contain at most 100 columns.")
    if any(not value or len(value) > 100 for value in headers):
        raise CRMImportError("invalid_headers", "Every CSV column needs a bounded header.")
    if len({value.casefold() for value in headers}) != len(headers):
        raise CRMImportError("duplicate_headers", "CSV column headers must be unique.")
    if set(column_mapping) != set(headers):
        raise CRMImportError("incomplete_column_mapping", "Map or explicitly ignore every CSV column.")
    mapped_targets = [value for value in column_mapping.values() if value is not None]
    if len(mapped_targets) != len(set(mapped_targets)):
        raise CRMImportError("duplicate_field_mapping", "Only one CSV column may map to each CRM field.")
    if not mapped_targets:
        raise CRMImportError("no_mapped_columns", "Map at least one approved CRM field.")
    non_empty_rows = [row for row in raw_rows[1:] if any(cell.strip() for cell in row)]
    if len(non_empty_rows) > MAX_CRM_IMPORT_ROWS:
        raise CRMImportError("too_many_rows", "CRM imports are limited to 5,000 rows.")
    parsed: list[ParsedCRMImportRow] = []
    for source_row, raw_row in enumerate(non_empty_rows, start=2):
        if len(raw_row) > len(headers):
            parsed.append(ParsedCRMImportRow(source_row, {}, False))
            continue
        padded = [*raw_row, *([""] * (len(headers) - len(raw_row)))]
        if any(len(cell) > MAX_CRM_IMPORT_CELL_CHARACTERS for cell in padded):
            parsed.append(ParsedCRMImportRow(source_row, {}, False))
            continue
        values: dict[str, str] = {}
        formula_like = False
        for index, header in enumerate(headers):
            target = column_mapping[header]
            if target is None:
                continue
            value = padded[index].strip()
            if value:
                values[target] = value
                formula_like = formula_like or value.startswith(("=", "+", "-", "@"))
        parsed.append(ParsedCRMImportRow(source_row, values, formula_like))
    if not parsed:
        raise CRMImportError("no_rows", "The CSV does not contain any data rows.")
    return ParsedCRMImport(
        file_size_bytes=len(content),
        file_fingerprint=hashlib.sha256(content).hexdigest(),
        headers=headers,
        rows=tuple(parsed),
    )
