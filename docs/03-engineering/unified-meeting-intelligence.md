# Unified Meeting Intelligence workspace

## Product behaviour

WO-005 replaces the six independent Meeting Detail Intelligence panels with one
responsive reading workspace. It presents, in order, Executive Summary, Key
Decisions, Action Items, Risks & Blockers, Open Questions and Follow-up Email.
The header shows one product-safe overall state, a deterministic count summary,
the last activity time, the primary **Generate Meeting Intelligence** action and
a retry action when terminal failures exist.

The work order adds no new extraction or composition capability. Each capability
continues to use its own durable job, append-only artefact, prompt/schema trace,
individual API and retry rules. Completed content remains visible when another
section fails. A valid completed list with zero items is labelled as ready with
no results and counts towards progress.

No UI or aggregate response exposes job/artefact identifiers, provider/model
labels, prompt/schema versions, worker state, leases, attempts, internal error
codes, transcript text, prompt text or raw provider output.

## Aggregate read API

`GET /api/v1/meetings/{meetingId}/intelligence` returns the current transcript
version's six product-safe capability views, overall state, last activity time,
generation/retry availability and progress counts. It preserves all individual
capability endpoints.

The read path performs four bounded tenant-scoped reads: meeting, current
transcript, current-version capability jobs and artefacts for the selected jobs.
It filters jobs by each code-deployed prompt/schema configuration and selects the
latest equivalent job deterministically. It does not execute providers or mutate
state. Missing completed artefacts or invalid persisted content fail closed as a
safe capability failure.

Capability states are `unavailable`, `not_generated`, `queued`, `processing`,
`completed`, `failed` and `cancelled`. `emptyResult=true` distinguishes a valid
completed empty list from work that has never been generated.

## Overall-state precedence

The overall state is derived, never persisted. Precedence is deterministic:

1. `unavailable` when there is no usable current transcript or it exceeds a
   capability input limit;
2. `processing` when any capability is running, including when another section
   is queued or failed;
3. `partially_failed` when at least one capability failed or was cancelled and
   at least one capability has usable completed content;
4. `failed` when at least one capability failed or was cancelled and no
   capability has usable completed content;
5. `queued` when one or more capabilities are pending and none is running or
   failed;
6. `completed_with_empty_results` when all six capabilities completed and at
   least one list capability produced a valid empty result;
7. `completed` when all six capabilities completed with non-empty results where
   the schema supports emptiness;
8. `partially_generated` when at least one capability completed and remaining
   capabilities have not been requested; and
9. `not_started` when no capability has been requested.

Cancelled work is never counted as ready and follows failure precedence. A
completed empty result is ready. Follow-up Email remains unavailable or not
generated until its required sources are ready.

Progress includes `ready`, `queued`, `processing`, `failed`, `notGenerated` and
`total=6`, plus accessible text such as `3 of 6 ready`, `Generating 2 sections`
or `5 ready · 1 failed`. No percentage is shown because capabilities are not
assigned misleading equal weights.

## Generation orchestration

`POST /api/v1/meetings/{meetingId}/intelligence/generate` is a small authenticated
orchestration endpoint. It:

1. validates membership, tenant-scoped meeting access and transcript usability;
2. calls the existing request services for Executive Summary, Decisions, Action
   Items, Risks & Blockers and Open Questions;
3. reuses equivalent active/completed extraction jobs and creates only missing,
   failed or cancelled work under existing rules;
4. derives an intermediate aggregate state; and
5. creates or reuses a professional Follow-up Email job only when Executive
   Summary, Decisions, Action Items and Open Questions are completed.

The endpoint never invokes a provider synchronously. It returns `202` when at
least one durable job was created and `200` when all applicable work was reused.
The response contains the same safe aggregate view plus capability names created
or reused; it contains no internal identifiers.

Each existing capability request retains its meeting row lock, unique
tenant/meeting/transcript/job/idempotency key and post-conflict lookup. The
orchestrator restores PostgreSQL's transaction-local tenant setting after each
capability service commit. Concurrent orchestration calls therefore converge on
one equivalent job per capability. Follow-up Email generation keys advance from
terminal generations only, so observing another active request cannot create a
second generation during a race. The rollback path also retains the scalar
transcript version before an ORM rollback so concurrent conflicts cannot trigger
an expired-object read.

Transcript changes create a new version and therefore new logical extraction
work. Completed equivalent extraction jobs are not regenerated by the unified
action. Follow-up Email's individual Regenerate action remains deliberate and
independent.

