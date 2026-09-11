# WO-054 draft Privacy Notice and Terms inputs

> **DRAFT — OWNER/QUALIFIED REVIEW REQUIRED. NOT APPROVED FOR PUBLICATION.**
>
> This is a factual drafting aid based on the repository as at 10 September 2026. It is not legal advice, a representation of legal compliance or an instruction to enable real customer data. The public routes intentionally remain GAP pages and the production build intentionally fails until reviewed copy is committed.

Owner decision recorded 11 September 2026: the six fixed subscription prices are
GST-inclusive customer totals. Qualified review remains required, the public routes
remain GAP pages and production billing must remain disabled until approved legal copy
and a durable tax-policy reference exist. See the
[professional-review package](wo-054-privacy-terms-professional-review-package.md).

## Confirmed publisher facts

- Product/business name: Oryntela.
- Legal entity/holder: Management Services Australia Pty. Ltd.
- ABN: 15 113 119 556; ACN: 113 119 556.
- Privacy/support contact: `support@oryntela.com.au`.
- General contact: `hello@oryntela.com.au`.
- Initial market: Australia; canonical proposed domain: `https://oryntela.com.au`.

The owner must confirm the registered/principal address and whether the entity is the contracting entity and APP entity before publication.

## Factual Privacy Notice draft

### 1. About this notice

This draft would explain how Management Services Australia Pty. Ltd., trading as Oryntela, handles information when authorised users use the Oryntela sales-work platform, website and support channels. It must receive a version, effective date and change-notice process before publication.

### 2. Information the service is designed to handle

When enabled for an organisation, Oryntela can hold identity and organisation membership references; business contact and company information; opportunities, tasks, pipeline, targets and forecasts; selling profiles and methodologies; deliberately supplied meeting, interaction, document, email and visual evidence; reviewed actions, presentations, business cases and handovers; connector configuration and encrypted provider tokens; service/security metadata; commercial state, invoices and Credit ledger metadata; and support/feedback records.

The browser sends API requests to Oryntela; it does not have privileged direct database access. Oryntela is not designed for passwords, payment-card numbers, government identifiers, medical/special-category information or unrelated personal files. Oryntela does not implicitly record or listen. Recording/capture features, where separately enabled, require an explicit user action and an approved authority/consent process.

No customer data exists at the date of this draft. Production connectors, live billing, live Prospect data and external AI are inactive. This section must be narrowed to the exact launch feature profile rather than describing disabled capabilities as active.

### 3. Collection sources and purposes

Subject to the customer's authority and the enabled profile, information may be supplied directly by an authorised user, imported through a reviewed CSV workflow, created from normal product use, obtained through an explicitly connected customer system, or obtained from a separately approved professional-data provider. Oryntela uses it to provide the selected sales workflow, maintain tenant isolation and access control, generate explicitly requested outputs, execute user-reviewed actions when enabled, reconcile provider outcomes, provide support, secure the service, meet deletion/export requests and administer the commercial relationship.

CSV contact data does not establish permission to send marketing. Engage retains suppression and review controls. This draft does not decide the legal basis for electronic marketing, enrichment or every collection source; owner/qualified review must do so before those capabilities activate.

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

Users can correct ordinary application records through supported product/admin workflows. A published notice should direct privacy access/correction, deletion/export and complaints to `support@oryntela.com.au`, explain the identity/authority verification process, and state the escalation and regulator pathway approved by qualified review. No response deadline or legal entitlement is invented here.

### 8. Cookies and website analytics

The repository does not implement a marketing analytics or advertising tracker. Clerk may use storage/cookies needed for authentication when enabled. The owner must inventory the deployed site's actual cookies, CDN logs and any future analytics before publication.

## Factual Terms drafting skeleton

> **DRAFT — OWNER/QUALIFIED REVIEW REQUIRED.** The headings below separate known product facts from clauses that must not be invented by engineering.

### Known service and commercial facts

- Oryntela is a B2B sales-work platform and complements external systems of record; it is not represented as a CRM replacement in every deployment, legal adviser, financial adviser or autonomous authority.
- The current plan catalogue is Core AUD 200/month or AUD 2,000/year; Growth AUD 350/month or AUD 3,500/year; Complete AUD 500/month or AUD 5,000/year; Enterprise custom. Included users are 5, 10 and 15 respectively. The owner selected the six fixed amounts as GST-inclusive customer totals on 11 September 2026. Enterprise quotes must state their GST treatment. Qualified review must make the site, Stripe catalogue, invoices and Terms consistent without increasing the approved fixed customer totals.
- The proposed trial is 14 days of Complete access, no card, no charge and no automatic conversion. Trial start is an operator action; self-service trial enrolment is not live.
- Provider availability is conditional. Microsoft, Google, HubSpot, Salesforce, Prospect, live Stripe and production Credits are not active. The site must not promise them as immediately connected/live.
- External mutations and outreach are designed to require review/approval and use bounded queues; users remain responsible for authority, accuracy, recipient rights, sending rules and their connected accounts.
- Users must not upload credentials, card data, unlawful content, special-category data or content they lack authority to use. Oryntela does not authorise unsolicited bulk marketing.

### Clauses requiring explicit qualified drafting and owner approval

1. Contracting entity, eligibility, authorised business users, acceptance mechanism and authority to bind an organisation.
2. Order form/plan precedence, billing timing, annual prepayment, GST/invoices, renewal, cancellation, downgrade, suspension, refunds, failed payment and price-change treatment.
3. Credit pack prices, action prices, expiry/refund treatment, provider no-match/error treatment and the manual cleared-funds exception.
4. Customer data ownership/licence instructions, confidentiality, privacy roles, DPA, subprocessors, international transfers, security commitments, retention/export/deletion and backup treatment.
5. Oryntela intellectual property, customer feedback, permitted use, account security, prohibited scraping/abuse and acceptable-use enforcement.
6. Third-party provider terms, customer connector licences, provider availability, changes and responsibility allocation.
7. AI/output review, accuracy limitations, decisions users must not delegate, and the absence of legal/financial/professional advice.
8. Service levels/support, maintenance, beta/trial limitations and changes to the service.
9. Warranties, disclaimers, liability caps/exclusions, indemnities and insurance. No language is proposed here.
10. Termination, data retrieval/offboarding, survival and record retention.
11. Dispute process, governing law/jurisdiction, notices, assignment, subcontracting, force majeure, severability, waiver and entire agreement. No jurisdiction is assumed here.
12. Version, effective date and how material changes are notified/accepted.

## Minimum owner answers before publication

1. Confirm the legal contracting/APP entity, principal address and authorised legal contact.
2. Obtain qualified review of Privacy Notice, Terms, DPA/order form and electronic-marketing/enrichment position.
3. Apply the owner-selected GST-inclusive treatment consistently to the website,
   Stripe catalogue, tax invoices and Terms after qualified review; the fixed customer
   totals must not increase.
4. Approve the actual V1 feature/provider list and each subprocessor/cross-border disclosure; remove inactive providers from public claims.
5. Approve category-specific retention, database and object-backup retention, export/deletion treatment and any accounting-record exception.
6. Approve customer authority/consent evidence for transcripts, recordings, imported contacts, email/calendar/CRM connections and outreach.
7. Approve the trial, subscription renewal/cancellation/refund and Credit-pack/action policies.
8. Approve complaint, incident and suspected-breach escalation, including when qualified legal advice is obtained.
9. Supply approved version/effective dates and publication/change-notice process.

Until all answers are resolved and approved copy replaces the GAP pages, the public legal launch gate is **BLOCKED**.
