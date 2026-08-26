from __future__ import annotations

from dataclasses import dataclass

from revenueos.domain import (
    ProspectCandidateMatchState,
    ProspectCandidatePriority,
    ProspectRelationshipState,
    ProspectTrustState,
)
from revenueos.models import ProspectTargetMarketVersion
from revenueos.prospect_discovery_provider import DiscoveredCompany

EMPLOYEE_BAND_RANK = {
    "50_199": 0,
    "200_499": 1,
    "500_999": 2,
    "1000_4999": 3,
    "5000_plus": 4,
}


@dataclass(frozen=True)
class MatchReason:
    reason_code: str
    criterion_key: str
    state: str
    text: str
    data_origin: str
    trust_state: ProspectTrustState
    observed_value_class: str | None = None
    source_reference: str | None = None


@dataclass(frozen=True)
class MatchResult:
    match_state: ProspectCandidateMatchState
    priority: ProspectCandidatePriority
    reasons: tuple[MatchReason, ...]
    missing_information: tuple[str, ...]


def evaluate_candidate(
    definition: ProspectTargetMarketVersion,
    candidate: DiscoveredCompany,
    relationship_state: ProspectRelationshipState,
) -> MatchResult:
    reasons: list[MatchReason] = []
    missing: list[str] = []
    excluded = False

    def provider_reason(
        code: str,
        criterion: str,
        state: str,
        text: str,
        observed: str | None,
    ) -> None:
        reasons.append(
            MatchReason(
                reason_code=code,
                criterion_key=criterion,
                state=state,
                text=text,
                data_origin="provider_supplied" if observed is not None else "unknown",
                trust_state=(
                    ProspectTrustState.PROVIDER_SUPPLIED if observed is not None else ProspectTrustState.UNKNOWN
                ),
                observed_value_class=observed,
            )
        )

    if candidate.industry in definition.excluded_industries:
        provider_reason(
            "excluded_industry",
            "excluded_industries",
            "excluded",
            f"Excluded industry: {candidate.industry}.",
            candidate.industry,
        )
        excluded = True
    elif definition.industries:
        if candidate.industry is None:
            provider_reason(
                "unknown_industry",
                "industries",
                "missing",
                "Industry could not be established.",
                None,
            )
            missing.append("Industry")
        elif candidate.industry in definition.industries:
            provider_reason(
                "industry_match",
                "industries",
                "matched",
                f"Matches your {candidate.industry} industry criterion.",
                candidate.industry,
            )
        else:
            provider_reason(
                "industry_mismatch",
                "industries",
                "excluded",
                f"Industry is {candidate.industry}, outside the selected industries.",
                candidate.industry,
            )
            excluded = True

    if candidate.country_code is None:
        provider_reason(
            "unknown_geography",
            "countries",
            "missing",
            "Country could not be established.",
            None,
        )
        missing.append("Country")
    elif candidate.country_code in definition.countries:
        provider_reason(
            "geography_match",
            "countries",
            "matched",
            f"Located in {candidate.country_code}, within this target market.",
            candidate.country_code,
        )
    else:
        provider_reason(
            "outside_territory",
            "countries",
            "excluded",
            f"Located in {candidate.country_code}, outside this target market.",
            candidate.country_code,
        )
        excluded = True

    if definition.regions:
        if candidate.region is None:
            provider_reason(
                "unknown_region",
                "regions",
                "missing",
                "State or region could not be established.",
                None,
            )
            missing.append("State or region")
        elif candidate.region in definition.regions:
            provider_reason(
                "region_match",
                "regions",
                "matched",
                f"Located in the selected {candidate.region} region.",
                candidate.region,
            )
        else:
            provider_reason(
                "outside_region",
                "regions",
                "excluded",
                f"Located in {candidate.region}, outside the selected regions.",
                candidate.region,
            )
            excluded = True

    if definition.minimum_employee_band is not None:
        if candidate.employee_band is None:
            provider_reason(
                "unknown_size",
                "minimum_employee_band",
                "missing",
                "Company size could not be established.",
                None,
            )
            missing.append("Company size")
        elif EMPLOYEE_BAND_RANK[candidate.employee_band] >= EMPLOYEE_BAND_RANK[definition.minimum_employee_band]:
            provider_reason(
                "size_match",
                "minimum_employee_band",
                "matched",
                f"Employee band {candidate.employee_band.replace('_', '–')} meets the selected minimum.",
                candidate.employee_band,
            )
        else:
            provider_reason(
                "size_below_minimum",
                "minimum_employee_band",
                "excluded",
                f"Employee band {candidate.employee_band.replace('_', '–')} is below the selected minimum.",
                candidate.employee_band,
            )
            excluded = True

    if definition.organisation_types:
        if candidate.organisation_type is None:
            provider_reason(
                "unknown_organisation_type",
                "organisation_types",
                "missing",
                "Organisation type could not be established.",
                None,
            )
            missing.append("Organisation type")
        elif candidate.organisation_type in definition.organisation_types:
            provider_reason(
                "organisation_type_match",
                "organisation_types",
                "matched",
                f"Matches the selected {candidate.organisation_type.replace('_', ' ')} organisation type.",
                candidate.organisation_type,
            )
        else:
            provider_reason(
                "organisation_type_mismatch",
                "organisation_types",
                "excluded",
                "Organisation type is outside the selected types.",
                candidate.organisation_type,
            )
            excluded = True

    preferred_matches = 0
    for characteristic in definition.preferred_business_characteristics:
        if characteristic in candidate.business_characteristics:
            provider_reason(
                f"preferred_{characteristic}_match",
                "preferred_business_characteristics",
                "matched",
                f"Preferred characteristic: {characteristic.replace('_', ' ')}.",
                characteristic,
            )
            preferred_matches += 1
        else:
            provider_reason(
                f"preferred_{characteristic}_not_established",
                "preferred_business_characteristics",
                "context",
                f"Preferred characteristic not established: {characteristic.replace('_', ' ')}.",
                None,
            )

    if definition.exclude_existing_accounts and relationship_state != ProspectRelationshipState.NEW_PROSPECT:
        reasons.append(
            MatchReason(
                reason_code="existing_account_excluded",
                criterion_key="exclude_existing_accounts",
                state="excluded",
                text="An exact-domain RevenueOS Account exists and this market excludes existing Accounts.",
                data_origin="existing_revenueos_data",
                trust_state=ProspectTrustState.VERIFIED,
                observed_value_class=relationship_state.value,
            )
        )
        excluded = True
    elif relationship_state == ProspectRelationshipState.ACTIVE_OPPORTUNITY:
        reasons.append(
            MatchReason(
                reason_code="active_opportunity",
                criterion_key="relationship_state",
                state="context",
                text="An active RevenueOS Opportunity already exists for this exact-domain Account.",
                data_origin="existing_revenueos_data",
                trust_state=ProspectTrustState.VERIFIED,
                observed_value_class=relationship_state.value,
            )
        )
    elif relationship_state == ProspectRelationshipState.EXISTING_ACCOUNT_NO_ACTIVE_OPPORTUNITY:
        reasons.append(
            MatchReason(
                reason_code="existing_account_no_active_opportunity",
                criterion_key="relationship_state",
                state="context",
                text="An exact-domain RevenueOS Account exists with no active Opportunity.",
                data_origin="existing_revenueos_data",
                trust_state=ProspectTrustState.VERIFIED,
                observed_value_class=relationship_state.value,
            )
        )

    if candidate.trigger_summary is not None:
        reasons.append(
            MatchReason(
                reason_code="public_trigger_context",
                criterion_key="current_public_context",
                state="context",
                text=candidate.trigger_summary,
                data_origin="provider_supplied",
                trust_state=ProspectTrustState.PROVIDER_SUPPLIED,
                observed_value_class="time_sensitive_public_context",
                source_reference=candidate.trigger_source_reference,
            )
        )

    if excluded:
        return MatchResult(
            match_state=ProspectCandidateMatchState.EXCLUDED,
            priority=ProspectCandidatePriority.EXCLUDED,
            reasons=tuple(reasons),
            missing_information=tuple(dict.fromkeys(missing)),
        )
    if missing:
        return MatchResult(
            match_state=ProspectCandidateMatchState.PARTIAL,
            priority=ProspectCandidatePriority.NEEDS_MORE_INFORMATION,
            reasons=tuple(reasons),
            missing_information=tuple(dict.fromkeys(missing)),
        )
    high_priority = (
        not definition.preferred_business_characteristics
        or preferred_matches > 0
        or candidate.trigger_summary is not None
    )
    return MatchResult(
        match_state=ProspectCandidateMatchState.MATCH,
        priority=(ProspectCandidatePriority.HIGH if high_priority else ProspectCandidatePriority.WORTH_RESEARCHING),
        reasons=tuple(reasons),
        missing_information=(),
    )
