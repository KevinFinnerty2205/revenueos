# Integration strategy

**Status:** Target strategy; no production integration is implemented today. Deterministic mocks are test infrastructure, not connected capability.

RevenueOS integrates as an intelligence and workflow layer while the connected provider remains authoritative. The first five design partners use one selected productivity ecosystem and one selected CRM; breadth follows demonstrated need. CRM updates and external communications require explicit user approval throughout beta.

## Integration contract

Every real adapter must provide:

- a declared capability set separating read, propose, draft, send and write;
- least-privilege OAuth scopes and an administrator-readable explanation;
- tenant-scoped credentials, cursors, external identities and idempotency keys;
- webhook verification and replay protection where webhooks exist;
- bounded polling only when webhooks cannot provide reliable coverage;
- typed rate-limit, authentication, validation, conflict, transient and unknown-outcome failures;
- reconciliation before retrying an operation that might have succeeded;
- connection health, revocation and deletion workflows;
- contract tests against deterministic mocks and safe provider test accounts; and
- an honest UI that never calls a proposed, mocked or failed operation “synced”.

Provider details must remain in adapters behind domain ports. Domain services own authorisation, source-of-truth rules, approval and state transitions.

## Beta-priority productivity integrations

### Google Calendar

- **User value:** Discover selected upcoming/completed meetings, attendees and context for preparation and ingestion.
- **Data flow:** Provider → RevenueOS for selected event metadata and change notifications; no RevenueOS event writes in pilot.
- **Read/write:** Read minimum calendar/event fields; calendar write is not beta-required.
- **Source of truth:** Google Calendar for event time, title, attendees and event state; RevenueOS for matching/review state.
- **Approval:** User/admin selects calendars and eligible events; adding/changing calendar events would require a separate future approval.
- **Authentication:** Google OAuth with offline access only where required; domain-wide delegation is not a default.
- **Webhook/polling:** Google watch channels plus bounded incremental sync for recovery; renew channels before expiry.
- **Rate limits:** Per-user/organisation budgeting, incremental sync tokens, backoff and `Retry-After`.
- **Error recovery:** Reauthorise on revoked grant, recreate expired channel, handle invalid sync token with bounded resync.
- **Data deletion:** Revoke token, remove connection/cursors and delete cached event data not retained as an independently authorised source.
- **Rollout:** Sprint 11 if Google is the pilot ecosystem; otherwise second-ecosystem Sprint 20.

### Microsoft Outlook Calendar

- **User value:** The Microsoft 365 equivalent of selected meeting discovery and preparation.
- **Data flow:** Microsoft Graph → RevenueOS for selected calendar/event metadata.
- **Read/write:** Delegated read scopes initially; no beta requirement to write calendar events.
- **Source of truth:** Outlook for event fields; RevenueOS for relationship matching and review state.
- **Approval:** User/admin selects account/calendars and ingestion policy.
- **Authentication:** Microsoft identity platform OAuth; delegated permissions first, administrator consent only where necessary.
- **Webhook/polling:** Graph subscriptions plus delta queries for recovery and expiry renewal.
- **Rate limits:** Respect Graph throttling headers, distribute subscription renewal and avoid tenant-wide scans.
- **Error recovery:** Delta reset, subscription recreation and explicit reauthorisation state.
- **Data deletion:** Revoke/remove credential and delete cursors/cached events according to source/deletion policy.
- **Rollout:** Sprint 11 if Microsoft is the pilot ecosystem; otherwise Sprint 20.

### Gmail

