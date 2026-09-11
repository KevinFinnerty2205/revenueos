from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.legal_contracts import (
    AcceptanceSource,
    LegalDocumentReleaseResponse,
    TermsAcceptanceEvidenceResponse,
    TermsAcceptanceStatusResponse,
)
from revenueos.legal_releases import (
    CURRENT_PRIVACY_NOTICE,
    CURRENT_TERMS_RELEASE,
    LegalDocumentRelease,
    acceptance_available,
)
from revenueos.models import Organisation, TermsAcceptance

if TYPE_CHECKING:
    from revenueos.tenant import TenantContext


def _release_response(document: LegalDocumentRelease) -> LegalDocumentReleaseResponse:
    return LegalDocumentReleaseResponse(
        status=document.status,
        version=document.version,
        fingerprint=f"sha256:{document.sha256}",
        effective_date=document.effective_date,
        href=document.href,
    )


def _evidence_response(record: TermsAcceptance) -> TermsAcceptanceEvidenceResponse:
    return TermsAcceptanceEvidenceResponse(
        id=record.id,
        accepted_by_user_id=record.accepted_by_user_id,
        terms_version=record.terms_version,
        terms_fingerprint=f"sha256:{record.terms_sha256}",
        terms_effective_date=record.terms_effective_date,
        accepted_at=record.accepted_at,
        acceptance_source=cast(AcceptanceSource, record.acceptance_source),
        privacy_notice_version=record.privacy_notice_version,
        privacy_notice_fingerprint=f"sha256:{record.privacy_notice_sha256}",
        privacy_notice_effective_date=record.privacy_notice_effective_date,
        privacy_notice_presented_at=record.privacy_notice_presented_at,
    )


async def current_terms_acceptance(session: AsyncSession, organisation_id: UUID) -> TermsAcceptance | None:
    record: TermsAcceptance | None = await session.scalar(
        select(TermsAcceptance).where(
            TermsAcceptance.organisation_id == organisation_id,
            TermsAcceptance.release_status == CURRENT_TERMS_RELEASE.status,
            TermsAcceptance.terms_version == CURRENT_TERMS_RELEASE.version,
            TermsAcceptance.terms_sha256 == CURRENT_TERMS_RELEASE.sha256,
            TermsAcceptance.terms_effective_date == CURRENT_TERMS_RELEASE.effective_date,
            TermsAcceptance.privacy_notice_version == CURRENT_PRIVACY_NOTICE.version,
            TermsAcceptance.privacy_notice_sha256 == CURRENT_PRIVACY_NOTICE.sha256,
            TermsAcceptance.privacy_notice_effective_date == CURRENT_PRIVACY_NOTICE.effective_date,
        )
    )
    return record


async def require_current_terms_acceptance(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
) -> TermsAcceptance:
    if not acceptance_available(settings.environment):
        raise PublicAPIError(
            "terms_acceptance_unavailable",
            "Terms acceptance is not available until the current legal release is owner-approved.",
            503,
        )
    record = await current_terms_acceptance(session, organisation_id)
    if record is None:
        raise PublicAPIError(
            "terms_acceptance_required",
            "An organisation administrator must accept the current Terms before this action can continue.",
            409,
        )
    return record


class LegalService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self._now = now

    async def status(self) -> TermsAcceptanceStatusResponse:
        record = await current_terms_acceptance(self.session, self.tenant.organisation_id)
        available = acceptance_available(self.settings.environment)
        accepted = available and record is not None
        if not available:
            message = "Terms acceptance is disabled until the legal documents are owner-approved and effective."
        elif accepted:
            message = "Your organisation has accepted the current Terms."
        elif self.tenant.can_manage():
            message = "An organisation administrator must accept the current Terms before continuing."
        else:
            message = "Ask an organisation administrator to accept the current Terms before continuing."
        return TermsAcceptanceStatusResponse(
            terms=_release_response(CURRENT_TERMS_RELEASE),
            privacy_notice=_release_response(CURRENT_PRIVACY_NOTICE),
            accepted=accepted,
            acceptance_available=available,
            can_accept=available and self.tenant.can_manage(),
            evidence=_evidence_response(record) if record is not None else None,
            message=message,
        )

    async def accept_current(self, source: AcceptanceSource) -> TermsAcceptanceStatusResponse:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Organisation administrator authority is required.", 403)
        if not acceptance_available(self.settings.environment):
            raise PublicAPIError(
                "terms_acceptance_unavailable",
                "Terms acceptance is not available until the current legal release is owner-approved.",
                503,
            )
        organisation = await self.session.scalar(
            select(Organisation).where(Organisation.id == self.tenant.organisation_id).with_for_update()
        )
        if organisation is None:
            raise PublicAPIError("organisation_unavailable", "The active organisation is unavailable.", 404)
        existing = await current_terms_acceptance(self.session, self.tenant.organisation_id)
        if existing is not None:
            return await self.status()
        accepted_at = self._now()
        self.session.add(
            TermsAcceptance(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                accepted_by_user_id=self.tenant.user_id,
                release_status=CURRENT_TERMS_RELEASE.status,
                terms_version=CURRENT_TERMS_RELEASE.version,
                terms_sha256=CURRENT_TERMS_RELEASE.sha256,
                terms_effective_date=CURRENT_TERMS_RELEASE.effective_date,
                accepted_at=accepted_at,
                acceptance_source=source,
                privacy_notice_version=CURRENT_PRIVACY_NOTICE.version,
                privacy_notice_sha256=CURRENT_PRIVACY_NOTICE.sha256,
                privacy_notice_effective_date=CURRENT_PRIVACY_NOTICE.effective_date,
                privacy_notice_presented_at=accepted_at,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            if await current_terms_acceptance(self.session, self.tenant.organisation_id) is None:
                raise
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        return await self.status()
