# Privacy, security and trust model

**Status:** Target controls through private beta. The [current security baseline](security-and-privacy.md) remains the truthful description of implemented controls.

No production customer data should be used until the production readiness gates in this document are met. Current mock authentication is development/test-only and must never protect a public or production deployment.

## Trust promises

RevenueOS must be able to demonstrate that:

1. one organisation cannot access another organisation's data;
2. capture is deliberate, visible and subject to consent and applicable law;
3. model output is reviewable, source-backed and correctable;
4. consequential actions do not occur without valid human approval during beta;
5. deletion, retention and connection behaviour are described accurately; and
6. operators can diagnose failures without reading raw customer content by default.

## Authentication

- Clerk is the planned production identity and organisation provider.
- API tokens must be cryptographically verified for issuer, audience, signature, expiry and other required claims.
- One active organisation is resolved from a verified token and current membership; the client cannot select an arbitrary `organisation_id`.
- Frontend route protection improves UX but never substitutes for API authorisation.
- Production configuration fails closed if mock auth, development headers or placeholder secrets are enabled.
- Administrator and high-risk actions should support recent authentication/step-up when Clerk capabilities and policy are selected.

## Tenant isolation

- Every tenant-owned database row, object-storage key, job, cache/index entry, webhook mapping and idempotency key is organisation-scoped.
- Repositories always apply an explicit organisation predicate.
- PostgreSQL RLS uses a transaction-local tenant setting; the application role does not bypass RLS.
- Worker transactions establish and clear tenant context per job; sessions are not reused across tenants.
- Same-tenant composite foreign keys prevent cross-organisation relationships.
- Search, embeddings, notifications, counts, exports, signed URLs and error messages are included in cross-tenant tests.
- Migrations and guarded administration use a separate role and path with explicit operational controls.

## Least privilege

- Provider scopes map to enabled capabilities; read, draft, send and write are independently disclosed and gated.
- Service-role credentials never reach the browser.
- Internal support has no standing raw-content access. Time-bound support access, if introduced, requires customer-visible policy, reason, approval and audit.
- Jobs receive only the tenant and resource identifiers required for their stage.
- AI providers receive the minimum authorised context and no application credentials or implicit tools.

## Encryption

- TLS 1.2+ is required for browser, API, database, storage and provider transport, subject to current platform recommendations.
- PostgreSQL, object storage, backups and secret stores use provider-managed encryption at rest.
- Highly sensitive connector tokens should use envelope encryption or a managed token/secret vault with key rotation and access audit.
- Signed object URLs are short-lived, resource-specific and issued only after authorisation.
- Key ownership, rotation, recovery and regional availability must be documented before production.

## Secret management

- Secrets enter through managed environment/secret services; only names/placeholders belong in `.env.example`.
- Credentials, OAuth tokens, signing secrets, recordings and transcripts are never committed.
- Secrets are separated by environment and provider connection purpose.
- Rotation is tested, including webhook overlap and token revocation.
- Logs and errors redact secrets and sensitive headers; a secret scan remains a required CI gate.

## Access controls and role model

The exact permission matrix requires a dedicated implementation decision. The beta baseline is:

| Capability | Member / sales representative | Manager | Organisation administrator |
| --- | --- | --- | --- |
| View assigned/authorised relationship context | Yes | Yes, plus policy-defined team context | Only where administration requires content; no blanket default |
| Ingest and review own/authorised meeting | Yes | Yes | Policy-controlled |
| Approve own follow-up/eligible CRM proposal | Yes, if connected policy allows | Yes for own work; escalation only if configured | Configure policy, not routine content approval |
| Manage team review exceptions | No | Yes within team scope | Configure scope |
| Connect personal provider | If permitted | If permitted | Enable/disable capability |
| Connect shared CRM / configure mappings | No | No by default | Yes |
| Invite/remove users and assign roles | No | No by default | Yes |
| Configure retention/export/deletion policy | No | No | Yes |
| View security/audit metadata | Own relevant history | Team workflow metadata where needed | Organisation-wide metadata |

Current Sprint 2 members have equal CRUD rights for core entities. Finer permissions above are target beta work and must not be claimed as implemented.

## Audit trails

Record content-minimised events for:

- authentication failures and membership/role changes;
- provider connection, scope, reauthorisation and revocation;
- consent confirmation and capture state;
- source access, export, exclusion and deletion;
- AI model/prompt/schema version, review decision and correction;
- suggested action, exact-version approval, expiry/revocation and execution outcome;
- CRM writes, communications and ambiguous/reconciled provider results; and
- retention-policy and high-risk administrative changes.

Audit events include tenant, actor/service, action, resource reference, time, request/job ID, result and safe reason. They exclude raw transcript, prompt, output, email body and secrets. Integrity, access, export and retention controls are production gates.

## Logging and observability

- Use structured logs with request/job IDs, tenant-safe opaque resource IDs, stage, duration and error class.
- Do not log raw customer content, query text, source excerpts, signed URLs, credentials or third-party payloads.
- Metrics are aggregated and access-controlled; per-user performance surveillance is not a product objective.
- Errors shown to users are safe and actionable; internal diagnostics remain content-minimised.
- Security alerts cover repeated authorisation failure, cross-tenant-test regressions, unusual export/deletion/admin activity and connector credential failure.

## Retention

