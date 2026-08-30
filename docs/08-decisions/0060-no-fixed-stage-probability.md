# ADR 0060 — No fixed stage probability or Opportunity probability field

- **Status:** Accepted
- **Date:** 30 August 2026

## Context

Conventional CRM weighted pipeline often assigns fixed percentages to stage names.
Those values are neither tenant history nor seller judgment and invite false precision.

## Decision

RevenueOS adds no fixed/configurable stage weight, Opportunity probability, predicted
close date or weighted-pipeline total. An observed historical outcome rate may be
displayed only with its exact cohort and minimum sample; it is not stored on the
Opportunity. Seller categories have no numeric percentages.

## Consequences

There is no familiar probability field to maintain. Sparse data remains visibly
unavailable. Future model changes require a versioned decision and calibration proof.
