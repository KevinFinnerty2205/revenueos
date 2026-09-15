# Oryntela legal production gate

- **Checked:** 15 September 2026 (Australia/Sydney)
- **Stripe control-plane update:** 15 September 2026 (Australia/Sydney)
- **Terms/Privacy state:** exact final text owner-approved; version/effective date `2026-09-15`; production publication authorised
- **External legal engagement:** none, by owner decision
- **Production state:** core infrastructure active; customer billing, customer data
  and public launch not activated; no Stripe charge or transaction fee

This document is the engineering record for the approved legal release. The owner
approved the exact PR #88 documents and authorised publication on 15 September 2026.
That approval does not authorise customer data, Credits, checkout or Stripe customer
billing.

## Terms acceptance implementation

The authenticated API exposes `GET` and `POST /api/v1/legal/terms-acceptance`.
Only an active organisation administrator may submit the explicit authority and Terms
acceptance. The checkbox is initially unchecked and the submit control remains
disabled until selected. The Terms link is contractual; the Privacy Policy link is
presented as notice and is not described as a separate agreement.

The server-owned event records the organisation, accepting user, UTC timestamp,
bounded context, exact Terms release identity and effective date, plus the Privacy
Notice identity and presentation time. It stores no browser, device, network address,
legal-document body or other customer content. Trial start and first paid Checkout
fail before commercial/provider side effects until the current event exists.

The release registry is pinned to the exact owner-approved canonical copy:

| Document | Status/version | Canonical content SHA-256 | Effective date |
| --- | --- | --- | --- |
| Terms & Conditions | `approved` / `2026-09-15` | `0c4fea346d5f4774a92819b1a8be1e83dcb1289d2650acce0bafc5f400cea3f7` | `2026-09-15` |
| Privacy Policy | `approved` / `2026-09-15` | `c707fa92f6dcd2dd4657a60fe96dce9f04bd805a15112cd224fa740fbc6cc1d5` | `2026-09-15` |

Production acceptance is available for this release and production preflight must
report `terms_acceptance_release=pass`. Each fingerprint is recomputed from the
canonical Markdown bytes, and the public legal status and server registry change
together. An organisation administrator must create a new acceptance event for this
exact approved release; a draft or retired event is never reused as final acceptance.

## Provider reconciliation for final owner review

This record reconciles the actual production control planes inspected during WO-054.
Do not convert a configured-but-disabled capability into a claim that it receives
Customer Data. For every provider below and every additional provider found before
publication, record:

1. enabled/disabled status and exact Oryntela purpose;
2. contracting entity, account/tenant/project reference (non-secret) and exact
   products/features/payment methods;
3. customer-content storage region, processing locations and applicable support or
   control-plane locations;
4. current Terms/DPA/subprocessor-list URLs and their checked/version dates;
5. data categories sent, provider retention/training settings and deletion path;
6. the matching Privacy disclosure text and owner approval reference; and
7. synthetic configuration evidence. Never include credentials, customer content or
   full provider payloads.

