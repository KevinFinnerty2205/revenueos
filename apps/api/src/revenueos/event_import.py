from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import ipaddress
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import PurePath
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from email_validator import EmailNotValidError, validate_email

EventImportField = Literal[
    "first_name",
    "last_name",
    "company_name",
    "job_title",
    "business_email",
    "country_or_location",
    "profile_url",
    "company_domain",
    "registration_category",
]

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 500
MAX_COLUMNS = 50
MAX_CELL_CHARACTERS = 1_000

AUTHORITY_STATEMENT = (
    "I confirm my organisation is authorised to use this attendee information for this business purpose."
)
PERMISSION_NOTICE = (
    "Being listed as an event attendee does not automatically make a person eligible for outreach. "
    "RevenueOS checks your organisation's Engage policy and Contact suppression/contactability before sending."
)

_HEADER_NORMALISER = re.compile(r"[^a-z0-9]+")
_FORMULA_PREFIXES = ("=", "+", "-", "@")
_PERSONAL_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "icloud.com",
        "me.com",
        "yahoo.com",
        "yahoo.com.au",
        "proton.me",
        "protonmail.com",
    }
)
_GENERIC_MAILBOX_LOCAL_PARTS = frozenset(
    {
        "admin",
        "contact",
        "enquiries",
        "events",
        "hello",
        "info",
        "office",
        "sales",
        "support",
        "team",
    }
)

_SYNONYMS: dict[str, EventImportField] = {
    "first name": "first_name",
    "firstname": "first_name",
    "given name": "first_name",
    "givenname": "first_name",
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "family name": "last_name",
    "company": "company_name",
    "company name": "company_name",
    "organisation": "company_name",
    "organization": "company_name",
    "organisation name": "company_name",
    "organization name": "company_name",
    "job title": "job_title",
    "title": "job_title",
    "role": "job_title",
    "position": "job_title",
    "business email": "business_email",
    "work email": "business_email",
    "email": "business_email",
    "country": "country_or_location",
    "location": "country_or_location",
    "country location": "country_or_location",
    "profile url": "profile_url",
    "professional profile": "profile_url",
    "linkedin url": "profile_url",
    "linkedin": "profile_url",
    "company domain": "company_domain",
    "domain": "company_domain",
    "website domain": "company_domain",
    "registration category": "registration_category",
    "attendee type": "registration_category",
    "ticket type": "registration_category",
}

_SENSITIVE_HEADERS = frozenset(
    {
        "home address",
        "personal address",
        "residential address",
        "date of birth",
        "dob",
        "birth date",
        "dietary requirements",
        "dietary requirement",
        "dietary restrictions",
        "allergies",
        "health information",
        "medical information",
        "disability",
        "ethnicity",
        "religion",
        "sexual orientation",
        "gender identity",
        "personal mobile",
        "private mobile",
        "personal phone",
        "emergency contact",
        "passport number",
        "government id",
    }
)


class EventImportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedAttendeeRow:
    source_row: int
    first_name: str | None
    last_name: str | None
    company_name: str | None
    job_title: str | None
    business_email: str | None
    country_or_location: str | None
    profile_url: str | None
    company_domain: str | None
    registration_category: str | None

    def json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ImportColumn:
    source_column: str
    mapped_field: EventImportField | None
    reason: str | None = None

    def json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ImportIssue:
    code: str
    count: int
    rows: tuple[int, ...]
    message: str

    def json(self) -> dict[str, object]:
        return {**asdict(self), "rows": list(self.rows)}


@dataclass(frozen=True)
class EventCSVPreview:
    file_name: str
    file_size_bytes: int
    file_fingerprint: str
    row_count: int
    rows: tuple[ParsedAttendeeRow, ...]
    recognised: tuple[ImportColumn, ...]
    ignored: tuple[ImportColumn, ...]
    issues: tuple[ImportIssue, ...]
    mapping: dict[str, EventImportField | None]


def _normalise_header(value: str) -> str:
    return _HEADER_NORMALISER.sub(" ", value.strip().casefold()).strip()


def _safe_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name.strip()
    if not name or len(name) > 255 or not name.casefold().endswith(".csv"):
        raise EventImportError("unsupported_file", "Choose a CSV file with a .csv extension.")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise EventImportError("unsafe_filename", "The CSV filename contains unsupported characters.")
    return name


