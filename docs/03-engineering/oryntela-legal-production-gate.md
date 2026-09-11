# Oryntela legal production gate

- **Checked:** 11 September 2026 (Australia/Sydney)
- **Terms/Privacy state:** owner-review draft; not effective, published or approved for production
- **External legal engagement:** none, by owner decision
- **Production state:** not activated; no customer data and no spend in this work

This document is the engineering handoff for durable Terms acceptance and the final
provider/retention reconciliation. The owner decisions recorded below do not approve
PR #88, publish either legal document or authorise production activity.

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

The draft/test release registry is pinned to the canonical legal Markdown on PR #88
at commit `49761341636f310ade1c42bf25a4699bdbf758c3`:

| Document | Status/version | Canonical content SHA-256 | Effective date |
| --- | --- | --- | --- |
| Terms & Conditions | `draft` / `owner-review-draft-v1` | `9425fe5c0d056e7669ee1fc8e3f977a5cd7d639ce775d36926bb89de54330652` | none |
| Privacy Policy | `draft` / `owner-review-draft-v1` | `31cbce440f61c97f033c8cca75b252f56a21832cc8b8585387e553327f681c22` | none |

Production acceptance is unavailable and production preflight reports
`terms_acceptance_release=fail`. Final approval must create a production version and
date, verify each fingerprint from the canonical Markdown bytes, update the public
legal status and server registry together, and prove the links and acceptance event
against that one release. Never reuse a draft event as final acceptance.

## Final provider reconciliation mechanism

Complete this record from the actual production control planes immediately before the
Privacy Policy is finalised. Do not copy proposal values into an approved column.
For every provider below and every additional provider found in the deployed
configuration, record:

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

| Provider | Current repository/launch state | Current official-location research to reconcile | Final evidence required |
| --- | --- | --- | --- |
| DigitalOcean | Proposed primary Sydney hosting; **not activated** | App Platform supports `SYD`. DigitalOcean says processing can occur in the selected region and at service-provider locations; its current all-services list includes AWS (USA—Washington), Cloudflare (USA—California) and Traversal (USA—New York). Do not claim Australia-only. | Exact App Platform, PostgreSQL and Spaces account/resource IDs; `syd`/`syd1` proof; enabled add-ons; DPA and subprocessor version; disclosure approval. |
| AWS | Proposed independent encrypted S3 backup only; **not activated** | S3 supports Sydney `ap-southeast-2`; AWS says the customer chooses content-storage regions and it does not move or replicate content outside them except for initiated services or legal requirements. Account, billing, security and support processing still require contract review, so the disclosure must not say all AWS processing is Australian. | Exact account/bucket, `ap-southeast-2`, replication-off, lifecycle, least privilege, DPA/subprocessor documents, restore proof and owner approval. |
| Clerk | Proposed production identity; **production instance not activated** | Clerk currently states that regional residency/region selection is not offered and data is hosted on US infrastructure. Likely customer identity/session processing country: **United States**. | Exact production instance, contracting entity/plan, enabled identity features and subprocessors, session/deletion configuration, US transfer disclosure and owner approval. |
| Zoho | Business/support email is selected and configured; no production customer onboarding | Zoho identifies an Australian entity/data centre and maps Australian accounts to `accounts.zoho.com.au`. Product-specific subprocessors vary and some features can activate additional providers. Likely primary country is **Australia only if the actual account endpoint confirms it**; list every applicable Zoho Mail/Accounts subprocessor country from the live product selection. | Actual account data-centre endpoint, exact Zoho products/features (including MFA/SMS and support), contracting entity, subprocessor export, retention/deletion behaviour and final disclosure. |
| Stripe | Live billing engineering exists; account, prices, webhook and portal are **not activated** | Stripe's current list says affiliates depend on business/end-customer location and services. Its processors include AWS in the **United States** and support providers in the **United States, Ireland, Colombia, Malaysia, Philippines, India, United Kingdom and Japan**; payment/fraud providers vary with enabled methods. These are potential locations, not proof every provider receives Oryntela data. | Exact Australian account/controller, Checkout/Billing/Payments configuration and methods, enabled fraud/support features, applicable entities/countries, DPA/subprocessor date and approved disclosure. |
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

These are recorded approvals, not proof that a target configuration implements them.
The operational-log window remains a separate unresolved owner choice. Target backup
configuration, actual provider enablement and final Privacy wording must still be
checked against the approvals before publication or production activation.

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

## Pull-request sequence

PR #88 remains open and draft. The acceptance PR is independently based on current
`main` and keeps the production release disabled. Recommended order:

1. review and merge the acceptance productionisation PR while its draft/test identity
   and production preflight failure remain in place;
2. capture actual production account facts, reconcile the enabled provider list and
   resolve the still-unapproved operational-log window;
3. rebase/update PR #88 on the resulting `main`, lock final content, version,
   effective date and canonical hashes in one reviewed change; and
4. only after explicit final publication approval, merge PR #88 and run the named
   target legal-link/acceptance/preflight proof. Production activation and WO-045
   remain separate owner gates.
