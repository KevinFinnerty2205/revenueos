# ADR 0059 — Empirical exact-stage outcome baseline v1

- **Status:** Accepted
- **Date:** 30 August 2026

## Context

WO-035 provides stable Pipeline/stage identity and reliable history; data maturity is
not sufficient to justify learned modelling or confidence intervals.

## Decision

Model `forecast_historical_stage_outcome_v1` uses the same-organisation, same-Pipeline,
exact-stage final Won/Lost cohort over 730 days, with reliable non-baseline stage entry
and a 10-outcome minimum. Expected contribution is current amount times observed win
rate. Counts, cutoff and coverage are disclosed.

## Alternatives

ML/LLM scoring, activity/methodology weighting, neighbouring-stage fallback and
Monte Carlo were rejected as premature or opaque.

## Consequences

Early tenants and sparse stages often see unavailable; this is intentional. Model
snapshots retain as-of context for future evaluation without future leakage.
