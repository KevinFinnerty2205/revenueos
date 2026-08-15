# ADR 0032: Keep provisional Live Intelligence in a separate polled aggregate

## Status

Accepted for WO-020.

## Context

Live transcript segments are partial, may be corrected and can have uncertain
speaker attribution. Treating their interpretation as final would contaminate the
Opportunity Workspace and Revenue Brain. A general streaming platform would add
long-lived connection, retry and operational complexity that the deterministic
private-beta workload does not justify.

## Decision

Store live sessions, bounded window idempotency, provisional signals and brief
progress in a separate tenant-owned aggregate. Use a server-authoritative segment
cursor and bounded HTTP polling. Keep the detector behind a strict provider port,
with a deterministic no-network implementation for WO-020. Freeze the aggregate on
Interaction completion and compare it with separately created final Interaction
Intelligence.

No provisional row is eligible as a Revenue Brain or final Opportunity Workspace
input. PostgreSQL RLS, composite tenant keys, retention, export and deletion apply to
the aggregate independently.

## Alternatives considered

- **Write live results into final snapshots:** rejected because partial evidence
  would acquire false authority and complicate immutable history.
- **Browser-owned cursor/local-only state:** rejected because retries, refresh and
  multiple tabs could duplicate or skip work.
- **WebSocket/broker/stream processor:** rejected because the bounded cadence does
  not justify new infrastructure and HTTP polling is easier to recover safely.
- **Reprocess the full transcript each poll:** rejected for cost, latency and
  duplicate interpretation.
- **Reuse AI jobs/artefacts directly:** rejected because their established lifecycle
  represents final/batch intelligence, not mutable provisional session state.

## Consequences

The model has a clear trust boundary and deterministic retry semantics. Live/final
differences remain inspectable. The trade-off is periodic rather than sub-second
updates and additional cleanup/export logic. A future external provider or streaming
transport requires a new approved decision with consent, data-processing, timeout,
claiming and unknown-outcome controls.
