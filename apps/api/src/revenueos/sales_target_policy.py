from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from revenueos.sales_metric_registry import SALES_METRIC_REGISTRY, SalesMetricDefinition

TargetCategory = Literal["outcome", "pipeline_development", "activity"]
TargetScope = Literal["personal", "organisation"]


@dataclass(frozen=True)
class SalesTargetMetricPolicy:
    metric_id: str
    category: TargetCategory
    allowed_scopes: tuple[TargetScope, ...]
    requires_currency: bool
    display_order: int

    @property
    def definition(self) -> SalesMetricDefinition:
        return SALES_METRIC_REGISTRY[self.metric_id]


SALES_TARGET_METRIC_POLICIES: tuple[SalesTargetMetricPolicy, ...] = (
    SalesTargetMetricPolicy(
        metric_id="won_value",
        category="outcome",
        allowed_scopes=("personal", "organisation"),
        requires_currency=True,
        display_order=1,
    ),
    SalesTargetMetricPolicy(
        metric_id="opportunities_closed_won_count",
        category="outcome",
        allowed_scopes=("personal", "organisation"),
        requires_currency=False,
        display_order=2,
    ),
    SalesTargetMetricPolicy(
        metric_id="opportunities_created_count",
        category="pipeline_development",
        allowed_scopes=("personal", "organisation"),
        requires_currency=False,
        display_order=3,
    ),
    SalesTargetMetricPolicy(
        metric_id="meetings_completed_count",
        category="activity",
        allowed_scopes=("personal", "organisation"),
        requires_currency=False,
        display_order=4,
    ),
    SalesTargetMetricPolicy(
        metric_id="phone_calls_completed_count",
        category="activity",
        allowed_scopes=("personal", "organisation"),
        requires_currency=False,
        display_order=5,
    ),
)

SALES_TARGET_METRIC_POLICY: dict[str, SalesTargetMetricPolicy] = {
    policy.metric_id: policy for policy in SALES_TARGET_METRIC_POLICIES
}

if len(SALES_TARGET_METRIC_POLICY) != len(SALES_TARGET_METRIC_POLICIES):
    raise RuntimeError("Sales target metric policy IDs must be unique.")
if any(not policy.definition.targetable for policy in SALES_TARGET_METRIC_POLICIES):
    raise RuntimeError("Every sales target policy metric must be targetable in the canonical registry.")
if any(policy.requires_currency != (policy.definition.unit == "currency") for policy in SALES_TARGET_METRIC_POLICIES):
    raise RuntimeError("Sales target currency policy must agree with the canonical metric unit.")
