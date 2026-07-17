# Sprint 01 — project foundation

## Objective

Create a working, testable web/API foundation without implementing Sales Brain product workflows.

## Delivered scope

- Next.js, TypeScript and Tailwind application with public and protected routes.
- Server-side protected layout, Clerk adapter/configuration path and visibly labelled development mock.
- Responsive application navigation and dashboard empty sections.
- Honest placeholder routes for Companies, Meetings, Tasks, Assistant and Settings.
- FastAPI with `/health`, `/ready` and `/api/v1/me`.
- Request IDs, structured content-redacted logging, safe errors and environment-based CORS.
- Organisation, User and OrganisationMembership SQLAlchemy models and initial Alembic migration.
- UUIDs, UTC timestamps, role/unique constraints, repository/service boundary and trusted tenant context.
- Small TypeScript contract surface with Pydantic/OpenAPI documented as canonical.
- Local PostgreSQL Compose service, environment examples, root commands and developer instructions.
- Backend, web and browser tests plus GitHub Actions validation.

## Explicitly not delivered

No customer CRUD, contacts, opportunities, meeting records, recording/upload, transcript, AI call, agent, worker, connector, billing, analytics, deployment or mobile code.

Clerk configuration is prepared but verified Clerk session/JWT handling is not connected. The readiness endpoint and UI report that honestly.

## Acceptance checks

- All required routes render or redirect safely.
- Production cannot enable mock auth.
- `/health` returns exactly `{"status":"healthy"}`.
- `/ready` returns `503` when persistence or configured authentication is unavailable.
- `/api/v1/me` returns context derived from the auth adapter, not request tenant input.
- OpenAPI exposes no product endpoints outside Sprint 1.
- Migration creates only organisations, users and memberships.
- Format, lint, type, unit, browser, migration and build gates pass.
- Secret/scope review finds no credential or later-sprint implementation.

## Manual setup

Developers install pnpm/uv dependencies, copy package environment examples and optionally start the local PostgreSQL Compose service. Real Clerk and production hosting configuration remain future work.
