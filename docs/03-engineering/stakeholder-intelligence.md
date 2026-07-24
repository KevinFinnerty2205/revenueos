# Stakeholder Intelligence

## Product behaviour

WO-006C adds an independent, transcript-grounded Sales Intelligence capability
to the Unified Meeting Intelligence workspace. It identifies people and buying
roles explicitly supported by the current usable meeting transcript, describes
their influence, stance and meeting engagement, and shows fixed buying-role
coverage.

The result is a cautious reading of one meeting. It is not a relationship graph,
an account history, a CRM identity match, a MEDDICC/BANT assessment, a deal score,
a forecast or an outreach recommendation. Confidence means confidence in the
transcript evidence, never the probability of a commercial outcome. When a name
is absent, a supported anonymous label such as `Customer procurement
representative` may be used; a person, name or organisation must not be invented.

## Schema v1

Prompt key, schema key and artefact/job type are
`stakeholder_intelligence`; each is version `1`.
`StakeholderIntelligenceArtifactContent` is strict, immutable and rejects unknown
fields. It requires:

- `stakeholders`: zero to 30 items, with one primary role per normalised name;
- `role_coverage`: fixed fields for `economic_buyer`, `decision_maker`,
  `champion`, `technical_buyer`, `procurement` and combined `legal_security`;
- `stakeholder_summary`: 20–800 trimmed characters grounded in the validated
  items and coverage; and
- `confidence`: a finite evidence confidence from `0` to `1`.

Each stakeholder contains a 1–200-character name or anonymous label, nullable
1–200-character organisation, one role, influence, stance, engagement, a
5–400-character evidence paraphrase and finite confidence from `0` to `1`.
Control characters are rejected and unknown fields are never retained.

The role vocabulary and meaning are:

| Role | Evidence-bound meaning |
| --- | --- |
| `economic_buyer` | Controls or owns final financial approval. |
| `decision_maker` | Has explicit final selection or approval authority. |
| `champion` | Actively advocates internally for the proposed change or solution. |
| `influencer` | Shapes the evaluation without supported final authority. |
| `blocker` | Explicitly resists or can prevent progress. |
| `technical_buyer` | Controls technical approval. |
| `technical_evaluator` | Assesses technical fit without supported approval authority. |
| `end_user` | Is expected to use the product or service. |
| `procurement` | Represents purchasing or procurement review. |
| `legal` | Represents legal or contracting review. |
| `security` | Represents security or privacy assurance review. |
| `finance` | Represents finance without supported final economic authority. |
| `executive_sponsor` | Provides explicit executive sponsorship. |
| `implementation_owner` | Owns implementation or rollout. |
| `vendor_representative` | Represents the seller or another vendor. |
| `participant` | Participated, but no stronger buying role is supported. |
| `unknown` | A person is referenced but a reliable role is not supported. |

These distinctions are deliberate. A champion advocates internally; an
influencer shapes evaluation; a decision maker controls selection; an economic
buyer controls financial approval; and a blocker explicitly resists or can
prevent progress. Titles, seniority, attendance, politeness and enthusiasm do
not establish any of those roles by themselves.

`influence` is `high`, `medium`, `low` or `unclear` and describes only the
authority or effect supported by this meeting. `stance` is `supportive`,
`neutral`, `resistant`, `mixed` or `unclear`. `engagement` is `active`,
`passive`, `absent_but_referenced` or `unclear`; it describes participation in
this meeting, not account engagement over time.

## Coverage, uncertainty and consistency

Every fixed coverage field is `identified`, `not_identified`, `unclear` or
`not_discussed`:

- `identified` requires a returned stakeholder with the matching primary role;
- `not_identified` means the role was relevant or explicitly missing, but no
  person was identified;
- `unclear` means the transcript touches the role but does not support a clear
  identification; and
- `not_discussed` means the role was not materially discussed.

`legal_security=identified` requires either a `legal` or `security` stakeholder.
The reverse also holds: a returned coverage role must be marked identified.
The contract rejects duplicate people, a supportive blocker, an absent
participant, high influence for `participant` or `unknown`, role confidence
above `0.5` for `unknown`, and role confidence above `0.8` for `participant`.
An empty result
cannot mark a role identified, cannot exceed `0.5` confidence and must use
insufficient-evidence language. The summary cannot invent names, relationship
claims or buying roles absent from the validated content. These are conservative
structural safeguards; they do not turn one transcript into historical truth.

The successful empty message is: “There was not enough evidence to identify
stakeholder roles reliably.”

## Prompt, mock and provider support

Prompt v1 receives only JSON-encoded `meeting_title`, `meeting_date` and
`transcript_text`. It treats title and transcript as untrusted data, ignores
embedded instructions, assigns one primary role per stakeholder, permits
anonymous labels only when supported, distinguishes role/influence/stance/
engagement, and requires explicit uncertainty. It prohibits invented people,
organisations, relationships, account history, MEDDICC/BANT, predictive scores,
CRM actions and outreach recommendations. Rendered prompts are neither logged
nor persisted.

The deterministic mock remains offline and credential-free. Its bounded fixture
logic covers named and anonymous people, the core buying roles, broader roles,
active/passive/absent/unclear engagement, supportive/resistant/mixed/unclear
stance, independent role-coverage outcomes, polite-but-unsupported discussion,
injection text, multiple stakeholders, empty output and malformed structured
output. It is deterministic test/demo behaviour, not production reasoning.

