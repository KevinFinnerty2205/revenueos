# Forecast calibration semantics

For up to eight completed periods of one type, the repository selects the latest
revision for each judgment before period end. Positive categories are assessed. A
realization is current final Won with an actual close date inside that period.

The API returns counts for Commit, Likely and Possible. A category rate is returned
only with five assessed records. There is no composite accuracy score, lead-time
claim, ranking or compensation interpretation. `not_this_period` is excluded from
positive-category realization. The revision's saved model context supports later
model-version evaluation, but WO-038 does not claim independent model calibration.
