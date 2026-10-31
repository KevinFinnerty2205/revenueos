from __future__ import annotations

import io
import multiprocessing
import re
import sys
import zipfile
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Protocol
from xml.etree import ElementTree

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


def parse_document_in_subprocess(
    content: bytes,
    mime_type: str,
    *,
    max_pages: int,
    max_characters: int,
    max_bytes: int,
    timeout_seconds: float,
) -> ParsedDocument:
    """Parse an untrusted document in a killable, resource-bounded child process."""

    context = multiprocessing.get_context("spawn")
    receiving_connection, sending_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_parse_document_child,
        args=(
            sending_connection,
            content,
            mime_type,
            max_pages,
            max_characters,
            max_bytes,
            timeout_seconds,
        ),
        daemon=True,
    )
    process.start()
    sending_connection.close()
    try:
        if not receiving_connection.poll(timeout_seconds):
            _stop_process(process)
            raise TimeoutError("document_parse_timeout")
        try:
            outcome, payload = receiving_connection.recv()
        except EOFError as exc:
            raise MalformedDocumentError from exc
    finally:
        receiving_connection.close()
    process.join(timeout=1)
    if process.is_alive():
        _stop_process(process)
    if outcome == "ok" and isinstance(payload, ParsedDocument):
        return payload
    if outcome == "error" and isinstance(payload, str):
        error_type = _DOCUMENT_ERROR_TYPES.get(payload, DocumentParsingError)
        raise error_type
    raise MalformedDocumentError


def _parse_document_child(
    connection: Connection,
    content: bytes,
    mime_type: str,
    max_pages: int,
    max_characters: int,
    max_bytes: int,
    timeout_seconds: float,
) -> None:
    try:
        _apply_child_resource_limits(timeout_seconds)
        parsed = BoundedDocumentParser(
            max_pages=max_pages,
            max_characters=max_characters,
            max_bytes=max_bytes,
        ).parse(content, mime_type)
        connection.send(("ok", parsed))
    except DocumentParsingError as exc:
        connection.send(("error", exc.code))
    except Exception:
        connection.send(("error", DocumentParsingError.code))
    finally:
        connection.close()


def _apply_child_resource_limits(timeout_seconds: float) -> None:
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows has no resource module.
        return
    memory_limit = 512 * 1024 * 1024
    cpu_limit = max(1, int(timeout_seconds))
    try:
        memory_resource = resource.RLIMIT_DATA if sys.platform == "darwin" else resource.RLIMIT_AS
        resource.setrlimit(memory_resource, (memory_limit, memory_limit))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
    except (OSError, ValueError):
        # The parent still enforces the hard wall-clock termination boundary.
        return


def _stop_process(process: BaseProcess) -> None:
    process.terminate()
    process.join(timeout=1)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=1)


class BoundedDocumentParser:
    """Narrow PDF/DOCX/TXT parser. It extracts text only and never executes or fetches content."""

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

    def __init__(self, *, max_pages: int, max_characters: int, max_bytes: int = 15_000_000) -> None:
        self.max_pages = max_pages
        self.max_characters = max_characters
        self.max_bytes = max_bytes

    def parse(self, content: bytes, mime_type: str) -> ParsedDocument:
        if not content:
            raise MalformedDocumentError
        if len(content) > self.max_bytes:
            raise DocumentLimitError
        self._scan_for_malware_boundary(content)
        if mime_type == "text/plain":
            return self._parse_text(content)
        if mime_type == "application/pdf":
            return self._parse_pdf(content)
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._parse_docx(content)
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
            pages: list[str] = []
            extracted_characters = 0
            for page in reader.pages:
                page_text = page.extract_text() or ""
                extracted_characters += len(page_text)
                if extracted_characters > self.max_characters:
                    raise DocumentLimitError
                pages.append(page_text)
        except PasswordProtectedDocumentError:
            raise
        except DocumentLimitError:
            raise
        except Exception as exc:
            raise MalformedDocumentError from exc
        return self._normalise_pages(tuple(pages), numbered_pages=True)

    def _parse_docx(self, content: bytes) -> ParsedDocument:
        if not content.startswith(b"PK"):
            raise MalformedDocumentError
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 2_000 or sum(item.file_size for item in entries) > 50_000_000:
                    raise DocumentLimitError
                if any(
                    item.file_size > 20_000_000
                    or item.compress_size == 0 < item.file_size
                    or (item.compress_size > 0 and item.file_size / item.compress_size > 100)
                    for item in entries
                ):
                    raise DocumentLimitError
                xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise MalformedDocumentError from exc
        except zipfile.BadZipFile as exc:
            raise MalformedDocumentError from exc
        if len(xml) > 20_000_000:
            raise DocumentLimitError
        lowered = xml.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise UnsafeDocumentError
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise MalformedDocumentError from exc
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
            if text:
                paragraphs.append(text)
        return self._normalise_pages(("\n\n".join(paragraphs),), numbered_pages=False)

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


_DOCUMENT_ERROR_TYPES: dict[str, type[DocumentParsingError]] = {
    error_type.code: error_type
    for error_type in (
        DocumentParsingError,
        UnsupportedDocumentError,
        MalformedDocumentError,
        UnsafeDocumentError,
        PasswordProtectedDocumentError,
        DocumentLimitError,
    )
}
