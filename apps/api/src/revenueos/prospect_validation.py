from __future__ import annotations

from revenueos.domain import ProspectSourceAuthority, ProspectTrustState
from revenueos.prospect_provider import ProviderResearchResult
from revenueos.prospect_url_security import canonicalize_public_https_url

VERIFIED_AUTHORITIES = frozenset(
    {
        ProspectSourceAuthority.PRIMARY,
        ProspectSourceAuthority.OFFICIAL_PUBLIC,
        ProspectSourceAuthority.REGULATORY,
    }
)
INFERENCE_MARKERS = ("may ", "could ", "possible ", "might ", "worth exploring")


class ProspectResultValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_research_result(result: ProviderResearchResult) -> None:
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
