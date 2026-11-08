from __future__ import annotations

import asyncio
import html
import re
import socket
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import UUID

import httpx
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.document_parsing import BoundedDocumentParser, DocumentParsingError, parse_document_in_subprocess
from revenueos.models import CompanyKnowledgeIngestionJob, CompanyKnowledgeSource
from revenueos.prospect_url_security import (
    MAX_REDIRECTS,
    PublicUrlSafetyError,
    canonicalize_public_https_url,
    validate_resolved_public_addresses,
)

Resolver = Callable[[str], Awaitable[tuple[str, ...]]]


class KnowledgeIngestionError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes


class WebsiteTransport(Protocol):
    async def get(
        self,
        url: str,
        *,
        connect_ip: str,
        domain: str,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_bytes: int,
    ) -> TransportResponse: ...


@dataclass(frozen=True)
class FetchedWebsite:
    text: str
    final_url: str
    etag: str | None
    last_modified: str | None


class HttpxPinnedWebsiteTransport:
    """Make one bounded HTTPS request pinned to an already validated public IP."""

    async def get(
        self,
        url: str,
        *,
        connect_ip: str,
        domain: str,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_bytes: int,
    ) -> TransportResponse:
        parsed = urlsplit(url)
        network_host = f"[{connect_ip}]" if ":" in connect_ip else connect_ip
        pinned_url = urlunsplit(("https", network_host, parsed.path or "/", parsed.query, ""))
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                request = client.build_request(
                    "GET", pinned_url, headers={"Host": domain, "Accept": "text/html,text/plain"}
                )
                request.extensions["sni_hostname"] = domain
                async with client.stream(
                    request.method, request.url, headers=request.headers, extensions=request.extensions
                ) as response:
                    declared = response.headers.get("content-length")
                    if declared is not None and int(declared) > max_bytes:
                        raise KnowledgeIngestionError("website_response_too_large")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise KnowledgeIngestionError("website_response_too_large")
                        chunks.append(chunk)
                    return TransportResponse(response.status_code, dict(response.headers), b"".join(chunks))
        except KnowledgeIngestionError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError, OSError) as exc:
            raise KnowledgeIngestionError("website_fetch_unavailable", retryable=True) from exc
        except (ValueError, UnicodeError) as exc:
            raise KnowledgeIngestionError("website_response_invalid") from exc


