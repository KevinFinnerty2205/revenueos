# Forecast revision and snapshot model

Every seller edit appends a revision containing category, actor/time, owner, amount,
currency, expected close date, Pipeline/stage names and IDs, Opportunity status,
model version/status, Won/Lost sample, minimum sample and lookback cutoff.

The fingerprint is evaluated structurally rather than persisted as opaque JSON. The
latest snapshot is stale when live owner, amount, currency, expected close, Pipeline,
stage or status differs. This keeps each reason visible and testable. Historical
responses render the stored model arithmetic, never a rerun with newer outcomes.

PostgreSQL triggers make period identities, judgment identities and revisions
immutable. Only approved maintenance used by tenant deletion/reset may bypass them.
The organisation export includes all three record types and snapshot fields.
