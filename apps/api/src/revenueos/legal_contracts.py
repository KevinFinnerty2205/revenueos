from datetime import date, datetime
from typing import Literal
from uuid import UUID

from revenueos.contracts import APIModel

AcceptanceSource = Literal["trial_onboarding", "subscription_checkout", "administrative_onboarding"]


class LegalDocumentReleaseResponse(APIModel):
    status: Literal["draft", "approved"]
    version: str
    fingerprint: str
    effective_date: date | None
    href: str


class TermsAcceptanceEvidenceResponse(APIModel):
    id: UUID
    accepted_by_user_id: UUID
    terms_version: str
    terms_fingerprint: str
    terms_effective_date: date | None
    accepted_at: datetime
    acceptance_source: AcceptanceSource
    privacy_notice_version: str
    privacy_notice_fingerprint: str
    privacy_notice_effective_date: date | None
    privacy_notice_presented_at: datetime


class TermsAcceptanceStatusResponse(APIModel):
    terms: LegalDocumentReleaseResponse
    privacy_notice: LegalDocumentReleaseResponse
    accepted: bool
    acceptance_available: bool
    can_accept: bool
    evidence: TermsAcceptanceEvidenceResponse | None
    message: str


class TermsAcceptanceCreateRequest(APIModel):
    authority_and_terms_accepted: Literal[True]
    source: AcceptanceSource
