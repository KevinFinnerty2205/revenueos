# First supervised real-data design-partner launch gate

- **Gate date:** 2 September 2026; commercial consolidation reviewed 4 September 2026 (Australia/Sydney)
- **Current documentation branch:** `docs/oryntela-product-commercial-consolidation`
- **Reviewed repository baseline:** `daedbbc`
- **Repository baseline:** WO-039A, WO-039B and WO-039C are on `main`; the single Alembic head is `0050_real_data_operations`
- **Current launch decision:** **WAITING FOR TARGET ENVIRONMENT PROOF**
- **Scope:** one named, supervised, Native CRM design partner; no Gmail, Apollo, live Prospect provider, live email or autonomous external execution

This is the controlling launch record. It turns the repository-level **GO WITH RESTRICTIONS** decision into a reusable, partner-specific release gate. It does not approve a deployment, legal position, provider or customer-data use.

The [Oryntela commercial-product handoff](../oryntela-commercial-product-handoff.md)
consolidates brand and commercial hypotheses without changing this gate. The
current launch decision remains **WAITING FOR TARGET ENVIRONMENT PROOF**.

The 2 September 2026 owner/target preparation reduces the remaining business input
to the [authoritative eight-decision register](owner-decision-register.md), recommends
one [primary target and one alternative](private-beta-target-environment-options.md),
and provides one [owner approval block](owner-approval-block.md). This preparation
does not change the current launch decision: no owner response, target selection,
spend, provider or real-data use has been approved.

## Named launch identity

Complete this before any final drill. An abstract customer cannot pass this gate.

| Field                                     | Required value                                                      | Current status                                 |
| ----------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------- |
| Design partner legal and trading name     | Owner-approved name                                                 | **WAITING FOR PARTNER**                        |
| Partner accountable administrator         | Name, business email and role                                       | **WAITING FOR PARTNER**                        |
| Deployment environment and public origins | Platform/project, region, web origin and API origin                 | **WAITING FOR TARGET**                         |
| Immutable release                         | Commit SHA and image/build identifiers                              | **WAITING FOR TARGET**                         |
| CRM mode                                  | `native`                                                            | **RECOMMENDED; PARTNER CONFIRMATION REQUIRED** |
| Feature profile                           | Signed copy of [the approved profile](real-data-feature-profile.md) | **OWNER AND PARTNER APPROVAL REQUIRED**        |
| Hosting/storage configuration             | Database, private object storage, backups, logs and regions         | **WAITING FOR TARGET**                         |
| AI configuration                          | Disabled profile or approved provider/model/data-flow profile       | **OWNER AND PARTNER APPROVAL REQUIRED**        |
| Evidence location                         | Access-restricted launch record or ticket                           | **WAITING FOR TARGET**                         |

Use only these evidence states: `PASS`, `FAIL`, `OWNER APPROVAL REQUIRED`, `PARTNER APPROVAL REQUIRED`, `WAITING FOR TARGET`, `WAITING FOR PARTNER` or `NOT APPLICABLE — APPROVED REASON`. Repository code or a local test cannot turn an environment, legal or partner item into `PASS`.

## Launch checklist

### Repository ready