def decode_csv(file_name: str, content_base64: str) -> tuple[str, bytes]:
    safe_name = _safe_filename(file_name)
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EventImportError("invalid_file_encoding", "The selected CSV could not be decoded.") from exc
    if not content:
        raise EventImportError("empty_file", "The selected CSV is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise EventImportError("file_too_large", "Attendee CSV files may be at most 5 MB.")
    if b"\x00" in content:
        raise EventImportError("invalid_csv", "The selected CSV contains null bytes and was rejected.")
    return safe_name, content


def parse_event_csv(
    file_name: str,
    content: bytes,
    requested_mapping: dict[str, EventImportField | None],
) -> EventCSVPreview:
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise EventImportError("invalid_file_encoding", "CSV files must use UTF-8 encoding.") from exc
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), delimiter=",", strict=True)
        raw_rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        raise EventImportError("malformed_csv", "The selected file is not a well-formed comma-separated CSV.") from exc
    if not raw_rows:
        raise EventImportError("empty_file", "The selected CSV is empty.")
    headers = [header.strip() for header in raw_rows[0]]
    if not headers or not any(headers):
        raise EventImportError("missing_headers", "The CSV must contain a header row.")
    if len(headers) > MAX_COLUMNS:
        raise EventImportError("too_many_columns", "Attendee CSV files may contain at most 50 columns.")
    if any(not header or len(header) > 100 for header in headers):
        raise EventImportError("invalid_headers", "Every CSV column needs a bounded header.")
    normalised_headers = [_normalise_header(header) for header in headers]
    if len(set(normalised_headers)) != len(normalised_headers):
        raise EventImportError("duplicate_headers", "CSV column headers must be unique.")
    non_empty_rows = [row for row in raw_rows[1:] if any(cell.strip() for cell in row)]
    if len(non_empty_rows) > MAX_ROWS:
        raise EventImportError("too_many_rows", "Attendee imports are limited to 500 rows per Event.")

    header_lookup = {header: index for index, header in enumerate(headers)}
    requested_lookup = {_normalise_header(key): value for key, value in requested_mapping.items()}
    unknown_requested = [key for key in requested_mapping if _normalise_header(key) not in normalised_headers]
    if unknown_requested:
        raise EventImportError("unknown_mapping_column", "Column mapping contains a header that is not in this CSV.")

    mapping: dict[str, EventImportField | None] = {}
    seen_targets: set[EventImportField] = set()
    recognised: list[ImportColumn] = []
    ignored: list[ImportColumn] = []
    for header, normalised in zip(headers, normalised_headers, strict=True):
        sensitive = normalised in _SENSITIVE_HEADERS
        target = requested_lookup.get(normalised, _SYNONYMS.get(normalised))
        if sensitive and target is not None:
            raise EventImportError(
                "sensitive_column_mapping",
                f"The sensitive column '{header}' cannot be mapped into Event attendee data.",
            )
        if target is not None and target in seen_targets:
            raise EventImportError("duplicate_field_mapping", "Only one CSV column may map to each attendee field.")
        mapping[header] = target
        if target is not None:
            seen_targets.add(target)
            recognised.append(ImportColumn(header, target))
        else:
            ignored.append(
                ImportColumn(
                    header,
                    None,
                    "Sensitive or private registration data is not accepted."
                    if sensitive
                    else "Column is not approved.",
                )
            )
    if not recognised:
        raise EventImportError("no_recognised_columns", "Map at least one approved attendee column before previewing.")

    issue_rows: dict[str, list[int]] = {}

    def note(code: str, row_number: int) -> None:
        issue_rows.setdefault(code, []).append(row_number)

    parsed_rows: list[ParsedAttendeeRow] = []
    seen_email: set[str] = set()
    seen_profile: set[str] = set()
    for data_index, raw_row in enumerate(non_empty_rows, start=2):
        if len(raw_row) > len(headers):
            note("malformed_row", data_index)
            continue
        padded = [*raw_row, *([""] * (len(headers) - len(raw_row)))]
        if any(len(cell) > MAX_CELL_CHARACTERS for cell in padded):
            note("field_too_long", data_index)
            continue
        values: dict[EventImportField, str] = {}
        for header, target in mapping.items():
            if target is None:
                continue
            value = padded[header_lookup[header]].strip()
            if value:
                values[target] = value
                if value.startswith(_FORMULA_PREFIXES):
                    note("formula_like_text", data_index)

        first_name = _bounded(values.get("first_name"), 100, data_index, note)
        last_name = _bounded(values.get("last_name"), 100, data_index, note)
        company_name = _bounded(values.get("company_name"), 200, data_index, note)
        job_title = _bounded(values.get("job_title"), 200, data_index, note)
        location = _bounded(values.get("country_or_location"), 200, data_index, note)
        category = _bounded(values.get("registration_category"), 80, data_index, note)
        email = _business_email(values.get("business_email"), data_index, note)
        profile = _https_url(values.get("profile_url"), data_index, "invalid_profile_url", note)
        domain = _company_domain(values.get("company_domain"), data_index, note)

        strong_email = email if email is not None and is_strong_business_email(email) else None
        if strong_email is not None and strong_email in seen_email:
            note("duplicate_strong_identity", data_index)
            continue
        if profile is not None and profile in seen_profile:
            note("duplicate_strong_identity", data_index)
            continue
        if strong_email is None and not (first_name and company_name):
            note("missing_identity", data_index)
            continue
        if strong_email is not None:
            seen_email.add(strong_email)
        if profile is not None:
            seen_profile.add(profile)
        parsed_rows.append(
            ParsedAttendeeRow(
                source_row=data_index,
                first_name=first_name,
                last_name=last_name,
                company_name=company_name,
                job_title=job_title,
                business_email=email,
                country_or_location=location,
                profile_url=profile,
                company_domain=domain,
                registration_category=category,
            )
        )

    issue_messages = {
        "malformed_row": "Rows with more cells than the header were rejected.",
        "field_too_long": "Rows containing an unbounded field were rejected.",
        "formula_like_text": "Formula-looking values are treated only as text and are never executed.",
        "invalid_email": "Invalid business email values were ignored.",
        "personal_email": "Personal/free-mail addresses are not accepted as business email.",
        "invalid_profile_url": "Profile URLs must be safe HTTPS URLs.",
        "invalid_company_domain": "Company domains must be public DNS names or HTTPS URLs.",
        "duplicate_strong_identity": "Duplicate exact email/profile rows were skipped.",
        "missing_identity": "Rows need a person-specific business email or a name and company.",
        "value_truncated_rejected": "Values beyond the approved field limit were ignored.",
    }
    issues = tuple(
        ImportIssue(code, len(rows), tuple(rows[:10]), issue_messages[code])
        for code, rows in sorted(issue_rows.items())
    )
    if not parsed_rows:
        raise EventImportError(
            "no_valid_rows",
            "No attendee rows met the approved identity and business-data requirements.",
        )
    return EventCSVPreview(
        file_name=file_name,
        file_size_bytes=len(content),
        file_fingerprint=hashlib.sha256(content).hexdigest(),
        row_count=len(non_empty_rows),
        rows=tuple(parsed_rows),
        recognised=tuple(recognised),
        ignored=tuple(ignored),
        issues=issues,
        mapping=mapping,
    )


