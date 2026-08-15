# Private beta operational and incident runbooks

These runbooks are human-operated. Preserve request IDs, timestamps, release
SHA, opaque organisation/user IDs and safe error codes only. Never copy a
transcript, prompt, generated result, provider payload, email body, customer
description, secret or database URL into logs or incident systems. For any
uncertain privacy impact, contain first and escalate to the security/privacy
owner.

## 1. API unhealthy

- **Detection:** `/health/live` is non-200, `/health/ready` is 503, latency/error
  alerts fire, or the web shows repeated product-safe failures.
- **Immediate containment:** stop rollout; keep the previous release available;
  disable affected beta traffic if errors could create inconsistent writes.
- **Diagnosis:** distinguish process, database, migration, auth, provider and
  worker configuration using the readiness component states and safe logs by
  request ID. Do not expose URLs or keys.
- **Safe recovery:** correct configuration through the secret manager, restore
  database reachability, or roll back API/web/worker together. Do not bypass
  readiness.
- **Validation:** liveness/readiness green, one synthetic authenticated read and
  write, no cross-tenant result, safe logs only.
- **Escalation:** platform owner; database owner for persistence; security owner
  for suspicious identity/tenant symptoms.

## 2. Worker not processing

- **Detection:** pending count/age rises, no safe completion events, expired
  leases accumulate or users see processing without progress.
- **Immediate containment:** keep OpenAI off if repeated calls are possible; do
  not manually mark jobs complete.
- **Diagnosis:** confirm worker release equals API release, migration readiness,
  non-bypass role, poll/lease/heartbeat configuration and supervisor state.
- **Safe recovery:** restart the matching worker; allow expired leases to
  recover through existing lease rules; reduce replicas only if contention is
  diagnosed.
- **Validation:** a synthetic mock job is claimed once, completes once and
  persists one validated artefact; backlog age falls.
- **Escalation:** application owner, then database/platform owner.

## 3. Migration failure

- **Detection:** migration job fails, readiness reports incompatible migration,
  or drift check changes.
- **Immediate containment:** keep API and worker for the new release stopped;
  prevent another migration runner; preserve database/backup.
- **Diagnosis:** record Alembic current/head and safe database error class with
  the migration role. Inspect whether the transaction rolled back; never edit
  the version table manually.
- **Safe recovery:** fix forward when safe; otherwise restore/roll back using an
  explicitly compatible release and approved backup. Treat `0020` downgrade as
  destructive.
- **Validation:** upgrade, downgrade/re-upgrade in validation; drift clean;
  forced RLS and append-only triggers present; readiness green.
- **Escalation:** database owner and engineering lead; security owner if RLS or
  constraints are affected.

## 4. OpenAI outage

- **Detection:** safe provider-unavailable/rate-limit errors increase while
  database/worker health remains green.
- **Immediate containment:** set `AI_PROVIDER=mock`, set the OpenAI feature flag
  false and restart worker/API consistently. Do not retry unboundedly.
- **Diagnosis:** use safe status/error classes and provider status information;
  never log raw provider output or key material.
- **Safe recovery:** continue synthetic/mock demonstrations or wait for provider
  recovery. Re-enable only with explicit approval and bounded canary.
- **Validation:** mock job completes with zero provider counter increase;
  OpenAI-disabled capabilities show safe state.
- **Escalation:** AI/provider owner and privacy owner if content transmission is
  in doubt.

## 5. Quota exceeded

- **Detection:** `daily_generation_limit_exceeded` or
  `daily_provider_limit_exceeded` responses and admin counter at its limit.
- **Immediate containment:** do not reset/manually edit counters or increase
  limits during an incident; disable OpenAI if an unexpected request spike is
  occurring.
- **Diagnosis:** compare UTC-date generation/provider counts with newly created
  jobs and actual provider attempts. Confirm idempotent reuse was not counted.
- **Safe recovery:** wait for the next UTC date, correct abusive/repeated client
  behaviour, or approve a reviewed configuration change for the next release.
- **Validation:** duplicate requests reuse a job; next-date counter starts at
  one; cross-tenant counters remain invisible.
- **Escalation:** product/admin owner for expected demand; security owner for
  abuse.

## 6. Stuck jobs

- **Detection:** running jobs exceed lease duration, heartbeat is stale or retry
  age exceeds the bounded schedule.
