# ADR 0054 — Canonical records form the native CRM

- **Status:** Accepted
- **Date:** 2026-08-29

## Context

RevenueOS already needs Company, Contact and Opportunity for Evidence, Revenue Brain, Methodology, Actions, Daily, Prospect, Engage, Create and focused HubSpot sync. A second CRM graph would create contradictory identity, tenancy, provenance and reconciliation rules. Small teams still need system-of-record administration without a Salesforce-scale object/workflow platform.

## Decision

Existing Company, Contact and Opportunity are the only CRM records in native and external modes. Add one organisation mode record, bounded typed custom-field metadata/values and field-level change history. Reuse existing owner fields, activity sources, promotion paths and HubSpot field authority. Do not introduce Lead, CRM Task, CRM Note or CRM Activity; no custom objects or executable workflow schema.

Custom fields support six non-executable optional types, at most 25 active definitions per organisation/entity and 50 select options. A generic tenant-scoped typed-value table is accepted: application lookup proves the canonical target because a single polymorphic database FK cannot reference three tables, while definition and actor use composite tenant FKs and all rows use forced RLS.

## Alternatives

- Parallel CRM entities: rejected because they duplicate truth and force continual reconciliation.
- JSON blobs on canonical rows: rejected because type validation, history, lifecycle and export become opaque.
- One value table per record type: valid referential integrity but rejected as repetitive for the bounded v1; revisit only if measured query/integrity cost justifies it.
- Arbitrary custom objects/formulas/workflows: rejected as scope, security and product-category drift.

## Consequences

All modules share stable canonical IDs and native CRM remains a thin system-of-record experience around Sales Brain. External mode can retain local mirrors without surrendering mapped authority. The generic value target must always be tenant-validated by services and is covered by RLS/cross-tenant tests. Pipeline definitions, safe CSV migration and provider-neutral native Action execution require later deliberate work.
