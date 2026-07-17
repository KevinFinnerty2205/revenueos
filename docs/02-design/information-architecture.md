# Information architecture

**Design intent:** RevenueOS is a relationship intelligence and workflow product, not a replacement CRM. Navigation should foreground recent movement, evidence, memory, next actions and exceptions requiring attention. Dense record maintenance remains in the connected system of record.

**Status legend:** **Current** exists now; **Pilot** is required for the first five companies; **Beta** is required for private beta; **Later** is deferred.

## Navigation model

### Primary navigation

1. Dashboard
2. Companies
3. Contacts
4. Opportunities
5. Meetings
6. Tasks
7. Assistant

### Global utilities

- Search
- Notifications
- Organisation switcher, where a verified user has multiple memberships
- User menu and Settings

### Settings navigation

- Personal preferences
- Integrations
- Organisation
- Users and permissions
- Privacy, retention and audit
- Billing and entitlements, when enabled

On small screens, use a compact menu and preserve direct access to Dashboard, Meetings, Tasks and Search. Responsive web is the beta surface; native mobile is later.

## Screens

### Dashboard — Current shell; Pilot intelligence surface

- **Purpose:** Answer “What needs my attention now?” without recreating a CRM dashboard.
- **Primary actions:** Open an upcoming brief, review a completed meeting, resolve an approval/exception or open an overdue commitment.
- **Main information:** Upcoming meetings, recent relationship movement, review queue, approvals, tasks and integration exceptions; no opaque activity score.
- **Empty state:** Explain the narrow meeting loop and offer manual ingestion or the next configured connection.
- **Loading state:** Stable skeletons per section; independent sections do not block the whole page.
- **Error state:** Preserve available sections and show a safe, retryable error for the failed source.
- **Permissions:** Personal work by default; managers see policy-approved team exceptions, not unrestricted raw content.
- **Mobile:** One-column priority feed with large touch targets and no wide pipeline table.
- **Beta status:** Pilot; the current dashboard is an honest placeholder summary.

### Companies — Current CRUD; Pilot relationship index

- **Purpose:** Find company relationships and understand recency, unresolved work and confidence.
- **Primary actions:** Search/filter, open company, create/edit current foundation fields and start a contextual question.
- **Main information:** Company identity, relationship recency, open commitments, active opportunities, last meaningful event and exceptions.
- **Empty state:** Create a company or connect/import from a supported CRM when available.
- **Loading state:** List skeleton with filters usable once metadata is ready.
- **Error state:** Safe error with retry; never fall back to another tenant or stale unauthorised data.
- **Permissions:** Organisation members currently have equal CRUD; finer beta policies are an explicit roadmap item.
- **Mobile:** Cards prioritise name, recency and next action; editing stays concise.
- **Beta status:** Current foundation, enriched during Pilot.

### Company detail — Pilot

- **Purpose:** Provide a relationship workspace centred on change over time.
- **Primary actions:** Prepare a brief, inspect timeline/memory, resolve tasks, review meetings, ask the assistant and propose/correct linked records.
- **Main information:** Relationship summary, stakeholders, opportunities, recent events, confirmed memory, commitments, risks, source conflicts and next meeting.
- **Empty state:** Explain which sources can build context; permit manual records without inventing intelligence.
- **Loading state:** Identity header first, then independently loaded timeline, memory and work panels.
- **Error state:** Label unavailable panels and retain actions that are still safe.
- **Permissions:** Source-level access is enforced; a summary must not reveal a restricted transcript.
- **Mobile:** Overview and next action first; timeline as a continuous feed; secondary panels collapse.
- **Beta status:** Pilot.

### Contacts — Current CRUD; Pilot relationship index

- **Purpose:** Find people and their company context without becoming a prospecting database.
- **Primary actions:** Search/filter, create/edit, open contact and resolve identity matches.
- **Main information:** Name, role, company, owner, last interaction, open commitment and identity confidence.
- **Empty state:** Create a contact or resolve contacts from an authorised source.
- **Loading state:** List skeleton; filters retain their values.
- **Error state:** Safe retry and connection status where relevant.
- **Permissions:** Tenant scope plus future source restrictions; no enrichment outside explicit later scope.
- **Mobile:** Compact identity cards with company, role and next action.
- **Beta status:** Current foundation, enriched during Pilot.

### Contact detail — Pilot

- **Purpose:** Preserve person-specific context, preferences, commitments and source history.
- **Primary actions:** Review timeline/memory, correct identity or memory, open linked company/opportunities and prepare interaction context.
- **Main information:** Confirmed identity, roles, relationship signals, meetings, commitments, preferences and provenance.
- **Empty state:** Show current contact data and explain that no authorised interaction evidence exists.
- **Loading state:** Identity first; relationship panels progressively load.
- **Error state:** Isolate source failures and avoid merging uncertain identities.
- **Permissions:** Respect transcript/source visibility and sensitive-information exclusions.
- **Mobile:** Identity, next commitment and latest events lead; editing is a separate focused view.
- **Beta status:** Pilot.

