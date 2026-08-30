# Seller Forecast guide

Seller Forecast is explicit human judgment, not a customer fact or system inference.
For each eligible Opportunity the current owner chooses:

- **Commit:** the seller is committing the full current Opportunity amount to the
  selected period;
- **Likely:** the seller believes it is likely in the period, without claiming a
  numeric probability;
- **Possible:** the seller sees credible upside in the period; or
- **Not this period:** the seller excludes it while the canonical close date remains
  visible for correction in the Opportunity record.

The aggregate cases are inclusive: Commit contains Commit only; Likely contains
Commit plus Likely; Possible contains Commit plus Likely plus Possible. Unreviewed
and Not this period Opportunities contribute zero and remain visible as counts.
Unvalued reviewed Opportunities contribute zero amount and remain visible in counts.

Saving never changes amount, stage, close date, status, Evidence, Methodology or
Revenue Brain. It appends a revision. If canonical deal facts later change, Forecast
uses the current amount for the live total and labels the judgment **Needs review**;
the old snapshot remains intact for history. Closed deals leave remaining forecast.

Admins can filter the organisation forecast and inspect deal categories. They have no
manager override in WO-038. An admin who owns an Opportunity acts only as its seller.
WO-039 may add a separate manager view; it must not replace seller history.