- **Immediate containment:** disable OpenAI for a suspected request loop; avoid
  direct status edits.
- **Diagnosis:** inspect safe job IDs, status, attempt count, lease/heartbeat and
  error code only. Confirm worker clock/config and database connectivity.
- **Safe recovery:** use normal expired-lease recovery and bounded durable retry;
  restart matching workers. Cancel through existing lifecycle rules only.
- **Validation:** each job has one owner, attempts remain within max, and final
  artefact trace matches current transcript version.
- **Escalation:** application/worker owner; provider owner if all failures share
  a provider class.

## 7. Retention failure

- **Detection:** scheduled command non-zero, repeated eligible counts, FK or
  append-only error, or old data remains visible.
- **Immediate containment:** stop that tenant's destructive run; preserve dry-run
  output and release SHA; never widen tenant scope.
- **Diagnosis:** rerun dry-run for the exact organisation and bounded batch;
  verify tenant/approved-maintenance context, policy and deletion dependencies.
- **Safe recovery:** fix forward, then resume small batches. A failed transaction
  is retriable and must not be replaced with ad-hoc global deletes.
- **Validation:** dry run reaches zero; target records disappear from meeting,
  Opportunity Workspace and Revenue Brain reads; another tenant is unchanged.
- **Escalation:** database and privacy owners before any manual SQL.

## 8. Export failure

- **Detection:** request becomes `failed`, generation command exits non-zero,
  download is unavailable, or expiry purge fails.
- **Immediate containment:** restrict/delete incomplete temporary files; do not
  transmit an unverified export.
- **Diagnosis:** verify exact tenant/request IDs, confirmed request, restricted
  directory permissions, disk capacity and safe failure code. Do not inspect
  content in logs.
- **Safe recovery:** retry the same request; generation atomically replaces its
  UUID filename. If expired, create a new admin request. Purge expired files.
- **Validation:** JSON version/tenant match, expected authorised sections exist,
  secrets/internal worker fields and other-tenant IDs are absent, expiry works.
- **Escalation:** privacy owner for delivery; platform owner for storage.

## 9. Deletion failure

- **Detection:** confirmed request remains processing/failed or command exits
  without organisation removal.
- **Immediate containment:** block new use of the target organisation and
  disable its memberships in Clerk/RevenueOS; do not claim success.
- **Diagnosis:** verify exact confirmation/request/tenant, transaction error and
  dependency ordering using metadata only.
- **Safe recovery:** retry the same maintenance command. The destructive phase
  is one transaction; never continue with partial ad-hoc deletes. Restore from
  backup only under the incident decision process.
- **Validation:** all target tenant rows/exports are absent, unrelated tenants
  and users with other memberships remain, identity-provider removal is
  completed manually.
- **Escalation:** engineering lead, database owner and privacy owner.

## 10. Suspected tenant-isolation incident

- **Detection:** a user reports another organisation's identifier/content,
  RLS test fails, a cross-tenant join is observed or tenant context is missing.
- **Immediate containment:** disable affected routes/features; stop API/worker
  if scope is uncertain; preserve logs/backups; do not query or copy more
  customer content than necessary.
- **Diagnosis:** use request IDs and opaque tenant IDs to trace auth claim,
  service predicates, composite keys and transaction-local RLS setting. Engage
  the security owner immediately.
- **Safe recovery:** patch with a regression test, rotate affected sessions,
  restore trustworthy isolation and notify partners under the incident plan.
- **Validation:** forced RLS, non-bypass runtime role, API cross-tenant tests,
  export/retention/deletion boundaries and affected route tests all pass.
- **Escalation:** highest severity to security/privacy, engineering lead and
  incident commander; follow legal notification guidance.

## 11. Secret exposure

- **Detection:** key/token/credential appears in logs, repository, frontend
  bundle, screenshot, support message or unauthorised access alert.
- **Immediate containment:** revoke/rotate the secret at its provider, disable
  affected integration/feature and restrict the exposed artefact. Do not paste
  the secret into the incident record.
- **Diagnosis:** identify secret class, exposure window and access using a hash
  or provider ID, then scan source/build/log destinations.
- **Safe recovery:** issue least-privilege replacement through secret manager,
  redeploy, purge where possible and fix the exposure path.
- **Validation:** old credential rejected, new path works, frontend/source/
  logs scans clean and no customer content was additionally exposed.
