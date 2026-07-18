# Product roadmap to beta

**Status:** Proposed sequence, subject to evidence and capacity planning. No future sprint is authorised by this document.

The roadmap preserves one demonstrable outcome per sprint where practical. It takes the current Sprint 1–3 baseline to a narrow design-partner loop before broadening integrations. Sprint numbers express sequence, not committed dates; estimates require team capacity, provider access and design-partner availability.

## Sequencing principles

- Build the meeting domain before ingestion and AI.
- Put verified production identity and administration ahead of customer-content use.
- Make manual upload/transcript paste a complete fallback before provider capture.
- Establish source-backed review before memory or external action.
- Separate proposals/approvals from execution adapters.
- Pilot one productivity ecosystem and one CRM selected from actual partner stacks.
- Add the second ecosystem, second CRM and conferencing breadth after the narrow loop has evidence.
- Apply tenant, consent, deletion, observability and audit gates incrementally; do not defer all security to hardening.

## Completed baseline

### Sprint 1 — Foundation — Complete

- **Objective:** Establish a production-shaped monorepo and secure local foundation.
- **User value:** A truthful, navigable application shell and reliable base for tenant-aware delivery.
- **Major deliverables:** Next.js/FastAPI structure, PostgreSQL/Alembic, auth boundary, request IDs, organisation/user/membership schema, RLS baseline, tests, CI and documentation.
- **Dependencies:** None.
- **Out of scope:** Business entities, meetings, AI, integrations and real Clerk verification.
- **Acceptance criteria:** Recorded in [Sprint 1](../07-sprints/sprint-01-foundation.md).
- **Security gates:** Mock auth blocked in production; secrets/scope scan; initial RLS tests.
- **Demonstration:** Start local services, enter the protected development shell and verify readiness/tenant context.

### Sprint 2 — Core business entities — Complete

- **Objective:** Provide secure tenant-isolated CRUD for companies, contacts, opportunities and tasks.
- **User value:** Users can establish the relationship records future meeting workflows will reference.
- **Major deliverables:** Models/migration, repositories/services, `/api/v1` CRUD, filters/pagination/sorting, responsive list/forms, cross-tenant and RLS tests.
- **Dependencies:** Sprint 1.
- **Out of scope:** Meetings, AI, ingestion, integrations and production Clerk verification.
- **Acceptance criteria:** Recorded in [Sprint 2](../07-sprints/sprint-02-core-business-entities.md).
- **Security gates:** Trusted auth-derived organisation context, explicit predicates, composite tenant FKs and forced RLS.
- **Demonstration:** Create and manage each entity while a cross-tenant request fails closed.

## Meeting intelligence foundation

### Sprint 3 — Meeting Domain Foundation — Complete

- **Objective:** Introduce the non-AI meeting aggregate and lifecycle needed by every later conversation workflow.
- **User value:** Users can create and organise meeting metadata, participants and deliberately supplied plain-text transcripts against the correct company and contacts.
- **Major deliverables:** Meeting, participant, transcript and audit-event models; tenant-safe migration/RLS; CRUD/repository/service/API contracts; responsive list/create/edit/detail UI; optimistic transcript versioning; soft deletion; tests and ADR.
- **Dependencies:** Sprint 2 entities and this blueprint.
- **Out of scope:** Media upload/storage, recording, transcription, AI, provider connections and external actions.
- **Acceptance criteria:** Create/edit/soft-delete a meeting; manage participants and one plain-text transcript; reject cross-tenant/invalid links; preserve content-minimised history; complete loading/empty/error UI.
- **Security gates:** Organisation only from trusted context, active membership check, composite tenant constraints, forced RLS, bounded transcript input and no transcript content in logs/audit.
- **Demonstration:** Create a customer meeting, add participants and authorised transcript text, correct the transcript, then review versioned activity metadata.

WO-003 expanded the earlier proposed Sprint 3 boundary to include direct plain-text transcript CRUD. It did not authorise recording, media ingestion, transcription or AI. Production customer data remains prohibited until production identity and operational privacy controls are complete.

### WO-004A1/A2/B1/B2/B3 — AI Infrastructure Foundation — Complete

