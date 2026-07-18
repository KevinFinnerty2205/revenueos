# WO-004C1 — Executive Summary Intelligence Capability

## Objective

Deliver the first end-to-end Meeting Intelligence capability on the merged AI infrastructure: a deterministic mock-generated Executive Summary from the current meeting transcript, with minimal authenticated API and responsive Meeting Detail UI.

## Delivered

- `executive_summary` job and artefact types;
- migration `0007_executive_summary`, widening only existing type constraints and preserving RLS/immutability guards;
- strict Executive Summary schema v1 and versioned prompt v1;
- 50,000-character current-transcript input policy with no truncation;
- deterministic no-network provider output and injection-as-data behaviour;
- transcript source loader and Executive Summary executor using the durable worker;
- append-only exact-trace artefact persistence before atomic job completion;
- idempotent request/retry/transcript-version rules;
- authenticated POST/GET endpoints under the meeting resource;
- accessible Meeting Detail Intelligence tab with six states, manual retry and non-overlapping three-second polling;
- safe metadata-only telemetry/audits;
- backend, API, migration, tenant, worker, component and browser coverage; and
- architecture, product, API, AI, provider, worker, prompt, development, security, roadmap and ADR updates.

## API

- `POST /api/v1/meetings/{meetingId}/intelligence/executive-summary` — queue or return equivalent work (`202` new, `200` existing).
- `GET /api/v1/meetings/{meetingId}/intelligence/executive-summary` — return empty, queued, running, completed, failed or cancelled state and the safe completed result when available.

No generic job, cancellation, streaming or WebSocket endpoint was added.

## Security and privacy

Organisation context comes only from verified application auth context. Meeting, transcript, job and artefact access retain explicit tenant predicates, composite tenant constraints and forced PostgreSQL RLS. Transcript text is structurally delimited as untrusted content and is excluded from logs, audits and safe errors. The provider performs no network call, so customer content does not leave the application.

Production customer data must not be used. Production identity, consent evidence, retention/export/erasure and operational controls remain incomplete.

## Validation

The repository gate covers Ruff/formatting, strict mypy, Pytest, PostgreSQL RLS/worker tests where configured, Alembic upgrade/downgrade/drift, ESLint, Prettier, TypeScript, Vitest, Playwright, production builds and repository audit/scope checks. CI is authoritative for PostgreSQL-only checks.

## Explicitly out of scope

No external/real AI provider or key, Decisions, Action Items, Risks, Open Questions, Follow-up Email, CRM Suggestions, integration, recording, transcription, embedding, vector search, relationship memory, notification, billing, agent, prompt editor, provider UI, streaming, WebSocket or external queue was added.

## Known limitations

- Output is deterministic mock content, not a real LLM result.
- Historical transcript bodies are not retained.
- Prompt/schema registries are code-deployed.
- Production customer data is prohibited.

See [Executive Summary intelligence](../03-engineering/executive-summary-intelligence.md) and [ADR 0010](../08-decisions/0010-current-transcript-executive-summary.md).
