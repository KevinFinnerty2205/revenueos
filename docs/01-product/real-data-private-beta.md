# Supervised real-data private beta

Status: implementation complete; partner launch remains approval-gated. This operating model does not authorise an unsupervised or commercial beta.

## Operating model

RevenueOS may accept real sales data only for a named design partner after the partner-specific launch record is complete. An operator provisions the organisation and first administrator; public tenant creation and production just-in-time membership creation are disabled. Onboarding is supervised, Native CRM is the default data path, and every add-on is explicitly selected.

The partner starts with a small synthetic or approved subset, then imports Accounts, Contacts and open Opportunities. RevenueOS does not treat an imported email as permission to contact, does not create Evidence or intelligence from CSV, and does not reconstruct historical pipeline events. A current imported stage is marked `import_baseline`; reliable time-in-stage begins only after a later RevenueOS transition.

## Capability matrix

| Capability | Supervised real-data state | Required gate |
| --- | --- | --- |
| Accounts, Contacts, open Opportunities, Pipeline | Available | Native CRM flag and tenant entitlement; admin-reviewed import |
| CRM duplicate merge | Available for Accounts and Contacts | Admin, Native CRM, explicit preview/conflict choices |
| Tasks, Interactions, methodology, Targets, Forecast, Manager | Available | Corresponding server flag; no synthetic provider presented as real |
| Evidence, Ask, Revenue Brain, Companion, Create | Conditional | Approved real-data AI/provider and storage profile, or disabled |
| Prospect live research | Unavailable | No approved live provider exists |
| Engage live mailbox delivery and Campaign sending | Unavailable | No Gmail/mailbox provider exists; CSV never grants consent |
| HubSpot | Conditional and off by default | Named target OAuth/security/rotation/reconciliation approval |
| Recording/transcription/live processing | Off in the restricted profile | Separate consent, storage and external-processing approval |
| Organisation export/deletion | Operator-supervised | Admin request, exact confirmation and post-operation verification |

Every high-risk capability has a server-authoritative flag. Disabling a flag prevents new use without deleting customer history. The deployment remains one web app, one API, PostgreSQL, private object storage and supervised workers; no generic admin console, ETL platform or workflow engine is introduced.

## Partner prerequisites

Before real data enters the product, the owner must record the approved legal entity, privacy notice/terms and data-processing terms, support and incident contacts, hosting/data locations, subprocessors, retention/backup period, AI processing decision and the partner's permitted feature profile. `API_PRIVATE_BETA_REAL_DATA_ENABLED` is not an approval substitute: the production preflight also requires an owner-controlled approval reference and support address.

Permitted data is ordinary business contact, sales-interaction, commercial and deliberately supplied sales-document data needed for the agreed use. Payment-card data, credentials, government identifiers, medical/special-category data and unrelated personal files are prohibited.

For Australia-first partners, counsel/owner review must determine Privacy Act/APP coverage, overseas disclosure and processor terms. The incident plan must assess the Notifiable Data Breaches scheme rather than assume a deadline or outcome. Live electronic marketing remains disabled; any future delivery must independently satisfy consent, sender-identification and unsubscribe obligations. See the current [OAIC APP guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines), [OAIC NDB guidance](https://www.oaic.gov.au/privacy/notifiable-data-breaches/quick-reference-guide-for-responding-to-data-breaches) and [ACMA spam guidance](https://www.acma.gov.au/avoid-sending-spam). This is an operational checklist, not legal advice or certification.

## First onboarding sequence

1. Approve the named partner and release profile; pass production preflight and the current restore-drill gate.
2. Provision the organisation and first admin with an idempotency key; select timezone, retention, Native CRM and add-ons.
3. Verify Clerk login, admin/member boundaries, tenant preflight, support route and backup schedule.
4. Configure a pipeline. Import a reviewed subset (suggested: five Accounts, ten Contacts and five open Opportunities) using explicit mappings.
5. Review duplicate/invalid summaries. Confirm only rows marked new. Merge exceptions one pair at a time when the provenance rules allow it.
6. Verify Accounts, Contacts, Pipeline, imported baseline copy and lack of contact permission. Train the partner on Home, Interactions, Sales Brain, Opportunity, Pipeline, Insights and Forecast only as enabled.
7. Expand the import under supervision; capture request IDs and counts, never CSV values, in the evidence record.

Offboarding is export-if-requested, access disable, connector revoke/disable, queue containment, exact-confirmation deletion, database/object/grant verification and a metadata-only completion record. Operational data is deleted when the workflow completes; encrypted backups age out under the approved backup retention window and are not falsely described as immediately physically erased.