- **Objective:** Establish tenant-safe AI persistence, internal domain rules and a durable provider-neutral execution path for deterministic infrastructure tests.
- **Major deliverables:** Exact transcript-version trace, append-only artefacts, forced RLS, tenant-scoped services, idempotency/lifecycle validation, PostgreSQL claim/lease/heartbeat/retry/recovery/cancellation, typed provider contracts, a deterministic no-network mock, bounded provider timeout/error handling, immutable versioned infrastructure prompt/schema registries, safe rendering, strict output parsing/validation/retry and metadata-only telemetry/audits.
- **Out of scope:** External/real providers, credentials, customer-content prompts, APIs, UI, polling and genuine meeting intelligence.
- **Security gates:** Explicit organisation predicates plus forced RLS, narrow tenant scheduling, composite tenant constraints, safe errors, atomic artefact/completion and content-free telemetry/audits.
- **Demonstration:** Concurrent backend workers claim one deterministic infrastructure-test job once, safely render its registered prompt, execute it through the mock provider, reject or retry invalid structured output, persist its typed artefact/zero usage/exact prompt-schema trace, recover expired work and fail cross-tenant operations closed.

These work orders create implementation seams only and do not change the separately proposed product sprint sequence below.

### WO-004C1 — Executive Summary Intelligence Capability — Complete

- **Objective:** Prove the first end-to-end Meeting Intelligence flow using only the current transcript and deterministic mock.
- **Major deliverables:** Executive Summary prompt/schema v1, transcript-bound durable job and append-only artefact, meeting-scoped POST/GET API, accessible Intelligence tab and bounded polling.
- **Out of scope:** Real/external provider, citations/review, Decisions, Action Items, Risks, Open Questions, follow-up, integrations, recording and transcription.
- **Security gates:** Trusted tenant context, forced RLS, exact transcript version, 50,000-character no-truncation limit, prompt-injection-as-data, content-redacted logs/audits and zero external content transfer.
- **Demonstration:** Generate a mock Executive Summary from an authorised transcript, observe queued/running state and retain the completed result on refresh.

This capability validates orchestration and product states, not AI quality. The
following C1A work order adds a real provider adapter only; the later proposed
source-backed intelligence sprint still owns citations, human review and
evaluation gates. Production customer data remains prohibited.

### WO-004C1A — Production OpenAI Provider Integration — Complete

- **Objective:** Add a real server-side provider option to the existing
  Executive Summary flow without changing its API/UI or adding intelligence
  fields.
- **Major deliverables:** Official OpenAI Responses API adapter, strict
  registry-derived JSON Schema, server-only configuration/secrets, safe
  response/error/usage normalisation, configurable mock/OpenAI selection and
  deterministic SDK-fake coverage.
- **Out of scope:** Another intelligence capability, citations/review, provider
  settings UI, tenant credentials, other vendors, recording, transcription,
  integration, billing or agents.
- **Security gates:** Mock remains default; no browser key; content-redacted
  telemetry; durable retry/RLS boundaries preserved; explicit external
  transcript-transmission warning.
- **Demonstration:** With synthetic content and an operator-supplied restricted
  key, run the unchanged Executive Summary journey through an available OpenAI
  model, then roll back to mock.

The adapter is production-shaped but does not authorise production customer
data. Identity, consent, provider privacy/retention, deletion and operational
readiness gates remain outstanding.

### WO-004C2 — Meeting Decisions Intelligence — Complete

- **Objective:** Add the second end-to-end Meeting Intelligence capability using only decisions supported by the current transcript.
- **Major deliverables:** Decisions prompt/schema v1, deterministic populated/empty mock output, explicit OpenAI allowlist extension, transcript-pinned durable job, append-only artefact, POST/GET API, accessible Decisions panel and terminating three-second polling.
- **Out of scope:** Action Items, due dates, Risks, Open Questions, follow-up, CRM changes, memory, recording, transcription, streaming and automation.
- **Security gates:** Trusted tenant context, forced RLS, exact transcript version, no truncation, prompt-injection-as-data, validated-content-only persistence, content-redacted telemetry/audits and explicit OpenAI external-data warning.
- **Demonstration:** Generate Decisions from a synthetic authorised transcript, observe queued/processing then completed cards or a successful empty result, refresh and retain the result.

The capability reuses the existing provider and worker stack and does not
authorise production customer data or any later intelligence output.

### WO-004C3 — Meeting Action Items Intelligence — Complete