The OpenAI Responses adapter explicitly allowlists `stakeholder_intelligence`,
uses the registry-derived strict JSON Schema, disables SDK retries and validates
the returned JSON with the same Pydantic and consistency rules. Unknown and
infrastructure-only job types fail before SDK construction. Tests use fakes and
make no real OpenAI call. Only when `AI_PROVIDER=openai` is deliberately enabled
does the server send the rendered instructions and bounded current transcript to
the configured OpenAI model.

## Execution, persistence and idempotency

`StakeholderIntelligenceExecutor` uses the existing prompt renderer, provider
registry, structured-output retry boundary and durable PostgreSQL-backed worker.
The worker loads the exact organisation/meeting/transcript/version source, caps
trimmed text at 50,000 characters without truncation, checks cancellation before
provider attempts and persistence, and completes the job only after the
validated append-only artefact is committed. Provider timeouts remain bounded
durable retries; source and exhausted validation failures are non-retryable.

Job equivalence includes organisation, meeting, current transcript version, job
type, prompt version, schema version and retry generation. Equivalent pending,
running or completed work is reused. Failed or cancelled work may create the
next ordinal retry; a transcript correction creates new logical work. The
meeting lock, unique key and post-conflict lookup converge concurrent requests.
Artefacts remain append-only and independent from every other capability.

Migration `0015_stakeholders` widens only `ai_jobs.job_type` and
`ai_artifacts.artifact_type` checks. Existing tenant, trace, immutability and
SQLite/PostgreSQL protections remain. Downgrade deletes only Stakeholder
Intelligence artefacts/jobs before restoring the WO-006B allowlists; re-upgrade
is supported.

## APIs and unified workspace

Individual endpoints are:

- `POST /api/v1/meetings/{meetingId}/intelligence/stakeholders`; and
- `GET /api/v1/meetings/{meetingId}/intelligence/stakeholders`.

They expose unavailable/empty, queued, running, completed, failed and cancelled
states. Completed empty content is successful. Product responses follow the
existing capability convention for job/status trace while excluding attempts,
leases, worker/provider/prompt/schema details, transcript text, raw output and
internal error codes.

The aggregate response adds `stakeholderIntelligence`. Unified generation now
creates or reuses eight independent transcript extractions: Executive Summary,
Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence,
Decisions, Action Items, Risks & Blockers and Open Questions. Follow-up Email is
the ninth capability and remains a separate composition. Its four prerequisites
and artefact-only provider input are unchanged; Stakeholder Intelligence is
neither a prerequisite nor an input. Aggregate progress therefore uses
`total=10` after WO-006D while retaining the bounded four-query read path.

The responsive Stakeholders section appears after Objections & Competitive
Signals and before Decisions. It shows the textual summary, current-meeting
confidence, six fixed coverage fields and evidence-backed stakeholder cards. It
uses cautious labels such as “Likely Champion” and “Role not discussed”, with no
gauge, score, graph or CRM action. Shared accessible states and actions cover
unavailable, not generated, queued, processing, completed/valid-empty, failed
and cancelled.

The workspace retains one non-overlapping three-second aggregate polling chain.
It stops when idle, resumes after generation/retry, aborts on navigation or
unmount and rejects stale responses. This capability adds no second poller,
WebSocket, streaming path or workflow engine.

## Tenant isolation, privacy and telemetry

Verified membership and tenant context are required. Every source/job/artefact
read uses explicit organisation, meeting and transcript-version predicates;
forced PostgreSQL RLS remains defence in depth. Unknown and cross-tenant
meetings fail as not found.

Existing trace metadata retains organisation, meeting, transcript version, job,
prompt/schema versions, provider/model, provider request ID, structured-output
attempts, token/cost data, finish state, duration and timestamps. Logs and audit
events record only identifiers, lifecycle labels, empty flags, aggregate counts
and counts by role, stance, engagement and coverage state. They never contain a
transcript, prompt body, stakeholder name, organisation, summary, evidence, raw
provider output, credential or SDK object.

## Testing, rollback and known limitations

Tests cover strict schema limits and consistency, every role/coverage state,
uncertainty and injection rules, deterministic mock fixtures, strict OpenAI
mapping, executor retry/exhaustion/cancellation, durable timeout handling,
idempotency/concurrency/append-only traceability, API lifecycles and tenant
denial, aggregate totals/query bounds, accessible UI states, single polling and
the mock-only persisted browser flow. PostgreSQL and forced-RLS tests run when
the configured test database is available.

Rollback first deploys the WO-006B application and stops new WO-006C workers.
Downgrade `0015_stakeholders` only after explicit approval to delete Stakeholder
Intelligence jobs and artefacts. Other intelligence data is retained.

Known limitations are intentional: current meeting transcript only; no
historical stakeholder tracking, cross-meeting relationship analysis, contact
enrichment, CRM identity resolution, organisation graph, account memory,
outreach recommendations, MEDDICC/BANT or predictive scoring; one primary role
per stakeholder; anonymous labels where names are unavailable; code-deployed
prompt/schema; external OpenAI data flow only when enabled; no retention of
historical transcript bodies; and no production customer data until production
identity, consent, retention, export/erasure and operational controls are
approved.
