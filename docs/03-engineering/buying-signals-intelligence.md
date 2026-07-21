# Buying Signals and Deal Momentum intelligence

## Product behaviour

WO-006A adds the first Sales Intelligence capability to the Unified Meeting
Intelligence workspace. It examines only the current usable meeting transcript
and returns transcript-supported buying or deal-progress signals plus a
qualitative assessment of **current meeting momentum**. It does not predict
whether the opportunity will close.

The product answers four bounded questions: which positive signals were present,
which negative or explicitly missing/unclear signals were present, how strong
and well-supported each signal is, and what overall direction the evidence from
this meeting supports. Politeness, attendance, feature questions, compliments,
general interest and requests for information are not commercial intent.

Confidence is evidence confidence from `0` to `1`. It is never close
probability. The contract contains no win probability, forecast category,
revenue forecast, expected value, predicted close date or numeric deal score.

## Schema v1

`BuyingSignalsArtifactContent` in `apps/api/src/revenueos/ai_contracts.py` is
strict, immutable and rejects unknown fields. It permits at most 20 signals.
Each signal contains:

- `signal_type`: one normalised value from the list below;
- `polarity`: `positive`, `neutral` or `negative`;
- `strength`: `strong`, `moderate` or `weak`;
- `confidence`: a finite value from `0` to `1`; and
- `evidence`: a trimmed paraphrase from 5 to 400 characters.

The top level contains `signals`, `overall_momentum`, `momentum_summary` and
`confidence`. The summary is trimmed plain text from 20 to 800 characters.
`signals=[]` is valid only with `insufficient_evidence`.

Normalised signal types are:

| Area | Positive/progress | Missing, unclear or negative |
| --- | --- | --- |
| Budget | `budget_confirmed` | `budget_unconfirmed` |
| Timeline | `timeline_confirmed` | `timeline_unclear` |
| Decision-maker | `decision_maker_engaged` | `decision_maker_missing` |
| Champion | `champion_identified` | `champion_not_evident` |
| Procurement | `procurement_active` | `procurement_unclear` |
| Competition | `competitor_absent` | `competitor_present` |
| Urgency | `urgency_present` | `urgency_absent` |
| Commercial progress | `commercial_intent`, `implementation_commitment`, `next_step_committed` | `next_step_weak` |
| Stakeholders | `stakeholder_alignment` | `stakeholder_misalignment` |
| Technical fit | `technical_fit_confirmed` | `technical_fit_uncertain` |
| Security/legal | `security_or_legal_progress` | `security_or_legal_blocker` |
| Bounded escape hatch | `other` with any valid polarity | `other` with any valid polarity |

Positive semantic types require positive polarity. Material blockers require
negative polarity. Explicit missing/unclear types may be neutral or negative
depending on whether the transcript establishes a material effect. Competitor
presence may be neutral or negative; confirmed absence may be neutral or weakly
positive. Neutral signals cannot be strong.

## Momentum classification and consistency

`overall_momentum` is one of `strong_positive`, `positive`, `neutral`,
`negative`, `strong_negative` and `insufficient_evidence`.

Application validation is deterministic and contains no weighted or hidden
score:

- positive classifications require at least one positive signal;
- negative classifications require at least one negative signal;
- strong classifications require a strong signal of the same polarity;
- no signals requires `insufficient_evidence`;
- `insufficient_evidence` cannot contain a strong signal;
- neutral signals cannot use strong strength; and
- when a summary names a defined signal area such as budget, timeline,
  procurement, technical, stakeholder or legal/security, the validated signal
  list must contain that area.

The last rule is a deliberately conservative vocabulary check, not semantic
proof. Provider instructions remain responsible for deriving the summary only
from extracted signals. A generic insufficient-evidence summary is required
when the transcript cannot support a reliable direction.

## Prompt, providers and execution

Prompt key/version and schema key/version are `buying_signals`/`1`. Prompt v1 is
code-deployed in `ai_prompt_registry.py` and accepts only JSON-encoded
`meeting_title`, `meeting_date` and `transcript_text`. It treats title and
transcript as untrusted content, ignores embedded instructions, separates
signals from Decisions, Action Items, Risks & Blockers and Open Questions, and
explicitly prohibits predictive output. Rendered prompts are neither logged nor
persisted.

The deterministic mock remains offline and credential-free. It supplies stable
demonstration/test fixtures for confirmed and unconfirmed budget, confirmed and
unclear timeline, committed and weak next steps, decision-maker and champion
evidence, competitor presence, technical uncertainty, legal/security blockers,
mixed evidence, neutral discussion, insufficient evidence, polite interest,
empty output and malformed/schema-invalid retries. This is deterministic
fixture logic, not production reasoning.

