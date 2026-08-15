from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Protocol

from pypdf import PdfReader


class DocumentParsingError(Exception):
    code = "document_parse_failed"


class UnsupportedDocumentError(DocumentParsingError):
    code = "unsupported_document"


class MalformedDocumentError(DocumentParsingError):
    code = "malformed_document"


class UnsafeDocumentError(DocumentParsingError):
    code = "unsafe_document"


class PasswordProtectedDocumentError(DocumentParsingError):
    code = "password_protected_document"


class DocumentLimitError(DocumentParsingError):
    code = "document_limit_exceeded"


@dataclass(frozen=True)
class ParsedDocumentFragment:
    page_number: int | None
    section: str | None
    paragraph_index: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    page_count: int
    character_count: int
    fragments: tuple[ParsedDocumentFragment, ...]


class DocumentParser(Protocol):
    def parse(self, content: bytes, mime_type: str) -> ParsedDocument: ...


class BoundedDocumentParser:
    """Narrow PDF/TXT parser. It extracts text only and never executes or fetches content."""

    _pdf_active_markers = (
        b"/javascript",
        b"/js",
        b"/openaction",
        b"/aa",
        b"/launch",
        b"/embeddedfile",
        b"/richmedia",
        b"/xfa",
    )

    def __init__(self, *, max_pages: int, max_characters: int) -> None:
        self.max_pages = max_pages
        self.max_characters = max_characters

    def parse(self, content: bytes, mime_type: str) -> ParsedDocument:
        if not content:
            raise MalformedDocumentError
        self._scan_for_malware_boundary(content)
        if mime_type == "text/plain":
            return self._parse_text(content)
        if mime_type == "application/pdf":
            return self._parse_pdf(content)
        raise UnsupportedDocumentError

    @staticmethod
    def _scan_for_malware_boundary(content: bytes) -> None:
        # This is a fail-closed safety boundary for deterministic tests, not a claim
        # that signature scanning replaces a deployment malware service.
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content.upper():
            raise UnsafeDocumentError

    def _parse_text(self, content: bytes) -> ParsedDocument:
        if content.startswith(b"%PDF-"):
            raise MalformedDocumentError
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise MalformedDocumentError from exc
        if _has_unsafe_control_character(text):
            raise UnsafeDocumentError
        return self._normalise_pages((text,), numbered_pages=False)

    def _parse_pdf(self, content: bytes) -> ParsedDocument:
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise MalformedDocumentError
        lowered = content.lower()
        if any(marker in lowered for marker in self._pdf_active_markers):
            raise UnsafeDocumentError
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise PasswordProtectedDocumentError
            if len(reader.pages) == 0:
                raise MalformedDocumentError
            if len(reader.pages) > self.max_pages:
                raise DocumentLimitError
            pages = tuple((page.extract_text() or "") for page in reader.pages)
        except PasswordProtectedDocumentError:
            raise
        except DocumentLimitError:
            raise
        except Exception as exc:
            raise MalformedDocumentError from exc
        return self._normalise_pages(pages, numbered_pages=True)

    def _normalise_pages(self, pages: tuple[str, ...], *, numbered_pages: bool) -> ParsedDocument:
        fragments: list[ParsedDocumentFragment] = []
        character_count = 0
        paragraph_index = 0
        for page_offset, raw_page in enumerate(pages):
            if _has_unsafe_control_character(raw_page):
                raise UnsafeDocumentError
            normalised = raw_page.replace("\r\n", "\n").replace("\r", "\n")
            normalised = "\n".join(line.rstrip() for line in normalised.splitlines()).strip()
            if not normalised:
                continue
            paragraphs = re.split(r"\n\s*\n+", normalised)
            section: str | None = None
            for raw_paragraph in paragraphs:
                paragraph = re.sub(r"[ \t]+", " ", raw_paragraph).strip()
                if not paragraph:
                    continue
                if len(paragraph) > 12_000:
                    pieces = tuple(paragraph[offset : offset + 12_000] for offset in range(0, len(paragraph), 12_000))
                else:
                    pieces = (paragraph,)
                first_line = paragraph.split("\n", 1)[0].strip()
                if len(first_line) <= 200 and (first_line.endswith(":") or first_line.isupper()):
                    section = first_line.rstrip(":")
                for piece in pieces:
                    character_count += len(piece)
                    if character_count > self.max_characters:
                        raise DocumentLimitError
                    fragments.append(
                        ParsedDocumentFragment(
                            page_number=page_offset + 1 if numbered_pages else None,
                            section=section,
                            paragraph_index=paragraph_index,
                            text=piece,
                        )
                    )
                    paragraph_index += 1
        if not fragments:
            raise MalformedDocumentError
        return ParsedDocument(page_count=len(pages), character_count=character_count, fragments=tuple(fragments))


def _has_unsafe_control_character(value: str) -> bool:
    return any(
        (ord(character) < 32 and character not in {"\t", "\n", "\r"}) or ord(character) == 127 for character in value
    )
