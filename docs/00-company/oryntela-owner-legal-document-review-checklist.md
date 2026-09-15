# Oryntela owner legal document review checklist

- **Status:** OWNER APPROVED — PRODUCTION PUBLICATION AUTHORISED
- **Prepared:** 11 September 2026
- **Final owner approval:** 15 September 2026
- **Operator:** Management Services Australia Pty. Ltd., ABN 15 113 119 556
- **External legal review:** deferred by owner; none requested or performed
- **Documents:** [Oryntela Terms & Conditions](oryntela-terms-and-conditions.md) and [Oryntela Privacy Policy](oryntela-privacy-policy.md)
- **Effective date/version:** `2026-09-15`

Kevin approved these ten grouped substantive positions on 11 September 2026. On 15 September 2026, after reviewing the exact PR #88 documents, Kevin approved both complete documents with effective date and version `2026-09-15` and authorised production publication. That final approval does not authorise customer billing, Credits, checkout or a real charge. Fixed owner facts such as the Oryntela name, operator, GST-inclusive plan amounts, user limits, trial and plan-change mechanics are not reopened here.

| # | Consequential decision | Draft position | Owner decision |
| -: | --- | --- | --- |
| 1 | Subscription, renewal, cancellation and payment | Monthly and annual Subscriptions automatically renew for the same interval unless cancelled. Annual plans are one annual prepayment. Cancellation stops the next renewal and takes effect at period end; it does not automatically refund an unused annual portion. Upgrades are immediate after provider confirmation with provider-calculated proration where applicable; downgrades and same-tier interval changes apply next renewal. A past-due state may temporarily retain access during provider recovery, but persistent or terminal non-payment may restrict or suspend paid functionality without deleting data. Future standard price changes apply only from a renewal after reasonable notice. Excess users after downgrade must be resolved, not silently deleted. | APPROVED — 11 Sep 2026 |
| 2 | Refunds | Subscription fees and purchased Credits are generally non-refundable after payment, including change-of-mind or part-period cancellation, except where required by law, expressly agreed by Oryntela, or provided by a specific written arrangement. If Oryntela discontinues the Service and terminates without Customer breach, it refunds the unused prepaid Subscription portion. Australian Consumer Law rights are preserved. | APPROVED — 11 Sep 2026 |
| 3 | Credits | Credits are usage units, not money, and cannot be cashed out or transferred between organisations without written agreement. Purchased Credits are granted only after verified cleared payment and do not expire while the account retains eligible active access. Promotional/trial Credits may have disclosed limits, conditions and expiry. No normal post-paid negative balance or automatic top-up exists. On final Customer-caused or Customer-elected account termination, unused Credits cease to be usable without cash redemption except where law or a written agreement requires otherwise; if Oryntela discontinues the Service without Customer breach, it provides a reasonable remedy for unused purchased Credits. | APPROVED — 11 Sep 2026 |
| 4 | AI, generated material and Customer responsibility | AI output and system inference can be incomplete, inaccurate and non-unique and require review appropriate to the use. The Customer is responsible for final decisions, external material and commercial commitments. Oryntela is sales software, not legal, financial, tax, accounting, HR, regulatory or other professional advice. AI has no authority to bind the Customer. Use rights in outputs remain subject to law and third-party rights, with no promise of universal copyright ownership or exclusivity. | APPROVED — 11 Sep 2026 |
| 5 | Customer Data, authority, outreach, providers and Privacy | The Customer owns its underlying Customer Data and grants only the limited rights needed to host, copy, process, transmit, display, analyse and transform it to operate, secure and support Oryntela. Customers must have authority for CRM, contact, mailbox, calendar, document, prospect and other connected data. They remain responsible for recipient selection, consent or lawful basis, content, suppression/unsubscribe and applicable outreach laws. Oryntela does not sell personal information, train a general-purpose model on identifiable Customer Data under the current policy, or use a Customer’s name/logo/testimonial without permission. Provider and integration availability is conditional; the Customer maintains its own third-party licences. Application retention is 90 days for retention-eligible content—not a universal deletion promise—and the independent encrypted backup rotation is 14 days. | APPROVED — 11 Sep 2026 |
| 6 | Acceptable use, service availability and suspension | Illegal use, fraud, harassment, malicious activity, rights infringement, unauthorised data, security attacks, credential/limit circumvention, unlawful outreach and abusive automation are prohibited. Oryntela provides reasonable published-channel support, no 24/7 promise and no SLA unless agreed in writing. Maintenance, third-party outages and incidents can affect availability. Suspension is proportionate for non-payment, material breach, illegal/abusive use or security risk, with notice and a remedy opportunity where reasonable and immediate action for urgent risk. | APPROVED — 11 Sep 2026 |
| 7 | Termination, export, governing law and disputes | Material breach generally receives a reasonable remedy opportunity; serious, unlawful, fraudulent, insolvent or irremediable conduct may justify immediate termination. Oryntela may discontinue for operational reasons with reasonable notice, unused-fee/Credit remedies where the Customer is not in breach, and no punitive fee. Customers receive a reasonable supported export opportunity where account state and security permit; retention is not indefinite and upstream third-party deletion is not promised. New South Wales law applies, with good-faith senior escalation before litigation while preserving urgent relief, limitation periods and statutory complaint rights. | APPROVED — 11 Sep 2026 |
| 8 | Confidentiality and intellectual property | Mutual confidentiality covers non-public business, technical and Customer information, uses reasonable protection, permits need-to-know service operation and lawful disclosure, and contains standard lawful-known/public/independent/third-party exceptions. It continues while information is confidential and protects trade secrets while they remain trade secrets. Oryntela retains platform IP; the Customer retains Customer Data and pre-existing IP. Feedback may be used to improve Oryntela but does not transfer unrelated Customer IP. | APPROVED — 11 Sep 2026 |
| 9 | Liability | Subject to non-excludable law, fraud and wilful misconduct, each party’s aggregate liability across all claims is capped at the greater of (a) fees paid or payable by the Customer during the 12 months immediately before the event giving rise to the first claim and (b) AUD $1,000. The AUD $1,000 floor avoids a zero cap for trials, promotional use and short payment history. Indirect/consequential loss is excluded to the extent permitted, with direct reasonably foreseeable loss preserved. Payment obligations are outside the damages cap. | APPROVED — 11 Sep 2026 |
| 10 | Indemnity | The Customer indemnity is limited to third-party claims caused by unlawful Customer use, infringing Customer Data/instructions, or material breach of data-authority, outreach or prohibited-conduct duties. It is reduced for Oryntela contribution, includes defence controls, is not an ordinary-use indemnity and is included within the aggregate liability cap except for fraud, wilful misconduct or liability that cannot lawfully be limited. | APPROVED — 11 Sep 2026 |

