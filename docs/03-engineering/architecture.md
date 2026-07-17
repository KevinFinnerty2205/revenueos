# Foundation architecture

## Current scope

Sprint 1 is a modular monolith with a web application, an API and PostgreSQL-compatible persistence. There is no AI runtime, media pipeline, worker, connector, billing service or mobile application.

```text
Browser
  │
  ├── Next.js App Router ── server-side route protection
  │
  └── HTTPS /api/v1
              │
              ▼
        FastAPI application
        auth · tenant context · health/readiness
              │
              ▼
       PostgreSQL / Supabase later
       organisation · user · membership
```

## Repository boundaries

- `apps/web` owns web presentation, navigation and server-side access checks.
- `apps/api` owns authentication dependencies, tenant context, application policy, Pydantic contracts and persistence.
- `packages/shared` contains the deliberately small TypeScript view of stable API responses.
- `packages/ui` is reserved for primitives with a real second consumer.
- Alembic is the sole application-schema migration owner.

## Web architecture

Next.js App Router, strict TypeScript and Tailwind CSS provide the responsive web shell. Pages compose application-local components; business rules remain server-side. Protected routes resolve an authentication adapter during server rendering and redirect when it does not provide a complete user and organisation context.

Development auth returns one fixed example user/organisation and displays a warning banner. Production never falls back to it. The Clerk adapter boundary and environment path exist, but Clerk sessions are not represented as connected.

## API architecture

FastAPI exposes:

- `GET /health` for process health;
- `GET /ready` for honest configured-dependency readiness;
- `GET /api/v1/me` for the authenticated identity and active organisation context.

Routes use Pydantic response models, camel-case JSON, request IDs, structured content-redacted logs, explicit CORS and central safe error handlers. No product CRUD endpoints exist in Sprint 1.

## Persistence and tenancy

SQLAlchemy 2 models Organisation, User and OrganisationMembership. UUIDs, UTC timestamps, unique organisation slugs, unique external auth IDs, membership uniqueness and allowed-role constraints are enforced in schema and migration.

The active organisation originates in the trusted auth adapter, never a request body. Repository methods accept organisation scope explicitly. PostgreSQL policies use a transaction-local `app.organisation_id` setting as defence in depth. Runtime deployment must use a non-bypass application role; migration credentials remain separate.

The API starts without a database so developers can inspect health and the shell, but `/ready` returns `503` and marks persistence unavailable.

## Contracts

FastAPI Pydantic models and OpenAPI are canonical. Sprint 1 has only a handful of stable responses, so `packages/shared` mirrors those shapes manually and is updated in the same pull request. Add client generation when the contract surface makes it the simpler option.

## Deployment direction

Vercel is planned for the web application. The API requires a managed Python host that supports a long-running ASGI process, private database connectivity, health/readiness probes, secrets and rolling rollback. Select it in a later ADR; Sprint 1 has no production deployment.

Supabase PostgreSQL, Clerk, Supabase Storage, OpenAI and Stripe are planned managed services. Only PostgreSQL-compatible persistence and auth adapter paths exist now.

## Future extension boundaries

Conversation capture, AI providers, storage and external systems will use narrow adapters. Future long-running work will run outside HTTP requests. A React Native client may later consume the same versioned API; no mobile code is included now. These boundaries prevent a Sales Brain implementation from blocking Recruitment Brain or Customer Success Brain without pre-building either product.