- **Objective:** Add the third end-to-end Meeting Intelligence capability using only concrete actions committed in the current transcript.
- **Major deliverables:** Action Items prompt/schema v1, deterministic populated/empty/nullable/relative-date mock output, explicit OpenAI allowlist extension, transcript-pinned durable job, append-only artefact, POST/GET API, accessible Action Items panel and terminating three-second polling.
- **Out of scope:** Risks, Blockers, Open Questions, follow-up email, task creation/editing/completion, reminders, calendar/email/CRM integration, memory, recording, transcription, streaming and automation.
- **Security gates:** Trusted tenant context, forced RLS, exact transcript version, no truncation, prompt-injection-as-data, conservative meeting-date-only normalisation, validated-content-only persistence, content-redacted telemetry/audits and explicit OpenAI external-data warning.
- **Demonstration:** Generate Action Items from a synthetic authorised transcript, observe queued/processing then completed cards or a successful empty result, and retain the result on refresh.

The capability extracts candidates only. It does not create tasks or authorise
production customer data or any later intelligence output.

### WO-004C4 — Meeting Risks & Blockers Intelligence — Complete

- **Objective:** Add the fourth end-to-end Meeting Intelligence capability using only risks and blockers supported by the current transcript.
- **Major deliverables:** Risks & Blockers prompt/schema v1, normalised category/severity, nullable owner, deterministic populated/empty mock output, explicit OpenAI allowlist extension, transcript-pinned durable job, append-only artefact, POST/GET API, accessible panel and terminating three-second polling.
- **Out of scope:** Open Questions, follow-up email, probability, mitigation planning, editing, task creation, CRM changes, deal scoring, memory, recording, transcription, streaming and automation.
- **Security gates:** Trusted tenant context, forced RLS, exact transcript version, no truncation, prompt-injection-as-data, validated-content-only persistence, content-redacted telemetry/audits and explicit OpenAI external-data warning.
- **Demonstration:** Generate Risks & Blockers from a synthetic authorised transcript, observe queued/processing then completed cards or a successful empty result, refresh and retain the result.

The capability is transcript-evidence limited. It does not infer probability,
plan mitigation or authorise production customer data or later intelligence.

### Sprint 4 — Production Identity and Organisation Administration

- **Objective:** Replace the development-only session path with verified Clerk identity/membership and bounded organisation administration.
- **User value:** A design partner can sign in and manage authorised users without unsafe development headers.
- **Major deliverables:** Clerk token verification, membership reconciliation, invitation/removal/role policy, organisation/user administration UI, production fail-closed configuration and auth test fixtures.
- **Dependencies:** Sprint 1 auth port, Clerk tenant configuration and Sprint 3 meeting permissions.
- **Out of scope:** SSO/SCIM, advanced enterprise roles, provider integrations and billing.
- **Acceptance criteria:** Verified user signs in; removed/non-member access fails; role changes take effect; mock mode cannot start in production; no cross-org switching by client ID.
- **Security gates:** Issuer/audience/signature/expiry verification, least-privilege role matrix, recent-auth decision for high-risk actions and audit metadata.
- **Demonstration:** Administrator invites a user, user accesses one organisation, administrator removes them and the next API request is denied.

### Sprint 5 — Secure Manual Media Ingestion

- **Objective:** Accept explicitly supplied media through a durable, consent-aware ingestion lifecycle and formalise consent/provenance for the existing plain-text path.
- **User value:** A user can bring one customer conversation into RevenueOS without waiting for integrations.
- **Major deliverables:** Private storage/quarantine, media flow, consent evidence, source validation, provenance for pasted text, durable database-backed job/worker entrypoint, idempotency, retry/cancel/delete and progress UI.
- **Dependencies:** Sprint 3 meeting aggregate, Sprint 4 production identity, storage/security decisions.
- **Out of scope:** Transcription/model calls, connected capture and meeting intelligence.
- **Acceptance criteria:** Valid source reaches a truthful accepted state; unsafe/oversized/duplicate source is rejected safely; retry is bounded; deletion removes source; API request never performs long work inline.
- **Security gates:** Signed upload/download authorisation, detected type/size/duration checks, quarantine, tenant-scoped jobs/storage, consent record, 30-day raw-audio default and content-free logs.
- **Demonstration:** Upload an authorised sample, observe validated job progress, then delete it and verify it is unavailable.