def _bounded(
    value: str | None,
    maximum: int,
    row_number: int,
    note: Callable[[str, int], None],
) -> str | None:
    if value is None:
        return None
    if len(value) > maximum:
        note("value_truncated_rejected", row_number)
        return None
    return value


def _business_email(value: str | None, row_number: int, note: Callable[[str, int], None]) -> str | None:
    if value is None:
        return None
    try:
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        note("invalid_email", row_number)
        return None
    email = result.normalized.casefold()
    domain = email.rsplit("@", 1)[1]
    if domain in _PERSONAL_EMAIL_DOMAINS:
        note("personal_email", row_number)
        return None
    return email


def is_strong_business_email(value: str) -> bool:
    """Return whether an address is suitable for exact person matching.

    Shared role inboxes remain approved Event-list display data, but cannot act
    as a strong person identity or silently merge two attendees.
    """
    local_part = value.rsplit("@", 1)[0].casefold().split("+", 1)[0]
    return local_part not in _GENERIC_MAILBOX_LOCAL_PARTS


def _https_url(
    value: str | None,
    row_number: int,
    code: str,
    note: Callable[[str, int], None],
) -> str | None:
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ValueError
        host = parsed.hostname.encode("idna").decode("ascii").casefold()
        _validate_public_hostname(host)
    except (UnicodeError, ValueError):
        note(code, row_number)
        return None
    return urlunsplit(("https", host, parsed.path or "", parsed.query, ""))


def _company_domain(value: str | None, row_number: int, note: Callable[[str, int], None]) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
        if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
        if parsed.port not in (None, 443):
            raise ValueError
        host = parsed.hostname.encode("idna").decode("ascii").casefold().rstrip(".")
        _validate_public_hostname(host)
    except (UnicodeError, ValueError):
        note("invalid_company_domain", row_number)
        return None
    return host


def _validate_public_hostname(host: str) -> None:
    if len(host) > 253 or "." not in host or host == "localhost" or host.endswith(".local"):
        raise ValueError
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError
    labels = host.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        raise ValueError
    if any(not re.fullmatch(r"[a-z0-9-]+", label) for label in labels):
        raise ValueError
