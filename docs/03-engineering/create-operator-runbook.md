# Create operator runbook

## Enablement

1. Keep `API_FEATURE_CREATE_ENABLED=true` only in an approved environment.
2. Configure private object storage. `local` storage is development/test only;
   production configuration validation requires the existing private S3-compatible
   adapter and deployment-managed credentials/signing secret.
3. Run Alembic through `0049_create_trust` and verify the runtime database role does
   not bypass RLS.
4. Start the existing API and durable worker. Create has no separate service.
5. An organisation administrator enables the server-side `create` entitlement in
   Settings, then uploads and reviews an authorised synthetic/template PPTX.

The readiness surface reports the environment feature flag. `/api/v1/create/availability`
reports the tenant entitlement and role capabilities. A feature flag alone is not a
customer launch approval.

## Limits and safe configuration

Defaults are 50 MB/100 source slides/2,000 ZIP entries/250 MB expanded package,
500 media assets/10 MB each/5 MB per XML part, 255 characters per package path,
128 XML levels, 100,000 XML elements per part, 1,000 relationships per part and
10,000 relationships per package. Compressed entries over 1 MiB are limited to
200:1 and aggregate compression to 100:1. Create also limits generated presentations
to 30 slides, active templates to 20, versions per template to 20, generations to
10 per user/day and 50 per organisation/day, with three processing attempts. Keep
these limits unless a measured work order changes code, tests, cost analysis and the
abuse review together.

## Failure triage

- `create_not_entitled`: verify the organisation entitlement; do not bypass it.
- `unsafe_pptx`, `unsupported_pptx`, `malformed_pptx`, `pptx_limit_exceeded`: ask the
  administrator for a clean standard `.pptx`; never weaken parsing for one file.
- template shows **Needs attention**: use native title/content placeholders, review
  the inferred roles and choose editable only when the slide has the required role.
- template shows **Unsupported**: remove external links, embedded objects, macros,
  custom XML, embedded fonts, SVG, hidden slides or ambiguous package content, then
  upload a new version. Do not override compatibility state in the database.
- processing stays queued: verify the worker is running, the feature flag is on and
  database leasing/RLS grants are correct.
- `create_storage_failure`: inspect private-store health and key permissions; content
  and grant secrets must not enter tickets/logs.
- `generated_validation_failed`: quarantine the version, preserve metadata-only
  diagnostics and regenerate only after finding the manifest/output or OOXML defect.
- `claim_source_changed`: a source was withdrawn or expired; regenerate and review.
- `presentation_file_unavailable`: verify the exact tenant-scoped private object;
  never substitute a different version. `presentation_file_integrity_failed` means
  checksum drift: contain downloads, preserve the object and investigate storage.
- approval unavailable: review every seller/inferred claim and wait for a successful
  current-profile render. Revalidating a template creates a current compatibility
  result; old approved template versions do not bypass the profile gate.

Safe events are `create_template_processed`, `create_presentation_rendered`,
`create_presentation_downloaded` and `create_work_failed`; they carry IDs/counts/
result codes only. Retry is capped at three. Download URLs never contain credentials;
the separate opaque grant secret is single-use, short-lived, user-bound and accepted
only in the authenticated POST body. Never paste the secret into a URL or ticket.
Resolve the cause before requeueing through an approved operational change—there is
no browser force-complete path.

## Rollback and incidents

Set `API_FEATURE_CREATE_ENABLED=false` for environment-wide containment or disable the
organisation entitlement for a tenant-specific stop. Both make new Create actions
fail closed; neither destroys retained records. Preserve storage/database evidence,
invalidate affected grants through the current membership, entitlement or approval
gate if download access may be compromised, and use the existing incident process.
Database downgrade below `0041_create_studio` deletes Create rows and
must occur only after an approved export/object-retention decision.

Run organisation export, deletion and storage reconciliation using the existing
private-beta maintenance commands. See [retention/export/deletion](create-retention-export-deletion.md)
and [security review](create-security-privacy-review.md).

The exact supported profile and administrator recovery guidance are in the
[Create PowerPoint trust guide](../01-product/create-powerpoint-trust-guide.md). Target-
environment scheduling, restore/offboarding proof and broader support ownership remain
WO-039C launch work, not claims made by this runbook.
