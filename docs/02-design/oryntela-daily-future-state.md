# Oryntela Daily future state

- **Status:** Future-state design hypothesis; not authorised for implementation
- **Last reviewed:** 4 September 2026

## Decision

Daily should remain the product's calm, role-aware starting point. It should answer what matters today and make the next action easy, not become a compressed copy of every Oryntela module.

The current Home experience already provides a meaningful base: a greeting, manager attention where applicable, active-event context, top priority, interactions, actions, deal attention, pipeline context and a recommendation. Target and forecast are not currently promoted on Home. Any change must be validated with the first design partner.

## Proposed hierarchy

The hierarchy below is conceptual, not a screen specification.

1. **Orientation:** date, role-relevant greeting and exceptional system state.
2. **Top priority:** one recommended outcome, its reason and its evidence.
3. **Today:** imminent meetings or interactions and the preparation they require.
4. **Commitments:** customer commitments and seller actions that are due or at risk.
5. **Deals needing attention:** changes, gaps or next steps, not an undifferentiated list.
6. **Performance context:** compact target, forecast and pipeline signals only when the data and time period are trustworthy.
7. **Recommended follow-through:** an editable action that closes the loop.

The first useful viewport should not contain seven equally weighted panels. Progressive disclosure and role-aware ordering should protect the information budget.

## Seller and manager emphasis

| Area                | Seller emphasis                       | Manager emphasis                                |
| ------------------- | ------------------------------------- | ----------------------------------------------- |
| Priority            | own next best action                  | team or deal exception requiring attention      |
| Interactions        | preparation and follow-through        | coverage and coaching opportunity               |
| Commitments         | promises to or from customers         | overdue or unowned risk                         |
| Deals               | movement and next step                | evidence gaps and concentration                 |
| Target and forecast | personal progress, when supported     | team confidence and variance                    |
| Recommendation      | action the seller can review and take | coaching or intervention the manager can review |

## Target, forecast and pipeline are different

- **Target** is the agreed outcome for a supported time period.
- **Forecast** is an evidence-based expectation with stated assumptions and confidence.
- **Pipeline** is the set and value of active opportunities.

They must not be collapsed into one number or represented as interchangeable progress. Monthly, quarterly and annual views should appear only when the underlying target periods and data semantics support them. A missing target must be labelled as missing, not inferred from pipeline.

## Evidence and action

Recommendations should show enough evidence to earn trust: relevant interactions, deal changes, explicit commitments, methodology gaps or target variance. Users must be able to inspect the reason, edit the proposed action and decline it without losing the underlying context.

## States that must be designed

- New organisation with no data.
- Active seller with no urgent work.
- Missing target or incomplete forecast inputs.
- Manager without team scope.
- Provider disconnected or unavailable.
- Data still processing or partially available.
- Recommendation declined, completed or superseded.

No empty state should claim an integration or intelligence capability that is not available.

## Mobile boundary

On a small screen, Daily should prioritise the top action, imminent interaction, commitments and one compact deal or performance signal. Dense charts, broad team comparisons and configuration belong on larger screens. This boundary does not authorise native recording or background capture.

## Validation before build

Test the current Home and one low-fidelity future hierarchy with sellers and managers. Observe what they notice first, what they ignore, whether they can distinguish target from forecast and whether the recommendation leads to a useful action. Authorise implementation only where evidence shows a meaningful improvement.

## Related sources

- [Current RevenueOS Daily experience](revenueos-daily-experience.md)
- [Oryntela simplicity principles](oryntela-simplicity-principles.md)
- [Sales targets](../01-product/sales-targets.md)
- [Transparent forecasting](../01-product/transparent-forecasting.md)
