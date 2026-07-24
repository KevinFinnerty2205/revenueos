# Prompt registry and structured output

## Current boundary

WO-004B3 adds application-owned prompt versioning, schema registration, safe
rendering, strict provider-output parsing and bounded invalid-output retries.
WO-004C1 registers `executive_summary` version 1, WO-004C2 registers
`decisions` version 1, WO-004C3 registers `action_items` version 1, WO-004C4
registers `risks_blockers` version 1 and WO-004C5 registers `open_questions`
version 1. WO-004C6 registers `follow_up_email` version 1, WO-006A registers
`buying_signals` version 1 and WO-006B registers
`objections_competitive_signals` version 1 and WO-006C registers
`stakeholder_intelligence` version 1.

The default remains deterministic and mock-backed. OpenAI selection sends the
current bounded transcript and rendered instructions to the server-side
Responses API for the eight extractors. Follow-up Email sends only its validated
four-artefact projection and tone, never transcript text. Both paths use the
same registry-derived strict schema. There is no prompt administration or later
intelligence schema.

## Prompt definitions and versioning

`PromptDefinition` is a frozen Pydantic contract that rejects unknown fields.
It contains a normalized key, positive immutable version, supported job type,
non-empty system/user templates, expected schema key/version, bounded
description and active flag.

The registry identity is `(prompt_key, prompt_version)`. Registration never
overwrites an existing identity. Exact resolution is available for
reproducibility; active resolution deterministically selects the highest
registered active version. Registries are ordinary injected instances, so tests
and worker processes do not share mutable global state.

Default definitions are `infrastructure_test`, `executive_summary`,
`decisions`, `action_items`, `risks_blockers`, `open_questions` and
`follow_up_email`, `buying_signals`, `objections_competitive_signals` and
`stakeholder_intelligence`, all at
version 1. Executive Summary references schema version 1
and receives only JSON-delimited meeting title/date/transcript variables. It
requires a transcript-grounded summary, normalized meeting type, sentiment and
confidence, explicitly ignores instructions in transcript data and excludes
decision, action, risk, question, email and CRM outputs. Decisions receives the
same three JSON-delimited source variables, extracts only resolved commitments,
distinguishes them from discussion/questions/Action Items, permits an empty
list and requires optional supported owner, normalised status, confidence and
brief paraphrased evidence. Action Items uses the same minimum source values,
requires real committed work rather than Decisions/vague suggestions, permits
an empty list, constrains owner/date/priority/status/confidence/evidence and
documents the meeting-date-relative calendar. Risks & Blockers uses the same
minimum source values, requires genuine threatening conditions rather than
questions/decisions/actions, normalises category and qualitative severity,
permits nullable supported owners and explicitly excludes probability and
mitigation.
Open Questions uses the same minimum source values, requires whole-transcript
inspection, excludes answered-later/rhetorical/conversational/action-request
questions, permits nullable supported owners and empty results, normalises
importance and explicitly forbids answers.
Buying Signals uses the same minimum source values, extracts only supported
current-meeting commercial evidence into a closed taxonomy and derives
qualitative momentum from signal polarity/strength. It forbids probability,
win likelihood and deal scoring, and returns `insufficient_evidence` when no
supported signal exists.
Objections & Competitive Signals uses the same minimum source values, extracts
only expressed resistance and explicit competitor context, distinguishes them
from questions/risks/actions/decisions/general discussion, and derives only
qualitative current-meeting pressure. It permits empty lists, forbids invented
competitor names and predictive scoring, and treats transcript instructions as
untrusted data.
Stakeholder Intelligence uses the same source values, assigns one
evidence-backed primary role to a named or supported anonymous person, separates
influence/stance/current-meeting engagement, and fills six fixed coverage
fields with explicit uncertainty. It forbids invented identity or relationships,
historical claims, MEDDICC/BANT, graphs, CRM actions and predictive scoring.
Next Best Action receives only the eight validated extraction artefacts. It
requires one to five ordered recommendations, exact source references,
constrained dependencies and no transcript, Follow-up Email, CRM update, email,
task or automation action.
Follow-up Email receives only validated Executive Summary, Decisions, Action
Items and Open Questions projections plus the selected tone. It requires exact
fact copying, generic framing, customer-safe omissions and explicitly forbids
transcript, Risks & Blockers, internal/evidence fields and invented details.