| Provider | Current production state | Current official-location research | Remaining release evidence |
| --- | --- | --- | --- |
| DigitalOcean | **ACTIVE** — production web, API, worker, PostgreSQL and private Spaces storage are deployed in Sydney; TLS/DNS and production authentication smoke passed. | App Platform supports `SYD`. DigitalOcean says processing can occur in the selected region and at service-provider locations; its current all-services list includes AWS (USA—Washington), Cloudflare (USA—California) and Traversal (USA—New York). Do not claim Australia-only. | Owner approval recorded 15 September 2026; preserve non-secret resource and region evidence. |
| AWS | **ACTIVE** — private encrypted S3 backup target in `ap-southeast-2`, versioning/encryption and 14-day lifecycle are configured; the daily 3:30 AM schedule is healthy and a named restore proof completed. | AWS says the customer chooses content-storage regions and it does not move or replicate content outside them except for initiated services or legal requirements. Account, billing, security and support processing can still occur elsewhere, so the disclosure must not say all AWS processing is Australian. | Owner approval recorded 15 September 2026; preserve lifecycle, least-privilege, key-cleanup and restore evidence. |
| Clerk | **ACTIVE** — the production instance and Pro workspace provide Oryntela identity, organisation access and session security. | Clerk currently states that regional residency/region selection is not offered and data is hosted on US infrastructure. Likely customer identity/session processing country: **United States**. | Owner approval recorded 15 September 2026; preserve production-instance, domain, session/deletion and plan evidence. |
| Zoho | **ACTIVE** — existing Oryntela business and support email, including MX/SPF/DKIM/DMARC, is preserved. | Zoho identifies an Australian entity/data centre and maps Australian accounts to `accounts.zoho.com.au`. Product-specific subprocessors vary and some features can activate additional providers. | Owner approval recorded 15 September 2026; preserve the actual account endpoint and enabled-product evidence. |
| Stripe | **ACTIVE CONTROL PLANE / CUSTOMER BILLING DISABLED** — Australian account `acct_1UFXmNEAHCYYkWOg`, six exact GST-inclusive recurring AUD Prices, webhook `we_1UFYbZEAHCYYkWOgz2zpW3Ox` and bounded portal `bpc_1UFYdFEAHCYYkWOg309ZjGMV` are configured; encrypted runtime-only secrets are bound to the production API and worker; read-only live preflight passes. The owner completed Stripe's Services Agreement certification on 15 September 2026; Stripe reports no active verification tasks and Payments/Payouts active. Billing and Credits remain disabled, and no customer, charge or subscription exists. | Stripe's current list says affiliates depend on business/end-customer location and services. Its processors include AWS in the **United States** and support providers in the **United States, Ireland, Colombia, Malaysia, Philippines, India, United Kingdom and Japan**; payment/fraud providers vary with enabled methods. These are potential locations, not proof every provider receives Oryntela data. | Owner approval recorded 15 September 2026; confirm exact payment methods immediately before the separate billing gate. |
| OpenAI | Conditional external AI; **not approved or activated for production** | API data is not used for training by default unless opted in. Default abuse-monitoring retention varies by endpoint and is commonly up to 30 days. The Australian endpoint can provide regional storage for eligible approved projects, but the current table says processing is not regional. OpenAI's API subprocessor list spans Australia and multiple overseas countries; exact routing cannot be inferred from repository code. | Exact organisation/project/model/endpoints, global or approved `au.api.openai.com` setting, MAM/ZDR eligibility, `store` behaviour, training opt-out, applicable processor countries, DPA and owner approval. |

Official sources checked for this mechanism:

