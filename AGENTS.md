# RevenueOS AI repository guidance

## Product context and scope

RevenueOS AI is an AI teammate for relationship-driven professionals. Sales Brain is the first product; Recruitment Brain and Customer Success Brain will reuse the same identity, organisation, interaction and workflow foundation. RevenueOS complements CRMs and other systems of record; it is not a CRM.

Implement only the active task or sprint specification. Sprints 1–3 are the current shipped baseline: foundation; tenant-isolated CRUD for companies, contacts, opportunities and tasks; and the tenant-isolated Meeting Domain with participants, deliberately supplied plain-text transcripts, soft deletion and audit metadata. The target [master product blueprint](docs/01-product/master-product-blueprint.md) and [roadmap](docs/06-roadmap/product-roadmap-to-beta.md) guide future sprint planning but do not authorise implementation. Recording, media storage, transcription, AI calls, integrations, production Clerk verification, billing, analytics, workers, automation and mobile code are not currently implemented.

## Repository structure

```text
apps/
  web/                 # Next.js App Router application
  api/                 # FastAPI application and Alembic migrations
packages/
  shared/              # small client-facing contract surface
  ui/                  # shared UI only after a real second consumer exists
docs/                  # product bible, sprint records and decisions
scripts/               # cross-platform automation only when root tasks are insufficient
.github/workflows/     # validation only; no automatic production deployment
```

## Architecture rules

- Keep a modular monolith: one web app, one API and PostgreSQL-compatible persistence.
- FastAPI/Pydantic/OpenAPI is the API source of truth. Keep `packages/shared` small and aligned in the same change; introduce generation only when it is simpler than the manual surface.
- Clerk, Supabase, OpenAI, Stripe and future connectors belong behind explicit interfaces/adapters. Local and CI paths use clearly labelled deterministic mocks.
- Never describe a stub, mock, interface, flag or log message as a working integration.
- Use SQLAlchemy 2 and Alembic; Alembic alone owns application schema migrations.
- Do not add microservices, Kubernetes, Redis, a message broker or another datastore without an approved decision record and measured need.

## Naming and coding conventions

- TypeScript is strict. Python passes mypy strictness. Avoid `any`/`Any`, hidden globals and unchecked casts.
- Use `PascalCase` for components/types, `camelCase` for TypeScript and JSON, and `snake_case` for Python/database names. Pydantic owns JSON aliases.
- Keep route handlers and React pages thin. Put policy in explicit functions/services and persistence in repositories.
- Use UUID identifiers and timezone-aware UTC timestamps. Format dates at the presentation edge.
- Prefer small, readable modules and explicit dependencies over speculative abstractions.
- User-facing text uses Australian English.

## Tenant isolation and authorisation

- Derive the active organisation only from verified authentication context; never trust a freely supplied organisation ID.
- Every tenant-owned row, unique key, cache key and future storage path includes organisation scope.
- Repository queries include explicit organisation predicates. PostgreSQL RLS provides defence in depth using a transaction-local trusted tenant setting.
- The application role must not bypass RLS. Migration/admin credentials are separate from runtime credentials.
- Missing tenant or membership context fails closed. Test cross-organisation reads, writes and relationship attachment for every tenant feature.
- Avoid privileged browser database access. The browser calls the API.

## Authentication

- Clerk is the approved production identity and organisation provider; do not build password authentication.
- Protected routes are checked server-side.
- Mock auth is development/test only, visibly labelled and prohibited in production.
- Clerk configuration without verified token/session handling is not a completed integration and must report unavailable.
- Never store plaintext passwords, tokens or session material in application tables or logs.

## Secrets and privacy

- Secrets come from environment-specific secret managers. Commit placeholder variable names only.
- Never log credentials, authorisation headers, signed URLs, recordings, transcripts, prompts, customer content or full provider payloads.
- Errors expose a safe code, message and request ID—not stack traces or provider internals.
- RevenueOS never records or listens implicitly. Future capture must be deliberately armed, visibly active and supported by authority/consent evidence.
- Sprint 3 transcript text is accepted only after deliberate paste or `.txt` selection and must remain out of logs/audit content. Do not use production customer data while production identity, consent evidence, retention, export and erasure controls remain incomplete.

## Testing and accessibility

- Backend: pytest, Ruff, mypy and real PostgreSQL tests where database/RLS behaviour matters.
- Web: Vitest, React Testing Library, Playwright and semantic accessibility assertions.
- Test health, readiness, authentication denial, trusted tenant context, safe errors and configuration failure.
- Every bug fix includes a regression test. External credentials never cause the normal suite to skip; use contract-compatible mocks.
- UI work includes loading, empty and error states, keyboard navigation, visible focus, semantic landmarks, labels and reduced-motion support.
- Do not chase arbitrary coverage percentages; cover important behaviour and failures.

## Documentation

- `docs/00-company` through `docs/08-decisions` is the canonical product bible.
- `docs/README.md` is the documentation index and `docs/01-product/master-product-blueprint.md` is the primary product contract through beta.
- Update documentation in the same pull request as contracts, schema, security behaviour or developer workflow.
- Record durable architecture changes under `docs/08-decisions` with context, decision, alternatives and consequences.
- Clearly distinguish current behaviour, approved near-term work and future direction.

## Validation commands

Run affected checks while developing and the complete gate before hand-off:

```text
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build:web
pnpm api:lint
pnpm api:format
pnpm api:typecheck
pnpm api:test
pnpm api:migrate
pnpm api:migration:check
pnpm build:api
```

Do not weaken or skip a check to make a change pass. Report exactly what ran.

## Pull requests and completion

Pull requests explain the problem, scope, assumptions, out-of-scope work, security/tenant impact, migration impact, tests, validation and rollback. Include screenshots for visible UI changes. Keep changes reviewable and use a protected `main` branch with short-lived topic branches and squash merges.

A task is complete only when code, schema, contracts, tests, documentation and observability agree; required checks pass; mocks remain clearly labelled; no secret is committed; and the implementation stops at the requested scope.
