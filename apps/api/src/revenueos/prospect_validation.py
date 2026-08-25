from __future__ import annotations

import re

from revenueos.domain import ProspectContactPointType, ProspectSourceAuthority, ProspectTrustState
from revenueos.prospect_provider import PersonCandidate, ProviderPersonResearchResult, ProviderResearchResult
from revenueos.prospect_url_security import canonicalize_public_https_url

VERIFIED_AUTHORITIES = frozenset(
    {
        ProspectSourceAuthority.PRIMARY,
        ProspectSourceAuthority.OFFICIAL_PUBLIC,
        ProspectSourceAuthority.REGULATORY,
    }
)
INFERENCE_MARKERS = ("may ", "could ", "possible ", "might ", "worth exploring")
PROHIBITED_PERSON_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\breligio(?:n|us)\b",
        r"\bpolitic(?:s|al)\b",
        r"\bhealth\b",
        r"\bdisabilit(?:y|ies)\b",
        r"\bethnic(?:ity|ities)\b",
        r"\brace\b",
        r"\bsexual(?:ity| orientation)\b",
        r"\btrade[- ]union\b",
        r"\bcriminal history\b",
        r"\bfamil(?:y|ies)\b",
        r"\bchildren\b",
        r"\bhome address\b",
        r"\bdate of birth\b",
        r"\bprivate hobby\b",
        r"\bpersonal travel\b",
        r"\bpersonality (?:type|profile)\b",
    )
)
PUBLIC_MAILBOX_DOMAINS = frozenset(
    {"gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"}
)
APPROVED_PERSON_DISCOVERY_SOURCES = frozenset(
    {
        "company_leadership",
        "structured_provider",
        "professional_profile",
        "company_contact_page",
        "other_public",
    }
)


class ProspectResultValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_research_result(result: ProviderResearchResult | ProviderPersonResearchResult) -> None:
    source_by_key = {source.source_key: source for source in result.sources}
    if len(source_by_key) != len(result.sources):
        raise ProspectResultValidationError("duplicate_source", "The provider returned duplicate source identifiers.")
    canonical_urls: set[str] = set()
    fingerprints: set[str] = set()
    for source in result.sources:
        canonical = canonicalize_public_https_url(source.url)
        if canonical.url in canonical_urls or source.content_fingerprint in fingerprints:
            raise ProspectResultValidationError("duplicate_source", "The provider returned duplicate research sources.")
        canonical_urls.add(canonical.url)
        fingerprints.add(source.content_fingerprint)

    observation_keys: set[str] = set()
    for observation in result.observations:
        if observation.observation_key in observation_keys:
            raise ProspectResultValidationError(
                "duplicate_observation",
                "The provider returned duplicate research observations.",
            )
        observation_keys.add(observation.observation_key)
        cited = []
        for source_key in observation.source_keys:
            cited_source = source_by_key.get(source_key)
            if cited_source is None:
                raise ProspectResultValidationError(
                    "invalid_citation",
                    "A research observation cited a source outside its research run.",
                )
            cited.append(cited_source)
        if len(set(observation.source_keys)) != len(observation.source_keys):
            raise ProspectResultValidationError("duplicate_citation", "A research observation repeated a citation.")

        if observation.trust_state == ProspectTrustState.VERIFIED:
            if not cited or not any(source.authority_class in VERIFIED_AUTHORITIES for source in cited):
                raise ProspectResultValidationError(
                    "unverified_source",
                    "A verified observation did not cite an approved authoritative source.",
                )
        elif observation.trust_state == ProspectTrustState.PROVIDER_SUPPLIED:
            if not cited or not any(
                source.authority_class == ProspectSourceAuthority.STRUCTURED_PROVIDER for source in cited
            ):
                raise ProspectResultValidationError(
                    "invalid_provider_observation",
                    "Provider-supplied information did not cite its structured provider source.",
                )
        elif observation.trust_state == ProspectTrustState.INFERRED:
            if not cited or not any(marker in observation.statement.casefold() for marker in INFERENCE_MARKERS):
                raise ProspectResultValidationError(
                    "unsafe_inference",
                    "An inference was not cautiously worded and supported by cited public observations.",
                )
        elif observation.trust_state == ProspectTrustState.UNKNOWN and cited:
            raise ProspectResultValidationError(
                "invalid_unknown",
                "An unknown observation cannot present a source as proof of an unknown value.",
            )


def validate_person_candidate(candidate: PersonCandidate) -> None:
    for value in (
        candidate.display_name,
        candidate.current_role,
        candidate.current_company,
        candidate.public_professional_location or "",
        candidate.why_may_matter,
    ):
        _reject_prohibited_person_content(value)
    if candidate.discovery_source not in APPROVED_PERSON_DISCOVERY_SOURCES:
        raise ProspectResultValidationError(
            "unapproved_person_source",
            "A person identity did not originate from an approved professional source type.",
        )
    if not any(marker in candidate.why_may_matter.casefold() for marker in INFERENCE_MARKERS):
        raise ProspectResultValidationError(
            "unsafe_person_relevance",
            "A person relevance explanation was not cautiously worded.",
        )