- [DigitalOcean App Platform availability](https://docs.digitalocean.com/products/app-platform/details/availability/), [DPA](https://www.digitalocean.com/legal/data-processing-agreement) and [subprocessors](https://www.digitalocean.com/trust/subprocessors)
- [AWS S3 regional endpoints](https://docs.aws.amazon.com/general/latest/gr/s3.html) and [data privacy FAQ](https://aws.amazon.com/compliance/data-privacy-faq/)
- [Clerk security/residency statement](https://clerk.com/security) and [DPA](https://clerk.com/legal/dpa)
- [Zoho Australian data-centre mapping](https://help.zoho.com/portal/en/kb/accounts/manage-your-zoho-account/articles/data-center-for-zoho-account), [group entities](https://www.zoho.com/en-uk/privacy/zoho-group.html) and [product-specific subprocessors](https://www.zoho.com/privacy/sub-processors.html?zredirect=f)
- [Stripe DPA FAQ](https://stripe.com/legal/dpa/faqs) and [service providers, subprocessors and affiliates](https://stripe.com/legal/service-providers)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data) and [subprocessor list](https://openai.com/policies/sub-processor-list/)

### Optional providers remain conditional

| Capability/provider | Current launch disclosure state |
| --- | --- |
| Prospect provider (Apollo adapter candidate) | **DISABLED — exclude from current receiving-provider disclosures.** Add only after exact provider activation, data-rights/privacy review, owner approval and synthetic proof. |
| Microsoft 365 / Graph | **DISABLED — exclude from current receiving-provider disclosures.** |
| Google Workspace / Gmail / Calendar | **DISABLED — exclude from current receiving-provider disclosures.** |
| HubSpot | **DISABLED — exclude from current receiving-provider disclosures.** |
| Salesforce | **DISABLED — exclude from current receiving-provider disclosures.** |

If any optional capability or an unlisted monitoring, analytics, support, CDN or
security provider is activated before launch, stop finalisation, add its exact facts
to the table and update the Privacy Policy. Disabled code/adapters do not receive data
and must not be represented as doing so.

## Retention and provider owner decisions

The owner approved the following positions on 11 September 2026:

- **Application retention: 90 days** for the existing retention-eligible content
  setting. Keep the implemented domain-specific expiry/deletion rules and active
  canonical-record lifecycle; do not claim that every record is automatically
  deleted at 90 days. Billing, Credit, security and acceptance evidence continue to
  follow their separately approved lifecycle and organisation deletion fails closed
  where a separate accounting decision is required.
- **Backup rotation: 14 days** for daily encrypted portable database/object backups,
  including current/noncurrent object versions and delete markers. Keep the separate
  key, daily freshness alert, 24-hour RPO/four-hour internal RTO objective and named
  restore proof.
- **Provider-list principle:** before Privacy Policy publication, reconcile the
  policy against only the providers actually enabled for production. Disabled
  providers remain conditional and must not be represented as actively receiving
  customer information.

These are recorded approvals. WO-054 production evidence now shows the independent
backup lifecycle and named restore proof implementing the 14-day decision. The
operational-log window remains a separate engineering configuration and the Policy
does not convert it into a universal retention promise. Recheck the production
settings and provider list immediately before the first customer is authorised.

## Validation evidence

The final owner-approved release gate completed locally on 15 September 2026:

- root format, lint and TypeScript typecheck passed;
- Vitest passed 367 tests across 81 files;
- Playwright passed 92 tests, including both legal pages at desktop and 390px,
  indexable metadata, keyboard navigation and exact effective-date/version content;
- the Next.js production build passed;
- Ruff format/check and mypy passed (287 source files);
- the focused legal-acceptance module passed 10 tests and the full pytest suite
  passed 1,339 tests with 14 environment-dependent skips;
- Alembic upgraded the working PostgreSQL database to `0064_deauthorisation`,
  reported no drift and the API distribution build passed;
- the canonical SHA-256 regression test matched both exact Markdown documents;
- the repository secret/prohibited-path audit and `git diff --check` passed; and
- the DigitalOcean production template still sets both
  `API_FEATURE_BILLING_ENABLED=false` and `API_FEATURE_CREDITS_ENABLED=false`.

All testing used synthetic local data. No production service, customer data, account
activation or paid resource was used.

Review captures: [approved Terms page](../07-sprints/assets/wo-054/legal-terms-approved-desktop.png),
[approved Privacy page](../07-sprints/assets/wo-054/legal-privacy-approved-desktop.png),
[desktop acceptance](../07-sprints/assets/wo-054/terms-acceptance-desktop.png) and
[390px acceptance](../07-sprints/assets/wo-054/terms-acceptance-mobile-390.png).

## Publication and billing boundary

The owner completed the first two steps on 15 September 2026. The release sequence is:

1. **COMPLETE:** validate the final-review copy and present the exact Terms and
   Privacy Policy to the owner;
2. **COMPLETE:** obtain explicit approval of both exact documents, effective date
   `2026-09-15` and production publication;
3. remove the draft presentation, set final document
   versions and date, compute and bind the canonical SHA-256 fingerprints, and update
   the server release registry as one atomic release;
4. merge/deploy and run the named public-link, acceptance and production-preflight
   proof while `API_FEATURE_BILLING_ENABLED=false`; and
5. treat any later customer checkout enablement as a separate explicit owner gate.
