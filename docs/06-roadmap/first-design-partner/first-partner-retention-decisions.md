# First-partner retention decisions

- **Status:** **ONE CONSOLIDATED OWNER DECISION REQUIRED**
- **Recommended profile:** application 90 days; encrypted backups 14 days;
  content-minimised operational logs 14 days

The repository already defines most lifecycle rules. Kevin should not be asked to
redesign them. OD-05 only approves the ordinary application setting and the two
launch-environment windows that remain owner-controlled.

## Canonical rules—do not reopen

| Data/lifecycle | Existing rule | First-partner treatment |
| --- | --- | --- |
| Ordinary retention-eligible tenant content | Admin explicitly chooses 30, 90 or 180 days, or manual; repository default is 90 days | Recommend and explicitly select **90 days** |
| Export download grant | Expires after 24 hours | Keep |
| Provisional live intelligence | Defaults to 30 days | Keep, but live intelligence is disabled |
| Recording session / verified raw audio | Session expires after 24 hours; raw audio defaults to seven days | Keep, but recording/audio are disabled |
| CRM import source file | Preview/metadata is bounded; raw CSV is not stored as a durable object | Keep |
| Create/private file lifecycle | Deleted through authorised organisation/file workflows and reconciled with private storage | Keep; Create is off unless separately approved |
| Organisation offboarding | Disable access, optional authorised export, exact-confirmation deletion, row/object/grant verification; immutable backups age out | Keep |
| Billing and Credit transaction history | Exportable, append-only/restrictively retained; organisation deletion fails closed | **Pre-live accounting/legal treatment still requires owner approval; do not infer a period from ordinary content retention** |
| RPO/RTO starting objectives | RPO 24 hours and RTO one business day, measured in target proof; not contractual SLAs | Keep |

The 90-day setting is not a promise that every record is automatically hard-deleted
at day 90. The domain-specific retention command applies to eligible completed or
cancelled resources, while active canonical records remain until archive,
offboarding/deletion or another documented lifecycle applies. The partner-facing
notice must say this accurately.

## The owner decision

Approve all three values together unless a documented legal/partner need requires a
shorter period:

| Setting | Options | Recommendation | Why |
| --- | --- | --- | --- |
| Private-beta application retention | `30`, `90`, `180` days or `MANUAL` | **90 days** | Existing product default; enough supervised learning/review time without indefinite retention |
| Encrypted backup retention | Up to repository starting maximum of 14 days | **14 days** | Covers two weekly cycles while remaining short; pairs with daily backup, RPO 24h and quarterly/pre-partner restore drills |
| Operational log retention | Owner-selected | **14 days** | Enough for a supervised incident investigation and weekly review while limiting metadata exposure/cost |

Manual retention is not recommended: it increases the chance that old customer data
is forgotten. A longer log or backup period requires a specific purpose, updated cost
and privacy review.

## What each period covers

- **Application retention:** the organisation's explicit RevenueOS retention setting
  and the existing domain-specific maintenance jobs. Run tenant-scoped dry-run first,
  then bounded execution and object reconciliation.
- **Backup retention:** encrypted portable PostgreSQL and private-object backup
  artefacts plus approved Lightsail manual snapshots. Automatic Lightsail
  point-in-time backups retain seven days; the portable daily backup supplies the
  approved 14-day window. The backup key remains separate.
- **Operational logs:** web/API/worker/platform access and error logs, health metrics
  and alert evidence. Logs must never contain credentials, authorisation headers,
  transcripts, prompts, customer documents, CSV rows, provider bodies or full
  payloads.

Security/audit records stored inside the application follow their domain and approved
legal lifecycle, not the platform log window. Provider-side retention—especially
Clerk and OpenAI—is governed separately and disclosed in the subprocessor/AI
decisions; RevenueOS cannot delete it by rotating its own logs.

## Implementation after approval

Codex can set the organisation/default retention to 90, configure 14-day S3 and log
lifecycle rules, schedule daily tenant retention and backup checks, and use synthetic
data to prove expiry, export, deletion, backup age and restore. It must stop if a
provider cannot implement the approved periods. No existing customer data is used.

Record the three values in the [owner approval block](owner-approval-block.md). Until
then their status is **OWNER INPUT REQUIRED**.
