# Forecast calibration guide

WO-038 calibration reports how final seller categories related to eventual outcomes.
For up to eight completed calendar periods of the selected type, RevenueOS takes the
last seller judgment recorded before period end. A judgment is realised only when the
Opportunity's current final state is Won and its canonical actual close date is inside
that period.

Commit, Likely and Possible show assessed count and realised-Won count. A realization
rate appears only from five observations; otherwise the UI says **Not enough data**.
Not this period is not presented as a positive forecast category.

This is final-call realization, not lead-time accuracy, a rep score, a leaderboard,
compensation evidence, causality or independent validation of the historical model.
Model context is retained in each seller revision so later work can evaluate model
versions without rewriting the original snapshot.
