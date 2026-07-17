# ADR 0001 — foundation architecture

- **Status:** Accepted
- **Date:** 2026-07-16
- **Scope:** Sprint 1

## Context

RevenueOS needs a fast early-stage foundation that supports Sales Brain and later Recruitment/Customer Success products without introducing operational systems before they are needed. The team needs strong typing, tenant-aware persistence, accessible web delivery and a Python ecosystem suitable for later AI work.

## Decision

Use a monorepo containing:

- Next.js App Router, strict TypeScript and Tailwind in `apps/web`;
- FastAPI, Pydantic, SQLAlchemy 2 and Alembic in `apps/api`;
- PostgreSQL-compatible persistence, with Supabase PostgreSQL planned;
- Clerk adapter boundaries for identity and organisations;
- `packages/shared` for the small current client contract and `packages/ui` only for truly shared primitives;
- GitHub Actions for validation, not deployment.

Keep the system a modular monolith. The browser calls the API; it never receives privileged database credentials. Pydantic/OpenAPI is canonical. Organisation context derives from trusted auth and is reinforced by repository scoping and PostgreSQL RLS.

Sprint 1 has no AI runtime, background worker, connector, billing service, mobile app, cache, broker or microservice.

## Alternatives considered

- **Single Next.js full-stack application:** simpler initially but weakens the approved Python/AI boundary and duplicates future API/mobile concerns.
- **Microservices from the start:** adds deployment, tracing and consistency cost without a measured requirement.
- **Supabase browser data access:** quick for prototypes but conflicts with server-owned authorisation and controlled tenant context.
- **GraphQL:** unnecessary for three small resource-style endpoints; OpenAPI provides a simpler typed boundary.
- **Redis/broker jobs now:** no Sprint 1 asynchronous product work exists.

## Consequences

Positive:

- clear web/API ownership and future mobile boundary;
- strong Python model/validation ecosystem;
- one transactional data foundation;
- provider adapters prevent unfinished integrations from leaking into domain code;
- simple local development without paid credentials.

Trade-offs:

- TypeScript response types are manually mirrored while the API is small;
- two language toolchains must be maintained;
- real Clerk, Supabase and deployment integration remain manual future work;
- RLS requires a separately provisioned non-bypass runtime role and PostgreSQL-specific verification.

## Follow-up trigger

Revisit this decision only when measured contract scale justifies client generation, durable background work requires a worker, or a hosting/provider requirement needs a narrower ADR.
