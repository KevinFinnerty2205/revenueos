# Support and monitoring launch checklist

Status: **WAITING FOR TARGET; OWNER APPROVAL REQUIRED**. Use current hosting/database/storage native monitoring where it covers the checks below. No paid monitoring service is authorised by this package.

## Support ownership

| Gate | Required proof | Status |
| --- | --- | --- |
| Support address | Owner-approved monitored address, hours and acknowledgement target; send/receive a synthetic ticket | **OWNER APPROVAL REQUIRED** |
| Incident contact | Primary and backup people with reachable channels; run a synthetic page | **OWNER APPROVAL REQUIRED** |
| Escalation owner | Named incident commander plus engineering, security/privacy, database and partner-communication owners | **OWNER APPROVAL REQUIRED** |
| Severity/pause policy | Team has reviewed [pause criteria](launch-pause-criteria.md) and can disable access/features/workers | **OWNER APPROVAL REQUIRED** |
| Request-ID workflow | Trigger one safe API error, give only its request ID to support, locate the matching content-safe log | **WAITING FOR TARGET** |
| Support bundle | `revenueos-operations support-bundle --organisation-id <synthetic-uuid>` returns `contentIncluded=false` and no canary content | **WAITING FOR TARGET** |

## Required signals and synthetic tests

| Signal | PASS check | Initial threshold/action |
| --- | --- | --- |
| API liveness/readiness | External HTTPS probe to `/health/live` and `/health/ready`; force a validation-environment readiness failure and receive an alert | Two consecutive failures page the operator; block rollout immediately |
| API error rate | Hosting/log metric for safe 5xx count/rate by release and route class; inject one synthetic failure | Alert route receives it without request/customer content; sustained elevation pauses onboarding |
| Database | Provider availability, connections, storage, CPU, latency, backup/PITR state and TLS | Alert before provider limits; any integrity/RLS symptom pauses immediately |
| Worker | Supervisor process health plus `queue-status` state counts/stale leases; stop a validation worker and observe alert/restart | No silent stopped worker; repeated stale leases or unknown states disable affected feature |
| Object storage | Provider availability/capacity/access alerts plus preflight write/read/delete canary | Any public-access finding, missing/corrupt object or credential error disables binary capabilities |
| Backup failure | Native backup-job failure and age alert; deliberately fail/withhold a validation backup | Alert before approved RPO; backup failure pauses real-data testing |
| Restore readiness | Named-target drill completion age | No launch without current pass; repeat quarterly and after material change |
| Retention failure | Scheduled command exit/status and repeated eligible counts; force a safe validation failure | Non-zero/repeated backlog alerts privacy/operations owner; stop destructive run for that tenant |
| Auth/revocation | Safe auth failure counts and Clerk health; session matrix result | Unexpected success after disablement or cross-org symptom pauses immediately |
| Feature/config drift | Scheduled or release-time `production-preflight` and flag diff | Any diff blocks release and data entry |

Canonical operator checks:

```sh
curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
  "$REVENUEOS_TARGET_API_ORIGIN/health/live"
curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
  "$REVENUEOS_TARGET_API_ORIGIN/health/ready"
revenueos-operations production-preflight > preflight.json
revenueos-operations queue-status --organisation-id <synthetic-tenant-uuid> > queues.json
revenueos-operations support-bundle --organisation-id <synthetic-tenant-uuid> > support.json
jq -e '.status == "ready" and .contentIncluded == false' support.json
```

Run a time-bounded content scan using unique synthetic canaries as defined in the [target preflight](target-environment-preflight-checklist.md). Operator dashboards/tickets may contain timestamps, release SHA, request IDs, opaque tenant/user/job IDs, controlled states/counts and safe error codes only. They must not contain names, email addresses, CSV rows, transcript/document/email text, prompts, generated content, values, object keys, signed URLs, credentials or provider payloads.

## During the first partner

- Review health/backup/retention each business day and before every supervised import.
- Keep an operator reachable during onboarding/import and the agreed support window.
- Record incidents and support issues by safe IDs; customer-content access is exceptional, explicitly authorised and time-bound.
- Never directly edit queue state or blindly retry `unknown_external_state`/`unknown_delivery_state`.
- Test the relevant kill switch and partner-communication path before launch.

## External monitoring decision

A paid external product is not yet shown to be necessary because no target platform has been selected and provider-native capabilities have not been assessed. If the selected target cannot supply the checks/alerts above, the operations owner must produce a separate comparison with exact missing coverage, monthly and usage-based cost, data categories/regions/subprocessors, access controls, retention, contract/DPA and exit plan. Owner approval is required before trial or activation.

All support ownership and every synthetic alert route must pass before real data. A dashboard without a tested notification path is not evidence.