The OpenAI Responses adapter explicitly allowlists `buying_signals`, sends the
registry-derived strict JSON Schema with SDK retries disabled, and rejects
unknown types and `infrastructure_test` before SDK invocation. When OpenAI is
enabled, the current transcript is sent to the configured OpenAI model.
Application Pydantic and consistency validation remains authoritative. Tests use
SDK fakes only and make no real OpenAI request.

`BuyingSignalsExecutor` uses the existing renderer, provider registry, bounded
structured-output retries and durable worker. The worker loads the exact
organisation/meeting/transcript/version trace, checks cancellation before each
provider attempt and again before persistence, persists the validated artefact
inside the completion transaction, and completes the job only after artefact
creation succeeds. Provider timeout remains a durable retry; transcript and
validation failures are non-retryable.

## Persistence, idempotency and migration

Migration `0013_buying_signals` is required because `ai_jobs.job_type` and
`ai_artifacts.artifact_type` are database-check-constrained. It adds only the
`buying_signals` values and preserves SQLite/PostgreSQL trace/immutability
guards. Downgrade deletes Buying Signals artefacts/jobs before narrowing the
checks; re-upgrade is supported.

The job key is scoped by organisation, meeting, transcript version, job type,
prompt version, schema version and retry generation. Equivalent pending,
running or completed work is reused. A failed or cancelled generation receives
the next bounded retry key. Meeting row locking, the database unique key and
post-conflict lookup make concurrent equivalent requests converge. A transcript
version change permits a new job. Completed artefacts remain append-only and
independent from every other capability.

## APIs and unified workspace

Individual endpoints are:

- `POST /api/v1/meetings/{meetingId}/intelligence/buying-signals`; and
- `GET /api/v1/meetings/{meetingId}/intelligence/buying-signals`.

They follow the existing empty/unavailable, queued, running, completed, failed
and cancelled conventions. A completed empty/insufficient result is successful.
Responses omit worker ownership, leases, attempts, internal error codes, prompts,
transcripts, raw output and provider configuration.

The aggregate endpoint includes `buyingSignals`. Generate Meeting Intelligence
now queues seven independent transcript extractions: Executive Summary, Buying
Signals, Objections & Competitive Signals, Decisions, Action Items, Risks &
Blockers and Open Questions. Follow-up Email remains the eighth capability and
separate composed output. Its four
prerequisites and artefact-only provider input are unchanged; Buying Signals is
not an email input. Progress therefore uses `total=8` and the existing bounded
four-query aggregate read avoids N+1 reads.

The frontend section appears after Executive Summary and before Decisions. It
shows a human-readable current-meeting momentum label, summary, assessment
confidence and signal cards with textual polarity, strength, confidence and
brief evidence. Colour is supplementary. There is no chart, gauge or score
meter. Not generated and insufficient-evidence states use the work-order copy.

The workspace continues to own one non-overlapping three-second aggregate
polling chain. It stops when idle, resumes after generation/retry, aborts on
unmount/navigation and rejects stale responses. Buying Signals creates no
second poller and adds no WebSocket.

## Tenant isolation, privacy, traceability and telemetry

Verified tenant context and active membership are required. All repository
queries include organisation predicates and forced RLS remains defence in depth.
The pinned transcript must belong to the same meeting and organisation. Missing,
blank, whitespace-only or transcripts over 50,000 characters fail safely without
truncation. The historical limitation remains: previous transcript bodies are
not retained, so a superseded pinned body cannot be reconstructed.

The job and artefact trace retains organisation, meeting, transcript version,
job, prompt/schema versions, provider/model, provider request ID, structured
output attempts, token usage, estimated cost/currency, finish state, duration and
creation time across existing job, artefact, log and audit fields. Logs/audits
contain only identifiers, versions, duration/usage and counts by polarity and
strength, overall classification and insufficient-evidence flags. Transcript,
prompt, evidence, momentum summary, raw output, generated signal text, API keys
and SDK objects are excluded.

## Testing, rollback and known limitations

Tests cover schema boundaries and immutability, consistency contradictions,
prompt variables/injection, deterministic fixtures, invalid-output retries,
cancellation, provider allowlisting, idempotency, transcript versioning,
append-only persistence, API state safety, aggregate totals, tenant denial,
single-chain polling, accessible UI states and the mock-only persisted browser
flow. PostgreSQL migration/RLS suites run only when their configured test URL is
available.

Rollback first deploys the prior application, then downgrades from
`0013_buying_signals` only if deleting Buying Signals jobs and artefacts is
acceptable. The downgrade does not affect other intelligence artefacts.

Known limitations are intentional: current meeting transcript only; no
cross-meeting trend, CRM/opportunity-stage context, predictive close probability,
forecast, revenue forecast, MEDDICC, BANT, objection taxonomy, stakeholder map,
next-best action or account memory. Prompt/schema definitions remain
code-deployed; mock behaviour is deterministic; OpenAI transfers transcript
content only when enabled; historical transcript bodies are not retained; and
production customer data remains prohibited until identity, consent, retention,
export/erasure and operational controls are approved.
