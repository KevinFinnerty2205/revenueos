# RevenueOS Historical Baseline

The RevenueOS baseline is a separate expected-value reference, not the seller
forecast and not a statistical range.

For each eligible valued Opportunity, RevenueOS finds final Won/Lost Opportunities
in the same organisation and Pipeline that have a reliable, non-baseline entry into
the live Opportunity's exact stable stage during the trailing 730 days. Only outcomes
known by the calculation cutoff are included. Reopened or currently open deals are
not final outcomes. Migrated baseline events are excluded.

At 10 or more comparable final outcomes:

`expected contribution = current Opportunity amount × won count / (won + lost count)`

The UI exposes Won/Lost counts, observed rate, cohort dates, model version, current
stage and contribution. With fewer than 10 outcomes the result is **insufficient
history**; no neighbour-stage, global, seller-category or fixed rate is substituted.
The aggregate reports covered and uncovered value separately.

This v1 model does not use Methodology state, Revenue Brain confidence, Actions,
Evidence sentiment, activity volume or seller category as numeric inputs. Those
sources can remain qualitative context elsewhere without changing baseline math.
