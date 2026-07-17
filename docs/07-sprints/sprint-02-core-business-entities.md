# Sprint 02 — core business entities

## Objective

Deliver a secure, tenant-isolated CRUD foundation for companies, contacts, opportunities and tasks without starting meeting, AI, integration or workflow features.

## Delivered scope

- SQLAlchemy models and Alembic migration for all four business entities.
- Explicit status/stage/priority enums and schema constraints.
- Organisation-scoped composite relationships and membership ownership constraints.
- Forced PostgreSQL RLS policies for each business table.
- Pydantic create, patch and response contracts with camel-case JSON.
- Repository and service boundaries with explicit organisation predicates.
- Versioned CRUD endpoints with bounded pagination, search, filters and sorting.
- Safe errors and request-ID propagation.
- Responsive list, create and edit experiences with loading, empty, error and validation states.
- Deterministic development identity provisioning, prohibited outside development.
- API, contract, migration, PostgreSQL RLS, web component and browser tests.

## Assumptions

- All authenticated members of an organisation may CRUD Sprint 2 entities because no role-specific policy was specified.
- Contacts and opportunities require a company.
- Tasks can be general. When relationships are supplied, all referenced records must identify the same company; the company is derived when omitted.
- Deleting a related parent returns a conflict instead of cascading product data.
- Owner defaults to the authenticated user; tasks may be unassigned and creator is immutable.

## Explicitly not delivered

No AI, meetings, recording, upload, transcription, relationship memory, follow-up email, calendar/email integration, CRM integration, contact enrichment, verified Clerk sessions, billing, mobile, workers, background jobs, workflows or automated actions.

## Security notes

The organisation is never accepted in write contracts. Repositories scope every operation, request transactions set trusted PostgreSQL tenant context, RLS is enabled and forced, and composite foreign keys enforce tenant-consistent relationships. Tests prove cross-tenant reads and mutations fail and PostgreSQL policies hide every Sprint 2 table from another tenant.

This sprint is not approved for production customer data. Verified production authentication, audit trails, production database-role provisioning, retention/deletion operations and production operations remain incomplete.

## Acceptance checks

- CRUD contracts and endpoints exist only under `/api/v1`.
- Input bounds and enum values fail safely.
- Collection pagination/filter/search/sorting behaves deterministically.
- Missing and cross-tenant resources return not found without existence disclosure.
- Task relationship inconsistency is rejected.
- Alembic upgrades to `0002_core_business_entities`, has no drift and downgrades cleanly in the migration test.
- PostgreSQL RLS integration checks all four business tables.
- Web list/forms cover loading, empty, error, validation, edit and responsive navigation.
- Formatting, linting, type checking, unit/API/browser tests, builds, migrations, secret scan and scope scan pass.
