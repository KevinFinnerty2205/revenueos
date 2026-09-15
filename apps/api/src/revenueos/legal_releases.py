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


# These fingerprints identify the exact owner-approved canonical Markdown
# documents effective on 15 September 2026. They deliberately exclude rendered
# navigation and footer content. Updating either identity requires the reviewed
# legal-release procedure and must never rewrite an acceptance row.
CURRENT_TERMS_RELEASE = LegalDocumentRelease(
    status="approved",
    version="2026-09-15",
    sha256="0c4fea346d5f4774a92819b1a8be1e83dcb1289d2650acce0bafc5f400cea3f7",
    effective_date=date(2026, 9, 15),
    href="/terms",
    canonical_source="docs/00-company/oryntela-terms-and-conditions.md",
)

CURRENT_PRIVACY_NOTICE = LegalDocumentRelease(
    status="approved",
    version="2026-09-15",
    sha256="c707fa92f6dcd2dd4657a60fe96dce9f04bd805a15112cd224fa740fbc6cc1d5",
    effective_date=date(2026, 9, 15),
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