class _VisibleHTML(HTMLParser):
    _ignored = frozenset({"script", "style", "svg", "template", "noscript", "iframe", "object"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in self._ignored:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._ignored and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            cleaned = re.sub(r"\s+", " ", html.unescape(data)).strip()
            if cleaned:
                self.parts.append(cleaned)


class SafeWebsiteFetcher:
    """Bounded redirect-following fetch with DNS validation and IP-pinned connections."""

    def __init__(
        self,
        settings: Settings,
        *,
        resolver: Resolver | None = None,
        transport: WebsiteTransport | None = None,
    ) -> None:
        self._settings = settings
        self._resolver = resolver or self._resolve
        self._transport = transport or HttpxPinnedWebsiteTransport()

    async def fetch(self, url: str) -> FetchedWebsite:
        current = canonicalize_public_https_url(url)
        visited: set[str] = set()
        for redirect_count in range(MAX_REDIRECTS + 1):
            if current.url in visited:
                raise KnowledgeIngestionError("website_redirect_loop")
            visited.add(current.url)
            try:
                addresses = await self._resolver(current.domain)
                validate_resolved_public_addresses(addresses)
            except PublicUrlSafetyError as exc:
                raise KnowledgeIngestionError(f"website_{exc.code}") from exc
            response = await self._transport.get(
                current.url,
                connect_ip=sorted(addresses)[0],
                domain=current.domain,
                connect_timeout_seconds=self._settings.knowledge_website_connect_timeout_seconds,
                read_timeout_seconds=self._settings.knowledge_website_read_timeout_seconds,
                max_bytes=self._settings.knowledge_website_max_response_bytes,
            )
            if len(response.content) > self._settings.knowledge_website_max_response_bytes:
                raise KnowledgeIngestionError("website_response_too_large")
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location or redirect_count >= MAX_REDIRECTS:
                    raise KnowledgeIngestionError("website_redirect_limit")
                try:
                    current = canonicalize_public_https_url(urljoin(current.url, location))
                except PublicUrlSafetyError as exc:
                    raise KnowledgeIngestionError(f"website_{exc.code}") from exc
                continue
            if response.status_code < 200 or response.status_code >= 300:
                retryable = response.status_code in {408, 425, 429} or response.status_code >= 500
                raise KnowledgeIngestionError("website_http_error", retryable=retryable)
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
            if content_type not in {"text/html", "text/plain"}:
                raise KnowledgeIngestionError("website_content_type_unsupported")
            decoded = response.content.decode("utf-8", errors="replace")
            extracted = self._extract_html(decoded) if content_type == "text/html" else decoded
            normalised = re.sub(r"[ \t]+", " ", extracted.replace("\r", "\n"))
            normalised = re.sub(r"\n{3,}", "\n\n", normalised).strip()
            if not normalised:
                raise KnowledgeIngestionError("website_content_empty")
            if len(normalised) > 500_000:
                raise KnowledgeIngestionError("website_text_limit")
            return FetchedWebsite(
                text=normalised,
                final_url=current.url,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            )
        raise KnowledgeIngestionError("website_redirect_limit")

    @staticmethod
    async def _resolve(domain: str) -> tuple[str, ...]:
        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, domain, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise KnowledgeIngestionError("website_dns_unavailable", retryable=True) from exc
        return tuple(sorted({str(item[4][0]) for item in infos}))

    @staticmethod
    def _extract_html(value: str) -> str:
        parser = _VisibleHTML()
        try:
            parser.feed(value)
            parser.close()
        except Exception as exc:
            raise KnowledgeIngestionError("website_html_invalid") from exc
        return "\n".join(parser.parts)


class DeterministicKnowledgeSynthesizer:
    """Produce a bounded extractive review summary without executing source instructions."""

    def summarize(self, text_value: str) -> str:
        candidates = [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text_value) if item.strip()]
        selected: list[str] = []
        total = 0
        for item in candidates:
            clipped = item[:500]
            if total + len(clipped) > 2_000:
                break
            selected.append(clipped)
            total += len(clipped)
            if len(selected) >= 6:
                break
        if not selected:
            raise KnowledgeIngestionError("knowledge_text_empty")
        return " ".join(selected)


@dataclass(frozen=True)
class ClaimedKnowledgeJob:
    organisation_id: UUID
    job_id: UUID
    source_id: UUID
    source_kind: str
    website_url: str | None
    source_text: str | None
    source_document: bytes | None
    source_mime_type: str | None
    attempt_count: int
    max_attempts: int
    worker_id: str


class KnowledgeIngestionWorkerService:
    """Process organisation knowledge in the existing bounded database worker."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        website_fetcher: SafeWebsiteFetcher | None = None,
        parser: BoundedDocumentParser | None = None,
        synthesizer: DeterministicKnowledgeSynthesizer | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._website_fetcher = website_fetcher or SafeWebsiteFetcher(settings)
        self._parser = parser or BoundedDocumentParser(
            max_pages=settings.private_beta_max_document_pages,
            max_characters=settings.private_beta_max_document_text_characters,
            max_bytes=settings.private_beta_max_document_bytes,
        )
        self._synthesizer = synthesizer or DeterministicKnowledgeSynthesizer()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_once(self, worker_id: str) -> bool:
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                organisations = list(
                    (
                        await session.scalars(
                            text("SELECT organisation_id FROM revenueos_knowledge_worker_eligible_organisations(1000)")
                        )
                    ).all()
                )
            else:
                organisations = list(
                    (
                        await session.scalars(
                            select(CompanyKnowledgeIngestionJob.organisation_id)
                            .where(CompanyKnowledgeIngestionJob.status.in_(("pending", "running")))
                            .distinct()
                        )
                    ).all()
                )
        processed = False
        for organisation_id in organisations:
            processed = bool(await self._recover_stale(organisation_id)) or processed
            claim = await self._claim(organisation_id, worker_id)
            if claim is not None:
                processed = True
                await self._execute(claim)
        return processed

    async def _claim(self, organisation_id: UUID, worker_id: str) -> ClaimedKnowledgeJob | None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            conditions = [
                CompanyKnowledgeIngestionJob.organisation_id == organisation_id,
                CompanyKnowledgeIngestionJob.status == "pending",
                CompanyKnowledgeIngestionJob.cancellation_requested_at.is_(None),
                CompanyKnowledgeIngestionJob.attempt_count < CompanyKnowledgeIngestionJob.max_attempts,
                or_(
                    CompanyKnowledgeIngestionJob.next_attempt_at.is_(None),
                    CompanyKnowledgeIngestionJob.next_attempt_at <= now,
                ),
            ]
            if not self._settings.feature_knowledge_website_fetch_enabled:
                conditions.append(CompanyKnowledgeSource.source_kind != "website")
            statement = (
                select(CompanyKnowledgeIngestionJob, CompanyKnowledgeSource)
                .join(
                    CompanyKnowledgeSource,
                    CompanyKnowledgeSource.id == CompanyKnowledgeIngestionJob.source_id,
                )
                .where(*conditions)
                .order_by(CompanyKnowledgeIngestionJob.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                return None
            job, source = row
            clean_worker_id = worker_id.strip()
            if not clean_worker_id or len(clean_worker_id) > 200:
                raise ValueError("Worker identity must contain 1 to 200 characters.")
            job.status = "running"
            job.attempt_count += 1
            job.worker_id = clean_worker_id
            job.started_at = now
            job.next_attempt_at = None
            job.lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            source.processing_status = "fetching" if source.source_kind == "website" else "extracting"
            source.processing_attempts += 1
            return ClaimedKnowledgeJob(
                organisation_id=organisation_id,
                job_id=job.id,
                source_id=source.id,
                source_kind=source.source_kind,
                website_url=source.website_url,
                source_text=source.source_text,
                source_document=source.source_document,
                source_mime_type=source.source_mime_type,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                worker_id=clean_worker_id,
            )

    async def _execute(self, claim: ClaimedKnowledgeJob) -> None:
        fetched: FetchedWebsite | None = None
        try:
            if claim.source_kind == "website":
                if claim.website_url is None:
                    raise KnowledgeIngestionError("knowledge_source_invalid")
                fetched = await self._website_fetcher.fetch(claim.website_url)
                extracted_text = fetched.text
            elif claim.source_kind in {"supporting_text", "text_file"}:
                if claim.source_text is None:
                    raise KnowledgeIngestionError("knowledge_source_invalid")
                extracted_text = claim.source_text
            elif claim.source_kind == "document":
                if claim.source_document is None or claim.source_mime_type is None:
                    raise KnowledgeIngestionError("knowledge_source_invalid")
                try:
                    if type(self._parser) is BoundedDocumentParser:
                        parsed = await asyncio.to_thread(
                            parse_document_in_subprocess,
                            claim.source_document,
                            claim.source_mime_type,
                            max_pages=self._parser.max_pages,
                            max_characters=self._parser.max_characters,
                            max_bytes=self._parser.max_bytes,
                            timeout_seconds=30,
                        )
                    else:
                        # Explicit test adapters remain injectable without crossing
                        # a process boundary; production uses the bounded parser.
                        parsed = await asyncio.wait_for(
                            asyncio.to_thread(
                                self._parser.parse,
                                claim.source_document,
                                claim.source_mime_type,
                            ),
                            timeout=30,
                        )
                except TimeoutError as exc:
                    raise KnowledgeIngestionError("document_parse_timeout", retryable=True) from exc
                except DocumentParsingError as exc:
                    raise KnowledgeIngestionError(exc.code) from exc
                extracted_text = "\n\n".join(item.text for item in parsed.fragments)
            else:
                raise KnowledgeIngestionError("knowledge_source_kind_unsupported")
            summary = self._synthesizer.summarize(extracted_text)
        except KnowledgeIngestionError as exc:
            await self._fail(claim, exc)
            return
        except Exception:
            # An unexpected parser or transport defect must fail this job,
            # not terminate the shared worker loop or strand its lease.
            await self._fail(
                claim,
                KnowledgeIngestionError("knowledge_processing_failed", retryable=True),
            )
            return
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await session.scalar(
                select(CompanyKnowledgeIngestionJob).where(
                    CompanyKnowledgeIngestionJob.organisation_id == claim.organisation_id,
                    CompanyKnowledgeIngestionJob.id == claim.job_id,
                )
            )
            source = await session.scalar(
                select(CompanyKnowledgeSource).where(
                    CompanyKnowledgeSource.organisation_id == claim.organisation_id,
                    CompanyKnowledgeSource.id == claim.source_id,
                )
            )
            if job is None or source is None or job.status != "running" or job.worker_id != claim.worker_id:
                return
            if job.cancellation_requested_at is not None:
                job.status = "cancelled"
                job.completed_at = now
                source.processing_status = "failed"
                source.failure_code = "ingestion_cancelled"
                return
            job.status = "completed"
            job.completed_at = now
            job.lease_expires_at = None
            source.extracted_text = extracted_text
            source.summary_text = summary
            source.processing_status = "ready_for_review"
            source.failure_code = None
            source.processed_at = now
            source.stale_at = None
            if fetched is not None:
                source.website_url = fetched.final_url
                source.last_http_etag = fetched.etag
                source.last_http_modified = fetched.last_modified

    async def _fail(self, claim: ClaimedKnowledgeJob, error: KnowledgeIngestionError) -> None:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            job = await session.scalar(
                select(CompanyKnowledgeIngestionJob).where(
                    CompanyKnowledgeIngestionJob.organisation_id == claim.organisation_id,
                    CompanyKnowledgeIngestionJob.id == claim.job_id,
                )
            )
            source = await session.scalar(
                select(CompanyKnowledgeSource).where(
                    CompanyKnowledgeSource.organisation_id == claim.organisation_id,
                    CompanyKnowledgeSource.id == claim.source_id,
                )
            )
            if job is None or source is None or job.status != "running" or job.worker_id != claim.worker_id:
                return
            if job.cancellation_requested_at is not None:
                job.status = "cancelled"
                job.completed_at = now
                job.failure_code = None
                job.worker_id = None
                job.lease_expires_at = None
                job.next_attempt_at = None
                source.processing_status = "failed"
                source.failure_code = "ingestion_cancelled"
                return
            job.failure_code = error.code
            job.worker_id = None
            job.lease_expires_at = None
            if error.retryable and claim.attempt_count < claim.max_attempts:
                job.status = "pending"
                job.next_attempt_at = now + timedelta(
                    seconds=self._settings.worker_base_retry_delay_seconds * (2 ** (claim.attempt_count - 1))
                )
                source.processing_status = "queued"
            else:
                job.status = "failed"
                job.completed_at = now
                source.processing_status = "failed"
            source.failure_code = error.code

    async def _recover_stale(self, organisation_id: UUID) -> int:
        now = self._clock()
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            jobs = list(
                (
                    await session.scalars(
                        select(CompanyKnowledgeIngestionJob)
                        .where(
                            CompanyKnowledgeIngestionJob.organisation_id == organisation_id,
                            CompanyKnowledgeIngestionJob.status == "running",
                            CompanyKnowledgeIngestionJob.lease_expires_at < now,
                        )
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for job in jobs:
                source = await session.scalar(
                    select(CompanyKnowledgeSource).where(
                        CompanyKnowledgeSource.organisation_id == organisation_id,
                        CompanyKnowledgeSource.id == job.source_id,
                    )
                )
                job.worker_id = None
                job.lease_expires_at = None
                if job.cancellation_requested_at is not None:
                    job.status = "cancelled"
                    job.completed_at = now
                    job.failure_code = None
                    job.next_attempt_at = None
                    if source is not None:
                        source.processing_status = "failed"
                        source.failure_code = "ingestion_cancelled"
                elif job.attempt_count < job.max_attempts:
                    job.status = "pending"
                    job.next_attempt_at = now
                    if source is not None:
                        source.processing_status = "queued"
                else:
                    job.status = "failed"
                    job.failure_code = "worker_lease_expired"
                    job.completed_at = now
                    if source is not None:
                        source.processing_status = "failed"
                        source.failure_code = "worker_lease_expired"
            return len(jobs)