def validate_person_research_result(
    result: ProviderPersonResearchResult,
    *,
    company_domain: str | None = None,
) -> None:
    validate_research_result(result)
    _reject_prohibited_person_content(result.current_role)
    _reject_prohibited_person_content(result.why_may_matter)
    if not any(marker in result.why_may_matter.casefold() for marker in INFERENCE_MARKERS):
        raise ProspectResultValidationError(
            "unsafe_person_relevance",
            "A person relevance explanation was not cautiously worded.",
        )
    if not any(observation.category.value == "why_person_matters" for observation in result.observations):
        raise ProspectResultValidationError(
            "unsupported_person_relevance",
            "Person research must contain a source-backed relevance observation.",
        )
    for source in result.sources:
        _reject_prohibited_person_content(source.title)
    for observation in result.observations:
        _reject_prohibited_person_content(observation.statement)

    source_by_key = {source.source_key: source for source in result.sources}
    current_role_observations = [
        observation for observation in result.observations if observation.category.value == "current_role"
    ]
    if len(current_role_observations) != 1:
        raise ProspectResultValidationError(
            "unsupported_current_employment",
            "Person research must contain one source-backed current-employment observation.",
        )
    current_role_observation = current_role_observations[0]
    if (
        current_role_observation.trust_state not in (ProspectTrustState.VERIFIED, ProspectTrustState.PROVIDER_SUPPLIED)
        or current_role_observation.observed_at is None
        or current_role_observation.freshness != "time_sensitive"
    ):
        raise ProspectResultValidationError(
            "stale_current_employment",
            "Current employment was not supported by a dated, time-sensitive professional source.",
        )
    role_keys: set[str] = set()
    for hypothesis in result.buying_roles:
        if hypothesis.role.value in role_keys:
            raise ProspectResultValidationError(
                "duplicate_buying_role",
                "The provider returned the same buying-role hypothesis more than once.",
            )
        role_keys.add(hypothesis.role.value)
        _reject_prohibited_person_content(hypothesis.rationale)
        if hypothesis.trust_state == ProspectTrustState.VERIFIED:
            raise ProspectResultValidationError(
                "confirmed_buying_role",
                "Public research cannot confirm a customer buying role.",
            )
        if not hypothesis.source_keys or any(key not in source_by_key for key in hypothesis.source_keys):
            raise ProspectResultValidationError(
                "invalid_buying_role_citation",
                "A buying-role hypothesis cited a source outside its person research run.",
            )
        if not any(marker in hypothesis.rationale.casefold() for marker in INFERENCE_MARKERS):
            raise ProspectResultValidationError(
                "unsafe_buying_role",
                "A buying-role hypothesis was not cautiously worded.",
            )

    contact_fingerprints: set[tuple[str, str]] = set()
    for contact in result.contact_points:
        contact_source = source_by_key.get(contact.source_key)
        if contact_source is None:
            raise ProspectResultValidationError(
                "invalid_contact_citation",
                "A business contact point cited a source outside its person research run.",
            )
        normalised_value = contact.value.strip().casefold()
        key = (contact.point_type.value, normalised_value)
        if key in contact_fingerprints:
            raise ProspectResultValidationError(
                "duplicate_contact_point",
                "The provider returned a duplicate business contact point.",
            )
        contact_fingerprints.add(key)
        if contact.trust_state in (ProspectTrustState.INFERRED, ProspectTrustState.UNKNOWN):
            raise ProspectResultValidationError(
                "unsupported_contact_inference",
                "WO-027 does not persist inferred or synthetic contact values.",
            )
        if contact.point_type == ProspectContactPointType.BUSINESS_PHONE:
            raise ProspectResultValidationError(
                "personal_phone_not_supported",
                "Personal or direct phone data is not supported in this release.",
            )
        if contact.point_type == ProspectContactPointType.BUSINESS_EMAIL:
            if "@" not in normalised_value:
                raise ProspectResultValidationError("invalid_business_email", "A business email was malformed.")
            domain = normalised_value.rsplit("@", 1)[1]
            if domain in PUBLIC_MAILBOX_DOMAINS:
                raise ProspectResultValidationError(
                    "personal_email_not_supported",
                    "Personal mailbox addresses are not supported.",
                )
            if company_domain is not None and not (
                domain == company_domain.casefold() or domain.endswith(f".{company_domain.casefold()}")
            ):
                raise ProspectResultValidationError(
                    "non_company_business_email",
                    "A business email did not use the researched company domain.",
                )
        if contact.point_type == ProspectContactPointType.PUBLIC_PROFESSIONAL_PROFILE:
            canonicalize_public_https_url(contact.value)
        if contact.trust_state == ProspectTrustState.VERIFIED:
            if (
                contact.verification_method != "authoritative_public"
                or contact_source.authority_class not in VERIFIED_AUTHORITIES
            ):
                raise ProspectResultValidationError(
                    "invalid_contact_verification",
                    "A verified business contact point lacked an approved verification method and source.",
                )
        if contact.trust_state == ProspectTrustState.PROVIDER_SUPPLIED:
            if (
                contact.verification_method != "provider_reported"
                or contact_source.authority_class != ProspectSourceAuthority.STRUCTURED_PROVIDER
            ):
                raise ProspectResultValidationError(
                    "invalid_provider_contact",
                    "Provider-supplied contact information lacked provider provenance.",
                )
        if contact.expires_at is not None and contact.expires_at <= contact.observed_at:
            raise ProspectResultValidationError(
                "invalid_contact_expiry",
                "A provider contact retention expiry was not after its observation time.",
            )


def _reject_prohibited_person_content(value: str) -> None:
    if any(pattern.search(value) for pattern in PROHIBITED_PERSON_PATTERNS):
        raise ProspectResultValidationError(
            "prohibited_person_data",
            "Person research included private, sensitive or prohibited personal information.",
        )
