# Methodology freshness and conflict resolution

Freshness is evaluated per field, not as one mechanical age for the deal. Identity,
decision path, timing and procurement fields generally use shorter windows than
enduring pain or impact. Standard/custom definitions set only bounded day policies;
fields without a meaningful expiry use `not_applicable`.

The engine compares the latest eligible support timestamp with the field policy.
Older support becomes `stale` only when a policy exists. Opportunity movement and
changed validated source state alter the source fingerprint and force a refresh
before the current view can claim support. Historical projections remain immutable.

A conflict requires current eligible sources with materially opposing structured
facts/conclusions. The deterministic v1 detector recognises explicit conflicting
source flags and bounded opposing terms/dates; it does not infer a winner. The field
is `conflicting`, the current conclusion explains the disagreement, and support and
conflict references are both returned. Users can mark an interpretation incorrect or
add a salesperson-reported clarification, but only later accepted/customer-direct
Evidence can establish customer confirmation.

Deletion or change of a referenced source changes the fingerprint. Current reads then
return `needs_refresh` with conclusions hidden; regeneration evaluates the surviving
sources. This fail-safe behaviour avoids orphaned confirmation while retaining the
historical fact that an earlier projection existed.
