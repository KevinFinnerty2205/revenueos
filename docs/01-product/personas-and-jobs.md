# Personas and jobs

**Scope:** Sales Brain through private beta. Recruitment Brain and Customer Success Brain personas are future context only.

These personas describe roles and jobs rather than permission guarantees. The beta role model is defined in the [privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md#access-controls-and-role-model).

## Sales representative

**Responsibilities**

- Build relationships, qualify needs and progress opportunities.
- Prepare for and conduct customer conversations.
- Follow up on commitments and keep the team's system of record current.

**Pains**

- Context is split across CRM, email, calendar, recordings and personal notes.
- Preparation and administration displace customer-facing time.
- Important nuance, stakeholder concerns and commitments are easily lost.
- Generic summaries require too much checking to become useful.

**Goals**

- Enter every meeting informed, follow up promptly and keep commitments visible.
- Preserve personal credibility while reducing repetitive administration.
- Correct AI output once and see the correction respected later.

**Current tools**

- Salesforce or HubSpot, Google Workspace or Microsoft 365, Zoom/Teams/Meet, notes and messaging.

**Important workflows**

- Meeting preparation, authorised capture, transcript and summary review, task management, follow-up approval, CRM proposal approval and relationship handover.

**Trust concerns**

- Covert recording, inaccurate attribution, fabricated facts, unexpected email or CRM writes, manager surveillance and customer data exposure.

**Expected RevenueOS value**

- A short source-backed briefing, a reviewable post-meeting work queue and correctable memory that reduce searching and re-entry.

**Primary jobs to be done**

- “Before I meet a customer, show me what changed, what I promised and what to ask.”
- “After the meeting, create accurate drafts and proposals that I can verify quickly.”
- “When the AI is wrong, let me correct or exclude the information without losing control.”

## Sales manager

**Responsibilities**

- Coach representatives, inspect deal health, allocate attention and communicate pipeline risk.
- Ensure next steps and customer commitments are owned.

**Pains**

- Pipeline fields lag reality and inspection meetings become data-cleaning sessions.
- Deal context depends on second-hand summaries.
- Activity volume can obscure relationship quality and actual blockers.

**Goals**

- Identify exceptions early, coach from evidence and spend less time reconstructing accounts.
- Support sellers without turning conversation intelligence into opaque surveillance.

**Current tools**

- CRM dashboards, forecast tools, call-recording platforms, spreadsheets and team meetings.

**Important workflows**

- Pipeline review, stalled-deal triage, coaching, ownership handover and approval escalation.

**Trust concerns**

- Unsupported risk scoring, decontextualised quotations, overbroad access, individual ranking and false certainty.

**Expected RevenueOS value**

- An exception-led view of changed commitments, inactivity, unresolved risk and low-confidence evidence with links to source context.

**Primary jobs to be done**

- “Show me which relationships need attention and the evidence behind that judgement.”
- “Help me prepare a useful coaching conversation without replacing human judgement.”
- “Show whether approved follow-ups and next steps were completed.”

## Revenue operations leader

**Responsibilities**

- Own revenue process, CRM quality, tool governance, reporting definitions and change adoption.
- Coordinate sales, finance, security and IT stakeholders.

**Pains**

- Seller adoption falls when data-entry burden rises.
- Integrations create duplicate, stale or conflicting records.
- Automation can improve completeness while making provenance and accountability worse.

**Goals**

- Improve trustworthy data quality with less manual effort.
- Roll out repeatable workflows, measurable value and recoverable integrations.
- Retain explicit control over fields, mappings, approval policy and retention.

**Current tools**

- CRM administration, integration platforms, BI, data quality tools, identity systems and support queues.

**Important workflows**

- Connection rollout, field mapping, approval policy, sync exception review, adoption measurement, audit and data lifecycle management.

**Trust concerns**

- Silent writes, untraceable transformations, non-idempotent sync, excessive scopes, weak tenant isolation and misleading success states.

**Expected RevenueOS value**

- Source-backed CRM proposals, execution receipts, connection health and exception queues that improve records without hiding failure.

**Primary jobs to be done**

- “Let me define what RevenueOS may read, propose and write.”
- “Show the source, approver and outcome for every change.”
- “Help me prove value and data quality without monitoring raw customer content.”

## System administrator

**Responsibilities**

- Configure identity, memberships, integrations, security controls, retention and support access.
- Investigate access or connection incidents and support user lifecycle changes.

**Pains**

- OAuth scopes and webhook behaviour are hard to assess.
- Removal, revocation and deletion behaviour varies by provider.
- Production incidents can require visibility without granting blanket content access.

**Goals**

- Deploy with least privilege, clear ownership and reliable offboarding.
- Understand connection health, audit events, retention and regional data handling.
- Fail closed when identity, membership or tenant context is uncertain.

**Current tools**

- Clerk or identity administration, provider admin consoles, secret managers, logs, audit tools and ticketing systems.

**Important workflows**

- Organisation setup, membership and role changes, connector authorisation, retention policy, export/deletion, incident response and credential rotation.

**Trust concerns**

- Service-role key exposure, bypassed row-level security, raw content in logs, overbroad support access, incomplete deletion and unrecorded impersonation.

**Expected RevenueOS value**

- A clear control plane for access, connection scopes, retention, audit evidence and recoverable configuration.

**Primary jobs to be done**

- “Let me enable only the capabilities the organisation has approved.”
- “When access changes, revoke it everywhere and prove what happened.”
- “When something fails, give me metadata-rich diagnostics without exposing customer content.”

## Cross-persona tensions

- Representatives need private preparation and correction; managers need evidence-led visibility. Beta policy must avoid default access to every raw transcript.
- Revenue operations needs consistent fields; representatives need fast review. Proposals should be concise, editable and policy-aware.
- Administrators need diagnostics; customers need content minimisation. Operational metadata should normally be sufficient.
- Managers may want automatic scores; trust requires explainable signals and human judgement. Individual performance scoring is not beta scope.

## Future personas

### Recruitment Brain — later

Recruiters, hiring managers and recruitment operations have analogous conversation, memory and approval needs, but candidate consent, employment decision risk, JobAdder workflows and retention rules require a separate product definition. They are not beta users for Sales Brain.

### Customer Success Brain — future

Customer success managers, team leaders and operations roles may use relationship memory for onboarding, adoption, renewals and expansion. Product-specific health models and customer-success integrations are future work, not abstractions to build during the Sales Brain beta.

## Related documents

- [Master product blueprint](master-product-blueprint.md)
- [User journeys](user-journeys.md)
- [Information architecture](../02-design/information-architecture.md)
- [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md)