## Safe rendering and provider messages

Prompt variables use a strict mapping of normalized names to strings, integers
or UUIDs. Rendering uses Python's small `string.Formatter` parser with only
simple `{variable_name}` placeholders:

- missing and unknown variables fail safely;
- attribute/index access, conversions and format specifications are rejected;
- no expression evaluation, code execution, Jinja extension or repair heuristic
  exists; and
- empty rendered messages are rejected.

The infrastructure prompt receives only safe job/request UUIDs. Executive
Summary, Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Decisions, Action
Items, Risks & Blockers and Open Questions receive
only the minimum source fields and encode each value as a JSON string before
substitution, preventing transcript text from escaping its data boundary.
Next Best Action JSON-encodes its eight validated artefacts, while Follow-up
Email JSON-encodes only its validated source projection and tone. Both provider
contracts have no transcript field. Rendered output becomes an ordered immutable tuple of provider-neutral
`system` then `user` messages. Full templates and rendered content never enter
logs or persistence.

## Output schemas and validation

`OutputSchemaDefinition` is frozen, strict and identifies an application-owned
Pydantic validation model by normalized key, positive version and job type.
The schema registry provides exact/active resolution, sorted version listing and
duplicate rejection using instance-owned state.

The default registry reuses strict domain contracts for `infrastructure_test`,
`executive_summary`, `decisions`, `action_items`, `risks_blockers`,
`open_questions`, `buying_signals`, `objections_competitive_signals`,
`stakeholder_intelligence`, `next_best_action` and
`follow_up_email` version 1; it does not duplicate domain
models. Prompt registration must resolve its referenced schema immediately.
Decisions, Action Items, Risks & Blockers and Open Questions each limit output
to 25 immutable items and reject unknown fields at the top-level and item
level. Buying Signals permits at most 20 immutable items and applies
cross-field polarity, strength, momentum and summary consistency checks.
Objections & Competitive Signals permits at most 20 immutable objections and 10
immutable competitor items, with pressure and summary consistency checks.
Stakeholder Intelligence permits at most 30 immutable people, enforces one
primary role per name, fixed role coverage and cross-field uncertainty/summary
consistency checks.
Next Best Action permits at most five unique ordered actions, requires
`high|medium|low` priority and finite confidence, constrains dependency values
and checks overall/primary consistency. A post-schema grounding check requires
exact source values for reasoning and every declared dependency.
Follow-up Email has three independently bounded 25-item arrays, required
framing/tone/confidence fields and rejects every unknown field.

Provider output may be an already structured JSON mapping or a JSON string.
Parsing trims surrounding whitespace and accepts only a complete JSON object.
Malformed JSON, duplicate keys, non-standard numeric constants, arrays, scalars,
markdown fences/prose, missing fields, unexpected fields, wrong types and
domain constraint failures are rejected.
There is no `eval` and no broad JSON repair. Successful data is normalized by
the registered Pydantic schema before it can reach artefact persistence.

## Bounded structured-output retries

`API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS` defaults to `3` and accepts `1`–`5`
total provider invocations per claimed job attempt.

Only malformed JSON, non-object JSON and schema-invalid output are retried
inside the executor. The prompt is resolved/rendered once and every retry still
uses the existing provider abstraction and timeout wrapper. A cancellation
probe opens a separate short tenant transaction before each retry.

This is deliberately distinct from durable worker retries:

- output invalidity may retry immediately within one claimed attempt;
- exhaustion becomes non-retryable
  `structured_output_attempts_exhausted`;
