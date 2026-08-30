# Historical baseline methodology

The cohort is tenant-local and exact: final current Won/Lost Opportunities with a
reliable non-baseline entry into the same Pipeline/stable stage, actual close date in
the trailing 730-day window, and no facts after the calculation cutoff. The current
live Opportunity is not itself required to have historical age.

For `n = won + lost`, v1 is available only when `n >= 10`:

`observed_rate = won / n`

`expected_contribution = current_live_amount × observed_rate`

The aggregate sums contributions only for valued covered Opportunities. It separately
reports covered/uncovered counts and amounts plus unvalued count. There is no global,
adjacent-stage, seller-category or configured fallback. Historical rates are
descriptive cohort observations, not an Opportunity probability column.

The review snapshot uses `as_of=reviewed_at`, preserving a cutoff that prevents later
outcomes from leaking into the saved historical context.
