# Objections & Competitive Signals intelligence

## Product behaviour

WO-006B adds an independent transcript-grounded Sales Intelligence capability
to the Unified Meeting Intelligence workspace. It identifies resistance,
concerns, hesitation or challenges expressed in the current usable meeting
transcript, records how each was handled, and reports explicit competitor
mentions and their transcript-supported position.

The capability reports **current meeting objection pressure**. This is a
qualitative description of the validated content from one meeting, not a deal
loss probability, close probability, forecast or numeric score. Confidence is
evidence confidence from `0` to `1`; it is not an outcome probability.

An objection is not every risk or question. “Legal review may delay signature”
is a risk; “the customer said the contract terms are unacceptable” is an
objection. “Does the platform support SSO?” is a question; “the customer said
lack of SSO would prevent adoption” is an objection. One issue may appear in
both Risks & Blockers and Objections only when the transcript supports both an
operational threat and expressed buyer resistance. Buying Signals describes
commercial progress or its absence; Objections captures expressed resistance
and does not mechanically copy Buying Signals.
Stakeholder Intelligence separately classifies explicitly supported people and
buying roles; an objection with a person attached does not by itself establish
that person's primary stakeholder role or influence.

## Schema v1

`ObjectionsCompetitiveSignalsArtifactContent` in
`apps/api/src/revenueos/ai_contracts.py` is strict, immutable and rejects
unknown fields. The top level requires:

- `objections`: at most 20 items; an empty list is valid;
- `competitors`: at most 10 items; an empty list is valid;
- `overall_objection_pressure`: `none`, `low`, `medium`, `high`, `severe` or
  `insufficient_evidence`; and
- `summary`: 20–800 trimmed characters based only on the validated items.

Each objection has concise plain text from 5–500 characters, one category, one
status, one strength, a nullable transcript-supported owner, finite confidence
from `0` to `1`, and a 5–400-character evidence paraphrase. The categories are:

| Commercial and governance                                                        | Delivery and product                                                                  | People and relationship                                            |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `pricing`, `budget`, `commercial`, `legal`, `security`, `privacy`, `procurement` | `technical`, `integration`, `implementation`, `resourcing`, `timeline`, `product_fit` | `stakeholder`, `change_management`, `competitor`, `trust`, `other` |

Status definitions are deliberately evidence-bound:

- `resolved`: the transcript clearly supports that the resistance was answered
  or accepted;
- `partially_addressed`: some response or progress is present but material
  concern remains;
- `deferred`: the parties explicitly left the objection for later; and
- `unresolved`: no transcript-supported resolution is present.

Strength describes the intensity and materiality expressed in the transcript:
`strong` is explicit and material resistance, `moderate` is meaningful but not
decisive resistance, and `weak` is tentative or limited resistance. Politeness
does not prove resolution.

Each competitor item requires a normalised name, one position, finite evidence
confidence, and a short evidence paraphrase. An explicitly identified but
unnamed alternative is normalised as `Unnamed competitor`; no name is invented.
Position means:

- `stronger`: the transcript compares the alternative favourably;
- `weaker`: the transcript compares the alternative unfavourably;
- `neutral`: a comparison is supported but neither side is favoured;
- `present`: the competitor is merely present without a supported comparison;
  and
- `unclear`: competitive position cannot be established from the available
  wording.

The contract contains no market-share field, ranking, win probability,
forecast, expected value or deal score.

## Qualitative pressure and consistency

Pressure is derived directly from the extracted items without a hidden numeric
model. Prompt v1 describes `none` as no supported objection pressure, `low` as
weak/resolved content, `medium` as material but bounded content, `high` as
strong unresolved resistance or meaningful disadvantage, `severe` as the most
acute supported resistance or competitive disadvantage, and
`insufficient_evidence` as genuinely inadequate evidence.

Application validation enforces conservative deterministic boundaries:

- an empty result can use only `none` or `insufficient_evidence`;
- a strong unresolved objection cannot use `none`, `low` or
  `insufficient_evidence`;
- `severe` requires a strong unresolved objection or a competitor explicitly
  positioned as `stronger`;
- `insufficient_evidence` cannot contain moderate/strong objections,
  directional competitor comparisons or item confidence above `0.7`;
- resolved-only weak objections with no competitors cannot imply `severe`;
- a summary may name a defined objection area only when that category is in the
  validated objection list; and
- a summary may discuss competition or name `Competitor …` only when the
  corresponding validated competitor content exists.

The vocabulary checks are conservative structural safeguards rather than
semantic proof. Prompt instructions remain responsible for producing a concise
summary from the returned items only.

## Prompt, providers and execution

Prompt key/version and schema key/version are
`objections_competitive_signals`/`1`. The code-deployed prompt receives only
JSON-encoded `meeting_title`, `meeting_date` and `transcript_text`. It treats
the meeting title and transcript as untrusted data, ignores embedded
instructions, distinguishes objections from questions, risks, action items,
decisions and general discussion, rejects curiosity as resistance and
politeness as resolution, prohibits invented competitor names and predictive
output, and requires strict structured output with empty lists when warranted.
Rendered prompts are neither logged nor persisted.

The deterministic mock remains offline and credential-free. Its bounded
fixtures cover pricing, security and implementation objections; resolved,
partially addressed, deferred and unresolved states; weak and strong intensity;
named and unnamed competitors; stronger, weaker and merely present positions;
question-only, risk-only, polite-interest and explicit no-objection content;
and malformed/schema-invalid retry paths. This is test/demo fixture logic, not
production reasoning.

