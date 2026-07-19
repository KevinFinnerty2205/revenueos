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

Use three terminals when exercising the worker or Meeting Intelligence:

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

Provider selection defaults to `AI_PROVIDER=mock`, with
`API_AI_PROVIDER_MODEL_IDENTIFIER=mock-infrastructure-v1` and
`API_AI_PROVIDER_TIMEOUT_SECONDS=10` for the mock. OpenAI selection requires
server-only `OPENAI_API_KEY` and `OPENAI_MODEL`; timeout and output ceilings use
`OPENAI_TIMEOUT_SECONDS` and `OPENAI_MAX_OUTPUT_TOKENS`. Unknown names/models
fail safely and never fall back. Prompt/output defaults are
`API_AI_PROMPT_KEY=infrastructure_test` and
`API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS=3`. The latter is the total number of
provider calls allowed for malformed or schema-invalid output within one
claimed job attempt and accepts values from 1 to 5.

To exercise the product flow, create a meeting with an authorised plain-text
transcript no longer than 50,000 characters, open its **Intelligence** tab and
generate the Executive Summary, Decisions, Action Items, Risks & Blockers or
Open Questions. Each UI panel checks state every three seconds while
the worker processes the mock job. No API key or external network access is
required. Enabling OpenAI sends the rendered capability instructions and
selected transcript to OpenAI. Use only synthetic non-sensitive data and follow
the [manual smoke procedure](openai-provider-integration.md#manual-non-production-smoke-test);
never put an actual key value in shell history, screenshots or repository files.

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

Migration `0007_executive_summary` widens only the existing AI job and artefact
type check constraints. It adds no table, column, RLS policy or prompt storage;
upgrade/downgrade tests preserve the worker trace and artefact immutability
triggers.

Migration `0008_decisions` widens the same two type checks for Decisions and
adds no table, column, RLS policy or prompt storage. Its downgrade deletes
Decisions rows before restoring the Executive Summary-era checks.

Migration `0009_action_items` widens the same checks for Action Items without
adding a table, column, RLS policy or prompt storage. Its downgrade deletes
Action Items rows before restoring the Decisions-era checks.

Migration `0010_risks_blockers` widens the same checks for Risks & Blockers
without adding a table, column, RLS policy or prompt storage. Its downgrade
deletes Risks & Blockers rows before restoring the Action Items-era checks.

Migration `0011_open_questions` widens the same checks for Open Questions
without adding a table, column, RLS policy or prompt storage. Its downgrade
deletes Open Questions rows before restoring the Risks & Blockers-era checks.

WO-004C1A requires no migration because the existing trace fields already
represent provider, model, request ID, usage and cost/currency metadata.

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