## Follow-up Email dependency handling

The browser uses backend-derived readiness rather than elapsed time. When the
aggregate view reports all four required source sections completed and Follow-up
Email as `not_generated`, the same polling chain calls the idempotent orchestration
endpoint. This is the deliberately small status-polling orchestration approach;
there is no general workflow engine.

The request service and worker independently require same-tenant, same-meeting,
same-transcript source artefacts for Executive Summary, Decisions, Action Items
and Open Questions. They also require the code-deployed source prompt and schema
versions. Append-only artefacts plus completed-job reuse make that validated
current-version source set stable for the queued composer job. Risks & Blockers
is not in the source type allowlist.

The composer source loader never queries the transcript. Its typed provider
input has no transcript field. If transcript audit metadata changes, a source is
missing, or prompt/schema/transcript traces disagree, composition fails safely
before provider execution or persistence.

## Frontend polling and interaction

`MeetingIntelligenceWorkspace` owns one non-overlapping three-second polling
chain against the aggregate endpoint. It schedules the next request only after
the prior request settles, stops when no capability is queued or processing,
resumes after unified generation or capability retry, and aborts on unmount or
when the user leaves the Intelligence tab. Monotonic request sequence checks
prevent an older response from replacing newer state.

Network failures keep the last completed content visible and provide a safe
retry. Individual capability generation/retry endpoints remain available.
Follow-up Email retains tone selection, plain-text Copy and Regenerate. There is
no Send action.

The layout is a single reading column on mobile. Desktop places Decisions beside
Action Items and Risks & Blockers beside Open Questions while keeping Executive
Summary and Follow-up Email full width. Sections share headings, status labels,
timestamps, spacing, loading/error treatment and retry controls. Semantic tab,
section, article, heading, list and definition-list markup; visible focus styles;
`aria-busy`; live progress status; explicit severity text; and colour-independent
labels provide the accessibility baseline. The loading card reserves space to
limit layout shift and all containers use bounded responsive widths without
horizontal overflow.

## Tenant isolation, privacy and telemetry

Both aggregate endpoints use the existing verified tenant dependency. Repository
queries include organisation, meeting and transcript-version predicates; forced
RLS remains defence in depth and the runtime role must not bypass it. There is no
privileged aggregator and cross-tenant reads/generation return not found.

Structured metadata-only logs record the initial workspace view, generation
requests, created/reused job counts, safe capability counts, overall-state
transitions, composer readiness, polling start/stop, partial failure and all-ready
states. The unified polling chain supplies only the previously observed safe
overall state and a bounded polling lifecycle value on later aggregate reads;
this adds no extra request loop or persistence. Logs never contain transcripts,
prompts, generated summaries, decisions, tasks, risks, questions, email content
or raw provider data. Existing job/artefact audit events remain content-minimised.

## Testing and local development

Backend tests cover all overall states and precedence, unavailable/product-safe
aggregate reads, orchestration reuse, concurrent generation, source dependency
gating, transcript-version changes and cross-tenant denial. Existing composer
tests prove artefact-only provider input and Risks & Blockers exclusion.

Frontend tests cover ordered rendering, duplicate-submit prevention, unified
polling and termination, automatic dependency orchestration, partial failures,
copy/no-send behaviour and abort on unmount. Deterministic Playwright routes
exercise the complete mock-only flow, refresh persistence, copy and mobile
overflow without a real OpenAI call.

For local use, run the API, web app and durable worker, add a synthetic transcript,
open the Intelligence tab and select **Generate Meeting Intelligence**. The mock
provider remains the default. Do not use production customer data.

## Migration, rollback and known limitations

No database migration is required. The implementation derives state from the
existing job, artefact and current-transcript trace.

Rollback is an application deploy rollback: restore the prior Meeting Detail
panel composition and remove the aggregate routes/service/contract additions.
Existing individual endpoints, jobs, artefacts and migrations remain compatible;
no data rollback is needed. In-flight jobs continue under the durable worker.

Known limitations remain:

- intelligence uses only the current transcript version and historical transcript
  bodies are not retained;
- prompts and schemas are code deployed;
- OpenAI sends content externally only when explicitly configured;
- production customer data remains prohibited;
- there is no editing, approval, sending, CRM/task/calendar integration,
  cross-meeting or account intelligence, streaming or WebSockets.