- Organisations receive understandable defaults and configurable policies within supported bounds.
- Raw audio default: delete 30 days after successful transcription; users can delete earlier.
- Failed/quarantined uploads have a shorter, documented cleanup window.
- Transcript, AI artefacts and memory persist only while authorised and useful; derived data follows source deletion.
- Operational logs/jobs are short-lived and content-minimised.
- Approval/sync/audit metadata follows a documented customer/security retention period without retaining unnecessary content.
- Backup expiry is documented; the product never claims immediate physical removal from immutable backups when that is not true.

## Deletion and exclusion

1. Authorised request identifies source/resource and impact.
2. Item is immediately blocked from retrieval, prompts, search and new actions.
3. Active storage, indexes, derived artefacts, object copies and cached URLs are deleted or invalidated.
4. Connected-system behaviour is attempted only with explicit authority and reported separately.
5. Metadata-only audit records the request/outcome and any lawful hold.
6. Completion distinguishes active systems, provider systems and backup-expiry schedule.

Exclusion allows a user to prevent processing/use without misrepresenting the source as deleted. Corrections, supersession, exclusion and deletion are distinct states.

## Data export

- Export requires current membership, role authorisation and recent authentication appropriate to risk.
- Export contents and date range are previewed; large exports run as tenant-scoped durable jobs.
- Files are encrypted in private storage with short-lived single-resource URLs and automatic expiry.
- Export access and download are audited without logging contents.
- Machine-readable formats preserve provenance, timestamps, source state and deletion limitations.

## AI transparency and source traceability

- Factual claims identify source and source version or clearly say evidence is unavailable.
- Direct evidence, external record, user-confirmed memory and inference are visually distinct.
- Prompt/model/schema versions and review/correction state are retained as safe metadata.
- Models have no implicit tools, credentials or write authority.
- Structured output is validated before storage/use; same-tenant identifiers are rechecked.
- Corrections invalidate dependent output and future retrieval.
- Customer content is not used to train models or build evaluation datasets without a separate, explicit and lawful choice.

## Recording consent

- RevenueOS never records or captures a conversation implicitly.
- MVP ingestion begins only when a user deliberately selects a file/pastes text and confirms they have the required consent or authority.
- Connected post-meeting capture has a clear enabled state, eligible-source policy and per-event provenance.
- Consent evidence records policy/version, actor, time and capture method without claiming to establish legal compliance.
- The organisation and user remain responsible for applicable participant notice and consent, supported by clear product guidance and controls.
- If consent is uncertain, capture/processing stops or the source is excluded.

### In-person meeting capture

In-person capture is a future, constrained concept. It requires:

- explicit arm and start actions;
- a persistent, understandable visual/audible indicator;
- pause/stop and immediate-delete controls;
- participant and jurisdiction-aware guidance;
- no background, ambient, lock-screen or covert activation; and
- separate privacy, safety, battery/device and app-store review.

Native mobile capture is not a beta dependency.

## Regional privacy considerations

Before each launch region, document with qualified counsel and privacy specialists as appropriate:

- lawful basis and transparency for employee/user and customer-participant data;
- one-party/all-party recording and workplace surveillance requirements;
- data residency and cross-border transfers across Supabase, Clerk, OpenAI and integration providers;
- data processor/controller roles and required agreements;
- access, correction, deletion, portability and objection rights;
- breach notification and incident-response obligations;
- retention requirements and legal holds; and
- restrictions on automated employment or consequential decision-making.

The product must not present generic consent copy as legal advice. Region and customer policy may disable capture methods.

## Production readiness gates

No production customer content until all applicable gates pass:

### Identity and tenancy

- Real Clerk verification, active membership resolution and role policy are implemented.
- Mock auth cannot start in production.
- Cross-tenant API, database/RLS, job, storage, search, export and notification tests pass against PostgreSQL.
- Application database role is proven not to bypass RLS.

### Data and privacy

- Data inventory, classification, retention, deletion/export and backup expiry are documented and tested.
- Private storage, quarantine, validation and signed-URL authorisation are implemented.
- Recording/ingestion consent experience and customer terms are reviewed.
- Provider data-processing, training/retention settings and launch-region requirements are approved.

### AI and actions

- Model/prompt/schema evaluation gates pass, including source attribution and prompt injection.
- External communications and CRM writes require exact-version approval and idempotent reconciliation.
- Kill switches and rollback exist for models, prompts and each write-capable integration.

### Operations

- Encryption, secret rotation, dependency/secret scanning and security headers pass.
- Content-safe logs, metrics, alerts, audit trails and incident/support runbooks exist.
- Backup/restore, deletion, provider outage, revoked credential and ambiguous-action recovery are tested.
- Rate limits, cost ceilings, abuse controls and load envelopes are defined.

### Customer readiness

- First-company configuration is reviewed by an accountable administrator.
- No demonstration, test or evaluation uses production customer data without explicit authorised handling.
- Product claims, availability labels and limitations match implemented adapters and controls.

## Current high-priority gaps

- Production Clerk session verification is not implemented.
- Current persistence can run without the full production Supabase role/RLS deployment.
- Storage, ingestion, connector, approval, complete audit, deletion/export and
  production worker-operations controls are not implemented. A server-side
  OpenAI adapter exists for Executive Summary, Decisions and Action Items, but production provider
  privacy/retention/residency, consent, evaluation, budget and operational
  enablement gates are incomplete. Selecting it sends the chosen transcript to
  OpenAI; production customer data remains prohibited.
- Sprint 2 core-entity permissions are coarse.

These are expected current limitations, not defects hidden by this target document.

## Related documents

- [Current security and privacy baseline](security-and-privacy.md)
- [Target domain model](target-domain-model.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
- [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md)