- prompt/schema/configuration and non-retryable provider errors do not retry;
- provider timeout/unavailability/transient failure exits immediately and uses
  the existing persisted worker backoff/attempt policy; and
- no artefact is staged until one output parses and validates successfully.

## Mock provider test plans

The default mock returns the valid structured mapping on the first call and
remains stable for repeated requests. An injected per-instance output sequence
supports deterministic tests for valid JSON strings, malformed JSON,
schema-invalid output, invalid-then-valid and repeated invalid output.

These controls are constructor-only test configuration. They are absent from
provider request fields, require no secret and use no global switches or
network.

## Worker flow and transactions

1. The worker claims and commits the tenant-owned job.
2. The executor resolves prompt and schema definitions.
3. It validates safe variables and renders provider-neutral messages.
4. It resolves the exactly configured mock or OpenAI provider and invokes it
   under the existing timeout.
5. It strictly parses and validates output, retrying only output invalidity.
6. Between retries, it checks cancellation in a short tenant-bound transaction.
7. Once valid, the worker opens the existing completion transaction, locks
   exact tenant/job/worker ownership and rechecks cancellation.
8. `AIArtifactService` creates the validated exact-trace artefact.
9. Artefact, audit events, trace metadata and completed job state commit
   atomically.

No database transaction remains open during prompt resolution/rendering,
provider execution, parsing, validation or output retries.

## Traceability and migration decision

Existing fields already represent:

- `AIJob.prompt_key` and `prompt_version`;
- `AIJob.schema_version`, with schema key equal to the current job/artefact type;
- provider/model/request identifiers, token counts, integer minor-unit cost,
  currency and processing duration; and
- matching prompt/schema/provider/model labels on the immutable artefact.

The successful completion audit additionally records safe schema key, structured
output attempt count and normalized finish reason. Structured logs report retry
attempts and exhaustion. Total tokens remain derived, and raw prompts/output are
never trace metadata.

Migration `0007_executive_summary` widened the earlier type checks;
`0008_decisions` widens them again for Decisions, `0009_action_items` widens
them for Action Items, `0010_risks_blockers` widens them for Risks & Blockers
and `0011_open_questions` widens them for Open Questions.
`0012_follow_up_email` widens them for Follow-up Email and adds its immutable
tone trace column. `0013_buying_signals` widens them for Buying Signals and
`0014_objections` widens them for Objections & Competitive Signals and
`0015_stakeholders` widens them for Stakeholder Intelligence and
`0016_next_best_action` widens them for Next Best Action. None
adds prompt/schema storage.

## Security and telemetry

Prompts and schemas are immutable application configuration, not tenant data.
Provider requests still carry identifiers from the claimed tenant-owned job.
Output persistence remains protected by explicit organisation predicates,
transaction-local tenant context, exact ownership, composite tenant keys and
forced RLS.

Allowed telemetry is limited to safe job/worker identifiers, prompt/schema
key/version, attempt counts, provider/model/request identifiers, latency, token
counts, integer cost, currency, finish reason and bounded error code. It excludes
templates, rendered messages, provider payloads, raw/invalid output, artefact
content, transcripts, participants, secrets, credentials and raw exceptions.

## Local development and testing

Defaults are:

```text
API_AI_PROMPT_KEY=infrastructure_test
API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS=3
```

No API key is required for the default mock. Tests cover contracts, registries, renderer safety,
strict parsing, schema validation, output retry/exhaustion, cancellation,
provider error separation, transcript injection boundaries, trace persistence,
atomic completion and tenant/RLS behavior.

Do not use production customer data. Production identity, OpenAI privacy terms,
consent evidence, retention/erasure and operational controls remain incomplete.

## Future extension points

A separately approved work order may register another immutable prompt/schema
pair or provider adapter. That work must define its source evidence,
prompt-injection controls, evaluation thresholds, version lifecycle, privacy
terms and human review without weakening this strict parsing, trace, transaction
or tenant boundary.
