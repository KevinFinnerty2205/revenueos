# Core roadmap adjustments after Checkpoint 1

- **Status:** Approved sequence; WO-025A/B/C implemented on 24 August 2026, while
  target-environment validation and observed Checkpoint 1B remain future
- **Source decision:** [Checkpoint 1 — Core competitive and product readiness](checkpoint-1-core-competitive-readiness.md)
- **Rule:** Prove the Core loop before adding a new data-acquisition module

## Sequence change

The former sequence moved directly from WO-025 RevenueOS Daily to WO-026 Account &
Lead Research. Checkpoint 1 changes it to: WO-025 Daily (complete) → WO-025A Core
readiness → WO-025B Ask RevenueOS → WO-025C Core CRM Sync → observed Checkpoint 1B.
Only a Checkpoint 1B pass proceeds to WO-026; otherwise revise the next smallest
experiment.

The inserted work is Core productisation, retrieval and external-system completion.
It does not add Prospect, Engage, Create or native CRM scope.

## WO-025A — Core Experience & Design-Partner Readiness

- **Objective/value/package:** Make the implemented Core loop safe, understandable
  and supportable for the first real design-partner cohort. **Core**.
- **Experience:** Replace entity-led onboarding with first-outcome onboarding;
  consolidate Core navigation; preserve compatible URLs; make Opportunity summary
  lead to why and Evidence; make mobile Today/Interactions/Actions/Search complete.
- **Operational outcome:** One existing capture path and its no-recording fallback
  are approved, configured, measured and supported in the target environment.
- **Security/privacy:** Close customer-data, identity, provider, storage, monitoring,
  backup/restore, incident, consent and launch-review gates for the offered cohort.
- **Acceptance:** A new seller reaches reviewed intelligence from a permitted real
  Interaction, understands the next action without assistance and encounters no
  clipped or feature-taxonomy navigation. Failure, correction, deletion and recovery
  behave as documented.
- **Out of scope:** New source taxonomy, meeting-bot matrix, new AI capability,
  forecast, manager analytics, Prospect and live external action.
- **Validate:** Time to first value, navigation success, review/correction behaviour,
  capture failures and trust interviews with actual cohort users.

WO-025A should select from existing capture architectures; it must not claim every
browser, meeting platform or jurisdiction is supported. If cohort evidence proves
native online capture essential to the first usable path, authorise a separately
bounded provider precursor rather than expanding this work order silently.

## WO-025B — Ask RevenueOS

- **Objective/value/package:** Let a seller or authorised manager retrieve and ask
  questions of current RevenueOS knowledge with citations, uncertainty and natural
  workflow links. **Core**.
- **Experience:** Search utility from Home and contextual workspaces; normal search,
  structured filters and answer mode; no new permanent Assistant destination.
- **Scope:** Account, Opportunity, Interaction, Action, methodology and portfolio
  questions over current final authorised projections and Evidence references.
- **Architecture:** Deterministic query planning and retrieval first; bounded provider
  synthesis only where useful; strict answer/citation contract; no model tool access.
- **Security/privacy:** Server-derived tenant/permission scope, source eligibility,
  no hidden body/transcript expansion, content-safe telemetry and adversarial access
  tests.
- **Acceptance:** Supported questions return concise answers with valid citations;
  unavailable, stale and conflicting evidence is stated; unsupported questions refuse
  safely; links open the authorised source.
- **Out of scope:** Generic web research, Prospect research, uncited chat, autonomous
  actions, cross-tenant retrieval, arbitrary SQL and a conversation-history product.
- **Validate:** Answer usefulness, citation validity, unsupported-claim rate, refusal
  quality, retrieval latency and repeat use.

**Implementation note (24 August 2026):** WO-025B chose deterministic classification,
bounded structured retrieval and deterministic composition with zero provider calls.
Opportunity, Account and user-owned workspace scopes, four answer states, strict
citations, quotas, metadata-only telemetry and ephemeral questions are current. A
provider composer remains a separately gated future change.

