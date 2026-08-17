# Core capability gap analysis

- **Status:** Checkpoint 1 architecture review; no code, schema or provider change
- **Baseline:** Implemented WO-011–025 modular monolith
- **Decision:** Existing foundations are reusable; productisation, retrieval and one
  live CRM adapter precede Prospect

## Architecture verdict

RevenueOS does not need a platform rewrite to close the important Core gaps. The
current FastAPI/web/PostgreSQL modular monolith already provides tenant-scoped domain
repositories, forced RLS, immutable/versioned Evidence and AI artefacts, a durable
job lifecycle, typed provider ports, Action review, execution preview,
idempotency/reconciliation, retention/export/deletion and safe telemetry.

The largest gaps are real product paths over those foundations:

- target-environment approval and support for one capture-to-intelligence path;
- authorised retrieval and cited Q&A over current final sources;
- a provider-specific but adapter-contained CRM binding and execution path; and
- a simpler read projection so users do not navigate the underlying domain model.

No microservice, broker, vector database, graph database, second CRM model or generic
agent runtime is justified.

## Implemented boundary assessment

| Boundary                 | Current engineering strength                                                                                      | Material limitation                                                                                         | Checkpoint class                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Interaction Intelligence | Extensible Interaction/Capture/Evidence model; strict source-aware artefacts; reviewed debrief/visual inputs      | Final source reconciliation is spread across source-specific projections; production data path not approved | A for production path; B for consolidated projection |
| Recording/transcription  | Resumable bounded private upload, worker, versioned transcript segments, partial/failure states, mock/OpenAI port | Browser foreground limits; flags default off; optional adapter and target environment not approved          | A for one supported path; B for provider breadth     |
| Revenue Brain            | Immutable snapshots, conservative deterministic changes, no inference from silence                                | On-demand, bounded adjacent comparisons; not universal retrieval or outcome learning                        | C foundation; B later expansion                      |
| Opportunity Workspace    | Tenant-safe aggregate, current artefact validation, partial states, Actions and Methodology                       | Very long mixed-purpose projection; latest-meeting bias; incomplete account/source/file organisation        | B                                                    |
| Action Layer             | Immutable revisions, provenance, risk, review and exact approval                                                  | Proposal preparation is not a guaranteed post-Interaction automation; no live effect                        | C foundation                                         |
| Execution Foundation     | Separate preview/confirmation, fingerprint, idempotency, attempts, revoke and unknown state                       | Mock connections and mock results only                                                                      | A first CRM adapter; B other providers               |
| Sales Methodology        | Deterministic evidence policies, immutable versions/history and correction                                        | No manager roll-up; limited standard registry; no automatic queue                                           | C; manager context B                                 |
| RevenueOS Daily          | Bounded set-based aggregate, deterministic ranking, partial availability                                          | Personal only; Search target is a placeholder; no target/forecast                                           | C; Search A; later engines B                         |
| Security/trust           | Verified-context design, explicit predicates, forced RLS, content-safe logs, lifecycle controls                   | Production customer-data and provider/operational approvals remain outstanding                              | A launch gate                                        |

## WO-025A engineering boundary

WO-025A is productisation and release readiness, not a new intelligence engine.
Implementation planning should inventory the already-supported capture paths and
select the narrow target-environment offer. It must prove:

- production Clerk organisation/user lifecycle and fail-closed membership;
- PostgreSQL runtime role without RLS bypass and complete tenant regression;
- private object storage, key/scoped grant policy and reconciliation where recording
  is offered;
- approved AI/transcription provider payloads, region, retention/training contract,
  quotas, kill switch and evaluated strict-output quality;
- capture consent/authority configuration for the cohort and jurisdictions;
- retention/export/erasure across source, derived data, object storage, provider and
  backups;
- operational logs/metrics/alerts, support access, incident, restore and rollback;
- one supported end-to-end path including finalisation, review and failure recovery;
  and
