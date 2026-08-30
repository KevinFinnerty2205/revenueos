# Forecast-history UX

**View review history** progressively reveals append-only revisions for one deal and
period. Each entry shows actor, category, time, amount/stage snapshot and the model
sample that existed at review. The current stale reasons are presented outside the
timeline because they compare the latest revision with live Opportunity state.

History remains accessible after the Opportunity closes, while the deal disappears
from remaining forecast. Past periods are read-only. The UI never offers edit/delete
controls for an individual revision and never retrofits old amounts or model counts.
