# ADR 0066 — Bounded admin CSV import without raw retention

## Context

Design partners need initial CRM data without manual recreation, while a generic ETL or retained raw upload would expand privacy and operations risk.

## Decision

Native CRM admins receive three fixed CSV schemas for Accounts, Contacts and open Opportunities. Mapping/owner/stage choices are explicit; preview performs no canonical writes; confirmation resends and revalidates the same bounded file. Persistent metadata is content-free. Strong deterministic matches skip, possible matches require review, and imported stage state is an honest `import_baseline`.

## Alternatives

Generic ETL, automatic mapping/fuzzy dedupe, raw upload retention, closed-opportunity history reconstruction and background import queues were rejected.

## Consequences

Imports are supervised and repeatable but refresh loses an unconfirmed preview. Customers correct/preview a file again rather than download a sensitive error file. Historical analytics before import remain incomplete.