The OpenAI Responses adapter explicitly allowlists the new job type, uses the
registry-derived strict JSON Schema, disables SDK retries, and validates the
response again with Pydantic and application consistency checks. Unknown types
and `infrastructure_test` fail before SDK invocation. Refusal, incomplete,
timeout and malformed output paths are safely normalised. Tests use SDK fakes
only and make no real OpenAI request. When OpenAI is explicitly enabled, the
bounded current transcript is sent to the configured model.

`ObjectionsCompetitiveSignalsExecutor` uses the existing renderer, provider
registry, structured-output parser, bounded validation retries and durable
worker. The worker loads the exact tenant/meeting/transcript/version source,
checks cancellation before provider attempts and persistence, and completes the
job only after the validated append-only artefact is created in the completion
transaction. Provider timeout remains a durable retry; source and validation
failures are non-retryable.

## Persistence, idempotency and migration

Migration `0014_objections` widens only the database checks for
`ai_jobs.job_type` and `ai_artifacts.artifact_type`, while preserving the
existing SQLite/PostgreSQL tenant, trace and immutability protections.
Downgrade removes Objections & Competitive Signals jobs and artefacts before
restoring the WO-006A checks; re-upgrade is supported.

Job equivalence is scoped by organisation, meeting, current transcript version,
job type, prompt version, schema version and retry generation. Equivalent
pending, running or completed work is reused. Failed or cancelled work may
advance to the next bounded retry key; a transcript version change permits a
new job. Meeting locking, the unique key and post-conflict lookup converge
concurrent requests. Artefacts are append-only and independent from other
capabilities.

## APIs and aggregate workspace

Individual endpoints are:

- `POST /api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals`;
  and
- `GET /api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals`.

They support unavailable/empty, queued, running, completed, failed and
cancelled lifecycle responses. A completed empty result is successful. Product
responses exclude job/artefact identifiers, worker ownership, leases, attempts,
internal error codes, prompt/schema/provider configuration, transcripts and raw
output.

The aggregate response includes `objectionsCompetitiveSignals`. Generate
Meeting Intelligence now creates or reuses eight independent transcript
extractions: Executive Summary, Buying Signals, Objections & Competitive
Signals, Stakeholder Intelligence, Decisions, Action Items, Risks & Blockers and Open Questions.
Follow-up Email remains the ninth capability and a separate composition. Its
four prerequisites and validated artefact-only input are unchanged; objections
are neither a prerequisite nor an email input. Progress therefore uses
`total=10` after WO-006D, and the aggregate read retains its bounded four-query path.

The UI section appears after Buying Signals and before Decisions. It shows a
textual current-meeting pressure label, summary, objection cards and competitor
cards with their explicit labels, confidence and evidence. It has no gauge or
probability. The completed empty copy is “No objections or competitive signals
were identified in this meeting.” Shared semantic headings, status text,
keyboard-accessible actions, focus treatment and responsive layout apply.

The workspace continues to own one non-overlapping three-second aggregate
polling chain. It stops when idle, resumes after generation/retry, aborts on
unmount/navigation and rejects stale responses. This capability adds no second
poller, WebSocket or workflow engine.

## Tenant isolation, privacy, traceability and telemetry

Verified tenant context and active membership are required. Repository reads
retain explicit organisation predicates and forced RLS remains defence in
depth. The source transcript must match the active meeting, organisation and
version. Blank or whitespace-only text and content over 50,000 trimmed
characters fail safely without truncation.

Existing job and artefact metadata retains organisation, meeting, transcript
version, job, prompt/schema versions, provider/model, provider request ID,
structured-output attempts, token usage, estimated cost/currency, finish state,
duration and timestamps. Logs/audits contain identifiers and metadata-only
created/reused/execution/completion/failure events plus objection/competitor
counts, counts by category/status/strength, pressure and empty-result flags.
They exclude transcript, prompt, objection/competitor/summary/evidence content,
raw output, API keys and SDK objects.

## Testing, rollback and known limitations

Tests cover schema limits/immutability, enum and confidence rejection,
cross-field contradictions, prompt injection and capability distinctions,
deterministic fixtures, strict OpenAI schema and safe provider failures,
executor success/empty/retry/exhaustion/cancellation/source handling,
idempotency and traceability, API lifecycle/tenant safety, aggregate totals and
query bounds, accessible UI lifecycle states, single-chain polling and the
mock-only persisted browser journey. PostgreSQL/RLS tests run when the
configured PostgreSQL test database is available.

Rollback first deploys the prior application and stops new WO-006B workers,
then downgrades `0014_objections` only if removal of this capability's jobs and
artefacts is approved. Other intelligence artefacts are not removed.

Known limitations are intentional: one current meeting transcript only; no
cross-meeting trends, account/opportunity context, MEDDICC/BANT, stakeholder
map, close probability, deal score, forecast, next-best action, CRM mutation,
task/email/calendar action, editing/approval workflow, memory, streaming,
recording, transcription or automation. Prompt/schema definitions are
code-deployed; mock extraction is deterministic; historical transcript bodies
are not retained; and production customer data remains prohibited until
identity, consent, retention, export/erasure and operational controls are
approved.
