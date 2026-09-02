# Checkpoint 3 post-WO-039C readiness decision

Date: 1 September 2026 (Australia/Sydney)
Decision: **GO WITH RESTRICTIONS — supervised real-data design partner only**
WO-040: **not authorised**

## Entry criteria reconciliation

| Criterion | Before WO-039C | After WO-039C | Proof | Remaining owner action | Blocker? |
| --- | --- | --- | --- | --- | --- |
| Production identity and invite-only tenancy | JIT tenant/member creation | Deliberate idempotent provision; production JIT rejected | Auth/operations tests and runbook | Target Clerk cookie/session/revoke evidence | Yes until target proof |
| Production configuration | Partial fail-closed | Real-data mode validates auth, PostgreSQL, HTTPS origins/hosts, logging, storage, providers, approval/contact | Configuration matrix and preflight | Supply real secret-manager values | Yes until pass |
| Tenant isolation | Forced RLS in schema | Runtime-role/BYPASSRLS and transaction-reset preflight; new tables covered | PostgreSQL RLS/migration suite | Capture target role output | Yes until pass |
| Backup/recovery | Documentation only | Encrypted database/object commands, manifest verification and isolated restore guards | Backup tests and synthetic drill | Target managed restore/RPO/RTO measurement | Yes until pass |
| Retention/export/deletion | Broad v28 lifecycle | v29 includes import/merge/provision metadata; preview expiry and deletion graph extended | Export/retention/deletion tests | Approve backup/log retention | Yes until approved |
| Provision/offboard/support | Manual/incomplete | Commands, admin lifecycle, tenant/queue/support reports and incident playbooks | Operations tests/runbook | Name contacts and escalation | Yes until supplied |
| Dependency security | Older cryptography line | Supported 50.0.1 line with regressions | Lock/audit/full API gate | Monitor future advisories | No |
| Provider/legal governance | Unrecorded | Real-data/external-AI gates and explicit matrix | Config tests/operating model | Counsel/owner approvals per partner | Yes until approved |
| Native onboarding | Manual creation | Bounded preview/confirm import, templates and supervised flow | API/UI tests | Supervise subset-first import | No after gates |
| Duplicate remediation | Direct database surgery | Human-reviewed Account/Contact merge with tombstone | Merge API/UI/RLS tests | Admin review | No after gates |
| External research/mail | No real provider | Still disabled and accurately labelled | Feature matrix/config | Separate future work order | No for Native-CRM restricted cohort |

## Status by release level

- Synthetic demo: **READY**.
- Supervised synthetic partner: **READY**.
- Supervised real-data design partner: **READY WITH RESTRICTIONS**, only after every `Yes until` partner/environment gate above is evidenced.
- Unsupervised beta: **NO-GO**.
- Commercial beta: **NO-GO**.

Checkpoint 3 remediation across WO-039A, WO-039B and WO-039C is **complete at repository level**. It does not transform absent legal or target-environment evidence into approval. Any named partner is **NO-GO** until its evidence pack is signed and production preflight/restore drill pass.

## First-partner launch-gate update

The 2 September 2026
[first-design-partner launch package](first-design-partner/first-design-partner-launch-gate.md)
is the controlling reusable operational record. Its current highest-level state is
**WAITING FOR TARGET ENVIRONMENT PROOF**. A named partner has not been selected;
target Clerk/session, RLS, runtime-role, backup/restore/Create, monitoring and
offboarding drills have not run; and legal/privacy/AI/feature-profile approvals have
not been provided. These are expected launch-time dependencies, not evidence that
WO-039C repository remediation is incomplete.

It is appropriate to seek/select a design partner for discovery and agreement now,
but no partner data may be requested, received, previewed or entered until the exact
target/partner profile passes the package and is signed. WO-040, Gmail and Apollo
remain unauthorised.

## Residual restrictions and rollback

Tenants are manually provisioned and support is supervised. Live Prospect and mailbox delivery are unavailable. HubSpot and external AI are separately disabled unless explicitly approved. No enterprise SSO/SCIM, legal hold, contractual SLA or high-availability claim exists. Local storage is never the production binary profile.

Rollback disables the affected server flag and worker claims, redeploys the last compatible web/API/worker release, keeps the forward schema where possible and verifies readiness/RLS with synthetic data. Downgrading `0050` is data-destructive for WO-039C metadata and requires backup plus explicit approval.