### Sprint 6 — Transcript Segments and Relationship Matching

- **Objective:** Extend the Sprint 3 plain-text transcript into snapshot/segment review and user-confirmed participant/account matching.
- **User value:** Users can correct the source record before intelligence is generated.
- **Major deliverables:** Transcript snapshot/segment lifecycle, deterministic transcript import path, speaker assignment, candidate matching/external identity foundation, duplicate detection and review UI.
- **Dependencies:** Sprint 5 ingestion and Sprint 2 entities.
- **Out of scope:** Generated summaries, relationship memory, CRM connection and auto-merge.
- **Acceptance criteria:** Review/correct transcript; resolve or leave participant unmatched; confirm same-tenant links; preserve source version/correction; reject ambiguous cross-tenant identity.
- **Security gates:** Source-level access, no fuzzy auto-merge, correction audit metadata, deletion propagation and no raw text in logs.
- **Demonstration:** Correct a speaker segment, match two contacts and keep an ambiguous attendee unresolved.

### Sprint 7 — Source-backed Meeting Intelligence

- **Objective:** Generate structured, cited meeting summary and next-step candidates behind a provider abstraction.
- **User value:** Users review accurate draft intelligence instead of writing notes from scratch.
- **Major deliverables:** Transcription provider if required, production-gated use of the existing structured AI adapter, meeting-intelligence prompt/schema definitions, AI artefacts, citations/confidence, summary/next-step review UI, deterministic mocks, evaluation and cost/latency instrumentation.
- **Dependencies:** Reviewed transcript from Sprint 6 and approved AI/provider privacy posture.
- **Out of scope:** Relationship memory, external actions, assistant and autonomous execution.
- **Acceptance criteria:** Supported source produces schema-valid cited output; unsupported claims fail review gates; user edits/rejects; low-confidence/partial/provider failure is explicit; eval thresholds pass.
- **Security gates:** Prompt-injection tests, minimum context, no implicit tools, provider no-training/retention settings, tenant checks on citations, kill switch and no customer content in logs.
- **Demonstration:** Review a summary, open each material citation, reject one unsupported next step and retain the corrected version.

## Relationship continuity and controlled action

### Sprint 8 — Relationship Timeline

- **Objective:** Show authorised, source-linked relationship events across meetings and core entities.
- **User value:** A seller can reconstruct recent account change without searching several screens.
- **Major deliverables:** Relationship event model, event projection from reviewed meetings/manual records, company/contact/opportunity timelines, filters, source links and correction/deletion propagation.
- **Dependencies:** Sprint 6 source identity and Sprint 7 reviewed artefacts.
- **Out of scope:** AI memory ranking, assistant answers and external event ingestion.
- **Acceptance criteria:** Timeline orders events, identifies source/type, filters correctly, honours source permissions and removes invalidated/deleted content.
- **Security gates:** Per-source authorisation, tenant-scoped projection, restricted-content snippet tests and deletion cascade.
- **Demonstration:** Open a company and trace a commitment from meeting to task through source-linked events.

### Sprint 9 — Relationship Memory and Meeting Preparation

- **Objective:** Preserve concise, correctable source-backed memory and use it in the next meeting brief.
- **User value:** A seller enters the next interaction knowing commitments, preferences, risks and changes.
- **Major deliverables:** Memory item/source lifecycle, conflict/staleness, correction/exclusion/deletion, authorised retrieval and structured pre-meeting brief with citations.
- **Dependencies:** Sprint 8 timeline and Sprint 7 evaluation framework.
- **Out of scope:** Open-ended assistant, vector infrastructure unless evidence proves necessary and autonomous action.
- **Acceptance criteria:** Accepted memory has evidence; correction changes later brief; deleted/excluded source disappears; insufficient evidence is stated; p95 brief target is measured.
- **Security gates:** Retrieval tenant/source tests, sensitive-category policy, provenance integrity and deletion from any index/cache.
- **Demonstration:** Correct a remembered preference and show the corrected, cited version in the next meeting brief.

### Sprint 10 — Approval Centre