- no production customer data in logs, tests, screenshots or demo fixtures.

Experience consolidation should create server-friendly read projections and route
composition while preserving current route/API compatibility. It should not rename
database entities merely to change navigation.

## WO-025B Ask RevenueOS architecture

### Query modes

Ask should have three explicit modes behind one Search experience:

1. **Navigation search** — find authorised accounts, Opportunities, Contacts,
   Interactions and Actions by indexed canonical metadata.
2. **Structured query** — deterministic filters/counts over typed current projections,
   such as Opportunities with an unknown economic buyer or unresolved security risk.
3. **Evidence-backed answer** — synthesise a concise answer from an authorised,
   bounded evidence bundle when deterministic presentation alone is insufficient.

A model must not generate SQL, expand permissions or choose an unbounded corpus. An
application-owned planner should map supported intents to typed query plans; an
unknown intent refuses or falls back to normal search.

### Source eligibility

Use current final validated projections and their source references. Exclude deleted,
superseded, stale-ineligible, provisional Live Intelligence, rejected Evidence,
unreviewed candidates and unauthorised bodies. Raw transcript/document/email bodies
must not be loaded merely because an answer can be produced from validated structured
intelligence. A separately justified exact-quote query may use a narrowly authorised
source-range retrieval contract with explicit source display and content controls.

### Answer contract

The future strict contract should distinguish:

- answered, partially answered, conflicting, stale, insufficient Evidence and
  unsupported query;
- bounded answer statements, each with one or more validated source references;
- scope, freshness and omitted/limited-result disclosure;
- suggested safe filters or destination links; and
- no proposed Action or tool call inside the answer.

References must be revalidated against tenant, permission, entity and current source
eligibility before persistence and again before display. Conversation history, if
retained at all, must be short, purpose-bound and tenant-owned; storing a generic chat
archive is unnecessary for the MVP.

### Search technology

Use PostgreSQL indexes/full-text search and existing typed repositories first. The
current scale and domain do not justify a vector database. Embeddings require a new
content-transfer, tenant-index, deletion, evaluation and cost boundary and should be
introduced only if measured retrieval quality cannot meet the supported question set
without them.

### Security and evaluation

Test cross-tenant and cross-role queries, indirect object references, prompt
injection inside customer sources, source deletion, stale/superseded inputs, citation
fabrication, conflicting evidence, broad portfolio queries and result-count limits.
Measure citation validity, supported-statement rate, refusal correctness, permission
denial, correction use, latency and safe provider cost. Logs contain query type,
scope class, counts, versions, latency and safe result state—not question or answer
content.

## WO-025C Core CRM Sync architecture

### Reuse

Extend the existing provider-neutral Connection, ActionExecutor, preview,
confirmation, attempt and reconciliation contracts. Add provider-specific OAuth and
API behaviour behind one adapter. Do not create CRMCompany, CRMContact or a parallel
Opportunity.

### Minimum additional concepts

The first connector needs a bounded tenant-owned binding/mapping surface:

- external connection/account identity and configuration version;
- canonical entity ↔ external object binding with provider revision/etag where
  available;
- allow-listed field/activity/task mapping and effective source authority;
- match confidence/review state without automatic person merge;
- incremental cursor/webhook receipt only if required by the selected MVP;
- conflict, tombstone/disconnect and last reconciled state; and
- immutable external execution receipt reference without customer payload in logs.

The exact schema belongs to the future work order. Checkpoint 1 does not authorise a
migration.

### Read/match before write

A safe write requires the product to know which external organisation, object and
field it is changing. The MVP must therefore read the minimum identifiers and current
values needed for explicit matching and conflict detection. It is not a general CRM
replica. Initial provider backfill must be bounded, resumable and reviewable.

### Authority and execution

