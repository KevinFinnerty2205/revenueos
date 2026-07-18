# RevenueOS AI

RevenueOS is the AI sales teammate that remembers every customer interaction and turns conversations into action.

This repository contains the Sprint 1 foundation, Sprint 2 tenant-isolated business entities, Sprint 3 Meeting Domain and WO-004A1/A2/B1 AI infrastructure. Meetings, deliberately supplied transcripts, audit history, AI persistence/domain rules and a separate durable worker for deterministic infrastructure tests are implemented. No API/UI exposes AI lifecycle data, and no provider, prompt, recording, media storage, transcription, genuine AI execution, integration, production Clerk verification or billing is implemented.

## Product blueprint

The [RevenueOS master product blueprint](docs/01-product/master-product-blueprint.md) defines the Sales Brain direction through private beta. Start with the [documentation index](docs/README.md), [MVP and beta scope](docs/06-roadmap/mvp-and-beta-scope.md) and [sequenced roadmap](docs/06-roadmap/product-roadmap-to-beta.md).

Target documents distinguish future direction from shipped functionality and do not authorise another sprint. The current implementation boundary is Sprints 1–3 plus WO-004A1/A2/B1.

## Prerequisites

- Node.js 22 or newer
- pnpm 11.9.0
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop or another PostgreSQL 16 instance if persistence is required

No paid-service credentials are required for local development.

## First-time setup

From the repository root:

```bash
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
pnpm install
uv sync --project apps/api
```

The example files contain local-only values and empty credential placeholders. Never commit the copied environment files.

## Start PostgreSQL and migrate

Docker Compose provides one local PostgreSQL service because PostgreSQL locking and forced RLS cannot be represented faithfully by a browser-side store.

```bash
docker compose -f infra/docker/compose.yml up -d
pnpm api:migrate
pnpm api:migration:check
```

If PostgreSQL is not configured, the API still starts in limited mode. `GET /health` remains healthy and `GET /ready` returns `503` with persistence marked unavailable.

## Run locally

Start the API, web application and internal worker in separate terminals:

```bash
pnpm dev:api
```

```bash
pnpm dev:web
```

```bash
pnpm dev:worker
```

Open:

- Web application: [http://localhost:3000](http://localhost:3000)
- API health: [http://localhost:8000/health](http://localhost:8000/health)
- API readiness: [http://localhost:8000/ready](http://localhost:8000/ready)
- OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

Local development defaults to a clearly labelled mock identity and example organisation. Mock authentication is rejected by API configuration and route policy in production.

## Available routes

Public web routes:

- `/`
- `/sign-in`
- `/sign-up`
- `/sign-out`

Protected routes:

- `/dashboard`
- `/companies`
- `/companies/new`
- `/companies/{id}/edit`
- `/contacts`
- `/contacts/new`
- `/contacts/{id}/edit`
- `/opportunities`
- `/opportunities/new`
- `/opportunities/{id}/edit`
- `/meetings`
- `/meetings/new`
- `/meetings/{id}`
- `/meetings/{id}/edit`
- `/tasks`
- `/tasks/new`
- `/tasks/{id}/edit`
- `/assistant`
- `/settings`

Assistant remains an honest placeholder. Company, contact, opportunity and task pages use the versioned API and provide list/create/edit states. Meeting pages provide list/search/filter/pagination, create/edit, participant management, deliberate plain-text transcript input and Overview/Transcript/History detail tabs.

API routes:

- `GET /health` — process health
- `GET /ready` — configured dependency readiness
- `GET /api/v1/me` — trusted authenticated user and organisation context
- CRUD under `/api/v1/companies`
- CRUD under `/api/v1/contacts`
- CRUD under `/api/v1/opportunities`
- CRUD under `/api/v1/tasks`
- CRUD under `/api/v1/meetings`
- nested participant CRUD under `/api/v1/meetings/{meetingId}/participants`
- singular transcript CRUD under `/api/v1/meetings/{meetingId}/transcript`
- `GET /api/v1/meetings/{meetingId}/history` — content-minimised audit activity

## Validation

Run the complete mock-backed validation gate:

```bash
pnpm validate
pnpm test:e2e
```

Individual commands:

```bash
pnpm audit
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm build:web
pnpm api:lint
pnpm api:format
pnpm api:typecheck
pnpm api:test
pnpm build:api
pnpm api:migration:check
```

CI runs the same checks, applies Alembic to PostgreSQL and performs the production builds. It does not deploy.

## Authentication configuration

The current authentication foundation provides:

- an explicit web/API authentication adapter boundary;
- server-side protected-route checks;
- a Clerk configuration path;
- a clearly labelled development mock;
- fail-closed production configuration.

Clerk token/session verification is not connected yet. Supplying placeholder keys does not make Clerk live, and the readiness endpoint reports that honestly. Do not use this repository with production customer data.

## Database migrations

Alembic is the only owner of application schema changes.

```bash
pnpm api:migrate
pnpm api:migration:check
```

Create future migrations from `apps/api` only after changing SQLAlchemy metadata, then review generated SQL and tenant implications before applying it.

## Production build commands

```bash
pnpm build:web
pnpm build:api
```

The web output is started with `pnpm --filter @revenueos/web start`. The API package is run with a production ASGI process using `revenueos.main:app`; the separately supervised worker uses `revenueos-ai-worker`. Deployment-provider configuration is intentionally deferred.

## Troubleshooting

- **`/ready` returns `503`:** start PostgreSQL, confirm `DATABASE_URL` in `apps/api/.env`, then run the migration.
- **Protected pages redirect to sign-in:** confirm `AUTH_MODE=mock` and `MOCK_AUTH_ENABLED=true` in `apps/web/.env.local` for local development.
- **API rejects mock auth:** `API_ENVIRONMENT=production` cannot use the mock. Use development locally.
- **Port already in use:** stop the existing process or change the local web/API command and update the corresponding URL/CORS variables.
- **OpenAPI or TypeScript contract changed:** update the small `packages/shared` surface in the same pull request. Pydantic/OpenAPI remains canonical.

See the [documentation index](docs/README.md), [development guide](docs/03-engineering/development-guide.md), [API reference](docs/03-engineering/api.md) and [WO-004B1 record](docs/07-sprints/wo-004b1-ai-worker-queue.md).
