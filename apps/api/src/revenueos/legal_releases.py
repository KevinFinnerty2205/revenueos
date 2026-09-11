from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from revenueos.config import Environment

LegalReleaseStatus = Literal["draft", "approved"]


@dataclass(frozen=True)
class LegalDocumentRelease:
    status: LegalReleaseStatus
    version: str
    sha256: str
    effective_date: date | None
    href: str
    canonical_source: str


# These fingerprints identify the exact canonical Markdown documents on PR #88
# at commit 49761341636f310ade1c42bf25a4699bdbf758c3. They deliberately exclude
# rendered navigation and footer content. Updating either identity requires the
# reviewed legal-release procedure and must never rewrite an acceptance row.
CURRENT_TERMS_RELEASE = LegalDocumentRelease(
    status="draft",
    version="owner-review-draft-v1",
    sha256="9425fe5c0d056e7669ee1fc8e3f977a5cd7d639ce775d36926bb89de54330652",
    effective_date=None,
    href="/terms",
    canonical_source="docs/00-company/oryntela-terms-and-conditions.md",
)

CURRENT_PRIVACY_NOTICE = LegalDocumentRelease(
    status="draft",
    version="owner-review-draft-v1",
    sha256="31cbce440f61c97f033c8cca75b252f56a21832cc8b8585387e553327f681c22",
    effective_date=None,
    href="/privacy",
    canonical_source="docs/00-company/oryntela-privacy-policy.md",
)


def acceptance_available(environment: Environment) -> bool:
    if environment in {"development", "test"}:
        return True
    return (
        CURRENT_TERMS_RELEASE.status == "approved"
        and CURRENT_TERMS_RELEASE.effective_date is not None
        and CURRENT_PRIVACY_NOTICE.status == "approved"
        and CURRENT_PRIVACY_NOTICE.effective_date is not None
    )
