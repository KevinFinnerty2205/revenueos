# ADR 0002 — tenant-owned business entities

- **Status:** Accepted
- **Date:** 2026-07-17
- **Scope:** Sprint 2

## Context

Companies, contacts, opportunities and tasks are the first tenant-owned product records. The implementation needs simple CRUD while preventing cross-organisation references and preserving a platform boundary suitable for later Sales Brain features.

## Decision

- Keep each entity in the existing modular-monolith API with route, service and repository boundaries.
- Put a non-null `organisation_id` on every entity and include it in every repository predicate.
- Use transaction-local PostgreSQL tenant context plus enabled and forced RLS on every business table.
- Use composite foreign keys `(organisation_id, related_id)` for entity relationships and `(organisation_id, user_id)` for owner/assignee/creator membership.
- Use string columns with explicit Python enums and database check constraints. This keeps migrations and future value changes simpler than native PostgreSQL enum alteration while retaining validation.
- Require a company for contacts and opportunities. Permit general tasks, but require all supplied task relationships to resolve to one tenant-owned company and derive the company when omitted.
- Restrict parent deletion while dependants exist instead of silently cascading customer records.
- Give all authenticated organisation members equal CRUD capability until product specifies a role matrix.

## Alternatives considered

- **Application predicates without RLS:** rejected because defence in depth is a required tenant control.
- **Global foreign keys by ID only:** rejected because they cannot prove a related row belongs to the same organisation.
- **Native PostgreSQL enum types:** rejected for the current small schema because check constraints are easier to evolve and remain explicit.
- **Soft deletion:** not introduced because retention, recovery and legal deletion semantics have not been specified.
- **Per-entity frontend implementations:** avoided because the four list/form state machines are equivalent; entity configuration keeps behaviour consistent without creating a general form framework.

## Consequences

Positive:

- cross-tenant attachment is blocked by both services and database constraints;
- repository and RLS failures independently fail closed;
- entities are ready for later meeting/memory relationships without implementing those features;
- list and form accessibility states remain consistent.

Trade-offs:

- composite keys add verbose constraints and indexes;
- parent deletion must be ordered explicitly by users/services;
- manual TypeScript response mirrors remain until OpenAPI generation is adopted;
- the equal-member CRUD assumption must be replaced when product defines finer authorisation.

## Follow-up triggers

Create a new decision record before adding soft deletion, entity-specific role permissions, bulk operations, generated API clients or relationships to meeting/memory systems.
