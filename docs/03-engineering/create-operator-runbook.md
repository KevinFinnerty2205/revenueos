# Create operator runbook

## Enablement

1. Keep `API_FEATURE_CREATE_ENABLED=true` only in an approved environment.
2. Configure private object storage. `local` storage is development/test only;
   production configuration validation requires the existing private S3-compatible
   adapter and deployment-managed credentials/signing secret.
3. Run Alembic through `0041_create_studio` and verify the runtime database role does
   not bypass RLS.
4. Start the existing API and durable worker. Create has no separate service.
5. An organisation administrator enables the server-side `create` entitlement in
   Settings, then uploads and reviews an authorised synthetic/template PPTX.

The readiness surface reports the environment feature flag. `/api/v1/create/availability`
reports the tenant entitlement and role capabilities. A feature flag alone is not a
customer launch approval.

## Limits and safe configuration

Defaults are 50 MB/100 source slides/2,000 ZIP entries/250 MB expanded XML package,
500 media assets/10 MB each/5 MB XML, 30 generated slides, 20 active templates,
20 versions per template, 10 generations per user/day, 50 per organisation/day and
three processing attempts. Keep the documented limits unless a measured work order
changes code, tests, cost analysis and abuse review together.

## Failure triage

- `create_not_entitled`: verify the organisation entitlement; do not bypass it.
- `unsafe_pptx`, `unsupported_pptx`, `malformed_pptx`, `pptx_limit_exceeded`: ask the
  administrator for a clean standard `.pptx`; never weaken parsing for one file.
- processing stays queued: verify the worker is running, the feature flag is on and
  database leasing/RLS grants are correct.
- `create_storage_failure`: inspect private-store health and key permissions; content
  and signed URLs must not enter tickets/logs.
- `claim_source_changed`: a source was withdrawn or expired; regenerate and review.
- approval unavailable: review every seller/inferred claim and wait for a successful
  current render.

Safe events are `create_template_processed`, `create_presentation_rendered` and
`create_work_failed`; they carry IDs/counts/codes only. Retry is capped at three.
Resolve the cause before requeueing through an approved operational change—there is
no browser force-complete path.

## Rollback and incidents

Set `API_FEATURE_CREATE_ENABLED=false` for environment-wide containment or disable the
organisation entitlement for a tenant-specific stop. Both make new Create actions
fail closed; neither destroys retained records. Preserve storage/database evidence,
revoke signing material if download grants may be compromised, and use the existing
incident process. Database downgrade below `0041_create_studio` deletes Create rows and
must occur only after an approved export/object-retention decision.

Run organisation export, deletion and storage reconciliation using the existing
private-beta maintenance commands. See [retention/export/deletion](create-retention-export-deletion.md)
and [security review](create-security-privacy-review.md).