### Opportunities — Current CRUD; Beta exception view

- **Purpose:** Surface opportunity movement and exceptions, not duplicate full CRM pipeline administration.
- **Primary actions:** Filter, open opportunity, review evidence, resolve overdue action and edit foundation fields.
- **Main information:** Stage/value from current records or CRM, recent relationship change, unresolved risk, next step, recency and sync state.
- **Empty state:** Create an opportunity or connect an authoritative CRM.
- **Loading state:** Summary placeholders retain filter layout.
- **Error state:** Distinguish RevenueOS failure from a stale or unavailable CRM.
- **Permissions:** Role and team visibility must be configured before beta; external field writes require approval.
- **Mobile:** Exception cards rather than horizontal pipeline grids.
- **Beta status:** Current CRUD; evidence-led exception experience in Beta.

### Opportunity detail — Beta

- **Purpose:** Explain why an opportunity changed and what human action is needed.
- **Primary actions:** Open evidence, prepare meeting, review risks/commitments, approve CRM proposal and manage tasks.
- **Main information:** Authoritative fields, relationship timeline, stakeholders, meeting intelligence, open commitments, source-backed risks and sync history.
- **Empty state:** Show authoritative record and ask for the next useful evidence source.
- **Loading state:** CRM snapshot and RevenueOS context load independently with freshness labels.
- **Error state:** Keep last-known data explicitly timestamped and disable unsafe write actions.
- **Permissions:** Field and transcript access may differ; approvals require eligible role and current membership.
- **Mobile:** Summary, next step and exceptions first; field diffs open in a focused approval view.
- **Beta status:** Beta.

### Meetings — Pilot

- **Purpose:** Manage explicitly supplied conversations through ingestion, review and completion.
- **Primary actions:** Upload recording, paste transcript, connect eligible source, filter by state and resume review.
- **Main information:** Meeting time/title, participants/account, source, processing/review state, confidence, owner and retention state.
- **Empty state:** Explain consent and offer manual upload or transcript paste.
- **Loading state:** Rows/cards show stable state placeholders and background progress separately.
- **Error state:** Give safe stage-specific recovery without exposing raw content in diagnostics.
- **Permissions:** Only authorised users may ingest or view sources; meeting visibility does not imply transcript visibility.
- **Mobile:** Status cards and review queue; large uploads warn about connection constraints.
- **Beta status:** Pilot.

### Meeting detail — Pilot

- **Purpose:** Provide one review surface for source, transcript, intelligence, memory candidates and proposed actions.
- **Primary actions:** Correct participants/transcript, approve or reject artefacts, edit drafts, delete/exclude source and retry failures.
- **Main information:** Provenance, consent evidence, processing state, transcript, citations, summary, next steps, follow-up, CRM proposal, memory candidates and audit status.
- **Empty state:** State which stage is waiting and the action needed; never show fabricated placeholder intelligence.
- **Loading state:** Stage timeline and deterministic progress; previously completed stages remain usable.
- **Error state:** Partial results are clearly labelled; recovery options are bounded and idempotent.
- **Permissions:** Consequential approvals require current membership and policy; raw source access is independently checked.
- **Mobile:** Review is sequential by section; transcript/source comparison is limited but usable.
- **Beta status:** Pilot.

### Tasks — Current CRUD; Pilot suggested-task review

- **Purpose:** Track human-owned commitments and next actions tied to relationship context.
- **Primary actions:** Create/edit/assign/complete, filter by due state and accept/reject a suggestion.
- **Main information:** Title, owner, due time, priority/status, linked records and source evidence where present.
- **Empty state:** Create a task; meeting-derived suggestions appear only after review.
- **Loading state:** Preserve filters with list skeleton.
- **Error state:** Inline save error plus safe retry; no optimistic success after failure.
- **Permissions:** Assignees and linked records must be same-tenant; assignment policy is a beta administration decision.
- **Mobile:** Today/overdue first with quick status updates and accessible controls.
- **Beta status:** Current manual CRUD; suggestions in Pilot.

### Assistant — Beta

- **Purpose:** Answer relationship questions from authorised, cited evidence.
- **Primary actions:** Ask, refine context, open citations, report/correct answer and create a separately reviewed proposal.
- **Main information:** Answer, uncertainty, sources, context boundary and data freshness.
- **Empty state:** Example relationship questions and a clear explanation of available evidence.
- **Loading state:** Cancelable progress with no fake streaming conclusion.
- **Error state:** Say whether evidence, retrieval or generation failed and allow safe retry.
- **Permissions:** Retrieval cannot exceed source access; no implicit tools, writes or sends.
- **Mobile:** Single-column conversation with citation drawer.
- **Beta status:** Beta, after source-backed memory and search.