- **Objective:** Create one bounded review/approval lifecycle for follow-up, task and CRM proposals without executing external writes.
- **User value:** Users can resolve consequential suggested work from a clear queue.
- **Major deliverables:** Suggested action/approval models, exact-version binding, expiry/revocation, field/content diff UI, task acceptance, follow-up and CRM proposal states, audit events.
- **Dependencies:** Sprint 7 artefacts, Sprint 9 context and agreed role policy.
- **Out of scope:** Email send/draft adapter and CRM write adapter.
- **Acceptance criteria:** Edit invalidates old approval; current eligible user can approve/reject; expired/removed user fails closed; approved proposal is never displayed as executed.
- **Security gates:** Reauthorisation/policy checks, immutable action digest, same-tenant destination validation and content-minimised audit.
- **Demonstration:** Edit and approve selected next steps while a CRM proposal remains accurately “approved, not synced”.

## Narrow pilot integrations

### Sprint 11 — Pilot Calendar Connection

- **Objective:** Connect one productivity ecosystem selected from the first five partners and associate eligible calendar events with meetings.
- **User value:** Upcoming meetings appear for preparation without manual recreation.
- **Major deliverables:** Source connection/capability model, OAuth, Google Calendar **or** Outlook Calendar adapter, webhook/delta recovery, event matching, connection health and revocation.
- **Dependencies:** Sprint 4 identity/admin, Sprint 9 briefs and provider test environment.
- **Out of scope:** Second ecosystem, mailbox access, automatic recording and calendar writes.
- **Acceptance criteria:** Connect/revoke; select calendars; import/update/cancel event; recover missed webhook; private events and unsupported meetings remain safe.
- **Security gates:** Minimum delegated scopes, encrypted tokens, signed webhooks/replay prevention, tenant-scoped cursors and provider deletion/disconnect tests.
- **Demonstration:** A provider event creates/links an upcoming meeting and opens a cited brief.

### Sprint 12 — Pilot Email Draft Delivery

- **Objective:** Create a reviewed follow-up draft—or approved send only if pilot evidence requires it—through the selected ecosystem.
- **User value:** The seller moves an approved follow-up into their real mailbox without copying text.
- **Major deliverables:** Gmail **or** Outlook Mail adapter, recipient validation, approved-content binding, idempotent draft/send command, receipt/reconciliation and failure recovery.
- **Dependencies:** Sprint 10 approvals, Sprint 11 OAuth/capability foundation and provider policy.
- **Out of scope:** Second mail provider, mailbox-wide ingestion, sequences and silent send.
- **Acceptance criteria:** Only exact approved content executes; changed recipient is blocked; ambiguous outcome is reconciled; repeat command cannot duplicate action; disconnect fails safely.
- **Security gates:** Narrow draft/send scopes, no bodies in logs/audit, token isolation, kill switch and explicit provider-side deletion limitations.
- **Demonstration:** Edit and approve a follow-up, create it in the selected mailbox, then view the confirmed receipt.

### Sprint 13 — Pilot CRM Read and Matching

- **Objective:** Connect one CRM selected from Salesforce or HubSpot and resolve authoritative relationship records.
- **User value:** Meeting context uses current CRM identity/fields without duplicate re-entry.
- **Major deliverables:** CRM connection, read-only adapter, field/source mapping, external identities, incremental sync, conflict/duplicate review and CRM snapshot freshness.
- **Dependencies:** Sprint 4 admin, Sprint 6 matching and provider sandbox/access.
- **Out of scope:** CRM writes, second CRM and broad object coverage.
- **Acceptance criteria:** Match supported company/contact/opportunity; preserve CRM authority; handle merge/deletion/rate limit/revocation; ambiguous match requires review.
- **Security gates:** Read-only least privilege, tenant-scoped IDs/cursors, field allowlist, webhook verification and deletion/disconnect tests.
- **Demonstration:** Link a meeting to an authoritative CRM opportunity and show a current field beside source-backed conversation context.

### Sprint 14 — Approved CRM Updates

- **Objective:** Apply selected, source-backed, field-level updates to the pilot CRM after explicit approval.
- **User value:** Sellers update the CRM accurately without retyping, while retaining control.
- **Major deliverables:** Write capability/field allowlist, sync operation lifecycle, optimistic conflict check, idempotency, provider receipt, reconciliation, failure/unknown-outcome recovery and admin kill switch.
- **Dependencies:** Sprint 10 approval centre and Sprint 13 CRM read snapshot.
- **Out of scope:** Silent/bulk writes, second CRM and automatic conflict resolution.
- **Acceptance criteria:** Exact approved diff writes once; stale field blocks; validation/rate-limit/unknown outcome is recoverable; confirmed state reflects provider result.
- **Security gates:** Eligible role, current membership, minimum scopes, audit source/actor/outcome, no blind retry and per-organisation disable control.
- **Demonstration:** Approve one opportunity-field change, reconcile it from the CRM and recover a rejected second change.

