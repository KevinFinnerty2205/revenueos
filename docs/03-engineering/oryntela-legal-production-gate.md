# Oryntela legal production gate

- **Checked:** 15 September 2026 (Australia/Sydney)
- **Stripe control-plane update:** 15 September 2026 (Australia/Sydney)
- **Terms/Privacy state:** substantive positions approved; exact final text, release identity, effective date and publication remain owner actions
- **External legal engagement:** none, by owner decision
- **Production state:** core infrastructure active; customer billing, customer data
  and public launch not activated; no Stripe charge or transaction fee

This document is the engineering handoff for final legal publication. The owner
decisions recorded below do not approve the final release, publish either legal
document, authorise customer data or enable Stripe customer billing.

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

The refreshed draft/test release registry is pinned to the canonical review copy:

| Document | Status/version | Canonical content SHA-256 | Effective date |
| --- | --- | --- | --- |
| Terms & Conditions | `draft` / `owner-review-draft-v1` | `9425fe5c0d056e7669ee1fc8e3f977a5cd7d639ce775d36926bb89de54330652` | none |
| Privacy Policy | `draft` / `owner-review-draft-v2` | `3026606e1eecf522b41ef6bd3008be3be3f0a6f55b30e3aa26f717ba33aeb115` | none |

Production acceptance remains unavailable and production preflight reports
`terms_acceptance_release=fail`. Final approval must create a production version and
date, verify each fingerprint from the canonical Markdown bytes, update the public
legal status and server registry together, and prove the links and acceptance event
against that one release. Never reuse a draft event as final acceptance.

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
| DigitalOcean | **ACTIVE** — production web, API, worker, PostgreSQL and private Spaces storage are deployed in Sydney; TLS/DNS and production authentication smoke passed. | App Platform supports `SYD`. DigitalOcean says processing can occur in the selected region and at service-provider locations; its current all-services list includes AWS (USA—Washington), Cloudflare (USA—California) and Traversal (USA—New York). Do not claim Australia-only. | Preserve non-secret resource/region evidence and obtain final owner approval for the disclosure text. |
| AWS | **ACTIVE** — private encrypted S3 backup target in `ap-southeast-2`, versioning/encryption and 14-day lifecycle are configured; the daily 3:30 AM schedule is healthy and a named restore proof completed. | AWS says the customer chooses content-storage regions and it does not move or replicate content outside them except for initiated services or legal requirements. Account, billing, security and support processing can still occur elsewhere, so the disclosure must not say all AWS processing is Australian. | Preserve lifecycle, least-privilege, key-cleanup and restore evidence; obtain final owner approval for the disclosure text. |
| Clerk | **ACTIVE** — the production instance and Pro workspace provide Oryntela identity, organisation access and session security. | Clerk currently states that regional residency/region selection is not offered and data is hosted on US infrastructure. Likely customer identity/session processing country: **United States**. | Preserve production-instance, domain, session/deletion and plan evidence; obtain final owner approval for the US transfer disclosure. |
| Zoho | **ACTIVE** — existing Oryntela business and support email, including MX/SPF/DKIM/DMARC, is preserved. | Zoho identifies an Australian entity/data centre and maps Australian accounts to `accounts.zoho.com.au`. Product-specific subprocessors vary and some features can activate additional providers. | Preserve the actual account endpoint and enabled-product evidence; obtain final owner approval without making an Australia-only claim. |
| Stripe | **ACTIVE CONTROL PLANE / CUSTOMER BILLING DISABLED** — Australian account `acct_1UFXmNEAHCYYkWOg`, six exact GST-inclusive recurring AUD Prices, webhook `we_1UFYbZEAHCYYkWOgz2zpW3Ox` and bounded portal `bpc_1UFYdFEAHCYYkWOg309ZjGMV` are configured; encrypted runtime-only secrets are bound to the production API and worker; read-only live preflight passes. The owner completed Stripe's Services Agreement certification on 15 September 2026; Stripe reports no active verification tasks and Payments/Payouts active. Billing and Credits remain disabled, and no customer, charge or subscription exists. | Stripe's current list says affiliates depend on business/end-customer location and services. Its processors include AWS in the **United States** and support providers in the **United States, Ireland, Colombia, Malaysia, Philippines, India, United Kingdom and Japan**; payment/fraud providers vary with enabled methods. These are potential locations, not proof every provider receives Oryntela data. | Confirm exact payment methods immediately before the separate billing gate and obtain final owner approval for the disclosure text. |
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

The isolated local gate completed on 11 September 2026:

- root format, lint and TypeScript typecheck passed;
- Vitest passed 358 tests across 79 files;
- Playwright passed 90 tests, including the 390px, keyboard, focus, unchecked
control and exact-payload acceptance coverage;
- the Next.js production build passed;
- Ruff format/check and mypy passed (286 source files);
- pytest passed 1,317 tests with 13 environment-dependent skips;
- Alembic upgraded the working PostgreSQL database to `0063_terms_acceptance`,
  reported no drift and the API distribution build passed;
- a disposable empty PostgreSQL database upgraded through all 63 revisions, reported
  no drift, and showed 174 tables with enabled and forced RLS;
- the dedicated PostgreSQL tests passed for cross-tenant RLS, immutable evidence,
  concurrent acceptance by two administrators, the acceptance/trial race and exact
  acceptance binding on Checkout;
- the 1,749-file repository secret/prohibited-path audit, pnpm vulnerability audit,
  locked production Python dependency audit and `git diff --check` passed.

All testing used synthetic local data. No production service, customer data, account
activation or paid resource was used.

Review captures: [desktop acceptance](../07-sprints/assets/wo-054/terms-acceptance-desktop.png)
and [390px acceptance](../07-sprints/assets/wo-054/terms-acceptance-mobile-390.png).

## Final publication sequence

PR #88 remains draft and customer billing remains disabled. The next boundary is:

1. validate this refreshed final-review copy and present the exact Terms and Privacy
   Policy to the owner;
2. obtain the owner’s explicit approval of both exact documents and one effective
   date;
3. in a reviewed follow-up, remove the draft presentation, set final document
   versions and date, compute and bind the canonical SHA-256 fingerprints, and update
   the server release registry as one atomic release;
4. merge/deploy and run the named public-link, acceptance and production-preflight
   proof while `API_FEATURE_BILLING_ENABLED=false`; and
5. treat any later customer checkout enablement as a separate explicit owner gate.
