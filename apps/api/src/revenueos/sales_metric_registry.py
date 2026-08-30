from __future__ import annotations

from dataclasses import dataclass

from revenueos.sales_analytics_contracts import MetricFilter, MetricUnit, SalesMetricDefinitionResponse


@dataclass(frozen=True)
class SalesMetricDefinition:
    id: str
    label: str
    description: str
    unit: MetricUnit
    targetable: bool
    supported_filters: tuple[MetricFilter, ...]
    date_semantics: str
    numerator: str | None
    denominator: str | None
    exclusions: tuple[str, ...]
    source_domain: str
    definition_version: str = "1"

    def response(self) -> SalesMetricDefinitionResponse:
        return SalesMetricDefinitionResponse(
            id=self.id,
            definition_version=self.definition_version,
            label=self.label,
            description=self.description,
            unit=self.unit,
            targetable=self.targetable,
            supported_filters=list(self.supported_filters),
            date_semantics=self.date_semantics,
            numerator=self.numerator,
            denominator=self.denominator,
            exclusions=list(self.exclusions),
            source_domain=self.source_domain,
        )


_DATE_FILTERS: tuple[MetricFilter, ...] = ("date_range", "timezone", "pipeline", "owner")
_FINAL_OUTCOME_EXCLUSIONS = (
    "Open Opportunities",
    "Archived Opportunities",
    "Opportunities that are currently reopened",
)