## Pilot completeness

### Sprint 15 — Assistant and Search

- **Objective:** Answer account questions and locate relationship evidence within authorised context.
- **User value:** Users find customer context without manually navigating every record.
- **Major deliverables:** Tenant/source-scoped search, account-context assistant, structured cited answers, uncertainty/conflict UI, retrieval evaluation and query/content-safe telemetry.
- **Dependencies:** Sprint 8 timeline, Sprint 9 memory and Sprint 7 AI evaluation.
- **Out of scope:** General web search, cross-organisation questions and action-taking agent tools.
- **Acceptance criteria:** Answers cite accessible sources, admit insufficient evidence, reflect corrections/deletions and pass cross-tenant/prompt-injection evaluation.
- **Security gates:** Retrieval authorisation before ranking/snippets, no implicit tools, sensitive-query redaction and deletion from index.
- **Demonstration:** Ask what a customer committed to, open the evidence and receive “unknown” for an unsupported question.

### Sprint 16 — Notifications and Exception Handling

- **Objective:** Surface only time-sensitive review, approval, sync, connection and commitment exceptions.
- **User value:** Users know what needs attention without monitoring every workflow.
- **Major deliverables:** Notification model/preferences, in-product inbox, content-minimised payloads, deduplication, defer/resolve state and deep links.
- **Dependencies:** Meeting, approval, sync, task and connection states from prior sprints.
- **Out of scope:** Slack, broad push/mobile notifications and activity-volume feeds.
- **Acceptance criteria:** Relevant exception appears once, respects preference/permission, opens a reauthorised destination and resolves with the underlying workflow.
- **Security gates:** No sensitive excerpts, source access rechecked on open, tenant-scoped delivery and removed-user suppression.
- **Demonstration:** A failed CRM sync creates one safe notification that leads to recovery and then resolves.

### Sprint 17 — Operational Observability and Audit

- **Objective:** Give operators and administrators evidence that the narrow loop is healthy, secure and recoverable.
- **User value:** Design partners receive reliable support and accountable records without exposing conversation content.
- **Major deliverables:** Audit model/export, content-safe dashboards/alerts, provider/job/AI cost and latency budgets, incident/restore/deletion runbooks, backup recovery test and support-access policy.
- **Dependencies:** Observable state from Sprints 5–16.
- **Out of scope:** Full enterprise compliance certification and general analytics warehouse.
- **Acceptance criteria:** Trace a request/job/action by safe IDs; alert on defined failures; export audit metadata; complete restore/deletion/credential-revocation game days.
- **Security gates:** Audit access/integrity/retention, log redaction verification, secret rotation, backup encryption and incident response exercise.
- **Demonstration:** Diagnose a failed ingestion and approved sync without viewing raw transcript or email content.

### Sprint 18 — Pilot Onboarding and Hardening

- **Objective:** Make the selected narrow loop repeatable and safe for first-company configuration.
- **User value:** A design partner can onboard with clear expectations and recoverable setup.
- **Major deliverables:** Guided organisation/connector setup, policy/readiness checks, pilot feature flags/kill switches, accessibility/performance fixes, support runbook, data-processing checklist and baseline time-saved instrumentation.
- **Dependencies:** Sprints 3–17 and named design partners/provider configurations.
- **Out of scope:** Second ecosystem/CRM, billing automation and public self-service.
- **Acceptance criteria:** A clean test tenant completes onboarding and the full loop; failure/deletion/offboarding paths pass; product claims match real capabilities.
- **Security gates:** Production readiness checklist in [trust model](../03-engineering/privacy-security-and-trust-model.md), penetration review plan and no production data before sign-off.
- **Demonstration:** Onboard a test organisation from invitation to approved CRM update and next-meeting brief.

### Sprint 19 — First-five Design-partner Pilot