- **User value:** Create an approved follow-up in the user's mailbox and confirm delivery state where sending is enabled.
- **Data flow:** RevenueOS → Gmail for one approved draft/send; minimal provider status → RevenueOS. No historic mailbox ingestion by default.
- **Read/write:** Begin with draft creation if it satisfies pilot workflow; enable send only after explicit approval/reconciliation is proven.
- **Source of truth:** Gmail for message/draft/delivery identifiers; RevenueOS for source-backed draft version and approval.
- **Approval:** Exact recipients, subject and body version require user approval; material edits invalidate approval.
- **Authentication:** Google OAuth with the narrowest draft/send scope for enabled capability; calendar and mail grants remain understandable.
- **Webhook/polling:** Direct command plus response; Gmail history/watch only if needed to reconcile status, not to ingest the mailbox.
- **Rate limits:** Per-user quotas, idempotency guard and no blind send retry.
- **Error recovery:** Revalidate recipients, reconcile unknown outcome by provider identifier, then require user attention if uncertain.
- **Data deletion:** Delete RevenueOS copy per policy; user controls provider-side message/draft, with limitations stated clearly; revoke tokens on disconnect.
- **Rollout:** Sprint 12 for a Google pilot; otherwise second-mail Sprint 21.

### Microsoft Outlook Mail

- **User value:** Create or send a reviewed follow-up through the user's Microsoft 365 mailbox.
- **Data flow:** RevenueOS → Microsoft Graph for one approved draft/send; minimal outcome metadata returns.
- **Read/write:** Narrow mail draft/send capability; no mailbox-wide read in beta unless a separately defined workflow requires it.
- **Source of truth:** Outlook for message/delivery state; RevenueOS for approved content/provenance.
- **Approval:** Bound to recipients, content version, mailbox and expiry.
- **Authentication:** Delegated Microsoft OAuth; avoid application-wide mailbox permission for the user workflow.
- **Webhook/polling:** Direct Graph commands and bounded reconciliation; subscriptions only when a product requirement justifies them.
- **Rate limits:** Respect Graph throttling and prevent duplicate send on retry.
- **Error recovery:** Reauthorise, resolve policy rejection and reconcile ambiguous response before another attempt.
- **Data deletion:** Remove RevenueOS content/metadata according to policy; explain that deleting a sent external email requires provider-side action and may not be possible.
- **Rollout:** Sprint 12 for a Microsoft pilot; otherwise Sprint 21.

### Google Meet

- **User value:** Associate eligible Meet sessions and available authorised artefacts with calendar meetings.
- **Data flow:** Google Calendar/Meet → RevenueOS for meeting identity and explicitly selected available artefact.
- **Read/write:** Read/import only; RevenueOS does not start recording or control meetings in beta.
- **Source of truth:** Google for meeting/recording availability; RevenueOS for ingestion and review state.
- **Approval:** User explicitly selects/imports or an administrator enables a clear post-meeting eligibility rule with user-visible state.
- **Authentication:** Google OAuth scopes added only after API availability and account-entitlement testing.
- **Webhook/polling:** Calendar event notifications plus bounded artefact discovery where supported.
- **Rate limits:** Reuse event identities, incremental checks and provider quotas.
- **Error recovery:** Fall back to manual upload/paste; distinguish unavailable artefact from processing failure.
- **Data deletion:** Remove imported source and derived data in RevenueOS; provider original remains governed in Google and is identified as such.
- **Rollout:** Calendar association arrives with the Google calendar sprint (11 or 20); artefact import is Sprint 22 only if Meet is the priority provider, otherwise a later focused beta increment. Exact API/edition feasibility remains to validate.

### Microsoft Teams

