# WO-054 Privacy and Terms factual drafting inputs

> **HISTORICAL FACTUAL INPUT — superseded by owner-review documents.**
>
> This factual aid records the repository position as at 10 September 2026. The
> owner decided on 11 September 2026 to prepare the launch documents internally
> and deferred external legal engagement. It is not authority to publish, enable
> real customer data or activate production.

The current owner-review documents are the
[Oryntela Terms & Conditions](oryntela-terms-and-conditions.md),
[Oryntela Privacy Policy](oryntela-privacy-policy.md) and
[owner legal document review checklist](oryntela-owner-legal-document-review-checklist.md).
The `/terms` and `/privacy` routes show those drafts with noindex metadata. The
production gate remains closed until owner approval, an effective date, versions
and content fingerprints are recorded.

## Confirmed publisher facts

- Product/business name: Oryntela.
- Legal entity/holder: Management Services Australia Pty. Ltd.
- ABN: 15 113 119 556; ACN: 113 119 556.
- Privacy/support contact: `support@oryntela.com.au`.
- General contact: `hello@oryntela.com.au`.
- Initial market: Australia; canonical proposed domain: `https://oryntela.com.au`.

The owner has confirmed Management Services Australia Pty. Ltd. as the contracting
operator and publisher. No separate postal address has been added to the current
drafts; the approved support and general email contacts are used.

## Factual Privacy Notice draft

### 1. About this notice

This draft would explain how Management Services Australia Pty. Ltd., trading as Oryntela, handles information when authorised users use the Oryntela sales-work platform, website and support channels. It must receive a version, effective date and change-notice process before publication.

### 2. Information the service is designed to handle

When enabled for an organisation, Oryntela can hold identity and organisation membership references; business contact and company information; opportunities, tasks, pipeline, targets and forecasts; selling profiles and methodologies; deliberately supplied meeting, interaction, document, email and visual evidence; reviewed actions, presentations, business cases and handovers; connector configuration and encrypted provider tokens; service/security metadata; commercial state, invoices and Credit ledger metadata; and support/feedback records.

The browser sends API requests to Oryntela; it does not have privileged direct database access. Oryntela is not designed for passwords, payment-card numbers, government identifiers, medical/special-category information or unrelated personal files. Oryntela does not implicitly record or listen. Recording/capture features, where separately enabled, require an explicit user action and an approved authority/consent process.

No customer data exists at the date of this draft. Production connectors, live billing, live Prospect data and external AI are inactive. This section must be narrowed to the exact launch feature profile rather than describing disabled capabilities as active.

### 3. Collection sources and purposes

Subject to the customer's authority and the enabled profile, information may be supplied directly by an authorised user, imported through a reviewed CSV workflow, created from normal product use, obtained through an explicitly connected customer system, or obtained from a separately approved professional-data provider. Oryntela uses it to provide the selected sales workflow, maintain tenant isolation and access control, generate explicitly requested outputs, execute user-reviewed actions when enabled, reconcile provider outcomes, provide support, secure the service, meet deletion/export requests and administer the commercial relationship.

CSV contact data does not establish permission to send marketing. Engage retains suppression and review controls. Customers remain responsible for applicable authority, consent and electronic-marketing requirements; disabled providers remain blocked until their separate activation gates pass.

### 4. Disclosures and processors

Only providers actually activated for the launch should appear in the published list. Current candidates and boundaries are:

| Provider | Intended purpose | Current state | Likely location/cross-border issue to review |
| --- | --- | --- | --- |
| DigitalOcean | Sydney web/API/worker, managed PostgreSQL and private object storage | proposed; not purchased | Sydney workloads, global CDN/control-plane/support processing requires provider review |
| Clerk | identity, organisations, sessions and hosted identity email/UI | required; production instance not configured | provider locations/subprocessors and overseas disclosure |
| Stripe | hosted checkout/portal, subscription and payment metadata | test-only; live prohibited | include only if activated; Stripe handles card data on hosted surfaces |
| Microsoft | customer-authorised Outlook/Calendar actions and reconciliation | disabled | customer tenant plus Microsoft processing locations |
| Google | customer-authorised Gmail/Calendar actions and reconciliation | disabled | restricted-scope verification and cross-border processing |
| HubSpot | customer-authorised CRM sync/write-back | disabled | customer account and HubSpot processing locations |
| Salesforce | customer-authorised CRM sync/write-back | disabled | customer org and Salesforce processing locations |
| Prospect provider | business-company/person research | none selected | data provenance, opt-out, permitted disclosure and Australian privacy/direct-marketing analysis |
| OpenAI | selected evidence/intelligence processing | disabled in real-data launch profile unless separately approved | input/output retention, training setting, region and cross-border review |
| Zoho | owner-operated support/general email | active existing business email | mailbox/support correspondence processing |

Oryntela should not claim exclusively Australian data residency: even with Sydney workloads, provider CDN, identity, support, customer connectors and optional AI can process data elsewhere.