- **Objective:** Operate the narrow Sales Brain loop with exactly five selected companies and validate value/trust assumptions.
- **User value:** Five companies use RevenueOS on real authorised workflows with direct support and clear limits.
- **Major deliverables:** Staged onboarding, per-company configuration review, weekly feedback/time study, incident/quality triage, adoption and correction analysis, go/no-go evidence.
- **Dependencies:** Sprint 18 gates, signed customer/privacy agreements and a shared supported stack or controlled cohorts.
- **Out of scope:** Unplanned integration breadth, public signup, autonomous action and bespoke product forks.
- **Acceptance criteria:** Five companies are onboarded deliberately; each can complete the narrow loop; high-severity security/privacy issues are zero; value/trust metrics and unresolved gaps are documented.
- **Security gates:** Named accountable admin, data inventory, consent policy, connector scopes, retention/deletion test and incident contact for each company.
- **Demonstration:** End-to-end evidence from one authorised meeting through the next-meeting brief, plus aggregate time-saved and correction outcomes across the cohort.

## Private beta expansion

### Sprint 20 — Second Calendar Ecosystem

- **Objective:** Add the calendar provider not selected for the pilot using the proven connection contract.
- **User value:** Both Google Workspace and Microsoft 365 customers can discover meetings for preparation.
- **Major deliverables:** Second OAuth/calendar adapter, delta/webhook recovery, event mapping, admin UX and contract parity.
- **Dependencies:** Sprint 11 contract and pilot evidence.
- **Out of scope:** Second mail provider and deep recording import.
- **Acceptance criteria:** Same connection, update, revocation, rate-limit and deletion behaviours pass for the second provider.
- **Security gates:** Provider-specific scopes/admin consent reviewed; cross-provider identity collisions tested.
- **Demonstration:** The same upcoming-meeting workflow succeeds from the second calendar.

### Sprint 21 — Second Mail Ecosystem

- **Objective:** Add the mail provider not selected for the pilot.
- **User value:** Approved follow-up delivery works for both target productivity ecosystems.
- **Major deliverables:** Second draft/send adapter, approval binding, receipts, reconciliation and provider-specific recovery.
- **Dependencies:** Sprint 12 contract and Sprint 20 OAuth.
- **Out of scope:** Mailbox ingestion, sequences and silent communications.
- **Acceptance criteria:** Contract parity for recipient/content validation, idempotency, ambiguous outcome and revocation.
- **Security gates:** Narrow scopes, tenant/mailbox binding, no body logs and provider deletion limitations.
- **Demonstration:** Create the same approved follow-up through the second mail provider.

### Sprint 22 — Priority Meeting-platform Import

- **Objective:** Add one connected post-meeting artefact import—Zoom, Teams or Meet—selected by pilot demand.
- **User value:** A common meeting source enters the review loop without manual upload.
- **Major deliverables:** Provider adapter, signed webhook/delta discovery, explicit eligibility/consent state, download idempotency and deletion/revocation handling.
- **Dependencies:** Sprint 5 ingestion contract, relevant ecosystem connection and provider API/edition access.
- **Out of scope:** Ambient recording, live bots, meeting control and the other two provider imports.
- **Acceptance criteria:** One authorised completed source imports once, manual fallback remains, revoked/deleted provider artefact is handled honestly.
- **Security gates:** Capture never starts implicitly, source URL/token protection, webhook replay tests and regional policy review.
- **Demonstration:** A selected completed provider meeting appears in the same review queue as manual uploads.

### Sprint 23 — Second CRM Read and Matching

- **Objective:** Add read/match support for the CRM not selected for the pilot.
- **User value:** Both Salesforce and HubSpot customers can ground relationships in their system of record.
- **Major deliverables:** Second read adapter, mappings, external identity, incremental sync and conflict recovery.
- **Dependencies:** Sprint 13 contract and pilot field/matching evidence.
- **Out of scope:** Writes to the second CRM.
- **Acceptance criteria:** Read/match contract parity across supported objects, limits, revocation and deletion.
- **Security gates:** Minimum scopes, per-provider webhook verification and tenant-scoped external IDs.
- **Demonstration:** Match the same relationship workflow against the second CRM.

### Sprint 24 — Second CRM Approved Writes