SALES_METRIC_DEFINITIONS: tuple[SalesMetricDefinition, ...] = (
    SalesMetricDefinition(
        id="opportunities_created_count",
        label="Opportunities created",
        description="Distinct Opportunities created during the selected local-calendar period.",
        unit="count",
        targetable=True,
        supported_filters=_DATE_FILTERS,
        date_semantics="Opportunity created_at falls inside the selected local-calendar range.",
        numerator="Distinct eligible Opportunities.",
        denominator=None,
        exclusions=("Archived Opportunities",),
        source_domain="Opportunity",
    ),
    SalesMetricDefinition(
        id="opportunities_closed_won_count",
        label="Closed Won",
        description="Distinct Opportunities that remain finally closed Won in the selected period.",
        unit="count",
        targetable=True,
        supported_filters=_DATE_FILTERS,
        date_semantics="Current final actual_close_date falls inside the selected range.",
        numerator="Distinct current final Won Opportunities.",
        denominator=None,
        exclusions=_FINAL_OUTCOME_EXCLUSIONS,
        source_domain="Opportunity and Opportunity stage history",
    ),
    SalesMetricDefinition(
        id="opportunities_closed_lost_count",
        label="Closed Lost",
        description="Distinct Opportunities that remain finally closed Lost in the selected period.",
        unit="count",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Current final actual_close_date falls inside the selected range.",
        numerator="Distinct current final Lost Opportunities.",
        denominator=None,
        exclusions=_FINAL_OUTCOME_EXCLUSIONS,
        source_domain="Opportunity and Opportunity stage history",
    ),
    SalesMetricDefinition(
        id="closed_win_rate",
        label="Closed-opportunity win rate",
        description="The share of current final closed Opportunities in the period that were Won.",
        unit="percent",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Current final actual_close_date falls inside the selected range.",
        numerator="Current final Won Opportunities.",
        denominator="Current final Won plus Lost Opportunities.",
        exclusions=_FINAL_OUTCOME_EXCLUSIONS,
        source_domain="Opportunity and Opportunity stage history",
    ),
    SalesMetricDefinition(
        id="median_sales_cycle_days",
        label="Median sales cycle",
        description="Median local calendar days from Opportunity creation to its current final close.",
        unit="days",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Current final actual_close_date falls inside the selected range.",
        numerator=None,
        denominator=None,
        exclusions=(*_FINAL_OUTCOME_EXCLUSIONS, "Invalid negative lifecycles"),
        source_domain="Opportunity",
    ),
    SalesMetricDefinition(
        id="won_value",
        label="Won value",
        description="Value of current final Won Opportunities in one explicitly selected currency.",
        unit="currency",
        targetable=True,
        supported_filters=(*_DATE_FILTERS, "currency"),
        date_semantics="Current final actual_close_date falls inside the selected range.",
        numerator="Sum of valued current final Won Opportunities in the requested currency.",
        denominator=None,
        exclusions=(*_FINAL_OUTCOME_EXCLUSIONS, "Unvalued Opportunities", "Every other currency"),
        source_domain="Opportunity",
    ),
    SalesMetricDefinition(
        id="meetings_completed_count",
        label="Meetings completed",
        description="Completed meeting and customer-session Interactions recorded in RevenueOS.",
        unit="count",
        targetable=True,
        supported_filters=_DATE_FILTERS,
        date_semantics="Interaction actual_end_at falls inside the selected local-calendar range.",
        numerator="Distinct eligible completed Interactions.",
        denominator=None,
        exclusions=("Phone calls", "Manual-only Interaction records", "Deleted or incomplete Interactions"),
        source_domain="Interaction",
    ),
    SalesMetricDefinition(
        id="phone_calls_completed_count",
        label="Calls completed",
        description="Completed phone-call Interactions recorded in RevenueOS as supporting activity context.",
        unit="count",
        targetable=True,
        supported_filters=_DATE_FILTERS,
        date_semantics="Interaction actual_end_at falls inside the selected local-calendar range.",
        numerator="Distinct completed phone-call Interactions.",
        denominator=None,
        exclusions=("Deleted or incomplete Interactions",),
        source_domain="Interaction",
    ),
    SalesMetricDefinition(
        id="calls_followed_by_meeting_rate_30d",
        label="Calls followed by a meeting",
        description="Associated mature calls followed by a later recorded meeting within 30 days; not causal attribution.",
        unit="percent",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Call actual_end_at is in range and at least 30 days old.",
        numerator="Eligible calls with a later same-Account or same-Contact meeting within 30 days.",
        denominator="Completed calls with an association and a fully elapsed 30-day window.",
        exclusions=("Immature calls", "Unassociated calls", "Deleted or incomplete Interactions"),
        source_domain="Interaction and Meeting participant",
    ),
    SalesMetricDefinition(
        id="meetings_followed_by_progression_rate_30d",
        label="Meetings followed by progression",
        description="Tracked mature meetings followed by forward Opportunity movement within 30 days; not causal attribution.",
        unit="percent",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Meeting actual_end_at is in range and at least 30 days old.",
        numerator="Eligible meetings followed by a higher open stage or Won within 30 days.",
        denominator="Opportunity-linked meetings with reliable stage context and a fully elapsed 30-day window.",
        exclusions=("Immature meetings", "Unlinked meetings", "Baseline-only stage history", "Backward movement"),
        source_domain="Interaction and Opportunity stage history",
    ),
    SalesMetricDefinition(
        id="live_outreach_sent_count",
        label="Live outreach sent",
        description="Provider-succeeded live email executions only; simulated execution never counts.",
        unit="count",
        targetable=False,
        supported_filters=_DATE_FILTERS,
        date_semantics="Live execution completed_at falls inside the selected local-calendar range.",
        numerator="Distinct succeeded live send-email executions.",
        denominator=None,
        exclusions=("Simulation", "Queued, failed or uncertain executions", "Draft or approval state alone"),
        source_domain="Outreach and Action Execution",
    ),
)

SALES_METRIC_REGISTRY: dict[str, SalesMetricDefinition] = {
    definition.id: definition for definition in SALES_METRIC_DEFINITIONS
}

if len(SALES_METRIC_REGISTRY) != len(SALES_METRIC_DEFINITIONS):
    raise RuntimeError("Sales metric IDs must be unique.")


def sales_metric_definitions() -> list[SalesMetricDefinitionResponse]:
    return [definition.response() for definition in SALES_METRIC_DEFINITIONS]