- **Escalation:** security incident commander, provider/database owner and
  privacy/legal as applicable.

## 12. Rollback

## 13. Visual upload, processing or storage failure

1. Confirm whether failure is upload validation, provider processing, object
   deletion or database/object reconciliation; do not request the customer image.
2. Inspect metadata-only events and safe failure codes. Never paste signed URLs,
   OCR or image bytes into logs or tickets.
3. Provider failures may use the bounded retry action. `delete_failed` requires
   an object-delete retry before reporting completion.
4. Run `visual-reconcile` without `--repair` for the affected organisation.
   Investigate unexpected missing/orphan counts before a reviewed `--repair`.
5. If tenant isolation, a public object or credential exposure is suspected,
   disable `visualEvidence`, revoke/rotate credentials and follow the tenant
   isolation/secret incident runbooks.

## 14. Recording upload, transcription or storage failure

1. Disable `recordingCapture` and, for provider/retry incidents,
   `transcription`/automatic intelligence. Do not delete or mark sessions complete.
2. Separate consent/permission, chunk receipt/integrity, storage, worker claim,
   provider and transcript-persistence failures using safe codes and opaque IDs.
3. Run tenant-scoped `recording-reconcile` without repair. Never request/download
   customer audio or paste transcript, object key, signed URL or provider payload.
4. Retry only classified transient transcription failures within the configured
   attempt limit. A final transcript remains usable if automatic intelligence fails.
5. For deletion failure, retry object deletion before relational removal or a
   complete-erasure report. Use the dedicated reconciliation runbook for repair.
6. Validate one synthetic mock WebM flow, one transcript version, no orphan object,
   forced RLS and content-free logs before re-enabling.

## 15. Browser Companion or marker failure

1. Disable `aiCompanion` to hide the orchestration route; independently disable
   `recordingCapture`, `visualEvidence` or `aiDebrief` only when that underlying
   capability is affected.
2. Confirm the Interaction lifecycle and tenant identifier using metadata only.
   Never request transcript, audio, photo or debrief content for a marker issue.
3. A duplicate-tab recording conflict is expected safe behaviour. Close or
   cancel/finalise the active session before retrying.
4. For in-tab upload loss, keep the tab open, restore connectivity and use
   `Retry queued audio`. A discarded tab cannot recover unsent memory bytes.
5. Marker rows are immutable. Correct an accidental marker only through the
   pre-completion soft-delete route; do not edit it in place.
6. Validate forced RLS, export version 8, deletion ordering and content-free logs
   before re-enabling a disabled Companion path.

- **Detection:** release regression, readiness failure, unsafe privacy/security
  behaviour or incompatible worker/API contract.
- **Immediate containment:** stop rollout and worker claims; disable the
  affected server flag; preserve current database and backup.
- **Diagnosis:** determine whether application-only rollback is compatible with
  the current schema. Treat database downgrade as a separate destructive
  decision.
- **Safe recovery:** deploy the last validated web/API/worker release together;
  keep forward-compatible migration when possible. Follow the deployment guide
  for any approved downgrade/restore.
- **Validation:** liveness/readiness, migration range, synthetic beta journey,
  tenant isolation, mock worker, quotas and safe logs.
- **Escalation:** engineering lead owns decision; database/security/privacy
  owners approve destructive or incident-related steps.
## 16. Document or email evidence failure

1. Check `/ready` capability flags, safe event codes and quota counters; do not ask
   for the customer's content in logs or tickets.
2. For parse rejection, confirm the source is PDF/TXT, within byte/page/text limits,
   not password-protected and has extractable text. Do not bypass active-content or
   malformed-file checks.
3. For provider failure, keep the source out of review/downstream views and retry
   only within its configured attempt limit. Switch
   `API_EVIDENCE_EXTRACTION_PROVIDER_NAME` to the labelled deterministic mock if
   external processing is paused.
4. For a stuck review, confirm every candidate has an explicit accept/reject
   decision. Zero findings require an explicit empty completion.
5. For document deletion failure, leave the row in `delete_failed`, repair storage
   access and retry. Never delete database lineage first. Email deletion has no
   external object but must clear both raw and normalised text.
6. Disable `API_FEATURE_DOCUMENT_EVIDENCE_ENABLED` or
   `API_FEATURE_EMAIL_EVIDENCE_ENABLED` to stop new intake while preserving existing
   data for recovery/export.