### 5. Security and access

Current controls include server-verified identity/organisation context, forced PostgreSQL RLS defence in depth, explicit tenant predicates, non-superuser runtime database access, encrypted connector-token envelopes, HTTPS-only production origins, private object storage with signed grants, bounded uploads and provider responses, metadata-only security/audit logging, suppression controls, safe public errors, and encrypted logical backup archives. These are controls, not a guarantee of absolute security.

### 6. Retention, export and deletion

The software supports an organisation retention choice of 30, 90 or 180 days; 90 days is the default configuration, not an approved universal legal policy. Different operational/commercial/audit categories can require separate treatment. Managed database backups/PITR and a separate daily encrypted database/object bundle are proposed; the latter requires an approved 14-day S3 version lifecycle. Connector tokens are revoked/disconnected through the supported workflow. Production organisation exports use tenant-scoped private object storage with authenticated 24-hour grants. Export and deletion remain operator-supervised and disabled until named-target storage, restore and deletion proof passes.

The published notice must state exact active retention periods, backup ageing, export format, deletion exceptions, commercial/accounting record treatment and how a person or organisation makes a request. It must not promise instantaneous physical erasure from backups.

### 7. Access, correction, complaints and contact

Users can correct ordinary application records through supported product/admin workflows. The owner-review Privacy Policy directs privacy access/correction, deletion/export and complaints to `support@oryntela.com.au`, explains reasonable identity/authority verification and gives the OAIC escalation route without inventing a fixed response deadline.

### 8. Cookies and website analytics

The repository does not implement a marketing analytics or advertising tracker. Clerk may use storage/cookies needed for authentication when enabled. The owner must inventory the deployed site's actual cookies, CDN logs and any future analytics before publication.

## Historical Terms drafting skeleton

> The complete owner-review Terms now supersede this skeleton.

### Known service and commercial facts

- Oryntela is a B2B sales-work platform and complements external systems of record; it is not represented as a CRM replacement in every deployment, legal adviser, financial adviser or autonomous authority.
- The current plan catalogue is Core AUD 200/month or AUD 2,000/year; Growth AUD 350/month or AUD 3,500/year; Complete AUD 500/month or AUD 5,000/year; Enterprise custom. Included users are 5, 10 and 15 respectively. The owner confirmed that the six standard amounts include GST; Enterprise GST treatment is stated in its specific Order.
- The proposed trial is 14 days of Complete access, no card, no charge and no automatic conversion. Trial start is an operator action; self-service trial enrolment is not live.
- Provider availability is conditional. Microsoft, Google, HubSpot, Salesforce, Prospect, live Stripe and production Credits are not active. The site must not promise them as immediately connected/live.
- External mutations and outreach are designed to require review/approval and use bounded queues; users remain responsible for authority, accuracy, recipient rights, sending rules and their connected accounts.
- Users must not upload credentials, card data, unlawful content, special-category data or content they lack authority to use. Oryntela does not authorise unsolicited bulk marketing.

### Topics carried into the owner-review Terms and checklist

1. Contracting entity, eligibility, authorised business users, acceptance mechanism and authority to bind an organisation.
2. Order form/plan precedence, billing timing, annual prepayment, GST/invoices, renewal, cancellation, downgrade, suspension, refunds, failed payment and price-change treatment.
3. Credit status, expiry/refund treatment, provider-error boundaries and the manual cleared-funds exception; no unapproved pack or action price is invented.
4. Customer data ownership/licence instructions, confidentiality, provider disclosures, international processing, security commitments, retention/export/deletion and backup treatment. A separate DPA is not created by this task.
5. Oryntela intellectual property, customer feedback, permitted use, account security, prohibited scraping/abuse and acceptable-use enforcement.
6. Third-party provider terms, customer connector licences, provider availability, changes and responsibility allocation.
7. AI/output review, accuracy limitations, decisions users must not delegate, and the absence of legal/financial/professional advice.
8. Service levels/support, maintenance, beta/trial limitations and changes to the service.
9. Warranties, disclaimers, liability caps/exclusions and the narrow indemnity. No insurance promise is made.
10. Termination, data retrieval/offboarding, survival and record retention.
11. Good-faith dispute process, New South Wales governing law/jurisdiction, notices, assignment, subcontracting, force majeure, severability, waiver and entire agreement.
12. Version, effective date and how material changes are notified/accepted.

## Current owner actions before publication

1. Review the ten grouped positions in the owner checklist, including the exact liability, indemnity, refund and unused-Credit treatment.
2. Confirm the exact enabled launch providers, likely overseas countries and production retention/backup settings.
3. Approve or change the complete Terms and Privacy Policy.
4. Supply the effective date; record versions and SHA-256 fingerprints in the existing release gate.
5. Implement durable Terms acceptance and separate Privacy acknowledgement evidence before trial or paid production activation.

Until those actions are complete, the public legal launch gate is **BLOCKED**. External legal review is deferred by owner and is not an active selected prerequisite.