## WO-025C — Core CRM Sync

**Implementation note (24 August 2026):** HubSpot was selected after a documented
Salesforce/HubSpot comparison. The implemented boundary is confidential OAuth,
explicit record linking, typed field/stage authority, current-value preview,
explicit confirmation, verified write/activity execution, stale-state protection
and read-only uncertainty reconciliation. It remains off by default and does not
constitute target-environment or customer launch approval.

- **Objective/value/package:** Close one real approved Opportunity/Contact update loop
  while the customer's CRM remains authoritative. **Core integration foundation**.
- **Provider decision:** **HubSpot selected; Salesforce deferred.** Only HubSpot has a
  production adapter in WO-025C.
- **Experience:** Admin connection and health; explicit record match/mapping; source
  authority visible in Opportunity/Action review; exact preview, confirmation and
  receipt; useful unavailable/conflict/recovery states.
- **Minimum scope:** Read the identifiers and bounded current fields needed to match
  Company/Contact/Opportunity; map an allow-listed field/activity/task subset; execute
  approved Action changes; reconcile results. Automatic preparation is permitted;
  external mutation is review-by-default.
- **Architecture:** Extend current Connection/ActionExecutor, idempotency and
  reconciliation contracts; tenant-scoped external bindings; no parallel CRM domain.
- **Security/privacy:** Verified OAuth state, least scopes, secret manager, revoke,
  field allow-list, provider audit, conflict policy, webhook verification if used,
  retention/deletion and incident runbook.
- **Acceptance:** Connect/revoke/match/preview/confirm/execute/reconcile work in a live
  provider sandbox/pilot; duplicate confirmation cannot duplicate a write; recent
  human edits are not silently overwritten; outage leaves Core readable.
- **Out of scope:** Connector matrix, arbitrary object/field ETL, bulk autonomous
  updates, mail/calendar send, native CRM, universal bidirectional sync and provider-
  specific logic in Core services.
- **Validate:** Admin setup time, match precision, proposal acceptance/edit rate,
  administration time avoided, conflict/support burden and provider reliability.

## Checkpoint 1B

Checkpoint 1B is an observed product gate, not a documentation assertion. It decides
whether to proceed, modify, defer or stop WO-026 using:

- real first-interaction completion and time to useful review;
- unaided navigation and mobile task completion;
- Ask usefulness, citation trust and refusal behaviour;
- CRM connection, mapping, update and recovery reliability;
- action edit/approval/rejection patterns and measured admin reduction;
- repeated Daily use and return to source workflows;
- support cost and security/privacy incidents; and
- willingness to keep using Core without an add-on.

## Later Core changes

### WO-036B — Win/Loss Intelligence

Insert after WO-036 Sales Analytics and before WO-037 Targets. Start with a reviewed
deal-level outcome explanation; aggregate only over explicit, sufficient cohorts.
Preserve source references, uncertainty and correction. Do not infer causality or
rank reps.

### WO-042 — CRM connector expansion

Revise WO-042 to build on WO-025C. It owns a second CRM only when incremental reach
justifies it, broader bidirectional mappings, backfill and advanced conflict/
reconciliation. It no longer owns the first production Core CRM path.

### WO-039 — Manager Intelligence and coaching

Keep its position after forecasting. Include evidence-based individual and manager
coaching, but no rep score, peer ranking, covert monitoring or causal performance
claim.

### WO-043 — Deal Rooms

Keep its position. WO-025A/WO-035 improve ordinary Workspace hierarchy and retrieval;
WO-043 owns governed files, versions and extended deal assets after Create/storage
dependencies exist.

## Unchanged conditional sequence

WO-026–045 remain proposed planning units. Checkpoints can modify, defer or remove
them. Forecasting stays WO-038; the first productivity ecosystem remains whichever
of WO-040/041 design-partner evidence supports; every later provider still requires
its own security, privacy and operational release gate.
