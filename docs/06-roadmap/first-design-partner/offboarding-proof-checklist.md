# Synthetic offboarding proof checklist

Status: **WAITING FOR TARGET**. Pass this with a synthetic tenant in the exact target environment before onboarding a real partner. Retain content-safe evidence only.

## Setup

Use a synthetic organisation containing representative Accounts, Contacts, open Opportunities, Tasks/Actions, Interactions/Evidence, Pipeline/Targets/Forecast, import/merge history, one generated Create object/download grant and one item in every enabled queue state that can be safely cancelled or completed. Record the organisation UUID, release, feature profile, storage/backup configuration and UTC start time.

## Procedure

| Step | Procedure | PASS condition |
| --- | --- | --- |
| 1. Authority | Create an admin deletion/export request using the ordinary Settings workflow and exact synthetic organisation | Request belongs to current tenant/admin and requires deliberate confirmation |
| 2. Export | Run `revenueos-beta-maintenance export --organisation-id <uuid> --request-id <uuid>`; download through the authorised flow; validate export version 29/tenant/expected sections and expiry/cross-tenant denial | Verified portable export, no credentials/leases/provider payloads/other tenant IDs; restricted temporary file handled under policy |
| 3. Disable users | Revoke/remove Clerk sessions/memberships, then disable RevenueOS memberships | Existing sessions are denied within measured objective; new login denied; shared history retained until deletion |
| 4. Invalidate grants | Attempt unused Create and export downloads after disablement; retry used/expired grants | Every grant denies; no signed URL/token appears in logs |
| 5. Cancel/contain work | Disable relevant feature flags/worker claims; use supported cancellation/revocation/reconciliation lifecycle for queued/retryable work; never edit statuses directly | `queue-status` shows no runnable work; unknown external/delivery states are resolved rather than replayed |
| 6. Revoke integrations | Confirm no connector is enabled in the recommended profile. If an approved exception exists, revoke provider first and record result | Provider and local connection disabled; failure blocks success and enters incident/reconciliation flow |
| 7. Delete organisation | Execute `revenueos-beta-maintenance delete-organisation --organisation-id <uuid> --request-id <uuid>` only after exact UI confirmation | Command completes once and is safe to retry after a failed transaction |
| 8. Verify database | Query all tenant tables using the guarded verification role and exact UUID; verify organisation/memberships/import/merge/CRM/Core/AI/Create/grant/control rows absent | Zero target rows; synthetic control tenant unchanged; no orphan FK/object metadata |
| 9. Verify blobs/files | List exact tenant prefixes in source object storage and export directory using provider/platform tools | Zero tenant objects and temporary exports; no broad/manual deletion was used |
| 10. Verify product routes | Try known Account/Contact/Opportunity/Interaction/Create/export IDs through API, Search and old/deep browser links | Safe not-found/denial; no cached content; no existence leakage |
| 11. Verify worker discovery | Query every worker eligible-organisation function and run `queue-status`/support tooling | Deleted organisation is not discoverable/claimable and no orphan job is processed |
| 12. Record backup expiry | Identify every backup/snapshot containing the synthetic tenant and its scheduled expiry | Active systems are deleted; immutable-copy expiry date is documented honestly |

Useful checks after deletion:

```sh
revenueos-operations tenant-preflight --organisation-id <deleted-uuid>
revenueos-operations queue-status --organisation-id <deleted-uuid>
```

`tenant-preflight` must return `blocked` because the organisation no longer exists. `queue-status` is deliberately content-safe and may return `ok`; when it does, every queue must have zero states and zero stale leases. Database/object verification uses a guarded operator role and provider console/CLI; do not add a privileged browser support path.

## Evidence record

```text
target/release/profile:
synthetic organisation UUID:
export request/result/checksum:
disablement and maximum latency:
grant checks:
queue containment/reconciliation:
integration revoke or not applicable reason:
deletion request/result:
database verification:
object/export verification:
deep-link/search verification:
worker discovery verification:
backup IDs and expiry dates:
completed UTC:
operator/reviewer:
overall result:
```

Any residual active row, blob, grant, deep link or worker discovery is `FAIL`. Provider revocation failure, backup ambiguity or an export that cannot be verified also blocks launch. Destroy the synthetic evidence files under the approved schedule after review.
