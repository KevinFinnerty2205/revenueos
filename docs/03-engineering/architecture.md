# Application architecture

## Current scope

Sprint 2 remains a modular monolith with a web application, a versioned API and PostgreSQL-compatible persistence. It adds the first business modules—companies, contacts, opportunities and tasks—without adding an AI runtime, media pipeline, worker, connector, billing service or mobile application.

```text
Browser
  │
  ├── Next.js App Router ── server-side route protection
  │
  └── HTTPS /api/v1
              │
              ▼
        FastAPI application
        auth · tenant context · business services
              │
              ▼
       PostgreSQL / Supabase later
       identity · business records · RLS
```

## Repository boundaries

- `apps/web` owns web presentation, navigation and server-side access checks.
- `apps/api` owns authentication dependencies, tenant context, application policy, Pydantic contracts and persistence.
- `packages/shared` contains the deliberately small TypeScript view of stable API responses.
- `packages/ui` is reserved for primitives with a real second consumer.
- Alembic is the sole application-schema migration owner.

## Web architecture

Next.js App Router, strict TypeScript and Tailwind CSS provide the responsive web shell. Pages compose application-local components; business rules remain server-side. Protected routes resolve an authentication adapter during server rendering and redirect when it does not provide a complete user and organisation context.

Development auth returns one fixed example user/organisation, provisions that identity only in a migrated development database, and displays a warning banner. Production never provisions or falls back to the mock identity. The Clerk adapter boundary and environment path exist, but Clerk sessions are not connected.

Companies, contacts, opportunities and tasks share list and form components. Each protected route supplies only the entity configuration; the browser API client owns safe transport errors and the components own loading, empty, error and responsive mobile/desktop states. Business validation remains server-side even when HTML constraints improve feedback.

## API architecture

FastAPI exposes:

- `GET /health` for process health;
- `GET /ready` for honest configured-dependency readiness;
- `GET /api/v1/me` for the authenticated identity and active organisation context.
- CRUD collections and resources under `/api/v1/companies`, `/api/v1/contacts`, `/api/v1/opportunities` and `/api/v1/tasks`.

Routes use Pydantic request/response models, camel-case JSON, bounded pagination, explicit filters/sorts, request IDs, structured content-redacted logs, explicit CORS and central safe error handlers. Route handlers delegate business rules to services and all SQL to repositories.

## Persistence and tenancy

SQLAlchemy 2 models Organisation, User, OrganisationMembership, Company, Contact, Opportunity and Task. UUIDs, UTC timestamps, allowed enum values, bounded numeric values, unique organisation slugs, unique external auth IDs and membership uniqueness are enforced in schema and migration.

Every business row has a non-null `organisation_id`. Composite foreign keys include the organisation for company/contact/opportunity relationships and membership-owned user fields, so the database cannot attach a record to another tenant even if application validation regresses. Deletes are restrictive when dependent product data exists.

The active organisation originates in the trusted auth adapter, never a body, path or query tenant identifier. Each request sets PostgreSQL's transaction-local `app.organisation_id`; repositories also apply an explicit organisation predicate. All four business tables enable and force RLS. Runtime deployment must use a non-bypass application role; migration credentials remain separate.

All authenticated organisation members currently have the same entity CRUD access. This is the safest simple interpretation because Sprint 2 specifies tenant isolation but no entity-level role matrix. A future authorisation change requires an explicit product decision and policy tests.

The API starts without a database so developers can inspect health and the shell, but `/ready` returns `503` and marks persistence unavailable. CRUD routes return a safe service-unavailable response.

## Contracts

FastAPI Pydantic models and OpenAPI are canonical. `packages/shared` mirrors the current response shapes manually and is updated in the same pull request. Client generation remains the intended follow-up when the contract surface makes generation simpler than the manual surface.

## Deployment direction

Vercel is planned for the web application. The API requires a managed Python host that supports a long-running ASGI process, private database connectivity, health/readiness probes, secrets and rolling rollback. Select it in a later ADR; the current system has no production deployment.

Supabase PostgreSQL, Clerk, Supabase Storage, OpenAI and Stripe are planned managed services. Only PostgreSQL-compatible persistence and auth adapter paths exist now.

## Future extension boundaries

Conversation capture, AI providers, storage and external systems will use narrow adapters. Future long-running work will run outside HTTP requests. A React Native client may later consume the same versioned API; no mobile code is included now. These boundaries prevent a Sales Brain implementation from blocking Recruitment Brain or Customer Success Brain without pre-building either product.
