# ADR 0058 — Separate seller forecast and system baseline

- **Status:** Accepted
- **Date:** 30 August 2026

## Context

Forecast needs human commercial judgment and a reproducible system reference. A
single blended number would hide which authority produced it and make later
calibration ambiguous.

## Decision

Seller Commit/Likely/Possible cases are the primary range. The RevenueOS historical
baseline is displayed and versioned separately. Neither overwrites or weights the
other; no hidden blended forecast is calculated.

## Alternatives

Weighted seller categories and seller-adjusted model output were rejected because
their percentages would be arbitrary. A system-only forecast was rejected because it
would erase seller accountability and be unavailable for early tenants.

## Consequences

Users can compare disagreement explicitly. Consumers must name which view they use.
WO-039 requires a third independently sourced manager view rather than an override.