Per field family, make external-authoritative, RevenueOS-authoritative or reviewed
bidirectional policy visible. The first Core connector should normally use
external-authoritative reads plus reviewed outbound proposals. A recent human edit,
validation rule, permission failure or unknown external state cannot be silently
overwritten/retried.

Provider idempotency is preferred; otherwise retain a durable request/result mapping
and reconcile before retry. Disconnect must stop new reads/writes immediately and
state what canonical data/receipts remain under policy.

### Provider selection

Choose Salesforce or HubSpot only after checking the design-partner majority,
sandbox/test support, granular OAuth scopes, object/field APIs, webhook/revision
semantics, rate limits, data residency/deletion, app-review requirements, pricing and
support burden. Do not select both for roadmap symmetry.

## Later dependency chain

### Pipeline, Analytics and Win/Loss

WO-035 should create the stable stage/current-deal projections and ordinary Workspace
hierarchy. WO-036 should define versioned business events, cohorts and metrics.
WO-036B can then create immutable reviewed deal-outcome explanations and sample-safe
aggregates. Win/Loss must not infer a lost reason solely from absent later Evidence or
from a model-selected theme.

### Targets and forecasting

WO-037 depends on metrics and team scope. WO-038 consumes explicit pipeline state,
metric history, target context, methodology/Evidence factors and outcome history. The
first implementation should be transparent deterministic/statistical policy with an
unavailable state; a learned model requires sample sufficiency, temporal evaluation,
calibration, bias review and a better-than-simple-baseline result.

### Manager Intelligence and coaching

WO-039 consumes the preceding typed projections. It may store a recommendation,
cited factors, review/dismissal and safe outcome association, not a general employee
profile. Team access must be separately authorised. Inputs such as keystrokes,
presence, private messages, emotion/personality and simplistic rep scores are
prohibited.

### Productivity and broader CRM integrations

Implement only the first of WO-040/041 justified by the cohort. It owns real
mail/calendar context and execution. Revised WO-042 builds on WO-025C for a second CRM
or broader mappings/backfill, not a new connector architecture.

## Workspace and Deal Room timing

Do not move WO-043 earlier. Current Opportunity hierarchy can be improved through
read projections and progressive disclosure without adding file entities. Secure
files, versions, previews, search, malware controls, object permissions and external
sharing should follow the WO-032 Create/storage foundation.

## Migration and dependency discipline

This review creates no migration and selects no provider. Future work orders must:

- retain one Alembic head and use Alembic alone for schema changes;
- update `packages/shared` only for the minimal client contract;
- keep provider clients behind typed adapters;
- use deterministic mocks in normal tests and separately prove live readiness;
- preserve existing APIs/routes or document compatible migration;
- include real PostgreSQL/RLS tests for every new tenant table/binding;
- update export, retention, deletion and organisation teardown in the same change;
  and
- pass the full repository gate without weakening checks.

## Risks and stop conditions

| Risk                                        | Control/stop condition                                                                                     |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Prospect starts before Core is observable   | Checkpoint 1B evidence is required; document completion is not a pass                                      |
| Ask leaks or hallucinates                   | Typed planner, bounded sources, citation validation and refusal; stop on unsupported-claim/access failures |
| CRM connector corrupts the system of record | Reviewed allow-listed changes, concurrency/conflict handling and reconciliation; stop automatic dispatch   |
| Navigation rewrite breaks current journeys  | Compatibility routes and task-based usability regression                                                   |
| Production enablement becomes a flag flip   | Target-environment evidence and named operational owners are release gates                                 |
| Forecast/coaching moves early for parity    | Preserve dependency order and explicit unavailable states                                                  |
| More infrastructure is added speculatively  | Require measured scale/retrieval/provider evidence and an ADR                                              |

## Conclusion

Architecture readiness is high. Product and operational readiness are not. Close the
three bounded pre-Prospect gaps on the existing foundations, validate them with real
users and retain the later dependency chain for analytics, forecast, coaching,
manager and Deal Room capability.
