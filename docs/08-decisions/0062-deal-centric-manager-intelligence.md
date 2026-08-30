# ADR 0062 — Deal-centric manager intelligence and independent forecast perspective

- **Status:** Accepted
- **Date:** 30 August 2026

## Context

Sales leaders need an explainable review surface across Daily, Pipeline, Opportunity,
Forecast and Insights. Persisting manager risk, coaching or employee profiles would
duplicate canonical state and create surveillance/HR semantics. Extending the
seller-only forecast identity would also risk WO-038 uniqueness and authority.

## Decision

Manager Intelligence is a deterministic projection of deals and typed canonical
conditions. Attention, recent-change summaries and source-backed questions are
derived on read and are not persisted. The only new business record is an explicit
human manager forecast, held in separate tenant-scoped identity/revision tables with
the same categories, snapshot and immutability rules as seller forecast.

Seller, manager and RevenueOS historical perspectives remain independent. Actual and
Target remain separate too; RevenueOS creates no blended/final forecast. V1 manager
authority uses the existing organisation `admin` capability and does not claim a
reporting hierarchy.

No score, rank, leaderboard, employee performance profile, behavioural surveillance,
persistent coaching dossier, AI coach or generic coaching prompt is permitted.

## Alternatives rejected

- A manager risk/attention table would retain derived state and require invalidation.
- Employee coaching notes/profiles would create unnecessary sensitive HR-like data.
- Adding a perspective column to seller judgment identities could alter existing
  uniqueness and authorisation semantics.
- Treating manager judgment as the final forecast would hide legitimate differences.
- An LLM-generated manager brief would weaken deterministic source guarantees and add
  customer/employee data processing without demonstrated need.

## Consequences

Reads are live and set-based, and sparse source state stays sparse. Manager revisions
add a small append-only/exportable lifecycle surface. Future hierarchy, governance or
calibration requires a separate decision; it cannot reinterpret current admin access
or silently blend existing perspectives.