- **Objective:** Add exact-approved, reconciled writes for the second CRM.
- **User value:** Both target CRM cohorts can complete the approved update loop.
- **Major deliverables:** Field allowlist, provider write adapter, conflict/idempotency/reconciliation and admin kill switch.
- **Dependencies:** Sprint 14 write contract and Sprint 23 reads.
- **Out of scope:** Bulk/silent writes and unsupported CRM objects.
- **Acceptance criteria:** Contract parity for field diff, stale data, provider validation and unknown outcome.
- **Security gates:** Approval digest, current membership/role, minimum write scopes and safe audit.
- **Demonstration:** Apply and reconcile one approved change in the second CRM.

### Sprint 25 — Billing and Entitlements

- **Objective:** Enforce a simple commercially approved private-beta entitlement model if required.
- **User value:** Organisations understand available capabilities and limits without unsafe partial activation.
- **Major deliverables:** Stripe customer/subscription projection, plan entitlements, usage guardrails, admin visibility, webhook idempotency and manual support path.
- **Dependencies:** Confirmed commercial packaging and measured AI/storage/integration costs.
- **Out of scope:** Complex usage billing, annual-contract automation, tax/accounting platform breadth and self-serve plan experimentation.
- **Acceptance criteria:** Entitlement changes follow verified Stripe state; duplicate/out-of-order webhooks are safe; suspended payment never causes data loss.
- **Security gates:** Signed webhooks, no card data in RevenueOS, tenant-scoped customer mapping and least-privilege billing administration.
- **Demonstration:** Change a test subscription and see capability availability update without altering retained customer data.

### Sprint 26 — Private Beta Hardening and Launch

- **Objective:** Open a controlled private beta with documented provider/region support and operational readiness.
- **User value:** Additional approved customers receive a stable, secure and supportable Sales Brain experience.
- **Major deliverables:** Pilot fixes, load/performance/cost tuning, security testing remediation, accessibility review, disaster/incident rehearsal, beta onboarding, support/SLA boundaries and launch documentation.
- **Dependencies:** Pilot evidence, required integration cohort coverage and all production gates.
- **Out of scope:** Public launch, native mobile, ambient capture, Recruitment Brain, Customer Success Brain and remaining meeting/provider breadth.
- **Acceptance criteria:** Release checklist passes; no open critical/high security issue; SLOs/cost ceilings meet target; deletion/export/restore and connector recovery are exercised; beta cohort/capacity is explicit.
- **Security gates:** Independent security review appropriate to risk, privacy/legal sign-off per launch region, dependency/secret scans and tested rollback/kill switches.
- **Demonstration:** Onboard a new beta organisation and complete the supported loop under production monitoring and support procedures.

## Integration coverage at launch stages

| Stage | Calendar/mail | CRM | Meeting source |
| --- | --- | --- | --- |
| Design-partner pilot | One selected ecosystem | One selected CRM | Manual upload/paste; connected source only if safely available |
| Private beta entry | Google and Microsoft calendar/mail | Salesforce and HubSpot read/approved write | Manual fallback plus one priority provider import |
| Later beta increments | Provider-specific improvements | Additional objects/fields by evidence | Remaining Zoom/Teams/Meet imports in focused sprints |

Not every listed integration is a prerequisite for the first pilot or private beta entry. Availability must be labelled by provider, edition, capability and region.

## Roadmap decision gates

- After Sprint 7: is meeting intelligence accurate and fast enough to justify memory work?
- After Sprint 10: do users understand and use approval queues?
- Before Sprint 11: which ecosystem/CRM maximises overlap across exactly five partners?
- After Sprint 14: does the narrow connected loop save measurable time without reducing trust?
- After Sprint 19: continue, narrow or change sequencing based on pilot evidence.
- Before Sprint 25: does commercial policy require automated billing at private-beta entry?

## Next sequencing decision

Sprint 3 is complete. This roadmap currently sequences Sprint 4 as Production Identity and Organisation Administration before production customer-content use. WO-003 identifies technical extension seams for future Meeting Intelligence, but does not authorise that work or resolve a different sprint sequence. A separate approved work order is required before any Sprint 4 implementation begins.

## Related documents

- [Master product blueprint](../01-product/master-product-blueprint.md)
- [MVP and beta scope](mvp-and-beta-scope.md)
- [Target domain model](../03-engineering/target-domain-model.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
- [ADR 0003](../08-decisions/0003-product-blueprint-and-beta-sequencing.md)
