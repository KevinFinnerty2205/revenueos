# Forecast to Analytics and Targets contract

Actual invokes WO-036 `SalesMetricService.observe("won_value", filters, currency)`
after constructing the canonical inclusive local-date filters. The service does not
copy Won predicates. Upcoming periods return no Actual; active/past calculation ends
at today/period end respectively.

Target comparison invokes `SalesTargetService.matching_forecast_targets`. Matching
requires metric/version `won_value`/`1`, exact period bounds, selected currency,
identical optional Pipeline binding and relevant personal or organisation scope.
Forecast reads the latest target goal revision and does not persist or recalculate
Target progress.

Both dependencies fail closed behind `salesAnalytics`, `salesTargets` and
`salesForecasting`. Forecast adds no target-triggered Action or mutation.