### Search — Beta

- **Purpose:** Find authorised people, companies, opportunities, meetings, events and memory from one entry point.
- **Primary actions:** Query, filter by entity/source/time, open result and report a mismatch.
- **Main information:** Ranked result, entity context, source type, recency and matching excerpt with sensitive minimisation.
- **Empty state:** Suggest narrower terms and disclose unavailable source categories.
- **Loading state:** Immediate local navigation results, then bounded evidence results.
- **Error state:** Preserve query and filters; distinguish partial index unavailability.
- **Permissions:** Search is not an access bypass; indexes and result snippets are tenant- and source-scoped.
- **Mobile:** Full-screen search with filter sheet and concise results.
- **Beta status:** Beta.

### Notifications — Beta

- **Purpose:** Surface time-sensitive exceptions without creating an activity feed of everything.
- **Primary actions:** Open item, mark read, defer, configure category and resolve the underlying workflow.
- **Main information:** Review ready, approval required, failed sync, expiring connection, overdue commitment and upcoming brief.
- **Empty state:** Confirm that there are no current exceptions and link to preferences.
- **Loading state:** Compact list skeleton; unread count remains conservative.
- **Error state:** Do not clear unread state; provide retry.
- **Permissions:** Content-minimised payloads; destination access is checked again when opened.
- **Mobile:** High-value categories only; deep links to the relevant workflow.
- **Beta status:** Beta.

### Settings — Beta

- **Purpose:** Manage personal preferences and discover organisation controls available to the user's role.
- **Primary actions:** Change locale/timezone, notification preferences, privacy defaults and open integration/organisation controls.
- **Main information:** Effective organisation, role, policy summaries and linked control areas.
- **Empty state:** Defaults explained; unavailable settings show their owner rather than disappearing ambiguously.
- **Loading state:** Section-level skeletons and disabled save until current values are known.
- **Error state:** Preserve unsaved edits and show field-level or connection-safe failure.
- **Permissions:** Personal and organisation settings are visibly separated.
- **Mobile:** Focused sections; destructive actions require explicit confirmation.
- **Beta status:** Beta.

### Integrations — Pilot foundation; Beta provider catalogue

- **Purpose:** Configure and monitor source connections and permitted actions.
- **Primary actions:** Connect, choose scopes, configure mappings, test, pause, reauthorise and delete.
- **Main information:** Provider, owner, granted capabilities, health, last sync, errors, policy and deletion state.
- **Empty state:** Recommend only the next integration needed for the narrow loop.
- **Loading state:** Provider catalogue and organisation connections load independently.
- **Error state:** Show actionable OAuth/scope/rate-limit/revocation state without revealing tokens.
- **Permissions:** Organisation administrators connect shared systems; personal connections and delegated admin consent remain distinct.
- **Mobile:** Health and reauthorisation usable; complex mapping is desktop-first.
- **Beta status:** One mail/calendar ecosystem and CRM for Pilot; phased provider catalogue in Beta.

### Organisation and user management — Beta

- **Purpose:** Govern membership, roles, access policy, retention and auditable administrative changes.
- **Primary actions:** Invite/remove user, change role, review effective access, configure policy and initiate export/deletion.
- **Main information:** Members, role, status, last authentication metadata, connection ownership, policy and audit events.
- **Empty state:** Guide the first administrator to invite a second accountable owner.
- **Loading state:** Member list and policy controls remain disabled until authoritative values load.
- **Error state:** Fail closed; do not show success until Clerk and application membership agree.
- **Permissions:** Administrator only for organisation-wide changes; high-risk actions require reauthentication and future step-up policy.
- **Mobile:** Membership review and urgent revocation supported; policy authoring is desktop-first.
- **Beta status:** Beta and a production-readiness gate.

## Cross-screen interaction rules

- Every AI claim links to a source or says that sufficient evidence is unavailable.
- Confidence affects presentation and review priority, never access control.
- Approval views show actor, destination, exact content/version, field-level changes and expiry.
- An external action is successful only after a confirmed provider receipt or reconciliation.
- Empty states describe what exists today; they do not market unimplemented features as active.
- Restricted and deleted content must not leak through counts, search snippets, notifications or derived summaries.
- Australian English, WCAG-aligned semantics, keyboard operation and complete loading/empty/error states are baseline requirements.

## Related documents

- [Design principles](design-principles.md)
- [Core workflows](core-workflows.md)
- [User journeys](../01-product/user-journeys.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