- **User value:** Associate Teams meetings and explicitly available artefacts with Outlook events.
- **Data flow:** Microsoft Graph/Teams → RevenueOS for meeting identity and authorised recording/transcript import.
- **Read/write:** Read/import only; no meeting control or implicit recording.
- **Source of truth:** Microsoft 365 for meeting and artefact availability; RevenueOS for review and memory.
- **Approval:** Visible connection policy and explicit eligible-source selection; no background capture.
- **Authentication:** Delegated Graph permissions first; admin-consent requirements and meeting policy must be validated.
- **Webhook/polling:** Graph subscriptions/delta where supported, bounded discovery otherwise.
- **Rate limits:** Coordinate with Outlook quotas/subscriptions and use durable backoff.
- **Error recovery:** Manual source fallback, reauthorisation and clear unsupported-policy state.
- **Data deletion:** RevenueOS deletion does not claim to delete the Microsoft original; revoke access and remove cached/derived content per policy.
- **Rollout:** Calendar association arrives with the Outlook calendar sprint (11 or 20); artefact import is Sprint 22 only if Teams is the priority provider, otherwise a later focused beta increment. Exact recording/transcript permissions are unresolved.

### Zoom

- **User value:** Import an explicitly authorised cloud recording or transcript after a customer meeting.
- **Data flow:** Zoom → RevenueOS for selected meeting metadata and artefacts; processing status remains in RevenueOS.
- **Read/write:** Read/import only; no meeting scheduling or recording control in beta.
- **Source of truth:** Zoom for cloud artefact availability; RevenueOS for the imported source lifecycle and review.
- **Approval:** Administrator connects the account; user selects or policy-enables eligible completed meetings with visible consent responsibility.
- **Authentication:** Zoom OAuth/server-to-server choice must follow account ownership and least privilege; never expose credentials client-side.
- **Webhook/polling:** Signed recording-completed/deleted webhooks, with bounded reconciliation for missed delivery.
- **Rate limits:** Durable queue, provider limit headers and artefact deduplication.
- **Error recovery:** Verify signature/replay, retry download within URL expiry, request reauthorisation or use manual upload.
- **Data deletion:** Delete RevenueOS copy/derivatives; handle provider deletion webhook; do not imply deletion of Zoom original unless an authorised delete capability exists.
- **Rollout:** Sprint 22 only if Zoom is the priority provider; otherwise a later focused beta increment. It is not required for the first pilot.

## Beta-priority CRM integrations

### Salesforce

- **User value:** Match authoritative accounts/contacts/opportunities, show current fields and apply selected approved changes.
- **Data flow:** Salesforce → RevenueOS for scoped records/snapshots; RevenueOS → Salesforce only for approved field-level updates.
- **Read/write:** Start read-only; enable a field allowlist for write after mapping, idempotency and conflict tests pass.
- **Source of truth:** Salesforce for mapped CRM fields; RevenueOS for evidence, proposals, approvals and execution status.
- **Approval:** Every write is a visible field diff approved by an eligible user during beta.
- **Authentication:** OAuth connected app with minimum object/field access; customer security policies and token rotation supported.
- **Webhook/polling:** Change Data Capture/platform events where available plus bounded incremental reconciliation; do not assume universal event coverage.
- **Rate limits:** Track organisation API allocation, use incremental queries and back off before exhaustion.
- **Error recovery:** Handle validation rules, field-level security, record version conflict, partial batch outcome and unknown result explicitly.
- **Data deletion:** Remove tokens, mappings, cursors and cached records; RevenueOS deletion cannot silently delete authoritative Salesforce records.
- **Rollout:** Sprints 13–14 if chosen for the pilot; otherwise second-CRM read/write Sprints 23–24.

### HubSpot

- **User value:** Match CRM companies/contacts/deals, display authoritative context and apply approved updates.
- **Data flow:** HubSpot → RevenueOS for scoped objects; approved RevenueOS changes → HubSpot.
- **Read/write:** Read first; write only allowlisted properties after review.
- **Source of truth:** HubSpot for mapped CRM properties; RevenueOS for conversational evidence and proposal lifecycle.
- **Approval:** Every beta write is approved at field level; no bulk silent synchronisation.
- **Authentication:** HubSpot OAuth/private-app choice must preserve per-customer least privilege; OAuth is preferred for repeatable SaaS rollout.
- **Webhook/polling:** Verified webhooks where supported plus cursor-based incremental reconciliation.
- **Rate limits:** Per-app/account limit budgeting, batching that preserves per-record outcomes and `Retry-After`.
- **Error recovery:** Property validation, archived object, merge/duplicate, conflict and partial result are typed and reviewable.
- **Data deletion:** Revoke token and remove mappings/cached data; disclose provider-side retention and authoritative-record behaviour.
- **Rollout:** Sprints 13–14 if chosen for the pilot; otherwise Sprints 23–24.

