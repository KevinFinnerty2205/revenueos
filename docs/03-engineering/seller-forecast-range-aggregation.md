# Seller-range aggregation definitions

Only eligible current Opportunities with a latest explicit revision are aggregated.
Live current amount is used so the operating forecast reflects canonical corrections;
the revision snapshot remains historical evidence.

- Commit = sum(category `commit`).
- Likely = Commit + sum(category `likely`).
- Possible = Likely + sum(category `possible`).
- `not_this_period` and unreviewed = zero contribution, separately counted.
- A reviewed unvalued Opportunity adds to the relevant case count/unvalued count but
  contributes zero amount.

Stale judgments remain in the live category aggregate using current amount and add to
`needsReviewCount`; they are never silently recategorised. Closed deals are excluded.
Each API call uses exactly one currency and applies no FX.