| Check                                                 | Status                       | Evidence                                                                                                                                                           |
| ----------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Requested branch started clean from `main`            | **PASS**                     | Git inspection at gate start; no branch was created or changed                                                                                                     |
| WO-039A, WO-039B and WO-039C are on `main`            | **PASS**                     | Merge commits `558795c`, `5f0a61c` and `93c386e`                                                                                                                   |
| One Alembic head: `0050_real_data_operations`         | **PASS**                     | Migration chain and WO-039C migration tests                                                                                                                        |
| Production build and complete repository gate         | **PASS AT WO-039C BASELINE** | [WO-039C validation record](../../07-sprints/wo-039c-real-data-operations.md#frozen-validation-gate); this documentation branch must also pass its required checks |
| Production preflight command                          | **PASS**                     | `revenueos-operations production-preflight` exists and fails closed                                                                                                |
| Forced RLS and runtime-role requirements              | **PASS — REPOSITORY ONLY**   | All-table PostgreSQL proof and non-bypass preflight exist; target repetition is separate                                                                           |
| Encrypted database/object backup and isolated restore | **PASS — REPOSITORY ONLY**   | AES-256-GCM backup/verify/restore tooling and synthetic local drill exist                                                                                          |
| Organisation/member provisioning and disablement      | **PASS — REPOSITORY ONLY**   | Idempotent operator commands and access-denial tests exist                                                                                                         |
| Export, retention and organisation deletion           | **PASS — REPOSITORY ONLY**   | Export v29 and tenant-scoped maintenance/deletion paths exist                                                                                                      |
| Native CRM import and Account/Contact merge           | **PASS — REPOSITORY ONLY**   | Bounded preview/confirm import and deliberate merge exist                                                                                                          |
| Create private files and downloads                    | **PASS — REPOSITORY ONLY**   | Validated PPTX output and authenticated one-time download grants exist                                                                                             |
| Feature kill switches and safe inventory              | **PASS — REPOSITORY ONLY**   | Server-authoritative flags are returned by `safe_feature_flags()`                                                                                                  |
| Dependency audits                                     | **PASS AT WO-039C BASELINE** | Production JavaScript/Python audits were green; rerun for the release SHA                                                                                          |

### Target environment ready

Every row is currently **WAITING FOR TARGET**. The operator must complete the [target preflight](target-environment-preflight-checklist.md), [Clerk/session proof](Clerk-session-proof-procedure.md), [target RLS proof](target-RLS-proof-procedure.md), [backup/restore drill](named-target-backup-restore-drill.md), [support/monitoring gate](support-monitoring-launch-checklist.md) and [offboarding proof](offboarding-proof-checklist.md). A pass requires the exact named environment, release, partner, feature profile, CRM mode, storage and AI configuration.

### Owner/legal approval required

Every item in the [legal and owner checklist](legal-owner-approval-checklist.md) is blocking and currently **OWNER APPROVAL REQUIRED**. The repository contains technical guidance, not approved Privacy Terms, Terms of Use, a DPA, a subprocessor schedule or legal certification. The owner must also approve the AI processing profile, hosting/data locations, support route, retention/backup periods and exact feature profile.

Use the [owner decision register](owner-decision-register.md) as the single question
surface and the [owner approval block](owner-approval-block.md) as the response. The
detailed [target options](private-beta-target-environment-options.md),
[cost model](target-environment-cost-model.md),
[OpenAI decision](first-partner-openai-decision.md),
[subprocessor register](first-partner-subprocessor-register.md),
[retention recommendation](first-partner-retention-decisions.md) and
[contact requirements](first-partner-support-contact-requirements.md) support those
eight choices; they are not independent approvals.

### Design-partner approval required

Before upload, the named partner must:

- sign or otherwise complete the owner-approved beta agreement and data-processing terms;
- nominate an accountable administrator and authorised source-data owner;
- approve the exact feature profile, CRM mode, retention and support/escalation route;
- confirm CSV authority, mappings, owners, stages, currency, duplicates and the data subset;
- accept that an imported email is not permission to contact and no historical stage dates will be fabricated;
- acknowledge the [data boundary](partner-data-boundary.md), AI/provider data flow if enabled, hosting/data locations and subprocessors; and
- approve the small-subset results before the larger import.

All are currently **WAITING FOR PARTNER**.

## Concise operator runbook

### Before

1. Obtain a completed owner approval block. If target setup is `NO`, stop. Do not
   convert recommendations into owner facts.
2. Name the partner, target, release, CRM mode, feature profile, storage and AI configuration in this record.
3. Obtain every owner/legal and partner approval; link the evidence without copying secrets or customer content.
4. Run the target preflight, Clerk/session matrix and target RLS drill with synthetic tenants.
5. Run the encrypted database/object backup and isolated restore drill, including a generated synthetic Create presentation.
6. Prove support, monitoring and complete synthetic offboarding. Resolve every `FAIL`; no risk acceptance is implied by supervision.
7. Hold a go/no-go review. Only the owner, security/operations lead and partner administrator may authorise real-data entry.

### Onboard

1. Provision the approved Clerk organisation and first admin with the idempotent operator command.
2. Verify login, organisation, admin permission, timezone, retention, Native CRM and exact flags.
3. Review the data boundary and mappings with the partner.
4. Import only 5 Accounts, about 10 Contacts and about 5 open Opportunities.
5. Review duplicates, suppression/contactability, Pipeline, Search and record links. Confirm no historical stage data was invented.
6. Obtain written partner confirmation, then import the approved larger set under supervision.
7. Reconcile totals and take a verified post-import backup.

### During

1. Monitor public health, database, worker, storage, backup and retention signals using content-safe metadata.
2. Use request IDs and `support-bundle`; never copy transcripts, prompts, CSV rows, customer documents or provider payloads into tickets.
3. Review backups daily, support issues continuously during agreed hours and partner feedback at Day 1, Week 1, Week 2 and Month 1.
4. Apply the [immediate pause criteria](launch-pause-criteria.md) without waiting for commercial approval.

### Offboard

1. Verify authority and generate/deliver an approved export if requested.
2. Disable Clerk and RevenueOS access; invalidate grants and contain eligible queued work.
3. Revoke/disable any approved connection. No connector is expected in the recommended Native CRM profile.
4. Execute exact-confirmation organisation deletion.
5. Verify database rows, blobs, grants, APIs/search/deep links and worker discovery are absent.
6. Record backup expiry and metadata-only completion; do not claim immediate deletion from immutable backups.

## Decision rule

Stop immediately on any technical `FAIL`. If technical proof passes but owner/legal approval is absent, the state is **WAITING FOR OWNER/LEGAL APPROVAL**. If both pass but partner approval is absent, the state remains **WAITING FOR PARTNER** and no data may enter. `API_PRIVATE_BETA_REAL_DATA_ENABLED=true` is never approval by itself.

The present highest-level state is **WAITING FOR TARGET ENVIRONMENT PROOF** because
the owner approval block is blank and no target deployment or named-target drill
evidence exists. It is appropriate to seek and select the first design partner now
against the [approved target profile](first-design-partner-profile.md) for discovery,
agreement and fit only, but not to accept, copy or preview their real data until this
record is fully signed.

## Package

- [Owner decision register](owner-decision-register.md)
- [Private-beta target-environment options](private-beta-target-environment-options.md)
- [Target-environment cost model](target-environment-cost-model.md)
- [First-partner OpenAI decision](first-partner-openai-decision.md)
- [First-partner subprocessor register](first-partner-subprocessor-register.md)
- [First-partner retention decisions](first-partner-retention-decisions.md)
- [First-partner support/contact requirements](first-partner-support-contact-requirements.md)
- [Ideal first design-partner profile](first-design-partner-profile.md)
- [First design-partner commercial model](first-design-partner-commercial-model.md)
- [Owner approval block](owner-approval-block.md)
- [Target-environment preflight](target-environment-preflight-checklist.md)
- [Clerk/session proof](Clerk-session-proof-procedure.md)
- [Target RLS proof](target-RLS-proof-procedure.md)
- [Named-target backup/restore drill](named-target-backup-restore-drill.md)
- [Legal/owner approval](legal-owner-approval-checklist.md)
- [Real-data feature profile](real-data-feature-profile.md)
- [AI processing gate](AI-real-data-processing-gate.md)
- [Native CRM onboarding](Native-CRM-first-partner-onboarding.md)
- [Partner data boundary](partner-data-boundary.md)
- [Partner getting started](partner-facing-getting-started.md)
- [Support/monitoring gate](support-monitoring-launch-checklist.md)
- [Offboarding proof](offboarding-proof-checklist.md)
- [Feedback plan](first-partner-feedback-plan.md)
- [Launch pause criteria](launch-pause-criteria.md)
- [Post-partner roadmap decision](post-partner-roadmap-decision.md)
