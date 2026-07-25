# WO-009 focused private beta security review

Date: 25 July 2026. Scope: repository implementation for controlled private
beta readiness. This is an engineering review, not a certification or external
penetration test. Production customer data remains prohibited.

## Trust boundaries reviewed

| Area | Implemented control | Residual/operator dependency |
| --- | --- | --- |
| Authentication | Clerk RS256 verification with required issuer, audience, expiry, issued-at, subject and active organisation; bounded cached JWKS | Clerk tenant, invitation and organisation-creation policy must be configured and monitored |
| Tenant derivation | Organisation comes only from verified token; deterministic local mapping; no request organisation selector | Clerk active-organisation claim must be present and correct |
| Authorisation | Only admin/member; active user/membership rejection; admin checks in service | Clerk invite/deletion remains manual; no advanced RBAC |
| Database isolation | Explicit organisation predicates, composite tenant keys, forced RLS on all new tenant tables, non-bypass role requirement | PostgreSQL integration tests require CI database and role-creation permission |
| Consent | Versioned server-owned acknowledgement required for transcript writes and all intelligence requests | Notice wording/approval and version rollout are operational decisions |
| Export | Admin-only request, explicit tenant queries, field allowlists, UUID filename, resolved-root check, 24-hour expiry/purge | Restricted storage/delivery and purge schedule are operator-owned |
| Retention/deletion | Tenant ID mandatory, bounded/retriable operations, dependency order, explicit append-only delete context | Human scheduling, dry-run review and Clerk cleanup |
| Usage | Atomic tenant/date counters at job creation and actual OpenAI request boundary; existing retry limits | Limits are global configuration, not per-partner commercial plans |
| Feature flags | Server-side safe defaults; disabled routes fail closed; frontend only receives safe booleans | Environment change/restart process must be controlled |
| OpenAI | Disabled flag by default; server-only credentials; selected provider config validated | Separate privacy/provider approval is required before customer content |
| Frontend | No secrets in public configuration; Clerk secret remains server-side; feature-gated content | Build/deployment environment must prevent accidental `NEXT_PUBLIC_` secrets |
| Logs | JSON request/correlation records with optional opaque UUIDs; content-redacted domain telemetry | Central collection/access/alerting platform is deployment-specific |
| Backup | Encrypted, least-privilege and non-local restore process documented | Hosting provider and restore drills are human-controlled |
| Demo data | Fixed tenant-derived IDs, synthetic labels/text, explicit seed/reset, no automatic production execution/provider call | Operators must select the correct tenant/user IDs |

## Defects found and resolved

1. First onboarding persistence relied on a database default before flush, so a
   new in-memory step could be `None`. The service now treats an unflushed record
   as step zero; persistence/skip regression tests cover it.
2. SQLite returned an expiry timestamp without timezone information, causing
   export status/download comparison to fail. Expiry comparison now normalises
   the persistence-edge value; download, expiry and traversal tests cover it.
3. The initial safe-event actor relationship was user-only. It is now a
   composite organisation-membership foreign key, preventing a cross-tenant
   actor reference.
4. The prior `manager` role exceeded the minimum beta model. Migration `0020`
   deterministically maps it to `member`, then constrains roles to admin/member.
5. OpenAI selection could be constructed outside production with its feature
   flag off. Configuration now rejects OpenAI selection in every environment
   unless the server flag is explicitly enabled; tests enable it deliberately.
6. A frontend capability response existed but disabled workspaces could still
   render before receiving it. Dedicated client gates now render workspace
   content only after a true server capability, while API dependencies remain
   authoritative.
7. Readiness database connectivity did not have a route-level deadline. Both
   connectivity and migration checks are now bounded and expose only safe state.
8. Daily provider-limit rejection was initially treated as transient worker
   failure. It now fails the job without a provider call or futile same-day
   durable retries; a regression verifies the provider cannot be reached.
9. The unconfigured production web build could render a Clerk sign-out control
   without its provider. The page now uses the same complete public
   configuration gate as sign-in/sign-up, with a fail-closed render regression.
10. Organisation deletion initially removed export database rows without
    removing their sensitive temporary files. Export paths are now validated
    and removed before record deletion; unsafe paths fail visibly and the same
    request can be retried after operator correction.
11. Fixed demo meeting dates would eventually make new demo seeds immediately
    eligible for default retention. Stable IDs/content are retained while new
    meetings use bounded recent relative dates; the demo regression runs a
    retention dry run before reset.
12. Some beta write responses initially refreshed tenant rows after committing,
    when PostgreSQL's transaction-local RLS context had already reset. Server
    defaults are now flushed/refreshed before commit; the notice concurrency
    recovery path explicitly restores the trusted tenant context before its
    post-rollback read.
13. Initial Clerk reconciliation looked up the organisation before setting the
    forced-RLS tenant context, which would make a production identity invisible
    and block provisioning. The verified external organisation claim now first
    derives the deterministic internal UUID, sets that transaction-local
    context, and queries both identifiers; the race-recovery path restores the
    same context. A PostgreSQL identity reconciliation regression covers it.

## Verification evidence

Regression coverage includes signed JWT claim validation, disabled user/member,
admin/member boundaries, notice version and spoof rejection, transcript bounds,
atomic quota/idempotency, retention dry-run/execution/cross-tenant behaviour,
organisation deletion preserving a shared user, deterministic export field
allowlist/path/expiry/purge, feature-gated API/UI, feedback limits, onboarding,
migration round trips and PostgreSQL forced-RLS coverage for every tenant table.

The repository secret/prohibited-scope audit, full backend/frontend tests,
Playwright journey, Ruff, mypy, ESLint, Prettier, TypeScript and production
builds are release gates. A skipped PostgreSQL test is not launch evidence; CI
must run it against PostgreSQL.

## Residual risks

- No external security assessment, compliance certification or regulated legal
  hold/erasure guarantee exists.
- Clerk organisation governance, secret manager, central monitoring, encrypted
  backups and incident contacts are deployment responsibilities.
- Export and transcript content are deliberately sensitive; support delivery
  and operator terminals remain exposure points.
- Database RLS is defence in depth and does not replace explicit predicates.
- Operational commands accept explicit UUIDs; two-person review is recommended
  for production deletion and restored-data access.
- OpenAI content transfer remains prohibited until separately approved even
  though the technical adapter and controls exist.

No new AI capability, prompt, schema, job type, provider or reasoning path was
introduced by this work order.