## Later integrations

### Phone providers — Later

- **User value:** Bring explicitly authorised sales-call evidence into the meeting loop.
- **Data flow/read-write:** Provider recording/transcript → RevenueOS only; no background call control.
- **Source of truth/approval:** Provider owns call artefact; user must deliberately select or visibly arm capture under organisation and regional policy.
- **Authentication/transport:** Provider-specific OAuth and signed webhooks where available; polling only as bounded recovery.
- **Limits/recovery/deletion:** Enforce duration/format limits, fall back to manual upload, delete imported/derived data independently and never claim deletion of provider originals.
- **Rollout:** Later, one provider selected through customer evidence and legal/privacy review.

### JobAdder — Later (Recruitment Brain)

- **User value:** Candidate/client context and approved workflow updates for recruiters.
- **Data flow/read-write:** Read authoritative recruitment records; future writes require explicit review and product-specific policy.
- **Source of truth/approval:** JobAdder remains authoritative; employment-related recommendations require stricter safety review.
- **Authentication/transport:** OAuth/API capability, webhook availability and rate limits must be validated before planning.
- **Limits/recovery/deletion:** Typed field/match errors, no mock success, and candidate privacy/retention controls.
- **Rollout:** Recruitment Brain discovery, not Sales Brain beta.

### Slack — Later

- **User value:** Content-minimised exception notifications or explicitly requested collaboration context.
- **Data flow/read-write:** RevenueOS → Slack notifications first; broad workspace ingestion is not planned.
- **Source of truth/approval:** RevenueOS owns workflow state; user/admin approves workspace/channel and message category.
- **Authentication/transport:** Slack OAuth and signed interaction/event verification; minimal scopes.
- **Limits/recovery/deletion:** Rate-limited delivery, deduplication, revocation handling and honest provider-message deletion limitations.
- **Rollout:** Later, after in-product notifications prove which events matter.

### Customer success platforms — Future

- **User value:** Bring relationship memory into onboarding, adoption, renewal and expansion workflows.
- **Data flow/read-write:** Product-specific and not yet defined; start read-only.
- **Source of truth/approval:** The customer success platform stays authoritative; writes/communications require explicit control.
- **Authentication/transport:** Replaceable OAuth adapters with webhooks/polling selected per provider.
- **Limits/recovery/deletion:** Same tenant, idempotency, reconciliation and deletion contract as CRM adapters.
- **Rollout:** Customer Success Brain discovery, not Sales Brain beta.

## Rollout gates for every provider

1. Product workflow and minimum scopes are documented.
2. Security, privacy, data processing and regional requirements are approved.
3. Real sandbox/test-account adapter passes contract, tenant, webhook, rate-limit, deletion and unknown-outcome tests.
4. Administrator and end-user consent/approval UX is complete.
5. Operational dashboards, alerts, kill switch, reauthorisation and support runbook exist.
6. Limited design-partner rollout demonstrates value and safe recovery.
7. Capability is labelled available only for supported plans, regions and provider editions.

## Unresolved decisions

- Which productivity ecosystem and CRM are shared by enough of the first five companies to be the pilot adapters?
- Whether draft creation alone is sufficient for pilot email value or approved sending is required.
- Provider API/edition access for Meet and Teams recording/transcript artefacts.
- Field allowlists and conflict policy for each CRM.
- Whether customer administrators require central connections or user-delegated connections for each provider.

## Related documents

- [Core workflows](../02-design/core-workflows.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
