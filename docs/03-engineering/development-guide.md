# Development guide

## Toolchain

- Node.js 22+
- pnpm 11.9.0
- Python 3.12+
- uv
- PostgreSQL 16 for persistence/migration work

Versions are pinned through repository metadata and lockfiles. Do not install project dependencies globally.

## Setup

From the repository root:

```bash
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
pnpm install
uv sync --project apps/api
docker compose -f infra/docker/compose.yml up -d
pnpm api:migrate
```

The default identity is a clearly labelled development mock. After migrations, the API idempotently provisions only that example organisation, user and membership in development. No paid credentials are required. Never use production customer data in the mock environment.

## Run

Use three terminals when exercising the internal infrastructure-test queue:

```bash
pnpm dev:api
```

```bash
pnpm dev:web
```

```bash
pnpm dev:worker
```

Web runs at `http://localhost:3000`, API at `http://localhost:8000`, and the worker runs as a separate backend process. The worker requires a migrated database. Its default deterministic mock provider makes no network call and needs no API key.

Provider defaults are `API_AI_PROVIDER_NAME=mock`,
`API_AI_PROVIDER_MODEL_IDENTIFIER=mock-infrastructure-v1` and
`API_AI_PROVIDER_TIMEOUT_SECONDS=10`. Unknown names/models fail safely; no real
provider or credential setting is implemented. Prompt/output defaults are
`API_AI_PROMPT_KEY=infrastructure_test` and
`API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS=3`. The latter is the total number of
provider calls allowed for malformed or schema-invalid output within one
claimed job attempt and accepts values from 1 to 5.

## Database workflow

SQLAlchemy metadata and Alembic migration history must agree:

```bash
pnpm api:migrate
pnpm api:migration:check
```

Do not edit an applied shared migration. Create a forward migration, review generated operations and test on PostgreSQL. The local Docker credentials are development-only.

Sprint 3 migration `0003_meeting_domain` creates meetings, participants, transcripts and meeting audit events with composite tenant relationships and forced PostgreSQL RLS. Its downgrade removes those four tables without changing Sprint 2 records.

Migration `0006_ai_worker_queue` adds worker ownership metadata and the narrow PostgreSQL tenant scheduler function. Upgrade, downgrade and re-upgrade preserve the existing AI trace and artefact immutability guards.

WO-004B2 requires no migration: existing AI job/artefact columns represent its
provider trace, usage and cost metadata.

WO-004B3 also requires no migration: existing prompt/schema trace columns plus
content-free audit metadata represent prompt/schema identity and structured
output attempt count.

## Validation

```bash
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
pnpm api:migration:check
pnpm build:api
```

`pnpm validate` runs the mock-backed format, lint, type, unit-test and build gate. Browser tests and database migration checks remain explicit because they require a browser or PostgreSQL.

## Changing an API field

1. Update the Pydantic contract.
2. Confirm the OpenAPI JSON name and required/optional behaviour.
3. Update `packages/shared` in the same pull request.
4. Add backend and consuming web tests.
5. Update documentation when the public behaviour changes.

## Troubleshooting

- `/ready` returning `503` is correct when PostgreSQL or authentication is unavailable.
- Mock auth is rejected in production and must remain visibly labelled locally.
- Empty Clerk values do not enable Clerk; the provider path remains unavailable until verified session/token handling is implemented.
- If a web build uses unexpected auth behaviour, check `AUTH_MODE` and `MOCK_AUTH_ENABLED` in `apps/web/.env.local`.
- Never paste real tokens into logs, issues, fixtures or documentation.