## Privacy facts reconciled after substantive approval

The owner approved the retention and provider-list principle on 11 September 2026. The production evidence was then reconciled as follows:

1. DigitalOcean hosts the production application, PostgreSQL database and private object storage in Sydney; AWS holds the independent encrypted backup in Sydney; Clerk provides production identity; Zoho provides business/support email; and Stripe is activated for future payments but customer billing remains disabled. Provider support, control-plane and subprocessor activity can occur outside Australia.
2. OpenAI, Prospect providers, Microsoft 365, Google Workspace, HubSpot and Salesforce are disabled for production and are not represented as receiving production Customer Data.
3. The application setting is 90 days for retention-eligible content, not every record or legal/accounting/security evidence. The independent encrypted backup rotation is 14 days.

## Terms acceptance implementation

PR #89 implemented durable organisation-scoped Terms acceptance and Privacy Policy presentation. The 15 September 2026 owner approval unlocks that path in production only for the exact versioned and fingerprinted release recorded below.

The implemented path:

- show the effective Terms, Privacy Policy, pricing, renewal and cancellation information before trial activation and paid checkout;
- require the organisation representative to affirm authority and accept the Terms before trial or paid activation;
- store an append-only tenant-scoped record containing Terms version, effective date, acceptance timestamp, accepting user, organisation and acceptance surface or Order reference;
- record Privacy Policy version and acknowledgement timestamp separately from contractual acceptance where acknowledgement is required;
- block activation when the required current record is absent and preserve prior records after document updates; and
- test cross-organisation denial, idempotency, version changes, audit minimisation, keyboard use and safe failure.

This does not create a legal-document management system. Live checkout remains disabled under the separate billing gate even after the approved legal release is committed and verified against the acceptance registry.

## Final owner publication approval

Kevin personally approved the exact PR #88 Terms and Privacy Policy text on 15 September 2026, selected effective date `2026-09-15`, and authorised production publication. The release binds:

- Terms version `2026-09-15`, SHA-256 `0c4fea346d5f4774a92819b1a8be1e83dcb1289d2650acce0bafc5f400cea3f7`;
- Privacy version `2026-09-15`, SHA-256 `c707fa92f6dcd2dd4657a60fe96dce9f04bd805a15112cd224fa740fbc6cc1d5`; and
- public `/terms` and `/privacy` routes to the same canonical Markdown bytes packaged in the web release.

Publication and Terms-acceptance proof must use this exact identity. Billing and Credits stay disabled; customer checkout and real charges require a separate explicit owner gate.
