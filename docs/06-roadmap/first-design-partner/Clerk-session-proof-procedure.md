# Clerk and session proof procedure

Status: **WAITING FOR TARGET AND PARTNER**. Repository tests prove token-validation and local access rules; they do not prove the target Clerk instance, browser cookies or revocation latency.

## Test identities and acceptance rule

Use only synthetic identities in the exact target deployment:

- Organisation A: one admin and one member;
- Organisation B: one admin;
- one unprovisioned Clerk organisation/user; and
- a clean browser profile plus a second device/private window for stale-session checks.

Record the Clerk instance ID/type, configured session/JWT lifetime, web/API origins, release SHA, UTC test times and request IDs. Before testing, the owner must set a maximum acceptable revocation objective. Recommended for the supervised cohort: RevenueOS disablement denies the next API request; Clerk-only session/member revocation is measured until denial and must not exceed the approved token/session lifetime. Emergency offboarding uses both Clerk revocation/removal and RevenueOS membership disablement.

## Procedure

| Proof | Steps | PASS evidence |
| --- | --- | --- |
| Legitimate login | Invite/provision synthetic Admin A; sign in from the public origin; select Organisation A; open Home and Settings; perform one authorised synthetic read | Correct user/organisation, no mock banner, API success with request ID, Secure/HttpOnly/SameSite cookie attributes recorded from browser tooling without copying cookie values |
| Logout | Start a UTC timer, log out normally, retry protected UI and API from the same tab, then reload | Redirect to sign-in and protected API denied; observed latency recorded |
| Revoked session | Sign in again, revoke the exact session in Clerk, poll a harmless protected read every five seconds without refreshing the token deliberately | Denial time and maximum observed latency recorded; no access after denial |
| Disabled user | Disable the user in RevenueOS and Clerk using the approved admin/operator flow; retry with the already-open browser | Next RevenueOS API request is denied; UI cannot fetch protected data; no download/export grant works |
| Removed organisation member | Restore a fresh synthetic user, remove their Organisation A membership in Clerk, and retry with both the existing tab and a new login | Existing-token window measured; new token cannot select/access Organisation A; RevenueOS membership is disabled for immediate denial |
| Wrong-organisation access | While authenticated to Organisation A, request known Organisation B Account, Contact, Opportunity, Interaction, export and Create identifiers through normal routes | Every request is safe `404`/denial with no existence or content disclosure |
| Stale browser after removal | Keep an Opportunity and one pre-issued download page open, remove/disable membership, then refresh, navigate back and attempt download | No cached protected content is newly returned; API and grant deny; browser no-store behaviour observed |
| Admin/member permissions | Admin A opens Settings, provisions/changes allowed beta settings and creates an import preview. Member A attempts the same routes. Both use normal Core reads | Admin succeeds; member receives safe denial on admin/import/merge/destructive paths while permitted member workflow remains available |
| Unprovisioned identity | Sign in with the synthetic unprovisioned organisation/user | Authentication fails closed; no organisation/user/membership row is created |

For each revocation case capture:

```text
case | change_at_utc | first_denied_at_utc | latency_seconds | configured_lifetime_seconds | result | request_ids
```

The maximum observed access-revocation latency is the maximum `latency_seconds` across logout, session revoke, user disablement, membership removal and stale-browser tests. Record it explicitly; do not substitute the configured lifetime or repository test result.

## Failure handling

Any cross-organisation disclosure, a disabled RevenueOS member receiving a successful protected response, a usable stale download grant, unprovisioned JIT creation or latency beyond the pre-approved objective is `FAIL` and triggers the [launch pause criteria](launch-pause-criteria.md). Contain access, preserve content-safe request IDs, correct configuration/code and repeat the complete matrix.
