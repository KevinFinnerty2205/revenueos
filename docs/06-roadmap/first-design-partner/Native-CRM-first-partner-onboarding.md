# Native CRM first-partner onboarding

Status: **WAITING FOR PARTNER AND TARGET**. This is the exact supervised operator/admin procedure. No real CSV may be requested, received, previewed or stored until every launch gate passes.

## Before the session

- Record the named partner, authorised administrator, target, release, Native CRM mode, approved feature/AI profile, timezone, retention, support route and data owner.
- Obtain the partner's confirmation of CSV authority and the [data boundary](partner-data-boundary.md).
- Confirm the source export contains only supported business data and open Opportunities; remove unsupported/sensitive columns before transfer.
- Agree secure transfer and deletion of the source CSV. The RevenueOS importer does not persist raw CSV, but the operator must also remove any transfer copy under the agreed process.
- Prepare separate UTF-8 comma CSVs for Accounts, Contacts and open Opportunities. XLS/XLSX, archives, delimiter guessing and transformations are unsupported.

## Provision identity and organisation

RevenueOS provisioning needs the exact Clerk organisation and user IDs. Therefore create the approved Clerk organisation, issue the first-admin invitation and verify the business identity before running the RevenueOS command. Public organisation creation and production JIT provisioning remain disabled.

```sh
revenueos-operations provision-organisation \
  --external-organisation-id <clerk-org-id> \
  --organisation-name <approved-partner-name> \
  --timezone <approved-IANA-timezone> \
  --admin-external-user-id <clerk-user-id> \
  --admin-email <verified-business-email> \
  --admin-display-name <approved-name> \
  --idempotency-key <non-secret-ticket-random-reference> \
  --operator-reference <operator-or-change-id> \
  --crm-mode native \
  --retention-days <30-or-90-or-180> \
  --confirm "PROVISION <clerk-org-id>"
```

Add `--enable-addon create` only when the signed profile includes Create. Do not enable Prospect or Engage. Repeating identical input must return `already_applied`; a reused key with changed input must fail.

Then:

1. sign in as the first admin and verify the public origin, exact organisation and admin-only Settings access;
2. acknowledge the current approved data notice;
3. verify timezone and retention against the signed record;
4. run `revenueos-operations tenant-preflight --organisation-id <uuid>` and require `ready`;
5. compare `production-preflight` flags with the signed profile; and
6. configure and review the Native Pipeline before importing Opportunities.

## Data mapping review

The partner data owner and operator review and sign:

| Decision | Required confirmation |
| --- | --- |
| Source authority | Export is from an authorised business system and approved for RevenueOS |
| Data minimisation | Only Accounts, business Contacts and open Opportunities needed for the pilot are included |
| Account mapping | Name required; domain/website/industry/location only when supported and necessary |
| Contact mapping | Business name/email and deliberate Account reference; no private profile or unrelated personal fields |
| Opportunity mapping | Account, active owner, Pipeline/stage, amount, ISO currency, expected close date; open only |
| Owner mapping | Every source owner maps to an active same-tenant member; unowned/unknown rows are resolved before confirm |
| Stage mapping | Every source stage maps to the configured active Native Pipeline; current stage only |
| Currency | ISO currency reviewed; no silent conversion or mixed-currency aggregation |
| Duplicates | Exact strong matches skip; possible duplicates are reviewed; no fuzzy auto-merge |
| Contact restrictions | `do_not_contact=true` may add restriction; `false` never removes one; imported email grants no permission |
| History | Import creates one `import_baseline`; it does not fabricate previous stages or time-in-stage |

## Small-subset import

Import in dependency order:

1. **Accounts:** preview exactly 5 representative Accounts. Map every header explicitly or set it to ignored. Resolve all errors and strong/possible duplicates. Confirm only approved new rows.
2. **Contacts:** preview about 10 Contacts attached to the reviewed Accounts. Verify business email, Account link and `do_not_contact` meaning. Confirm only approved rows.
3. **Open Opportunities:** preview about 5 open Opportunities. Verify Account, owner, Pipeline/stage, amount, currency and close date. Confirm only approved rows.

The preview stores fingerprints, counts, row numbers/dispositions, safe issue codes and resulting IDs only. Confirm must resend the same bytes/mapping and match the batch fingerprints. Do not email screenshots containing CSV rows or paste row content into support tickets. There is no import rollback; use preview, a backup and containment instead of casual confirmation.

## Acceptance before larger import

The partner admin completes these tasks without engineering/database intervention:

- find every sample Account, Contact and Opportunity through navigation and Search;
- verify Account ↔ Contact ↔ Opportunity links and owners;
- confirm Pipeline totals/stages/amounts and currency separation;
- inspect duplicate states and use one deliberate Account or Contact merge only if needed;
- confirm imported Contacts remain `permission not assessed`/suppressed as applicable;
- create one deliberate Interaction and inspect the enabled Sales Brain workflow;
- confirm no historical stage date/time-in-stage was inferred; and
- sign the sample counts, discrepancies and approval to continue.

Any unexplained count, cross-link, amount/currency, owner, suppression, provenance or stage-history issue stops onboarding.

## Larger import and completion

1. Agree the next bounded batch; never exceed 5 MB, 5,000 rows or 100 columns per file.
2. Repeat preview, mapping review, duplicate review and explicit confirm for Accounts, then Contacts, then open Opportunities.
3. Reconcile source accepted/skipped/blocked counts to RevenueOS records, Pipeline totals, owner totals and currencies. Record counts only.
4. Remove transfer copies of the CSV under the approved process and record deletion; RevenueOS retains no raw CSV.
5. Run tenant preflight, queue status and a content-safe support bundle.
6. Take and verify the approved post-import encrypted database/object backup.
7. Record the partner administrator's final acceptance and the first feedback session date.

No unsupervised bulk migration, direct database correction, fuzzy auto-merge, historical stage reconstruction, closed-Opportunity import, permission inference or Gmail/Apollo/provider enrichment is allowed.
