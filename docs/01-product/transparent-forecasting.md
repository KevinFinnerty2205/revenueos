# Transparent Forecasting

**Status:** Implemented by WO-038 as a RevenueOS Core capability.

Forecast answers what may close in a calendar month or quarter without presenting a
weighted-pipeline fiction. The Insights **Forecast** tab keeps four concepts visible
and separate:

- **Actual:** canonical Won value from Sales Analytics;
- **Target:** an explicit matching Won-value goal from Targets;
- **Seller forecast:** human Commit, Likely and Possible cases; and
- **RevenueOS baseline:** a deterministic reference from comparable historical stage
  outcomes.

An Opportunity is eligible only when it is currently open/on hold, has a canonical
expected close date in the selected period, has a stable Pipeline stage and matches
the selected currency and scope. Closing a deal removes it from remaining forecast;
Won value then appears in Actual. Missing dates are counted, never predicted.

The v1 baseline uses 730 trailing days and requires 10 final reliable outcomes for
the same organisation, Pipeline and exact stage. It applies `current amount ×
observed win rate`. Counts, lookback, coverage and per-deal arithmetic are visible.
There is no fallback rate, fixed stage table, probability field, predicted close
date, FX, confidence interval, AI/ML model or blended seller/system number.

Only the current Opportunity owner records seller judgment. Admins may inspect the
organisation roll-up but cannot overwrite a seller. Each edit creates an immutable,
period-specific revision with the contemporaneous Opportunity and model context.
Past periods are locked; owner, amount, currency, close date, Pipeline, stage and
status changes mark the latest judgment for review.

See the [seller guide](seller-forecast-guide.md), [baseline guide](revenueos-historical-baseline.md),
[comparison guide](actual-target-forecast.md), [calibration guide](forecast-calibration.md)
and [model specification](../03-engineering/forecast-model-v1-specification.md).
