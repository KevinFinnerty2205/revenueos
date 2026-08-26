# Campaign quotas and cost controls

WO-030 uses deterministic local composition and Mock Email; it creates no AI/provider
cost. Limits nevertheless protect safety, database work and future adapters:

| Control | Private-beta value |
| --- | ---: |
| selected Contacts per campaign | 50 |
| enabled steps | 1–4 |
| active campaigns per owner | 5 |
| active campaigns per organisation | 10 |
| prepared Campaign drafts per organisation/day | 100 |
| recipient launch spacing | 5 minutes |
| step wait | 0 first; 1–30 days later |

Existing outreach policy additionally applies per-user and per-organisation daily
send limits and global Contact cooldown across one-to-one and Campaign activity.
Quota/cooldown outcomes are `deferred`, not silently dropped and not treated as
permanent audience ineligibility. Recovery always recalculates a safe window and does
not burst overdue work.

Limits live in server settings and database checks where stable. They are not client
trust boundaries. Raising them or adding paid generation/delivery requires a new
security/cost review and explicit approval.
