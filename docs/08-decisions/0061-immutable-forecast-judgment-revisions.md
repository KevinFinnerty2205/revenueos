# ADR 0061 — Immutable period-specific forecast judgment revisions

- **Status:** Accepted
- **Date:** 30 August 2026

## Context

Current deal values change, while history and calibration need to know what a seller
actually said with the information available then.

## Decision

One judgment identity exists per Opportunity/calendar period; edits append revisions.
Each revision snapshots canonical deal context and model version/count/cutoff. Live
aggregates use current amount and identify stale differences. Past periods cannot be
rewritten. PostgreSQL triggers enforce immutability with an explicit maintenance-only
bypass.

## Consequences

History grows append-only and export/delete paths must include it. Corrections remain
visible without freezing the live operating forecast.
